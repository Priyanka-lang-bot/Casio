import datetime as dt
import uuid
from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.db import SessionLocal
from app.finance import monthly_amount, profile_summary
from app.main import app
from app.models import AuditLog
from tests.conftest import make_user

TODAY = dt.date.today().isoformat()


def category_id(client, name):
    return next(c["id"] for c in client.get("/api/categories").json() if c["name"] == name)


# ---- pure calculations ---------------------------------------------------
class Row:
    def __init__(self, **kw):
        self.__dict__.update(kw)


def test_monthly_conversion_is_exact():
    assert monthly_amount(Decimal("12000"), "yearly") == Decimal("1000")
    assert monthly_amount(Decimal("3000"), "quarterly").quantize(Decimal("0.01")) == Decimal("1000.00")
    assert monthly_amount(Decimal("1200"), "weekly").quantize(Decimal("0.01")) == Decimal("5200.00")


def test_profile_summary_formulas():
    s = profile_summary(
        incomes=[Row(amount=Decimal("50000"), frequency="monthly"), Row(amount=Decimal("60000"), frequency="yearly")],
        expenses=[
            Row(amount=Decimal("15000"), frequency="monthly", kind="fixed"),
            Row(amount=Decimal("8000"), frequency="monthly", kind="variable"),
        ],
        assets=[Row(kind="emergency_fund", value=Decimal("60000")), Row(kind="bank_account", value=Decimal("20000"))],
        liabilities=[Row(balance=Decimal("100000"), monthly_payment=Decimal("5000"))],
    )
    assert s["monthly_income"] == Decimal("55000.00")
    assert s["monthly_total_spending"] == Decimal("28000.00")
    assert s["monthly_surplus"] == Decimal("27000.00")
    assert s["net_worth"] == Decimal("-20000.00")
    assert s["emergency_fund_months"] == Decimal("2.1")
    assert s["basis"] == "user_estimate"


# ---- profile API ---------------------------------------------------------
def test_new_user_gets_inr_profile(client):
    make_user(client)
    assert client.get("/api/profile").json() == {"currency": "INR", "country": None}


def test_profile_crud_and_summary(client):
    make_user(client)
    r = client.post("/api/profile/income", json={"name": "Salary", "amount": "50000", "frequency": "monthly"})
    assert r.status_code == 201
    assert r.json()["amount"] == "50000"  # money is sent as a string, never a float
    inc_id = r.json()["id"]
    client.post("/api/profile/expenses", json={"name": "Rent", "amount": "15000", "kind": "fixed"})
    client.post("/api/profile/assets", json={"name": "Rainy day", "kind": "emergency_fund", "value": "30000"})
    client.post("/api/profile/liabilities", json={"name": "Card", "kind": "credit_card", "balance": "10000", "monthly_payment": "2000"})

    s = client.get("/api/profile/summary").json()
    assert s["monthly_income"] == "50000.00"
    assert s["monthly_surplus"] == "33000.00"
    assert s["net_worth"] == "20000.00"

    assert client.put(f"/api/profile/income/{inc_id}", json={"name": "Salary", "amount": "55000"}).status_code == 200
    assert client.get("/api/profile/summary").json()["monthly_income"] == "55000.00"
    assert client.delete(f"/api/profile/income/{inc_id}").status_code == 204
    assert client.get("/api/profile/income").json() == []


def test_money_validation(client):
    make_user(client)
    for bad in ["-5", "0", "12.345", "1e15", "abc"]:
        r = client.post("/api/profile/income", json={"name": "X", "amount": bad})
        assert r.status_code == 422, bad
    assert client.post("/api/profile/assets", json={"name": "X", "kind": "gold_bars", "value": "1"}).status_code == 422


def test_users_cannot_see_each_others_data(client):
    make_user(client, "a@example.com")
    item = client.post("/api/profile/income", json={"name": "Salary", "amount": "1000"}).json()
    tx = client.post(
        "/api/transactions", json={"type": "expense", "amount": "10", "occurred_on": TODAY, "description": "Tea"}
    ).json()

    other = TestClient(app)
    make_user(other, "b@example.com")
    assert other.get("/api/profile/income").json() == []
    assert other.get("/api/transactions").json()["total"] == 0
    assert other.put(f"/api/profile/income/{item['id']}", json={"name": "Hacked", "amount": "1"}).status_code == 404
    assert other.delete(f"/api/profile/income/{item['id']}").status_code == 404
    assert other.delete(f"/api/transactions/{tx['id']}").status_code == 404
    assert client.get("/api/profile/income").json()[0]["name"] == "Salary"


def test_endpoints_require_login(client):
    for path in ["/api/profile", "/api/profile/summary", "/api/transactions", "/api/overview", "/api/categories"]:
        assert client.get(path).status_code == 401, path


# ---- transactions --------------------------------------------------------
def test_transaction_crud_filters_and_idempotency(client):
    make_user(client)
    food = category_id(client, "Food and Dining")
    rid = str(uuid.uuid4())
    body = {"type": "expense", "amount": "250.50", "occurred_on": TODAY, "description": "Lunch", "category_id": food, "client_request_id": rid}
    first = client.post("/api/transactions", json=body)
    second = client.post("/api/transactions", json=body)  # double-click
    assert first.status_code == 201
    assert second.json()["id"] == first.json()["id"]
    assert client.get("/api/transactions").json()["total"] == 1
    assert first.json()["category_name"] == "Food and Dining"
    assert first.json()["currency"] == "INR"

    client.post("/api/transactions", json={"type": "income", "amount": "1000", "occurred_on": TODAY, "description": "Salary"})
    assert client.get("/api/transactions?type=income").json()["total"] == 1
    assert client.get("/api/transactions?q=lun").json()["total"] == 1
    assert client.get(f"/api/transactions?category_id={food}").json()["total"] == 1

    tx_id = first.json()["id"]
    upd = client.put(f"/api/transactions/{tx_id}", json={**body, "amount": "300", "client_request_id": None})
    assert upd.json()["amount"] == "300.00"
    assert client.delete(f"/api/transactions/{tx_id}").status_code == 204
    assert client.get("/api/transactions").json()["total"] == 1


def test_transaction_validation(client):
    make_user(client)
    future = (dt.date.today() + dt.timedelta(days=10)).isoformat()
    r = client.post("/api/transactions", json={"type": "expense", "amount": "10", "occurred_on": future, "description": "x"})
    assert r.json()["fields"]["occurred_on"] == "The date can't be in the future."
    salary = category_id(client, "Salary and Income")
    r = client.post("/api/transactions", json={"type": "expense", "amount": "10", "occurred_on": TODAY, "description": "x", "category_id": salary})
    assert r.status_code == 422


def test_currency_locked_after_transactions(client):
    make_user(client)
    assert client.patch("/api/profile", json={"currency": "USD"}).json()["currency"] == "USD"
    client.post("/api/transactions", json={"type": "expense", "amount": "10", "occurred_on": TODAY, "description": "x"})
    assert client.patch("/api/profile", json={"currency": "EUR"}).status_code == 409


# ---- overview ------------------------------------------------------------
def test_overview_uses_actual_transactions(client):
    make_user(client)
    o = client.get("/api/overview").json()
    assert o["has_transactions"] is False
    assert o["actual"]["month_income"] == "0.00"

    food = category_id(client, "Food and Dining")
    client.post("/api/transactions", json={"type": "income", "amount": "40000", "occurred_on": TODAY, "description": "Salary"})
    client.post("/api/transactions", json={"type": "expense", "amount": "1500.25", "occurred_on": TODAY, "description": "Dinner", "category_id": food})
    client.post("/api/transactions", json={"type": "expense", "amount": "499.75", "occurred_on": TODAY, "description": "Misc"})
    o = client.get("/api/overview").json()
    a = o["actual"]
    assert (a["month_income"], a["month_expenses"], a["month_net"]) == ("40000.00", "2000.00", "38000.00")
    assert a["savings_rate_percent"] == "95.0"
    assert o["spending_by_category"][0] == {"category": "Food and Dining", "amount": "1500.25"}
    assert len(o["trend"]) == 6 and o["trend"][-1]["expenses"] == "2000.00"
    assert len(o["recent_transactions"]) == 3


def test_audit_log_has_no_sensitive_values(client):
    make_user(client)
    client.post("/api/transactions", json={"type": "expense", "amount": "777", "occurred_on": TODAY, "description": "Secret shop"})
    with SessionLocal() as db:
        logs = db.scalars(select(AuditLog)).all()
    actions = {l.action for l in logs}
    assert {"auth.register", "transaction.create"} <= actions
    dump = str([(l.action, l.details) for l in logs])
    assert "777" not in dump and "Secret" not in dump and "secret123" not in dump


def test_import_dedupe_fingerprint_ignores_reference_numbers():
    from app.importers.base import dedupe_hash, normalise_description

    assert normalise_description("SWIGGY ORDER 4589 ") == "swiggy order"
    d = dt.date(2026, 11, 1)
    assert dedupe_hash(d, Decimal("450"), "expense", "SWIGGY ORDER 4589") == dedupe_hash(
        d, Decimal("450.00"), "expense", "Swiggy order 9921"
    )
    assert dedupe_hash(d, Decimal("450"), "expense", "SWIGGY") != dedupe_hash(d, Decimal("451"), "expense", "SWIGGY")
