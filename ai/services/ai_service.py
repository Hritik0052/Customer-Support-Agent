"""
The orchestrator: string in, validated dict out.

Deliberately free of Django imports so the whole AI path can be exercised from
a plain script without a database. Run it directly to smoke-test:

    python -m ai.services.ai_service
"""

import logging
import os
import time

from ai.exceptions import AIServiceError, ParseError
from ai.prompts.classifier import build_messages
from ai.services.openrouter import chat_completion
from ai.services.parser import parse_classification
from ai.utils.helpers import truncate

logger = logging.getLogger(__name__)


def _models():
    """Primary model plus fallback, from Django settings or the environment."""
    try:
        from django.conf import settings

        if settings.configured:
            return settings.OPENROUTER_MODEL, settings.OPENROUTER_FALLBACK_MODEL
    except (ImportError, Exception):  # noqa: B014 - ImproperlyConfigured included
        pass

    return (
        os.environ.get("OPENROUTER_MODEL", "nvidia/nemotron-3-nano-30b-a3b:free"),
        os.environ.get("OPENROUTER_FALLBACK_MODEL", "openai/gpt-oss-20b:free"),
    )


def classify_ticket(subject, message, customer_name="the customer"):
    """
    Classify one support ticket.

    Returns:
        {
          category, priority, sentiment, summary, suggested_reply,
          confidence, model_name, processing_time
        }

    Raises AIServiceError (or a subclass) if every attempt fails.
    """
    primary, fallback = _models()
    subject = truncate(subject, 200)
    message = truncate(message, 4000)

    # Three escalating attempts: normal, a stricter "JSON only" retry on the
    # same model, then the fallback model. Parse failures are by far the most
    # common failure mode with free models, and a nudge usually fixes them.
    attempts = [
        (primary, False),
        (primary, True),
        (fallback, True),
    ]

    last_error = None
    started = time.perf_counter()

    for model, retry in attempts:
        try:
            raw = chat_completion(build_messages(subject, message, customer_name, retry=retry), model=model)
            result = parse_classification(raw)
            result["model_name"] = model
            result["processing_time"] = round(time.perf_counter() - started, 2)
            return result

        except ParseError as exc:
            last_error = exc
            logger.warning(
                "Parse failed on %s (retry=%s): %s | raw=%r",
                model, retry, exc, exc.raw_response[:400],
            )
            continue

        except AIServiceError as exc:
            last_error = exc
            logger.warning("Call failed on %s: %s", model, exc)
            continue

    logger.error("All classification attempts failed after %.2fs", time.perf_counter() - started)
    raise last_error or AIServiceError("Classification failed.")


# ---------------------------------------------------------------------------
# Standalone smoke test — the M4 gate. No Django, no database.
# ---------------------------------------------------------------------------

SAMPLES = [
    {
        "customer_name": "Priya Sharma",
        "subject": "Charged twice for my Pro subscription",
        "message": (
            "Hi, I was billed 1,499 rupees twice this month for the same Pro plan. "
            "I only have one subscription. This is the second month it has happened "
            "and honestly I am losing patience. Please refund the duplicate charge."
        ),
    },
    {
        "customer_name": "Tom Baker",
        "subject": "Export button does nothing on Safari",
        "message": (
            "Clicking Export CSV on the reports page does nothing in Safari 17. "
            "No download, no error. Works fine in Chrome. Not urgent for me since "
            "I can switch browsers, just wanted to flag it."
        ),
    },
    {
        "customer_name": "Aisha Khan",
        "subject": "Any plans for a dark mode?",
        "message": (
            "Love the product, we use it daily across the team. Would be great to "
            "have a dark theme for late night shifts. Is that on the roadmap?"
        ),
    },
]


def _smoke_test():
    import json
    import sys
    from pathlib import Path

    # Models emit typographic characters (curly quotes, non-breaking hyphens)
    # that the default Windows console codepage cannot encode. Force UTF-8 so
    # printing a result never crashes the test.
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    # Load .env so the script works without Django's settings machinery.
    env_path = Path(__file__).resolve().parents[2] / ".env"
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, _, value = line.partition("=")
                os.environ.setdefault(key.strip(), value.strip())

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

    failures = 0
    for i, sample in enumerate(SAMPLES, 1):
        print(f"\n{'=' * 70}\n[{i}/{len(SAMPLES)}] {sample['subject']}\n{'=' * 70}")
        try:
            result = classify_ticket(**sample)
            print(json.dumps(result, indent=2, ensure_ascii=False))
        except AIServiceError as exc:
            failures += 1
            print(f"FAILED: {type(exc).__name__}: {exc}")

    print(f"\n{len(SAMPLES) - failures}/{len(SAMPLES)} classified successfully.")
    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    _smoke_test()
