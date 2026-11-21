"""Upload -> parse -> check -> categorise -> rows waiting for review.

The router calls `start_import`; this file does the work so it can be
tested without HTTP."""
import hashlib
import logging
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app import ai
from app.importers.base import MAX_UPLOAD_BYTES, ParseResult, dedupe_hash
from app.importers.categorize import keyword_guess
from app.importers.csv_importer import CsvImporter
from app.importers.normalize import privacy_scrub
from app.importers.pdf_importer import PdfImporter
from app.importers.sms_importer import SmsImporter
from app.models import Category, ImportBatch, ImportError, ImportRow, Transaction, User

log = logging.getLogger("casio.import")
IMPORTERS = {"csv": CsvImporter(), "pdf": PdfImporter(), "sms": SmsImporter()}
AI_ASK_BELOW = 0.8  # rows the keyword rules are less sure about go to the AI


class ImportRejected(Exception):
    """The upload can't be processed at all (wrong type, too big, empty)."""


def detect_source(filename: str | None, content: bytes) -> str:
    """Decide the importer from the extension AND the file's contents, so a
    renamed file can't sneak through."""
    name = (filename or "").lower()
    if len(content) == 0:
        raise ImportRejected("The file is empty.")
    if len(content) > MAX_UPLOAD_BYTES:
        raise ImportRejected("The file is bigger than 10 MB. Try a shorter date range.")
    if name.endswith((".xls", ".xlsx")):
        raise ImportRejected("Excel files aren't supported yet. Open it in Excel or Google Sheets and save it as CSV, then upload that.")
    is_pdf = content.startswith(b"%PDF-")
    if name.endswith(".pdf"):
        if not is_pdf:
            raise ImportRejected("This file is named .pdf but isn't a real PDF. Download the statement again.")
        return "pdf"
    if is_pdf:
        raise ImportRejected("This is a PDF file. Please rename it to end in .pdf.")
    if b"\x00" in content[:4096]:
        raise ImportRejected("This doesn't look like a text file. Upload a CSV, a PDF, or a .txt file of SMS messages.")
    if name.endswith(".csv"):
        return "csv"
    if name.endswith(".txt"):
        return "sms"
    raise ImportRejected("Please upload a .csv or .pdf bank statement, or a .txt file of bank SMS messages.")


def compute_problems(row: ImportRow) -> list[str]:
    """What still has to be fixed before this row can be saved. Recomputed
    after every edit."""
    problems = []
    if row.occurred_on is None:
        problems.append("Please enter the date.")
    elif row.occurred_on > date.today() + timedelta(days=1):
        problems.append("This date is in the future. Please check it.")
    if row.amount is None:
        problems.append("Please enter the amount.")
    if row.type is None:
        problems.append("Please choose money in or money out.")
    if not row.description.strip() or row.description == "(no description)":
        problems.append("Please add a description.")
    return problems


def _categories(db: Session, user: User) -> list[Category]:
    return list(db.scalars(select(Category).where(or_(Category.user_id.is_(None), Category.user_id == user.id))))


def _fits(cat: Category, tx_type: str | None) -> bool:
    return cat.kind == "transfer" or cat.kind == tx_type


def categorise(db: Session, user: User, rows: list[ImportRow]) -> str:
    """Fill in category, confidence and reason for each row. Returns the AI
    status for the batch."""
    cats = _categories(db, user)
    by_name = {c.name: c for c in cats if c.user_id is None}
    by_name.update({c.name: c for c in cats if c.user_id is not None})  # custom wins on name clash
    ask: list[dict] = []
    for i, row in enumerate(rows):
        g = keyword_guess(row.description, row.merchant, row.type)
        cat = by_name.get(g.category)
        if cat and _fits(cat, row.type):
            row.category_id, row.category = cat.id, cat
            row.category_source, row.category_confidence, row.category_reason = g.source, Decimal(str(g.confidence)), g.reason
        if g.confidence < AI_ASK_BELOW and row.type:
            ask.append({"id": i, "description": privacy_scrub(row.description), "direction": "money in" if row.type == "income" else "money out"})

    if not ask:
        return "not_needed"
    if ai.ai_status() != "ready":
        return "not_configured"
    answers = ai.classify(ask, [{"name": c.name, "kind": c.kind} for c in cats])
    if not answers:
        return "failed"
    for i, a in answers.items():
        if not (0 <= i < len(rows)):
            continue
        row, cat = rows[i], by_name.get(a.category)
        current = float(row.category_confidence or 0)
        if cat and _fits(cat, row.type) and a.confidence > current:
            row.category_id, row.category = cat.id, cat
            row.category_source, row.category_confidence = "ai", Decimal(str(round(a.confidence, 3)))
            row.category_reason = f"AI: {a.reason}"[:300]
    return "used"


def mark_duplicates(db: Session, user: User, rows: list[ImportRow]) -> int:
    """Compare against transactions already saved and against earlier rows
    in the same file. Exact matches are unticked; near matches stay ticked
    but are pointed out. Returns the number of exact matches."""
    dated = [r.occurred_on for r in rows if r.occurred_on]
    existing: list[Transaction] = []
    if dated:
        existing = list(
            db.scalars(
                select(Transaction).where(
                    Transaction.user_id == user.id,
                    Transaction.occurred_on >= min(dated),
                    Transaction.occurred_on <= max(dated),
                )
            )
        )
    by_hash = {dedupe_hash(t.occurred_on, t.amount, t.type, t.description): t for t in existing}
    by_key = {(t.occurred_on, t.amount, t.type): t for t in existing}
    seen: dict[str, ImportRow] = {}
    exact = 0
    for row in rows:
        if row.occurred_on is None or row.amount is None or row.type is None:
            continue
        h = dedupe_hash(row.occurred_on, row.amount, row.type, row.description)
        if h in by_hash:
            t = by_hash[h]
            row.duplicate_kind, row.duplicate_of_id, row.include = "exact", t.id, False
            where = f"imported from {t.source.upper()}" if t.source != "manual" else "added by hand"
            row.duplicate_note = f"Already in your transactions ({where}). Unticked so it isn't counted twice."
            exact += 1
        elif (row.occurred_on, row.amount, row.type) in by_key:
            t = by_key[(row.occurred_on, row.amount, row.type)]
            row.duplicate_kind, row.duplicate_of_id = "possible", t.id
            row.duplicate_note = f"Same date and amount as “{t.description[:60]}”, already saved. Untick it if it's the same payment."
        elif h in seen:
            first = seen[h]
            row.duplicate_kind = "in_file"
            row.duplicate_note = f"Looks the same as another row in this file ({first.description[:40]}). Both kept, since two identical payments can be real."
        seen.setdefault(h, row)
    return exact


def start_import(db: Session, user: User, source: str, filename: str | None, content: bytes) -> ImportBatch:
    sha = hashlib.sha256(content).hexdigest()
    batch = ImportBatch(
        user_id=user.id, source_type=source, original_filename=(filename or None) and filename[:255],
        file_sha256=sha, file_size=len(content), status="processing", warnings=[],
    )
    db.add(batch)
    db.flush()

    previous = db.scalar(
        select(ImportBatch).where(
            ImportBatch.user_id == user.id, ImportBatch.file_sha256 == sha,
            ImportBatch.status == "completed", ImportBatch.id != batch.id,
        ).order_by(ImportBatch.created_at.desc())
    )
    warnings: list[str] = []
    if previous:
        warnings.append(f"You already imported this exact {'text' if source == 'sms' else 'file'} on {previous.created_at:%d %b %Y}. Rows that are already saved have been unticked.")

    try:
        parsed: ParseResult = IMPORTERS[source].parse(content, filename or "")
    except Exception:
        log.exception("importer crashed")
        parsed = ParseResult([], [(None, "", "Something went wrong while reading this file. Please check it's a bank statement and try again.")])

    warnings += parsed.warnings
    for row_no, raw, message in parsed.errors:
        db.add(ImportError(batch_id=batch.id, row_number=row_no, raw_text=(raw or None) and raw[:2000], message=message[:500]))

    rows: list[ImportRow] = []
    for pos, p in enumerate(parsed.rows):
        row = ImportRow(
            batch_id=batch.id, user_id=user.id, position=pos, row_number=p.row_number or None, raw_text=p.raw_text,
            occurred_on=p.occurred_on, description=p.description, merchant=p.merchant, amount=p.amount, type=p.type,
            balance_after=p.balance_after, include=True, edited=False,
        )
        computed = compute_problems(row)
        # Keep the parser's specific message ("Couldn't read the date '31/02'") when it has one.
        row.problems = (p.problems + [c for c in computed if "future" in c]) if p.problems else computed
        rows.append(row)

    batch.rows_found = len(rows)
    batch.rows_failed = len(parsed.errors)
    if rows:
        batch.rows_duplicate = mark_duplicates(db, user, rows)
        batch.ai_status = categorise(db, user, rows)
        db.add_all(rows)
        batch.status = "needs_review"
    else:
        batch.status = "failed"
    batch.warnings = warnings
    return batch

