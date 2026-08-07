from django.contrib import admin

from .models import Document, Project


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
