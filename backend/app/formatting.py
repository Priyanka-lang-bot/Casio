"""Money as text for messages (alerts, explanations). The browser formats
numbers itself; this is only for sentences the backend writes."""
from decimal import ROUND_HALF_UP, Decimal

SYMBOLS = {"INR": "₹", "USD": "$", "EUR": "€", "GBP": "£"}


def fmt_money(amount: Decimal, currency: str = "INR") -> str:
    """Decimal('123456.5') -> '₹1,23,456.50'; whole amounts drop '.00'."""
    amount = Decimal(amount).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    sign = "-" if amount < 0 else ""
    whole, cents = f"{abs(amount):.2f}".split(".")
    if currency == "INR" and len(whole) > 3:  # Indian grouping: 1,23,456
        head, tail = whole[:-3], whole[-3:]
        parts = []
        while len(head) > 2:
            parts.insert(0, head[-2:])
            head = head[:-2]
        if head:
            parts.insert(0, head)
        whole = ",".join(parts + [tail])
    else:
        whole = f"{int(whole):,}"
    symbol = SYMBOLS.get(currency, currency + " ")
    return f"{sign}{symbol}{whole}" + ("" if cents == "00" else f".{cents}")
