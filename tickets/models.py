from django.conf import settings
from django.db import models
from django.urls import reverse


class Category(models.TextChoices):
    BILLING = "billing", "Billing"
    BUG = "bug", "Bug"
    FEATURE_REQUEST = "feature_request", "Feature Request"
    TECHNICAL = "technical", "Technical"
    ACCOUNT = "account", "Account"
    GENERAL = "general", "General"


class Priority(models.TextChoices):
    LOW = "low", "Low"
    MEDIUM = "medium", "Medium"
    HIGH = "high", "High"
    URGENT = "urgent", "Urgent"


class Sentiment(models.TextChoices):
    POSITIVE = "positive", "Positive"
    NEUTRAL = "neutral", "Neutral"
    NEGATIVE = "negative", "Negative"


class Status(models.TextChoices):
    PENDING = "pending", "Pending"
    PROCESSING = "processing", "Processing"
    COMPLETED = "completed", "Completed"
    FAILED = "failed", "Failed"


# Ordering used when the user sorts by priority — most urgent first.
PRIORITY_RANK = {
    Priority.URGENT: 0,
    Priority.HIGH: 1,
    Priority.MEDIUM: 2,
    Priority.LOW: 3,
}


class Ticket(models.Model):
    """
    A customer support ticket plus the AI's analysis of it.

    Every AI-derived field is nullable: a ticket exists the moment it is
    submitted, before analysis has run, and analysis can fail.
    """

    # --- Ownership ---
    # Not in the original roadmap schema, but the panel is login-gated, so
    # tickets need an owner or every user would see everyone else's.
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="tickets",
    )

    # --- Submitted by the user ---
    customer_name = models.CharField(max_length=100)
    email = models.EmailField()
    subject = models.CharField(max_length=200)
    message = models.TextField()

    # --- Produced by the AI ---
    category = models.CharField(max_length=20, choices=Category, blank=True, db_index=True)
    priority = models.CharField(max_length=10, choices=Priority, blank=True, db_index=True)
    sentiment = models.CharField(max_length=10, choices=Sentiment, blank=True, db_index=True)
    summary = models.TextField(blank=True)
    suggested_reply = models.TextField(blank=True)
    confidence = models.FloatField(null=True, blank=True)

    # --- Run metadata ---
    model_name = models.CharField(max_length=100, blank=True)
    processing_time = models.FloatField(null=True, blank=True, help_text="Seconds")
    status = models.CharField(max_length=12, choices=Status, default=Status.PENDING, db_index=True)
    error_message = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "-created_at"]),
            models.Index(fields=["user", "status"]),
        ]

    def __str__(self):
        return f"#{self.pk} {self.subject}"

    def get_absolute_url(self):
        return reverse("tickets:detail", kwargs={"pk": self.pk})

    # --- Display helpers, used by templates for badge styling ---

    @property
    def priority_badge_class(self):
        return f"badge-{self.priority}" if self.priority else "badge-neutral"

    @property
    def sentiment_badge_class(self):
        return f"badge-{self.sentiment}" if self.sentiment else "badge-neutral"

    @property
    def confidence_percent(self):
        return round(self.confidence * 100) if self.confidence is not None else None

    @property
    def is_analyzed(self):
        return self.status == Status.COMPLETED

    def as_export_dict(self):
        """Shape used by both the single-ticket JSON download and the bulk export."""
        return {
            "id": self.pk,
            "customer_name": self.customer_name,
            "email": self.email,
            "subject": self.subject,
            "message": self.message,
            "category": self.get_category_display() if self.category else None,
            "priority": self.get_priority_display() if self.priority else None,
            "sentiment": self.get_sentiment_display() if self.sentiment else None,
            "summary": self.summary or None,
            "suggested_reply": self.suggested_reply or None,
            "confidence": self.confidence,
            "model_name": self.model_name or None,
            "processing_time": self.processing_time,
            "status": self.get_status_display(),
            "created_at": self.created_at.isoformat(),
        }
