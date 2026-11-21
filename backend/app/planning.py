"""Planning maths: budgets, goals, the Living Money Model and the what-if
simulator. Plain deterministic Python with Decimal, like finance.py.

Every figure carries a basis so the screen can label it:
  actual        - calculated from recorded transactions
  user_estimate - what the user typed into their Financial Profile
  planned       - budgets and goal contributions the user set
  forecast      - a projection; never a promise

The AI coach calls these functions as tools. It never does maths itself."""
import calendar
import datetime as dt
import uuid
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy import case, func, literal_column, select
from sqlalchemy.orm import Session

from app.finance import ZERO, money, monthly_amount, profile_summary
from app.models import (
    Asset,
    Budget,
    Category,
    ExpenseItem,
    FinancialGoal,
    IncomeSource,
    Liability,
    RecurringPayment,
    Transaction,
    User,
)

HISTORY_MONTHS = 3  # "usual" spending = average of the last 3 full months with data
PROJECTION_MONTHS = 12


# ---------------------------------------------------------------------------
# Dates
# ---------------------------------------------------------------------------
def month_start(d: dt.date) -> dt.date:
    return d.replace(day=1)


def add_months(d: dt.date, n: int) -> dt.date:
    m = d.month - 1 + n
    y, m = d.year + m // 12, m % 12 + 1
    return dt.date(y, m, min(d.day, calendar.monthrange(y, m)[1]))


def month_bounds(first: dt.date) -> tuple[dt.date, dt.date]:
    return first, add_months(first, 1)


def parse_month(value: str | None, default: dt.date | None = None) -> dt.date:
    if value:
        y, m = map(int, value.split("-"))
        return dt.date(y, m, 1)
    return month_start(default or dt.date.today())


def months_between(a: dt.date, b: dt.date) -> int:
    """Whole months from a to b (b later), counting a part month as one."""
    n = (b.year - a.year) * 12 + (b.month - a.month)
    if b.day > a.day:
        n += 1
    return max(n, 0)


def latest_activity(db: Session, user: User) -> dt.date:
    """The last date CASIO has data for (capped at today). Used so that an
    imported statement from earlier in the year still gets sensible checks."""
    latest = db.scalar(select(func.max(Transaction.occurred_on)).where(Transaction.user_id == user.id))
    today = dt.date.today()
    return min(latest, today) if latest else today


# ---------------------------------------------------------------------------
# Actuals from transactions
# ---------------------------------------------------------------------------
def _sum(type_: str):
    return func.coalesce(func.sum(case((Transaction.type == type_, Transaction.amount), else_=0)), 0)


def month_totals(db: Session, user: User, first: dt.date) -> tuple[Decimal, Decimal]:
    start, end = month_bounds(first)
    inc, exp = db.execute(
        select(_sum("income"), _sum("expense")).where(
            Transaction.user_id == user.id, Transaction.occurred_on >= start, Transaction.occurred_on < end
        )
    ).one()
    return money(Decimal(inc)), money(Decimal(exp))


def category_spend(db: Session, user: User, start: dt.date, end: dt.date) -> dict[uuid.UUID | None, Decimal]:
    rows = db.execute(
        select(Transaction.category_id, func.sum(Transaction.amount))
        .where(
            Transaction.user_id == user.id, Transaction.type == "expense",
            Transaction.occurred_on >= start, Transaction.occurred_on < end,
        )
        .group_by(Transaction.category_id)
    ).all()
    return {cid: money(Decimal(a)) for cid, a in rows}


def history_months(db: Session, user: User, before: dt.date, count: int = HISTORY_MONTHS) -> list[dt.date]:
    """The last `count` full months before `before` that have any transactions."""
    m = func.date_trunc(literal_column("'month'"), Transaction.occurred_on)
    rows = db.execute(
        select(m).where(Transaction.user_id == user.id, Transaction.occurred_on < before)
        .group_by(m).order_by(m.desc()).limit(count)
    ).all()
    return [r[0].date() if isinstance(r[0], dt.datetime) else r[0] for r in rows]


def usual_month(db: Session, user: User, as_of: dt.date) -> dict:
    """Average monthly income, spending and spending per category, from the
    last few full months before `as_of`'s month. Basis: actual."""
    months = history_months(db, user, month_start(as_of))
    if not months:
        return {"months": [], "income": ZERO, "expenses": ZERO, "by_category": {}}
    n = Decimal(len(months))
    inc = exp = ZERO
    by_cat: dict[uuid.UUID | None, Decimal] = {}
    for m in months:
        i, e = month_totals(db, user, m)
        inc, exp = inc + i, exp + e
        for cid, amt in category_spend(db, user, *month_bounds(m)).items():
            by_cat[cid] = by_cat.get(cid, ZERO) + amt
    return {
        "months": months,
        "income": money(inc / n),
        "expenses": money(exp / n),
        "by_category": {cid: money(a / n) for cid, a in by_cat.items()},
    }


def category_names(db: Session) -> dict[uuid.UUID, Category]:
    return {c.id: c for c in db.scalars(select(Category))}


# ---------------------------------------------------------------------------
# Budgets
# ---------------------------------------------------------------------------
WARN_AT = Decimal("0.8")


def budget_status(db: Session, user: User, first: dt.date) -> dict:
    """Each budget with what's been spent this month, what's left, and a
    month-end forecast (current month only)."""
    start, end = month_bounds(first)
    today = dt.date.today()
    is_current = start <= today < end
    days = calendar.monthrange(start.year, start.month)[1]
    elapsed = today.day if is_current else days
    spent = category_spend(db, user, start, end)
    usual = usual_month(db, user, start)["by_category"]
    cats = category_names(db)

    items = []
    for b in db.scalars(select(Budget).where(Budget.user_id == user.id)):
        s = spent.get(b.category_id, ZERO)
        pct = (s / b.amount * 100).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)
        projected = money(s / elapsed * days) if is_current and elapsed > 0 else s
        if s > b.amount:
            state = "over"
        elif s >= b.amount * WARN_AT:
            state = "near"
        elif is_current and projected > b.amount:
            state = "on_pace_to_exceed"
        else:
            state = "ok"
        items.append({
            "id": b.id, "category_id": b.category_id, "category_name": b.category.name, "amount": b.amount,
            "spent": s, "remaining": money(b.amount - s), "percent_used": pct,
            "projected": projected, "projected_basis": "forecast" if is_current else "actual",
            "usual_spend": usual.get(b.category_id), "state": state,
        })
    items.sort(key=lambda i: (-i["percent_used"], i["category_name"]))

    budgeted = {i["category_id"] for i in items}
    unbudgeted = sorted(
        ({"category_id": cid, "category_name": cats[cid].name if cid in cats else "Uncategorised", "spent": amt}
         for cid, amt in spent.items() if cid not in budgeted),
        key=lambda x: -x["spent"],
    )
    # Suggestions: categories with usual spending but no budget, rounded up to the next ₹100.
    suggestions = []
    for cid, amt in sorted(usual.items(), key=lambda kv: -kv[1]):
        if cid is None or cid in budgeted or cid not in cats or cats[cid].kind != "expense" or amt < 100:
            continue
        suggestions.append({
            "category_id": cid, "category_name": cats[cid].name, "usual_spend": amt,
            "suggested_amount": (amt / 100).to_integral_value(rounding="ROUND_CEILING") * 100,
        })
    total_budget = sum((i["amount"] for i in items), ZERO)
    total_spent = sum((i["spent"] for i in items), ZERO)
    return {
        "month": f"{start:%Y-%m}", "is_current_month": is_current, "days_in_month": days, "days_elapsed": elapsed,
        "items": items, "unbudgeted": unbudgeted, "suggestions": suggestions[:6],
        "total_budget": money(total_budget), "total_spent": money(total_spent),
        "total_remaining": money(total_budget - total_spent),
    }


# ---------------------------------------------------------------------------
# Goals
# ---------------------------------------------------------------------------
def goal_status(g: FinancialGoal, today: dt.date | None = None, monthly: Decimal | None = None) -> dict:
    """Progress and a forecast finish date. `monthly` overrides the goal's
    own contribution (used by the what-if simulator)."""
    today = today or dt.date.today()
    remaining = max(g.target_amount - g.saved_amount, ZERO)
    progress = min((g.saved_amount / g.target_amount * 100), Decimal(100)).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)
    contribution = g.monthly_contribution if monthly is None else monthly
    months_left = months_between(today, g.target_date) if g.target_date else None
    needed = None
    if g.target_date and remaining > 0:
        needed = money(remaining / months_left) if months_left else remaining
    months_to_finish = None
    finish = None
    if remaining == 0:
        months_to_finish, finish = 0, today
    elif contribution and contribution > 0:
        months_to_finish = int((remaining / contribution).to_integral_value(rounding="ROUND_CEILING"))
        finish = add_months(today, months_to_finish)
    if remaining == 0 or g.status == "achieved":
        state = "achieved"
    elif g.status == "paused":
        state = "paused"
    elif not g.target_date:
        state = "no_date"
    elif g.target_date < today:
        state = "past_due"
    elif finish is None:
        state = "no_plan"
    elif finish <= g.target_date:
        state = "on_track"
    else:
        state = "behind"
    return {
        "remaining": money(remaining), "progress_percent": progress, "months_left": months_left,
        "needed_per_month": needed, "monthly_contribution": contribution,
        "months_to_finish": months_to_finish, "projected_finish": finish, "state": state,
    }


# ---------------------------------------------------------------------------
# Living Money Model
# ---------------------------------------------------------------------------
def money_model(db: Session, user: User) -> dict:
    """Everything CASIO knows about the user's money, with each figure's
    basis kept separate. Nothing here mixes an estimate with an actual."""
    uid = user.id
    incomes = db.scalars(select(IncomeSource).where(IncomeSource.user_id == uid)).all()
    expenses = db.scalars(select(ExpenseItem).where(ExpenseItem.user_id == uid)).all()
    assets = db.scalars(select(Asset).where(Asset.user_id == uid)).all()
    liabilities = db.scalars(select(Liability).where(Liability.user_id == uid)).all()
    estimate = profile_summary(incomes, expenses, assets, liabilities)

    as_of = latest_activity(db, user)
    usual = usual_month(db, user, as_of)
    cats = category_names(db)
    this_inc, this_exp = month_totals(db, user, month_start(as_of))

    recurring = db.scalars(select(RecurringPayment).where(RecurringPayment.user_id == uid, RecurringPayment.status == "active")).all()
    commitments = [
        {"name": r.name, "kind": r.kind, "frequency": r.frequency, "amount": r.amount,
         "monthly": money(monthly_amount(r.amount, r.frequency)), "next_expected_on": r.next_expected_on}
        for r in sorted(recurring, key=lambda r: -r.amount)
    ]
    commitments_monthly = money(sum((c["monthly"] for c in commitments), ZERO))

    budgets = db.scalars(select(Budget).where(Budget.user_id == uid)).all()
    goals = db.scalars(select(FinancialGoal).where(FinancialGoal.user_id == uid).order_by(FinancialGoal.priority, FinancialGoal.created_at)).all()
    active_goals = [g for g in goals if g.status == "active"]
    goal_contrib = money(sum((g.monthly_contribution or ZERO for g in active_goals), ZERO))

    has_actuals = bool(usual["months"])
    # Which income/spending to plan with: what really happened if we have it,
    # otherwise what the user told us.
    if has_actuals:
        base_income, base_spend, base_basis = usual["income"], usual["expenses"], "actual"
    else:
        base_income, base_spend, base_basis = estimate["monthly_income"], estimate["monthly_total_spending"], "user_estimate"
    surplus = money(base_income - base_spend)
    free_after_goals = money(surplus - goal_contrib)

    # Forecast: savings grow by the monthly surplus (no interest, no surprises).
    start_savings = estimate["savings"]
    projection = []
    bal = start_savings
    first = month_start(add_months(as_of, 1))
    for i in range(PROJECTION_MONTHS):
        bal = money(bal + surplus)
        projection.append({"month": f"{add_months(first, i):%Y-%m}", "savings": bal})

    by_cat = sorted(
        ({"category": cats[cid].name if cid in cats else "Uncategorised", "amount": a} for cid, a in usual["by_category"].items()),
        key=lambda x: -x["amount"],
    )
    gaps = []
    if has_actuals and estimate["monthly_income"] > 0:
        diff = usual["expenses"] - estimate["monthly_total_spending"]
        if estimate["monthly_total_spending"] > 0 and abs(diff) > estimate["monthly_total_spending"] * Decimal("0.15"):
            gaps.append(
                f"You estimated spending of {estimate['monthly_total_spending']} a month, but your transactions show "
                f"about {usual['expenses']}. Consider updating your Financial Profile."
            )
        idiff = usual["income"] - estimate["monthly_income"]
        if abs(idiff) > estimate["monthly_income"] * Decimal("0.15"):
            gaps.append(
                f"Your recorded income averages {usual['income']} a month, but your profile says {estimate['monthly_income']}."
            )
    spend_for_ef = base_spend if base_spend > 0 else estimate["monthly_total_spending"]
    ef_months = (estimate["emergency_fund"] / spend_for_ef).quantize(Decimal("0.1")) if spend_for_ef > 0 else None

    return {
        "as_of": as_of,
        "currency": None,  # filled by the router
        "has_actuals": has_actuals,
        "history_months": [f"{m:%Y-%m}" for m in sorted(usual["months"])],
        "estimate": estimate,
        "actual": {
            "basis": "actual",
            "usual_monthly_income": usual["income"],
            "usual_monthly_spending": usual["expenses"],
            "usual_spending_by_category": by_cat,
            "this_month": f"{as_of:%Y-%m}",
            "this_month_income": this_inc,
            "this_month_spending": this_exp,
        },
        "planned": {
            "basis": "planned",
            "budgets_total": money(sum((b.amount for b in budgets), ZERO)),
            "budget_count": len(budgets),
            "goal_contributions": goal_contrib,
            "active_goals": len(active_goals),
        },
        "commitments": {"basis": "actual", "monthly_total": commitments_monthly, "items": commitments[:12]},
        "plan_basis": base_basis,
        "monthly_income": base_income,
        "monthly_spending": base_spend,
        "monthly_surplus": surplus,
        "free_after_goals": free_after_goals,
        "emergency_fund_months": ef_months,
        "forecast": {"basis": "forecast", "starting_savings": start_savings, "monthly_change": surplus, "months": projection},
        "gaps": gaps,
    }


def snapshot_data(model: dict) -> dict:
    """The few numbers worth comparing month to month."""
    e = model["estimate"]
    return {
        "monthly_income": model["monthly_income"], "monthly_spending": model["monthly_spending"],
        "monthly_surplus": model["monthly_surplus"], "plan_basis": model["plan_basis"],
        "net_worth": e["net_worth"], "savings": e["savings"], "emergency_fund": e["emergency_fund"],
        "total_liabilities": e["total_liabilities"], "commitments_monthly": model["commitments"]["monthly_total"],
        "goal_contributions": model["planned"]["goal_contributions"],
        "this_month_income": model["actual"]["this_month_income"],
        "this_month_spending": model["actual"]["this_month_spending"],
    }


# ---------------------------------------------------------------------------
# What-if simulator
# ---------------------------------------------------------------------------
CHANGE_TYPES = ("income_change", "category_change", "new_expense", "extra_saving", "one_time_expense")


def _apply(base: Decimal, percent: Decimal | None, amount: Decimal | None) -> Decimal:
    out = base
    if percent is not None:
        out = out * (1 + percent / 100)
    if amount is not None:
        out = out + amount
    return max(out, ZERO)


def simulate(db: Session, user: User, changes: list[dict]) -> dict:
    """Apply changes to the user's usual month and compare.

    changes: list of dicts, each with "type" in CHANGE_TYPES and:
      income_change:     percent and/or amount (+ raises, - cuts), monthly
      category_change:   category (name), percent and/or amount, monthly
      new_expense:       label, amount (monthly)
      extra_saving:      amount (monthly, set aside for goals), optional goal_id
      one_time_expense:  label, amount (happens once, next month)
    """
    model = money_model(db, user)
    cats = category_names(db)
    by_name = {c.name.lower(): c for c in cats.values()}
    as_of = model["as_of"]

    # Baseline spending lines: per category when we have actuals; otherwise the profile's items.
    lines: dict[str, Decimal] = {}
    if model["has_actuals"]:
        for row in model["actual"]["usual_spending_by_category"]:
            lines[row["category"]] = row["amount"]
    else:
        e = model["estimate"]
        if e["monthly_fixed_expenses"]:
            lines["Fixed costs"] = e["monthly_fixed_expenses"]
        if e["monthly_variable_expenses"]:
            lines["Variable costs"] = e["monthly_variable_expenses"]
        if e["monthly_debt_payments"]:
            lines["Debt payments"] = e["monthly_debt_payments"]
    base_income = model["monthly_income"]
    base_spend = sum(lines.values(), ZERO)

    new_income = base_income
    new_lines = dict(lines)
    extra_saving = ZERO
    extra_goal_id = None
    one_time = ZERO
    applied, problems = [], []

    def dec(v):
        return None if v in (None, "") else Decimal(str(v))

    for ch in changes:
        t = ch.get("type")
        pct, amt = dec(ch.get("percent")), dec(ch.get("amount"))
        if t == "income_change":
            before = new_income
            new_income = money(_apply(new_income, pct, amt))
            applied.append({"type": t, "label": "Income", "before": before, "after": new_income})
        elif t == "category_change":
            name = str(ch.get("category") or "").strip()
            cat = by_name.get(name.lower())
            label = cat.name if cat else name
            if not label:
                problems.append("A category change didn't name a category.")
                continue
            if model["has_actuals"] and cat is None:
                problems.append(f"There's no category called “{name}”.")
                continue
            before = new_lines.get(label, ZERO)
            if before == 0 and pct is not None and amt is None:
                problems.append(f"You have no usual spending on {label}, so a percentage change does nothing.")
            new_lines[label] = money(_apply(before, pct, amt))
            applied.append({"type": t, "label": label, "before": before, "after": new_lines[label]})
        elif t == "new_expense":
            label = str(ch.get("label") or "New expense")[:60]
            if not amt or amt <= 0:
                problems.append("A new expense needs an amount above zero.")
                continue
            new_lines[label] = money(new_lines.get(label, ZERO) + amt)
            applied.append({"type": t, "label": label, "before": ZERO, "after": amt})
        elif t == "extra_saving":
            if not amt or amt <= 0:
                problems.append("Extra saving needs an amount above zero.")
                continue
            extra_saving += amt
            extra_goal_id = ch.get("goal_id") or extra_goal_id
            applied.append({"type": t, "label": "Extra saving each month", "before": ZERO, "after": amt})
        elif t == "one_time_expense":
            if not amt or amt <= 0:
                problems.append("A one-off expense needs an amount above zero.")
                continue
            one_time += amt
            applied.append({"type": t, "label": str(ch.get("label") or "One-off expense")[:60], "before": ZERO, "after": amt})
        else:
            problems.append(f"Unknown change type “{t}”.")

    new_spend = sum(new_lines.values(), ZERO)
    base_surplus = money(base_income - base_spend)
    new_surplus = money(new_income - new_spend)

    def rate(inc, sur):
        return (sur / inc * 100).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP) if inc > 0 else None

    # Savings path over 12 months. Extra saving is still your money (it moves
    # into goals), so it doesn't change total savings; a one-off cost does.
    start = model["forecast"]["starting_savings"]
    first = month_start(add_months(as_of, 1))
    path = []
    b = s = start
    for i in range(PROJECTION_MONTHS):
        b = money(b + base_surplus)
        s = money(s + new_surplus - (one_time if i == 0 else ZERO))
        path.append({"month": f"{add_months(first, i):%Y-%m}", "baseline": b, "scenario": s})

    # Goals: contributions as planned; if the monthly surplus can't cover them
    # they shrink in proportion. Extra saving goes to the chosen goal (or the top-priority one).
    goals = db.scalars(
        select(FinancialGoal).where(FinancialGoal.user_id == user.id, FinancialGoal.status == "active")
        .order_by(FinancialGoal.priority, FinancialGoal.created_at)
    ).all()
    planned = sum((g.monthly_contribution or ZERO for g in goals), ZERO)

    def contributions(surplus: Decimal, extra: Decimal) -> dict:
        total = planned + extra
        scale = Decimal(1)
        if total > 0 and surplus < total:
            scale = max(surplus, ZERO) / total
        out = {}
        target = None
        if extra > 0 and goals:
            target = next((g for g in goals if str(g.id) == str(extra_goal_id)), goals[0])
        for g in goals:
            c = (g.monthly_contribution or ZERO) + (extra if target is not None and g.id == target.id else ZERO)
            out[g.id] = money(c * scale)
        return out

    today = dt.date.today()
    base_c, new_c = contributions(base_surplus, ZERO), contributions(new_surplus, extra_saving)
    goal_rows = []
    for g in goals:
        bs, ns = goal_status(g, today, base_c[g.id]), goal_status(g, today, new_c[g.id])
        delay = None
        if bs["months_to_finish"] is not None and ns["months_to_finish"] is not None:
            delay = ns["months_to_finish"] - bs["months_to_finish"]
        goal_rows.append({
            "id": g.id, "name": g.name, "target_amount": g.target_amount, "saved_amount": g.saved_amount,
            "target_date": g.target_date,
            "baseline": {"monthly": base_c[g.id], "finish": bs["projected_finish"], "months": bs["months_to_finish"], "state": bs["state"]},
            "scenario": {"monthly": new_c[g.id], "finish": ns["projected_finish"], "months": ns["months_to_finish"], "state": ns["state"]},
            "months_sooner_or_later": delay,
        })

    explanation = explain(model, base_income, new_income, base_spend, new_spend, base_surplus, new_surplus,
                          extra_saving, one_time, goal_rows, planned)
    return {
        "basis": "forecast",
        "plan_basis": model["plan_basis"],
        "has_data": base_income > 0 or base_spend > 0,
        "changes": applied,
        "problems": problems,
        "baseline": {"income": base_income, "spending": money(base_spend), "surplus": base_surplus, "savings_rate": rate(base_income, base_surplus)},
        "scenario": {"income": new_income, "spending": money(new_spend), "surplus": new_surplus, "savings_rate": rate(new_income, new_surplus),
                     "extra_saving": money(extra_saving), "one_time_expense": money(one_time)},
        "difference": {"income": money(new_income - base_income), "spending": money(new_spend - base_spend),
                       "surplus": money(new_surplus - base_surplus),
                       "after_12_months": money(path[-1]["scenario"] - path[-1]["baseline"]) if path else ZERO},
        "projection": path,
        "goals": goal_rows,
        "explanation": explanation,
        "disclaimer": "This is an estimate based on your usual month. Real life varies, so treat it as a guide, not a promise.",
    }


def _m(v: Decimal) -> str:
    from app.formatting import fmt_money

    return fmt_money(v)


def explain(model, bi, ni, bs, ns, bsur, nsur, extra, one_time, goals, planned) -> list[str]:
    """Plain-language sentences about the result. Deterministic."""
    out = []
    basis = "your recorded transactions" if model["has_actuals"] else "the estimates in your Financial Profile"
    out.append(f"Starting point (from {basis}): you usually bring in {_m(bi)} and spend {_m(bs)} a month, leaving {_m(bsur)}.")
    diff = nsur - bsur
    if diff > 0:
        out.append(f"With these changes you'd keep about {_m(diff)} more each month ({_m(diff * 12)} over a year).")
    elif diff < 0:
        out.append(f"With these changes you'd have about {_m(-diff)} less each month ({_m(-diff * 12)} over a year).")
    else:
        out.append("These changes don't alter what's left over each month.")
    if nsur < 0:
        out.append(f"Careful: you'd be spending {_m(-nsur)} more than you earn each month, which eats into savings.")
    if one_time > 0:
        out.append(f"The one-off cost of {_m(one_time)} comes straight out of your savings.")
    if extra > 0:
        if nsur >= planned + extra:
            out.append(f"Setting aside an extra {_m(extra)} a month fits within what's left over.")
        else:
            out.append(f"An extra {_m(extra)} a month is more than your leftover money can cover, so goal contributions are scaled down to what's affordable.")
    elif planned > 0 and nsur < planned <= bsur:
        out.append(f"Your goal contributions ({_m(planned)} a month) no longer fit, so goals would be funded more slowly.")
    for g in goals:
        d = g["months_sooner_or_later"]
        if d:
            out.append(f"“{g['name']}” would finish about {abs(d)} month{'s' if abs(d) != 1 else ''} {'later' if d > 0 else 'sooner'}.")
        elif g["baseline"]["months"] is None and g["scenario"]["months"] is not None:
            out.append(f"“{g['name']}” would get a finish date: around {g['scenario']['finish']:%b %Y}.")
        elif g["baseline"]["months"] is not None and g["scenario"]["months"] is None:
            out.append(f"“{g['name']}” would stall: nothing left over to put towards it.")
    return out
