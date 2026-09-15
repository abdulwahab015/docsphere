"""Root URL configuration.

One path per app under ``api/v1/``, with one exception: documents are a
resource of the ``projects`` app but get their own flat ``api/v1/documents/``
prefix (``projects.api.v1.document_urlpatterns``) so they're searchable and
listable independently of any project id, rather than nested under
``api/v1/projects/<id>/documents/``. Operational endpoints (schema, docs,
health, the Stripe webhook) sit outside the versioned API namespace.
"""

from decouple import config
from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

from core.health import HealthzView
from projects.api.v1.urls import document_urlpatterns

_ADMIN_PATH = config("DJANGO_ADMIN_PATH", default="admin/")

urlpatterns = [
    path(_ADMIN_PATH, admin.site.urls),
    path("healthz/", HealthzView.as_view(), name="healthz"),
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path(
        "api/docs/",
        SpectacularSwaggerView.as_view(url_name="schema"),
        name="swagger_ui",
    ),
    path("api/v1/users/", include("users.api.v1.urls")),
    path("api/v1/projects/", include("projects.api.v1.urls")),
    path("api/v1/documents/", include(document_urlpatterns)),
    path("stripe/", include("djstripe.urls", namespace="djstripe")),
]
