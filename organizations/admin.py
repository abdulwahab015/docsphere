from django.contrib import admin

from .models import Organization


@admin.register(Organization)
class OrganizationAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "billing_email",
        "is_active",
        "last_expiry_reminder_sent_at",
        "created",
    )
    list_filter = ("is_active",)
    search_fields = ("name",)
    actions = ("deactivate_organizations", "activate_organizations")

    @admin.action(description="Deactivate selected organizations")
    def deactivate_organizations(self, request, queryset):
        queryset.update(is_active=False)

    @admin.action(description="Activate selected organizations")
    def activate_organizations(self, request, queryset):
        queryset.update(is_active=True)
