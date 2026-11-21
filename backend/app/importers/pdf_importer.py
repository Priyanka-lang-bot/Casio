"""PDF bank statements (text-based).

Two ways to read a statement, tried in order:
1. Tables: if pdfplumber finds a ruled table with headings, it's read the
   same way as a CSV file.
2. Lines: otherwise each text line that starts with a date is a
   transaction. Whether an amount is money in or out is decided by which
   column it sits under (Debit/Withdrawal vs Credit/Deposit), a Dr/Cr
   marker, or how the running balance changed. If none of those works the
   row is flagged for the user; we never guess.

Scanned statements (photos of paper, no text inside) are detected and the
user is told they need OCR, which is a later add-on."""
import io
import re
from decimal import Decimal

import pdfplumber
from pdfminer.pdfdocument import PDFPasswordIncorrect

from app.importers.base import ParsedRow, ParseResult
from app.importers.csv_importer import SUMMARY_WORDS, parse_table
from app.importers.normalize import clean_description, detect_day_first, guess_merchant, parse_amount, parse_date

MAX_PAGES = 100
# Money in a statement always has 2 decimals ("1,250.00"); this keeps
# reference numbers like "40291837" from being read as amounts.
MONEY = re.compile(r"^\(?[-+]?(₹|Rs\.?|INR)?\s?\d{1,3}(,\d{2,3})*(\.\d{2})\)?(Dr|Cr|DR|CR|-)?$|^\(?[-+]?(₹|Rs\.?|INR)?\d+\.\d{2}\)?(Dr|Cr|DR|CR|-)?$")
DEBIT_HEAD = re.compile(r"^(debit|debits|withdrawal|withdrawals|withdrawal\(dr\)|dr|paid|out)\b", re.I)
CREDIT_HEAD = re.compile(r"^(credit|credits|deposit|deposits|deposit\(cr\)|cr|received|in)\b", re.I)
BALANCE_HEAD = re.compile(r"^(balance|bal)\b", re.I)


def _lines(page) -> list[list[dict]]:
    """Group the page's words into visual lines (same height on the page)."""
    words = page.extract_words(keep_blank_chars=False, x_tolerance=1.5, y_tolerance=3)
    lines: list[list[dict]] = []
    for w in sorted(words, key=lambda w: (round(w["top"]), w["x0"])):
        if lines and abs(lines[-1][0]["top"] - w["top"]) <= 3:
            lines[-1].append(w)
        else:
            lines.append([w])
    return [sorted(line, key=lambda w: w["x0"]) for line in lines]


def _centre(w: dict) -> float:
    return (w["x0"] + w["x1"]) / 2


def _leading_date(words: list[dict], day_first: bool):
    """A transaction line starts with a date, written as 1 to 3 words."""
    for n in (3, 2, 1):
        if len(words) >= n:
            d = parse_date(" ".join(w["text"] for w in words[:n]), day_first)
            if d:
                return d, n
    return None, 0


class PdfImporter:
    source_type = "pdf"

    def parse(self, content: bytes, filename: str) -> ParseResult:
        try:
            pdf = pdfplumber.open(io.BytesIO(content))
        except Exception as exc:
            wrapped = exc.args[0] if exc.args else None
            if isinstance(exc, PDFPasswordIncorrect) or isinstance(wrapped, PDFPasswordIncorrect):
                return ParseResult([], [(None, "", "This PDF is password-protected. Open it, save a copy without a password (Print → Save as PDF), and upload that.")])
            return ParseResult([], [(None, "", "This file couldn't be opened as a PDF. It may be damaged. Try downloading the statement again.")])
        with pdf:
            pages = pdf.pages[:MAX_PAGES]
            texts = [(p.extract_text() or "") for p in pages]
            if sum(len(t.strip()) for t in texts) < 30 * max(1, len(pages)) and not any(re.search(r"\d", t) for t in texts):
                return ParseResult(
                    [], [(None, "", "This looks like a scanned statement (a picture of paper), so there's no text to read. Scanned PDFs need OCR, which CASIO doesn't support yet. Download a text PDF or CSV from your bank's website instead.")],
                    needs_ocr=True,
                )
            result = self._from_tables(pages)
            if not result.rows:
                result = self._from_lines(pages, texts)
            if len(pdf.pages) > MAX_PAGES:
                result.warnings.append(f"Only the first {MAX_PAGES} pages were read.")
            return result

    # -- 1. ruled tables ----------------------------------------------------
    def _from_tables(self, pages) -> ParseResult:
        rows: list[list[str]] = []
        for p in pages:
            for table in p.extract_tables():
                rows += [[" ".join((c or "").split()) for c in r] for r in table]
        if not rows:
            return ParseResult([], [])
        result = parse_table(rows)
        for r in result.rows:  # table "line numbers" aren't meaningful in a PDF
            r.row_number = 0
        return result

    # -- 2. text lines --------------------------------------------------------
    def _from_lines(self, pages, texts) -> ParseResult:
        all_lines = [(pi, line) for pi, p in enumerate(pages) for line in _lines(p)]
        day_first = detect_day_first([ln[0]["text"] for _, ln in all_lines if ln])
        result = ParseResult([], [])
        columns: dict[str, float] = {}  # column name -> x centre, from the heading line
        prev_balance: Decimal | None = None
        last: ParsedRow | None = None
        count = 0

        for page_idx, words in all_lines:
            text = " ".join(w["text"] for w in words)
            heads = {}
            for w in words:
                if DEBIT_HEAD.match(w["text"]):
                    heads["debit"] = _centre(w)
                elif CREDIT_HEAD.match(w["text"]):
                    heads["credit"] = _centre(w)
                elif BALANCE_HEAD.match(w["text"]):
                    heads["balance"] = _centre(w)
            if "debit" in heads and "credit" in heads:
                columns = heads
                last = None
                continue
            if re.search(r"opening balance|balance brought forward|b/f", text, re.I):
                money = [w for w in words if MONEY.match(w["text"])]
                if money:
                    prev_balance, _ = parse_amount(money[-1]["text"])
                last = None
                continue

            occurred, n = _leading_date(words, day_first)
            money = [w for w in words[n:] if MONEY.match(w["text"])]
            if occurred is None or not money:
                # A wrapped description continues on the next line.
                if last is not None and not money and occurred is None and len(text) < 80 and not SUMMARY_WORDS.search(text) and not re.search(r"page \d|statement|account", text, re.I):
                    last.description = clean_description(f"{last.description} {text}")
                    last.raw_text += "\n" + text
                    last.merchant = guess_merchant(last.description)
                elif occurred is None:
                    last = None
                continue

            count += 1
            first_money_idx = words.index(money[0])
            desc = clean_description(" ".join(w["text"] for w in words[n:first_money_idx]))
            amount = direction = balance = None
            problems: list[str] = []

            if columns:
                picked = {}
                for w in money:
                    col = min(columns, key=lambda c: abs(columns[c] - _centre(w)))
                    picked[col] = w["text"]
                if "balance" in picked:
                    balance, _ = parse_amount(picked["balance"])
                if "debit" in picked and "credit" not in picked:
                    amount, _ = parse_amount(picked["debit"])
                    direction = "expense"
                elif "credit" in picked and "debit" not in picked:
                    amount, _ = parse_amount(picked["credit"])
                    direction = "income"
            if amount is None:
                amount, direction = parse_amount(money[0]["text"])
                if len(money) >= 2:
                    balance, _ = parse_amount(money[-1]["text"])
                if direction is None and balance is not None and prev_balance is not None and amount is not None:
                    if prev_balance + amount == balance:
                        direction = "income"
                    elif prev_balance - amount == balance:
                        direction = "expense"
            if direction is None:
                problems.append("Couldn't tell if this was money in or out. Please choose.")
            if balance is not None:
                prev_balance = balance
            if not desc:
                desc = "(no description)"
                problems.append("No description. Please add one.")

            last = ParsedRow(
                row_number=page_idx + 1,  # page number, shown as "page 2"
                raw_text=text[:2000],
                occurred_on=occurred,
                description=desc,
                amount=amount,
                type=direction,
                balance_after=balance,
                merchant=guess_merchant(desc),
                problems=problems,
            )
            result.rows.append(last)

        if count == 0:
            result.errors.append((None, "", "No transactions were found in this PDF. It may be a summary page or an unusual layout. Try the CSV download from your bank instead."))
        return result
