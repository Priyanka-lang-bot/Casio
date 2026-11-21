import re

from sqlalchemy import select

from app.db import SessionLocal
from app.models import User, UserSession

GOOD = {"full_name": "Ana Silva", "email": "Ana@Example.com", "password": "secret123", "confirm_password": "secret123"}


def register(client, **overrides):
    return client.post("/api/auth/register", json={**GOOD, **overrides})


def test_register_creates_account_and_signs_in(client):
    r = register(client)
    assert r.status_code == 201
    assert r.json()["email"] == "ana@example.com"  # stored lower-case
    assert "casio_session" in r.cookies
    assert client.get("/api/auth/me").json()["full_name"] == "Ana Silva"


def test_password_is_hashed_not_stored(client):
    register(client)
    with SessionLocal() as db:
        user = db.scalar(select(User))
        assert "secret123" not in user.password_hash
        assert user.password_hash.startswith("$argon2id$")


def test_session_token_is_hashed_in_db(client):
    r = register(client)
    with SessionLocal() as db:
        assert db.scalar(select(UserSession)).token_hash != r.cookies["casio_session"]


def test_duplicate_email_rejected_case_insensitive(client):
    register(client)
    client.cookies.clear()
    r = client.post("/api/auth/register", json={**GOOD, "email": "ana@EXAMPLE.com"})
    assert r.status_code == 409


def test_validation_messages(client):
    r = register(client, full_name="  ", email="not-an-email", password="short", confirm_password="other")
    assert r.status_code == 422
    fields = r.json()["fields"]
    assert fields["full_name"] == "Please enter your full name."
    assert fields["email"] == "Please enter a valid email address."
    assert "at least 8" in fields["password"]
    assert "secret" not in r.text  # never echo inputs back


def test_password_needs_letter_and_number(client):
    r = register(client, password="abcdefgh", confirm_password="abcdefgh")
    assert "letter and one number" in r.json()["fields"]["password"]


def test_password_mismatch(client):
    r = register(client, confirm_password="secret124")
    assert r.status_code == 422
    assert r.json()["fields"]["confirm_password"] == "The two passwords don't match."


def test_login_success_and_wrong_password(client):
    register(client)
    client.cookies.clear()
    assert client.get("/api/auth/me").status_code == 401
    bad = client.post("/api/auth/login", json={"email": "ana@example.com", "password": "wrong1234"})
    assert bad.status_code == 401
    assert bad.json()["detail"] == "Incorrect email or password."
    unknown = client.post("/api/auth/login", json={"email": "nobody@example.com", "password": "wrong1234"})
    assert unknown.json()["detail"] == bad.json()["detail"]  # doesn't reveal which accounts exist
    ok = client.post("/api/auth/login", json={"email": " ANA@example.com ", "password": "secret123"})
    assert ok.status_code == 200
    assert client.get("/api/auth/me").status_code == 200


def test_remember_me_sets_persistent_cookie(client):
    register(client)
    client.cookies.clear()
    short = client.post("/api/auth/login", json={"email": "ana@example.com", "password": "secret123"})
    assert "Max-Age" not in short.headers["set-cookie"]
    long = client.post("/api/auth/login", json={"email": "ana@example.com", "password": "secret123", "remember_me": True})
    assert "Max-Age=2592000" in long.headers["set-cookie"]
    assert "HttpOnly" in long.headers["set-cookie"]
    assert "SameSite=lax" in long.headers["set-cookie"]


def test_logout_invalidates_session_server_side(client):
    r = register(client)
    token = r.cookies["casio_session"]
    assert client.post("/api/auth/logout").status_code == 200
    client.cookies.set("casio_session", token)  # replaying the old cookie must fail
    assert client.get("/api/auth/me").status_code == 401


def test_fake_cookie_rejected(client):
    client.cookies.set("casio_session", "made-up-token")
    assert client.get("/api/auth/me").status_code == 401


def test_too_many_failed_logins_blocked(client):
    register(client)
    client.cookies.clear()
    for _ in range(5):
        client.post("/api/auth/login", json={"email": "ana@example.com", "password": "wrong1234"})
    r = client.post("/api/auth/login", json={"email": "ana@example.com", "password": "secret123"})
    assert r.status_code == 429


def test_password_reset_flow(client, capsys):
    register(client)
    old_cookie = client.cookies["casio_session"]
    r = client.post("/api/auth/forgot-password", json={"email": "ana@example.com"})
    assert r.status_code == 200
    token = re.search(r"token=([\w-]+)", capsys.readouterr().out).group(1)

    r = client.post("/api/auth/reset-password", json={"token": token, "password": "newpass456", "confirm_password": "newpass456"})
    assert r.status_code == 200
    # Old sessions are signed out
    client.cookies.set("casio_session", old_cookie)
    assert client.get("/api/auth/me").status_code == 401
    # Token can't be reused
    again = client.post("/api/auth/reset-password", json={"token": token, "password": "other789x", "confirm_password": "other789x"})
    assert again.status_code == 400
    # Old password no longer works, new one does
    client.cookies.clear()
    assert client.post("/api/auth/login", json={"email": "ana@example.com", "password": "secret123"}).status_code == 401
    assert client.post("/api/auth/login", json={"email": "ana@example.com", "password": "newpass456"}).status_code == 200


def test_forgot_password_same_reply_for_unknown_email(client, capsys):
    r = client.post("/api/auth/forgot-password", json={"email": "nobody@example.com"})
    assert r.status_code == 200
    assert "If an account exists" in r.json()["message"]
    assert "reset-password" not in capsys.readouterr().out
