"""Learned rules: preview, create, edit, pause, remove (with undo).

See app/learning.py for how the engine works."""
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session, aliased

from app import learning
from app.audit import audit
from app.db import get_db
from app.deps import get_current_user
from app.models import Category, CategorizationRule, CategoryCorrection, ImportRow, Transaction, User
from app.routers.transactions import _check_category
from app.schemas import CorrectionOut, RuleIn, RuleOut, RulePreviewIn, RuleSaveOut, RuleUpdate

router = APIRouter(tags=["rules"])
_PRIORITY_NAME = {v: k for k, v in learning.PRIORITY.items()}


def _priority_name(p: int) -> str:
    return _PRIORITY_NAME.get(p, "high" if p > 70 else "low" if p < 30 else "normal")


def _out(r: CategorizationRule, applied: int = 0, conflicts: list | None = None) -> RuleOut:
    return RuleOut(
        id=r.id, category_id=r.category_id, category_name=r.category.name, match_type=r.match_type, pattern=r.pattern,
        applies_to=r.applies_to, priority=_priority_name(r.priority), active=r.active, times_applied=r.times_applied,
        times_overridden=r.times_overridden, confidence=float(r.confidence), weak=learning.is_weak(r),
        currently_applied=applied, last_applied_at=r.last_applied_at, created_at=r.created_at, conflicts=conflicts or [],
    )


def _get_rule(db: Session, user: User, rule_id: uuid.UUID) -> CategorizationRule:
    r = db.scalar(select(CategorizationRule).where(CategorizationRule.id == rule_id, CategorizationRule.user_id == user.id))
    if r is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "That rule wasn't found.")
    return r


def _applied(db: Session, rule_id: uuid.UUID) -> int:
    return db.scalar(select(func.count()).select_from(Transaction).where(Transaction.rule_id == rule_id)) or 0


def _check_pattern(pattern: str) -> str:
    clean = learning.clean_pattern(pattern)
    problem = learning.pattern_problem(clean)
    if problem:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, problem)
    return clean


@router.get("/rules", response_model=list[RuleOut])
def list_rules(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    rules = db.scalars(select(CategorizationRule).where(CategorizationRule.user_id == user.id)).all()
    counts = dict(db.execute(
        select(Transaction.rule_id, func.count()).where(Transaction.user_id == user.id, Transaction.rule_id.is_not(None))
        .group_by(Transaction.rule_id)
    ).all())
    conflicts = learning.find_conflicts(db, user, list(rules))
    ordered = sorted(rules, key=lambda r: (not r.active, learning._rank(r)))
    return [_out(r, counts.get(r.id, 0), conflicts.get(r.id)) for r in ordered]


@router.post("/rules/preview")
def preview(data: RulePreviewIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """What a rule made from this correction would do. Changes nothing."""
    if data.transaction_id:
        item = db.scalar(select(Transaction).where(Transaction.id == data.transaction_id, Transaction.user_id == user.id))
    else:
        item = db.scalar(select(ImportRow).where(ImportRow.id == data.import_row_id, ImportRow.user_id == user.id))
    if item is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "That transaction wasn't found.")
    _check_category(db, user, data.category_id, item.type or "expense")
    return learning.preview(db, user, item, db.get(Category, data.category_id), data.match_type, data.pattern)


@router.post("/rules", response_model=RuleSaveOut, status_code=201)
def create_rule(data: RuleIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Create a rule (only ever called after the user said yes). If a rule
    with the same match already exists, it's switched to the new category."""
    _check_category(db, user, data.category_id, data.applies_to)
    pattern = _check_pattern(data.pattern)
    rule = db.scalar(select(CategorizationRule).where(
        CategorizationRule.user_id == user.id, CategorizationRule.match_type == data.match_type,
        CategorizationRule.pattern == pattern, CategorizationRule.applies_to == data.applies_to,
    ))
    replaced = rule is not None and rule.category_id != data.category_id
    if rule is None:
        rule = CategorizationRule(
            user_id=user.id, category_id=data.category_id, match_type=data.match_type, pattern=pattern,
            applies_to=data.applies_to, priority=learning.PRIORITY[data.priority], active=True,
            confidence=learning.START_CONFIDENCE, times_applied=0, times_overridden=0,
            created_from_transaction_id=None,
        )
        if data.source_transaction_id and db.scalar(select(Transaction.id).where(
            Transaction.id == data.source_transaction_id, Transaction.user_id == user.id
        )):
            rule.created_from_transaction_id = data.source_transaction_id
        db.add(rule)
    else:
        rule.category_id, rule.active, rule.priority = data.category_id, True, learning.PRIORITY[data.priority]
        if replaced:  # a different answer: start its track record again
            rule.times_applied = rule.times_overridden = 0
            rule.confidence = learning.START_CONFIDENCE
    db.flush()
    db.refresh(rule)
    # Link the correction that led to this rule (shown as "Made a rule").
    q = select(CategoryCorrection).where(
        CategoryCorrection.user_id == user.id, CategoryCorrection.rule_id.is_(None),
        CategoryCorrection.to_category_id == rule.category_id,
    ).order_by(CategoryCorrection.created_at.desc()).limit(20)
    if data.source_transaction_id:
        q = q.where(CategoryCorrection.transaction_id == data.source_transaction_id)
    for c in db.scalars(q):
        if learning.matches(rule, c.description, None, c.tx_type):
            c.rule_id = rule.id
            break
    tx, rows = learning.reapply(db, user, {rule.id}, transactions=data.apply_to_past)
    audit(db, "rule.replace" if replaced else "rule.create", user.id, "rule", rule.id, changed=tx)
    db.commit()
    db.refresh(rule)
    return RuleSaveOut(rule=_out(rule, _applied(db, rule.id)), changed_transactions=tx, changed_import_rows=rows, replaced=replaced)


@router.patch("/rules/{rule_id}", response_model=RuleSaveOut)
def update_rule(rule_id: uuid.UUID, data: RuleUpdate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    rule = _get_rule(db, user, rule_id)
    sent = data.model_fields_set
    if "category_id" in sent and data.category_id:
        _check_category(db, user, data.category_id, rule.applies_to)
        if data.category_id != rule.category_id:
            rule.category_id = data.category_id
            rule.category = db.get(Category, data.category_id)
    new_type = data.match_type if "match_type" in sent and data.match_type else rule.match_type
    new_pattern = _check_pattern(data.pattern) if "pattern" in sent and data.pattern else rule.pattern
    if (new_type, new_pattern) != (rule.match_type, rule.pattern):
        clash = db.scalar(select(CategorizationRule).where(
            CategorizationRule.user_id == user.id, CategorizationRule.id != rule.id,
            CategorizationRule.match_type == new_type, CategorizationRule.pattern == new_pattern,
            CategorizationRule.applies_to == rule.applies_to,
        ))
        if clash:
            raise HTTPException(status.HTTP_409_CONFLICT, f"You already have a rule for “{new_pattern}” ({clash.category.name}). Edit that one instead.")
        rule.match_type, rule.pattern = new_type, new_pattern
    if "priority" in sent and data.priority:
        rule.priority = learning.PRIORITY[data.priority]
    if "active" in sent and data.active is not None:
        rule.active = data.active
    tx, rows = learning.reapply(db, user, {rule.id})
    audit(db, "rule.update", user.id, "rule", rule.id, changed=tx)
    db.commit()
    db.refresh(rule)
    return RuleSaveOut(rule=_out(rule, _applied(db, rule.id)), changed_transactions=tx, changed_import_rows=rows)


@router.delete("/rules/{rule_id}")
def delete_rule(rule_id: uuid.UUID, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Remove a rule. Transactions it categorised go back to what they were
    before (or to another rule that matches). Also used for "Undo"."""
    rule = _get_rule(db, user, rule_id)
    rule.active = False
    tx, rows = learning.reapply(db, user, {rule.id})
    db.delete(rule)
    audit(db, "rule.delete", user.id, "rule", rule_id, reverted=tx)
    db.commit()
    return {"reverted_transactions": tx, "reverted_import_rows": rows}


@router.get("/rules/corrections", response_model=list[CorrectionOut])
def corrections(limit: int = Query(20, ge=1, le=100), user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """The user's recent category changes, newest first."""
    old, new = aliased(Category), aliased(Category)
    q = (
        select(CategoryCorrection, old.name, new.name)
        .outerjoin(old, old.id == CategoryCorrection.from_category_id)
        .outerjoin(new, new.id == CategoryCorrection.to_category_id)
        .where(CategoryCorrection.user_id == user.id)
        .order_by(CategoryCorrection.created_at.desc())
        .limit(limit)
    )
    return [
        CorrectionOut(
            id=c.id, description=c.description, from_category=o, to_category=n, from_source=c.from_source,
            made_rule=c.rule_id is not None, created_at=c.created_at,
        )
        for c, o, n in db.execute(q).all()
    ]
