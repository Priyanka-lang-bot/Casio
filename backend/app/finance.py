"""All money maths lives here: plain, deterministic Python with Decimal.

The AI coach (later) will call these functions as tools and explain the
results; it will never do arithmetic itself."""
from collections.abc import Iterable
from decimal import ROUND_HALF_UP, Decimal

ZERO = Decimal("0")
CENT = Decimal("0.01")

# How many times per month something happens, on average.
_PER_MONTH = {
    "weekly": Decimal(52) / Decimal(12),
    "fortnightly": Decimal(26) / Decimal(12),
    "monthly": Decimal(1),
    "quarterly": Decimal(1) / Decimal(3),
    "yearly": Decimal(1) / Decimal(12),
}


def money(value: Decimal) -> Decimal:
    return value.quantize(CENT, rounding=ROUND_HALF_UP)


def monthly_amount(amount: Decimal, frequency: str) -> Decimal:
    """Convert e.g. ₹12,000 per year to ₹1,000 per month (unrounded)."""
    return amount * _PER_MONTH[frequency]


def total(values: Iterable[Decimal | None]) -> Decimal:
    return sum((v for v in values if v is not None), ZERO)


def profile_summary(incomes, expenses, assets, liabilities) -> dict:
    """The user's plan as they described it. Every figure is an ESTIMATE
    entered by the user, not money we have seen move."""
    monthly_income = total(monthly_amount(i.amount, i.frequency) for i in incomes)
    fixed = total(monthly_amount(e.amount, e.frequency) for e in expenses if e.kind == "fixed")
    variable = total(monthly_amount(e.amount, e.frequency) for e in expenses if e.kind == "variable")
    debt_payments = total(l.monthly_payment for l in liabilities)
    monthly_spend = fixed + variable + debt_payments

    total_assets = total(a.value for a in assets)
    total_liabilities = total(l.balance for l in liabilities)
    emergency_fund = total(a.value for a in assets if a.kind == "emergency_fund")
    savings = total(a.value for a in assets if a.kind in ("savings", "emergency_fund"))

    return {
        "basis": "user_estimate",
        "monthly_income": money(monthly_income),
        "monthly_fixed_expenses": money(fixed),
        "monthly_variable_expenses": money(variable),
        "monthly_debt_payments": money(debt_payments),
        "monthly_total_spending": money(monthly_spend),
        # Monthly Surplus = Income - (Fixed + Variable + Debt payments)
        "monthly_surplus": money(monthly_income - monthly_spend),
        "total_assets": money(total_assets),
        "total_liabilities": money(total_liabilities),
        # Net Worth = Total Assets - Total Liabilities
        "net_worth": money(total_assets - total_liabilities),
        "savings": money(savings),
        "emergency_fund": money(emergency_fund),
        # How many months the emergency fund would cover current spending.
        "emergency_fund_months": (
            (emergency_fund / monthly_spend).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP) if monthly_spend > 0 else None
        ),
        "is_empty": not (incomes or expenses or assets or liabilities),
    }


def to_json(value):
    """Prepare a result for the API: Decimals become strings like "1500.25"
    so no precision is lost to floating point on the way to the browser."""
    from pydantic import BaseModel

    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    if isinstance(value, dict):
        return {k: to_json(v) for k, v in value.items()}
    if isinstance(value, list | tuple):
        return [to_json(v) for v in value]
    return value
