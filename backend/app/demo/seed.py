"""The "Try CASIO Demo" sandbox.

Every visitor who presses the button gets their OWN new account, filled with
the same fictional sample data. Nobody shares a demo account, so one visitor
can never see or change what another visitor did, and real accounts are never
touched. Demo accounts can't sign in with a password and are deleted
automatically after DEMO_LIFETIME.

The sample data is generated relative to today, so it always looks current:
six full months of history plus the current month so far. The bank-statement
part goes through CASIO's real import pipeline (the same parsing,
categorisation and subscription detection a real upload gets).

Everything here is fictional. Names, merchants and amounts are made up.
"""
import csv
import datetime as dt
import io
import random
import re
import secrets
from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.audit import audit
from app.importers.pipeline import start_import
from app.learning import START_CONFIDENCE, merchant_key
from app.recurring import detect_recurring
from app.models import (
    Asset,
    Budget,
    CategorizationRule,
    Category,
    ExpenseItem,
    FinancialGoal,
    GoalContribution,
    IncomeSource,
    Liability,
    RecurringAlert,
    RecurringPayment,
    Transaction,
    User,
    UserProfile,
)
from app.security import hash_password

DEMO_NAME = "Aanya Kapoor"
DEMO_LIFETIME = dt.timedelta(hours=24)
MAX_LIVE_DEMOS = 400  # safety cap; the oldest sandboxes are removed first
HISTORY_MONTHS = 6
SALARY = Decimal("45000")
EMPLOYER = "NIMBUS ANALYTICS PVT LTD"
STATEMENT_NAME = "demo-bank-statement-6-months.csv"

# A merchant the built-in keyword rules don't recognise. It lands in "Other",
# which is what the "correct a category and save it as a rule" demo uses.
UNKNOWN_CAFE = "UPI-BLUE PEAK ROASTERS-bluepeak@okaxis"
NICE_NAMES = {
    "rent": "Rent (Sunrise Residency PG)", "netflix": "Netflix", "cultfit": "Cult.fit membership", "spotify": "Spotify",
    "youtube": "YouTube Premium", "bescom": "BESCOM electricity", "airtel": "Airtel postpaid", "fibernet": "ACT Fibernet broadband",
}
# The payments that really are regular in the sample data.
REGULAR = re.compile(r"\b(rent|netflix|cultfit|spotify|youtube|bescom|airtel|fibernet)\b")


@dataclass
class Line:
    day: int
    description: str
    amount: Decimal
    income: bool = False


def _d(x) -> Decimal:
    return Decimal(str(x)).quantize(Decimal("0.01"))


def add_months(d: dt.date, n: int) -> dt.date:
    y, m = divmod(d.month - 1 + n, 12)
    return dt.date(d.year + y, m + 1, 1)


def month_lines(index: int, first: dt.date, rng: random.Random) -> list[Line]:
    """One month of statement lines. index 0 = oldest month, HISTORY_MONTHS =
    the current month. Month HISTORY_MONTHS-1 (last month) is the festival
    month: more shopping, a doctor's visit and the Netflix price rise, so
    "why did my spending go up?" has a real answer."""
    last_month = index == HISTORY_MONTHS - 1
    ref = lambda: rng.randint(10000, 99999)  # noqa: E731
    # Everyday spending happens on random days; only real subscriptions and
    # bills keep a fixed day, so only they are detected as regular payments.
    day = lambda: rng.randint(1, 28)  # noqa: E731
    mon = f"{first:%b}".upper()
    L = [
        Line(1, f"SALARY {mon} {EMPLOYER}", SALARY, income=True),
        Line(3, "NACH-RENT-SUNRISE RESIDENCY PG", _d(10000)),
        # four subscriptions; Netflix goes up from 499 to 649 two months ago
        Line(6, "POS 4321XXXX NETFLIX.COM", _d(649 if index >= HISTORY_MONTHS - 2 else 499)),
        Line(9, "UPI-CULTFIT-cult@ybl-MONTHLY MEMBERSHIP", _d(999)),
        Line(12, "UPI-SPOTIFY INDIA-spotify@hdfc-AUTOPAY", _d(119)),
        Line(15, "YOUTUBE PREMIUM GOOGLE PLAY", _d(129)),
        # bills
        Line(18, "BILLPAY BESCOM ELECTRICITY", _d(rng.choice([760, 820, 880, 940, 1010]))),
        Line(20, "AIRTEL POSTPAID BILL", _d(599)),
        Line(22, "ACT FIBERNET BROADBAND", _d(589)),
        # groceries
        Line(day(), f"UPI-BIGBASKET-bigbasket@hdfc-REF {ref()}", _d(rng.randint(1250, 1650))),
        Line(day(), f"UPI-ZEPTO-zepto@ybl-ORDER {ref()}", _d(rng.randint(320, 480))),
        Line(day(), f"UPI-ZEPTO-zepto@ybl-ORDER {ref()}", _d(rng.randint(300, 450))),
        Line(day(), f"UPI-ZEPTO-zepto@ybl-ORDER {ref()}", _d(rng.randint(340, 520))),
        Line(day(), "POS 4321XXXX DMART AVENUE SUPERMARTS", _d(rng.randint(1050, 1250))),
        # food and dining
        Line(day(), f"UPI-SWIGGY-swiggy@icici-ORDER {ref()}", _d(rng.randint(300, 420))),
        Line(day(), f"UPI-SWIGGY-swiggy@icici-ORDER {ref()}", _d(rng.randint(260, 360))),
        Line(day(), f"UPI-SWIGGY-swiggy@icici-ORDER {ref()}", _d(rng.randint(380, 480))),
        Line(day(), f"UPI-SWIGGY-swiggy@icici-ORDER {ref()}", _d(rng.randint(280, 360))),
        Line(day(), f"UPI-SWIGGY-swiggy@icici-ORDER {ref()}", _d(rng.randint(300, 400))),
        Line(day(), f"UPI-ZOMATO-zomato@hdfc-ORDER {ref()}", _d(rng.randint(360, 460))),
        Line(day(), f"UPI-ZOMATO-zomato@hdfc-ORDER {ref()}", _d(rng.randint(300, 400))),
        Line(day(), f"UPI-CHAI POINT-chaipoint@ybl-{ref()}", _d(rng.randint(90, 160))),
        Line(day(), f"UPI-CHAI POINT-chaipoint@ybl-{ref()}", _d(rng.randint(90, 160))),
        Line(day(), f"UPI-CHAI POINT-chaipoint@ybl-{ref()}", _d(rng.randint(90, 160))),
        Line(day(), f"{UNKNOWN_CAFE}-{ref()}", _d(rng.randint(180, 280))),
        Line(day(), f"{UNKNOWN_CAFE}-{ref()}", _d(rng.randint(180, 280))),
        # transport
        Line(day(), f"UPI-UBER INDIA-uber@axis-RIDE {ref()}", _d(rng.randint(180, 260))),
        Line(day(), f"UPI-UBER INDIA-uber@axis-RIDE {ref()}", _d(rng.randint(160, 240))),
        Line(day(), f"UPI-UBER INDIA-uber@axis-RIDE {ref()}", _d(rng.randint(200, 300))),
        Line(day(), f"UPI-UBER INDIA-uber@axis-RIDE {ref()}", _d(rng.randint(180, 260))),
        Line(day(), f"UPI-RAPIDO-rapido@ybl-RIDE {ref()}", _d(rng.randint(70, 110))),
        Line(day(), f"UPI-RAPIDO-rapido@ybl-RIDE {ref()}", _d(rng.randint(70, 110))),
        Line(day(), "BMRCL METRO CARD RECHARGE", _d(500)),
        Line(day(), "BMRCL METRO CARD RECHARGE", _d(300)),
        # shopping
        Line(day(), f"AMAZON PAY INDIA ORDER {ref()}{ref()}", _d(rng.randint(599, 1249))),
        Line(day(), f"MYNTRA DESIGNS ORDER {ref()}", _d(rng.randint(699, 1299))),
        # education
        Line(day(), "CROSSWORD BOOKSTORES KORAMANGALA", _d(rng.randint(420, 680))),
        # entertainment
        Line(day(), f"BOOKMYSHOW-{ref()}", _d(rng.randint(380, 660))),
        # healthcare
        Line(day(), "WELLNESS FOREVER MEDICOS", _d(rng.randint(260, 440))),
    ]
    if index % 2 == 0:
        L.append(Line(19, "UDEMY ONLINE COURSE", _d(rng.randint(399, 599))))
    else:
        L.append(Line(27, "PVR CINEMAS ORION MALL", _d(rng.randint(340, 480))))
    if last_month:
        L += [
            Line(day(), f"FLIPKART INTERNET ORDER {ref()}", _d(1999)),
            Line(day(), f"AMAZON PAY INDIA ORDER {ref()}{ref()}", _d(1249)),
            Line(day(), "PRACTO CONSULTATION FEE", _d(600)),
            Line(day(), "BARBEQUE NATION INDIRANAGAR", _d(980)),
        ]
    elif index == 2:
        L.append(Line(18, "APOLLO PHARMACY", _d(460)))
    return L


def build_statement(today: dt.date, seed: int = 2026) -> tuple[bytes, list[tuple[dt.date, str, Decimal, bool]]]:
    """The six-month sample bank statement as CSV bytes, plus the rows."""
    rng = random.Random(seed)
    start = add_months(today.replace(day=1), -HISTORY_MONTHS)
    rows: list[tuple[dt.date, str, Decimal, bool]] = []
    for i in range(HISTORY_MONTHS + 1):
        first = add_months(start, i)
        for line in month_lines(i, first, rng):
            day = dt.date(first.year, first.month, line.day)
            if day > today:
                continue  # the current month only goes up to today
            rows.append((day, line.description, line.amount, line.income))
    rows.sort(key=lambda r: (r[0], not r[3]))
    return _to_csv(rows, start, today), rows


def _to_csv(rows, start: dt.date, end: dt.date) -> bytes:
    out = io.StringIO()
    w = csv.writer(out)
    w.writerow(["Account Statement (SAMPLE DATA - FICTIONAL)"])
    w.writerow([f"Name: {DEMO_NAME.upper()} (DEMO)"])
    w.writerow(["Account No: XXXXXXXX4321"])
    w.writerow([f"Statement From: {start:%d/%m/%Y} To: {end:%d/%m/%Y}"])
    w.writerow([])
    w.writerow(["Date", "Narration", "Chq./Ref.No.", "Value Dt", "Withdrawal Amt.", "Deposit Amt.", "Closing Balance"])
    bal = Decimal("38250.00")
    for n, (day, desc, amt, income) in enumerate(rows):
        bal += amt if income else -amt
        w.writerow([
            f"{day:%d/%m/%y}", desc, f"0007{n:08d}", f"{day:%d/%m/%y}",
            "" if income else f"{amt:,.2f}", f"{amt:,.2f}" if income else "", f"{bal:,.2f}",
        ])
    return out.getvalue().encode()


def _transfers(today: dt.date) -> list[tuple[dt.date, str, Decimal]]:
    """Money moved to the user's own savings and investments. These are
    transfers, not spending, so they don't count as expenses."""
    out = []
    start = add_months(today.replace(day=1), -HISTORY_MONTHS)
    for i in range(HISTORY_MONTHS + 1):
        first = add_months(start, i)
        for day, desc, amt in (
            (2, "TRANSFER TO OWN SAVINGS A/C - EMERGENCY FUND", _d(6000)),
            (2, "TRANSFER TO OWN SAVINGS A/C - LAPTOP FUND", _d(4000)),
            (5, "ACH D- GROWW MUTUAL FUND SIP", _d(2500)),
        ):
            d = dt.date(first.year, first.month, day)
            if d <= today:
                out.append((d, desc, amt))
    return out


def _cat(db: Session, name: str) -> Category:
    return db.scalar(select(Category).where(Category.user_id.is_(None), Category.name == name))


def cleanup(db: Session) -> int:
    """Delete expired demo sandboxes (and the oldest ones beyond the cap).
    Every table cascades from users, so this removes all their data."""
    cutoff = dt.datetime.now(dt.UTC) - DEMO_LIFETIME
    removed = db.execute(delete(User).where(User.is_demo.is_(True), User.created_at < cutoff)).rowcount or 0
    live = db.scalar(select(func.count()).select_from(User).where(User.is_demo.is_(True))) or 0
    if live >= MAX_LIVE_DEMOS:
        oldest = select(User.id).where(User.is_demo.is_(True)).order_by(User.created_at).limit(live - MAX_LIVE_DEMOS + 1)
        removed += db.execute(delete(User).where(User.id.in_(oldest))).rowcount or 0
    return removed


def create_demo_user(db: Session, today: dt.date | None = None) -> User:
    """A brand-new sandbox account with the full sample data set."""
    from app.routers.imports import confirm  # avoid a circular import

    today = today or dt.date.today()
    cleanup(db)
    user = User(
        email=f"demo-{secrets.token_hex(6)}@demo.casio.example",
        full_name=DEMO_NAME,
        # Random, never shown: a demo account can't be signed into with a password.
        password_hash=hash_password(secrets.token_urlsafe(24)),
        is_demo=True,
    )
    db.add(user)
    db.flush()
    db.add(UserProfile(user_id=user.id, currency="INR", country="IN"))

    # Saved categorisation rules (as if the user had made them earlier).
    # They're created before the import so the statement shows "Your rule".
    for desc, cat in (
        ("UPI-CHAI POINT-chaipoint@ybl-11111", "Food and Dining"),
        ("WELLNESS FOREVER MEDICOS", "Healthcare"),
        ("CROSSWORD BOOKSTORES KORAMANGALA", "Education"),
    ):
        db.add(CategorizationRule(
            user_id=user.id, category_id=_cat(db, cat).id, match_type="merchant", pattern=merchant_key(desc, None),
            applies_to="expense", priority=50, active=True, confidence=START_CONFIDENCE, times_applied=0, times_overridden=0,
        ))
    db.flush()

    # Six months of bank statement, through the real import pipeline.
    content, _ = build_statement(today)
    batch = start_import(db, user, "csv", STATEMENT_NAME, content)
    db.flush()
    confirm(batch.id, user, db)  # saves the rows, detects subscriptions, commits
    # Everyday spending can repeat by chance (two similar Uber fares a month
    # apart). Treat those as already dismissed by the user, so the demo shows
    # exactly the real subscriptions and bills.
    for rp in db.scalars(select(RecurringPayment).where(RecurringPayment.user_id == user.id)):
        if not REGULAR.search(rp.merchant_key):
            rp.status = "not_recurring"
            db.execute(delete(RecurringAlert).where(RecurringAlert.recurring_payment_id == rp.id))
            continue
        for word, name in NICE_NAMES.items():
            if word in rp.merchant_key:
                rp.name, rp.name_edited = name, True
    # Re-raise the alerts so their messages use the tidied names.
    db.execute(delete(RecurringAlert).where(RecurringAlert.user_id == user.id))
    db.flush()
    detect_recurring(db, user)

    transfers_cat = _cat(db, "Transfers")
    for d, desc, amt in _transfers(today):
        db.add(Transaction(
            user_id=user.id, currency="INR", type="transfer", amount=amt, occurred_on=d, description=desc,
            merchant="Own savings" if "OWN SAVINGS" in desc else "Groww", source="demo", category_id=transfers_cat.id,
            category_source="keyword", category_confidence=Decimal("0.8"), category_reason="Money moved to your own savings or investments.",
        ))

    # Financial profile (the user's own ESTIMATES, kept apart from actuals).
    db.add(IncomeSource(user_id=user.id, name="Salary (Nimbus Analytics)", amount=SALARY, frequency="monthly"))
    for name, amt, kind, cat in (
        ("Rent (PG room)", 10000, "fixed", "Housing and Rent"),
        ("Phone, internet and electricity", 2000, "fixed", "Utilities"),
        ("Subscriptions", 1900, "fixed", "Subscriptions"),
        ("Groceries", 4000, "variable", "Groceries"),
        ("Eating out", 3500, "variable", "Food and Dining"),
        ("Getting around", 2000, "variable", "Transportation"),
        ("Shopping and fun", 4000, "variable", "Shopping"),
    ):
        db.add(ExpenseItem(user_id=user.id, name=name, amount=_d(amt), frequency="monthly", kind=kind, category_id=_cat(db, cat).id))

    n = sum(1 for d, desc, _ in _transfers(today) if "EMERGENCY" in desc)
    ef_saved = _d(30000 + 6000 * n)
    laptop_saved = _d(4000 * n)
    for name, kind, value in (
        ("Salary account", "bank_account", 41800),
        ("Emergency fund (savings account)", "emergency_fund", ef_saved),
        ("Laptop fund (savings account)", "savings", laptop_saved),
        ("Mutual fund SIP", "investment", 2500 * n + 21000),
    ):
        db.add(Asset(user_id=user.id, name=name, kind=kind, value=_d(value)))
    db.add(Liability(user_id=user.id, name="Education loan (repayment starts next year)", kind="education_loan",
                     balance=_d(180000), monthly_payment=None, interest_rate=Decimal("9.50")))

    # Budgets for the main spending categories.
    for cat, amt in (
        ("Food and Dining", 3500), ("Groceries", 4000), ("Transportation", 2000), ("Shopping", 2500),
        ("Entertainment", 1000), ("Utilities", 2200), ("Subscriptions", 2000), ("Healthcare", 1500),
    ):
        db.add(Budget(user_id=user.id, category_id=_cat(db, cat).id, amount=_d(amt)))

    # Two savings goals, with the monthly transfers above as contributions.
    ef = FinancialGoal(user_id=user.id, name="Emergency fund (6 months of costs)", kind="emergency_fund",
                       target_amount=_d(150000), saved_amount=ef_saved, monthly_contribution=_d(6000), priority=1,
                       target_date=add_months(today.replace(day=1), 14), status="active")
    laptop = FinancialGoal(user_id=user.id, name="New laptop for final-year project", kind="purchase",
                           target_amount=_d(85000), saved_amount=laptop_saved, monthly_contribution=_d(4000), priority=2,
                           target_date=add_months(today.replace(day=1), 10), status="active")
    db.add_all([ef, laptop])
    db.flush()
    start = add_months(today.replace(day=1), -HISTORY_MONTHS)
    db.add(GoalContribution(user_id=user.id, goal_id=ef.id, amount=_d(30000), contributed_on=start, note="Starting balance"))
    for d, desc, amt in _transfers(today):
        if "EMERGENCY" in desc:
            db.add(GoalContribution(user_id=user.id, goal_id=ef.id, amount=amt, contributed_on=d, note="Monthly transfer"))
        elif "LAPTOP" in desc:
            db.add(GoalContribution(user_id=user.id, goal_id=laptop.id, amount=amt, contributed_on=d, note="Monthly transfer"))

    audit(db, "demo.create", user.id)
    db.commit()
    return user


# ---------------------------------------------------------------------------
# Sample files for trying Smart Import inside the demo
# ---------------------------------------------------------------------------
def _recent_imported(db: Session, user: User, n: int = 3) -> list[Transaction]:
    return list(db.scalars(
        select(Transaction).where(Transaction.user_id == user.id, Transaction.source == "csv")
        .order_by(Transaction.occurred_on.desc(), Transaction.description).limit(n)
    ))


def _new_rows(today: dt.date) -> list[tuple[dt.date, str, Decimal, bool]]:
    y = today - dt.timedelta(days=1) if today.day > 1 else today
    return [
        (y, "UPI-SWIGGY-swiggy@icici-ORDER 55821", _d(345), False),
        (y, f"{UNKNOWN_CAFE}-55902", _d(260), False),
        (today, "UPI-CHAI POINT-chaipoint@ybl-56010", _d(120), False),
        (today, "UPI-ZEPTO-zepto@ybl-ORDER 56044", _d(389), False),
        (today, "PVR CINEMAS ORION MALL", _d(450), False),
        (today, "UPI-HARBOUR LANE STATIONERS-harbour@okhdfc", _d(185), False),
    ]


def sample_statement(db: Session, user: User, today: dt.date | None = None) -> bytes:
    """A short statement for this demo account: 3 rows it already has (to show
    duplicate detection) and 6 new ones (to show categorisation and rules)."""
    today = today or dt.date.today()
    old = [(t.occurred_on, t.description, t.amount, t.type == "income") for t in reversed(_recent_imported(db, user))]
    rows = sorted(old + _new_rows(today), key=lambda r: r[0])
    return _to_csv(rows, rows[0][0], today)


def sample_sms(db: Session, user: User, today: dt.date | None = None) -> str:
    """Bank SMS alerts for the same kind of check: one already saved, a few new,
    and an OTP message that CASIO should ignore."""
    today = today or dt.date.today()
    lines = []
    old = _recent_imported(db, user, 1)
    if old:
        t = old[0]
        lines.append(f"Rs.{t.amount:,.2f} debited from A/c XX4321 on {t.occurred_on:%d-%m-%y}. Info: {t.description}. Avl Bal Rs.52,310.40")
    lines += [
        f"Rs.212.00 debited from A/c XX4321 on {today:%d-%m-%y} to VPA uber@axis (Uber India). Avl Bal Rs.52,098.40",
        f"Rs.540.00 debited from A/c XX4321 on {today:%d-%m-%y} to VPA bigbasket@hdfc (BigBasket). Avl Bal Rs.51,558.40",
        "Your OTP for transaction is 482913. Valid for 10 minutes. Do not share it with anyone.",
        f"INR 1,250.00 credited to your A/c XX4321 on {today:%d/%m/%Y} by UPI from RAHUL MEHTA (split for dinner). Avl Bal: INR 52,808.40",
    ]
    return "\n\n".join(lines) + "\n"
