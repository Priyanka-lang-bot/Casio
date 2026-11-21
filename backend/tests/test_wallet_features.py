"""Hand-added subscriptions and unusual-spending detection."""
import datetime as dt

from tests.conftest import make_user


def test_add_edit_delete_manual_subscription(client):
    make_user(client)
    nxt = (dt.date.today() + dt.timedelta(days=5)).isoformat()
    r = client.post("/api/subscriptions", json={"name": " Hotstar  yearly ", "amount": "1499", "frequency": "yearly", "next_payment_on": nxt})
    assert r.status_code == 201, r.text
    sub = r.json()
    assert sub["manual"] and sub["name"] == "Hotstar yearly" and sub["monthly_cost"] == "124.92" and sub["next_expected_on"] == nxt

    page = client.get("/api/subscriptions").json()  # detection runs and must keep it
    assert [i["name"] for i in page["items"]] == ["Hotstar yearly"]
    assert page["summary"]["yearly_total"] == "1499.00"

    r = client.patch(f"/api/subscriptions/{sub['id']}", json={"amount": "199", "frequency": "monthly"})
    assert r.status_code == 200 and r.json()["yearly_cost"] == "2388.00"

    # A past next date rolls forward to the next one due.
    past = (dt.date.today() - dt.timedelta(days=40)).isoformat()
    r = client.patch(f"/api/subscriptions/{sub['id']}", json={"next_payment_on": past})
    assert dt.date.fromisoformat(r.json()["next_expected_on"]) >= dt.date.today()

    assert client.delete(f"/api/subscriptions/{sub['id']}").status_code == 204
    assert client.get("/api/subscriptions").json()["items"] == []


def test_found_subscriptions_cannot_be_deleted_or_repriced(client):
    client.post("/api/demo/start")
    netflix = next(i for i in client.get("/api/subscriptions").json()["items"] if i["name"] == "Netflix")
    assert not netflix["manual"]
    assert client.delete(f"/api/subscriptions/{netflix['id']}").status_code == 400
    assert client.patch(f"/api/subscriptions/{netflix['id']}", json={"amount": "1"}).status_code == 400


def test_other_users_cannot_touch_a_manual_subscription(client):
    from fastapi.testclient import TestClient
    from app.main import app

    make_user(client)
    sub = client.post("/api/subscriptions", json={"name": "Gym", "amount": "999", "next_payment_on": dt.date.today().isoformat()}).json()
    other = TestClient(app)
    make_user(other, email="someone-else@example.com")
    assert other.delete(f"/api/subscriptions/{sub['id']}").status_code == 404
    assert other.patch(f"/api/subscriptions/{sub['id']}", json={"name": "x"}).status_code == 404


def test_unusual_spending_flags_big_one_offs(client):
    client.post("/api/demo/start")
    r = client.get("/api/insights/unusual")
    assert r.status_code == 200
    data = r.json()
    assert data["method"]
    descs = " ".join(i["transaction"]["description"].upper() for i in data["items"])
    assert "BARBEQUE" in descs
    for i in data["items"]:
        assert float(i["transaction"]["amount"]) >= 2.5 * float(i["typical"])


def test_unusual_spending_empty_for_new_user(client):
    make_user(client)
    assert client.get("/api/insights/unusual").json()["items"] == []


def test_what_if_all_spending_change(client):
    client.post("/api/demo/start")
    r = client.post("/api/what-if", json={"changes": [{"type": "spending_change", "percent": "-10"}]})
    assert r.status_code == 200, r.text
    d = r.json()
    base, new = float(d["baseline"]["spending"]), float(d["scenario"]["spending"])
    assert abs(new - base * 0.9) < 1.0  # per-line rounding only
    assert float(d["difference"]["surplus"]) > 0
