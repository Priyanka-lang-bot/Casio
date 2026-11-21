"""Bring the database schema up to date (alembic upgrade head).

Used on start-up in production (MIGRATE_ON_STARTUP=true), so a new deploy
never runs against an old schema. A Postgres advisory lock makes sure only
one server instance migrates at a time; the others wait, then see there's
nothing to do. Migrations only add things; they never delete user data."""
import logging
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text
from sqlalchemy.pool import NullPool

from app.config import get_settings

log = logging.getLogger("casio.migrate")
BACKEND_DIR = Path(__file__).resolve().parent.parent
LOCK_ID = 7_212_026  # any constant number shared by all instances


def upgrade() -> None:
    s = get_settings()
    cfg = Config(str(BACKEND_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
    engine = create_engine(s.database_url_unpooled or s.database_url, poolclass=NullPool, connect_args={"prepare_threshold": None})
    with engine.connect() as conn:
        conn.execute(text("SELECT pg_advisory_lock(:id)"), {"id": LOCK_ID})
        try:
            cfg.attributes["connection"] = conn
            command.upgrade(cfg, "head")
            conn.commit()
        finally:
            conn.execute(text("SELECT pg_advisory_unlock(:id)"), {"id": LOCK_ID})
            conn.commit()
    engine.dispose()
    log.info("database schema is up to date")


if __name__ == "__main__":
    upgrade()
