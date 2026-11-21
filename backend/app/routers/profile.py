"""Financial profile: what the user tells CASIO about their money
(income, regular expenses, things they own, debts). These are the inputs
to the Living Money Model."""
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.audit import audit
from app.db import get_db
from app.deps import get_current_user
from app.finance import profile_summary, to_json
from app.models import Asset, ExpenseItem, IncomeSource, Liability, Transaction, User, UserProfile
from app.schemas import (
    AssetIn,
    AssetOut,
    ExpenseItemIn,
    ExpenseItemOut,
    IncomeSourceIn,
    IncomeSourceOut,
    LiabilityIn,
    LiabilityOut,
    ProfileOut,
    ProfileUpdate,
)

router = APIRouter(prefix="/profile", tags=["profile"])


def get_or_create_profile(db: Session, user: User) -> UserProfile:
    profile = db.get(UserProfile, user.id)
    if profile is None:
        profile = UserProfile(user_id=user.id)
        db.add(profile)
        db.commit()
    return profile


@router.get("", response_model=ProfileOut)
def read_profile(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return get_or_create_profile(db, user)


@router.patch("", response_model=ProfileOut)
def update_profile(data: ProfileUpdate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    profile = get_or_create_profile(db, user)
    if data.currency and data.currency != profile.currency:
        has_tx = db.scalar(select(func.count()).select_from(Transaction).where(Transaction.user_id == user.id))
        if has_tx:
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                "You can't change currency after adding transactions, because old amounts would be mislabelled.",
            )
        profile.currency = data.currency
    if data.country is not None:
        profile.country = data.country
    audit(db, "profile.update", user.id, "user_profile", user.id)
    db.commit()
    return profile


@router.get("/summary")
def summary(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Monthly plan and net worth calculated from the profile (estimates)."""
    rows = {m: db.scalars(select(m).where(m.user_id == user.id)).all() for m in (IncomeSource, ExpenseItem, Asset, Liability)}
    result = profile_summary(rows[IncomeSource], rows[ExpenseItem], rows[Asset], rows[Liability])
    result["currency"] = get_or_create_profile(db, user).currency
    return to_json(result)


def _crud(path: str, model, schema_in: type[BaseModel], schema_out: type[BaseModel], label: str) -> None:
    """Adds list/create/update/delete endpoints for one kind of profile entry.
    Every query is filtered by the signed-in user, so nobody can see or touch
    someone else's entries (they get 404, as if it doesn't exist)."""

    def _get_owned(db: Session, user: User, item_id: uuid.UUID):
        item = db.scalar(select(model).where(model.id == item_id, model.user_id == user.id))
        if item is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, f"That {label} wasn't found.")
        return item

    @router.get(f"/{path}", response_model=list[schema_out], name=f"list_{path}")
    def list_items(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
        return db.scalars(select(model).where(model.user_id == user.id).order_by(model.created_at)).all()

    @router.post(f"/{path}", response_model=schema_out, status_code=201, name=f"create_{path}")
    def create_item(data: schema_in, user: User = Depends(get_current_user), db: Session = Depends(get_db)):  # type: ignore[valid-type]
        item = model(user_id=user.id, **data.model_dump())
        db.add(item)
        db.flush()
        audit(db, f"{path}.create", user.id, model.__tablename__, item.id)
        db.commit()
        return item

    @router.put(f"/{path}/{{item_id}}", response_model=schema_out, name=f"update_{path}")
    def update_item(
        item_id: uuid.UUID, data: schema_in, user: User = Depends(get_current_user), db: Session = Depends(get_db)  # type: ignore[valid-type]
    ):
        item = _get_owned(db, user, item_id)
        for k, v in data.model_dump().items():
            setattr(item, k, v)
        audit(db, f"{path}.update", user.id, model.__tablename__, item.id)
        db.commit()
        return item

    @router.delete(f"/{path}/{{item_id}}", status_code=204, name=f"delete_{path}")
    def delete_item(item_id: uuid.UUID, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
        item = _get_owned(db, user, item_id)
        db.delete(item)
        audit(db, f"{path}.delete", user.id, model.__tablename__, item_id)
        db.commit()


_crud("income", IncomeSource, IncomeSourceIn, IncomeSourceOut, "income source")
_crud("expenses", ExpenseItem, ExpenseItemIn, ExpenseItemOut, "expense")
_crud("assets", Asset, AssetIn, AssetOut, "asset")
_crud("liabilities", Liability, LiabilityIn, LiabilityOut, "debt")
