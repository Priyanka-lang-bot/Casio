"""Automatic categorisation, step 1: keyword rules (always available).

Each rule says "descriptions containing these words are probably this
category", with a confidence: well-known merchant names are very likely
right (0.9), general words less so (0.7). Anything unmatched goes to
"Other" with low confidence and is flagged for the user to check.

Rows the rules aren't sure about are then sent to the AI model, if one is
configured (see app/ai.py). Phase 3 adds the user's own learned rules,
which will run before these."""
import re
from dataclasses import dataclass

REVIEW_BELOW = 0.6  # confidence under this is flagged "please check"


@dataclass
class Guess:
    category: str
    confidence: float
    source: str  # "keyword" | "ai"
    reason: str


def _rx(words: str, whole_word: bool = False) -> re.Pattern:
    """Brand names match at the start of a word (bank text often glues
    words together: "AMAZONPAY"); short generic words must be whole words."""
    return re.compile(r"\b(" + words + r")" + (r"\b" if whole_word else ""), re.I)


# (category, pattern, confidence). First match wins, so specific merchants
# come before generic words.
EXPENSE_RULES: list[tuple[str, re.Pattern, float]] = [
    ("Subscriptions", _rx(r"netflix|spotify|prime video|amazon prime|hotstar|disney|youtube premium|youtube music|apple\.com|icloud|google one|google storage|jiocinema|sonyliv|zee5|audible|kindle unlimited|chatgpt|openai|adobe|microsoft 365|office 365|linkedin premium|canva|notion|dropbox"), 0.92),
    ("Food and Dining", _rx(r"swiggy|zomato|eatsure|dominos|domino's|pizza hut|mcdonald|kfc|burger king|starbucks|cafe coffee day|ccd|subway|haldiram|barbeque nation|chaayos|blue tokri|faasos|box8|behrouz"), 0.9),
    ("Groceries", _rx(r"bigbasket|big basket|blinkit|grofers|zepto|instamart|dmart|d-mart|jiomart|reliance fresh|more retail|spencer|nature's basket|natures basket|star bazaar|ratnadeep|country delight|milkbasket|licious|freshtohome"), 0.9),
    ("Transportation", _rx(r"uber|ola cabs|olacabs|\bola\b|rapido|blusmart|metro rail|dmrc|bmrcl|irctc|indian oil|iocl|hpcl|bharat petroleum|bpcl|shell|fastag|petrol|diesel|fuel|parking|namma yatri", True), 0.88),
    ("Travel", _rx(r"makemytrip|goibibo|cleartrip|yatra|easemytrip|indigo|air india|vistara|akasa|spicejet|oyo|airbnb|booking\.com|agoda|taj hotels|marriott|redbus|ixigo"), 0.9),
    ("Shopping", _rx(r"amazon|flipkart|myntra|ajio|meesho|nykaa|tata cliq|croma|reliance digital|decathlon|ikea|lifestyle|westside|pantaloons|h&m|zara|uniqlo|shoppers stop|lenskart|firstcry|snapdeal"), 0.85),
    ("Utilities", _rx(r"electricity|bescom|tata power|adani electricity|msedcl|bses|torrent power|water bill|gas bill|indane|hp gas|bharat gas|mahanagar gas|airtel|jio|vodafone|\bvi\b|bsnl|act fibernet|hathway|broadband|recharge|dth|tata play|dish tv", True), 0.88),
    ("Housing and Rent", _rx(r"rent|nobroker|housing\.com|maintenance|society|landlord|nestaway|magicbricks", True), 0.82),
    ("Healthcare", _rx(r"apollo|pharmeasy|1mg|tata 1mg|netmeds|medplus|practo|hospital|clinic|pharmacy|chemist|medical|diagnostic|lab test|thyrocare|dr lal|cult\.fit|cultfit|health", True), 0.88),
    ("Education", _rx(r"udemy|coursera|byju|unacademy|upgrad|vedantu|simplilearn|school fee|college|university|tuition|exam fee|books|edx|skillshare", True), 0.88),
    ("Entertainment", _rx(r"bookmyshow|pvr|inox|cinepolis|paytm insider|steam|playstation|xbox|gaming|concert|movie", True), 0.88),
    ("Transfers", _rx(r"self transfer|own account|to self|credit card payment|cc payment|card payment|atm|cash withdrawal|cash wdl|nwd|mutual fund|sip|zerodha|groww|upstox|ppf|recurring deposit|fixed deposit", True), 0.8),
    # generic words, less certain
    ("Food and Dining", _rx(r"restaurant|cafe|coffee|dhaba|bakery|food|dining|eatery|biryani|kitchen", True), 0.7),
    ("Groceries", _rx(r"grocery|grocer|supermarket|kirana|vegetable|fruits|mart", True), 0.7),
    ("Shopping", _rx(r"store|shop|retail|fashion|electronics", True), 0.6),
    ("Housing and Rent", _rx(r"emi|home loan|loan", True), 0.55),
]

INCOME_RULES: list[tuple[str, re.Pattern, float]] = [
    ("Salary and Income", _rx(r"salary|sal cr|payroll|wages|stipend|bonus|incentive|freelance|consulting|invoice", True), 0.9),
    ("Transfers", _rx(r"self transfer|own account|from self|reversal|cash deposit", True), 0.75),
    ("Other Income", _rx(r"refund|cashback|interest|int\.pd|int pd|dividend|reward|rent received", True), 0.85),
]


def keyword_guess(description: str, merchant: str | None, tx_type: str | None) -> Guess:
    text = f"{description} {merchant or ''}"
    rules = INCOME_RULES if tx_type == "income" else EXPENSE_RULES
    for category, pattern, confidence in rules:
        m = pattern.search(text)
        if m:
            return Guess(category, confidence, "keyword", f"Description mentions “{m.group(1).strip()}”.")
    if tx_type == "income":
        # Money that came from a company name with NEFT/IMPS is often salary,
        # but we can't be sure, so it's flagged.
        return Guess("Other Income", 0.4, "keyword", "No clear match. Please check.")
    if re.search(r"\b(upi|imps|neft)\b", text, re.I):
        return Guess("Other", 0.35, "keyword", "Looks like a payment to a person or shop we don't recognise.")
    return Guess("Other", 0.25, "keyword", "No clear match. Please check.")
