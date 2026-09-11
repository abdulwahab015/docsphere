from django.db import transaction
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema
from rest_framework import generics
from rest_framework.exceptions import ValidationError
from rest_framework.filters import SearchFilter
from rest_framework.response import Response
from rest_framework.views import APIView

from core.permissions import ExtraPermissionsMixin
from projects.api.v1.serializers import ProjectSerializer
from projects.choices import AccessLevel
from projects.models import Project, ProjectPermission
from projects.permissions import HasProjectAccess
from users.permissions import IsOrganizationAdmin


class ProjectListCreateAPIView(ExtraPermissionsMixin, generics.ListCreateAPIView):
    """Lists the caller's organization's projects (``?search=`` matches the
    name); creates one - admins only - recording the caller as ``created_by``
    and granting them Owner access to it."""

    serializer_class = ProjectSerializer
    filter_backends = (SearchFilter,)
    search_fields = ("name",)

    def get_permissions(self):
        if self.request.method == "POST":
            return self._permissions_for(IsOrganizationAdmin)
        return self._permissions_for()

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


class ProjectDetailAPIView(
    ExtraPermissionsMixin, generics.RetrieveUpdateDestroyAPIView
):
    """Retrieve, update, or soft-delete a single project. Requires a resolvable
    ProjectPermission: read needs Viewer, write needs Editor, delete needs
    Owner. Cross-organization projects are indistinguishable from missing ones.
    """

    serializer_class = ProjectSerializer
    extra_permission_classes = (HasProjectAccess,)

    def get_queryset(self):
        return Project.objects.for_organization(self.request.user.organization)

    def perform_destroy(self, instance):
        """Soft delete: flip ``is_active`` instead of the default hard delete, so
        the row drops out of every ``for_organization`` queryset afterward."""
        instance.is_active = False
        instance.save(update_fields=["is_active"])


class ProjectRestoreAPIView(ExtraPermissionsMixin, APIView):
    """Reverses a soft-delete. Admin-only, like project creation - a Project's
    own ProjectPermission rows survive the soft-delete, but restoring one isn't
    gated on them. Cross-organization and already-active projects are both a
    404, since neither is in the restore lookup set.
    """

    extra_permission_classes = (IsOrganizationAdmin,)

    @extend_schema(request=None, responses={200: ProjectSerializer})
    def post(self, request, pk):
        project = get_object_or_404(
            Project.objects.inactive_for_organization(request.user.organization),
            pk=pk,
        )
        project.is_active = True
        project.save(update_fields=["is_active"])

        return Response(ProjectSerializer(project, context={"request": request}).data)
