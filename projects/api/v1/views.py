from django.db import transaction
from django.http import Http404
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema
from rest_framework import generics
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.filters import SearchFilter
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from core.permissions import HasActiveSubscription
from projects.api.v1.serializers import DocumentSerializer, ProjectSerializer
from projects.choices import AccessLevel, Action
from projects.models import Document, Project, ProjectPermission
from projects.permissions import (
    HasDocumentAccess,
    HasProjectAccess,
    access_permits,
    resolve_access,
    resolve_project_access,
)
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
            return [IsOrganizationAdmin(), HasActiveSubscription()]
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


class ProjectRetrieveUpdateDestroyAPIView(generics.RetrieveUpdateDestroyAPIView):
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


class ProjectRestoreAPIView(APIView):
    """Reverses a soft-delete. Admin-only, like project creation - a Project's
    own ProjectPermission rows survive the soft-delete, but restoring one isn't
    gated on them. Cross-organization and already-active projects are both a
    404, since neither is in the restore lookup set.
    """

    permission_classes = [IsOrganizationAdmin, HasActiveSubscription]

    @extend_schema(request=None, responses={200: ProjectSerializer})
    def post(self, request, pk):
        project = get_object_or_404(
            Project.objects.inactive_for_organization(request.user.organization),
            pk=pk,
        )
        project.is_active = True
        project.save(update_fields=["is_active"])

        return Response(ProjectSerializer(project, context={"request": request}).data)


def _get_org_project_or_404(organization, project_id):
    """Shared lookup for both creating and listing documents: a project id
    that doesn't resolve to an active project in the caller's organization is
    a 404, never a 403 or a validation error - it must not reveal whether the
    id belongs to another organization at all."""
    try:
        project_id = int(project_id)
    except (TypeError, ValueError):
        raise Http404 from None

    return get_object_or_404(
        Project.objects.for_organization(organization), pk=project_id
    )


class DocumentListCreateAPIView(generics.ListCreateAPIView):
    """Lists the caller's organization's documents (``?search=`` matches the
    title, ``?project=`` narrows to one project); creates one under a project
    the caller has at least Editor access to, recording the caller as
    ``created_by``.
    """

    serializer_class = DocumentSerializer
    permission_classes = (IsAuthenticated, HasActiveSubscription)
    filter_backends = (SearchFilter,)
    search_fields = ("title",)

    def get_queryset(self):
        organization = self.request.user.organization
        queryset = Document.objects.for_organization(organization)

        project_id = self.request.query_params.get("project")
        if project_id:
            project = _get_org_project_or_404(organization, project_id)
            queryset = queryset.filter(project=project)

        return queryset.order_by("title")

    def perform_create(self, serializer):
        user = self.request.user
        organization = user.organization
        if not organization:
            raise ValidationError(
                {"detail": "You must belong to an organization to create a document."}
            )

        project = _get_org_project_or_404(
            organization, self.request.data.get("project")
        )
        if not access_permits(resolve_project_access(user, project), Action.WRITE):
            raise PermissionDenied(
                "You must have at least Editor access to this project to add documents to it."
            )

        serializer.save(created_by=user, project=project)


class DocumentRetrieveUpdateDestroyAPIView(generics.RetrieveUpdateDestroyAPIView):
    """Retrieve, update, or soft-delete a single document. Requires a
    resolvable access level (``DocumentPermission`` first, falling back to
    the parent project's ``ProjectPermission``): read needs Viewer, write
    needs Editor, delete needs Owner. Cross-organization or soft-deleted
    documents are indistinguishable from missing ones.
    """

    serializer_class = DocumentSerializer
    permission_classes = (IsAuthenticated, HasDocumentAccess, HasActiveSubscription)

    def get_queryset(self):
        return Document.objects.for_organization(self.request.user.organization)

    def perform_destroy(self, instance):
        """Soft delete: flip ``is_active`` instead of the default hard delete, so
        the row drops out of every ``for_organization`` queryset afterward."""
        instance.is_active = False
        instance.save(update_fields=["is_active"])


class DocumentRestoreAPIView(APIView):
    """Reverses a soft-delete. Unlike ``ProjectRestoreAPIView`` (admin-only,
    matching project creation), document creation isn't admin-gated - so
    restoring one requires the same Owner-level access that deleting it did,
    resolved the usual way (``DocumentPermission`` first, falling back to the
    parent project's ``ProjectPermission``). A document's own permission rows
    survive its soft-delete, same as a project's do. Cross-organization and
    already-active documents are both a 404, since neither is in the restore
    lookup set.
    """

    permission_classes = [IsAuthenticated, HasActiveSubscription]

    @extend_schema(request=None, responses={200: DocumentSerializer})
    def post(self, request, pk):
        document = get_object_or_404(
            Document.objects.inactive_for_organization(request.user.organization),
            pk=pk,
        )
        if not access_permits(resolve_access(request.user, document), Action.DELETE):
            raise PermissionDenied(
                "You must have Owner access to this document to restore it."
            )

        document.is_active = True
        document.save(update_fields=["is_active"])

        return Response(DocumentSerializer(document, context={"request": request}).data)
