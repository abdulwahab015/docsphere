from django.contrib import admin

from .models import Organization, OrganizationExport


@admin.register(Organization)
class OrganizationAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "billing_email",
        "is_active",
        "last_expiry_reminder_sent_at",
        "deletion_requested_at",
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


@admin.register(OrganizationExport)
class OrganizationExportAdmin(admin.ModelAdmin):
    list_display = ("organization", "requested_by", "file", "created")
    list_filter = ("organization",)
