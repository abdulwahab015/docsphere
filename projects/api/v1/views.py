from django.db import transaction
from rest_framework import generics
from rest_framework.exceptions import ValidationError
from rest_framework.filters import SearchFilter
from rest_framework.permissions import IsAuthenticated

from core.permissions import HasActiveSubscription
from projects.api.v1.serializers import ProjectSerializer
from projects.choices import AccessLevel
from projects.models import Project, ProjectPermission
from projects.permissions import HasProjectAccess
from users.permissions import IsOrganizationAdmin


class ProjectListCreateAPIView(generics.ListCreateAPIView):
    """Lists the caller's organization's projects (``?search=`` matches the
    name); creates one - admins only - recording the caller as ``created_by``
    and granting them Owner access to it."""

    serializer_class = ProjectSerializer
    filter_backends = (SearchFilter,)
    search_fields = ("name",)

    def get_permissions(self):
        if self.request.method == "POST":
            return [IsAuthenticated(), IsOrganizationAdmin(), HasActiveSubscription()]
        return [IsAuthenticated(), HasActiveSubscription()]

    def get_queryset(self):
        return Project.objects.for_organization(
            self.request.user.organization
        ).order_by("name")

    def perform_create(self, serializer):
        organization = self.request.user.organization
        if not organization:
            raise ValidationError(
                {"detail": "You must belong to an organization to create a project."}
            )

        with transaction.atomic():
            project = serializer.save(
                created_by=self.request.user, organization=organization
            )
            ProjectPermission.objects.create(
                project=project,
                user=self.request.user,
                access_level=AccessLevel.OWNER,
            )


class ProjectDetailAPIView(generics.RetrieveUpdateDestroyAPIView):
    """Retrieve, update, or soft-delete a single project. Requires a resolvable
    ProjectPermission: read needs Viewer, write needs Editor, delete needs
    Owner. Cross-organization projects are indistinguishable from missing ones.
    """

    serializer_class = ProjectSerializer
    permission_classes = (IsAuthenticated, HasProjectAccess, HasActiveSubscription)

    def get_queryset(self):
        return Project.objects.for_organization(self.request.user.organization)

    def perform_destroy(self, instance):
        """Soft delete: flip ``is_active`` instead of the default hard delete, so
        the row drops out of every ``for_organization`` queryset afterward."""
        instance.is_active = False
        instance.save(update_fields=["is_active"])
