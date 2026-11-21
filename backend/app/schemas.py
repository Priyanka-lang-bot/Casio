import re
import uuid

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator
from pydantic_core import PydanticCustomError


def _check_password(value: str) -> str:
    if len(value) < 8:
        raise ValueError("Password must be at least 8 characters long.")
    if len(value) > 128:
        raise ValueError("Password must be 128 characters or fewer.")
    if not re.search(r"[A-Za-z]", value) or not re.search(r"\d", value):
        raise ValueError("Password must include at least one letter and one number.")
    return value


class RegisterIn(BaseModel):
    full_name: str = Field(max_length=100)
    email: EmailStr
    password: str
    confirm_password: str

    @field_validator("full_name")
    @classmethod
    def name_not_blank(cls, v: str) -> str:
        v = " ".join(v.split())
        if not v:
            raise ValueError("Please enter your full name.")
        return v

    @field_validator("email")
    @classmethod
    def normalise_email(cls, v: str) -> str:
        return v.strip().lower()

    @field_validator("password")
    @classmethod
    def strong_password(cls, v: str) -> str:
        return _check_password(v)

    @model_validator(mode="after")
    def passwords_match(self):
        if self.password != self.confirm_password:
            raise PydanticCustomError("password_mismatch", "The two passwords don't match.")
        return self


class LoginIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)
    remember_me: bool = False

    @field_validator("email")
    @classmethod
    def normalise_email(cls, v: str) -> str:
        return v.strip().lower()


class ForgotPasswordIn(BaseModel):
    email: EmailStr

    @field_validator("email")
    @classmethod
    def normalise_email(cls, v: str) -> str:
        return v.strip().lower()


class ResetPasswordIn(BaseModel):
    token: str = Field(min_length=10, max_length=200)
    password: str
    confirm_password: str

    @field_validator("password")
    @classmethod
    def strong_password(cls, v: str) -> str:
        return _check_password(v)

    @model_validator(mode="after")
    def passwords_match(self):
        if self.password != self.confirm_password:
            raise PydanticCustomError("password_mismatch", "The two passwords don't match.")
        return self


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    full_name: str
    is_demo: bool = False


class MessageOut(BaseModel):
    message: str


# ---------------------------------------------------------------------------
# Financial data
# ---------------------------------------------------------------------------
import datetime as dt  # noqa: E402
from decimal import Decimal  # noqa: E402
from typing import Annotated, Literal  # noqa: E402

# Money must be positive, at most 2 decimal places, below one trillion.
PositiveMoney = Annotated[Decimal, Field(gt=0, max_digits=14, decimal_places=2)]
NonNegativeMoney = Annotated[Decimal, Field(ge=0, max_digits=14, decimal_places=2)]
Name = Annotated[str, Field(min_length=1, max_length=100)]
Frequency = Literal["weekly", "fortnightly", "monthly", "quarterly", "yearly"]
AssetKind = Literal["cash", "bank_account", "savings", "emergency_fund", "investment", "property", "vehicle", "other"]
LiabilityKind = Literal["credit_card", "personal_loan", "home_loan", "vehicle_loan", "education_loan", "other"]


class _Clean(BaseModel):
    @field_validator("name", check_fields=False)
    @classmethod
    def strip_name(cls, v: str) -> str:
        v = " ".join(v.split())
        if not v:
            raise ValueError("Please enter a name.")
        return v


class IncomeSourceIn(_Clean):
    name: Name
    amount: PositiveMoney
    frequency: Frequency = "monthly"


class ExpenseItemIn(_Clean):
    name: Name
    amount: PositiveMoney
    frequency: Frequency = "monthly"
    kind: Literal["fixed", "variable"] = "fixed"


class AssetIn(_Clean):
    name: Name
    kind: AssetKind
    value: NonNegativeMoney


class LiabilityIn(_Clean):
    name: Name
    kind: LiabilityKind
    balance: NonNegativeMoney
    monthly_payment: NonNegativeMoney | None = None
    interest_rate: Annotated[Decimal, Field(ge=0, le=100, max_digits=5, decimal_places=2)] | None = None


class _Out(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID


class IncomeSourceOut(IncomeSourceIn, _Out):
    pass


class ExpenseItemOut(ExpenseItemIn, _Out):
    pass


class AssetOut(AssetIn, _Out):
    pass


class LiabilityOut(LiabilityIn, _Out):
    pass


class ProfileOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    currency: str
    country: str | None


class ProfileUpdate(BaseModel):
    currency: Annotated[str, Field(pattern=r"^[A-Z]{3}$")] | None = None
    country: Annotated[str, Field(pattern=r"^[A-Z]{2}$")] | None = None


class CategoryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    name: str
    kind: str
    is_custom: bool = False


class TransactionIn(BaseModel):
    type: Literal["income", "expense"]
    amount: PositiveMoney
    occurred_on: dt.date
    description: Annotated[str, Field(min_length=1, max_length=500)]
    category_id: uuid.UUID | None = None
    notes: Annotated[str, Field(max_length=2000)] | None = None
    # Sent by the app with every new transaction; repeating it doesn't create a duplicate.
    client_request_id: uuid.UUID | None = None

    @field_validator("description")
    @classmethod
    def strip_description(cls, v: str) -> str:
        v = " ".join(v.split())
        if not v:
            raise ValueError("Please describe the transaction.")
        return v

    @field_validator("occurred_on")
    @classmethod
    def not_far_future(cls, v: dt.date) -> dt.date:
        if v > dt.date.today() + dt.timedelta(days=1):
            raise ValueError("The date can't be in the future.")
        if v.year < 1970:
            raise ValueError("Please enter a valid date.")
        return v


class TransactionUpdate(TransactionIn):
    client_request_id: None = None


class TransactionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    type: str
    amount: Decimal
    currency: str
    occurred_on: dt.date
    description: str
    notes: str | None
    category_id: uuid.UUID | None
    category_name: str | None = None
    source: str
    import_batch_id: uuid.UUID | None
    category_source: str | None
    category_confidence: float | None = None
    category_reason: str | None = None
    rule_id: uuid.UUID | None = None
    merchant: str | None = None


class TransactionPage(BaseModel):
    items: list[TransactionOut]
    total: int


# ---------------------------------------------------------------------------
# Smart import
# ---------------------------------------------------------------------------
class ImportErrorOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    row_number: int | None
    raw_text: str | None
    message: str


class ImportRowOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    position: int
    row_number: int | None
    raw_text: str
    occurred_on: dt.date | None
    description: str
    merchant: str | None
    amount: Decimal | None
    type: str | None
    balance_after: Decimal | None
    category_id: uuid.UUID | None
    category_name: str | None = None
    category_source: str | None
    category_confidence: float | None
    category_reason: str | None
    needs_check: bool = False  # low confidence: "please check this category"
    rule_id: uuid.UUID | None = None
    problems: list[str]
    duplicate_kind: str | None
    duplicate_note: str | None
    include: bool
    edited: bool


class ImportBatchOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    source_type: str
    original_filename: str | None
    status: str
    rows_found: int
    rows_imported: int
    rows_duplicate: int
    rows_failed: int
    warnings: list[str] | None
    ai_status: str | None
    created_at: dt.datetime
    completed_at: dt.datetime | None


class ImportDetailOut(ImportBatchOut):
    errors: list[ImportErrorOut] = []
    rows: list[ImportRowOut] = []


class ImportRowUpdate(BaseModel):
    """Any field the user changed on the review screen. Only fields that are
    sent are changed."""

    occurred_on: dt.date | None = None
    description: Annotated[str, Field(min_length=1, max_length=500)] | None = None
    amount: PositiveMoney | None = None
    type: Literal["income", "expense"] | None = None
    category_id: uuid.UUID | None = None
    include: bool | None = None
    # When the category changes: also change rows in this import with the
    # same shop/description that the user hasn't changed themselves.
    apply_to_similar: bool = False

    @field_validator("description")
    @classmethod
    def strip_description(cls, v: str | None) -> str | None:
        if v is None:
            return v
        v = " ".join(v.split())
        if not v:
            raise ValueError("Please describe the transaction.")
        return v

    @field_validator("occurred_on")
    @classmethod
    def sensible_date(cls, v: dt.date | None) -> dt.date | None:
        if v is not None and (v.year < 1970 or v > dt.date.today() + dt.timedelta(days=1)):
            raise ValueError("Please enter a real date that isn't in the future.")
        return v


class ImportBulkInclude(BaseModel):
    include: bool
    which: Literal["all", "duplicates", "ready"] = "all"


# ---------------------------------------------------------------------------
# Learned rules
# ---------------------------------------------------------------------------
Priority = Literal["high", "normal", "low"]


class RulePreviewIn(BaseModel):
    """Exactly one of transaction_id / import_row_id: the item the user just changed."""

    transaction_id: uuid.UUID | None = None
    import_row_id: uuid.UUID | None = None
    category_id: uuid.UUID
    match_type: Literal["merchant", "contains"] | None = None
    pattern: Annotated[str, Field(max_length=100)] | None = None

    @model_validator(mode="after")
    def one_item(self):
        if (self.transaction_id is None) == (self.import_row_id is None):
            raise ValueError("Send transaction_id or import_row_id.")
        return self


class RuleIn(BaseModel):
    category_id: uuid.UUID
    match_type: Literal["merchant", "contains"]
    pattern: Annotated[str, Field(min_length=1, max_length=100)]
    applies_to: Literal["income", "expense"] = "expense"
    priority: Priority = "normal"
    apply_to_past: bool = True
    source_transaction_id: uuid.UUID | None = None


class RuleUpdate(BaseModel):
    category_id: uuid.UUID | None = None
    match_type: Literal["merchant", "contains"] | None = None
    pattern: Annotated[str, Field(min_length=1, max_length=100)] | None = None
    priority: Priority | None = None
    active: bool | None = None


class RuleConflictOut(BaseModel):
    rule_id: uuid.UUID
    pattern: str
    match_type: str
    category_name: str
    this_wins: bool
    transactions: int


class RuleOut(BaseModel):
    id: uuid.UUID
    category_id: uuid.UUID
    category_name: str
    match_type: str
    pattern: str
    applies_to: str
    priority: Priority
    active: bool
    times_applied: int
    times_overridden: int
    confidence: float
    weak: bool
    currently_applied: int = 0
    last_applied_at: dt.datetime | None
    created_at: dt.datetime
    conflicts: list[RuleConflictOut] = []


class RuleSaveOut(BaseModel):
    rule: RuleOut
    changed_transactions: int
    changed_import_rows: int
    replaced: bool = False


class CorrectionOut(BaseModel):
    id: uuid.UUID
    description: str
    from_category: str | None
    to_category: str | None
    from_source: str | None
    made_rule: bool
    created_at: dt.datetime


# ---------------------------------------------------------------------------
# Recurring payments and subscriptions
# ---------------------------------------------------------------------------
class RecurringOut(BaseModel):
    id: uuid.UUID
    name: str
    kind: str
    category_name: str | None
    frequency: str
    amount: Decimal
    average_amount: Decimal
    amount_varies: bool
    monthly_cost: Decimal
    yearly_cost: Decimal
    first_paid_on: dt.date
    last_paid_on: dt.date
    next_expected_on: dt.date | None  # a forecast
    occurrences: int
    confidence: float
    charges: list[dict]
    price_changes: list[dict]
    status: str
    state: str  # active | overdue | cancelled | not_recurring
    usage: str
    usage_confirmed_at: dt.datetime | None
    explanation: str


class RecurringAlertOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    recurring_payment_id: uuid.UUID
    kind: str
    message: str
    created_at: dt.datetime


class RecurringSummary(BaseModel):
    basis: Literal["actual"] = "actual"
    active_count: int
    monthly_total: Decimal
    yearly_total: Decimal
    subscriptions_monthly: Decimal
    bills_monthly: Decimal
    not_using_yearly: Decimal  # could be saved if the user cancels what they don't use
    unknown_usage_count: int


class RecurringPage(BaseModel):
    as_of: dt.date
    currency: str
    summary: RecurringSummary
    items: list[RecurringOut]
    alerts: list[RecurringAlertOut]


class RecurringUpdate(BaseModel):
    name: Annotated[str, Field(min_length=1, max_length=100)] | None = None
    kind: Literal["subscription", "bill", "other"] | None = None
    status: Literal["active", "cancelled", "not_recurring"] | None = None
    usage: Literal["unknown", "using", "rarely", "not_using"] | None = None
