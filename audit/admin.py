from django.contrib import admin

from .models import AuditEvent


@admin.register(AuditEvent)
class AuditEventAdmin(admin.ModelAdmin):
    list_display = (
        "created",
        "organization",
        "actor",
        "verb",
        "target_user",
        "project",
        "document",
    )
    list_filter = ("organization", "verb")
    search_fields = ("actor__email", "target_user__email")
