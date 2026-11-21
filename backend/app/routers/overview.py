"""Numbers for the Overview dashboard. ACTUAL figures come only from
recorded transactions; PLAN figures come from the user's profile."""
import datetime as dt
from decimal import Decimal

from fastapi import APIRouter, Depends, Query
from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import get_current_user
from app.finance import ZERO, money, to_json
from app.models import Category, Transaction, User
from app.routers.profile import get_or_create_profile, summary
from app.routers.transactions import to_out

router = APIRouter(tags=["overview"])


def _month_bounds(year: int, month: int) -> tuple[dt.date, dt.date]:
    start = dt.date(year, month, 1)
    end = dt.date(year + (month == 12), month % 12 + 1, 1)
    return start, end


def _sum(type_: str):
    return func.coalesce(func.sum(case((Transaction.type == type_, Transaction.amount), else_=0)), 0)


@router.get("/overview")
def overview(
    month: str | None = Query(None, pattern=r"^\d{4}-\d{2}$"),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    today = dt.date.today()
    year, mon = map(int, month.split("-")) if month else (today.year, today.month)
    start, end = _month_bounds(year, mon)
    mine = Transaction.user_id == user.id

    income, expenses = db.execute(
        select(_sum("income"), _sum("expense")).where(mine, Transaction.occurred_on >= start, Transaction.occurred_on < end)
    ).one()
    all_income, all_expenses, tx_count = db.execute(select(_sum("income"), _sum("expense"), func.count()).where(mine)).one()

    by_category = db.execute(
        select(func.coalesce(Category.name, "Uncategorised"), func.sum(Transaction.amount))
        .select_from(Transaction)
        .outerjoin(Category, Transaction.category_id == Category.id)
        .where(mine, Transaction.type == "expense", Transaction.occurred_on >= start, Transaction.occurred_on < end)
        .group_by(Category.name)
        .order_by(func.sum(Transaction.amount).desc())
    ).all()

    # Last 6 months of income vs expenses, for the chart.
    trend = []
    y, m = year, mon
    for _ in range(6):
        s, e = _month_bounds(y, m)
        inc, exp = db.execute(
            select(_sum("income"), _sum("expense")).where(mine, Transaction.occurred_on >= s, Transaction.occurred_on < e)
        ).one()
        trend.append({"month": f"{y:04d}-{m:02d}", "income": money(Decimal(inc)), "expenses": money(Decimal(exp))})
        y, m = (y - 1, 12) if m == 1 else (y, m - 1)
    trend.reverse()

    recent = db.scalars(
        select(Transaction).where(mine).order_by(Transaction.occurred_on.desc(), Transaction.created_at.desc()).limit(5)
    ).all()

    income, expenses = Decimal(income), Decimal(expenses)
    return to_json({
        "currency": get_or_create_profile(db, user).currency,
        "month": f"{year:04d}-{mon:02d}",
        "has_transactions": tx_count > 0,
        "actual": {
            "basis": "actual",
            "month_income": money(income),
            "month_expenses": money(expenses),
            # Net for the month = Income - Expenses
            "month_net": money(income - expenses),
            "savings_rate_percent": (
                ((income - expenses) / income * 100).quantize(Decimal("0.1")) if income > ZERO else None
            ),
            # Tracked balance = all recorded income - all recorded expenses
            "tracked_balance": money(Decimal(all_income) - Decimal(all_expenses)),
        },
        "spending_by_category": [{"category": n, "amount": money(Decimal(a))} for n, a in by_category],
        "trend": trend,
        "recent_transactions": [to_out(t) for t in recent],
        "plan": summary(user=user, db=db),
    })
