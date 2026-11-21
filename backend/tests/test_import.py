"""Smart import: parsers, categorisation and the review-then-save flow.

Sample files live in docs/samples/ (the same ones you can use for a demo)."""
import io
import json
import types
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle

from app import ai
from app.importers.csv_importer import CsvImporter
from app.importers.normalize import detect_day_first, parse_amount, parse_date, privacy_scrub
from app.importers.pdf_importer import PdfImporter
from app.importers.sms_importer import SmsImporter
from tests.conftest import make_user

SAMPLES = Path(__file__).resolve().parents[2] / "docs" / "samples"


def sample(name: str) -> bytes:
    return (SAMPLES / name).read_bytes()


# ---- normalisation -------------------------------------------------------
@pytest.mark.parametrize(
    "text,expected",
    [
        ("₹1,23,456.50", (Decimal("123456.50"), None)),
        ("450.00 Dr", (Decimal("450.00"), "expense")),
        ("1,200 CR", (Decimal("1200.00"), "income")),
        ("(1,200.00)", (Decimal("1200.00"), "expense")),
        ("-75", (Decimal("75.00"), "expense")),
        ("Rs. 99", (Decimal("99.00"), None)),
        ("INR 5,000.5", (Decimal("5000.50"), None)),
        ("", (None, None)),
        ("-", (None, None)),
        ("abc", (None, None)),
    ],
)
def test_parse_amount(text, expected):
    assert parse_amount(text) == expected


def test_parse_date_formats():
    assert parse_date("05/03/2026") == date(2026, 3, 5)  # day first (India)
    assert parse_date("05/03/2026", day_first=False) == date(2026, 5, 3)
    assert parse_date("2026-03-05") == date(2026, 3, 5)
    assert parse_date("5 Mar 2026") == date(2026, 3, 5)
    assert parse_date("05-Mar-26") == date(2026, 3, 5)
    assert parse_date("1st March 2026") == date(2026, 3, 1)
    assert parse_date("05/03/2026 14:22") == date(2026, 3, 5)
    assert parse_date("31/13/26") is None
    assert parse_date("hello") is None


def test_detect_day_first():
    assert detect_day_first(["03/04/2026", "25/04/2026"]) is True
    assert detect_day_first(["03/04/2026", "04/25/2026"]) is False
    assert detect_day_first(["03/04/2026"]) is True  # can't tell: Indian default


def test_privacy_scrub_removes_identifiers():
    out = privacy_scrub("UPI-RAMESH-ramesh123@okaxis-REF 6123498712 card XX4321")
    assert "okaxis" not in out and "6123498712" not in out and "4321" not in out


# ---- CSV ------------------------------------------------------------------
def test_csv_sample_statement():
    r = CsvImporter().parse(sample("sample-statement.csv"), "sample-statement.csv")
    assert len(r.rows) == 17 and not r.errors  # preamble, blank and balance lines skipped
    salary = r.rows[0]
    assert (salary.occurred_on, salary.amount, salary.type, salary.balance_after) == (
        date(2026, 10, 1), Decimal("85000.00"), "income", Decimal("102340.50"))
    swiggy = r.rows[1]
    assert (swiggy.amount, swiggy.type, swiggy.merchant) == (Decimal("450.00"), "expense", "Swiggy")
    bad = r.rows[-1]
    assert bad.occurred_on is None and "31/13/26" in bad.problems[0]


def test_csv_signed_amount_semicolons_iso_dates():
    text = "Date;Description;Amount (INR)\n2026-10-01;Salary;50000\n2026-10-02;Zomato;-320.50\n"
    r = CsvImporter().parse(text.encode(), "x.csv")
    assert [(x.type, x.amount) for x in r.rows] == [("income", Decimal("50000.00")), ("expense", Decimal("320.50"))]
    assert not r.warnings


def test_csv_amount_with_dr_cr_column_and_us_dates():
    text = "Txn Date,Particulars,Amount,Dr/Cr,Balance\n10/25/2026,Rent,15000,DR,5000\n10/01/2026,Salary,20000,CR,20000\n"
    r = CsvImporter().parse(text.encode(), "x.csv")
    assert r.rows[0].occurred_on == date(2026, 10, 25) and r.rows[0].type == "expense"
    assert r.rows[1].occurred_on == date(2026, 10, 1) and r.rows[1].type == "income"


def test_csv_all_positive_single_amount_warns():
    text = "Date,Merchant,Amount\n01/10/2026,Amazon,999\n"
    r = CsvImporter().parse(text.encode(), "card.csv")
    assert r.rows[0].type == "expense" and "money out" in r.warnings[0]


def test_csv_without_headings_is_a_clear_error():
    r = CsvImporter().parse(b"foo,bar\n1,2\n", "x.csv")
    assert not r.rows and "column headings" in r.errors[0][2]


# ---- PDF ------------------------------------------------------------------
def test_pdf_text_statement_uses_columns():
    r = PdfImporter().parse(sample("sample-statement.pdf"), "s.pdf")
    assert len(r.rows) == 9 and not r.errors
    assert (r.rows[0].type, r.rows[0].amount) == ("income", Decimal("85000.00"))
    assert all(x.type == "expense" for x in r.rows[1:])
    assert r.rows[3].balance_after == Decimal("123858.95")


def test_pdf_scanned_is_flagged_for_ocr():
    r = PdfImporter().parse(sample("sample-scanned.pdf"), "scan.pdf")
    assert r.needs_ocr and not r.rows and "OCR" in r.errors[0][2]


def test_pdf_ruled_table():
    buf = io.BytesIO()
    data = [["Date", "Narration", "Debit", "Credit", "Balance"],
            ["01/10/2026", "SALARY", "", "50,000.00", "50,000.00"],
            ["02/10/2026", "SWIGGY", "250.00", "", "49,750.00"]]
    t = Table(data)
    t.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), 0.5, (0, 0, 0))]))
    SimpleDocTemplate(buf, pagesize=A4).build([t])
    r = PdfImporter().parse(buf.getvalue(), "t.pdf")
    assert [(x.type, x.amount) for x in r.rows] == [("income", Decimal("50000.00")), ("expense", Decimal("250.00"))]


def test_pdf_without_headings_uses_running_balance():
    buf = io.BytesIO()
    c = canvas.Canvas(buf)
    c.drawString(40, 800, "Opening Balance 1,000.00")
    c.drawString(40, 780, "01/10/2026 SALARY CREDIT 500.00 1,500.00")
    c.drawString(40, 760, "02/10/2026 GROCERY SHOP 200.00 1,300.00")
    c.drawString(40, 740, "03/10/2026 MYSTERY 50.00")
    c.save()
    r = PdfImporter().parse(buf.getvalue(), "x.pdf")
    assert [x.type for x in r.rows] == ["income", "expense", None]
    assert "money in or out" in r.rows[2].problems[0]  # never guessed


def test_pdf_password_and_garbage():
    buf = io.BytesIO()
    c = canvas.Canvas(buf, encrypt="secret")
    c.drawString(40, 800, "01/10/2026 X 1.00")
    c.save()
    assert "password" in PdfImporter().parse(buf.getvalue(), "p.pdf").errors[0][2]
    assert "couldn't be opened" in PdfImporter().parse(b"%PDF-1.4 broken", "b.pdf").errors[0][2]


# ---- SMS ------------------------------------------------------------------
def test_sms_sample():
    r = SmsImporter().parse(sample("sample-sms.txt"), "sms.txt")
    got = [(x.occurred_on, x.amount, x.type, x.description) for x in r.rows]
    assert got[0] == (date(2026, 11, 2), Decimal("450.00"), "expense", "Swiggy")
    assert got[1][2] == "income" and got[1][1] == Decimal("85000.00")
    assert got[2][3] == "Amazon" and got[3][3] == "Netflix"
    assert r.rows[0].balance_after == Decimal("62070.95")  # balance is not mistaken for the amount
    no_date = r.rows[4]
    assert no_date.occurred_on is None and no_date.problems  # date not invented
    assert len(r.rows) == 5 and "2 messages were skipped" in r.warnings[0]  # OTP + loan offer


# ---- API flow -------------------------------------------------------------
def upload(client, name, content=None):
    return client.post("/api/imports", files={"file": (name, content if content is not None else sample(name))})


def test_full_csv_import_flow(client):
    make_user(client)
    r = upload(client, "sample-statement.csv")
    assert r.status_code == 201, r.text
    batch = r.json()
    assert batch["status"] == "needs_review" and batch["rows_found"] == 17
    assert batch["ai_status"] in ("not_configured", "not_needed")
    rows = batch["rows"]
    swiggy = rows[1]
    assert swiggy["category_name"] == "Food and Dining" and swiggy["category_source"] == "keyword"
    assert swiggy["category_confidence"] == 0.9 and not swiggy["needs_check"]
    ramesh = next(x for x in rows if "RAMESH" in x["description"])
    assert ramesh["needs_check"] and ramesh["category_name"] == "Other"

    # Nothing counts yet
    assert client.get("/api/transactions").json()["total"] == 0

    # Can't save while a ticked row has no date
    bad = rows[-1]
    r = client.post(f"/api/imports/{batch['id']}/confirm")
    assert r.status_code == 422 and "1 ticked row still needs fixing" in r.json()["detail"]

    # Fix the date
    r = client.patch(f"/api/imports/{batch['id']}/rows/{bad['id']}", json={"occurred_on": "2026-10-31"})
    assert r.status_code == 200 and r.json()[0]["problems"] == [] and r.json()[0]["edited"]

    # Change Swiggy to Groceries for every Swiggy row in this file
    cats = {c["name"]: c["id"] for c in client.get("/api/categories").json()}
    r = client.patch(
        f"/api/imports/{batch['id']}/rows/{swiggy['id']}",
        json={"category_id": cats["Groceries"], "apply_to_similar": True},
    )
    changed = r.json()
    assert len(changed) == 2 and all(x["category_name"] == "Groceries" and x["category_source"] == "user" for x in changed)

    # A category that doesn't match money in/out is refused
    r = client.patch(f"/api/imports/{batch['id']}/rows/{swiggy['id']}", json={"category_id": cats["Salary and Income"]})
    assert r.status_code == 422

    # Untick one row, then save
    client.patch(f"/api/imports/{batch['id']}/rows/{ramesh['id']}", json={"include": False})
    r = client.post(f"/api/imports/{batch['id']}/confirm")
    assert r.status_code == 200 and r.json()["rows_imported"] == 16 and r.json()["status"] == "completed"

    txs = client.get("/api/transactions?limit=100").json()
    assert txs["total"] == 16
    t = next(x for x in txs["items"] if "SWIGGY" in x["description"])
    assert t["source"] == "csv" and t["import_batch_id"] == batch["id"] and t["category_source"] == "user"

    # Provenance in the database
    from app.db import SessionLocal
    from app.models import Transaction
    with SessionLocal() as db:
        row = db.get(Transaction, __import__("uuid").UUID(t["id"]))
        assert "swiggy@icici" in row.raw_text and row.dedupe_hash and row.balance_after is not None

    # Overview now reflects the import
    assert client.get("/api/overview?month=2026-10").status_code in (200, 422)

    # Upload the same file again: already-saved rows are unticked
    again = upload(client, "sample-statement.csv").json()
    assert "already imported this exact file" in again["warnings"][0]
    exact = [x for x in again["rows"] if x["duplicate_kind"] == "exact"]
    assert len(exact) == 15 and not any(x["include"] for x in exact)  # 16 saved; the date-fixed row differs
    assert again["rows_duplicate"] == 15
    client.delete(f"/api/imports/{again['id']}")

    # Undo the first import: its transactions disappear
    r = client.delete(f"/api/imports/{batch['id']}")
    assert r.json()["status"] == "cancelled"
    assert client.get("/api/transactions").json()["total"] == 0
    assert [b["status"] for b in client.get("/api/imports").json()] == ["cancelled", "cancelled"]


def test_manual_transaction_is_detected_as_duplicate(client):
    make_user(client)
    client.post("/api/transactions", json={"type": "expense", "amount": "450.00", "occurred_on": "2026-10-02", "description": "UPI-SWIGGY-swiggy@icici-ORDER 4589"})
    client.post("/api/transactions", json={"type": "expense", "amount": "649.00", "occurred_on": "2026-10-06", "description": "Netflix"})
    rows = upload(client, "sample-statement.csv").json()["rows"]
    assert rows[1]["duplicate_kind"] == "exact" and rows[1]["include"] is False
    netflix = next(x for x in rows if "NETFLIX" in x["description"])
    assert netflix["duplicate_kind"] == "possible" and netflix["include"] is True


def test_sms_paste_and_pdf_upload(client):
    make_user(client)
    r = client.post("/api/imports", data={"sms_text": sample("sample-sms.txt").decode()})
    assert r.status_code == 201 and r.json()["source_type"] == "sms" and r.json()["rows_found"] == 5
    r = upload(client, "sample-statement.pdf")
    assert r.status_code == 201 and r.json()["rows_found"] == 9
    r = upload(client, "sample-scanned.pdf")
    assert r.status_code == 201 and r.json()["status"] == "failed" and "OCR" in r.json()["errors"][0]["message"]


def test_bulk_include_and_cancel(client):
    make_user(client)
    b = upload(client, "sample-statement.csv").json()
    r = client.post(f"/api/imports/{b['id']}/include", json={"include": False, "which": "all"})
    assert not any(x["include"] for x in r.json()["rows"])
    assert client.post(f"/api/imports/{b['id']}/confirm").status_code == 422  # nothing ticked
    client.post(f"/api/imports/{b['id']}/include", json={"include": True, "which": "ready"})
    assert client.post(f"/api/imports/{b['id']}/confirm").json()["rows_imported"] == 16
    assert client.post(f"/api/imports/{b['id']}/confirm").status_code == 409  # can't save twice


@pytest.mark.parametrize(
    "name,content,message",
    [
        ("x.csv", b"", "empty"),
        ("x.xlsx", b"PK\x03\x04", "Excel"),
        ("x.pdf", b"not a pdf", "isn't a real PDF"),
        ("x.csv", b"%PDF-1.4", "rename"),
        ("x.exe", b"MZ\x00\x00", "text file"),
        ("x.doc", b"hello", "Please upload"),
    ],
)
def test_bad_uploads_are_refused_clearly(client, name, content, message):
    make_user(client)
    r = upload(client, name, content)
    assert r.status_code == 422 and message in r.json()["detail"]


def test_imports_are_private(client):
    from fastapi.testclient import TestClient
    from app.main import app
    make_user(client)
    b = upload(client, "sample-statement.csv").json()
    other = TestClient(app)
    make_user(other, "bob@example.com")
    assert other.get(f"/api/imports/{b['id']}").status_code == 404
    assert other.post(f"/api/imports/{b['id']}/confirm").status_code == 404
    assert other.patch(f"/api/imports/{b['id']}/rows/{b['rows'][0]['id']}", json={"include": False}).status_code == 404
    assert other.get("/api/imports").json() == []
    assert TestClient(app).get("/api/imports").status_code == 401


# ---- AI boundary ---------------------------------------------------------
class FakeClient:
    """Stands in for the Anthropic client so tests never call the internet."""

    def __init__(self, answer=None, fail=False):
        self.calls = []
        self.answer, self.fail = answer, fail
        self.beta = types.SimpleNamespace(messages=types.SimpleNamespace(create=self.create))

    def create(self, **kwargs):
        self.calls.append(kwargs)
        if self.fail:
            raise RuntimeError("network down")
        items = json.loads(kwargs["messages"][0]["content"].split("(JSON):\n", 1)[1])
        results = [{"id": i["id"], "category": self.answer, "confidence": 0.83, "reason": "Payment to a person, likely rent share."} for i in items]
        return types.SimpleNamespace(stop_reason="end_turn", content=[types.SimpleNamespace(type="text", text=json.dumps({"results": results}))])


def test_ai_classifies_uncertain_rows_and_never_sees_identifiers(client, monkeypatch):
    fake = FakeClient(answer="Housing and Rent")
    monkeypatch.setattr(ai, "ai_status", lambda: "ready")
    monkeypatch.setattr(ai, "_client", lambda: fake)
    make_user(client)
    b = upload(client, "sample-statement.csv").json()
    assert b["ai_status"] == "used"
    ramesh = next(x for x in b["rows"] if "RAMESH" in x["description"])
    assert ramesh["category_name"] == "Housing and Rent" and ramesh["category_source"] == "ai"
    assert ramesh["category_reason"].startswith("AI:") and ramesh["category_confidence"] == 0.83
    swiggy = b["rows"][1]
    assert swiggy["category_source"] == "keyword"  # confident rules are kept, not overwritten
    sent = fake.calls[0]["messages"][0]["content"]
    assert "okaxis" not in sent and "000245678915" not in sent and "1500" not in sent
    assert fake.calls[0]["model"] == "claude-opus-5-5"


def test_ai_failure_falls_back_to_rules(client, monkeypatch):
    monkeypatch.setattr(ai, "ai_status", lambda: "ready")
    monkeypatch.setattr(ai, "_client", lambda: FakeClient(fail=True))
    make_user(client)
    b = upload(client, "sample-statement.csv").json()
    assert b["status"] == "needs_review" and b["ai_status"] == "failed"
    assert b["rows"][1]["category_name"] == "Food and Dining"


def test_ai_answer_with_wrong_direction_is_ignored(client, monkeypatch):
    monkeypatch.setattr(ai, "ai_status", lambda: "ready")
    monkeypatch.setattr(ai, "_client", lambda: FakeClient(answer="Salary and Income"))
    make_user(client)
    b = upload(client, "sample-statement.csv").json()
    ramesh = next(x for x in b["rows"] if "RAMESH" in x["description"])
    assert ramesh["category_name"] == "Other"  # an income category can't be put on money out
