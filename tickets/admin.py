from django.contrib import admin

from .models import Ticket


@admin.register(Ticket)
class TicketAdmin(admin.ModelAdmin):
    list_display = ["id", "subject", "customer_name", "category", "priority", "sentiment", "status", "created_at"]
    list_filter = ["status", "category", "priority", "sentiment", "created_at"]
    search_fields = ["customer_name", "email", "subject", "message"]
    readonly_fields = ["model_name", "processing_time", "created_at", "updated_at"]
    list_select_related = ["user"]
    date_hierarchy = "created_at"

    fieldsets = (
        ("Owner", {"fields": ("user",)}),
        ("Customer", {"fields": ("customer_name", "email")}),
        ("Ticket", {"fields": ("subject", "message")}),
        ("AI analysis", {"fields": ("category", "priority", "sentiment", "summary", "suggested_reply", "confidence")}),
        ("Run metadata", {"fields": ("status", "model_name", "processing_time", "error_message", "created_at", "updated_at")}),
    )
