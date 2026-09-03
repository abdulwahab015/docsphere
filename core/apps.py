from django.apps import AppConfig


class CoreConfig(AppConfig):
    """Cross-cutting infrastructure shared by the domain apps.

    `core` holds no domain models — only project-wide plumbing: the
    `TimeStampedModel` base, DRF pagination, and request/response logging.
    """

    default_auto_field = "django.db.models.BigAutoField"
    name = "core"
