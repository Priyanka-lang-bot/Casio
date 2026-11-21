"""Account management and privacy: change name or password, download all
your data, delete your account, and load demo data."""
import datetime as dt
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel, Field, field_validator, model_validator
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.audit import audit
from app.config import get_settings
from app.db import get_db
from app.deps import get_current_session, get_current_user
from app.finance import to_json
from app.importers.pipeline import ImportRejected, start_import
from app.models import (
    Asset,
    Budget,
    CategorizationRule,
    Category,
    CoachMessage,
    ExpenseItem,
    FinancialGoal,
    FinancialSnapshot,
    GoalContribution,
    ImportBatch,
    IncomeSource,
    Liability,
    MonthlyReport,
    RecurringPayment,
    Transaction,
    User,
    UserSession,
)
from app.routers.profile import get_or_create_profile
from app.schemas import _check_password
from app.security import hash_password, verify_password

router = APIRouter(prefix="/account", tags=["account"])
DEMO_FILE = Path(__file__).resolve().parent.parent / "demo" / "sample-6-months.csv"


class NameIn(BaseModel):
    full_name: str = Field(min_length=1, max_length=100)

    @field_validator("full_name")
    @classmethod
    def clean(cls, v: str) -> str:
        v = " ".join(v.split())
        if not v:
            raise ValueError("Please enter your full name.")
        return v


class PasswordChangeIn(BaseModel):
    current_password: str
    new_password: str
    confirm_password: str

    @field_validator("new_password")
    @classmethod
    def strong(cls, v: str) -> str:
        return _check_password(v)

    @model_validator(mode="after")
    def match(self):
        if self.new_password != self.confirm_password:
            raise ValueError("password_mismatch")
        return self


class DeleteIn(BaseModel):
    password: str
    confirm: str

    @field_validator("confirm")
    @classmethod
    def typed_delete(cls, v: str) -> str:
        if v.strip().upper() != "DELETE":
            raise ValueError("Type DELETE to confirm.")
        return v


@router.patch("/name")
def change_name(data: NameIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    user.full_name = data.full_name
    audit(db, "account.rename", user.id)
    db.commit()
    return {"id": str(user.id), "email": user.email, "full_name": user.full_name}


@router.post("/password")
def change_password(data: PasswordChangeIn, session: UserSession = Depends(get_current_session), db: Session = Depends(get_db)):
    user = session.user
    if not verify_password(user.password_hash, data.current_password):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Your current password isn't right.")
    user.password_hash = hash_password(data.new_password)
    # Sign out every other browser; keep this one.
    db.execute(delete(UserSession).where(UserSession.user_id == user.id, UserSession.id != session.id))
    audit(db, "account.password_change", user.id)
    db.commit()
    return {"message": "Password changed. Other devices have been signed out."}


def _rows(db: Session, model, user: User, *cols):
    out = []
    for obj in db.scalars(select(model).where(model.user_id == user.id)):
        out.append({c: getattr(obj, c) for c in cols})
    return out


@router.get("/export")
def export_data(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Everything CASIO stores about you, as one JSON file."""
    profile = get_or_create_profile(db, user)
    cats = {c.id: c.name for c in db.scalars(select(Category))}
    txs = [
        {"date": t.occurred_on, "type": t.type, "amount": t.amount, "currency": t.currency, "description": t.description,
         "merchant": t.merchant, "category": cats.get(t.category_id), "category_source": t.category_source,
         "notes": t.notes, "source": t.source, "balance_after": t.balance_after}
        for t in db.scalars(select(Transaction).where(Transaction.user_id == user.id).order_by(Transaction.occurred_on))
    ]
    data = {
        "exported_at": dt.datetime.now(dt.UTC),
        "account": {"full_name": user.full_name, "email": user.email, "created_at": user.created_at, "currency": profile.currency},
        "transactions": txs,
        "income_sources": _rows(db, IncomeSource, user, "name", "amount", "frequency"),
        "regular_costs": _rows(db, ExpenseItem, user, "name", "amount", "frequency", "kind"),
        "assets": _rows(db, Asset, user, "name", "kind", "value"),
        "debts": _rows(db, Liability, user, "name", "kind", "balance", "monthly_payment", "interest_rate"),
        "budgets": [{"category": b.category.name, "amount": b.amount} for b in db.scalars(select(Budget).where(Budget.user_id == user.id))],
        "goals": _rows(db, FinancialGoal, user, "name", "kind", "target_amount", "saved_amount", "target_date", "monthly_contribution", "status"),
        "goal_contributions": _rows(db, GoalContribution, user, "goal_id", "amount", "contributed_on", "note"),
        "learned_rules": [{"match": r.match_type, "pattern": r.pattern, "category": cats.get(r.category_id), "active": r.active}
                          for r in db.scalars(select(CategorizationRule).where(CategorizationRule.user_id == user.id))],
        "recurring_payments": _rows(db, RecurringPayment, user, "name", "kind", "frequency", "amount", "status", "usage"),
        "imports": _rows(db, ImportBatch, user, "source_type", "original_filename", "status", "rows_imported", "created_at"),
        "money_model_snapshots": _rows(db, FinancialSnapshot, user, "month", "data"),
        "monthly_reports": _rows(db, MonthlyReport, user, "month", "narrative", "data"),
        "coach_conversation": _rows(db, CoachMessage, user, "role", "content", "created_at"),
    }
    audit(db, "account.export", user.id)
    db.commit()
    import json

    body = json.dumps(to_json(data), default=str, indent=2, ensure_ascii=False)
    return Response(body, media_type="application/json",
                    headers={"Content-Disposition": f'attachment; filename="casio-data-{dt.date.today()}.json"'})


@router.post("/delete")
def delete_account(data: DeleteIn, response: Response, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Permanently deletes the account and all its data (every table cascades from users)."""
    if not verify_password(user.password_hash, data.password):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "That password isn't right.")
    uid = user.id
    db.delete(user)
    audit(db, "account.delete", None, "user", uid)
    db.commit()
    response.delete_cookie(get_settings().session_cookie_name, path="/")
    return {"message": "Your account and all its data have been deleted."}


@router.post("/demo-data")
def load_demo_data(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Imports a realistic 6-month sample statement so every feature has
    something to show. Only for accounts with no transactions yet."""
    has = db.scalar(select(func.count()).select_from(Transaction).where(Transaction.user_id == user.id))
    if has:
        raise HTTPException(status.HTTP_409_CONFLICT, "Sample data can only be added to an account with no transactions.")
    from app.routers.imports import confirm

    try:
        batch = start_import(db, user, "csv", "casio-sample-6-months.csv", DEMO_FILE.read_bytes())
    except ImportRejected as exc:  # pragma: no cover - the bundled file is known good
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc))
    db.commit()
    done = confirm(batch.id, user, db)
    audit(db, "account.demo_data", user.id, "import_batch", done.id)
    db.commit()
    return {"import_batch_id": str(done.id), "rows_imported": done.rows_imported}
