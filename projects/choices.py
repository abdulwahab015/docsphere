from django.db import models


class AccessLevel(models.TextChoices):
    """Shared role hierarchy: Owner > Editor > Viewer."""

    VIEWER = "VIEWER", "Viewer"
    EDITOR = "EDITOR", "Editor"
    OWNER = "OWNER", "Owner"


class Action(models.TextChoices):
    """Things a user can attempt against a document or project."""

    READ = "read", "Read"
    WRITE = "write", "Write"
    DELETE = "delete", "Delete"
    RESHARE = "reshare", "Re-share"
