"""App settings, read from environment variables (or the .env file).

Secrets and machine-specific values never live in the code."""
from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def _psycopg_url(url: str) -> str:
    """Hosting providers hand out "postgres://..." URLs; SQLAlchemy needs the
    driver named: "postgresql+psycopg://...". Query options (sslmode) are kept."""
    for prefix in ("postgres://", "postgresql://"):
        if url.startswith(prefix):
            return "postgresql+psycopg://" + url[len(prefix):]
    return url


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://casio:casio_dev_password@localhost:5432/casio"
    # Optional direct (non-pooled) connection for migrations. Neon provides one.
    database_url_unpooled: str = ""
    # Production: bring the database schema up to date when the API starts.
    migrate_on_startup: bool = False
    cookie_secure: bool = False
    frontend_url: str = "http://localhost:3000"
    email_mode: str = "console"

    # AI (optional). Without a key, CASIO uses its built-in keyword rules.
    anthropic_api_key: str = ""
    ai_model: str = "claude-opus-5-5"

    session_cookie_name: str = "casio_session"

    @field_validator("database_url", "database_url_unpooled")
    @classmethod
    def driver_url(cls, v: str) -> str:
        return _psycopg_url(v.strip())
    # "Remember me" keeps you signed in for 30 days; otherwise 12 hours
    # and the cookie disappears when the browser closes.
    remember_me_days: int = 30
    short_session_hours: int = 12
    password_reset_minutes: int = 30


@lru_cache
def get_settings() -> Settings:
    return Settings()
