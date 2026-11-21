"""Database tables for milestone 1 (authentication).

Financial tables (accounts, transactions, budgets, ...) come in later
milestones and will all hang off users.id with a foreign key."""
import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, false, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    # Stored lower-cased so "Ana@x.com" and "ana@x.com" are the same account.
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    full_name: Mapped[str] = mapped_column(String(100))
    # Argon2 hash. The real password is never stored.
    password_hash: Mapped[str] = mapped_column(String(255))
    # Throwaway sandbox account from "Try CASIO Demo" (sample data only, auto-deleted).
    is_demo: Mapped[bool] = mapped_column(default=False, server_default=false())
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    sessions: Mapped[list["UserSession"]] = relationship(back_populates="user", cascade="all, delete-orphan")


class UserSession(Base):
    """One row per signed-in browser. Deleting the row signs that browser out."""

    __tablename__ = "user_sessions"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    # SHA-256 of the cookie value. A leaked database can't be used to log in.
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)

    user: Mapped[User] = relationship(back_populates="sessions")


class PasswordResetToken(Base):
    __tablename__ = "password_reset_tokens"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


# ---------------------------------------------------------------------------
# Shared building blocks
# ---------------------------------------------------------------------------
from datetime import date  # noqa: E402
from decimal import Decimal  # noqa: E402

from sqlalchemy import (  # noqa: E402
    CheckConstraint,
    Date,
    Index,
    Integer,
    Numeric,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB  # noqa: E402

# Money is always stored as an exact decimal with 2 places (never a float),
# up to 999,999,999,999.99.
Money = Numeric(14, 2)

FREQUENCIES = ("weekly", "fortnightly", "monthly", "quarterly", "yearly")
_FREQ_CHECK = "frequency IN ('weekly','fortnightly','monthly','quarterly','yearly')"


class Timestamps:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


def owner_column() -> Mapped[uuid.UUID]:
    """Every piece of financial data belongs to exactly one user. Deleting the
    user deletes their data (supports "delete my account")."""
    return mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)


# ---------------------------------------------------------------------------
# Profile
# ---------------------------------------------------------------------------
class UserProfile(Timestamps, Base):
    __tablename__ = "user_profiles"

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    # One currency per user keeps every total meaningful (no mixing ₹ and $).
    currency: Mapped[str] = mapped_column(String(3), default="INR", server_default="INR")
    country: Mapped[str | None] = mapped_column(String(2))


# ---------------------------------------------------------------------------
# Living Money Model inputs (what the user tells us; these are ESTIMATES)
# ---------------------------------------------------------------------------
class IncomeSource(Timestamps, Base):
    __tablename__ = "income_sources"
    __table_args__ = (CheckConstraint("amount > 0", name="amount_positive"), CheckConstraint(_FREQ_CHECK, name="frequency_valid"))

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = owner_column()
    name: Mapped[str] = mapped_column(String(100))
    amount: Mapped[Decimal] = mapped_column(Money)
    frequency: Mapped[str] = mapped_column(String(12), default="monthly")


class ExpenseItem(Timestamps, Base):
    """A regular cost the user expects: rent (fixed) or groceries (variable)."""

    __tablename__ = "expense_items"
    __table_args__ = (
        CheckConstraint("amount > 0", name="amount_positive"),
        CheckConstraint(_FREQ_CHECK, name="frequency_valid"),
        CheckConstraint("kind IN ('fixed','variable')", name="kind_valid"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = owner_column()
    name: Mapped[str] = mapped_column(String(100))
    amount: Mapped[Decimal] = mapped_column(Money)
    frequency: Mapped[str] = mapped_column(String(12), default="monthly")
    kind: Mapped[str] = mapped_column(String(10), default="fixed")
    category_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("categories.id", ondelete="SET NULL"))


ASSET_KINDS = ("cash", "bank_account", "savings", "emergency_fund", "investment", "property", "vehicle", "other")
LIABILITY_KINDS = ("credit_card", "personal_loan", "home_loan", "vehicle_loan", "education_loan", "other")


class Asset(Timestamps, Base):
    __tablename__ = "assets"
    __table_args__ = (
        CheckConstraint("value >= 0", name="value_not_negative"),
        CheckConstraint("kind IN ('" + "','".join(ASSET_KINDS) + "')", name="kind_valid"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = owner_column()
    name: Mapped[str] = mapped_column(String(100))
    kind: Mapped[str] = mapped_column(String(20))
    value: Mapped[Decimal] = mapped_column(Money)


class Liability(Timestamps, Base):
    __tablename__ = "liabilities"
    __table_args__ = (
        CheckConstraint("balance >= 0", name="balance_not_negative"),
        CheckConstraint("monthly_payment IS NULL OR monthly_payment >= 0", name="payment_not_negative"),
        CheckConstraint("interest_rate IS NULL OR (interest_rate >= 0 AND interest_rate <= 100)", name="rate_valid"),
        CheckConstraint("kind IN ('" + "','".join(LIABILITY_KINDS) + "')", name="kind_valid"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = owner_column()
    name: Mapped[str] = mapped_column(String(100))
    kind: Mapped[str] = mapped_column(String(20))
    balance: Mapped[Decimal] = mapped_column(Money)
    monthly_payment: Mapped[Decimal | None] = mapped_column(Money)
    interest_rate: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))  # yearly %, e.g. 12.50


# ---------------------------------------------------------------------------
# Money that actually moved (ACTUALS)
# ---------------------------------------------------------------------------
class Category(Base):
    """user_id NULL = built-in category shared by everyone; otherwise a custom
    category that only its owner can see."""

    __tablename__ = "categories"
    __table_args__ = (
        UniqueConstraint("user_id", "name", postgresql_nulls_not_distinct=True, name="uq_categories_user_name"),
        CheckConstraint("kind IN ('income','expense','transfer')", name="kind_valid"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(60))
    kind: Mapped[str] = mapped_column(String(10))


class Account(Timestamps, Base):
    __tablename__ = "accounts"
    __table_args__ = (CheckConstraint("kind IN ('bank','cash','credit_card','wallet','other')", name="kind_valid"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = owner_column()
    name: Mapped[str] = mapped_column(String(100))
    kind: Mapped[str] = mapped_column(String(20), default="bank")


class ImportBatch(Base):
    """One uploaded file (or pasted block of SMS). Every imported transaction
    points back to its batch so we always know where a number came from."""

    __tablename__ = "import_batches"
    __table_args__ = (
        CheckConstraint("source_type IN ('csv','pdf','sms')", name="source_valid"),
        CheckConstraint("status IN ('processing','needs_review','completed','failed','cancelled')", name="status_valid"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = owner_column()
    account_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("accounts.id", ondelete="SET NULL"))
    source_type: Mapped[str] = mapped_column(String(10))
    original_filename: Mapped[str | None] = mapped_column(String(255))
    file_sha256: Mapped[str | None] = mapped_column(String(64), index=True)  # spots re-uploads of the same file
    file_size: Mapped[int | None] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(15), default="processing")
    rows_found: Mapped[int] = mapped_column(Integer, default=0)
    rows_imported: Mapped[int] = mapped_column(Integer, default=0)
    rows_duplicate: Mapped[int] = mapped_column(Integer, default=0)
    rows_failed: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # File-level notes for the review screen ("treated every row as money out", ...)
    warnings: Mapped[list | None] = mapped_column(JSONB)
    # Was AI used to categorise? 'used' | 'not_configured' | 'failed' | 'not_needed'
    ai_status: Mapped[str | None] = mapped_column(String(20))


class ImportError(Base):
    __tablename__ = "import_errors"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    batch_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("import_batches.id", ondelete="CASCADE"), index=True)
    row_number: Mapped[int | None] = mapped_column(Integer)
    raw_text: Mapped[str | None] = mapped_column(Text)
    message: Mapped[str] = mapped_column(String(500))


class ImportRow(Base):
    """A transaction found in an uploaded file, waiting for the user to
    review it. Nothing here counts in totals until the user confirms the
    import, which copies the ticked rows into `transactions`."""

    __tablename__ = "import_rows"
    __table_args__ = (
        CheckConstraint("amount IS NULL OR amount > 0", name="amount_positive"),
        CheckConstraint("type IS NULL OR type IN ('income','expense')", name="type_valid"),
        CheckConstraint("duplicate_kind IS NULL OR duplicate_kind IN ('exact','possible','in_file')", name="duplicate_kind_valid"),
        Index("ix_import_rows_batch_row", "batch_id", "position"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    batch_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("import_batches.id", ondelete="CASCADE"))
    user_id: Mapped[uuid.UUID] = owner_column()
    position: Mapped[int] = mapped_column(Integer)  # order in the file
    row_number: Mapped[int | None] = mapped_column(Integer)  # line (CSV), page (PDF) or message (SMS)
    raw_text: Mapped[str] = mapped_column(Text)
    occurred_on: Mapped[date | None] = mapped_column(Date)
    description: Mapped[str] = mapped_column(String(500))
    merchant: Mapped[str | None] = mapped_column(String(200))
    amount: Mapped[Decimal | None] = mapped_column(Money)
    type: Mapped[str | None] = mapped_column(String(10))
    balance_after: Mapped[Decimal | None] = mapped_column(Money)
    category_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("categories.id", ondelete="SET NULL"))
    category_source: Mapped[str | None] = mapped_column(String(10))
    category_confidence: Mapped[Decimal | None] = mapped_column(Numeric(4, 3))
    category_reason: Mapped[str | None] = mapped_column(String(300))
    problems: Mapped[list] = mapped_column(JSONB, default=list)
    duplicate_kind: Mapped[str | None] = mapped_column(String(10))
    duplicate_of_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("transactions.id", ondelete="SET NULL"))
    duplicate_note: Mapped[str | None] = mapped_column(String(300))
    include: Mapped[bool] = mapped_column(default=True)
    edited: Mapped[bool] = mapped_column(default=False)

    rule_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("categorization_rules.id", ondelete="SET NULL"))

    category: Mapped[Category | None] = relationship(lazy="joined")


class Transaction(Timestamps, Base):
    __tablename__ = "transactions"
    __table_args__ = (
        CheckConstraint("amount > 0", name="amount_positive"),  # direction is in `type`, not the sign
        CheckConstraint("type IN ('income','expense','transfer')", name="type_valid"),
        CheckConstraint("source IN ('manual','csv','pdf','sms','demo')", name="source_valid"),
        CheckConstraint(
            "category_source IS NULL OR category_source IN ('user','rule','ai','keyword')", name="category_source_valid"
        ),
        CheckConstraint(
            "category_confidence IS NULL OR (category_confidence >= 0 AND category_confidence <= 1)",
            name="confidence_valid",
        ),
        # A double-clicked "Save" sends the same request id twice; the second is ignored.
        UniqueConstraint("user_id", "client_request_id", name="uq_transactions_client_request"),
        Index("ix_transactions_user_date", "user_id", "occurred_on"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = owner_column()
    account_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("accounts.id", ondelete="SET NULL"))
    category_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("categories.id", ondelete="SET NULL"), index=True)
    type: Mapped[str] = mapped_column(String(10))
    amount: Mapped[Decimal] = mapped_column(Money)
    currency: Mapped[str] = mapped_column(String(3))
    occurred_on: Mapped[date] = mapped_column(Date)
    description: Mapped[str] = mapped_column(String(500))
    merchant: Mapped[str | None] = mapped_column(String(200))
    notes: Mapped[str | None] = mapped_column(Text)

    # Provenance: where did this transaction come from?
    source: Mapped[str] = mapped_column(String(10), default="manual")
    import_batch_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("import_batches.id", ondelete="SET NULL"), index=True
    )
    raw_text: Mapped[str | None] = mapped_column(Text)  # original statement line / SMS
    balance_after: Mapped[Decimal | None] = mapped_column(Money)  # running balance if the statement shows one
    dedupe_hash: Mapped[str | None] = mapped_column(String(64), index=True)
    client_request_id: Mapped[uuid.UUID | None] = mapped_column()

    # How the category was chosen (feeds the learning engine in phase 3)
    category_source: Mapped[str | None] = mapped_column(String(10))
    category_confidence: Mapped[Decimal | None] = mapped_column(Numeric(4, 3))
    category_reason: Mapped[str | None] = mapped_column(String(300))
    # The learned rule that chose the category (category_source == 'rule')
    rule_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("categorization_rules.id", ondelete="SET NULL", use_alter=True), index=True
    )

    category: Mapped[Category | None] = relationship(lazy="joined")


# ---------------------------------------------------------------------------
# Audit log: who did what, when. Never stores passwords or amounts.
# ---------------------------------------------------------------------------
class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), index=True)
    action: Mapped[str] = mapped_column(String(50))
    entity_type: Mapped[str | None] = mapped_column(String(50))
    entity_id: Mapped[str | None] = mapped_column(String(64))
    details: Mapped[dict | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)




# ---------------------------------------------------------------------------
# Adaptive learning (Phase 3): the user's own categorisation rules
# ---------------------------------------------------------------------------
class CategorizationRule(Timestamps, Base):
    """"Always put SWIGGY in Groceries." Created only when the user says a
    correction should be reused, never silently.

    match_type:
      merchant  the shop name CASIO reads from the description starts with `pattern`
      contains  the description contains `pattern` as whole words
    When several rules match, the winner is: higher priority, then the more
    specific (longer) pattern, then shop-name rules, then the newest."""

    __tablename__ = "categorization_rules"
    __table_args__ = (
        CheckConstraint("match_type IN ('merchant','contains')", name="match_type_valid"),
        CheckConstraint("applies_to IN ('income','expense')", name="applies_to_valid"),
        CheckConstraint("confidence >= 0 AND confidence <= 1", name="confidence_valid"),
        UniqueConstraint("user_id", "match_type", "pattern", "applies_to", name="uq_rules_user_key"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = owner_column()
    category_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("categories.id", ondelete="CASCADE"))
    match_type: Mapped[str] = mapped_column(String(10))
    pattern: Mapped[str] = mapped_column(String(100))  # already normalised: lower case, no numbers
    applies_to: Mapped[str] = mapped_column(String(10))  # money in or money out
    priority: Mapped[int] = mapped_column(Integer, default=50)  # 90 high, 50 normal, 10 low
    active: Mapped[bool] = mapped_column(default=True)
    times_applied: Mapped[int] = mapped_column(Integer, default=0)
    times_overridden: Mapped[int] = mapped_column(Integer, default=0)  # user changed a transaction this rule set
    confidence: Mapped[Decimal] = mapped_column(Numeric(4, 3), default=Decimal("0.95"))
    last_applied_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_from_transaction_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("transactions.id", ondelete="SET NULL"))

    category: Mapped[Category] = relationship(lazy="joined")


class RuleApplication(Base):
    """What a transaction's category was before a rule changed it, so
    removing or undoing the rule puts it back exactly."""

    __tablename__ = "rule_applications"

    transaction_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("transactions.id", ondelete="CASCADE"), primary_key=True)
    previous_category_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("categories.id", ondelete="SET NULL"))
    previous_source: Mapped[str | None] = mapped_column(String(10))
    previous_confidence: Mapped[Decimal | None] = mapped_column(Numeric(4, 3))
    previous_reason: Mapped[str | None] = mapped_column(String(300))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class CategoryCorrection(Base):
    """Every time the user changes a category CASIO chose. Kept even when no
    rule is made: repeated identical corrections are how CASIO notices a
    preference worth suggesting."""

    __tablename__ = "category_corrections"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = owner_column()
    transaction_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("transactions.id", ondelete="SET NULL"))
    description: Mapped[str] = mapped_column(String(500))
    merchant_key: Mapped[str | None] = mapped_column(String(200), index=True)
    tx_type: Mapped[str] = mapped_column(String(10))
    from_category_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("categories.id", ondelete="SET NULL"))
    to_category_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("categories.id", ondelete="SET NULL"))
    from_source: Mapped[str | None] = mapped_column(String(10))
    rule_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("categorization_rules.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


# ---------------------------------------------------------------------------
# Recurring payments and subscriptions (Phase 3)
# ---------------------------------------------------------------------------
class RecurringPayment(Timestamps, Base):
    """A payment CASIO saw repeating at a regular interval. Found from
    transactions (ACTUALS); the next payment date is a FORECAST."""

    __tablename__ = "recurring_payments"
    __table_args__ = (
        CheckConstraint(_FREQ_CHECK, name="frequency_valid"),
        CheckConstraint("kind IN ('subscription','bill','other')", name="kind_valid"),
        CheckConstraint("status IN ('active','cancelled','not_recurring')", name="status_valid"),
        CheckConstraint("usage IN ('unknown','using','rarely','not_using')", name="usage_valid"),
        UniqueConstraint("user_id", "merchant_key", name="uq_recurring_user_merchant"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = owner_column()
    merchant_key: Mapped[str] = mapped_column(String(200))
    name: Mapped[str] = mapped_column(String(100))
    kind: Mapped[str] = mapped_column(String(15), default="other")
    category_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("categories.id", ondelete="SET NULL"))
    frequency: Mapped[str] = mapped_column(String(12))
    amount: Mapped[Decimal] = mapped_column(Money)  # latest charge
    average_amount: Mapped[Decimal] = mapped_column(Money)
    amount_varies: Mapped[bool] = mapped_column(default=False)  # e.g. electricity
    first_paid_on: Mapped[date] = mapped_column(Date)
    last_paid_on: Mapped[date] = mapped_column(Date)
    next_expected_on: Mapped[date | None] = mapped_column(Date)
    occurrences: Mapped[int] = mapped_column(Integer)
    confidence: Mapped[Decimal] = mapped_column(Numeric(4, 3))
    # [{"date": "2026-05-06", "amount": "649.00"}], oldest first
    charges: Mapped[list] = mapped_column(JSONB, default=list)
    # [{"date": "2026-09-06", "old": "649.00", "new": "799.00"}]
    price_changes: Mapped[list] = mapped_column(JSONB, default=list)
    # Things only the user can tell us
    status: Mapped[str] = mapped_column(String(15), default="active")
    status_changed_on: Mapped[date | None] = mapped_column(Date)
    usage: Mapped[str] = mapped_column(String(10), default="unknown")
    usage_confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    name_edited: Mapped[bool] = mapped_column(default=False)
    # Added by the user, not found in transactions. Detection leaves it alone.
    manual: Mapped[bool] = mapped_column(default=False, server_default=false())

    category: Mapped[Category | None] = relationship(lazy="joined")


class RecurringAlert(Base):
    __tablename__ = "recurring_alerts"
    __table_args__ = (
        CheckConstraint(
            "kind IN ('new','price_increase','price_decrease','unusual_amount','missed','charged_after_cancel','usage_check')",
            name="kind_valid",
        ),
        UniqueConstraint("user_id", "dedupe_key", name="uq_recurring_alert_key"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = owner_column()
    recurring_payment_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("recurring_payments.id", ondelete="CASCADE"), index=True)
    kind: Mapped[str] = mapped_column(String(25))
    message: Mapped[str] = mapped_column(String(400))
    dedupe_key: Mapped[str] = mapped_column(String(200))  # the same event never alerts twice
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    dismissed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


# ---------------------------------------------------------------------------
# Planning: budgets, goals, snapshots (Phase 4)
# ---------------------------------------------------------------------------
class Budget(Timestamps, Base):
    """A monthly spending limit for one category (a PLANNED allocation)."""

    __tablename__ = "budgets"
    __table_args__ = (
        CheckConstraint("amount > 0", name="amount_positive"),
        UniqueConstraint("user_id", "category_id", name="uq_budget_user_category"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = owner_column()
    category_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("categories.id", ondelete="CASCADE"))
    amount: Mapped[Decimal] = mapped_column(Money)

    category: Mapped[Category] = relationship(lazy="joined")


GOAL_KINDS = ("emergency_fund", "purchase", "education", "travel", "home", "debt", "other")


class FinancialGoal(Timestamps, Base):
    __tablename__ = "financial_goals"
    __table_args__ = (
        CheckConstraint("target_amount > 0", name="target_positive"),
        CheckConstraint("saved_amount >= 0", name="saved_not_negative"),
        CheckConstraint("monthly_contribution IS NULL OR monthly_contribution >= 0", name="contribution_not_negative"),
        CheckConstraint("kind IN ('" + "','".join(GOAL_KINDS) + "')", name="kind_valid"),
        CheckConstraint("status IN ('active','achieved','paused')", name="status_valid"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = owner_column()
    name: Mapped[str] = mapped_column(String(100))
    kind: Mapped[str] = mapped_column(String(20), default="other")
    target_amount: Mapped[Decimal] = mapped_column(Money)
    saved_amount: Mapped[Decimal] = mapped_column(Money, default=Decimal("0"))
    target_date: Mapped[date | None] = mapped_column(Date)
    monthly_contribution: Mapped[Decimal | None] = mapped_column(Money)
    priority: Mapped[int] = mapped_column(Integer, default=2)  # 1 high, 2 normal, 3 low
    status: Mapped[str] = mapped_column(String(10), default="active")


class GoalContribution(Base):
    """Money the user says they put towards (or took out of) a goal."""

    __tablename__ = "goal_contributions"
    __table_args__ = (CheckConstraint("amount <> 0", name="amount_not_zero"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = owner_column()
    goal_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("financial_goals.id", ondelete="CASCADE"), index=True)
    amount: Mapped[Decimal] = mapped_column(Money)
    contributed_on: Mapped[date] = mapped_column(Date)
    note: Mapped[str | None] = mapped_column(String(200))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class FinancialSnapshot(Base):
    """The Living Money Model as it stood in one month, kept so changes over
    time can be compared. One per user per month, refreshed during the month."""

    __tablename__ = "financial_snapshots"
    __table_args__ = (UniqueConstraint("user_id", "month", name="uq_snapshot_user_month"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = owner_column()
    month: Mapped[date] = mapped_column(Date)  # first day of the month
    data: Mapped[dict] = mapped_column(JSONB)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


# ---------------------------------------------------------------------------
# Coaching: nudges, monthly reports, AI coach (Phase 5)
# ---------------------------------------------------------------------------
class FinancialNudge(Base):
    __tablename__ = "financial_nudges"
    __table_args__ = (
        CheckConstraint("severity IN ('info','warning','critical','good')", name="severity_valid"),
        UniqueConstraint("user_id", "dedupe_key", name="uq_nudge_user_key"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = owner_column()
    kind: Mapped[str] = mapped_column(String(30))
    severity: Mapped[str] = mapped_column(String(10))
    title: Mapped[str] = mapped_column(String(150))
    message: Mapped[str] = mapped_column(String(500))
    link: Mapped[str | None] = mapped_column(String(100))
    dedupe_key: Mapped[str] = mapped_column(String(200))
    active: Mapped[bool] = mapped_column(default=True)  # false once the condition no longer holds
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    dismissed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class MonthlyReport(Base):
    __tablename__ = "monthly_reports"
    __table_args__ = (UniqueConstraint("user_id", "month", name="uq_report_user_month"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = owner_column()
    month: Mapped[date] = mapped_column(Date)
    data: Mapped[dict] = mapped_column(JSONB)
    narrative: Mapped[str] = mapped_column(Text)
    narrative_source: Mapped[str] = mapped_column(String(10))  # 'ai' or 'template'
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class CoachMessage(Base):
    __tablename__ = "coach_messages"
    __table_args__ = (CheckConstraint("role IN ('user','assistant')", name="role_valid"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = owner_column()
    role: Mapped[str] = mapped_column(String(10))
    content: Mapped[str] = mapped_column(Text)
    # tools used, guardrail decisions, whether AI or the built-in helper answered
    meta: Mapped[dict | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
