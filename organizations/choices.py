from django.db import models


class ExportStatus(models.TextChoices):
    """Where an organization export is: still being built, ready to
    download, or given up on after its retries."""

    BUILDING = "BUILDING", "Building"
    READY = "READY", "Ready"
    FAILED = "FAILED", "Failed"
