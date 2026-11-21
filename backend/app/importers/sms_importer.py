"""Bank SMS messages, pasted in or uploaded as a .txt file.

CASIO never reads anyone's SMS inbox. The user copies messages in
themselves. One message per paragraph (blank line between messages), or
one per line if there are no blank lines. Messages that aren't
transactions (OTPs, offers) are skipped and counted."""
import re

from app.importers.base import ParsedRow, ParseResult
from app.importers.normalize import clean_description, guess_merchant, parse_amount, parse_date

AMOUNT = re.compile(r"(?:rs\.?|inr|₹)\s*([\d,]+(?:\.\d{1,2})?)", re.I)
BALANCE = re.compile(r"(?:avl\.?\s*bal(?:ance)?|available\s+bal(?:ance)?|a/c\s+bal(?:ance)?|bal(?:ance)?)\s*(?:is|:|-)?\s*(?:rs\.?|inr|₹)\s*([\d,]+(?:\.\d{1,2})?)", re.I)
DEBIT = re.compile(r"\b(debited|spent|paid|withdrawn|sent|deducted|purchase|txn of|used for|dr\b|debit)", re.I)
CREDIT = re.compile(r"\b(credited|received|deposited|refund(?:ed)?|cr\b|credit(?! card))", re.I)
NOT_TXN = re.compile(r"\b(otp|one time password|verification code|offer|cashback upto|apply now|pre-approved|due date|is due|statement is ready|minimum amount due|requested|will be debited)\b", re.I)
DATE_TOKENS = [
    r"\d{1,2}[/-]\d{1,2}[/-]\d{2,4}",
    r"\d{4}-\d{2}-\d{2}",
    r"\d{1,2}[- ]?[A-Za-z]{3}[- ]?\d{2,4}",
    r"[A-Za-z]{3} \d{1,2},? \d{4}",
]
DATE = re.compile(r"(?<![\d])(" + "|".join(DATE_TOKENS) + r")(?![\d])")
MERCHANT = [
    re.compile(r"\b(?:at|to|towards|for)\s+([A-Za-z0-9&.'\- ]{2,40}?)(?=\s+(?:on|via|ref|upi|avl|bal|txn|using|from|\.|,)|[.,;]|$)", re.I),
    re.compile(r"\binfo[:\-]\s*([A-Za-z0-9&.'\-/ ]{2,40})", re.I),
    re.compile(r"\bfrom\s+([A-Za-z0-9&.'\- ]{2,40}?)(?=\s+(?:on|via|ref|upi|avl|bal|\.|,)|[.,;]|$)", re.I),
    re.compile(r"\(([A-Za-z][A-Za-z .&']{2,40})\)"),  # VPA name in brackets
]


def split_messages(text: str) -> list[str]:
    text = text.replace("\r\n", "\n").strip()
    if not text:
        return []
    parts = re.split(r"\n\s*\n", text) if re.search(r"\n\s*\n", text) else text.split("\n")
    return [" ".join(p.split()) for p in parts if p.strip()]


def _merchant(msg: str) -> str | None:
    for pattern in MERCHANT:
        m = pattern.search(msg)
        if m:
            name = m.group(1).strip(" .-")
            name = re.sub(r"\S+@\S+", "", name)  # UPI id
            if re.search(r"(a/c|acct|account|card|xx|\*\*)", name, re.I) or not re.search(r"[A-Za-z]{2}", name):
                continue
            return name.title()[:200]
    return None


class SmsImporter:
    source_type = "sms"

    def parse(self, content: bytes, filename: str) -> ParseResult:
        text = content.decode("utf-8", errors="replace")
        result = ParseResult([], [])
        skipped = 0
        for i, msg in enumerate(split_messages(text), start=1):
            if NOT_TXN.search(msg):
                skipped += 1
                continue
            bal_match = BALANCE.search(msg)
            amount_match = next((m for m in AMOUNT.finditer(msg) if not (bal_match and m.start() >= bal_match.start() and m.end() <= bal_match.end())), None)
            is_debit, is_credit = DEBIT.search(msg), CREDIT.search(msg)
            if amount_match is None or not (is_debit or is_credit):
                skipped += 1
                continue
            amount, _ = parse_amount(amount_match.group(1))
            # Whichever word comes first decides ("debited ... credited to X" is a debit).
            if is_debit and is_credit:
                direction = "expense" if is_debit.start() < is_credit.start() else "income"
            else:
                direction = "expense" if is_debit else "income"
            date_match = DATE.search(msg)
            occurred = parse_date(date_match.group(1)) if date_match else None
            balance = parse_amount(bal_match.group(1))[0] if bal_match else None
            merchant = _merchant(msg)
            problems = []
            if occurred is None:
                problems.append("This message has no date we could read. Please enter it.")
            if amount is None:
                problems.append("Couldn't read the amount. Please enter it.")
            desc = clean_description(merchant or ("Money received" if direction == "income" else "Card/UPI payment"))
            result.rows.append(
                ParsedRow(
                    row_number=i,
                    raw_text=msg[:2000],
                    occurred_on=occurred,
                    description=desc,
                    amount=amount,
                    type=direction,
                    balance_after=balance,
                    merchant=merchant or guess_merchant(msg),
                    problems=problems,
                )
            )
        if skipped:
            result.warnings.append(f"{skipped} message{'s were' if skipped != 1 else ' was'} skipped because {'they' if skipped != 1 else 'it'} didn't look like a completed payment (for example OTPs, offers or reminders).")
        if not result.rows:
            result.errors.append((None, "", "No transaction messages were found. Paste bank SMS that say an amount was debited or credited, one message per line or with a blank line between them."))
        return result
