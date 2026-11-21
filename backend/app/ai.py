"""The boundary between CASIO and the AI model.

Everything AI-related goes through this file, so the rest of the app never
depends on it. If no API key is configured, or the model is unreachable,
every function returns "no answer" and CASIO falls back to its own rules.

What the AI is allowed to do here: pick a category for a transaction
description and say how sure it is. What it is never given: names,
account numbers, card numbers, UPI ids or amounts. What it never does:
create or change dates or amounts."""
import json
import logging
from dataclasses import dataclass

from app.config import get_settings

log = logging.getLogger("casio.ai")
BATCH_SIZE = 40


@dataclass
class AiCategory:
    category: str
    confidence: float
    reason: str


def ai_status() -> str:
    """'ready' or 'not_configured'. Shown to the user so they know whether
    AI was used."""
    return "ready" if get_settings().anthropic_api_key else "not_configured"


def _client():
    import anthropic  # imported lazily: the app works without the package configured

    s = get_settings()
    return anthropic.Anthropic(api_key=s.anthropic_api_key, timeout=45.0, max_retries=1)


SYSTEM = (
    "You categorise personal bank transactions for a budgeting app used in India. "
    "For each item, choose exactly one category from the allowed list that fits the item's "
    "direction (money in or money out). Use what the description says, including Indian merchant "
    "names, UPI and NEFT conventions. If the description is too vague to know, choose 'Other' "
    "(money out) or 'Other Income' (money in) and give a low confidence. Confidence is your "
    "probability from 0 to 1 that the category is right. The reason is one short plain-English "
    "sentence a non-expert would understand. Never invent details that are not in the description."
)


def classify(items: list[dict], categories: list[dict], client=None) -> dict[int, AiCategory]:
    """items: [{"id": int, "description": str, "direction": "money in"|"money out"}]
    categories: [{"name": str, "kind": "income"|"expense"|"transfer"}]
    Returns {id: AiCategory} for the items the model answered. Never raises."""
    if not items or (client is None and ai_status() != "ready"):
        return {}
    names = sorted({c["name"] for c in categories})
    schema = {
        "type": "object",
        "properties": {
            "results": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "integer"},
                        "category": {"type": "string", "enum": names},
                        "confidence": {"type": "number"},
                        "reason": {"type": "string"},
                    },
                    "required": ["id", "category", "confidence", "reason"],
                    "additionalProperties": False,
                },
            }
        },
        "required": ["results"],
        "additionalProperties": False,
    }
    allowed = "\n".join(f"- {c['name']} ({'money in' if c['kind'] == 'income' else 'money out' if c['kind'] == 'expense' else 'either'})" for c in categories)
    out: dict[int, AiCategory] = {}
    try:
        client = client or _client()
        model = get_settings().ai_model
        for start in range(0, len(items), BATCH_SIZE):
            chunk = items[start : start + BATCH_SIZE]
            response = client.beta.messages.create(
                model=model,
                max_tokens=8000,
                system=SYSTEM,
                messages=[{"role": "user", "content": f"Allowed categories:\n{allowed}\n\nTransactions (JSON):\n{json.dumps(chunk, ensure_ascii=False)}"}],
                output_config={"effort": "low", "format": {"type": "json_schema", "schema": schema}},
                betas=["server-side-fallback-2026-07-01"],
                fallbacks="default",
            )
            if response.stop_reason in ("refusal", "max_tokens"):
                log.warning("AI categorisation stopped early (%s); using keyword rules for this batch", response.stop_reason)
                continue
            text = next((b.text for b in response.content if b.type == "text"), "")
            for r in json.loads(text).get("results", []):
                if r.get("category") in names and isinstance(r.get("id"), int):
                    conf = max(0.0, min(0.95, float(r.get("confidence", 0))))
                    out[r["id"]] = AiCategory(r["category"], conf, str(r.get("reason", ""))[:280])
    except Exception as exc:  # network, auth, parsing: the import must still work
        log.warning("AI categorisation unavailable, using keyword rules: %s", exc.__class__.__name__)
    return out
