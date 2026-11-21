"""CSV bank statements.

Banks name their columns differently ("Txn Date", "Value Date", "Withdrawal
Amt.", "Debit", "Amount (INR)"...), put a few lines of account details above
the table, and use commas, semicolons or tabs. This importer finds the
header row, maps columns by many possible names, and reads every row."""
import csv
import io
import re

from app.importers.base import ParsedRow, ParseResult
from app.importers.normalize import clean_description, detect_day_first, guess_merchant, parse_amount, parse_date

# Possible header names for each field, compared after lower-casing and
# removing punctuation. Order matters: the first match wins.
COLUMN_NAMES = {
    "type": ["type", "dr cr", "drcr", "cr dr", "transaction type", "debit credit", "txn type"],  # before debit/credit so "Dr/Cr" is the type column
    "date": ["transaction date", "txn date", "tran date", "date", "posting date", "value date", "value dt", "txn dt", "trans date", "booking date", "completed date", "started date"],
    "description": ["description", "narration", "particulars", "transaction details", "details", "remarks", "transaction remarks", "merchant", "payee", "name", "memo", "transaction description"],
    "debit": ["debit", "debit amount", "withdrawal", "withdrawal amt", "withdrawal amount", "withdrawals", "dr", "dr amount", "money out", "paid out", "debit inr", "amount debited"],
    "credit": ["credit", "credit amount", "deposit", "deposit amt", "deposit amount", "deposits", "cr", "cr amount", "money in", "paid in", "credit inr", "amount credited"],
    "amount": ["amount", "transaction amount", "amount inr", "txn amount", "amt", "value", "amount rs"],
    "balance": ["balance", "closing balance", "running balance", "available balance", "balance inr", "bal"],
}
SUMMARY_WORDS = re.compile(r"(opening balance|closing balance|total|statement summary|brought forward|carried forward|end of statement|\*\*\*)", re.I)


def _key(h: str) -> str:
    return " ".join(re.sub(r"[^a-z0-9/ ]", " ", h.lower()).replace("/", " ").split())


def _map_columns(header: list[str]) -> dict[str, int]:
    keys = [_key(h) for h in header]
    mapping: dict[str, int] = {}
    for field, names in COLUMN_NAMES.items():
        for name in names:
            k = _key(name)
            # exact match first, then "starts with" (e.g. "withdrawal amt inr")
            idx = next((i for i, h in enumerate(keys) if h == k and i not in mapping.values()), None)
            if idx is None:
                idx = next((i for i, h in enumerate(keys) if h.startswith(k + " ") and i not in mapping.values()), None)
            if idx is not None:
                mapping[field] = idx
                break
    return mapping


def _decode(content: bytes) -> str:
    for enc in ("utf-8-sig", "cp1252", "latin-1"):
        try:
            return content.decode(enc)
        except UnicodeDecodeError:
            continue
    return content.decode("utf-8", errors="replace")


def _rows(text: str) -> list[list[str]]:
    sample = text[:5000]
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=",;\t|")
        delimiter = dialect.delimiter
    except csv.Error:
        delimiter = max(",;\t|", key=sample.count)
    return [[c.strip() for c in r] for r in csv.reader(io.StringIO(text), delimiter=delimiter)]


def parse_table(rows: list[list[str]]) -> ParseResult:
    """Shared by CSV files and tables found inside PDFs."""
    header_idx, mapping = None, {}
    for i, r in enumerate(rows[:40]):
        m = _map_columns(r)
        if "date" in m and ({"debit", "credit"} & m.keys() or "amount" in m):
            header_idx, mapping = i, m
            break
    if header_idx is None:
        return ParseResult(
            rows=[],
            errors=[(None, "", "We couldn't find the column headings. The file needs columns for the date and the amount (or debit and credit). Check it's a bank transaction export, not a summary.")],
        )
    data = rows[header_idx + 1 :]
    get = lambda r, f: r[mapping[f]] if f in mapping and mapping[f] < len(r) else ""  # noqa: E731
    day_first = detect_day_first([get(r, "date") for r in data])
    result = ParseResult(rows=[], errors=[])

    # Single signed "Amount" column with no Dr/Cr column: if nothing is
    # negative, we can't tell money in from money out, so assume spending
    # and tell the user.
    single = "amount" in mapping and not ({"debit", "credit"} & mapping.keys()) and "type" not in mapping
    all_positive = single and not any(get(r, "amount").strip().startswith(("-", "(")) for r in data)
    if all_positive:
        result.warnings.append("This file has one Amount column with no minus signs, so every row was treated as money out. Change any that were money in.")

    for offset, r in enumerate(data):
        line_no = header_idx + offset + 2  # 1-based line in the file
        if not any(c for c in r):
            continue
        if "date" in _map_columns(r):  # the heading repeated (e.g. on every PDF page)
            continue
        raw = ", ".join(r)
        date_text, desc = get(r, "date"), clean_description(get(r, "description"))
        occurred = parse_date(date_text, day_first)
        amount = direction = None
        if {"debit", "credit"} & mapping.keys():
            d_amt, _ = parse_amount(get(r, "debit"))
            c_amt, _ = parse_amount(get(r, "credit"))
            if d_amt and not c_amt:
                amount, direction = d_amt, "expense"
            elif c_amt and not d_amt:
                amount, direction = c_amt, "income"
            elif d_amt and c_amt:
                amount = None
            elif "amount" in mapping:
                amount, direction = parse_amount(get(r, "amount"))
        else:
            amount, direction = parse_amount(get(r, "amount"))
        if "type" in mapping:
            t = get(r, "type").strip().lower()
            if t.startswith(("d", "w", "out", "purchase", "payment", "-")):
                direction = "expense"
            elif t.startswith(("c", "in", "dep", "refund", "+")):
                direction = "income"
        if direction is None and amount is not None:
            direction = "expense" if all_positive else "income"
        balance, _ = parse_amount(get(r, "balance"))

        if occurred is None and amount is None:
            # Totals, "opening balance", page footers: not transactions.
            if SUMMARY_WORDS.search(raw) or len([c for c in r if c]) <= 2:
                continue
            result.errors.append((line_no, raw, "This line has no readable date or amount, so it was skipped."))
            continue
        if amount == 0:
            continue
        if SUMMARY_WORDS.search(desc) and occurred is None:
            continue

        problems = []
        if occurred is None:
            problems.append(f"Couldn't read the date “{date_text}”. Please enter it." if date_text else "No date on this line. Please enter it.")
        if amount is None:
            problems.append("Couldn't read the amount. Please enter it.")
        if not desc:
            desc = "(no description)"
            problems.append("No description. Please add one.")
        result.rows.append(
            ParsedRow(
                row_number=line_no,
                raw_text=raw[:2000],
                occurred_on=occurred,
                description=desc,
                amount=amount,
                type=direction if amount is not None else None,
                balance_after=balance,
                merchant=guess_merchant(desc),
                problems=problems,
            )
        )
    if not result.rows and not result.errors:
        result.errors.append((None, "", "The headings were found but there are no transactions under them."))
    return result


class CsvImporter:
    source_type = "csv"

    def parse(self, content: bytes, filename: str) -> ParseResult:
        return parse_table(_rows(_decode(content)))
