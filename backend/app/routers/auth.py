from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app import rate_limit
from app.config import get_settings
from app.db import get_db
from app.deps import get_current_session, get_current_user
from app.email import send_password_reset
from app.audit import audit
from app.models import PasswordResetToken, User, UserProfile, UserSession
from app.schemas import (
    ForgotPasswordIn,
    LoginIn,
    MessageOut,
    RegisterIn,
    ResetPasswordIn,
    UserOut,
)
from app.security import hash_password, hash_token, new_token, verify_password

router = APIRouter(prefix="/auth", tags=["auth"])


def _start_session(db: Session, response: Response, user: User, remember_me: bool) -> None:
    s = get_settings()
    token = new_token()
    lifetime = timedelta(days=s.remember_me_days) if remember_me else timedelta(hours=s.short_session_hours)
    db.add(UserSession(user_id=user.id, token_hash=hash_token(token), expires_at=datetime.now(UTC) + lifetime))
    # Tidy up this user's expired sessions while we're here.
    db.execute(delete(UserSession).where(UserSession.user_id == user.id, UserSession.expires_at < datetime.now(UTC)))
    db.commit()
    response.set_cookie(
        s.session_cookie_name,
        token,
        # No max_age = cookie is deleted when the browser closes.
        max_age=int(lifetime.total_seconds()) if remember_me else None,
        httponly=True,  # JavaScript can't read it, which blocks token theft via XSS
        secure=s.cookie_secure,
        samesite="lax",  # not sent on cross-site form posts, which blocks CSRF
        path="/",
    )


@router.post("/register", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def register(data: RegisterIn, response: Response, db: Session = Depends(get_db)):
    user = User(email=data.email, full_name=data.full_name, password_hash=hash_password(data.password))
    db.add(user)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "An account with this email already exists. Try logging in.")
    db.add(UserProfile(user_id=user.id))
    audit(db, "auth.register", user.id, "user", user.id)
    _start_session(db, response, user, remember_me=False)
    return user


@router.post("/login", response_model=UserOut)
def login(data: LoginIn, response: Response, db: Session = Depends(get_db)):
    if rate_limit.is_blocked(data.email):
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            "Too many failed attempts. Please wait 15 minutes or reset your password.",
        )
    user = db.scalar(select(User).where(User.email == data.email))
    if not verify_password(user.password_hash if user else None, data.password):
        rate_limit.record_failure(data.email)
        audit(db, "auth.login_failed", user.id if user else None)
        db.commit()
        # Same message whether the email or the password was wrong,
        # so nobody can use this form to find out who has an account.
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Incorrect email or password.")
    rate_limit.reset(data.email)
    audit(db, "auth.login", user.id, remember_me=data.remember_me)
    _start_session(db, response, user, data.remember_me)
    return user


@router.post("/logout", response_model=MessageOut)
def logout(response: Response, session: UserSession = Depends(get_current_session), db: Session = Depends(get_db)):
    audit(db, "auth.logout", session.user_id)
    db.delete(session)
    db.commit()
    response.delete_cookie(get_settings().session_cookie_name, path="/")
    return {"message": "You have been logged out."}


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)):
    return user


@router.post("/forgot-password", response_model=MessageOut)
def forgot_password(data: ForgotPasswordIn, db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(User.email == data.email))
    if user:
        token = new_token()
        db.add(
            PasswordResetToken(
                user_id=user.id,
                token_hash=hash_token(token),
                expires_at=datetime.now(UTC) + timedelta(minutes=get_settings().password_reset_minutes),
            )
        )
        audit(db, "auth.password_reset_requested", user.id)
        db.commit()
        send_password_reset(user.email, f"{get_settings().frontend_url}/reset-password?token={token}")
    # Same reply either way so this can't be used to discover accounts.
    return {"message": "If an account exists for this email, we've sent a link to reset the password."}


@router.post("/reset-password", response_model=MessageOut)
def reset_password(data: ResetPasswordIn, db: Session = Depends(get_db)):
    record = db.scalar(select(PasswordResetToken).where(PasswordResetToken.token_hash == hash_token(data.token)))
    if not record or record.used_at or record.expires_at < datetime.now(UTC):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "This reset link is invalid or has expired. Please request a new one.")
    user = db.get(User, record.user_id)
    user.password_hash = hash_password(data.password)
    record.used_at = datetime.now(UTC)
    # Sign out every device, in case someone else had access.
    db.execute(delete(UserSession).where(UserSession.user_id == user.id))
    audit(db, "auth.password_reset", user.id)
    db.commit()
    rate_limit.reset(user.email)
    return {"message": "Your password has been changed. You can now log in."}
