from collections.abc import Iterator

import os

from sqlalchemy import create_engine
from sqlalchemy.pool import NullPool
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import get_settings


class Base(DeclarativeBase):
    pass


# On Vercel each function instance is short-lived, so don't hold a pool of
# connections open; the database provider's pooler does that job. Prepared
# statements are switched off so this works through a connection pooler.
_serverless = bool(os.environ.get("VERCEL"))
engine = create_engine(
    get_settings().database_url,
    pool_pre_ping=True,
    poolclass=NullPool if _serverless else None,
    connect_args={"prepare_threshold": None},
)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)


def get_db() -> Iterator[Session]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
