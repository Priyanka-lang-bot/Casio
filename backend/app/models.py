"""Database tables for milestone 1 (authentication).

Financial tables (accounts, transactions, budgets, ...) come in later
milestones and will all hang off users.id with a foreign key."""
import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, func
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


class ImportError(Base):
    __tablename__ = "import_errors"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    batch_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("import_batches.id", ondelete="CASCADE"), index=True)
    row_number: Mapped[int | None] = mapped_column(Integer)
    raw_text: Mapped[str | None] = mapped_column(Text)
    message: Mapped[str] = mapped_column(String(500))


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


