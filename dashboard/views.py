from datetime import timedelta

from django.contrib.auth.decorators import login_required
from django.db.models import Avg, Count, Q
from django.shortcuts import render
from django.utils import timezone

from tickets.models import Category, Priority, Sentiment, Status, Ticket


@login_required
def index(request):
    tickets = Ticket.objects.filter(user=request.user)

    # All six card numbers plus the averages in a single query. The obvious
    # alternative — one .count() per card — is seven round trips for the
    # same information.
    stats = tickets.aggregate(
        total=Count("id"),
        billing=Count("id", filter=Q(category=Category.BILLING)),
        bugs=Count("id", filter=Q(category=Category.BUG)),
        features=Count("id", filter=Q(category=Category.FEATURE_REQUEST)),
        high_priority=Count("id", filter=Q(priority__in=[Priority.HIGH, Priority.URGENT])),
        negative=Count("id", filter=Q(sentiment=Sentiment.NEGATIVE)),
        avg_confidence=Avg("confidence"),
        avg_processing=Avg("processing_time"),
        completed=Count("id", filter=Q(status=Status.COMPLETED)),
        failed=Count("id", filter=Q(status=Status.FAILED)),
    )

    context = {
        "stats": stats,
        "avg_confidence_pct": round((stats["avg_confidence"] or 0) * 100),
        "recent_tickets": tickets.select_related("user")[:8],
        # Passed as plain dicts — the templates render them through
        # |json_script, which does the serialising and escaping itself.
        "category_chart": _distribution(tickets, "category", Category),
        "priority_chart": _distribution(tickets, "priority", Priority),
        "sentiment_chart": _distribution(tickets, "sentiment", Sentiment),
        "volume_chart": _volume_last_30_days(tickets),
        "has_data": stats["total"] > 0,
    }
    return render(request, "dashboard/index.html", context)


def _distribution(queryset, field, choices):
    """Count tickets per choice value — one GROUP BY, not one query per label."""
    counts = {
        row[field]: row["count"]
        for row in queryset.exclude(**{f"{field}": ""})
        .values(field)
        .annotate(count=Count("id"))
    }
    labels, data = [], []
    for value, label in choices.choices:
        if counts.get(value):
            labels.append(label)
            data.append(counts[value])

    return {"labels": labels, "data": data}


def _volume_last_30_days(queryset):
    """Daily ticket counts for the last 30 days, zero-filled."""
    today = timezone.localdate()
    start = today - timedelta(days=29)

    rows = (
        queryset.filter(created_at__date__gte=start)
        .values("created_at__date")
        .annotate(count=Count("id"))
    )
    counts = {row["created_at__date"]: row["count"] for row in rows}

    labels, data = [], []
    for offset in range(30):
        day = start + timedelta(days=offset)
        labels.append(day.strftime("%d %b"))
        data.append(counts.get(day, 0))

    return {"labels": labels, "data": data}
