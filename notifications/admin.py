from django.contrib import admin

from .models import Notification


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = (
        "created",
        "recipient",
        "verb",
        "actor",
        "project",
        "document",
        "read_at",
    )
    list_filter = ("verb",)
    search_fields = ("recipient__email", "actor__email")
