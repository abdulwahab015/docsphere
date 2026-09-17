from django.db import transaction
from drf_spectacular.utils import extend_schema
from rest_framework import generics, mixins
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.filters import SearchFilter
from rest_framework.generics import get_object_or_404
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from core.permissions import HasActiveSubscription
from projects.api.v1.serializers import (
    DocumentPermissionSerializer,
    DocumentSerializer,
    ProjectPermissionSerializer,
    ProjectSerializer,
    ShareSerializer,
)
from projects.choices import AccessLevel, Action
from projects.models import Document, DocumentPermission, Project, ProjectPermission
from projects.permissions import (
    HasDocumentAccess,
    HasProjectAccess,
    access_permits,
    resolve_access,
    resolve_project_access,
)
from projects.tasks import (
    send_document_shared_email_task,
    send_project_shared_email_task,
)
from users.permissions import IsOrganizationAdmin


def _get_org_scoped_or_404(model, organization, pk):
    """A pk outside the caller's organization is a 404, never a 403 - it must
    not reveal whether the id belongs to another organization."""
    return get_object_or_404(model.objects.for_organization(organization), pk=pk)


def _check_can_share(user, resource, resource_field, resolve_access_fn):
    """Owner-level ``Action.RESHARE`` is required to view or change sharing."""
    if not access_permits(resolve_access_fn(user, resource), Action.RESHARE):
        raise PermissionDenied(
            f"You must have Owner access to this {resource_field} to share it."
        )


def _ensure_not_last_owner(permission, permission_model, resource_field, resource):
    """A resource's last Owner-level grant can't be revoked, so it never ends
    up with nobody able to manage its sharing."""
    if permission.access_level != AccessLevel.OWNER:
        return

    owner_count = permission_model.objects.filter(
        access_level=AccessLevel.OWNER, **{resource_field: resource}
    ).count()
    if owner_count <= 1:
        raise ValidationError(
            {"detail": f"Cannot revoke the {resource_field}'s last Owner."}
        )


class SoftDeleteMixin:
    """Flips ``is_active`` instead of hard-deleting, so the row drops out of
    every ``for_organization`` queryset."""

    def perform_destroy(self, instance):
        instance.is_active = False
        instance.save(update_fields=["is_active"])


class ProjectListCreateAPIView(generics.ListCreateAPIView):
    """Lists the org's projects (``?search=`` matches name); creates one -
    admin-only - granting the creator Owner access."""

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


class ProjectRetrieveUpdateDestroyAPIView(
    SoftDeleteMixin, generics.RetrieveUpdateDestroyAPIView
):
    """Retrieve/update/soft-delete a project. Requires a resolvable
    ProjectPermission: read needs Viewer, write Editor, delete Owner.
    Cross-organization projects are a 404, not a 403."""

    serializer_class = ProjectSerializer
    permission_classes = (IsAuthenticated, HasProjectAccess, HasActiveSubscription)

    def get_queryset(self):
        return Project.objects.for_organization(self.request.user.organization)


class ProjectRestoreAPIView(APIView):
    """Reverses a soft-delete. Admin-only, like project creation - not gated
    on the project's own ProjectPermission rows. Cross-organization and
    already-active projects are both a 404."""

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


class DocumentListCreateAPIView(generics.ListCreateAPIView):
    """Lists the org's documents (``?search=`` matches title, ``?project=``
    narrows to one project); creates one under a project the caller has at
    least Editor access to."""

    serializer_class = DocumentSerializer
    filter_backends = (SearchFilter,)
    search_fields = ("title",)

    def get_queryset(self):
        organization = self.request.user.organization
        queryset = Document.objects.for_organization(organization)

        project_id = self.request.query_params.get("project")
        if project_id:
            project = _get_org_scoped_or_404(Project, organization, project_id)
            queryset = queryset.filter(project=project)

        return queryset.order_by("title")

    def perform_create(self, serializer):
        user = self.request.user
        organization = user.organization
        if not organization:
            raise ValidationError(
                {"detail": "You must belong to an organization to create a document."}
            )

        project = _get_org_scoped_or_404(
            Project, organization, self.request.data.get("project")
        )
        if not access_permits(resolve_project_access(user, project), Action.WRITE):
            raise PermissionDenied(
                "You must have Editor access to this project to add documents to it."
            )

        serializer.save(created_by=user, project=project)


class DocumentRetrieveUpdateDestroyAPIView(
    SoftDeleteMixin, generics.RetrieveUpdateDestroyAPIView
):
    """Retrieve/update/soft-delete a document. Access resolves via
    ``DocumentPermission``, falling back to the parent project's
    ``ProjectPermission``: read needs Viewer, write Editor, delete Owner."""

    serializer_class = DocumentSerializer
    permission_classes = (IsAuthenticated, HasDocumentAccess, HasActiveSubscription)

    def get_queryset(self):
        return Document.objects.for_organization(self.request.user.organization)


class DocumentRestoreAPIView(APIView):
    """Reverses a soft-delete. Unlike ``ProjectRestoreAPIView`` (admin-only),
    document creation isn't admin-gated, so restoring requires the same
    Owner-level access that deleting it did."""

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


class ProjectShareAPIView(mixins.ListModelMixin, generics.GenericAPIView):
    """Lists a project's ``ProjectPermission`` grants, or grants/updates one
    for a target user - Owner-level access required. Granting an already-
    permitted user updates their level in place; each grant emails the
    target user."""

    serializer_class = ProjectPermissionSerializer

    def _get_project(self):
        return _get_org_scoped_or_404(
            Project, self.request.user.organization, self.kwargs["pk"]
        )

    def get_queryset(self):
        project = self._get_project()
        _check_can_share(self.request.user, project, "project", resolve_project_access)
        return ProjectPermission.objects.filter(project=project).order_by("user_id")

    @extend_schema(responses={200: ProjectPermissionSerializer(many=True)})
    def get(self, request, pk):
        return self.list(request)

    @extend_schema(
        request=ShareSerializer, responses={200: ProjectPermissionSerializer}
    )
    def post(self, request, pk):
        project = self._get_project()
        _check_can_share(request.user, project, "project", resolve_project_access)

        serializer = ShareSerializer(
            data=request.data, context={"organization": project.organization}
        )
        serializer.is_valid(raise_exception=True)

        permission, _ = ProjectPermission.objects.update_or_create(
            project=project,
            user=serializer.validated_data["user"],
            defaults={"access_level": serializer.validated_data["access_level"]},
        )
        send_project_shared_email_task.delay(permission.pk)

        return Response(ProjectPermissionSerializer(permission).data)


class ProjectShareRevokeAPIView(generics.DestroyAPIView):
    """Revokes a ``ProjectPermission`` outright (row deletion, not a
    soft-delete). Owner-level access required; refuses to remove the
    project's last remaining Owner."""

    @extend_schema(request=None, responses={204: None})
    def delete(self, request, *args, **kwargs):
        return self.destroy(request, *args, **kwargs)

    def get_object(self):
        project = _get_org_scoped_or_404(
            Project, self.request.user.organization, self.kwargs["pk"]
        )
        _check_can_share(self.request.user, project, "project", resolve_project_access)

        permission = get_object_or_404(
            ProjectPermission, project=project, user_id=self.kwargs["user_id"]
        )
        _ensure_not_last_owner(permission, ProjectPermission, "project", project)

        return permission


class DocumentShareAPIView(mixins.ListModelMixin, generics.GenericAPIView):
    """Lists a document's ``DocumentPermission`` grants, or grants/updates
    one for a target user - same convention as ``ProjectShareAPIView``,
    Owner-level access resolved via the usual fallback to ``ProjectPermission``."""

    serializer_class = DocumentPermissionSerializer

    def _get_document(self):
        return _get_org_scoped_or_404(
            Document, self.request.user.organization, self.kwargs["pk"]
        )

    def get_queryset(self):
        document = self._get_document()
        _check_can_share(self.request.user, document, "document", resolve_access)
        return DocumentPermission.objects.filter(document=document).order_by("user_id")

    @extend_schema(responses={200: DocumentPermissionSerializer(many=True)})
    def get(self, request, pk):
        return self.list(request)

    @extend_schema(
        request=ShareSerializer, responses={200: DocumentPermissionSerializer}
    )
    def post(self, request, pk):
        document = self._get_document()
        _check_can_share(request.user, document, "document", resolve_access)

        serializer = ShareSerializer(
            data=request.data,
            context={"organization": document.project.organization},
        )
        serializer.is_valid(raise_exception=True)

        permission, _ = DocumentPermission.objects.update_or_create(
            document=document,
            user=serializer.validated_data["user"],
            defaults={"access_level": serializer.validated_data["access_level"]},
        )
        send_document_shared_email_task.delay(permission.pk)

        return Response(DocumentPermissionSerializer(permission).data)


class DocumentShareRevokeAPIView(generics.DestroyAPIView):
    """Revokes a ``DocumentPermission`` outright (row deletion, not a
    soft-delete); access then falls back to the parent ``ProjectPermission``.
    Owner-level access required; refuses to remove the document's last Owner."""

    @extend_schema(request=None, responses={204: None})
    def delete(self, request, *args, **kwargs):
        return self.destroy(request, *args, **kwargs)

    def get_object(self):
        document = _get_org_scoped_or_404(
            Document, self.request.user.organization, self.kwargs["pk"]
        )
        _check_can_share(self.request.user, document, "document", resolve_access)

        permission = get_object_or_404(
            DocumentPermission, document=document, user_id=self.kwargs["user_id"]
        )
        _ensure_not_last_owner(permission, DocumentPermission, "document", document)

        return permission
