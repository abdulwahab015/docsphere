from django.contrib import admin

from .models import (
    Document,
    DocumentAccessRequest,
    DocumentPermission,
    Project,
    ProjectPermission,
)


@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "organization",
        "visibility",
        "created_by",
        "is_active",
        "created",
    )
    list_filter = ("organization", "visibility", "is_active")
    search_fields = ("name",)


@admin.register(Document)
class DocumentAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "organization",
        "project",
        "visibility",
        "created_by",
        "is_active",
        "created",
        "modified",
    )
    list_filter = ("organization", "visibility", "is_active")
    search_fields = ("title",)


@admin.register(ProjectPermission)
class ProjectPermissionAdmin(admin.ModelAdmin):
    list_display = ("project", "user", "access_level")
    list_filter = ("access_level",)


@admin.register(DocumentPermission)
class DocumentPermissionAdmin(admin.ModelAdmin):
    list_display = ("document", "user", "access_level")
    list_filter = ("access_level",)


@admin.register(DocumentAccessRequest)
class DocumentAccessRequestAdmin(admin.ModelAdmin):
    list_display = ("document", "requested_by", "status", "reviewed_by", "created")
    list_filter = ("status",)
