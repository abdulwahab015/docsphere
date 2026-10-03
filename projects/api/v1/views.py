from django.contrib.auth import get_user_model
from django.db import transaction
from drf_spectacular.utils import (
    OpenApiParameter,
    OpenApiResponse,
    extend_schema,
    extend_schema_view,
)
from rest_framework import generics, mixins
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.filters import SearchFilter
from rest_framework.generics import get_object_or_404
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from core.permissions import HasActiveSubscription
from projects.api.v1.mixins import SoftDeleteMixin
from projects.api.v1.serializers import (
    DocumentAccessRequestSerializer,
    DocumentCreateSerializer,
    DocumentPermissionSerializer,
    DocumentSerializer,
    ProjectPermissionSerializer,
    ProjectSerializer,
    ShareSerializer,
    SoleOwnershipSerializer,
)
from projects.choices import AccessLevel, AccessRequestStatus, Action
from projects.managers import outside_trashed_projects
from projects.models import (
    Document,
    DocumentAccessRequest,
    DocumentPermission,
    Project,
    ProjectPermission,
)
from projects.permissions import (
    HasDocumentAccess,
    HasProjectAccess,
    access_permits,
    check_can_share,
    resolve_access,
    resolve_project_access,
)
from projects.tasks import (
    send_access_request_approved_email_task,
    send_access_request_created_email_task,
    send_access_request_denied_email_task,
    send_document_shared_email_task,
    send_project_shared_email_task,
)
from projects.validators import ensure_not_last_owner
from users.permissions import IsOrganizationAdmin

User = get_user_model()

DOCUMENT_IN_TRASHED_PROJECT_MESSAGE = (
    "This document's project is in the trash. Ask an organization admin to "
    "restore the project first."
)


def _grant_creator_ownership(permission_model, resource_field, resource, user):
    """Creates an Owner-level permission row for a newly created resource's
    creator - the same pattern for both Project and Document creation - and
    records that level on the instance the way ``visible_to`` would have
    annotated it, so the create response needn't re-query it."""
    permission_model.objects.create(
        **{resource_field: resource, "user": user, "access_level": AccessLevel.OWNER}
    )
    resource.user_access_level = AccessLevel.OWNER


def _grant_access(permission_model, resource_field, resource, user, access_level):
    """Gives ``user`` ``access_level`` on ``resource``, updating an existing
    grant in place. Lowering the resource's last Owner is refused, the same
    as revoking them."""
    existing = permission_model.objects.filter(
        user=user, **{resource_field: resource}
    ).first()
    if existing and access_level != AccessLevel.OWNER:
        ensure_not_last_owner(
            existing, permission_model, resource_field, resource, verb="downgrade"
        )

    permission, _ = permission_model.objects.update_or_create(
        user=user, defaults={"access_level": access_level}, **{resource_field: resource}
    )
    return permission


def _filter_by_id_param(queryset, request, param, field):
    """Narrows ``queryset`` to ``field`` = the ``?param=`` id when one is
    given; a non-numeric value matches nothing rather than erroring."""
    value = request.query_params.get(param)
    if not value:
        return queryset
    if not value.isdigit():
        return queryset.none()
    return queryset.filter(**{field: value})


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
        return (
            Project.objects.visible_to(self.request.user)
            .select_related("created_by")
            .order_by("name")
        )

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
            _grant_creator_ownership(
                ProjectPermission, "project", project, self.request.user
            )


class ProjectRetrieveUpdateDestroyAPIView(
    SoftDeleteMixin, generics.RetrieveUpdateDestroyAPIView
):
    """Retrieve/update/soft-delete a project. A project outside the
    requester's organization, or a private one they have no resolvable
    access to, is a 404 either way; one they can see but can't act on at the
    requested level (read needs Viewer, write Editor, delete Owner) is a
    403."""

    serializer_class = ProjectSerializer
    permission_classes = (IsAuthenticated, HasProjectAccess, HasActiveSubscription)

    def get_queryset(self):
        return Project.objects.visible_to(self.request.user).select_related(
            "created_by"
        )

    def perform_update(self, serializer):
        if "visibility" in serializer.validated_data:
            level = resolve_project_access(self.request.user, serializer.instance)
            if not access_permits(level, Action.RESHARE):
                raise PermissionDenied(
                    "You must have Owner access to this project to change its visibility."
                )
        serializer.save()


class ProjectRestoreAPIView(APIView):
    """Reverses a soft-delete. Admin-only, like project creation - not gated
    on the project's own ProjectPermission rows. Cross-organization and
    already-active projects are both a 404."""

    permission_classes = [IsOrganizationAdmin, HasActiveSubscription]

    @extend_schema(request=None, responses={200: ProjectSerializer})
    def post(self, request, pk):
        project = get_object_or_404(
            Project.objects.inactive_for_organization(request.user.organization)
            .with_access_level(request.user)
            .select_related("created_by"),
            pk=pk,
        )
        project.is_active = True
        project.save(update_fields=["is_active"])

        return Response(ProjectSerializer(project, context={"request": request}).data)


@extend_schema_view(
    get=extend_schema(
        parameters=[
            OpenApiParameter(
                "project",
                int,
                description="Only documents filed under this project.",
            )
        ]
    ),
    post=extend_schema(
        request=DocumentCreateSerializer, responses={201: DocumentSerializer}
    ),
)
class DocumentListCreateAPIView(generics.ListCreateAPIView):
    """Lists the org's documents (``?search=`` matches title, ``?project=``
    narrows to one project); creates one either under a project the caller has
    at least Editor access to, or - with no ``project`` given - as a personal
    document any org member may create. The creator always becomes Owner."""

    serializer_class = DocumentSerializer
    filter_backends = (SearchFilter,)
    search_fields = ("title",)

    def get_queryset(self):
        queryset = Document.objects.visible_to(self.request.user).select_related(
            "created_by"
        )
        return _filter_by_id_param(
            queryset, self.request, "project", "project_id"
        ).order_by("title")

    def perform_create(self, serializer):
        user = self.request.user
        organization = user.organization
        if not organization:
            raise ValidationError(
                {"detail": "You must belong to an organization to create a document."}
            )

        project = None
        project_id = self.request.data.get("project")
        if project_id:
            project = get_object_or_404(Project.objects.visible_to(user), pk=project_id)
            if not access_permits(resolve_project_access(user, project), Action.WRITE):
                raise PermissionDenied(
                    "You must have Editor access to this project to add documents to it."
                )

        with transaction.atomic():
            document = serializer.save(
                created_by=user, organization=organization, project=project
            )
            _grant_creator_ownership(DocumentPermission, "document", document, user)


class DocumentRetrieveUpdateDestroyAPIView(
    SoftDeleteMixin, generics.RetrieveUpdateDestroyAPIView
):
    """Retrieve/update/soft-delete a document. Access resolves via
    ``DocumentPermission`` alone - explicit grant, else implicit Viewer if the
    document is public, else nothing: read needs Viewer, write Editor, delete
    Owner. A document outside the requester's organization, or a private one
    they have no resolvable access to, is a 404 either way; one they can see
    but can't act on at the requested level is a 403."""

    serializer_class = DocumentSerializer
    permission_classes = (IsAuthenticated, HasDocumentAccess, HasActiveSubscription)

    def get_queryset(self):
        return Document.objects.visible_to(self.request.user).select_related(
            "created_by"
        )

    def perform_update(self, serializer):
        if "visibility" in serializer.validated_data:
            level = resolve_access(self.request.user, serializer.instance)
            if not access_permits(level, Action.RESHARE):
                raise PermissionDenied(
                    "You must have Owner access to this document to change its visibility."
                )
        serializer.save()


class DocumentRestoreAPIView(APIView):
    """Reverses a soft-delete. Unlike ``ProjectRestoreAPIView`` (admin-only),
    document creation isn't admin-gated, so restoring requires the same
    Owner-level access that deleting it did. A document whose project is in
    the trash can't be restored on its own - it would stay hidden."""

    @extend_schema(
        request=None,
        responses={
            200: DocumentSerializer,
            400: OpenApiResponse(description="The document's project is in the trash."),
        },
    )
    def post(self, request, pk):
        document = get_object_or_404(
            Document.objects.inactive_for_organization(request.user.organization)
            .with_access_level(request.user)
            .select_related("created_by", "project"),
            pk=pk,
        )
        if not access_permits(document.user_access_level, Action.DELETE):
            raise PermissionDenied(
                "You must have Owner access to this document to restore it."
            )
        # Restored on its own, it would stay hidden with its trashed project.
        if document.project and not document.project.is_active:
            raise ValidationError({"detail": DOCUMENT_IN_TRASHED_PROJECT_MESSAGE})

        document.is_active = True
        document.save(update_fields=["is_active"])

        return Response(DocumentSerializer(document, context={"request": request}).data)


class ProjectShareAPIView(mixins.ListModelMixin, generics.GenericAPIView):
    """Lists a project's ``ProjectPermission`` grants, or grants/updates one
    for a target user - Owner-level access required. Granting an already-
    permitted user updates their level in place (never lowering the last
    Owner); each grant emails the target user."""

    serializer_class = ProjectPermissionSerializer

    def _get_project(self):
        return get_object_or_404(
            Project.objects.visible_to(self.request.user),
            pk=self.kwargs["pk"],
        )

    def get_queryset(self):
        project = self._get_project()
        check_can_share(self.request.user, project, "project", resolve_project_access)
        return (
            ProjectPermission.objects.filter(project=project)
            .select_related("user")
            .order_by("user_id")
        )

    @extend_schema(responses={200: ProjectPermissionSerializer(many=True)})
    def get(self, request, pk):
        return self.list(request)

    @extend_schema(
        request=ShareSerializer, responses={200: ProjectPermissionSerializer}
    )
    def post(self, request, pk):
        project = self._get_project()
        check_can_share(request.user, project, "project", resolve_project_access)

        serializer = ShareSerializer(
            data=request.data, context={"organization": project.organization}
        )
        serializer.is_valid(raise_exception=True)

        permission = _grant_access(
            ProjectPermission, "project", project, **serializer.validated_data
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
        project = get_object_or_404(
            Project.objects.visible_to(self.request.user),
            pk=self.kwargs["pk"],
        )
        check_can_share(self.request.user, project, "project", resolve_project_access)

        permission = get_object_or_404(
            ProjectPermission, project=project, user_id=self.kwargs["user_id"]
        )
        ensure_not_last_owner(permission, ProjectPermission, "project", project)

        return permission


class DocumentShareAPIView(mixins.ListModelMixin, generics.GenericAPIView):
    """Lists a document's ``DocumentPermission`` grants, or grants/updates
    one for a target user - same convention as ``ProjectShareAPIView``.
    Owner-level access is resolved via ``resolve_access`` (explicit grant, or
    implicit Viewer on a public document - never enough to share, since
    sharing needs ``Action.RESHARE``)."""

    serializer_class = DocumentPermissionSerializer

    def _get_document(self):
        return get_object_or_404(
            Document.objects.visible_to(self.request.user),
            pk=self.kwargs["pk"],
        )

    def get_queryset(self):
        document = self._get_document()
        check_can_share(self.request.user, document, "document", resolve_access)
        return (
            DocumentPermission.objects.filter(document=document)
            .select_related("user")
            .order_by("user_id")
        )

    @extend_schema(responses={200: DocumentPermissionSerializer(many=True)})
    def get(self, request, pk):
        return self.list(request)

    @extend_schema(
        request=ShareSerializer, responses={200: DocumentPermissionSerializer}
    )
    def post(self, request, pk):
        document = self._get_document()
        check_can_share(request.user, document, "document", resolve_access)

        serializer = ShareSerializer(
            data=request.data,
            context={"organization": document.organization},
        )
        serializer.is_valid(raise_exception=True)

        permission = _grant_access(
            DocumentPermission, "document", document, **serializer.validated_data
        )
        send_document_shared_email_task.delay(permission.pk)

        return Response(DocumentPermissionSerializer(permission).data)


class DocumentShareRevokeAPIView(generics.DestroyAPIView):
    """Revokes a ``DocumentPermission`` outright (row deletion, not a
    soft-delete); access then falls back to implicit Viewer if the document is
    public, or to nothing. Owner-level access required; refuses to remove the
    document's last Owner."""

    @extend_schema(request=None, responses={204: None})
    def delete(self, request, *args, **kwargs):
        return self.destroy(request, *args, **kwargs)

    def get_object(self):
        document = get_object_or_404(
            Document.objects.visible_to(self.request.user),
            pk=self.kwargs["pk"],
        )
        check_can_share(self.request.user, document, "document", resolve_access)

        permission = get_object_or_404(
            DocumentPermission, document=document, user_id=self.kwargs["user_id"]
        )
        ensure_not_last_owner(permission, DocumentPermission, "document", document)

        return permission


class DocumentAccessRequestListCreateAPIView(generics.ListCreateAPIView):
    """Lists a document's pending access requests (Owner-only), or files a new
    one. A Viewer who can see the document - typically because it's public -
    may request Editor access; a document the caller can't resolve any access
    to is a 404, same as everywhere else private resources are hidden."""

    serializer_class = DocumentAccessRequestSerializer

    def _get_document(self):
        return get_object_or_404(
            Document.objects.visible_to(self.request.user),
            pk=self.kwargs["pk"],
        )

    def get_queryset(self):
        document = self._get_document()
        check_can_share(self.request.user, document, "document", resolve_access)
        return (
            DocumentAccessRequest.objects.filter(
                document=document, status=AccessRequestStatus.PENDING
            )
            .select_related("document", "requested_by", "reviewed_by")
            .order_by("created")
        )

    def perform_create(self, serializer):
        user = self.request.user
        document = self._get_document()
        level = resolve_access(user, document)

        if level != AccessLevel.VIEWER:
            raise ValidationError(
                {"detail": "You already have sufficient access to this document."}
            )

        if DocumentAccessRequest.objects.filter(
            document=document, requested_by=user, status=AccessRequestStatus.PENDING
        ).exists():
            raise ValidationError(
                {"detail": "You already have a pending request for this document."}
            )

        access_request = serializer.save(document=document, requested_by=user)
        send_access_request_created_email_task.delay(access_request.pk)


def _get_pending_access_request_to_review(user, document_id, request_id):
    """The pending access request an Owner approves or denies. The document
    must be visible to them (else 404) and theirs to share (else 403)."""
    document = get_object_or_404(Document.objects.visible_to(user), pk=document_id)
    check_can_share(user, document, "document", resolve_access)

    return get_object_or_404(
        DocumentAccessRequest.objects.select_related("document", "requested_by"),
        pk=request_id,
        document=document,
        status=AccessRequestStatus.PENDING,
    )


class DocumentAccessRequestApproveAPIView(APIView):
    """Owner-only. Upgrades the requester to Editor and marks the request
    approved, inside one transaction. Approval only ever raises access: a
    requester who has been given Editor or Owner since asking keeps it."""

    @extend_schema(request=None, responses={200: DocumentAccessRequestSerializer})
    def post(self, request, pk, request_id):
        access_request = _get_pending_access_request_to_review(
            request.user, pk, request_id
        )

        with transaction.atomic():
            permission, _ = DocumentPermission.objects.get_or_create(
                document=access_request.document,
                user=access_request.requested_by,
                defaults={"access_level": AccessLevel.EDITOR},
            )
            if permission.access_level == AccessLevel.VIEWER:
                permission.access_level = AccessLevel.EDITOR
                permission.save(update_fields=["access_level"])
            access_request.status = AccessRequestStatus.APPROVED
            access_request.reviewed_by = request.user
            access_request.save(update_fields=["status", "reviewed_by", "modified"])

        send_access_request_approved_email_task.delay(access_request.pk)

        return Response(DocumentAccessRequestSerializer(access_request).data)


class DocumentAccessRequestDenyAPIView(APIView):
    """Owner-only. Marks the request denied without touching permissions."""

    @extend_schema(request=None, responses={200: DocumentAccessRequestSerializer})
    def post(self, request, pk, request_id):
        access_request = _get_pending_access_request_to_review(
            request.user, pk, request_id
        )
        access_request.status = AccessRequestStatus.DENIED
        access_request.reviewed_by = request.user
        access_request.save(update_fields=["status", "reviewed_by", "modified"])

        send_access_request_denied_email_task.delay(access_request.pk)

        return Response(DocumentAccessRequestSerializer(access_request).data)


class ProjectTrashListAPIView(generics.ListAPIView):
    """Soft-deleted projects in the admin's organization, most recently
    deleted first - the list ``ProjectRestoreAPIView`` restores from, and
    admin-only for the same reason."""

    serializer_class = ProjectSerializer
    permission_classes = [IsOrganizationAdmin, HasActiveSubscription]

    def get_queryset(self):
        user = self.request.user
        return (
            Project.objects.inactive_for_organization(user.organization)
            .with_access_level(user)
            .select_related("created_by")
            .order_by("-modified")
        )


class DocumentTrashListAPIView(generics.ListAPIView):
    """Soft-deleted documents the caller owns, most recently deleted first -
    exactly the ones ``DocumentRestoreAPIView`` would let them restore."""

    serializer_class = DocumentSerializer

    def get_queryset(self):
        user = self.request.user
        return (
            Document.objects.inactive_for_organization(user.organization)
            .with_access_level(user)
            .filter(user_access_level=AccessLevel.OWNER)
            .select_related("created_by")
            .order_by("-modified")
        )


@extend_schema_view(
    get=extend_schema(
        parameters=[
            OpenApiParameter(
                "document",
                int,
                description="Only requests for this document.",
            )
        ]
    )
)
class MyDocumentAccessRequestListAPIView(generics.ListAPIView):
    """The caller's own access requests in every status, newest first, so a
    requester can see whether theirs was approved or denied (``?document=``
    narrows to one document). Requests on documents since soft-deleted, or
    hidden in a trashed project, are left out."""

    serializer_class = DocumentAccessRequestSerializer

    def get_queryset(self):
        user = self.request.user
        queryset = DocumentAccessRequest.objects.filter(
            outside_trashed_projects("document__"),
            requested_by=user,
            document__organization=user.organization,
            document__is_active=True,
        )
        return (
            _filter_by_id_param(queryset, self.request, "document", "document_id")
            .select_related("document", "requested_by", "reviewed_by")
            .order_by("-created")
        )


class IncomingDocumentAccessRequestListAPIView(generics.ListAPIView):
    """Pending access requests across every active document the caller is an
    Owner of - an inbox, so an Owner needn't open each document to find
    them. Approve/deny still go through the per-document endpoints."""

    serializer_class = DocumentAccessRequestSerializer

    def get_queryset(self):
        user = self.request.user
        owned_documents = Document.objects.for_organization(user.organization).filter(
            permissions__user=user, permissions__access_level=AccessLevel.OWNER
        )
        return (
            DocumentAccessRequest.objects.filter(
                document__in=owned_documents, status=AccessRequestStatus.PENDING
            )
            .select_related("document", "requested_by", "reviewed_by")
            .order_by("created")
        )


class SoleOwnershipAPIView(APIView):
    """What deactivating a member would leave unmanaged: the live projects and
    documents in the admin's organization that the member is the only active
    Owner of. Someone outside the organization is indistinguishable from a
    missing user."""

    permission_classes = [IsOrganizationAdmin, HasActiveSubscription]

    @extend_schema(responses=SoleOwnershipSerializer)
    def get(self, request, user_id):
        organization = request.user.organization
        member = get_object_or_404(
            User.objects.filter(organization=organization), pk=user_id
        )
        counts = {
            "projects": Project.objects.for_organization(organization)
            .solely_owned_by(member)
            .count(),
            "documents": Document.objects.for_organization(organization)
            .solely_owned_by(member)
            .count(),
        }
        return Response(SoleOwnershipSerializer(counts).data)
