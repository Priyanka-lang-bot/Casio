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


UNUSUAL_WINDOW_DAYS = 45
UNUSUAL_BASELINE_DAYS = 180
UNUSUAL_RATIO = Decimal("2.5")
UNUSUAL_MIN_GAP = Decimal("500")


@router.get("/insights/unusual")
def unusual_spending(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Recent single payments that are much larger than usual for their
    category. "Usual" is the median payment in that category over the six
    months before the window. All ACTUAL data; nothing is estimated."""
    latest = db.scalar(select(func.max(Transaction.occurred_on)).where(Transaction.user_id == user.id))
    if latest is None:
        return {"window_start": None, "items": [], "method": ""}
    latest = min(latest, dt.date.today())
    window_start = latest - dt.timedelta(days=UNUSUAL_WINDOW_DAYS)
    base_start = window_start - dt.timedelta(days=UNUSUAL_BASELINE_DAYS)
    rows = db.scalars(
        select(Transaction).where(
            Transaction.user_id == user.id, Transaction.type == "expense",
            Transaction.occurred_on >= base_start, Transaction.occurred_on <= latest,
        )
    ).all()
    baseline: dict = {}
    for t in rows:
        if t.occurred_on < window_start:
            baseline.setdefault(t.category_id, []).append(t.amount)
    items = []
    for t in rows:
        if t.occurred_on < window_start:
            continue
        prior = baseline.get(t.category_id) or []
        if len(prior) < 5:
            continue  # not enough history to say what's usual
        typical = money(sorted(prior)[len(prior) // 2])
        if t.amount >= typical * UNUSUAL_RATIO and t.amount - typical >= UNUSUAL_MIN_GAP:
            out = to_out(t)
            items.append({
                "transaction": to_json(out),
                "typical": str(typical),
                "times": str(money(t.amount / typical)) if typical else None,
                "count_before": len(prior),
            })
    items.sort(key=lambda i: Decimal(i["transaction"]["amount"]), reverse=True)
    return {
        "window_start": window_start.isoformat(),
        "as_of": latest.isoformat(),
        "items": items[:12],
        "method": (
            f"A payment is flagged when it is at least {UNUSUAL_RATIO}× the usual payment in its category and at least "
            f"{UNUSUAL_MIN_GAP:.0f} more. Usual = the middle (median) payment in that category over the {UNUSUAL_BASELINE_DAYS} days "
            f"before the last {UNUSUAL_WINDOW_DAYS} days. Categories with fewer than 5 earlier payments are skipped."
        ),
    }
