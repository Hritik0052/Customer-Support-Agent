"""
Turn a model's raw text reply into a validated dict.

Free-tier models are unreliable about "return only JSON". In practice they wrap
the object in markdown fences, prepend "Here is the JSON:", add a trailing
explanation, emit trailing commas, use single quotes, invent category names, or
return confidence as "85%" instead of 0.85. Every one of those is handled here
rather than being allowed to reach the database.
"""

import json
import re

from ai.exceptions import ParseError
from ai.prompts.classifier import CATEGORIES, PRIORITIES, SENTIMENTS

REQUIRED_KEYS = ["category", "priority", "sentiment", "summary", "confidence", "suggested_reply"]

DEFAULT_CATEGORY = "general"
DEFAULT_PRIORITY = "medium"
DEFAULT_SENTIMENT = "neutral"

# Words the models reach for that are not in our enums.
CATEGORY_ALIASES = {
    "billing_issue": "billing", "payment": "billing", "invoice": "billing",
    "refund": "billing", "subscription": "billing", "pricing": "billing",
    "bug_report": "bug", "defect": "bug", "error": "bug", "broken": "bug",
    "issue": "bug", "problem": "bug",
    "feature": "feature_request", "feature request": "feature_request",
    "enhancement": "feature_request", "request": "feature_request",
    "suggestion": "feature_request", "improvement": "feature_request",
    "tech": "technical", "technical_support": "technical", "support": "technical",
    "integration": "technical", "api": "technical", "setup": "technical",
    "how_to": "technical", "configuration": "technical",
    "login": "account", "auth": "account", "authentication": "account",
    "password": "account", "profile": "account", "access": "account",
    "other": "general", "misc": "general", "miscellaneous": "general",
    "question": "general", "inquiry": "general", "feedback": "general",
}

PRIORITY_ALIASES = {
    "critical": "urgent", "p0": "urgent", "highest": "urgent",
    "blocker": "urgent", "emergency": "urgent", "severe": "urgent",
    "p1": "high", "important": "high", "major": "high",
    "p2": "medium", "normal": "medium", "moderate": "medium", "standard": "medium",
    "p3": "low", "minor": "low", "lowest": "low", "trivial": "low", "cosmetic": "low",
}

SENTIMENT_ALIASES = {
    "happy": "positive", "satisfied": "positive", "pleased": "positive",
    "grateful": "positive", "good": "positive",
    "angry": "negative", "frustrated": "negative", "upset": "negative",
    "unhappy": "negative", "dissatisfied": "negative", "bad": "negative",
    "mixed": "neutral", "calm": "neutral", "informational": "neutral",
    "factual": "neutral", "ok": "neutral", "okay": "neutral",
}


def parse_classification(raw_text):
    """
    Parse and validate a classification response.

    Returns a dict with exactly REQUIRED_KEYS, all values valid.
    Raises ParseError (carrying the raw text) if no usable JSON is present.
    """
    if not raw_text or not raw_text.strip():
        raise ParseError("Model returned an empty response.", raw_text or "")

    data = _extract_json(raw_text)

    missing = [k for k in REQUIRED_KEYS if k not in data]
    if missing:
        # Summary and reply carry the real value — without them there is
        # nothing worth showing, so treat their absence as a hard failure.
        if "summary" in missing or "suggested_reply" in missing:
            raise ParseError(f"Response missing required keys: {missing}", raw_text)

    return {
        "category": _coerce_choice(data.get("category"), CATEGORIES, CATEGORY_ALIASES, DEFAULT_CATEGORY),
        "priority": _coerce_choice(data.get("priority"), PRIORITIES, PRIORITY_ALIASES, DEFAULT_PRIORITY),
        "sentiment": _coerce_choice(data.get("sentiment"), SENTIMENTS, SENTIMENT_ALIASES, DEFAULT_SENTIMENT),
        "summary": _coerce_text(data.get("summary"), max_length=1000),
        "suggested_reply": _coerce_text(data.get("suggested_reply"), max_length=3000),
        "confidence": _coerce_confidence(data.get("confidence")),
    }


# ---------------------------------------------------------------------------
# JSON extraction
# ---------------------------------------------------------------------------

def _extract_json(text):
    """Try progressively more forgiving strategies to get a dict out of `text`."""
    candidates = []

    cleaned = _strip_fences(text).strip()
    candidates.append(cleaned)

    block = _first_balanced_object(cleaned)
    if block and block != cleaned:
        candidates.append(block)

    for candidate in list(candidates):
        repaired = _repair(candidate)
        if repaired != candidate:
            candidates.append(repaired)

    for candidate in candidates:
        if not candidate:
            continue
        try:
            data = json.loads(candidate)
        except (json.JSONDecodeError, ValueError):
            continue
        if isinstance(data, dict):
            return data
        # A model occasionally wraps the object in a single-element list.
        if isinstance(data, list) and data and isinstance(data[0], dict):
            return data[0]

    raise ParseError("No valid JSON object found in the response.", text)


def _strip_fences(text):
    """Remove markdown code fences and any prose around them."""
    fence = re.search(r"```(?:json|JSON)?\s*(.*?)```", text, re.DOTALL)
    if fence:
        return fence.group(1)

    # An unterminated fence — common when the model hits the token limit.
    open_fence = re.search(r"```(?:json|JSON)?\s*(.*)", text, re.DOTALL)
    if open_fence:
        return open_fence.group(1)

    return text


def _first_balanced_object(text):
    """
    Return the first brace-balanced {...} block, ignoring braces inside strings.

    A plain regex cannot do this correctly: a JSON string value containing a
    brace would end the match early.
    """
    start = text.find("{")
    if start == -1:
        return None

    depth = 0
    in_string = False
    escaped = False

    for i in range(start, len(text)):
        char = text[i]

        if escaped:
            escaped = False
            continue
        if char == "\\":
            escaped = True
            continue
        if char == '"':
            in_string = not in_string
            continue
        if in_string:
            continue

        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return text[start:i + 1]

    return None


def _repair(text):
    """Fix the malformations that show up most often in free-model output."""
    repaired = text

    # Trailing commas before a closing brace or bracket.
    repaired = re.sub(r",(\s*[}\]])", r"\1", repaired)

    # Python literals.
    repaired = re.sub(r"\bTrue\b", "true", repaired)
    repaired = re.sub(r"\bFalse\b", "false", repaired)
    repaired = re.sub(r"\bNone\b", "null", repaired)

    # Unquoted keys: {category: "bug"} -> {"category": "bug"}
    repaired = re.sub(r"([{,]\s*)([A-Za-z_][A-Za-z0-9_]*)(\s*:)", r'\1"\2"\3', repaired)

    return repaired


# ---------------------------------------------------------------------------
# Value coercion
# ---------------------------------------------------------------------------

def _coerce_choice(value, allowed, aliases, default):
    """Map a model's answer onto our enum, falling back to `default`."""
    if value is None:
        return default

    if isinstance(value, (list, tuple)) and value:
        value = value[0]

    text = str(value).strip().lower().replace("-", "_").replace(" ", "_")

    if text in allowed:
        return text

    if text in aliases:
        return aliases[text]

    # "Feature Request (new)" -> match on the leading token.
    for option in allowed:
        if text.startswith(option) or option in text:
            return option

    spaced = text.replace("_", " ")
    if spaced in aliases:
        return aliases[spaced]

    return default


def _coerce_text(value, max_length):
    if value is None:
        return ""

    if isinstance(value, (list, tuple)):
        value = " ".join(str(v) for v in value)
    elif isinstance(value, dict):
        value = " ".join(str(v) for v in value.values())

    text = str(value).strip()
    if len(text) > max_length:
        text = text[:max_length].rsplit(" ", 1)[0] + "…"
    return text


def _coerce_confidence(value):
    """
    Normalise confidence to a float in 0.0-1.0.

    Models return 0.85, "0.85", "85%", 85, or "high". Anything unreadable
    becomes 0.5 rather than failing the whole classification.
    """
    if value is None:
        return 0.5

    if isinstance(value, bool):
        return 1.0 if value else 0.0

    if isinstance(value, (int, float)):
        number = float(value)
    else:
        text = str(value).strip().lower()
        worded = {"very high": 0.95, "high": 0.85, "medium": 0.6, "moderate": 0.6, "low": 0.3, "very low": 0.15}
        if text in worded:
            return worded[text]

        match = re.search(r"-?\d+(?:\.\d+)?", text)
        if not match:
            return 0.5
        number = float(match.group())
        if "%" in text:
            number /= 100

    # A bare 85 means 85%, not 8500%.
    if number > 1.0:
        number = number / 100 if number <= 100 else 1.0

    return round(max(0.0, min(1.0, number)), 2)
