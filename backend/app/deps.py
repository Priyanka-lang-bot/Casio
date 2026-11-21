from datetime import UTC, datetime

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_db
from app.models import User, UserSession
from app.security import hash_token


def get_current_session(request: Request, db: Session = Depends(get_db)) -> UserSession:
    """Every protected endpoint uses this. It finds the signed-in user from the
    session cookie, or refuses the request with 401."""
    token = request.cookies.get(get_settings().session_cookie_name)
    if token:
        session = db.scalar(select(UserSession).where(UserSession.token_hash == hash_token(token)))
        if session and session.expires_at > datetime.now(UTC):
            return session
    raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Please log in to continue.")


def get_current_user(session: UserSession = Depends(get_current_session)) -> User:
    return session.user
