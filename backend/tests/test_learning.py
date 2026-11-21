"""Adaptive learning: corrections, user-confirmed rules, priority,
conflicts, confidence, pause and undo."""
from datetime import date, timedelta

from tests.conftest import make_user

DAY = date.today() - timedelta(days=10)


def cats(client):
    return {c["name"]: c["id"] for c in client.get("/api/categories").json()}


def add_tx(client, description, amount="450.00", category_id=None, type_="expense", on=DAY):
    r = client.post("/api/transactions", json={
        "type": type_, "amount": amount, "occurred_on": on.isoformat(), "description": description, "category_id": category_id,
    })
    assert r.status_code == 201, r.text
    return r.json()


def recategorise(client, tx, category_id):
    body = {k: tx[k] for k in ("type", "amount", "occurred_on", "description", "notes")} | {"category_id": category_id}
    r = client.put(f"/api/transactions/{tx['id']}", json=body)
    assert r.status_code == 200, r.text
    return r.json()


def all_tx(client, **params):
    return client.get("/api/transactions", params={"limit": 200, **params}).json()["items"]


def set_auto(client, tx_id, name, c):
    """Simulate a transaction categorised by CASIO (as after an import)."""
    from app.db import SessionLocal
    from app.models import Transaction
    with SessionLocal() as db:
        t = db.get(Transaction, tx_id)
        t.category_id, t.category_source, t.category_confidence, t.category_reason = c[name], "keyword", 0.9, "Description mentions “swiggy”."
        db.commit()


def test_correction_is_saved_but_no_rule_is_made_without_asking(client):
    make_user(client)
    c = cats(client)
    tx = add_tx(client, "UPI-SWIGGY-swiggy@icici-ORDER 4589")
    set_auto(client, tx["id"], "Food and Dining", c)
    recategorise(client, tx, c["Groceries"])
    assert client.get("/api/rules").json() == []
    hist = client.get("/api/rules/corrections").json()
    assert len(hist) == 1 and hist[0]["from_category"] == "Food and Dining" and hist[0]["to_category"] == "Groceries"
    assert hist[0]["made_rule"] is False


def test_preview_then_rule_applies_to_past_but_never_to_user_choices(client):
    make_user(client)
    c = cats(client)
    first = add_tx(client, "UPI-SWIGGY-swiggy@icici-ORDER 4589")
    auto = [add_tx(client, f"UPI-SWIGGY-swiggy@icici-ORDER {n}") for n in (1111, 2222)]
    for t in [first, *auto]:
        set_auto(client, t["id"], "Food and Dining", c)
    mine = add_tx(client, "UPI-SWIGGY-swiggy@icici-ORDER 3333", category_id=c["Entertainment"])  # chosen by hand
    recategorise(client, first, c["Groceries"])

    p = client.post("/api/rules/preview", json={"transaction_id": first["id"], "category_id": c["Groceries"]}).json()
    assert p["match_type"] == "merchant" and p["pattern"] == "swiggy"
    assert p["matching_past"] == 2 and p["recommendation"] == "always"
    assert all_tx(client, category_id=c["Groceries"]).__len__() == 1  # preview changed nothing

    r = client.post("/api/rules", json={"category_id": c["Groceries"], "match_type": "merchant", "pattern": "swiggy",
                                         "applies_to": "expense", "source_transaction_id": first["id"]})
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["changed_transactions"] == 2
    by_id = {t["id"]: t for t in all_tx(client)}
    for t in auto:
        assert by_id[t["id"]]["category_name"] == "Groceries"
        assert by_id[t["id"]]["category_source"] == "rule"
        assert by_id[t["id"]]["rule_id"] == body["rule"]["id"]
        assert "Your rule" in by_id[t["id"]]["category_reason"]
    assert by_id[mine["id"]]["category_name"] == "Entertainment"  # untouched
    assert by_id[first["id"]]["category_source"] == "user"
    rule = client.get("/api/rules").json()[0]
    assert rule["times_applied"] == 2 and rule["currently_applied"] == 2 and rule["confidence"] == 0.95
    assert client.get("/api/rules/corrections").json()[0]["made_rule"] is True


def test_rule_used_for_new_transactions_and_imports(client):
    make_user(client)
    c = cats(client)
    client.post("/api/rules", json={"category_id": c["Groceries"], "match_type": "merchant", "pattern": "swiggy", "applies_to": "expense"})
    t = add_tx(client, "UPI-SWIGGY-swiggy@icici-ORDER 9")
    assert t["category_name"] == "Groceries" and t["category_source"] == "rule"
    csv = b"Date,Description,Amount\n01/10/2026,UPI-SWIGGY-swiggy@icici-ORDER 4589,-450\n02/10/2026,UBER RIDE,-200\n"
    batch = client.post("/api/imports", files={"file": ("s.csv", csv, "text/csv")}).json()
    sw = next(r for r in batch["rows"] if "SWIGGY" in r["description"])
    assert sw["category_name"] == "Groceries" and sw["category_source"] == "rule" and sw["rule_id"]
    assert any("learned rules" in w for w in batch["warnings"])
    client.post(f"/api/imports/{batch['id']}/confirm", json={})
    saved = next(t for t in all_tx(client) if t["description"].startswith("UPI-SWIGGY") and t["source"] == "csv")
    assert saved["rule_id"] == sw["rule_id"]
    assert client.get("/api/rules").json()[0]["times_applied"] == 2


def test_delete_rule_undoes_exactly(client):
    make_user(client)
    c = cats(client)
    t = add_tx(client, "UPI-SWIGGY-swiggy@icici-ORDER 1")
    set_auto(client, t["id"], "Food and Dining", c)
    rule = client.post("/api/rules", json={"category_id": c["Groceries"], "match_type": "merchant", "pattern": "swiggy"}).json()["rule"]
    assert all_tx(client)[0]["category_name"] == "Groceries"
    r = client.delete(f"/api/rules/{rule['id']}")
    assert r.json()["reverted_transactions"] == 1
    back = all_tx(client)[0]
    assert back["category_name"] == "Food and Dining" and back["category_source"] == "keyword" and back["rule_id"] is None
    assert client.get("/api/rules").json() == []


def test_more_specific_rule_wins_and_priority_overrides(client):
    make_user(client)
    c = cats(client)
    food = client.post("/api/rules", json={"category_id": c["Food and Dining"], "match_type": "merchant", "pattern": "swiggy"}).json()["rule"]
    client.post("/api/rules", json={"category_id": c["Groceries"], "match_type": "merchant", "pattern": "swiggy instamart"})
    a = add_tx(client, "UPI-SWIGGY INSTAMART-swiggy@icici-ORDER 77")
    b = add_tx(client, "UPI-SWIGGY-swiggy@icici-ORDER 78")
    assert a["category_name"] == "Groceries" and b["category_name"] == "Food and Dining"
    rules = client.get("/api/rules").json()
    general = next(r for r in rules if r["pattern"] == "swiggy")
    assert general["conflicts"] and general["conflicts"][0]["this_wins"] is False
    # Raise the general rule's priority: it now wins everywhere.
    r = client.patch(f"/api/rules/{food['id']}", json={"priority": "high"})
    assert r.json()["changed_transactions"] == 1
    assert next(t for t in all_tx(client) if t["id"] == a["id"])["category_name"] == "Food and Dining"


def test_same_match_with_new_category_replaces_rule(client):
    make_user(client)
    c = cats(client)
    client.post("/api/rules", json={"category_id": c["Food and Dining"], "match_type": "merchant", "pattern": "swiggy"})
    t = add_tx(client, "UPI-SWIGGY-swiggy@icici-ORDER 4")
    p = client.post("/api/rules/preview", json={"transaction_id": t["id"], "category_id": c["Groceries"]}).json()
    assert p["existing_rule"]["category_name"] == "Food and Dining"
    r = client.post("/api/rules", json={"category_id": c["Groceries"], "match_type": "merchant", "pattern": "swiggy"}).json()
    assert r["replaced"] is True and r["changed_transactions"] == 1
    assert len(client.get("/api/rules").json()) == 1
    assert all_tx(client)[0]["category_name"] == "Groceries"


def test_generic_patterns_and_wrong_kind_rejected(client):
    make_user(client)
    c = cats(client)
    r = client.post("/api/rules", json={"category_id": c["Groceries"], "match_type": "contains", "pattern": "UPI"})
    assert r.status_code == 422 and "almost every" in r.json()["detail"]
    r = client.post("/api/rules", json={"category_id": c["Groceries"], "match_type": "contains", "pattern": "ab"})
    assert r.status_code == 422
    r = client.post("/api/rules", json={"category_id": c["Salary and Income"], "match_type": "contains", "pattern": "swiggy", "applies_to": "expense"})
    assert r.status_code == 422


def test_contains_rule_and_pause(client):
    make_user(client)
    c = cats(client)
    t = add_tx(client, "POS 4321XXXX DECATHLON SPORTS BLR")
    rule = client.post("/api/rules", json={"category_id": c["Entertainment"], "match_type": "contains", "pattern": "decathlon sports"}).json()
    assert rule["changed_transactions"] == 1
    r = client.patch(f"/api/rules/{rule['rule']['id']}", json={"active": False})
    assert r.json()["changed_transactions"] == 1
    assert all_tx(client)[0]["category_name"] is None  # exactly as before the rule: no category
    client.patch(f"/api/rules/{rule['rule']['id']}", json={"active": True})
    assert all_tx(client)[0]["id"] == t["id"] and all_tx(client)[0]["category_name"] == "Entertainment"


def test_overrides_lower_confidence_and_flag_weak_rule(client):
    make_user(client)
    c = cats(client)
    client.post("/api/rules", json={"category_id": c["Groceries"], "match_type": "merchant", "pattern": "swiggy"})
    txs = [add_tx(client, f"UPI-SWIGGY-swiggy@icici-ORDER {n}") for n in (1, 2, 3)]
    for t in txs:
        recategorise(client, t, c["Food and Dining"])
    rule = client.get("/api/rules").json()[0]
    assert rule["times_overridden"] == 3 and rule["confidence"] < 0.6 and rule["weak"] is True


def test_recommendation_learns_from_repeated_corrections(client):
    make_user(client)
    c = cats(client)
    a = add_tx(client, "ZEPTO MARKETPLACE ORDER 1", category_id=c["Shopping"])
    b = add_tx(client, "ZEPTO MARKETPLACE ORDER 2", category_id=c["Shopping"])
    recategorise(client, a, c["Food and Dining"])
    recategorise(client, b, c["Food and Dining"])
    p = client.post("/api/rules/preview", json={"transaction_id": b["id"], "category_id": c["Food and Dining"]}).json()
    assert p["recommendation"] == "always" and "2 times" in p["reason"]


def test_rule_from_import_review_updates_rows_in_that_import(client):
    make_user(client)
    c = cats(client)
    csv = b"Date,Description,Amount\n01/10/2026,UPI-SWIGGY-swiggy@icici-ORDER 1,-450\n02/10/2026,UPI-SWIGGY-swiggy@icici-ORDER 2,-300\n"
    batch = client.post("/api/imports", files={"file": ("s.csv", csv, "text/csv")}).json()
    row = batch["rows"][0]
    client.patch(f"/api/imports/{batch['id']}/rows/{row['id']}", json={"category_id": c["Groceries"]})
    p = client.post("/api/rules/preview", json={"import_row_id": row["id"], "category_id": c["Groceries"]}).json()
    assert p["matching_in_import"] == 1
    r = client.post("/api/rules", json={"category_id": c["Groceries"], "match_type": "merchant", "pattern": p["pattern"]}).json()
    assert r["changed_import_rows"] == 1
    rows = client.get(f"/api/imports/{batch['id']}").json()["rows"]
    assert [x["category_name"] for x in rows] == ["Groceries", "Groceries"]
    assert rows[1]["category_source"] == "rule"


def test_rules_are_private(client):
    make_user(client)
    c = cats(client)
    rule = client.post("/api/rules", json={"category_id": c["Groceries"], "match_type": "merchant", "pattern": "swiggy"}).json()["rule"]
    client.post("/api/auth/logout")
    make_user(client, "other@example.com")
    assert client.get("/api/rules").json() == []
    assert client.delete(f"/api/rules/{rule['id']}").status_code == 404
    assert client.patch(f"/api/rules/{rule['id']}", json={"active": False}).status_code == 404


def test_import_row_correction_not_counted_twice(client):
    make_user(client)
    c = cats(client)
    csv = b"Date,Description,Amount\n01/10/2026,UPI-SWIGGY-swiggy@icici-ORDER 1,-450\n"
    batch = client.post("/api/imports", files={"file": ("s.csv", csv, "text/csv")}).json()
    row = batch["rows"][0]
    client.patch(f"/api/imports/{batch['id']}/rows/{row['id']}", json={"category_id": c["Groceries"]})
    p = client.post("/api/rules/preview", json={"import_row_id": row["id"], "category_id": c["Groceries"]}).json()
    assert p["prior_corrections"] == 0 and p["recommendation"] == "once"
