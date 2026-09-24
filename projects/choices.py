from django.db import models


class AccessLevel(models.TextChoices):
    """Shared role hierarchy: Owner > Editor > Viewer."""

    VIEWER = "VIEWER", "Viewer"
    EDITOR = "EDITOR", "Editor"
    OWNER = "OWNER", "Owner"


class Action(models.TextChoices):
    """Things a user can attempt against a document or project."""

    READ = "READ", "Read"
    WRITE = "WRITE", "Write"
    DELETE = "DELETE", "Delete"
    RESHARE = "RESHARE", "Re-share"


class Visibility(models.TextChoices):
    """Shared by ``Project`` and ``Document``. ``PUBLIC`` grants every member of the
    resource's organization an implicit Viewer level; ``PRIVATE`` grants nothing beyond
    explicit permission rows."""

    PRIVATE = "PRIVATE", "Private"
    PUBLIC = "PUBLIC", "Public"


class AccessRequestStatus(models.TextChoices):
    """Lifecycle of a ``DocumentAccessRequest``."""

    PENDING = "PENDING", "Pending"
    APPROVED = "APPROVED", "Approved"
    DENIED = "DENIED", "Denied"
