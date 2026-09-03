from django.db import connection
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView


class HealthzView(APIView):
    """Container liveness/readiness probe.

    Confirms the process is up and the database answers a trivial query;
    returns 200 ``{"status": "ok"}`` or 503 ``{"status": "unhealthy"}``.
    Deliberately hand-rolled — a full health-check framework is more than a
    single Postgres round-trip warrants here.
    """

    authentication_classes = []
    permission_classes = [AllowAny]

    @extend_schema(
        auth=[],
        responses={
            200: OpenApiResponse(description='{"status": "ok"}'),
            503: OpenApiResponse(description='{"status": "unhealthy"}'),
        },
    )
    def get(self, request):
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
                cursor.fetchone()
        except Exception:
            return Response(
                {"status": "unhealthy"},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        return Response({"status": "ok"})
