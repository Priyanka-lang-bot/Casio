"""Recurring payments and subscriptions."""
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

from app.recurring import Charge, add_period, find_series
from tests.conftest import make_user

SAMPLE = Path(__file__).resolve().parents[2] / "docs" / "samples" / "sample-6-months.csv"


def charges(start: date, gap: int, amounts: list) -> list[Charge]:
    return [Charge(start + timedelta(days=gap * i), Decimal(str(a)), None, "x") for i, a in enumerate(amounts)]


def test_frequencies():
    assert find_series(charges(date(2026, 1, 5), 30, [649] * 4), False, False).frequency == "monthly"
    assert find_series(charges(date(2026, 1, 5), 7, [420] * 5), False, False).frequency == "weekly"
    assert find_series(charges(date(2026, 1, 5), 14, [99] * 3), False, False).frequency == "fortnightly"
    assert find_series(charges(date(2025, 1, 5), 91, [3999] * 2), False, False).frequency == "quarterly"
    assert find_series(charges(date(2024, 1, 5), 365, [1499] * 2), False, False).frequency == "yearly"


def test_rejects_irregular_and_random_amounts():
    assert find_series(charges(date(2026, 1, 1), 30, [649, 649]), False, False) is None  # 2 monthly: not enough
    assert find_series(charges(date(2026, 1, 1), 30, [649, 649]), False, True) is not None  # unless a known service
    food = charges(date(2026, 1, 1), 7, [189, 615, 245, 520, 312, 450])
    assert find_series(food, False, False) is None
    bills = charges(date(2026, 1, 15), 30, [1820, 2140, 2390, 1960])
    s = find_series(bills, True, False)
    assert s is not None and s.varies
    gaps = [Charge(date(2026, 1, 1) + timedelta(days=d), Decimal("100"), None, "x") for d in (0, 9, 40, 44, 90)]
    assert find_series(gaps, False, False) is None


def test_add_period_clamps_month_end():
    assert add_period(date(2026, 1, 31), "monthly") == date(2026, 2, 28)
    assert add_period(date(2026, 11, 30), "quarterly") == date(2027, 2, 28)
    assert add_period(date(2024, 2, 29), "yearly") == date(2025, 2, 28)


def import_sample(client):
    batch = client.post("/api/imports", files={"file": ("six.csv", SAMPLE.read_bytes(), "text/csv")}).json()
    assert client.post(f"/api/imports/{batch['id']}/confirm", json={}).status_code == 200
    return batch


def test_detects_subscriptions_bills_and_alerts(client):
    make_user(client)
    import_sample(client)
    page = client.get("/api/subscriptions").json()
    items = {i["name"]: i for i in page["items"]}
    assert page["as_of"] == "2026-11-20"
    assert {"Netflix", "Spotify", "Bescom Electricity", "Airtel Postpaid", "Openai Chatgpt", "Cultfit",
            "Country Delight Milk", "Rent Nobroker Housing"} <= set(items)
    assert not any("Swiggy" in n or "Uber" in n or "Amazon" in n for n in items)  # random spending isn't recurring
    nf = items["Netflix"]
    assert nf["kind"] == "subscription" and nf["frequency"] == "monthly" and nf["amount"] == "799.00"
    assert nf["next_expected_on"] == "2026-12-06" and nf["price_changes"] == [{"date": "2026-09-06", "old": "649.00", "new": "799.00"}]
    assert items["Spotify"]["state"] == "overdue"
    assert items["Country Delight Milk"]["frequency"] == "weekly"
    assert items["Cultfit"]["frequency"] == "quarterly"
    assert items["Bescom Electricity"]["amount_varies"] is True and items["Bescom Electricity"]["kind"] == "bill"
    kinds = {a["kind"] for a in page["alerts"]}
    assert {"price_increase", "missed", "new", "unusual_amount", "usage_check"} <= kinds
    price = next(a for a in page["alerts"] if a["kind"] == "price_increase")
    assert "₹649 to ₹799" in price["message"] and "₹1,800 more a year" in price["message"]
    # Running again doesn't repeat alerts
    again = client.get("/api/subscriptions").json()
    assert len(again["alerts"]) == len(page["alerts"])
    assert Decimal(page["summary"]["monthly_total"]) > 0


def test_user_answers_usage_and_status(client):
    make_user(client)
    import_sample(client)
    page = client.get("/api/subscriptions").json()
    nf = next(i for i in page["items"] if i["name"] == "Netflix")
    r = client.patch(f"/api/subscriptions/{nf['id']}", json={"usage": "not_using"})
    assert r.json()["usage"] == "not_using" and r.json()["usage_confirmed_at"]
    page = client.get("/api/subscriptions").json()
    assert page["summary"]["not_using_yearly"] == "9588.00"
    assert not any(a["kind"] == "usage_check" and "Netflix" in a["message"] for a in page["alerts"])

    sp = next(i for i in page["items"] if i["name"] == "Spotify")
    client.patch(f"/api/subscriptions/{sp['id']}", json={"status": "cancelled"})
    page = client.get("/api/subscriptions").json()
    sp = next(i for i in page["items"] if i["name"] == "Spotify")
    assert sp["state"] == "cancelled" and sp["next_expected_on"] is None
    assert not any(a["kind"] == "missed" and "Spotify" in a["message"] for a in page["alerts"])

    milk = next(i for i in page["items"] if i["name"] == "Country Delight Milk")
    client.patch(f"/api/subscriptions/{milk['id']}", json={"status": "not_recurring", "name": "Milk"})
    page = client.get("/api/subscriptions").json()
    milk = next(i for i in page["items"] if i["id"] == milk["id"])
    assert milk["status"] == "not_recurring" and milk["name"] == "Milk"


def test_charged_after_cancel_alert(client):
    make_user(client)
    import_sample(client)
    nf = next(i for i in client.get("/api/subscriptions").json()["items"] if i["name"] == "Netflix")
    client.patch(f"/api/subscriptions/{nf['id']}", json={"status": "cancelled"})
    client.post("/api/transactions", json={"type": "expense", "amount": "799", "occurred_on": "2026-11-21", "description": "POS 4321XXXX NETFLIX.COM"})
    page = client.get("/api/subscriptions").json()
    assert any(a["kind"] == "charged_after_cancel" for a in page["alerts"])


def test_undo_import_removes_detected_payments_and_dismiss(client):
    make_user(client)
    batch = import_sample(client)
    page = client.get("/api/subscriptions").json()
    a = page["alerts"][0]
    assert client.post(f"/api/subscriptions/alerts/{a['id']}/dismiss").status_code == 204
    assert all(x["id"] != a["id"] for x in client.get("/api/subscriptions/alerts", params={"limit": 50}).json())
    client.delete(f"/api/imports/{batch['id']}")
    assert client.get("/api/subscriptions").json()["items"] == []


def test_subscriptions_are_private(client):
    make_user(client)
    import_sample(client)
    rp = client.get("/api/subscriptions").json()["items"][0]
    client.post("/api/auth/logout")
    make_user(client, "other@example.com")
    assert client.get("/api/subscriptions").json()["items"] == []
    assert client.patch(f"/api/subscriptions/{rp['id']}", json={"usage": "using"}).status_code == 404
