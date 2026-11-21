"""Subscriptions and recurring payments: list, alerts, and what the user tells us."""
import uuid
from datetime import UTC, date, datetime
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.audit import audit
from app.db import get_db
from app.deps import get_current_user
from app.finance import money, monthly_amount
from app.formatting import fmt_money
from app.models import RecurringAlert, RecurringPayment, User
from app.recurring import as_of_date, detect_recurring, dismiss_usage_alerts, state
from app.routers.profile import get_or_create_profile
from app.schemas import RecurringAlertOut, RecurringOut, RecurringPage, RecurringSummary, RecurringUpdate

router = APIRouter(tags=["subscriptions"])
_EVERY = {"weekly": "every week", "fortnightly": "every two weeks", "monthly": "every month", "quarterly": "every three months", "yearly": "every year"}
_ORDER = {"active": 0, "overdue": 0, "cancelled": 1, "not_recurring": 2}


def _out(rp: RecurringPayment, as_of: date, currency: str) -> RecurringOut:
    monthly = money(monthly_amount(rp.amount, rp.frequency))
    amt = f"about {fmt_money(rp.average_amount, currency)}" if rp.amount_varies else fmt_money(rp.amount, currency)
    why = (
        f"Paid {rp.occurrences} times {_EVERY[rp.frequency]}, {amt}"
        f"{' (the amount changes each time)' if rp.amount_varies else ''}. "
        f"Last paid {rp.last_paid_on:%d %b %Y}."
    )
    return RecurringOut(
        id=rp.id, name=rp.name, kind=rp.kind, category_name=rp.category.name if rp.category else None,
        frequency=rp.frequency, amount=rp.amount, average_amount=rp.average_amount, amount_varies=rp.amount_varies,
        monthly_cost=monthly, yearly_cost=money(monthly * 12), first_paid_on=rp.first_paid_on, last_paid_on=rp.last_paid_on,
        next_expected_on=rp.next_expected_on if rp.status == "active" else None, occurrences=rp.occurrences,
        confidence=float(rp.confidence), charges=rp.charges, price_changes=rp.price_changes, status=rp.status,
        state=state(rp, as_of), usage=rp.usage, usage_confirmed_at=rp.usage_confirmed_at, explanation=why,
    )


def _alerts(db: Session, user: User, limit: int = 50) -> list[RecurringAlert]:
    return list(db.scalars(
        select(RecurringAlert).where(RecurringAlert.user_id == user.id, RecurringAlert.dismissed_at.is_(None))
        .order_by(RecurringAlert.created_at.desc()).limit(limit)
    ))


@router.get("/subscriptions", response_model=RecurringPage)
def list_recurring(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Re-checks the transactions first, so the list is always current."""
    as_of = detect_recurring(db, user)
    db.commit()
    currency = get_or_create_profile(db, user).currency
    rows = db.scalars(select(RecurringPayment).where(RecurringPayment.user_id == user.id)).all()
    items = sorted((_out(r, as_of, currency) for r in rows), key=lambda o: (_ORDER[o.state], -o.monthly_cost, o.name))
    live = [i for i in items if i.status == "active"]
    zero = Decimal("0.00")
    summary = RecurringSummary(
        active_count=len(live),
        monthly_total=sum((i.monthly_cost for i in live), zero),
        yearly_total=sum((i.yearly_cost for i in live), zero),
        subscriptions_monthly=sum((i.monthly_cost for i in live if i.kind == "subscription"), zero),
        bills_monthly=sum((i.monthly_cost for i in live if i.kind == "bill"), zero),
        not_using_yearly=sum((i.yearly_cost for i in live if i.usage == "not_using"), zero),
        unknown_usage_count=sum(1 for i in live if i.kind == "subscription" and i.usage == "unknown"),
    )
    return RecurringPage(
        as_of=as_of, currency=currency, summary=summary, items=items,
        alerts=[RecurringAlertOut.model_validate(a) for a in _alerts(db, user)],
    )


@router.get("/subscriptions/alerts", response_model=list[RecurringAlertOut])
def list_alerts(limit: int = Query(5, ge=1, le=50), user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return _alerts(db, user, limit)


@router.patch("/subscriptions/{rp_id}", response_model=RecurringOut)
def update_recurring(rp_id: uuid.UUID, data: RecurringUpdate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    rp = db.scalar(select(RecurringPayment).where(RecurringPayment.id == rp_id, RecurringPayment.user_id == user.id))
    if rp is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "That payment wasn't found.")
    sent = data.model_fields_set
    if "name" in sent and data.name:
        rp.name, rp.name_edited = " ".join(data.name.split()), True
    if "kind" in sent and data.kind:
        rp.kind = data.kind
    if "status" in sent and data.status and data.status != rp.status:
        rp.status, rp.status_changed_on = data.status, as_of_date(db, user)
    if "usage" in sent and data.usage:
        rp.usage = data.usage
        rp.usage_confirmed_at = datetime.now(UTC) if data.usage != "unknown" else None
    dismiss_usage_alerts(db, rp)
    audit(db, "recurring.update", user.id, "recurring_payment", rp.id, fields=sorted(sent))
    db.commit()
    db.refresh(rp)
    return _out(rp, as_of_date(db, user), get_or_create_profile(db, user).currency)


@router.post("/subscriptions/alerts/{alert_id}/dismiss", status_code=204)
def dismiss_alert(alert_id: uuid.UUID, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    a = db.scalar(select(RecurringAlert).where(RecurringAlert.id == alert_id, RecurringAlert.user_id == user.id))
    if a is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "That alert wasn't found.")
    a.dismissed_at = datetime.now(UTC)
    db.commit()
