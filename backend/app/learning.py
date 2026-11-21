"""Adaptive learning engine: the user's own categorisation rules.

How it works, in plain words:

1. The user changes a category. That correction is always saved
   (`record_correction`), but it does NOT become a rule by itself.
2. CASIO asks "use this for similar transactions?" and shows what would
   change (`preview`). It recommends an answer from the user's history,
   for example "you've made this same change twice before".
3. Only if the user says yes, a rule is created (`create_rule`) and applied
   to matching transactions the user hasn't categorised themselves.
4. Rules run before CASIO's built-in keyword rules and before AI, on every
   import and every new transaction (`resolve`).
5. Every rule can be edited, paused or removed. Removing (or undoing) a rule
   puts each transaction back to the category it had before
   (`RuleApplication`).

Rules never touch a category the user picked by hand."""
import uuid
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.importers.base import normalise_description
from app.importers.categorize import keyword_guess
from app.importers.normalize import guess_merchant
from app.models import (
    Category,
    CategorizationRule,
    CategoryCorrection,
    ImportBatch,
    ImportRow,
    RuleApplication,
    Transaction,
    User,
)

PRIORITY = {"high": 90, "normal": 50, "low": 10}
PRIOR_WEIGHT = Decimal(5)  # a new rule starts at 95% and needs evidence to drop
START_CONFIDENCE = Decimal("0.95")
WEAK_RULE_BELOW = Decimal("0.6")

# Words too common to make a useful rule on their own: "upi" would match
# almost every payment.
_TOO_GENERIC = set(
    "upi imps neft rtgs pos ecom ach nach txn ref payment paid to from via by at on debit credit card vpa "
    "transfer order bill purchase india the and of for in online bank atm cash".split()
)


# ---------------------------------------------------------------------------
# Matching
# ---------------------------------------------------------------------------
def merchant_key(description: str, merchant: str | None) -> str:
    """The shop name CASIO compares rules against. 'UPI-SWIGGY-swiggy@icici-ORDER 4589' -> 'swiggy'."""
    return normalise_description(merchant or guess_merchant(description) or "")


def clean_pattern(text: str) -> str:
    return normalise_description(text)[:100]


def pattern_problem(pattern: str) -> str | None:
    """Why a pattern would make a bad rule, or None if it's fine."""
    if len(pattern) < 3:
        return "Use at least 3 letters so the rule doesn't match unrelated payments."
    if all(w in _TOO_GENERIC for w in pattern.split()):
        return f"“{pattern}” appears in almost every bank description. Pick a word that names the shop or service."
    return None


def matches(rule: CategorizationRule, description: str, merchant: str | None, tx_type: str | None) -> bool:
    if tx_type != rule.applies_to:
        return False
    if rule.match_type == "merchant":
        key = merchant_key(description, merchant)
        return key == rule.pattern or key.startswith(rule.pattern + " ")
    text = normalise_description(f"{description} {merchant or ''}")
    return f" {rule.pattern} " in f" {text} "


def _rank(rule: CategorizationRule):
    """Sort key: the first rule in sorted order wins a conflict."""
    created = rule.created_at.timestamp() if rule.created_at else datetime.now(UTC).timestamp()
    return (-rule.priority, -len(rule.pattern.split()), -len(rule.pattern), 0 if rule.match_type == "merchant" else 1, -created)


def active_rules(db: Session, user: User) -> list[CategorizationRule]:
    rules = db.scalars(
        select(CategorizationRule).where(CategorizationRule.user_id == user.id, CategorizationRule.active.is_(True))
    ).all()
    return sorted(rules, key=_rank)


def resolve(rules: list[CategorizationRule], description: str, merchant: str | None, tx_type: str | None) -> CategorizationRule | None:
    """The winning rule for a transaction, or None. `rules` must be sorted (active_rules does this)."""
    for r in rules:
        if matches(r, description, merchant, tx_type):
            return r
    return None


def describe(rule: CategorizationRule) -> str:
    what = f"shop name “{rule.pattern}”" if rule.match_type == "merchant" else f"descriptions containing “{rule.pattern}”"
    return f"Your rule: {what} → {rule.category.name}"


def update_confidence(rule: CategorizationRule) -> None:
    """Laplace-style estimate: how often the user kept what this rule chose.
    Starts at 95% and falls when the user keeps overriding it."""
    applied = Decimal(max(rule.times_applied, rule.times_overridden))
    kept = applied - Decimal(rule.times_overridden)
    rule.confidence = ((kept + PRIOR_WEIGHT * START_CONFIDENCE) / (applied + PRIOR_WEIGHT)).quantize(Decimal("0.001"))


def apply_to(item: Transaction | ImportRow, rule: CategorizationRule) -> None:
    item.category_id, item.category = rule.category_id, rule.category
    item.category_source = "rule"
    item.category_confidence = rule.confidence
    item.category_reason = describe(rule)[:300]
    item.rule_id = rule.id


def _categories_by_name(db: Session, user: User) -> dict[str, Category]:
    cats = db.scalars(select(Category).where(or_(Category.user_id.is_(None), Category.user_id == user.id))).all()
    by_name = {c.name: c for c in cats if c.user_id is None}
    by_name.update({c.name: c for c in cats if c.user_id is not None})
    return by_name


def _fallback(item: Transaction | ImportRow, by_name: dict[str, Category]) -> None:
    """No rule applies any more: go back to CASIO's built-in guess."""
    g = keyword_guess(item.description, item.merchant, item.type)
    cat = by_name.get(g.category)
    if cat and (cat.kind == "transfer" or cat.kind == item.type):
        item.category_id, item.category = cat.id, cat
        item.category_source, item.category_confidence, item.category_reason = "keyword", Decimal(str(g.confidence)), g.reason
    else:
        item.category_id, item.category, item.category_source, item.category_confidence, item.category_reason = None, None, None, None, None
    item.rule_id = None


# ---------------------------------------------------------------------------
# Applying rules to what's already there
# ---------------------------------------------------------------------------
def reapply(
    db: Session, user: User, touched: set[uuid.UUID] | None = None, transactions: bool = True, import_rows: bool = True
) -> tuple[int, int]:
    """Bring categories in line with the current rules. Only items that
    involve a rule in `touched` (or every item, if None) are looked at.
    Categories the user chose by hand are never changed.
    Returns (transactions changed, import rows changed)."""
    db.flush()
    rules = active_rules(db, user)
    by_name = None
    now = datetime.now(UTC)
    counts = [0, 0]

    def relevant(item, winner):
        return touched is None or (winner is not None and winner.id in touched) or item.rule_id in touched

    if transactions:
        txs = db.scalars(
            select(Transaction).where(
                Transaction.user_id == user.id,
                or_(Transaction.category_source.is_(None), Transaction.category_source != "user"),
                Transaction.type.in_(("income", "expense")),
            )
        ).all()
        for t in txs:
            winner = resolve(rules, t.description, t.merchant, t.type)
            if not relevant(t, winner):
                continue
            if winner:
                if t.rule_id == winner.id and t.category_id == winner.category_id:
                    continue
                if t.rule_id is None and db.get(RuleApplication, t.id) is None:
                    db.add(RuleApplication(
                        transaction_id=t.id, previous_category_id=t.category_id, previous_source=t.category_source,
                        previous_confidence=t.category_confidence, previous_reason=t.category_reason,
                    ))
                apply_to(t, winner)
                winner.times_applied += 1
                winner.last_applied_at = now
                counts[0] += 1
            elif t.rule_id is not None:
                prev = db.get(RuleApplication, t.id)
                if prev:
                    t.category_id = prev.previous_category_id
                    t.category = db.get(Category, prev.previous_category_id) if prev.previous_category_id else None
                    t.category_source, t.category_confidence = prev.previous_source, prev.previous_confidence
                    t.category_reason, t.rule_id = prev.previous_reason, None
                    db.delete(prev)
                else:
                    by_name = by_name or _categories_by_name(db, user)
                    _fallback(t, by_name)
                counts[0] += 1

    if import_rows:
        rows = db.scalars(
            select(ImportRow)
            .join(ImportBatch, ImportBatch.id == ImportRow.batch_id)
            .where(
                ImportRow.user_id == user.id, ImportBatch.status == "needs_review",
                or_(ImportRow.category_source.is_(None), ImportRow.category_source != "user"),
            )
        ).all()
        for r in rows:
            winner = resolve(rules, r.description, r.merchant, r.type)
            if not relevant(r, winner):
                continue
            if winner:
                if r.rule_id == winner.id and r.category_id == winner.category_id:
                    continue
                apply_to(r, winner)
                counts[1] += 1
            elif r.rule_id is not None:
                by_name = by_name or _categories_by_name(db, user)
                _fallback(r, by_name)
                counts[1] += 1
    return counts[0], counts[1]


# ---------------------------------------------------------------------------
# Corrections and suggestions
# ---------------------------------------------------------------------------
def record_correction(
    db: Session, user: User, item: Transaction | ImportRow, old_category_id, old_source, new_category_id
) -> None:
    """Save the correction. If a rule had chosen the old category, count it
    against that rule so its confidence drops."""
    if old_category_id == new_category_id:
        return
    if old_source == "rule" and item.rule_id:
        rule = db.get(CategorizationRule, item.rule_id)
        if rule:
            rule.times_overridden += 1
            update_confidence(rule)
    db.add(CategoryCorrection(
        user_id=user.id, transaction_id=item.id if isinstance(item, Transaction) else None,
        description=item.description[:500], merchant_key=merchant_key(item.description, item.merchant) or None,
        tx_type=item.type or "expense", from_category_id=old_category_id, to_category_id=new_category_id,
        from_source=old_source, rule_id=item.rule_id,
    ))
    item.rule_id = None


def _first_word(key: str) -> str:
    for w in key.split():
        if w not in _TOO_GENERIC and len(w) >= 3:
            return w
    return key


def preview(
    db: Session, user: User, item: Transaction | ImportRow, category: Category,
    match_type: str | None = None, pattern: str | None = None,
) -> dict:
    """Everything the "Remember this?" dialog needs: what the rule would
    be, what it would change, any conflicts, and a recommendation."""
    key = merchant_key(item.description, item.merchant)
    tx_type = item.type or "expense"
    if match_type is None:
        match_type = "merchant" if key else "contains"
    if pattern is None:
        pattern = key if match_type == "merchant" else _first_word(key or normalise_description(item.description))
    pattern = clean_pattern(pattern)
    problem = pattern_problem(pattern) if pattern else "CASIO couldn't find a shop name in this description."

    draft = CategorizationRule(
        id=uuid.uuid4(), user_id=user.id, category_id=category.id, category=category, match_type=match_type,
        pattern=pattern, applies_to=tx_type, priority=PRIORITY["normal"], active=True, confidence=START_CONFIDENCE,
        times_applied=0, times_overridden=0, created_at=datetime.now(UTC),
    )
    existing = db.scalar(select(CategorizationRule).where(
        CategorizationRule.user_id == user.id, CategorizationRule.match_type == match_type,
        CategorizationRule.pattern == pattern, CategorizationRule.applies_to == tx_type,
    ))
    others = [r for r in active_rules(db, user) if not existing or r.id != existing.id]
    with_draft = sorted(others + [draft], key=_rank)

    past_examples, past_count = [], 0
    if not problem:
        txs = db.scalars(
            select(Transaction).where(
                Transaction.user_id == user.id, Transaction.type == tx_type,
                or_(Transaction.category_source.is_(None), Transaction.category_source != "user"),
            ).order_by(Transaction.occurred_on.desc())
        ).all()
        for t in txs:
            if isinstance(item, Transaction) and t.id == item.id:
                continue
            if resolve(with_draft, t.description, t.merchant, t.type) is draft and t.category_id != category.id:
                past_count += 1
                if len(past_examples) < 5:
                    past_examples.append({
                        "description": t.description, "occurred_on": t.occurred_on.isoformat(), "amount": str(t.amount),
                        "category_name": t.category.name if t.category else None,
                    })

    in_import = 0
    if isinstance(item, ImportRow) and not problem:
        for r in db.scalars(select(ImportRow).where(ImportRow.batch_id == item.batch_id, ImportRow.id != item.id)):
            if (r.category_source != "user" and r.category_id != category.id
                    and resolve(with_draft, r.description, r.merchant, r.type) is draft):
                in_import += 1

    overlaps = []
    if not problem:
        sample = (item.description, item.merchant, tx_type)
        for r in others:
            if r.category_id != category.id and matches(r, *sample):
                overlaps.append({
                    "id": str(r.id), "match_type": r.match_type, "pattern": r.pattern, "category_name": r.category.name,
                    "wins": _rank(r) < _rank(draft),
                })

    # Recommendation: learn from what the user has done before.
    same, different = 0, 0
    if key:
        skipped_own = False
        for c in db.scalars(select(CategoryCorrection).where(
            CategoryCorrection.user_id == user.id, CategoryCorrection.merchant_key == key, CategoryCorrection.tx_type == tx_type,
        ).order_by(CategoryCorrection.created_at.desc())):
            if isinstance(item, Transaction) and c.transaction_id == item.id:
                continue
            # An import row's own correction (just saved) isn't "before".
            if isinstance(item, ImportRow) and not skipped_own and c.transaction_id is None and c.description == item.description[:500]:
                skipped_own = True
                continue
            if c.to_category_id == category.id:
                same += 1
            else:
                different += 1
    name = category.name
    if problem:
        rec, why = "once", problem
    elif existing and existing.category_id != category.id:
        rec, why = "always", f"You already have a rule sending these to {existing.category.name}. Choose “Always” to switch it to {name}."
    elif different:
        rec, why = "once", f"You've put this shop in other categories before, so this might be a one-off."
    elif same:
        rec, why = "always", f"You've made this same change {same + 1} times now. A rule saves you doing it again."
    elif past_count or in_import:
        rec, why = "always", f"{past_count + in_import} similar transaction{'s' if past_count + in_import != 1 else ''} could be fixed at once."
    else:
        rec, why = "once", "This is the first time you've changed this one. Make a rule if it's always this category."

    return {
        "tx_type": tx_type, "merchant_key": key or None, "match_type": match_type, "pattern": pattern,
        "suggested_word": _first_word(key or normalise_description(item.description)),
        "pattern_problem": problem, "category_id": str(category.id), "category_name": name,
        "matching_past": past_count, "examples": past_examples, "matching_in_import": in_import,
        "existing_rule": (
            {"id": str(existing.id), "category_name": existing.category.name, "same_category": existing.category_id == category.id}
            if existing else None
        ),
        "overlaps": overlaps, "recommendation": rec, "reason": why, "prior_corrections": same,
    }


def find_conflicts(db: Session, user: User, rules: list[CategorizationRule]) -> dict[uuid.UUID, list[dict]]:
    """For the Rules page: which rules match the same transactions but pick
    different categories, and which one wins."""
    active = sorted([r for r in rules if r.active], key=_rank)
    if len(active) < 2:
        return {}
    out: dict[uuid.UUID, dict[uuid.UUID, dict]] = {}
    txs = db.execute(
        select(Transaction.description, Transaction.merchant, Transaction.type)
        .where(Transaction.user_id == user.id).order_by(Transaction.occurred_on.desc()).limit(3000)
    ).all()
    for desc, merch, typ in txs:
        hits = [r for r in active if matches(r, desc, merch, typ)]
        if len(hits) < 2:
            continue
        winner = hits[0]
        for loser in hits[1:]:
            if loser.category_id == winner.category_id:
                continue
            for a, b, wins in ((winner, loser, True), (loser, winner, False)):
                entry = out.setdefault(a.id, {}).setdefault(b.id, {
                    "rule_id": str(b.id), "pattern": b.pattern, "match_type": b.match_type,
                    "category_name": b.category.name, "this_wins": wins, "transactions": 0,
                })
                entry["transactions"] += 1
    return {k: list(v.values()) for k, v in out.items()}


def is_weak(rule: CategorizationRule) -> bool:
    return Decimal(rule.confidence) < WEAK_RULE_BELOW

