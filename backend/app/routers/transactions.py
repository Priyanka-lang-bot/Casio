import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import extract, func, or_, select
from sqlalchemy.orm import Session

from app.audit import audit
from app.db import get_db
from app.deps import get_current_user
from app.models import Category, Transaction, User
from app.routers.profile import get_or_create_profile
from app.schemas import CategoryOut, TransactionIn, TransactionOut, TransactionPage, TransactionUpdate

router = APIRouter(tags=["transactions"])


def to_out(t: Transaction) -> TransactionOut:
    out = TransactionOut.model_validate(t)
    out.category_name = t.category.name if t.category else None
    return out


def _check_category(db: Session, user: User, category_id: uuid.UUID | None, tx_type: str) -> None:
    if category_id is None:
        return
    cat = db.scalar(
        select(Category).where(Category.id == category_id, or_(Category.user_id.is_(None), Category.user_id == user.id))
    )
    if cat is None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Please choose a category from the list.")
    if cat.kind != "transfer" and cat.kind != tx_type:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            f"“{cat.name}” is an {cat.kind} category. Pick one that matches this {tx_type}.",
        )


@router.get("/categories", response_model=list[CategoryOut])
def list_categories(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    cats = db.scalars(
        select(Category)
        .where(or_(Category.user_id.is_(None), Category.user_id == user.id))
        .order_by(Category.kind, Category.name)
    ).all()
    return [CategoryOut(id=c.id, name=c.name, kind=c.kind, is_custom=c.user_id is not None) for c in cats]


@router.get("/transactions", response_model=TransactionPage)
def list_transactions(
    type: str | None = Query(None, pattern="^(income|expense|transfer)$"),
    category_id: uuid.UUID | None = None,
    month: str | None = Query(None, pattern=r"^\d{4}-\d{2}$", description="YYYY-MM"),
    q: str | None = Query(None, max_length=100),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    filters = [Transaction.user_id == user.id]
    if type:
        filters.append(Transaction.type == type)
    if category_id:
        filters.append(Transaction.category_id == category_id)
    if month:
        y, m = map(int, month.split("-"))
        filters += [extract("year", Transaction.occurred_on) == y, extract("month", Transaction.occurred_on) == m]
    if q:
        filters.append(Transaction.description.ilike(f"%{q.replace('%', r'\%').replace('_', r'\_')}%"))
    total = db.scalar(select(func.count()).select_from(Transaction).where(*filters))
    rows = db.scalars(
        select(Transaction)
        .where(*filters)
        .order_by(Transaction.occurred_on.desc(), Transaction.created_at.desc())
        .limit(limit)
        .offset(offset)
    ).all()
    return TransactionPage(items=[to_out(t) for t in rows], total=total or 0)


@router.post("/transactions", response_model=TransactionOut, status_code=201)
def create_transaction(data: TransactionIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if data.client_request_id:
        existing = db.scalar(
            select(Transaction).where(
                Transaction.user_id == user.id, Transaction.client_request_id == data.client_request_id
            )
        )
        if existing:  # same request sent twice (double-click, retry): don't add it again
            return to_out(existing)
    _check_category(db, user, data.category_id, data.type)
    t = Transaction(
        user_id=user.id,
        currency=get_or_create_profile(db, user).currency,
        source="manual",
        category_source="user" if data.category_id else None,
        **data.model_dump(),
    )
    db.add(t)
    db.flush()
    audit(db, "transaction.create", user.id, "transaction", t.id, source="manual")
    db.commit()
    db.refresh(t)
    return to_out(t)


def _get_owned(db: Session, user: User, tx_id: uuid.UUID) -> Transaction:
    t = db.scalar(select(Transaction).where(Transaction.id == tx_id, Transaction.user_id == user.id))
    if t is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "That transaction wasn't found.")
    return t


@router.put("/transactions/{tx_id}", response_model=TransactionOut)
def update_transaction(
    tx_id: uuid.UUID, data: TransactionUpdate, user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    t = _get_owned(db, user, tx_id)
    _check_category(db, user, data.category_id, data.type)
    if data.category_id != t.category_id:
        t.category_source = "user" if data.category_id else None
        t.category_confidence = None
        t.category_reason = None
    for k, v in data.model_dump(exclude={"client_request_id"}).items():
        setattr(t, k, v)
    audit(db, "transaction.update", user.id, "transaction", t.id)
    db.commit()
    db.refresh(t)
    return to_out(t)


@router.delete("/transactions/{tx_id}", status_code=204)
def delete_transaction(tx_id: uuid.UUID, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    t = _get_owned(db, user, tx_id)
    db.delete(t)
    audit(db, "transaction.delete", user.id, "transaction", tx_id)
    db.commit()


