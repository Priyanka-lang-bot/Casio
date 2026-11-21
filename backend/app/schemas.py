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


class TransactionPage(BaseModel):
    items: list[TransactionOut]
    total: int
