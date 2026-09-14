from django.db import transaction
from django.http import Http404
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema
from rest_framework import generics, mixins, status
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.filters import SearchFilter
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
    """Lists the project's current ``ProjectPermission`` grants, or grants/
    updates one for a target user posted in the body. Only a caller with
    Owner-level access may view or change sharing (``Action.RESHARE``);
    everyone else gets ``403``. Granting a user who already has a permission
    updates their existing ``AccessLevel`` in place (``update_or_create``)
    rather than erroring - re-share and grant are the same operation here.
    Each successful grant/re-share emails the target user their new access
    level.
    """

    serializer_class = ProjectPermissionSerializer

    def _get_project(self):
        return get_object_or_404(
            Project.objects.for_organization(self.request.user.organization),
            pk=self.kwargs["pk"],
        )

    def _check_can_share(self, project):
        if not access_permits(
            resolve_project_access(self.request.user, project), Action.RESHARE
        ):
            raise PermissionDenied(
                "You must have Owner access to this project to share it."
            )

    def get_queryset(self):
        project = self._get_project()
        self._check_can_share(project)
        return ProjectPermission.objects.filter(project=project).order_by("user_id")

    @extend_schema(responses={200: ProjectPermissionSerializer(many=True)})
    def get(self, request, pk):
        return self.list(request)

    @extend_schema(
        request=ShareSerializer, responses={200: ProjectPermissionSerializer}
    )
    def post(self, request, pk):
        project = self._get_project()
        self._check_can_share(project)

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


class ProjectShareRevokeAPIView(APIView):
    """Revokes a user's ``ProjectPermission`` outright (row deletion, not a
    soft-delete - permissions don't inherit ``TimeStampedModel``). Requires
    the same Owner-level ``Action.RESHARE`` access as granting one. Refuses
    to remove the project's last remaining Owner-level grant, regardless of
    who holds it or who's revoking it, so a project can never end up with
    nobody able to manage its sharing.
    """

    @extend_schema(request=None, responses={204: None})
    def delete(self, request, pk, user_id):
        project = get_object_or_404(
            Project.objects.for_organization(request.user.organization), pk=pk
        )
        if not access_permits(
            resolve_project_access(request.user, project), Action.RESHARE
        ):
            raise PermissionDenied(
                "You must have Owner access to this project to share it."
            )

        permission = ProjectPermission.objects.filter(
            project=project, user_id=user_id
        ).first()
        if not permission:
            raise Http404

        if permission.access_level == AccessLevel.OWNER:
            owner_count = ProjectPermission.objects.filter(
                project=project, access_level=AccessLevel.OWNER
            ).count()
            if owner_count <= 1:
                raise ValidationError(
                    {"detail": "Cannot revoke the project's last Owner."}
                )

        permission.delete()

        return Response(status=status.HTTP_204_NO_CONTENT)


class DocumentShareAPIView(mixins.ListModelMixin, generics.GenericAPIView):
    """Lists the document's current ``DocumentPermission`` grants, or grants/
    updates one for a target user posted in the body. Access is resolved the
    usual way (``DocumentPermission`` first, falling back to the parent
    project's ``ProjectPermission``); only a caller whose resolved level
    permits ``Action.RESHARE`` (Owner) may view or change sharing. Granting a
    user who already has a ``DocumentPermission`` updates it in place
    (``update_or_create``), the same grant/re-share convention as
    ``ProjectShareAPIView``. Each successful grant/re-share emails the target
    user their new access level.
    """

    serializer_class = DocumentPermissionSerializer

    def _get_document(self):
        return get_object_or_404(
            Document.objects.for_organization(self.request.user.organization),
            pk=self.kwargs["pk"],
        )

    def _check_can_share(self, document):
        if not access_permits(
            resolve_access(self.request.user, document), Action.RESHARE
        ):
            raise PermissionDenied(
                "You must have Owner access to this document to share it."
            )

    def get_queryset(self):
        document = self._get_document()
        self._check_can_share(document)
        return DocumentPermission.objects.filter(document=document).order_by("user_id")

    @extend_schema(responses={200: DocumentPermissionSerializer(many=True)})
    def get(self, request, pk):
        return self.list(request)

    @extend_schema(
        request=ShareSerializer, responses={200: DocumentPermissionSerializer}
    )
    def post(self, request, pk):
        document = self._get_document()
        self._check_can_share(document)

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


class DocumentShareRevokeAPIView(APIView):
    """Revokes a user's ``DocumentPermission`` outright (row deletion, not a
    soft-delete). Once removed, access resolution falls back to the user's
    ``ProjectPermission`` on the parent project, per the usual resolution
    order. Requires the same Owner-level ``Action.RESHARE`` access as
    granting one. Refuses to remove the document's last remaining
    Owner-level ``DocumentPermission`` override, the same invariant
    ``ProjectShareRevokeAPIView`` enforces at the project level - this
    protects the document's own override table, independent of whatever
    Owner access a parent ``ProjectPermission`` might still grant.
    """

    @extend_schema(request=None, responses={204: None})
    def delete(self, request, pk, user_id):
        document = get_object_or_404(
            Document.objects.for_organization(request.user.organization), pk=pk
        )
        if not access_permits(resolve_access(request.user, document), Action.RESHARE):
            raise PermissionDenied(
                "You must have Owner access to this document to share it."
            )

        permission = DocumentPermission.objects.filter(
            document=document, user_id=user_id
        ).first()
        if not permission:
            raise Http404

        if permission.access_level == AccessLevel.OWNER:
            owner_count = DocumentPermission.objects.filter(
                document=document, access_level=AccessLevel.OWNER
            ).count()
            if owner_count <= 1:
                raise ValidationError(
                    {"detail": "Cannot revoke the document's last Owner."}
                )

        permission.delete()

        return Response(status=status.HTTP_204_NO_CONTENT)
