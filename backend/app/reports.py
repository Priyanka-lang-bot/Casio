"""Monthly financial review: the numbers, worked out deterministically.
The AI (if enabled) only writes the friendly opening paragraph."""
import datetime as dt
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy import func, literal_column, select
from sqlalchemy.orm import Session

from app.finance import ZERO, money, monthly_amount
from app.formatting import fmt_money
from app.models import FinancialGoal, GoalContribution, RecurringPayment, Transaction, User
from app.planning import (
    add_months,
    budget_status,
    category_names,
    category_spend,
    goal_status,
    month_bounds,
    month_totals,
)


def _rate(inc: Decimal, exp: Decimal):
    return ((inc - exp) / inc * 100).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP) if inc > 0 else None


def months_with_data(db: Session, user: User) -> list[str]:
    m = func.to_char(Transaction.occurred_on, literal_column("'YYYY-MM'"))
    rows = db.execute(select(m).where(Transaction.user_id == user.id).group_by(m).order_by(m.desc())).all()
    return [r[0] for r in rows]


def build(db: Session, user: User, first: dt.date, currency: str) -> dict:
    m = lambda v: fmt_money(v, currency)  # noqa: E731
    start, end = month_bounds(first)
    prev = add_months(first, -1)
    inc, exp = month_totals(db, user, first)
    pinc, pexp = month_totals(db, user, prev)
    cats = category_names(db)
    now = category_spend(db, user, start, end)
    before = category_spend(db, user, *month_bounds(prev))

    categories = []
    for cid in set(now) | set(before):
        a, b = now.get(cid, ZERO), before.get(cid, ZERO)
        categories.append({
            "category": cats[cid].name if cid in cats else "Uncategorised", "amount": a, "previous": b,
            "change": money(a - b), "change_percent": ((a - b) / b * 100).quantize(Decimal("0.1")) if b > 0 else None,
            "share_percent": (a / exp * 100).quantize(Decimal("0.1")) if exp > 0 else None,
        })
    categories.sort(key=lambda c: -c["amount"])

    budgets = budget_status(db, user, first)
    tx_count = db.scalar(select(func.count()).select_from(Transaction).where(
        Transaction.user_id == user.id, Transaction.occurred_on >= start, Transaction.occurred_on < end)) or 0
    biggest = db.scalars(select(Transaction).where(
        Transaction.user_id == user.id, Transaction.type == "expense", Transaction.occurred_on >= start, Transaction.occurred_on < end,
    ).order_by(Transaction.amount.desc()).limit(5)).all()

    goals = []
    for g in db.scalars(select(FinancialGoal).where(FinancialGoal.user_id == user.id).order_by(FinancialGoal.priority)):
        added = db.scalar(select(func.coalesce(func.sum(GoalContribution.amount), 0)).where(
            GoalContribution.goal_id == g.id, GoalContribution.contributed_on >= start, GoalContribution.contributed_on < end)) or 0
        st = goal_status(g)
        goals.append({"name": g.name, "saved_amount": g.saved_amount, "target_amount": g.target_amount,
                      "added_this_month": money(Decimal(added)), "progress_percent": st["progress_percent"], "state": st["state"]})

    subs = db.scalars(select(RecurringPayment).where(RecurringPayment.user_id == user.id, RecurringPayment.status == "active")).all()
    sub_monthly = money(sum((monthly_amount(r.amount, r.frequency) for r in subs), ZERO))
    price_rises = [
        {"name": r.name, "old": c["old"], "new": c["new"], "date": c["date"]}
        for r in subs for c in (r.price_changes or [])
        if start.isoformat() <= c["date"] < end.isoformat() and Decimal(c["new"]) > Decimal(c["old"])
    ]
    new_subs = [r.name for r in subs if start <= r.first_paid_on < end]

    # Highlights: the sentences a person would want to read first.
    hl = []
    if tx_count == 0:
        hl.append("There are no transactions recorded for this month yet.")
    else:
        net = inc - exp
        if inc > 0:
            hl.append(f"You received {m(inc)} and spent {m(exp)}, {'keeping' if net >= 0 else 'overspending by'} {m(abs(net))}"
                      + (f" ({_rate(inc, exp)}% of income saved)." if net >= 0 else "."))
        else:
            hl.append(f"You spent {m(exp)}. No income was recorded this month.")
        if pexp > 0:
            d = exp - pexp
            if abs(d) >= pexp * Decimal("0.05"):
                hl.append(f"Spending was {m(abs(d))} {'higher' if d > 0 else 'lower'} than last month.")
            else:
                hl.append("Spending was about the same as last month.")
        risers = [c for c in categories if c["previous"] > 0 and c["change"] > 0 and c["change_percent"] and c["change_percent"] >= 25 and c["amount"] >= 500]
        if risers:
            c = max(risers, key=lambda c: c["change"])
            hl.append(f"{c['category']} rose the most: {m(c['amount'])}, up {c['change_percent']:.0f}% from {m(c['previous'])}.")
        if categories and categories[0]["amount"] > 0:
            hl.append(f"Your biggest category was {categories[0]['category']} at {m(categories[0]['amount'])}.")
    over = [b for b in budgets["items"] if b["state"] == "over"]
    kept = [b for b in budgets["items"] if b["state"] in ("ok", "near", "on_pace_to_exceed") and b["spent"] <= b["amount"]]
    if budgets["items"]:
        if over:
            hl.append(f"Over budget: {', '.join(b['category_name'] for b in over)}. Within budget: {len(kept)} of {len(budgets['items'])}.")
        else:
            hl.append(f"You stayed within all {len(budgets['items'])} budgets.")
    for p in price_rises:
        hl.append(f"{p['name']} went up from {m(Decimal(p['old']))} to {m(Decimal(p['new']))}.")
    if new_subs:
        hl.append(f"New regular payment{'s' if len(new_subs) > 1 else ''}: {', '.join(new_subs)}.")
    added = sum((g["added_this_month"] for g in goals), ZERO)
    if added > 0:
        hl.append(f"You put {m(added)} towards your goals.")

    # One practical suggestion, from the data.
    tips = []
    if over:
        tips.append(f"Look at {over[0]['category_name']} first: it went {m(-over[0]['remaining'])} over budget.")
    elif not budgets["items"] and budgets["suggestions"]:
        s = budgets["suggestions"][0]
        tips.append(f"Try a {m(s['suggested_amount'])} budget for {s['category_name']}, close to what you usually spend.")
    if inc > 0 and exp > inc:
        tips.append("Spending was above income. Pick one category to trim next month.")
    if not goals:
        tips.append("Set a goal (an emergency fund is a good first one) so leftover money has a job.")

    return {
        "month": f"{first:%Y-%m}", "currency": currency, "basis": "actual",
        "summary": {"income": inc, "spending": exp, "net": money(inc - exp), "savings_rate": _rate(inc, exp), "transactions": tx_count},
        "previous": {"month": f"{prev:%Y-%m}", "income": pinc, "spending": pexp, "net": money(pinc - pexp), "savings_rate": _rate(pinc, pexp)},
        "categories": categories,
        "budgets": {"items": budgets["items"], "total_budget": budgets["total_budget"], "total_spent": budgets["total_spent"]},
        "goals": goals,
        "subscriptions": {"monthly_total": sub_monthly, "count": len(subs), "price_rises": price_rises, "new": new_subs},
        "largest_expenses": [{"date": t.occurred_on, "description": t.description[:80], "amount": t.amount,
                              "category": t.category.name if t.category else None} for t in biggest],
        "highlights": hl,
        "suggestions": tips,
    }
