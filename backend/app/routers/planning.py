"""Budgets, goals, the Living Money Model and the what-if simulator."""
import datetime as dt
import uuid
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app import coach, planning
from app.audit import audit
from app.db import get_db
from app.deps import get_current_user
from app.finance import to_json
from app.models import GOAL_KINDS, Budget, Category, FinancialGoal, FinancialSnapshot, GoalContribution, User
from app.routers.profile import get_or_create_profile
from app.routers.transactions import _check_category

router = APIRouter(tags=["planning"])
MAX_MONEY = Decimal("999999999999.99")
MONTH = Query(None, pattern=r"^\d{4}-\d{2}$")


def _currency(db: Session, user: User) -> str:
    return get_or_create_profile(db, user).currency


# ---------------------------------------------------------------------------
# Budgets
# ---------------------------------------------------------------------------
class BudgetIn(BaseModel):
    category_id: uuid.UUID
    amount: Decimal = Field(gt=0, le=MAX_MONEY, decimal_places=2)


class BudgetUpdate(BaseModel):
    amount: Decimal = Field(gt=0, le=MAX_MONEY, decimal_places=2)


@router.get("/budgets")
def list_budgets(month: str | None = MONTH, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    data = planning.budget_status(db, user, planning.parse_month(month))
    data["currency"] = _currency(db, user)
    return to_json(data)


@router.post("/budgets", status_code=201)
def create_budget(data: BudgetIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _check_category(db, user, data.category_id, "expense")
    cat = db.get(Category, data.category_id)
    if cat.kind != "expense":
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Budgets are for spending categories.")
    existing = db.scalar(select(Budget).where(Budget.user_id == user.id, Budget.category_id == data.category_id))
    if existing:
        raise HTTPException(status.HTTP_409_CONFLICT, f"You already have a budget for {cat.name}. Edit that one instead.")
    b = Budget(user_id=user.id, category_id=data.category_id, amount=data.amount)
    db.add(b)
    db.flush()
    audit(db, "budget.create", user.id, "budget", b.id)
    db.commit()
    return {"id": str(b.id)}


@router.patch("/budgets/{budget_id}")
def update_budget(budget_id: uuid.UUID, data: BudgetUpdate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    b = db.scalar(select(Budget).where(Budget.id == budget_id, Budget.user_id == user.id))
    if b is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "That budget wasn't found.")
    b.amount = data.amount
    audit(db, "budget.update", user.id, "budget", b.id)
    db.commit()
    return {"id": str(b.id)}


@router.delete("/budgets/{budget_id}", status_code=204)
def delete_budget(budget_id: uuid.UUID, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    b = db.scalar(select(Budget).where(Budget.id == budget_id, Budget.user_id == user.id))
    if b is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "That budget wasn't found.")
    db.delete(b)
    audit(db, "budget.delete", user.id, "budget", budget_id)
    db.commit()


# ---------------------------------------------------------------------------
# Goals
# ---------------------------------------------------------------------------
class GoalIn(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    kind: str = "other"
    target_amount: Decimal = Field(gt=0, le=MAX_MONEY, decimal_places=2)
    saved_amount: Decimal = Field(default=Decimal("0"), ge=0, le=MAX_MONEY, decimal_places=2)
    target_date: dt.date | None = None
    monthly_contribution: Decimal | None = Field(default=None, ge=0, le=MAX_MONEY, decimal_places=2)
    priority: int = Field(default=2, ge=1, le=3)

    @field_validator("name")
    @classmethod
    def clean_name(cls, v: str) -> str:
        v = " ".join(v.split())
        if not v:
            raise ValueError("Please give the goal a name.")
        return v

    @field_validator("kind")
    @classmethod
    def valid_kind(cls, v: str) -> str:
        if v not in GOAL_KINDS:
            raise ValueError("Please choose a goal type from the list.")
        return v

    @field_validator("target_date")
    @classmethod
    def future_date(cls, v: dt.date | None) -> dt.date | None:
        if v is not None and v <= dt.date.today():
            raise ValueError("Pick a date in the future.")
        return v


class GoalUpdate(GoalIn):
    status: str = "active"

    @field_validator("status")
    @classmethod
    def valid_status(cls, v: str) -> str:
        if v not in ("active", "achieved", "paused"):
            raise ValueError("Unknown status.")
        return v

    @field_validator("target_date")
    @classmethod
    def future_date(cls, v):  # editing an old goal may keep its past date
        return v


class ContributionIn(BaseModel):
    amount: Decimal = Field(le=MAX_MONEY, decimal_places=2)
    contributed_on: dt.date | None = None
    note: str | None = Field(default=None, max_length=200)

    @field_validator("amount")
    @classmethod
    def not_zero(cls, v: Decimal) -> Decimal:
        if v == 0:
            raise ValueError("Enter an amount (use a minus sign for money taken out).")
        return v


def _goal_out(g: FinancialGoal) -> dict:
    return {
        "id": g.id, "name": g.name, "kind": g.kind, "target_amount": g.target_amount, "saved_amount": g.saved_amount,
        "target_date": g.target_date, "priority": g.priority, "status": g.status, "created_at": g.created_at,
        **planning.goal_status(g),
    }


def _get_goal(db: Session, user: User, goal_id: uuid.UUID) -> FinancialGoal:
    g = db.scalar(select(FinancialGoal).where(FinancialGoal.id == goal_id, FinancialGoal.user_id == user.id))
    if g is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "That goal wasn't found.")
    return g


@router.get("/goals")
def list_goals(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    goals = db.scalars(select(FinancialGoal).where(FinancialGoal.user_id == user.id)
                       .order_by(FinancialGoal.status, FinancialGoal.priority, FinancialGoal.created_at)).all()
    model = planning.money_model(db, user)
    active = [g for g in goals if g.status == "active"]
    return to_json({
        "currency": _currency(db, user),
        "goals": [_goal_out(g) for g in goals],
        "totals": {
            "target": sum((g.target_amount for g in active), Decimal(0)),
            "saved": sum((g.saved_amount for g in active), Decimal(0)),
            "monthly_contributions": model["planned"]["goal_contributions"],
            "monthly_surplus": model["monthly_surplus"], "plan_basis": model["plan_basis"],
        },
        "suggested_emergency_fund": (model["monthly_spending"] * 3) if model["monthly_spending"] > 0 else None,
    })


@router.post("/goals", status_code=201)
def create_goal(data: GoalIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    g = FinancialGoal(user_id=user.id, status="active", **data.model_dump())
    db.add(g)
    db.flush()
    audit(db, "goal.create", user.id, "goal", g.id)
    db.commit()
    db.refresh(g)
    return to_json(_goal_out(g))


@router.put("/goals/{goal_id}")
def update_goal(goal_id: uuid.UUID, data: GoalUpdate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    g = _get_goal(db, user, goal_id)
    for k, v in data.model_dump().items():
        setattr(g, k, v)
    audit(db, "goal.update", user.id, "goal", g.id)
    db.commit()
    db.refresh(g)
    return to_json(_goal_out(g))


@router.delete("/goals/{goal_id}", status_code=204)
def delete_goal(goal_id: uuid.UUID, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    g = _get_goal(db, user, goal_id)
    db.delete(g)
    audit(db, "goal.delete", user.id, "goal", goal_id)
    db.commit()


@router.get("/goals/{goal_id}/contributions")
def list_contributions(goal_id: uuid.UUID, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    g = _get_goal(db, user, goal_id)
    rows = db.scalars(select(GoalContribution).where(GoalContribution.goal_id == g.id)
                      .order_by(GoalContribution.contributed_on.desc(), GoalContribution.created_at.desc())).all()
    return to_json([{"id": c.id, "amount": c.amount, "contributed_on": c.contributed_on, "note": c.note} for c in rows])


@router.post("/goals/{goal_id}/contributions", status_code=201)
def add_contribution(goal_id: uuid.UUID, data: ContributionIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    g = _get_goal(db, user, goal_id)
    if g.saved_amount + data.amount < 0:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "You can't take out more than has been saved.")
    db.add(GoalContribution(user_id=user.id, goal_id=g.id, amount=data.amount,
                            contributed_on=data.contributed_on or dt.date.today(), note=data.note))
    g.saved_amount = g.saved_amount + data.amount
    if g.saved_amount >= g.target_amount and g.status == "active":
        g.status = "achieved"
    elif g.saved_amount < g.target_amount and g.status == "achieved":
        g.status = "active"
    audit(db, "goal.contribute", user.id, "goal", g.id)
    db.commit()
    db.refresh(g)
    return to_json(_goal_out(g))


# ---------------------------------------------------------------------------
# Living Money Model
# ---------------------------------------------------------------------------
def save_snapshot(db: Session, user: User, model: dict) -> None:
    first = planning.month_start(dt.date.today())
    data = to_json(planning.snapshot_data(model))
    db.execute(
        insert(FinancialSnapshot).values(user_id=user.id, month=first, data=data)
        .on_conflict_do_update(constraint="uq_snapshot_user_month", set_={"data": data, "updated_at": dt.datetime.now(dt.UTC)})
    )


@router.get("/money-model")
def money_model(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Recomputed on every visit, so it always reflects the latest
    transactions, corrections and profile changes. This month's snapshot is
    refreshed at the same time."""
    model = planning.money_model(db, user)
    save_snapshot(db, user, model)
    db.commit()
    model["currency"] = _currency(db, user)
    snaps = db.scalars(select(FinancialSnapshot).where(FinancialSnapshot.user_id == user.id).order_by(FinancialSnapshot.month)).all()
    model["snapshots"] = [{"month": f"{s.month:%Y-%m}", **s.data} for s in snaps][-12:]
    return to_json(model)


# ---------------------------------------------------------------------------
# What-if simulator
# ---------------------------------------------------------------------------
class ChangeIn(BaseModel):
    type: str
    category: str | None = Field(default=None, max_length=60)
    label: str | None = Field(default=None, max_length=60)
    percent: Decimal | None = Field(default=None, ge=-100, le=1000)
    amount: Decimal | None = Field(default=None, ge=-MAX_MONEY, le=MAX_MONEY)
    goal_id: uuid.UUID | None = None

    @field_validator("type")
    @classmethod
    def valid_type(cls, v: str) -> str:
        if v not in planning.CHANGE_TYPES:
            raise ValueError("Unknown change type.")
        return v


class SimulateIn(BaseModel):
    changes: list[ChangeIn] = Field(min_length=1, max_length=10)


class ParseIn(BaseModel):
    question: str = Field(min_length=3, max_length=500)


@router.post("/what-if")
def what_if(data: SimulateIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    result = planning.simulate(db, user, [c.model_dump(mode="json") for c in data.changes])
    result["currency"] = _currency(db, user)
    return to_json(result)


@router.post("/what-if/ask")
def what_if_ask(data: ParseIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Plain-English question -> structured changes (AI if enabled, otherwise
    CASIO's built-in rules) -> deterministic simulation."""
    cats = sorted({c.name for c in db.scalars(select(Category).where(Category.kind == "expense"))})
    changes = coach.ai_parse_what_if(data.question, cats)
    parser = "ai"
    if not changes:
        changes = coach.parse_what_if(data.question)
        parser = "rules"
    if not changes:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "I couldn't turn that into a scenario. Try something like “What if I cut dining by 30%?” or "
            "“What if my rent goes up by ₹3,000?”, or build it with the options below.",
        )
    result = planning.simulate(db, user, changes)
    result["currency"] = _currency(db, user)
    result["parsed_by"] = parser
    result["parsed_changes"] = changes
    return to_json(result)
