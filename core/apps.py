from django.apps import AppConfig


class CoreConfig(AppConfig):
    """Cross-cutting infrastructure shared by the domain apps.

    `core` holds no domain models — only project-wide plumbing: the
    `TimeStampedModel` base, DRF pagination, request/response logging and
    error tracking.
    """

    default_auto_field = "django.db.models.BigAutoField"
    name = "core"

    def ready(self):
        # Here rather than in settings, so the web server and the Celery
        # processes - which all load the apps - report errors alike.
        from core.error_tracking import init_error_tracking

        init_error_tracking()
