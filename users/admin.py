from django.contrib import admin

from .models import Invitation, User


@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = (
        "email",
        "organization",
        "org_role",
        "is_active",
        "is_staff",
    )
    list_filter = ("organization", "org_role", "is_active")
    search_fields = ("email",)


@admin.register(Invitation)
class InvitationAdmin(admin.ModelAdmin):
    list_display = (
        "email",
        "organization",
        "status",
        "invited_by",
        "created",
        "accepted_at",
    )
    list_filter = ("status", "organization")
    search_fields = ("email",)
