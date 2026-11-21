"""Shared building blocks for every importer (CSV, PDF, SMS).

Each importer turns a messy file into a list of ParsedRow objects. It never
guesses: if a date or amount can't be read, the row becomes an error the user
can fix, instead of an invented value."""
import hashlib
import re
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Literal, Protocol

SourceType = Literal["csv", "pdf", "sms"]

# Upload safety limits, checked before any parsing happens.
MAX_UPLOAD_BYTES = 10 * 1024 * 1024  # 10 MB
MAX_SMS_CHARS = 200_000
ALLOWED_TYPES: dict[SourceType, dict] = {
    "csv": {"extensions": {".csv"}, "magic": None},
    "pdf": {"extensions": {".pdf"}, "magic": b"%PDF-"},
    "sms": {"extensions": {".txt"}, "magic": None},
}


@dataclass
class ParsedRow:
    """One transaction found in a statement, before the user confirms it."""

    row_number: int
    raw_text: str  # exactly what the statement said (provenance)
    occurred_on: date | None
    description: str
    amount: Decimal | None  # always positive; direction is in `type`
    type: Literal["income", "expense"] | None
    balance_after: Decimal | None = None
    merchant: str | None = None
    problems: list[str] = field(default_factory=list)  # shown to the user for fixing

    @property
    def is_complete(self) -> bool:
        return self.occurred_on is not None and self.amount is not None and self.type is not None and not self.problems


@dataclass
class ParseResult:
    rows: list[ParsedRow]
    errors: list[tuple[int | None, str, str]]  # (row number, raw text, message)
    needs_ocr: bool = False  # scanned PDF with no text layer
    warnings: list[str] = field(default_factory=list)  # file-level notes shown above the review table


class Importer(Protocol):
    source_type: SourceType

    def parse(self, content: bytes, filename: str) -> ParseResult: ...


def normalise_description(text: str) -> str:
    """'SWIGGY ORDER 4589 ' -> 'swiggy order' (drops reference numbers) so the
    same purchase looks the same across statements."""
    text = re.sub(r"\d{3,}", " ", text.lower())
    return " ".join(re.sub(r"[^a-z0-9& ]", " ", text).split())


def dedupe_hash(occurred_on: date, amount: Decimal, type_: str, description: str) -> str:
    """Fingerprint used to warn about transactions already imported.
    Matches are flagged for review, not silently dropped, because two
    identical coffees on the same day can both be real."""
    key = f"{occurred_on.isoformat()}|{amount.quantize(Decimal('0.01'))}|{type_}|{normalise_description(description)}"
    return hashlib.sha256(key.encode()).hexdigest()
