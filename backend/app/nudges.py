"""Proactive nudges: short, specific messages when spending drifts away
from the plan. Deterministic checks over the user's own data.

Each nudge has a dedupe key (for example "budget_over:<budget>:2026-11"), so
the same situation never nags twice and a dismissed nudge stays dismissed.
When a condition stops being true, its nudge is quietly retired."""
import datetime as dt
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.formatting import fmt_money
from app.models import FinancialGoal, FinancialNudge, RecurringAlert, Transaction, User
from app.planning import (
    budget_status,
    category_names,
    category_spend,
    goal_status,
    latest_activity,
    month_bounds,
    month_start,
    money_model,
    usual_month,
)

SPIKE_RATIO = Decimal("1.5")
SPIKE_MIN = Decimal("1000")
SEVERITY_ORDER = {"critical": 0, "warning": 1, "info": 2, "good": 3}


def _find(db: Session, user: User, currency: str) -> list[dict]:
    as_of = latest_activity(db, user)
    first = month_start(as_of)
    mon = f"{first:%Y-%m}"
    m = lambda v: fmt_money(v, currency)  # noqa: E731
    out: list[dict] = []

    def add(kind, severity, key, title, message, link):
        out.append({"kind": kind, "severity": severity, "dedupe_key": key, "title": title, "message": message, "link": link})

    # 1. Budgets
    bs = budget_status(db, user, first)
    for b in bs["items"]:
        name = b["category_name"]
        if b["state"] == "over":
            add("budget_over", "critical", f"budget_over:{b['id']}:{mon}", f"{name} budget exceeded",
                f"You've spent {m(b['spent'])} on {name} this month, {m(-b['remaining'])} over your {m(b['amount'])} budget.", "/budgets")
        elif b["state"] == "near":
            add("budget_near", "warning", f"budget_near:{b['id']}:{mon}", f"{b['percent_used']:.0f}% of your {name} budget used",
                f"{m(b['remaining'])} left for {name} this month. Slowing down now keeps you on plan.", "/budgets")
        elif b["state"] == "on_pace_to_exceed":
            add("budget_pace", "info", f"budget_pace:{b['id']}:{mon}", f"{name} spending is running ahead",
                f"At this pace you'll spend about {m(b['projected'])} on {name} by month end, above your {m(b['amount'])} budget. This is a forecast, not a certainty.", "/budgets")

    # 2. Unusual category spending vs the usual month
    usual = usual_month(db, user, first)["by_category"]
    if usual:
        cats = category_names(db)
        for cid, amt in category_spend(db, user, *month_bounds(first)).items():
            base = usual.get(cid)
            if cid is None or not base or amt < SPIKE_MIN or amt < base * SPIKE_RATIO:
                continue
            name = cats[cid].name if cid in cats else "Uncategorised"
            if name in ("Transfers",):
                continue
            pct = (amt / base - 1) * 100
            add("spending_spike", "warning", f"spike:{cid}:{mon}", f"{name} is {pct:.0f}% above usual",
                f"{m(amt)} so far this month compared with a usual {m(base)}. Worth a look in Transactions.", "/transactions")

    # 3. Spending more than income this month
    mm = money_model(db, user)
    inc, exp = mm["actual"]["this_month_income"], mm["actual"]["this_month_spending"]
    if inc > 0 and exp > inc:
        add("negative_month", "warning", f"negative:{mon}", "Spending is above income this month",
            f"You've spent {m(exp)} against {m(inc)} coming in. The difference comes from savings.", "/overview")

    # 4. Goals
    today = dt.date.today()
    for g in db.scalars(select(FinancialGoal).where(FinancialGoal.user_id == user.id, FinancialGoal.status == "active")):
        st = goal_status(g, today)
        if st["state"] == "behind":
            add("goal_behind", "warning", f"goal_behind:{g.id}:{mon}", f"“{g.name}” is behind schedule",
                f"At {m(st['monthly_contribution'])} a month you'd finish around {st['projected_finish']:%b %Y}, after your {g.target_date:%b %Y} target. "
                f"About {m(st['needed_per_month'])} a month would get you there.", "/goals")
        elif st["state"] == "no_plan" and st["needed_per_month"]:
            add("goal_no_plan", "info", f"goal_no_plan:{g.id}", f"Set a monthly amount for “{g.name}”",
                f"To reach it by {g.target_date:%b %Y} you'd need about {m(st['needed_per_month'])} a month.", "/goals")
        elif st["state"] == "achieved":
            add("goal_achieved", "good", f"goal_done:{g.id}", f"You reached “{g.name}” 🎉",
                "Mark it as achieved, or raise the target if you want to keep going.", "/goals")
    if mm["planned"]["goal_contributions"] > 0 and mm["monthly_surplus"] < mm["planned"]["goal_contributions"]:
        add("goals_unaffordable", "warning", f"goals_unaffordable:{mon}", "Your goal plan doesn't fit your usual month",
            f"Goals need {m(mm['planned']['goal_contributions'])} a month but you usually have {m(mm['monthly_surplus'])} left over.", "/what-if")

    # 5. Emergency fund
    efm = mm["emergency_fund_months"]
    if mm["monthly_spending"] > 0 and efm is not None and efm < 3:
        add("emergency_fund_low", "info", f"ef_low:{mon}", "Your emergency fund covers less than 3 months",
            f"It covers about {efm} months of spending. Many people aim for 3 to 6 months before other goals.", "/goals")

    # 6. Housekeeping: transactions CASIO wasn't sure about
    unsure = db.scalar(select(func.count()).select_from(Transaction).where(
        Transaction.user_id == user.id, Transaction.type == "expense",
        (Transaction.category_id.is_(None)) | ((Transaction.category_confidence < Decimal("0.6")) & (Transaction.category_source != "user")),
    )) or 0
    if unsure >= 3:
        add("needs_review", "info", f"needs_review:{unsure // 5}", f"{unsure} transactions need a category check",
            "Fixing them makes budgets, reports and the coach more accurate. Your fixes can become rules.", "/transactions")

    # 7. Positive reinforcement
    if inc > 0 and exp < inc and as_of.day >= 20 and not any(o["severity"] == "critical" for o in out):
        rate = (inc - exp) / inc * 100
        if rate >= 20:
            add("good_month", "good", f"good_month:{mon}", f"You're saving {rate:.0f}% of income this month",
                "Nice work. Consider moving the extra into a goal before it gets spent.", "/goals")
    return out


def refresh(db: Session, user: User, currency: str) -> None:
    found = _find(db, user, currency)
    keys = {f["dedupe_key"] for f in found}
    for f in found:
        db.execute(
            insert(FinancialNudge).values(user_id=user.id, active=True, **f)
            .on_conflict_do_update(constraint="uq_nudge_user_key", set_={"active": True, "title": f["title"], "message": f["message"]})
        )
    for n in db.scalars(select(FinancialNudge).where(FinancialNudge.user_id == user.id, FinancialNudge.active.is_(True))):
        if n.dedupe_key not in keys:
            n.active = False


def current(db: Session, user: User, limit: int = 20) -> list[FinancialNudge]:
    rows = db.scalars(select(FinancialNudge).where(
        FinancialNudge.user_id == user.id, FinancialNudge.active.is_(True), FinancialNudge.dismissed_at.is_(None)
    )).all()
    return sorted(rows, key=lambda n: (SEVERITY_ORDER.get(n.severity, 9), -n.created_at.timestamp()))[:limit]


def subscription_alert_count(db: Session, user: User) -> int:
    return db.scalar(select(func.count()).select_from(RecurringAlert).where(
        RecurringAlert.user_id == user.id, RecurringAlert.dismissed_at.is_(None))) or 0

