from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.routers import account, auth, coaching, imports, overview, planning, profile, rules, subscriptions, transactions

app = FastAPI(title="CASIO API", version="0.1.0")


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
    subscriptions.router, planning.router, coaching.router,
):
    app.include_router(r, prefix="/api")


@app.get("/api/health")
def health():
    return {"status": "ok"}
