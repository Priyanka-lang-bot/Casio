"""Recurring payments and subscriptions, found from transaction history.

Plain, deterministic rules (no AI, no guessing amounts):

1. Group money-out transactions by shop name.
2. Look at the gaps between payments. If most gaps are about 7, 14, 30, 91
   or 365 days, the payment repeats weekly, fortnightly, monthly,
   quarterly or yearly.
3. The amount must be steady (the same price, maybe with a price change),
   except for bills such as electricity where it naturally varies.
4. If a shop mixes a subscription with one-off purchases (Amazon Prime vs
   Amazon shopping), payments of a similar amount are checked on their own.

The next payment date is a FORECAST, not a promise. Whether a subscription
is still used is something only the user knows, so CASIO asks instead of
assuming."""
import calendar
import re
from collections import Counter
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from statistics import median

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.finance import money, monthly_amount
from app.formatting import fmt_money
from app.importers.normalize import guess_merchant
from app.learning import merchant_key
from app.models import Category, RecurringAlert, RecurringPayment, Transaction, User, UserProfile

# frequency: (typical gap in days, allowed difference, fewest payments needed, grace days before "missed")
PERIODS = {
    "weekly": (7, 2, 4, 3),
    "fortnightly": (14, 3, 3, 5),
    "monthly": (30.44, 5, 3, 7),
    "quarterly": (91.3, 10, 2, 15),
    "yearly": (365.25, 20, 2, 30),
}
LOOKBACK_DAYS = 800  # enough to see a yearly payment twice
NEW_WITHIN_DAYS = 70
PRICE_STEP = Decimal("0.02")  # a change of more than 2% counts as a price change

BILL_CATEGORIES = {"Utilities", "Housing and Rent", "Healthcare", "Education"}
SUBSCRIPTION_CATEGORIES = {"Subscriptions", "Entertainment"}
_BILL_WORDS = re.compile(r"\b(rent|emi|loan|insurance|premium|electricity|water|gas|broadband|fibernet|postpaid|maintenance|society|school|tuition|lic)\b")
_SUB_WORDS = re.compile(r"\b(netflix|spotify|prime|hotstar|disney|youtube|apple|icloud|google one|jiocinema|sonyliv|zee5|audible|kindle|chatgpt|openai|adobe|microsoft|linkedin|canva|notion|dropbox|gym|cult|cultfit|membership|subscription)\b")
_NAME_NOISE = re.compile(r"\b(billpay|bill|autopay|auto|subscription|subscr|pack|plan|quarterly|monthly|yearly|annual|recharge|mandate|si|renewal|india|pay)\b", re.I)
_SKIP = re.compile(r"\b(atm|cash|self|wdl|nwd|withdrawal|own account)\b")


@dataclass
class Charge:
    on: date
    amount: Decimal
    category_id: object
    merchant: str


@dataclass
class Series:
    frequency: str
    charges: list[Charge]
    regularity: float
    varies: bool


def add_period(d: date, frequency: str) -> date:
    if frequency == "weekly":
        return d + timedelta(days=7)
    if frequency == "fortnightly":
        return d + timedelta(days=14)
    months = {"monthly": 1, "quarterly": 3, "yearly": 12}[frequency]
    m = d.month - 1 + months
    y, m = d.year + m // 12, m % 12 + 1
    return date(y, m, min(d.day, calendar.monthrange(y, m)[1]))


def _frequency_for(gap: float) -> str | None:
    for name, (period, tol, _, _) in PERIODS.items():
        if abs(gap - period) <= tol * 1.5:
            return name
    return None


def find_series(charges: list[Charge], allow_varying: bool, known_subscription: bool) -> Series | None:
    """Do these payments repeat on a schedule? `charges` sorted by date."""
    by_day: dict[date, Charge] = {}
    for c in charges:
        by_day.setdefault(c.on, c)  # two payments on one day: keep the first
    charges = list(by_day.values())
    if len(charges) < 2:
        return None
    gaps = [(b.on - a.on).days for a, b in zip(charges, charges[1:])]
    freq = _frequency_for(median(gaps))
    if freq is None:
        return None
    period, tol, need, _ = PERIODS[freq]
    if len(charges) < need and not (freq == "monthly" and known_subscription and len(charges) == 2):
        return None
    regular = sum(1 for g in gaps if abs(g - period) <= tol) / len(gaps)
    if regular < 0.6:
        return None
    # Is the amount steady? Count how often it changes from one payment to the next.
    amounts = [c.amount for c in charges]
    steps = sum(1 for a, b in zip(amounts, amounts[1:]) if abs(b - a) > a * PRICE_STEP)
    varies = False
    if steps > max(1, len(amounts) // 4):
        mid = Decimal(median(amounts))
        spread = max(abs(a - mid) / mid for a in amounts)
        if not allow_varying or spread > Decimal("0.6"):
            return None  # e.g. food orders at random amounts: not a subscription
        varies = True
    return Series(freq, charges, regular, varies)


def _clusters(charges: list[Charge], known_subscription: bool) -> list[list[Charge]]:
    """Group payments of (almost) the same amount, keeping date order. Needs
    3 or more, because two one-off purchases at the same price happen by chance."""
    groups: list[list[Charge]] = []
    for c in sorted(charges, key=lambda c: c.amount):
        if groups and c.amount <= groups[-1][0].amount * Decimal("1.03"):
            groups[-1].append(c)
        else:
            groups.append([c])
    least = 2 if known_subscription else 3
    return [sorted(g, key=lambda c: c.on) for g in groups if len(g) >= least]


def display_name(merchant: str, key: str) -> str:
    """'Billpay Bescom Electricity' -> 'Bescom Electricity'."""
    name = " ".join(_NAME_NOISE.sub(" ", merchant).split())
    return (name or merchant or key.title())[:100]


def _kind(key: str, category_name: str | None) -> str:
    if category_name in SUBSCRIPTION_CATEGORIES or _SUB_WORDS.search(key):
        return "subscription"
    if category_name in BILL_CATEGORIES or _BILL_WORDS.search(key):
        return "bill"
    return "other"


def _price_changes(series: Series) -> list[dict]:
    if series.varies:
        return []
    out = []
    for a, b in zip(series.charges, series.charges[1:]):
        if abs(b.amount - a.amount) > a.amount * PRICE_STEP:
            out.append({"date": b.on.isoformat(), "old": str(a.amount), "new": str(b.amount)})
    return out


def _confidence(series: Series) -> Decimal:
    n = len(series.charges)
    score = 0.45 + 0.1 * min(n - 2, 3) + 0.2 * series.regularity - (0.1 if series.varies else 0)
    return Decimal(str(round(max(0.3, min(0.95, score)), 3)))


def as_of_date(db: Session, user: User) -> date:
    """CASIO only knows what's been imported. Judge "missed" and "new"
    against the latest transaction, not today, so an old statement doesn't
    make everything look missed."""
    latest = db.scalar(select(func.max(Transaction.occurred_on)).where(Transaction.user_id == user.id))
    today = date.today()
    return min(latest, today) if latest else today


def _alert(db: Session, user: User, rp: RecurringPayment, kind: str, key: str, message: str) -> None:
    db.execute(
        insert(RecurringAlert)
        .values(user_id=user.id, recurring_payment_id=rp.id, kind=kind, dedupe_key=key[:200], message=message[:400])
        .on_conflict_do_nothing(constraint="uq_recurring_alert_key")
    )


def detect_recurring(db: Session, user: User) -> date:
    """Re-check all recurring payments for this user and raise alerts for
    anything new. Safe to run as often as you like. Returns the as-of date."""
    as_of = as_of_date(db, user)
    cats = {c.id: c.name for c in db.scalars(select(Category))}
    txs = db.scalars(
        select(Transaction).where(
            Transaction.user_id == user.id, Transaction.type == "expense",
            Transaction.occurred_on >= as_of - timedelta(days=LOOKBACK_DAYS),
        ).order_by(Transaction.occurred_on)
    ).all()
    groups: dict[str, list[Charge]] = {}
    for t in txs:
        key = merchant_key(t.description, t.merchant)
        if not key or _SKIP.search(key):
            continue
        groups.setdefault(key, []).append(Charge(t.occurred_on, t.amount, t.category_id, t.merchant or guess_merchant(t.description) or key))

    found: dict[str, tuple[Series, str | None]] = {}
    for key, charges in groups.items():
        cat_id = Counter(c.category_id for c in charges).most_common(1)[0][0]
        cat_name = cats.get(cat_id)
        kind = _kind(key, cat_name)
        series = find_series(charges, allow_varying=kind == "bill", known_subscription=kind == "subscription")
        if series is None and len(charges) >= 3:
            for group in sorted(_clusters(charges, kind == "subscription"), key=len, reverse=True):
                series = find_series(group, allow_varying=False, known_subscription=kind == "subscription")
                if series:
                    break
        if series:
            found[key] = (series, cat_id)

    profile = db.get(UserProfile, user.id)
    currency = profile.currency if profile else "INR"
    existing = {r.merchant_key: r for r in db.scalars(select(RecurringPayment).where(RecurringPayment.user_id == user.id))}
    for key, rp in existing.items():
        if key not in found and rp.status != "not_recurring":
            db.delete(rp)  # no longer repeating (e.g. an import was undone)

    for key, (series, cat_id) in found.items():
        rp = existing.get(key)
        if rp is not None and rp.status == "not_recurring":
            continue  # the user said this isn't a regular payment
        last = series.charges[-1]
        amounts = [c.amount for c in series.charges]
        avg = money(sum(amounts, Decimal(0)) / len(amounts))
        is_new = rp is None
        if rp is None:
            rp = RecurringPayment(user_id=user.id, merchant_key=key, status="active", usage="unknown", name_edited=False)
            db.add(rp)
        if not rp.name_edited:
            rp.name = display_name(last.merchant, key)
        rp.kind = _kind(key, cats.get(cat_id))
        rp.category_id = cat_id
        rp.frequency = series.frequency
        rp.amount, rp.average_amount, rp.amount_varies = last.amount, avg, series.varies
        rp.first_paid_on, rp.last_paid_on = series.charges[0].on, last.on
        rp.next_expected_on = add_period(last.on, series.frequency)
        rp.occurrences = len(series.charges)
        rp.confidence = _confidence(series)
        rp.charges = [{"date": c.on.isoformat(), "amount": str(c.amount)} for c in series.charges]
        rp.price_changes = _price_changes(series)
        db.flush()
        _raise_alerts(db, user, rp, as_of, is_new, currency)
    return as_of


def _raise_alerts(db: Session, user: User, rp: RecurringPayment, as_of: date, is_new: bool, currency: str) -> None:
    def inr(amount: Decimal) -> str:
        return fmt_money(amount, currency)

    every = {"weekly": "week", "fortnightly": "two weeks", "monthly": "month", "quarterly": "three months", "yearly": "year"}[rp.frequency]
    key = rp.merchant_key
    per_year = lambda amt: money(monthly_amount(amt, rp.frequency) * 12)  # noqa: E731

    if is_new and rp.first_paid_on >= as_of - timedelta(days=NEW_WITHIN_DAYS):
        _alert(db, user, rp, "new", f"new:{key}",
               f"New regular payment: {rp.name}, {inr(rp.amount)} every {every} since {rp.first_paid_on:%d %b}. "
               f"That's about {inr(per_year(rp.amount))} a year.")

    if rp.price_changes:
        ch = rp.price_changes[-1]
        old, new = Decimal(ch["old"]), Decimal(ch["new"])
        pct = abs(new - old) / old * 100
        if new > old:
            _alert(db, user, rp, "price_increase", f"price:{key}:{ch['date']}",
                   f"{rp.name} went up from {inr(old)} to {inr(new)} (+{pct:.0f}%) on {date.fromisoformat(ch['date']):%d %b}. "
                   f"That's {inr(per_year(new - old))} more a year.")
        else:
            _alert(db, user, rp, "price_decrease", f"price:{key}:{ch['date']}",
                   f"{rp.name} went down from {inr(old)} to {inr(new)} (−{pct:.0f}%).")

    if rp.amount_varies and rp.occurrences >= 3 and rp.amount > rp.average_amount * Decimal("1.3"):
        pct = (rp.amount - rp.average_amount) / rp.average_amount * 100
        _alert(db, user, rp, "unusual_amount", f"unusual:{key}:{rp.last_paid_on}",
               f"{rp.name} was {inr(rp.amount)} on {rp.last_paid_on:%d %b}, about {pct:.0f}% more than usual ({inr(rp.average_amount)}).")

    grace = PERIODS[rp.frequency][3]
    if rp.status == "active" and rp.next_expected_on and rp.next_expected_on + timedelta(days=grace) < as_of:
        _alert(db, user, rp, "missed", f"missed:{key}:{rp.next_expected_on}",
               f"No {rp.name} payment seen around {rp.next_expected_on:%d %b}. If you cancelled it, mark it as cancelled.")

    if rp.status == "cancelled" and rp.status_changed_on and rp.last_paid_on > rp.status_changed_on:
        _alert(db, user, rp, "charged_after_cancel", f"after_cancel:{key}:{rp.last_paid_on}",
               f"You marked {rp.name} as cancelled, but it charged {inr(rp.amount)} on {rp.last_paid_on:%d %b}. Check with the provider.")

    if rp.kind == "subscription" and rp.usage == "unknown" and rp.status == "active":
        _alert(db, user, rp, "usage_check", f"usage:{key}",
               f"Do you still use {rp.name}? It costs about {inr(per_year(rp.amount))} a year. "
               "CASIO can't tell from bank data alone, so tell us and we'll keep track.")


def state(rp: RecurringPayment, as_of: date) -> str:
    if rp.status != "active":
        return rp.status
    if rp.next_expected_on and rp.next_expected_on + timedelta(days=PERIODS[rp.frequency][3]) < as_of:
        return "overdue"
    return "active"


def dismiss_usage_alerts(db: Session, rp: RecurringPayment) -> None:
    for a in db.scalars(select(RecurringAlert).where(
        RecurringAlert.recurring_payment_id == rp.id, RecurringAlert.kind.in_(("usage_check", "missed")),
        RecurringAlert.dismissed_at.is_(None),
    )):
        if a.kind == "usage_check" or rp.status != "active":
            a.dismissed_at = datetime.now(UTC)
