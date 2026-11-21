# Smart Import Engine (Phase 2 plan)

The database tables are ready (`import_batches`, `import_errors`, and the
provenance columns on `transactions`). This folder holds the shared types;
the parsers are built in Phase 2.

## Flow

1. **Upload** `POST /api/imports` (file or pasted SMS text).
   Check size (10 MB), extension and file signature *before* parsing.
   Hash the file (SHA-256) and warn if this exact file was imported before.
   Create an `import_batches` row with status `processing`.
2. **Parse** with the matching importer (`csv.py`, `pdf.py`, `sms.py`), each
   returning `ParseResult` (see `base.py`).
   - CSV: detect delimiter and header row; map columns by many possible names
     (Date / Txn Date / Value Date, Debit / Withdrawal, Credit / Deposit,
     Amount + Dr/Cr, Balance); try several date formats (DD/MM/YYYY first for
     Indian banks, then ISO, then MM/DD/YYYY only when unambiguous).
   - PDF: `pdfplumber` text and table extraction. No text layer means
     `needs_ocr = True` and a clear message (OCR is a later add-on).
   - SMS: regex templates for common bank formats ("debited by Rs 450.00 ...",
     "INR 1,200 credited ..."), with each message as one row.
   Amounts: strip ₹ / Rs / INR / commas, handle "(450.00)" and "450.00 Dr".
3. **Categorise** each row: learned user rules first, then keyword rules,
   then the AI model for leftovers (only the description is sent, never names
   or account numbers). Store `category_source`, `category_confidence` and
   `category_reason`; below 0.6 confidence is flagged "please check".
4. **Review** status `needs_review`. The user sees every row, fixes dates,
   amounts or categories, and un-ticks duplicates (`dedupe_hash` matches).
   AI never fills in a missing date or amount; the user must.
5. **Confirm** `POST /api/imports/{id}/confirm` saves the ticked rows in one
   database transaction with `source`, `import_batch_id` and `raw_text`, and
   updates the batch counts. Status becomes `completed`.

Uploaded files are processed in memory and not kept after parsing.
