"""Budgets, goals, money model, what-if, nudges, reports, coach, account."""
import datetime as dt
from decimal import Decimal

from app import coach, guardrails
from app.planning import add_months, month_start
from tests.conftest import make_user

TODAY = dt.date.today()
THIS_MONTH = month_start(TODAY)


def cat_id(client, name):
    return next(c["id"] for c in client.get("/api/categories").json() if c["name"] == name)


def add_tx(client, amount, category, on, type_="expense", desc="Test"):
    r = client.post("/api/transactions", json={
        "type": type_, "amount": str(amount), "occurred_on": on.isoformat(), "description": desc,
        "category_id": cat_id(client, category),
    })
    assert r.status_code == 201, r.text


def seed_history(client):
    """Three past months of salary 50,000, food 6,000, rent 15,000; this month food 9,000."""
    for back in (1, 2, 3):
        d = add_months(THIS_MONTH, -back).replace(day=5)
        add_tx(client, 50000, "Salary and Income", d, "income", "SALARY")
        add_tx(client, 6000, "Food and Dining", d, desc="SWIGGY")
        add_tx(client, 15000, "Housing and Rent", d, desc="RENT")
    add_tx(client, 9000, "Food and Dining", THIS_MONTH, desc="ZOMATO")


def test_budget_crud_and_status(client):
    make_user(client)
    seed_history(client)
    food = cat_id(client, "Food and Dining")
    r = client.post("/api/budgets", json={"category_id": food, "amount": "8000"})
    assert r.status_code == 201
    assert client.post("/api/budgets", json={"category_id": food, "amount": "1"}).status_code == 409
    assert client.post("/api/budgets", json={"category_id": cat_id(client, "Salary and Income"), "amount": "1"}).status_code == 422
    data = client.get("/api/budgets").json()
    b = data["items"][0]
    assert b["spent"] == "9000.00" and b["remaining"] == "-1000.00" and b["state"] == "over"
    assert b["usual_spend"] == "6000.00"
    # Rent has usual spending but no budget -> suggested, rounded up to 100
    sug = {s["category_name"]: s for s in data["suggestions"]}
    assert sug["Housing and Rent"]["suggested_amount"] == "15000"
    bid = b["id"]
    assert client.patch(f"/api/budgets/{bid}", json={"amount": "10000"}).status_code == 200
    assert client.get("/api/budgets").json()["items"][0]["state"] in ("near", "on_pace_to_exceed", "ok")
    assert client.delete(f"/api/budgets/{bid}").status_code == 204


def test_budget_isolation(client):
    make_user(client, "a@example.com")
    bid = client.post("/api/budgets", json={"category_id": cat_id(client, "Shopping"), "amount": "100"}).json()["id"]
    client.post("/api/auth/logout")
    make_user(client, "b@example.com")
    assert client.patch(f"/api/budgets/{bid}", json={"amount": "5"}).status_code == 404
    assert client.get("/api/budgets").json()["items"] == []


def test_goals_progress_and_contributions(client):
    make_user(client)
    target = add_months(TODAY, 10)
    r = client.post("/api/goals", json={"name": "Laptop", "kind": "purchase", "target_amount": "60000",
                                        "saved_amount": "10000", "target_date": target.isoformat(), "monthly_contribution": "2000"})
    assert r.status_code == 201, r.text
    g = r.json()
    assert g["progress_percent"] == "16.7" and g["remaining"] == "50000.00"
    assert g["months_to_finish"] == 25 and g["state"] == "behind"
    assert Decimal(g["needed_per_month"]) == Decimal("5000.00")
    g2 = client.post(f"/api/goals/{g['id']}/contributions", json={"amount": "50000"}).json()
    assert g2["status"] == "achieved" and g2["state"] == "achieved"
    assert client.post(f"/api/goals/{g['id']}/contributions", json={"amount": "-70000"}).status_code == 422
    assert len(client.get(f"/api/goals/{g['id']}/contributions").json()) == 1
    assert client.post("/api/goals", json={"name": "x", "target_amount": "1", "target_date": "2000-01-01"}).status_code == 422


def test_money_model_keeps_bases_apart_and_snapshots(client):
    make_user(client)
    client.post("/api/profile/income", json={"name": "Job", "amount": "45000", "frequency": "monthly"})
    m = client.get("/api/money-model").json()
    assert m["has_actuals"] is False and m["plan_basis"] == "user_estimate" and m["monthly_income"] == "45000.00"
    seed_history(client)
    m = client.get("/api/money-model").json()
    assert m["has_actuals"] is True and m["plan_basis"] == "actual"
    assert m["actual"]["usual_monthly_income"] == "50000.00" and m["actual"]["usual_monthly_spending"] == "21000.00"
    assert m["estimate"]["monthly_income"] == "45000.00"  # the estimate is still reported separately
    assert m["monthly_surplus"] == "29000.00"
    assert len(m["forecast"]["months"]) == 12 and m["forecast"]["basis"] == "forecast"
    assert len(m["snapshots"]) == 1 and m["snapshots"][0]["monthly_surplus"] == "29000.00"


def test_what_if_simulation(client):
    make_user(client)
    seed_history(client)
    client.post("/api/goals", json={"name": "Trip", "target_amount": "50000", "monthly_contribution": "5000"})
    r = client.post("/api/what-if", json={"changes": [
        {"type": "category_change", "category": "Food and Dining", "percent": -30},
        {"type": "category_change", "category": "Housing and Rent", "amount": 3000},
    ]})
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["baseline"]["surplus"] == "29000.00"
    # food 6000 -> 4200 (-1800), rent +3000 => surplus 27,800
    assert d["scenario"]["surplus"] == "27800.00" and d["difference"]["surplus"] == "-1200.00"
    assert d["difference"]["after_12_months"] == "-14400.00"
    assert d["goals"][0]["baseline"]["months"] == 10
    assert any("less each month" in s for s in d["explanation"])
    # Income drop large enough that goals no longer fit
    d = client.post("/api/what-if", json={"changes": [{"type": "income_change", "percent": -50}]}).json()
    assert d["scenario"]["surplus"] == "4000.00"
    assert d["goals"][0]["scenario"]["monthly"] == "4000.00" and d["goals"][0]["months_sooner_or_later"] > 0
    assert client.post("/api/what-if", json={"changes": [{"type": "nope"}]}).status_code == 422


def test_what_if_ask_uses_rules_without_ai(client):
    make_user(client)
    seed_history(client)
    d = client.post("/api/what-if/ask", json={"question": "What if I save another ₹2,000 every month?"}).json()
    assert d["parsed_by"] == "rules" and d["scenario"]["extra_saving"] == "2000.00"
    assert client.post("/api/what-if/ask", json={"question": "tell me a joke"}).status_code == 422


def test_parse_what_if_examples():
    assert coach.parse_what_if("What if I reduce dining expenses by 30%?") == [{"type": "category_change", "category": "Food and Dining", "percent": -30.0}]
    assert coach.parse_what_if("What if my rent increases by ₹3,000?") == [{"type": "category_change", "category": "Housing and Rent", "amount": 3000.0}]
    assert coach.parse_what_if("What if my income decreases by 10%?") == [{"type": "income_change", "percent": -10.0}]
    assert coach.parse_what_if("What if I save another ₹2,000 every month?") == [{"type": "extra_saving", "amount": 2000.0}]


def test_nudges_raise_and_dismiss(client):
    make_user(client)
    seed_history(client)
    client.post("/api/budgets", json={"category_id": cat_id(client, "Food and Dining"), "amount": "8000"})
    ns = client.get("/api/nudges").json()
    kinds = {n["kind"] for n in ns}
    assert "budget_over" in kinds and "spending_spike" in kinds
    first = next(n for n in ns if n["kind"] == "budget_over")
    assert client.post(f"/api/nudges/{first['id']}/dismiss").status_code == 204
    assert "budget_over" not in {n["kind"] for n in client.get("/api/nudges").json()}
    # Raise the budget: the over-budget condition goes away and doesn't come back
    bid = client.get("/api/budgets").json()["items"][0]["id"]
    client.patch(f"/api/budgets/{bid}", json={"amount": "50000"})
    assert "budget_over" not in {n["kind"] for n in client.get("/api/nudges").json()}


def test_monthly_report(client):
    make_user(client)
    seed_history(client)
    last = add_months(THIS_MONTH, -1)
    months = client.get("/api/reports").json()["months"]
    assert months[0]["month"] == f"{THIS_MONTH:%Y-%m}"
    r = client.get(f"/api/reports/{last:%Y-%m}").json()
    assert r["summary"]["income"] == "50000.00" and r["summary"]["spending"] == "21000.00" and r["summary"]["savings_rate"] == "58.0"
    assert r["narrative_source"] == "template" and r["highlights"]
    assert r["categories"][0]["category"] == "Housing and Rent"
    assert client.get("/api/reports/garbage").status_code == 422


def test_coach_helper_and_guardrail(client):
    make_user(client)
    seed_history(client)
    r = client.post("/api/coach", json={"message": "Which stocks should I buy?"}).json()
    assert r["answer"]["meta"]["source"] == "guardrail" and "can't recommend" in r["answer"]["content"]
    r = client.post("/api/coach", json={"message": "Where did my money go?"}).json()
    assert r["answer"]["meta"]["source"] == "helper" and "AI is switched off" in r["answer"]["content"]
    r = client.post("/api/coach", json={"message": "What if I cut dining by 30%?"}).json()
    assert "more each month" in r["answer"]["content"]
    hist = client.get("/api/coach").json()
    assert hist["ai"] == "not_configured" and len(hist["messages"]) == 6
    assert client.delete("/api/coach").status_code == 204
    assert client.get("/api/coach").json()["messages"] == []


def test_guardrail_patterns():
    for q in ["Which stock should I buy?", "Should I buy Reliance shares?", "best mutual funds for 2026", "should I buy bitcoin"]:
        assert guardrails.asks_for_security_pick(q), q
    for q in ["Should I invest more in my emergency fund?", "What is a mutual fund?", "Can I afford my Reliance Jio bill?", "What is bitcoin?"]:
        assert not guardrails.asks_for_security_pick(q), q
    assert guardrails.recommends_security("You could buy Infosys shares now")
    assert not guardrails.recommends_security("Put ₹2,000 into your emergency fund each month.")


class FakeBlock:
    def __init__(self, **kw):
        self.__dict__.update(kw)


class FakeAI:
    """Pretends to be Claude: first asks for a tool, then answers with the number it got."""

    def __init__(self, final_text):
        self.calls = []
        self.final_text = final_text
        self.beta = self
        self.messages = self

    def create(self, **kw):
        self.calls.append(kw)
        if len(self.calls) == 1:
            return FakeBlock(stop_reason="tool_use", content=[FakeBlock(type="tool_use", id="t1", name="get_month_summary", input={})])
        tool_result = kw["messages"][-1]["content"][0]["content"]
        return FakeBlock(stop_reason="end_turn", content=[FakeBlock(type="text", text=self.final_text.format(data=tool_result[:40]))])


def test_coach_ai_uses_tools_and_output_guardrail(client, monkeypatch):
    make_user(client)
    seed_history(client)
    from app import ai

    fake = FakeAI("From your transactions: {data}")
    monkeypatch.setattr(ai, "ai_status", lambda: "ready")
    monkeypatch.setattr(ai, "_client", lambda: fake)
    r = client.post("/api/coach", json={"message": "How did I do this month?"}).json()["answer"]
    assert r["meta"]["source"] == "ai" and r["meta"]["tools"] == ["get_month_summary"]
    assert "basis" in r["content"]  # the tool's real JSON reached the model
    assert fake.calls[0]["tools"] and "Never recommend" in fake.calls[0]["system"]

    bad = FakeAI("You should buy Infosys shares now.")
    monkeypatch.setattr(ai, "_client", lambda: bad)
    r = client.post("/api/coach", json={"message": "Any ideas for my savings?"}).json()["answer"]
    assert r["meta"]["source"] == "guardrail" and r["meta"]["blocked"] is True


def test_account_export_password_delete_and_demo(client):
    make_user(client)
    r = client.post("/api/account/demo-data")
    assert r.status_code == 200, r.text
    assert r.json()["rows_imported"] > 100
    assert client.post("/api/account/demo-data").status_code == 409
    subs = client.get("/api/subscriptions").json()
    assert subs["summary"]["active_count"] >= 3
    exp = client.get("/api/account/export")
    assert exp.status_code == 200 and "attachment" in exp.headers["content-disposition"]
    assert len(exp.json()["transactions"]) > 100
    assert client.patch("/api/account/name", json={"full_name": "  New   Name "}).json()["full_name"] == "New Name"
    assert client.post("/api/account/password", json={"current_password": "wrong", "new_password": "newpass123", "confirm_password": "newpass123"}).status_code == 422
    assert client.post("/api/account/password", json={"current_password": "secret123", "new_password": "newpass123", "confirm_password": "newpass123"}).status_code == 200
    assert client.post("/api/account/delete", json={"password": "newpass123", "confirm": "nope"}).status_code == 422
    assert client.post("/api/account/delete", json={"password": "newpass123", "confirm": "DELETE"}).status_code == 200
    assert client.get("/api/auth/me").status_code == 401
    assert client.post("/api/auth/login", json={"email": "ana@example.com", "password": "newpass123"}).status_code == 401
