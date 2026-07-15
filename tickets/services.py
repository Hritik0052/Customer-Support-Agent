"""
The bridge between the Django models and the framework-free `ai` package.

Keeping this here means views never touch the AI layer directly, and the AI
layer never imports Django.
"""

import logging

from django.conf import settings
from django.utils import timezone

from ai.exceptions import AIServiceError
from ai.services.ai_service import classify_ticket

from .models import Status, Ticket

logger = logging.getLogger(__name__)


def analyze_ticket(ticket):
    """
    Run classification for `ticket` and persist the result.

    Never raises: a failed analysis is a saved FAILED state, not a 500. Returns
    True on success so the caller can pick a message to show.
    """
    ticket.status = Status.PROCESSING
    ticket.save(update_fields=["status", "updated_at"])

    try:
        result = classify_ticket(
            subject=ticket.subject,
            message=ticket.message,
            customer_name=ticket.customer_name,
        )
    except AIServiceError as exc:
        logger.error("Analysis failed for ticket %s: %s", ticket.pk, exc)
        ticket.status = Status.FAILED
        ticket.error_message = getattr(exc, "user_message", str(exc))
        ticket.save(update_fields=["status", "error_message", "updated_at"])
        return False
    except Exception as exc:  # noqa: BLE001 - a bug here must not 500 the page
        logger.exception("Unexpected error analysing ticket %s", ticket.pk)
        ticket.status = Status.FAILED
        ticket.error_message = "An unexpected error occurred while analysing this ticket."
        ticket.save(update_fields=["status", "error_message", "updated_at"])
        return False

    ticket.category = result["category"]
    ticket.priority = result["priority"]
    ticket.sentiment = result["sentiment"]
    ticket.summary = result["summary"]
    ticket.suggested_reply = result["suggested_reply"]
    ticket.confidence = result["confidence"]
    ticket.model_name = result["model_name"]
    ticket.processing_time = result["processing_time"]
    ticket.status = Status.COMPLETED
    ticket.error_message = ""
    ticket.save()
    return True


def rate_limit_exceeded(user):
    """True if `user` has run more analyses in the last hour than we allow."""
    limit = getattr(settings, "ANALYSIS_RATE_LIMIT_PER_HOUR", 30)
    since = timezone.now() - timezone.timedelta(hours=1)
    used = Ticket.objects.filter(user=user, created_at__gte=since).count()
    return used >= limit
