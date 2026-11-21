"""The one-click demo: every visitor gets a private, fully populated sandbox."""
import datetime as dt
from decimal import Decimal

from sqlalchemy import func, select, update

from app.db import SessionLocal
from app.demo import seed
from app.models import Transaction, User
from tests.conftest import make_user


def test_demo_start_creates_a_private_populated_sandbox(client):
    r = client.post("/api/demo/start")
    assert r.status_code == 201, r.text
    me = client.get("/api/auth/me").json()
    assert me["is_demo"] is True and me["full_name"] == seed.DEMO_NAME

    txs = client.get("/api/transactions?limit=200").json()
    assert txs["total"] > 150
    types = {t["type"] for t in txs["items"]}
    assert types == {"income", "expense", "transfer"}

    # Usual month (last 3 full months): ₹45,000 in, roughly ₹28,500 out.
    mm = client.get("/api/money-model").json()
    assert Decimal(mm["monthly_income"]) == Decimal("45000")
    assert Decimal("26500") < Decimal(mm["monthly_spending"]) < Decimal("30500")

    subs = client.get("/api/subscriptions").json()
    names = {i["name"] for i in subs["items"] if i["kind"] == "subscription" and i["status"] == "active"}
    assert names == {"Netflix", "Spotify", "YouTube Premium", "Cult.fit membership"}
    netflix = next(i for i in subs["items"] if i["name"] == "Netflix")
    assert netflix["price_changes"] and netflix["price_changes"][-1]["new"] == "649.00"
    alerts = " ".join(a["message"] for a in client.get("/api/subscriptions/alerts?limit=20").json())
    assert "Netflix went up" in alerts and "Youtube Premium Google" not in alerts

    assert len(client.get("/api/goals").json()["goals"]) == 2
    assert len(client.get("/api/budgets").json()["items"]) >= 6
    rules = client.get("/api/rules").json()
    assert len(rules) == 3 and all(r["times_applied"] > 0 for r in rules)


def test_each_visitor_gets_their_own_sandbox(client):
    from fastapi.testclient import TestClient
    from app.main import app

    other = TestClient(app)
    a = client.post("/api/demo/start").json()
    b = other.post("/api/demo/start").json()
    assert a["id"] != b["id"]
    # Visitor A deletes a transaction; visitor B's sandbox is unaffected.
    tx = client.get("/api/transactions?limit=1").json()["items"][0]
    assert client.delete(f"/api/transactions/{tx['id']}").status_code == 204
    before = other.get("/api/transactions?limit=1").json()["total"]
    assert before == client.get("/api/transactions?limit=1").json()["total"] + 1


def test_demo_has_no_password_login_and_real_users_are_untouched(client):
    make_user(client)  # a real account
    real_total = client.get("/api/transactions").json()["total"]
    client.post("/api/demo/start")
    with SessionLocal() as db:
        real = db.scalar(select(User).where(User.email == "ana@example.com"))
        assert real.is_demo is False
        assert db.scalar(select(func.count()).select_from(Transaction).where(Transaction.user_id == real.id)) == real_total == 0


def test_reset_gives_a_fresh_sandbox(client):
    first = client.post("/api/demo/start").json()
    tx = client.get("/api/transactions?limit=1").json()["items"][0]
    client.delete(f"/api/transactions/{tx['id']}")
    r = client.post("/api/demo/reset")
    assert r.status_code == 201
    assert r.json()["id"] != first["id"]
    with SessionLocal() as db:
        assert db.get(User, first["id"]) is None  # the old sandbox is gone


def test_reset_and_sample_files_are_demo_only(client):
    make_user(client)
    assert client.post("/api/demo/reset").status_code == 403
    assert client.get("/api/demo/sample-statement.csv").status_code == 404


def test_sample_statement_shows_duplicates_and_new_rows(client):
    client.post("/api/demo/start")
    csv = client.get("/api/demo/sample-statement.csv")
    assert csv.status_code == 200 and "SAMPLE DATA" in csv.text
    r = client.post("/api/imports", files={"file": ("casio-demo-new-statement.csv", csv.content, "text/csv")})
    assert r.status_code in (200, 201), r.text
    batch = r.json()
    rows = batch["rows"]
    assert sum(1 for x in rows if x["duplicate_kind"] == "exact") == 3
    unknown = next(x for x in rows if "BLUE PEAK" in x["description"])
    assert unknown["category_name"] == "Other"
    chai = next(x for x in rows if "CHAI POINT" in x["description"])
    assert chai["category_source"] == "rule"

    sms = client.get("/api/demo/sample-sms.txt")
    assert sms.status_code == 200 and "OTP" in sms.text


def test_expired_sandboxes_are_cleaned_up(client):
    client.post("/api/demo/start")
    with SessionLocal() as db:
        db.execute(update(User).where(User.is_demo.is_(True)).values(created_at=dt.datetime.now(dt.UTC) - dt.timedelta(days=2)))
        db.commit()
        assert seed.cleanup(db) == 1
        db.commit()
        assert db.scalar(select(func.count()).select_from(User).where(User.is_demo.is_(True))) == 0


def test_coach_answers_demo_questions_from_data(client):
    client.post("/api/demo/start")
    ask = lambda q: client.post("/api/coach", json={"message": q}).json()["answer"]["content"]  # noqa: E731
    assert "Housing and Rent" in ask("Where is most of my money going?")
    assert "What went up" in ask("Why did my expenses increase this month?")
    assert "20% less" in ask("How can I save more?")
    subs_answer = ask("What subscriptions am I paying for?")
    assert "Netflix" in subs_answer and "YouTube Premium" in subs_answer
    assert "30% as an example" in ask("What happens if I reduce dining expenses?")
