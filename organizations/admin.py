from django.contrib import admin

from .models import Invitation, Organization, User


@admin.register(Organization)
class OrganizationAdmin(admin.ModelAdmin):
    list_display = ("name", "djstripe_customer", "created_at")
    search_fields = ("name",)


@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = (
        "email",
        "username",
        "organization",
        "org_role",
        "is_active",
        "is_staff",
    )
    list_filter = ("organization", "org_role", "is_active")
    search_fields = ("email", "username")


@admin.register(Invitation)
class InvitationAdmin(admin.ModelAdmin):
    list_display = (
        "email",
        "organization",
        "status",
        "invited_by",
        "created_at",
        "accepted_at",
    )
    list_filter = ("status", "organization")
    search_fields = ("email",)
