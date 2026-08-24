from django.db import models


class AccessLevel(models.TextChoices):
    """Shared role hierarchy: Owner > Editor > Viewer."""

    VIEWER = "VIEWER", "Viewer"
    EDITOR = "EDITOR", "Editor"
    OWNER = "OWNER", "Owner"
