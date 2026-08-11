from django.contrib import admin

from .models import Document, DocumentPermission, Project, ProjectPermission


@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = ("name", "organization", "created_by", "created_at")
    list_filter = ("organization",)
    search_fields = ("name",)


@admin.register(Document)
class DocumentAdmin(admin.ModelAdmin):
    list_display = ("title", "project", "created_by", "created_at", "updated_at")
    list_filter = ("project__organization",)
    search_fields = ("title",)


@admin.register(ProjectPermission)
class ProjectPermissionAdmin(admin.ModelAdmin):
    list_display = ("project", "user", "access_level")
    list_filter = ("access_level",)


@admin.register(DocumentPermission)
class DocumentPermissionAdmin(admin.ModelAdmin):
    list_display = ("document", "user", "access_level")
    list_filter = ("access_level",)
