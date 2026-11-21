"""Turning messy statement text into clean values.

Every function here either returns a correct value or None. None means
"couldn't read it" and the row is shown to the user to fix. Nothing is
ever guessed."""
import re
from datetime import date, datetime
from decimal import Decimal, InvalidOperation

# ---------------------------------------------------------------------------
# Amounts
# ---------------------------------------------------------------------------
_CURRENCY = re.compile(r"(₹|rs\.?|inr|\$|usd|€|eur|£|gbp)", re.I)
_DR = re.compile(r"\b(dr|debit|db|withdrawal)\.?\s*$", re.I)
_CR = re.compile(r"\b(cr|credit|deposit)\.?\s*$", re.I)


def parse_amount(text: str | None) -> tuple[Decimal | None, str | None]:
    """Read an amount and, if the text says so, its direction.

    "₹1,23,456.50"  -> (123456.50, None)
    "450.00 Dr"     -> (450.00, "expense")
    "(1,200.00)"    -> (1200.00, "expense")     accounting style negative
    "-75"           -> (75, "expense")
    "1,200 CR"      -> (1200, "income")
    "" / "-" / "abc" -> (None, None)
    """
    if text is None:
        return None, None
    s = str(text).strip()
    if not s or s in {"-", "--", "—", "nil", "NIL", "N/A"}:
        return None, None
    direction = None
    if _DR.search(s):
        direction, s = "expense", _DR.sub("", s)
    elif _CR.search(s):
        direction, s = "income", _CR.sub("", s)
    s = _CURRENCY.sub("", s).replace(",", "").replace(" ", "").replace(" ", "")
    if s.startswith("(") and s.endswith(")"):
        s, direction = s[1:-1], "expense"
    if s.startswith("-"):
        s, direction = s[1:], "expense"
    elif s.startswith("+"):
        s, direction = s[1:], direction or "income"
    if s.endswith("-"):  # some banks print "450.00-"
        s, direction = s[:-1], "expense"
    if not re.fullmatch(r"\d+(\.\d+)?", s):
        return None, None
    try:
        value = Decimal(s)
    except InvalidOperation:
        return None, None
    return value.quantize(Decimal("0.01")), direction


# ---------------------------------------------------------------------------
# Dates
# ---------------------------------------------------------------------------
# Indian banks write day first, so day-first formats are tried first.
_DATE_FORMATS = [
    "%d/%m/%Y", "%d-%m-%Y", "%d.%m.%Y", "%d/%m/%y", "%d-%m-%y", "%d.%m.%y",
    "%Y-%m-%d", "%Y/%m/%d",
    "%d %b %Y", "%d-%b-%Y", "%d %b %y", "%d-%b-%y", "%d/%b/%Y", "%d/%b/%y",
    "%d %B %Y", "%d-%B-%Y", "%b %d, %Y", "%B %d, %Y", "%b %d %Y", "%d%b%Y", "%d%b%y",
]
_US_FORMATS = ["%m/%d/%Y", "%m-%d-%Y", "%m/%d/%y"]


def parse_date(text: str | None, day_first: bool = True) -> date | None:
    """Read a date in any common format. Returns None when unsure.

    "05/03/2026" is read as 5 March (day first) unless the file as a whole
    shows it uses month-first (see detect_day_first)."""
    if text is None:
        return None
    s = " ".join(str(text).strip().split())
    s = re.sub(r"(\d)(st|nd|rd|th)\b", r"\1", s)  # 1st Jan -> 1 Jan
    s = re.sub(r"[ T]\d{1,2}:\d{2}(:\d{2})?(\s?[AP]M)?$", "", s, flags=re.I)  # drop a time part
    if not s:
        return None
    formats = (_US_FORMATS + _DATE_FORMATS) if not day_first else (_DATE_FORMATS + _US_FORMATS)
    for fmt in formats:
        try:
            d = datetime.strptime(s, fmt).date()
        except ValueError:
            continue
        if 1970 <= d.year <= date.today().year + 1:
            return d
    return None


def detect_day_first(samples: list[str]) -> bool:
    """Look at all the dates in a file. If any has a first number above 12
    it must be the day; if any has a second number above 12, the file is
    month-first (US style). Defaults to day-first."""
    for s in samples:
        m = re.match(r"\s*(\d{1,2})[/.-](\d{1,2})[/.-]\d{2,4}", str(s or ""))
        if not m:
            continue
        a, b = int(m.group(1)), int(m.group(2))
        if a > 12:
            return True
        if b > 12:
            return False
    return True


# ---------------------------------------------------------------------------
# Descriptions and merchants
# ---------------------------------------------------------------------------
def clean_description(text: str | None) -> str:
    return " ".join(str(text or "").split())[:500]


_NOISE = re.compile(
    r"\b(upi|imps|neft|rtgs|pos|ecom|ach|nach|txn|ref|no|purchase|payment|paid|to|from|via|by|at|on|"
    r"debit|credit|card|vpa|p2m|p2a|mmt|inb|ib|bil|onl|tpt|order|dr|cr|nach|ecs|pvt|ltd|limited|india|com|in|www|online)\b",
    re.I,
)


def guess_merchant(description: str) -> str | None:
    """Best-effort shop name from a bank description, used for display and
    for categorisation rules. "UPI/SWIGGY/4589/food" -> "Swiggy"."""
    text = re.sub(r"[/|*:_#.-]", " ", description)
    text = re.sub(r"\S+@\S+", " ", text)  # UPI ids / emails
    text = re.sub(r"\b[\w]*\d[\w]*\b", " ", text)  # anything with digits (refs, card numbers)
    text = _NOISE.sub(" ", text)
    words = [w for w in text.split() if len(w) > 1]
    if not words:
        return None
    return " ".join(words[:3]).title()[:200]


def privacy_scrub(description: str) -> str:
    """What may leave CASIO for the AI model: no numbers (account, card,
    phone, reference) and no UPI ids or emails."""
    text = re.sub(r"\S+@\S+", " ", description)
    text = re.sub(r"\d{3,}", " ", text)
    text = re.sub(r"[xX*]{2,}\d*", " ", text)  # masked card numbers
    return " ".join(text.split())[:200]
