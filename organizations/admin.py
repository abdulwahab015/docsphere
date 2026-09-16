from django.contrib import admin

from .models import Organization


@admin.register(Organization)
class OrganizationAdmin(admin.ModelAdmin):
    list_display = ("name", "billing_email", "last_expiry_reminder_sent_at", "created")
    search_fields = ("name",)
