"""Tests run against a separate database (casio_test) so your real data is
never touched. Tables are emptied between tests."""
import os

os.environ["DATABASE_URL"] = os.environ.get(
    "TEST_DATABASE_URL", "postgresql+psycopg://casio:casio_dev_password@localhost:5432/casio_test"
)

import pytest  # noqa: E402
from alembic import command  # noqa: E402
from alembic.config import Config  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import text  # noqa: E402

from app import rate_limit  # noqa: E402
from app.db import engine  # noqa: E402
from app.main import app  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def migrated_db():
    command.upgrade(Config("alembic.ini"), "head")


@pytest.fixture(autouse=True)
def clean_tables():
    with engine.begin() as conn:
        # DELETE (not TRUNCATE) so built-in categories survive; user data cascades.
        conn.execute(text("DELETE FROM users"))
        conn.execute(text("DELETE FROM audit_logs"))
    rate_limit.reset()


@pytest.fixture
def client():
    return TestClient(app)


def make_user(client, email="ana@example.com"):
    """Register a user; the client keeps their session cookie."""
    r = client.post(
        "/api/auth/register",
        json={"full_name": "Test User", "email": email, "password": "secret123", "confirm_password": "secret123"},
    )
    assert r.status_code == 201, r.text
    return r.json()
