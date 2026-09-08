"""Root URL configuration.

One path per app under ``api/v1/``. Operational endpoints
(schema, docs, health, the Stripe webhook) sit outside the versioned API
namespace.
"""

from decouple import config
from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

from core.health import HealthzView

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
    path("stripe/", include("djstripe.urls", namespace="djstripe")),
]
