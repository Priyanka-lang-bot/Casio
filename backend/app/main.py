import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.routers import account, auth, coaching, demo, imports, overview, planning, profile, rules, subscriptions, transactions

from app.config import get_settings  # noqa: E402

logging.basicConfig(level=logging.INFO)


@asynccontextmanager
async def lifespan(_: FastAPI):
    if get_settings().migrate_on_startup:
        from starlette.concurrency import run_in_threadpool

        from app.migrate import upgrade

        await run_in_threadpool(upgrade)
    yield


app = FastAPI(title="CASIO API", version="1.0.0", lifespan=lifespan)


@app.exception_handler(RequestValidationError)
async def friendly_validation_errors(request: Request, exc: RequestValidationError):
    """Turn Pydantic's technical errors into one plain sentence per field.
    The submitted values are never echoed back (they may contain passwords)."""
    fields: dict[str, str] = {}
    for err in exc.errors():
        loc = [p for p in err.get("loc", ()) if p != "body"]
        field = str(loc[-1]) if loc else ("confirm_password" if err.get("type") == "password_mismatch" else "form")
        msg = err.get("msg", "Invalid value.")
        msg = msg.removeprefix("Value error, ")
        if field == "email":
            msg = "Please enter a valid email address."
        elif err.get("type") == "missing":
            msg = "This field is required."
        fields.setdefault(field, msg)
    return JSONResponse(status_code=422, content={"detail": "Please check the highlighted fields.", "fields": fields})


for r in (
    auth.router, account.router, profile.router, transactions.router, overview.router, imports.router, rules.router,
    subscriptions.router, planning.router, coaching.router, demo.router,
):
    app.include_router(r, prefix="/api")


@app.get("/api/health")
def health():
    """For uptime checks: confirms the API runs and can reach the database."""
    from sqlalchemy import text

    from app import ai
    from app.db import engine

    try:
        with engine.connect() as conn:
            version = conn.execute(text("SELECT version_num FROM alembic_version")).scalar()
        db = "ok"
    except Exception:
        version, db = None, "unreachable"
    return JSONResponse(
        status_code=200 if db == "ok" else 503,
        content={"status": "ok" if db == "ok" else "degraded", "database": db, "schema": version, "ai": ai.ai_status()},
    )
