"""Responsible-AI guardrails for the coach.

CASIO helps with budgeting, saving and planning. It must never recommend
specific securities (named stocks, funds, crypto coins, IPOs) or tell
someone to buy, sell or hold one. General education ("what is an index
fund?", "what does diversification mean?") is fine.

Two checks, both deterministic so they work with or without AI:
1. `asks_for_security_pick(question)` before anything is sent to a model.
2. `recommends_security(answer)` on every answer before the user sees it.
The coach's system prompt says the same thing, but these checks don't rely
on the model following it."""
import re

_INSTRUMENT = (
    r"(stocks?|shares?|equit(y|ies)|mutual ?funds?|funds?|etfs?|ipos?|crypto(currency|currencies)?|coins?|tokens?|"
    r"bitcoin|btc|ethereum|eth|dogecoin|solana|nft|options?|futures?|f&o|smallcaps?|midcaps?|penny stocks?|bonds?)"
)
_PICK = r"(which|what|best|top|good|recommend\w*|suggest\w*|tips?|pick)"
_ACT = r"(buy|sell|invest|put (my )?money|hold|purchase|trade|get into|park)"

# Company names are ambiguous (an "HDFC account", a "Reliance Jio bill"), so
# they only count next to a word like "shares". Coins are always investments.
_COMPANIES = (
    r"reliance|tcs|infosys|wipro|hdfc|icici|sbi|adani|tata motors|tata steel|itc|bajaj|kotak|zomato|paytm|nykaa|"
    r"lic|irctc|yes bank|vodafone idea|tesla|apple|nvidia|amazon|google|microsoft|parag parikh|axis|mirae|nippon"
)
_COINS = r"bitcoin|btc|ethereum|dogecoin|solana|shiba|xrp|bnb|cardano"
# Savings pots that are not investments.
_SAFE = re.compile(r"\b(emergency|sinking|goal|rainy[- ]day|holiday|travel|house|laptop)\s+funds?\b", re.I)

_Q_PATTERNS = [
    re.compile(rf"\b{_PICK}\b.{{0,40}}\b{_INSTRUMENT}\b.{{0,40}}\b{_ACT}\b", re.I),
    re.compile(rf"\b{_PICK}\b.{{0,40}}\b{_ACT}\b.{{0,50}}\b{_INSTRUMENT}\b", re.I),
    re.compile(rf"\b(best|top|recommend\w*|suggest\w*)\b.{{0,20}}\b{_INSTRUMENT}\b", re.I),
    re.compile(rf"\b({_COMPANIES})\b.{{0,15}}\b(shares?|stocks?|equity|ipo|mutual fund|fund)\b", re.I),
    re.compile(rf"\b({_ACT}|which|best|top|good|recommend\w*|suggest\w*|should i|worth)\b.{{0,30}}\b({_COINS})\b", re.I),
    re.compile(rf"\b({_COINS})\b.{{0,30}}\b({_ACT}|investment|price|go up|worth)\b", re.I),
    re.compile(r"\b(price target|target price|multibagger|stock tips?|intraday tips?)\b", re.I),
]

_A_PATTERNS = [
    # "buy Infosys shares", "invest in the XYZ Bluechip Fund", "sell your TCS stock"
    re.compile(rf"\b(buy|sell|invest in|put .{{0,15}} into|hold on to|purchase)\b\s+(the\s+|some\s+|your\s+)?([A-Z][\w&.-]+\s){{1,4}}({_INSTRUMENT})\b"),
    re.compile(rf"\b(buy|sell|invest in|purchase)\b\s+(some\s+)?({_COINS})\b", re.I),
    re.compile(r"\b(NSE|BSE|NASDAQ|NYSE)\s*:\s*[A-Z]{2,}\b"),
    re.compile(r"\bI (would )?recommend (buying|investing in|selling)\b", re.I),
]

REFUSAL = (
    "I can't recommend specific stocks, funds, crypto or other investments, or say whether to buy, sell or hold one. "
    "That needs a licensed adviser who knows your full situation (in India, a SEBI-registered investment adviser).\n\n"
    "What I can do: help you work out how much you can safely set aside each month, check that your emergency fund "
    "is in place first, and explain general ideas like diversification, risk and fees in plain language. "
    "Want me to look at how much room your budget has for long-term saving?"
)


def asks_for_security_pick(text: str) -> bool:
    text = _SAFE.sub(" savings pot ", text or "")
    return any(p.search(text) for p in _Q_PATTERNS)


def recommends_security(text: str) -> bool:
    return any(p.search(text or "") for p in _A_PATTERNS)
