"""Nudges, monthly reports and the AI coach."""
import datetime as dt
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app import ai, coach, nudges, planning, rate_limit, reports
from app.audit import audit
from app.db import get_db
from app.deps import get_current_user
from app.finance import to_json
from app.models import CoachMessage, FinancialNudge, MonthlyReport, User
from app.routers.profile import get_or_create_profile

router = APIRouter(tags=["coaching"])


# ---------------------------------------------------------------------------
# Nudges
# ---------------------------------------------------------------------------
def _nudge_out(n: FinancialNudge) -> dict:
    return {"id": n.id, "kind": n.kind, "severity": n.severity, "title": n.title, "message": n.message,
            "link": n.link, "created_at": n.created_at}


@router.get("/nudges")
def list_nudges(limit: int = Query(20, ge=1, le=50), user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Re-checks the user's data first, so nudges are always current."""
    nudges.refresh(db, user, get_or_create_profile(db, user).currency)
    db.commit()
    return to_json([_nudge_out(n) for n in nudges.current(db, user, limit)])


@router.post("/nudges/{nudge_id}/dismiss", status_code=204)
def dismiss_nudge(nudge_id: uuid.UUID, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    n = db.scalar(select(FinancialNudge).where(FinancialNudge.id == nudge_id, FinancialNudge.user_id == user.id))
    if n is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "That message wasn't found.")
    n.dismissed_at = dt.datetime.now(dt.UTC)
    db.commit()


# ---------------------------------------------------------------------------
# Monthly reports
# ---------------------------------------------------------------------------
def _report_out(r: MonthlyReport) -> dict:
    return {**r.data, "narrative": r.narrative, "narrative_source": r.narrative_source, "generated_at": r.generated_at}


@router.get("/reports")
def list_reports(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    saved = {f"{r.month:%Y-%m}": r.generated_at for r in db.scalars(select(MonthlyReport).where(MonthlyReport.user_id == user.id))}
    months = reports.months_with_data(db, user)
    return to_json({"months": [{"month": m, "generated_at": saved.get(m)} for m in months], "ai": ai.ai_status()})


@router.get("/reports/{month}")
def get_report(month: str, refresh: bool = False, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Built the first time it's opened and saved. The current month (or
    refresh=true) is rebuilt so it includes the latest transactions."""
    try:
        first = planning.parse_month(month)
    except ValueError:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Use a month like 2026-11.")
    r = db.scalar(select(MonthlyReport).where(MonthlyReport.user_id == user.id, MonthlyReport.month == first))
    is_current = first == planning.month_start(dt.date.today())
    if r is None or refresh or is_current:
        currency = get_or_create_profile(db, user).currency
        data = to_json(reports.build(db, user, first, currency))
        # Keep the existing AI summary for the current month unless asked to refresh (saves AI calls).
        if r is not None and is_current and not refresh:
            r.data = data
        else:
            text, source = coach.report_narrative(data, currency)
            if r is None:
                r = MonthlyReport(user_id=user.id, month=first, data=data, narrative=text, narrative_source=source)
                db.add(r)
            else:
                r.data, r.narrative, r.narrative_source = data, text, source
                r.generated_at = dt.datetime.now(dt.UTC)
        db.commit()
        db.refresh(r)
    return to_json(_report_out(r))


# ---------------------------------------------------------------------------
# AI coach
# ---------------------------------------------------------------------------
class ChatIn(BaseModel):
    message: str = Field(min_length=1, max_length=2000)


def _msg_out(m: CoachMessage) -> dict:
    return {"id": m.id, "role": m.role, "content": m.content, "meta": m.meta or {}, "created_at": m.created_at}


@router.get("/coach")
def coach_history(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    rows = db.scalars(select(CoachMessage).where(CoachMessage.user_id == user.id).order_by(CoachMessage.created_at.desc()).limit(60)).all()
    return to_json({"ai": ai.ai_status(), "messages": [_msg_out(m) for m in reversed(rows)]})


@router.post("/coach")
def coach_chat(data: ChatIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if not rate_limit.allow(f"coach:{user.id}", limit=30, window_seconds=3600):
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "You've asked a lot of questions this hour. Please try again a bit later.")
    history_rows = db.scalars(select(CoachMessage).where(CoachMessage.user_id == user.id)
                              .order_by(CoachMessage.created_at.desc()).limit(coach.HISTORY_TURNS * 2)).all()
    history = [{"role": m.role, "content": m.content} for m in reversed(history_rows)]
    while history and history[0]["role"] != "user":
        history.pop(0)
    question = data.message.strip()
    user_msg = CoachMessage(user_id=user.id, role="user", content=question)
    db.add(user_msg)
    db.flush()
    result = coach.answer(db, user, question, history, get_or_create_profile(db, user).currency)
    reply = CoachMessage(user_id=user.id, role="assistant", content=result["text"],
                         meta={"source": result["source"], "tools": result["tools"], "blocked": result["blocked"]})
    db.add(reply)
    audit(db, "coach.ask", user.id, source=result["source"], blocked=result["blocked"])
    db.commit()
    db.refresh(user_msg)
    db.refresh(reply)
    return to_json({"question": _msg_out(user_msg), "answer": _msg_out(reply)})


@router.delete("/coach", status_code=204)
def clear_coach(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    db.execute(delete(CoachMessage).where(CoachMessage.user_id == user.id))
    db.commit()
