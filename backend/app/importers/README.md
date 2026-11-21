# Smart Import Engine

## Flow

1. **Upload** `POST /api/imports` with a file (CSV, PDF, `.txt` of SMS) or
   `sms_text`. `pipeline.detect_source` checks size (10 MB), extension *and*
   contents (a renamed file is refused) before parsing. Files are read in
   memory and not kept.
2. **Parse** with `csv_importer.py`, `pdf_importer.py` or `sms_importer.py`,
   each returning `ParseResult` (`base.py`). Values come from
   `normalize.py`, which returns `None` when unsure. A row with a missing
   date, amount or direction is shown with a problem for the user to fix;
   nothing is invented.
3. **Check duplicates** (`pipeline.mark_duplicates`) against saved
   transactions in the same date range (manual ones too):
   exact match → unticked; same date + amount → flagged, still ticked;
   repeated within the file → flagged, still ticked (two coffees can be real).
4. **Categorise** (`categorize.py`): keyword rules with a confidence. Rows
   under 0.8 go to the AI (`app/ai.py`) if `ANTHROPIC_API_KEY` is set; the AI
   only sees a privacy-scrubbed description and direction, and its answer
   is used only if it fits money in/out and is more confident. Under 0.6 is
   shown as "Please check". The batch records `ai_status`.
5. **Review** rows live in `import_rows` (status `needs_review`).
   `PATCH /api/imports/{id}/rows/{row}` edits a row; problems are recomputed.
   `apply_to_similar` changes the same shop's other rows in this import.
6. **Confirm** `POST /api/imports/{id}/confirm` refuses if a ticked row still
   has problems, then saves all ticked rows in one database transaction with
   `source`, `import_batch_id`, `raw_text`, `balance_after`, `dedupe_hash`
   and the category source/confidence/reason.
7. **Undo** `DELETE /api/imports/{id}` cancels a pending import, or deletes
   the transactions of a saved one.

## Adding a bank format

Most CSVs work through `COLUMN_NAMES` in `csv_importer.py`: add the bank's
heading to the right list. For SMS, add a keyword to `DEBIT`/`CREDIT` or a
pattern to `MERCHANT` in `sms_importer.py`. Add a test in
`tests/test_import.py` with a real (anonymised) example.
