import csv
import json

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Case, IntegerField, Q, When
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from .forms import SORT_OPTIONS, TicketFilterForm, TicketForm
from .models import Priority, Ticket
from .services import analyze_ticket, rate_limit_exceeded

PAGE_SIZE = 10


def _owned(request):
    """
    Every queryset in this module starts here.

    Scoping to request.user in one place — rather than remembering it in each
    view — is what stops one user reading another's tickets.
    """
    return Ticket.objects.filter(user=request.user)


def _apply_filters(queryset, cleaned):
    """Apply the search/filter/sort options from TicketFilterForm."""
    q = (cleaned.get("q") or "").strip()
    if q:
        queryset = queryset.filter(
            Q(customer_name__icontains=q)
            | Q(email__icontains=q)
            | Q(subject__icontains=q)
            | Q(message__icontains=q)
        )

    for field in ["category", "priority", "sentiment", "status"]:
        value = cleaned.get(field)
        if value:
            queryset = queryset.filter(**{field: value})

    if cleaned.get("date_from"):
        queryset = queryset.filter(created_at__date__gte=cleaned["date_from"])
    if cleaned.get("date_to"):
        queryset = queryset.filter(created_at__date__lte=cleaned["date_to"])

    sort = cleaned.get("sort") or "newest"

    if sort == "priority":
        # Alphabetical ordering would put "urgent" last. Rank explicitly.
        queryset = queryset.annotate(
            priority_rank=Case(
                When(priority=Priority.URGENT, then=0),
                When(priority=Priority.HIGH, then=1),
                When(priority=Priority.MEDIUM, then=2),
                When(priority=Priority.LOW, then=3),
                default=4,
                output_field=IntegerField(),
            )
        ).order_by("priority_rank", "-created_at")
    else:
        order = SORT_OPTIONS.get(sort, SORT_OPTIONS["newest"])[0]
        queryset = queryset.order_by(f"{order}", "-created_at") if order else queryset

    return queryset


def _querystring_without_page(request):
    """Preserve active filters across pagination links."""
    params = request.GET.copy()
    params.pop("page", None)
    encoded = params.urlencode()
    return f"&{encoded}" if encoded else ""


@login_required
def ticket_list(request):
    """`/tickets/` — the history page: search, filters, sorting, pagination."""
    form = TicketFilterForm(request.GET or None)
    queryset = _owned(request)

    if form.is_valid():
        queryset = _apply_filters(queryset, form.cleaned_data)

    paginator = Paginator(queryset, PAGE_SIZE)
    page = paginator.get_page(request.GET.get("page"))

    context = {
        "form": form,
        "page_obj": page,
        "total": paginator.count,
        "querystring": _querystring_without_page(request),
        "has_filters": any(request.GET.get(k) for k in ["q", "category", "priority", "sentiment", "status", "date_from", "date_to"]),
    }

    # HTMX live search swaps just the results, not the whole page.
    if request.htmx:
        return render(request, "tickets/partials/ticket_table.html", context)

    return render(request, "tickets/list.html", context)


@login_required
def ticket_create(request):
    if request.method == "POST":
        form = TicketForm(request.POST)
        if form.is_valid():
            if rate_limit_exceeded(request.user):
                messages.error(request, "You've hit the hourly analysis limit. Please try again shortly.")
                return render(request, "tickets/create.html", {"form": form})

            ticket = form.save(commit=False)
            ticket.user = request.user
            ticket.save()

            if not analyze_ticket(ticket):
                messages.warning(request, "The ticket was saved, but the AI analysis failed. You can retry it below.")

            return redirect("tickets:result", pk=ticket.pk)
    else:
        form = TicketForm()

    return render(request, "tickets/create.html", {"form": form})


@login_required
def ticket_result(request, pk):
    ticket = get_object_or_404(_owned(request), pk=pk)
    return render(request, "tickets/result.html", {"ticket": ticket})


@login_required
def ticket_detail(request, pk):
    ticket = get_object_or_404(_owned(request), pk=pk)
    return render(request, "tickets/detail.html", {"ticket": ticket})


@login_required
@require_POST
def ticket_reanalyze(request, pk):
    ticket = get_object_or_404(_owned(request), pk=pk)

    if rate_limit_exceeded(request.user):
        messages.error(request, "You've hit the hourly analysis limit. Please try again shortly.")
        return redirect("tickets:detail", pk=ticket.pk)

    if analyze_ticket(ticket):
        messages.success(request, "Ticket re-analysed.")
    else:
        messages.error(request, ticket.error_message or "Analysis failed. Please try again.")

    return redirect("tickets:detail", pk=ticket.pk)


@login_required
@require_POST
def ticket_delete(request, pk):
    ticket = get_object_or_404(_owned(request), pk=pk)
    subject = ticket.subject
    ticket.delete()
    messages.success(request, f"Deleted “{subject}”.")
    return redirect("tickets:list")


@login_required
def ticket_download_json(request, pk):
    ticket = get_object_or_404(_owned(request), pk=pk)
    response = JsonResponse(ticket.as_export_dict(), json_dumps_params={"indent": 2})
    response["Content-Disposition"] = f'attachment; filename="ticket-{ticket.pk}.json"'
    return response


# ---------------------------------------------------------------------------
# Bulk export — honours whatever filters are active on the history page.
# ---------------------------------------------------------------------------

EXPORT_COLUMNS = [
    "id", "customer_name", "email", "subject", "message", "category", "priority",
    "sentiment", "summary", "suggested_reply", "confidence", "model_name",
    "processing_time", "status", "created_at",
]


def _filtered_for_export(request):
    form = TicketFilterForm(request.GET or None)
    queryset = _owned(request)
    if form.is_valid():
        queryset = _apply_filters(queryset, form.cleaned_data)
    return queryset


@login_required
def export_csv(request):
    queryset = _filtered_for_export(request)

    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = 'attachment; filename="tickets.csv"'
    # Excel needs a BOM to read UTF-8 correctly, otherwise accented names break.
    response.write("﻿")

    writer = csv.DictWriter(response, fieldnames=EXPORT_COLUMNS, extrasaction="ignore")
    writer.writeheader()
    for ticket in queryset.iterator(chunk_size=200):
        writer.writerow(ticket.as_export_dict())

    return response


@login_required
def export_json(request):
    queryset = _filtered_for_export(request)
    payload = [t.as_export_dict() for t in queryset.iterator(chunk_size=200)]

    response = HttpResponse(
        json.dumps(payload, indent=2, ensure_ascii=False),
        content_type="application/json",
    )
    response["Content-Disposition"] = 'attachment; filename="tickets.json"'
    return response
