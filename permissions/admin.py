from django.contrib import admin

from .models import DocumentPermission, ProjectPermission


@admin.register(ProjectPermission)
class ProjectPermissionAdmin(admin.ModelAdmin):
    list_display = ("project", "user", "access_level")
    list_filter = ("access_level",)


@admin.register(DocumentPermission)
class DocumentPermissionAdmin(admin.ModelAdmin):
    list_display = ("document", "user", "access_level")
    list_filter = ("access_level",)
