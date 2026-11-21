"""Smart Import endpoints: upload, review, fix, confirm, undo.

Nothing from an upload counts in the user's totals until they press
"Save" (confirm). Every saved transaction remembers which import it came
from and the exact original text."""
import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.audit import audit
from app.db import get_db
from app.deps import get_current_user
from app.importers.base import MAX_SMS_CHARS, MAX_UPLOAD_BYTES, dedupe_hash, normalise_description
from app.importers.categorize import REVIEW_BELOW
from app.importers.pipeline import ImportRejected, compute_problems, detect_source, start_import
from app.models import Category, ImportBatch, ImportError, ImportRow, Transaction, User
from app.routers.profile import get_or_create_profile
from app.routers.transactions import _check_category
from app.schemas import ImportBatchOut, ImportBulkInclude, ImportDetailOut, ImportErrorOut, ImportRowOut, ImportRowUpdate

router = APIRouter(tags=["imports"])


def _row_out(r: ImportRow) -> ImportRowOut:
    out = ImportRowOut.model_validate(r)
    out.category_name = r.category.name if r.category else None
    out.category_confidence = float(r.category_confidence) if r.category_confidence is not None else None
    out.needs_check = r.category_id is None or (r.category_source != "user" and (out.category_confidence or 0) < REVIEW_BELOW)
    return out


def _detail(db: Session, batch: ImportBatch) -> ImportDetailOut:
    out = ImportDetailOut.model_validate(batch)
    out.errors = [ImportErrorOut.model_validate(e) for e in db.scalars(select(ImportError).where(ImportError.batch_id == batch.id).order_by(ImportError.row_number.nulls_first()))]
    out.rows = [_row_out(r) for r in db.scalars(select(ImportRow).where(ImportRow.batch_id == batch.id).order_by(ImportRow.position))]
    return out


def _get_batch(db: Session, user: User, batch_id: uuid.UUID) -> ImportBatch:
    b = db.scalar(select(ImportBatch).where(ImportBatch.id == batch_id, ImportBatch.user_id == user.id))
    if b is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "That import wasn't found.")
    return b


def _need_review(b: ImportBatch) -> None:
    if b.status != "needs_review":
        raise HTTPException(status.HTTP_409_CONFLICT, "This import has already been saved or cancelled.")


@router.post("/imports", response_model=ImportDetailOut, status_code=201)
async def upload(
    file: UploadFile | None = File(None),
    sms_text: str | None = Form(None),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Send either a file (CSV, PDF, or .txt of SMS) or pasted SMS text."""
    if file is not None and file.filename:
        content = await file.read(MAX_UPLOAD_BYTES + 1)
        filename = file.filename
        try:
            source = detect_source(filename, content)
        except ImportRejected as e:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(e)) from None
    elif sms_text and sms_text.strip():
        if len(sms_text) > MAX_SMS_CHARS:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "That's too much text at once. Paste up to about 1,000 messages at a time.")
        content, filename, source = sms_text.encode(), None, "sms"
    else:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Choose a file to upload or paste some SMS messages.")

    batch = start_import(db, user, source, filename, content)
    audit(db, "import.upload", user.id, "import_batch", batch.id, source=source, rows=batch.rows_found)
    db.commit()
    return _detail(db, batch)


@router.get("/imports", response_model=list[ImportBatchOut])
def list_imports(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return db.scalars(
        select(ImportBatch).where(ImportBatch.user_id == user.id).order_by(ImportBatch.created_at.desc()).limit(50)
    ).all()


@router.get("/imports/{batch_id}", response_model=ImportDetailOut)
def get_import(batch_id: uuid.UUID, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return _detail(db, _get_batch(db, user, batch_id))


@router.patch("/imports/{batch_id}/rows/{row_id}", response_model=list[ImportRowOut])
def update_row(
    batch_id: uuid.UUID, row_id: uuid.UUID, data: ImportRowUpdate,
    user: User = Depends(get_current_user), db: Session = Depends(get_db),
):
    """Fix one row. Returns every row that changed (more than one when
    apply_to_similar is used)."""
    batch = _get_batch(db, user, batch_id)
    _need_review(batch)
    row = db.scalar(select(ImportRow).where(ImportRow.id == row_id, ImportRow.batch_id == batch.id, ImportRow.user_id == user.id))
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "That row wasn't found.")
    sent = data.model_fields_set
    changed = [row]
    for field in ("occurred_on", "description", "amount", "type"):
        if field in sent and getattr(data, field) is not None and getattr(data, field) != getattr(row, field):
            setattr(row, field, getattr(data, field))
            row.edited = True
    if "include" in sent and data.include is not None:
        row.include = data.include
    if "category_id" in sent:
        if data.category_id is not None:
            _check_category(db, user, data.category_id, row.type or "expense")
        if data.category_id != row.category_id or row.category_source != "user":
            row.category_id = data.category_id
            row.category = db.get(Category, data.category_id) if data.category_id else None
            row.category_source = "user" if data.category_id else None
            row.category_confidence = None
            row.category_reason = "You chose this." if data.category_id else None
            row.edited = True
        if data.apply_to_similar and data.category_id:
            key = normalise_description(row.merchant or row.description)
            others = db.scalars(select(ImportRow).where(ImportRow.batch_id == batch.id, ImportRow.id != row.id, ImportRow.type == row.type)).all()
            for o in others:
                if o.category_source != "user" and normalise_description(o.merchant or o.description) == key:
                    o.category_id, o.category = row.category_id, row.category
                    o.category_source, o.category_confidence = "user", None
                    o.category_reason = f"Changed with “{row.description[:60]}”."
                    changed.append(o)
    if row.category_id and row.category and row.category.kind not in ("transfer", row.type):
        # Money in/out was flipped and the old category no longer fits.
        row.category_id, row.category, row.category_source, row.category_confidence = None, None, None, None
        row.category_reason = "Please choose a category that matches money in/out."
    row.problems = compute_problems(row)
    audit(db, "import.row_update", user.id, "import_batch", batch.id)
    db.commit()
    return [_row_out(r) for r in changed]


@router.post("/imports/{batch_id}/include", response_model=ImportDetailOut)
def bulk_include(batch_id: uuid.UUID, data: ImportBulkInclude, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    batch = _get_batch(db, user, batch_id)
    _need_review(batch)
    for r in db.scalars(select(ImportRow).where(ImportRow.batch_id == batch.id)):
        if data.which == "all" or (data.which == "duplicates" and r.duplicate_kind) or (data.which == "ready" and not r.problems):
            r.include = data.include
    db.commit()
    return _detail(db, batch)


@router.post("/imports/{batch_id}/confirm", response_model=ImportBatchOut)
def confirm(batch_id: uuid.UUID, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Save the ticked rows as real transactions, all at once."""
    batch = _get_batch(db, user, batch_id)
    _need_review(batch)
    rows = db.scalars(select(ImportRow).where(ImportRow.batch_id == batch.id, ImportRow.include.is_(True)).order_by(ImportRow.position)).all()
    if not rows:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "No rows are ticked. Tick the transactions you want to save.")
    broken = [r for r in rows if compute_problems(r)]
    if broken:
        n = len(broken)
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            f"{n} ticked row{'s' if n != 1 else ''} still need{'' if n != 1 else 's'} fixing (missing date, amount or money in/out). Fix {'them' if n != 1 else 'it'} or untick {'them' if n != 1 else 'it'}.",
        )
    currency = get_or_create_profile(db, user).currency
    for r in rows:
        db.add(
            Transaction(
                user_id=user.id, currency=currency, type=r.type, amount=r.amount, occurred_on=r.occurred_on,
                description=r.description, merchant=r.merchant, source=batch.source_type, import_batch_id=batch.id,
                raw_text=r.raw_text, balance_after=r.balance_after,
                dedupe_hash=dedupe_hash(r.occurred_on, r.amount, r.type, r.description),
                category_id=r.category_id, category_source=r.category_source,
                category_confidence=r.category_confidence, category_reason=r.category_reason,
            )
        )
    batch.rows_imported = len(rows)
    batch.status = "completed"
    batch.completed_at = datetime.now(UTC)
    # The review copies are no longer needed: the transactions now hold the
    # original text and point back to this import.
    db.execute(delete(ImportRow).where(ImportRow.batch_id == batch.id))
    audit(db, "import.confirm", user.id, "import_batch", batch.id, saved=len(rows))
    db.commit()
    return batch


@router.delete("/imports/{batch_id}", response_model=ImportBatchOut)
def cancel_or_undo(batch_id: uuid.UUID, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Waiting for review: throw it away. Already saved: undo it, which
    deletes the transactions that came from this import."""
    batch = _get_batch(db, user, batch_id)
    if batch.status == "cancelled":
        return batch
    removed = 0
    if batch.status == "completed":
        removed = db.execute(
            delete(Transaction).where(Transaction.import_batch_id == batch.id, Transaction.user_id == user.id)
        ).rowcount
    db.execute(delete(ImportRow).where(ImportRow.batch_id == batch.id))
    was = batch.status
    batch.status = "cancelled"
    audit(db, "import.undo" if was == "completed" else "import.cancel", user.id, "import_batch", batch.id, removed=removed)
    db.commit()
    return batch

