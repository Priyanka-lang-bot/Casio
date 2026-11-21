"""App settings, read from environment variables (or the .env file).

Secrets and machine-specific values never live in the code."""
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://casio:casio_dev_password@localhost:5432/casio"
    cookie_secure: bool = False
    frontend_url: str = "http://localhost:3000"
    email_mode: str = "console"

    session_cookie_name: str = "casio_session"
    # "Remember me" keeps you signed in for 30 days; otherwise 12 hours
    # and the cookie disappears when the browser closes.
    remember_me_days: int = 30
    short_session_hours: int = 12
    password_reset_minutes: int = 30


@lru_cache
def get_settings() -> Settings:
    return Settings()
