""""Try CASIO Demo": one click gives the visitor their own private sandbox
account full of fictional sample data. See app/demo/seed.py."""
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.responses import PlainTextResponse
from sqlalchemy.orm import Session

from app import rate_limit
from app.audit import audit
from app.db import get_db
from app.demo import seed
from app.deps import get_current_user
from app.models import User
from app.routers.auth import _start_session
from app.schemas import UserOut

router = APIRouter(prefix="/demo", tags=["demo"])

PER_VISITOR_LIMIT = 15  # new sandboxes per visitor per window
WINDOW_SECONDS = 60 * 60


def _visitor(request: Request) -> str:
    fwd = request.headers.get("x-forwarded-for", "")
    return fwd.split(",")[0].strip() or (request.client.host if request.client else "unknown")


def _new_sandbox(request: Request, response: Response, db: Session) -> User:
    if not rate_limit.allow(f"demo:{_visitor(request)}", PER_VISITOR_LIMIT, WINDOW_SECONDS):
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "Too many demo accounts were started from here. Please try again in an hour.")
    user = seed.create_demo_user(db)
    _start_session(db, response, user, remember_me=False)
    return user


@router.post("/start", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def start_demo(request: Request, response: Response, db: Session = Depends(get_db)):
    """Create a fresh sandbox and sign this browser into it."""
    return _new_sandbox(request, response, db)


@router.post("/reset", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def reset_demo(request: Request, response: Response, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Throw this sandbox away and start again with the original sample data."""
    if not user.is_demo:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only demo accounts can be reset.")
    uid = user.id
    db.delete(user)
    audit(db, "demo.reset", None, "user", uid)
    db.commit()
    return _new_sandbox(request, response, db)


def _demo_only(user: User) -> None:
    if not user.is_demo:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Sample files are only available in the demo.")


@router.get("/sample-statement.csv")
def sample_statement(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """A short statement made for this sandbox: some rows are already saved
    (duplicate check), the rest are new (categorisation and rules)."""
    _demo_only(user)
    return Response(seed.sample_statement(db, user), media_type="text/csv",
                    headers={"Content-Disposition": 'attachment; filename="casio-demo-new-statement.csv"'})


@router.get("/sample-sms.txt", response_class=PlainTextResponse)
def sample_sms(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _demo_only(user)
    return PlainTextResponse(seed.sample_sms(db, user))
