from django.contrib.auth import get_user_model
from django.db import transaction
from django.http import FileResponse
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import (
    OpenApiParameter,
    OpenApiResponse,
    extend_schema,
    extend_schema_view,
)
from rest_framework import generics, mixins, status
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.filters import SearchFilter
from rest_framework.generics import get_object_or_404
from rest_framework.parsers import MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from audit.choices import AuditVerb
from audit.models import AuditEvent
from core.permissions import HasActiveSubscription
from notifications.choices import NotificationVerb
from notifications.models import Notification
from projects.api.v1.mixins import SoftDeleteMixin
from projects.api.v1.serializers import (
    AttachmentSerializer,
    AttachmentUploadSerializer,
    DocumentAccessRequestSerializer,
    DocumentCreateSerializer,
    DocumentListSerializer,
    DocumentPermissionSerializer,
    DocumentSerializer,
    DocumentVersionDetailSerializer,
    DocumentVersionSerializer,
    ProjectPermissionSerializer,
    ProjectSerializer,
    ShareSerializer,
    SoleOwnershipSerializer,
)
from projects.choices import AccessLevel, AccessRequestStatus, Action
from projects.constants import GIGABYTE, ORGANIZATION_ATTACHMENT_QUOTA_BYTES
from projects.exceptions import EditConflict
from projects.managers import outside_trashed_projects
from projects.models import (
    Attachment,
    Document,
    DocumentAccessRequest,
    DocumentPermission,
    DocumentVersion,
    Project,
    ProjectPermission,
)
from projects.permissions import (
    HasDocumentAccess,
    HasProjectAccess,
    access_permits,
    active_owners,
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
from users.permissions import (
    HasVerifiedEmail,
    IsOrganizationAdmin,
    MeetsTwoFactorRequirement,
)

User = get_user_model()

# The fields whose change makes a new revision of a document.
DOCUMENT_TEXT_FIELDS = ("title", "content")

ATTACHING_NEEDS_EDITOR_MESSAGE = (
    "You must have Editor access to this document to attach or delete files."
)
ATTACHMENT_QUOTA_MESSAGE = (
    f"Your organization has used its {ORGANIZATION_ATTACHMENT_QUOTA_BYTES // GIGABYTE} "
    "GB for attached files. Delete some (files of documents in the trash count "
    "too) to make room."
)

HISTORY_NEEDS_EDITOR_MESSAGE = (
    "You must have Editor access to this document to see its history."
)

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


def _visible_document(request, pk):
    """The document ``pk`` if the caller can open it, annotated with their
    access level; otherwise - another organization's, private to others,
    deleted, in a trashed project - a 404, never revealing it exists."""
    return get_object_or_404(Document.objects.visible_to(request.user), pk=pk)


def _lock_access(resource):
    """Locks the resource's row until the transaction ends, so changes to who
    may access it happen one at a time. Otherwise two Owners lowering or
    removing each other at once would each still see the other as an Owner,
    both pass the last-Owner check, and leave the resource with none."""
    type(resource).objects.select_for_update().get(pk=resource.pk)


def _grant_access(
    actor, permission_model, resource_field, resource, user, access_level
):
    """``actor`` gives ``user`` ``access_level`` on ``resource``, updating an
    existing grant in place, and returns ``(permission, changed)`` -
    unchanged when they already had that level. Lowering the resource's last
    Owner is refused, the same as revoking them. Call inside a transaction,
    after ``_lock_access``."""
    existing = permission_model.objects.filter(
        user=user, **{resource_field: resource}
    ).first()
    if existing and existing.access_level == access_level:
        return existing, False
    if existing and access_level != AccessLevel.OWNER:
        ensure_not_last_owner(
            existing, permission_model, resource_field, resource, verb="downgrade"
        )

    permission, _ = permission_model.objects.update_or_create(
        user=user, defaults={"access_level": access_level}, **{resource_field: resource}
    )
    if existing:
        AuditEvent.objects.record(
            actor,
            AuditVerb.ACCESS_CHANGED,
            target_user=user,
            access_level=access_level,
            previous_access_level=existing.access_level,
            **{resource_field: resource},
        )
    else:
        AuditEvent.objects.record(
            actor,
            AuditVerb.ACCESS_GRANTED,
            target_user=user,
            access_level=access_level,
            **{resource_field: resource},
        )
    Notification.objects.notify(
        [user],
        actor,
        (
            NotificationVerb.ACCESS_CHANGED
            if existing
            else NotificationVerb.ACCESS_GRANTED
        ),
        access_level=access_level,
        **{resource_field: resource},
    )
    return permission, True


def _revoke_access(actor, permission_model, resource_field, resource, user_id):
    """``actor`` deletes ``user_id``'s grant on ``resource`` (a 404 if they
    have none), unless it's the resource's last active Owner."""
    with transaction.atomic():
        _lock_access(resource)
        permission = get_object_or_404(
            permission_model.objects.select_related("user"),
            user_id=user_id,
            **{resource_field: resource},
        )
        ensure_not_last_owner(permission, permission_model, resource_field, resource)
        permission.delete()
        AuditEvent.objects.record(
            actor,
            AuditVerb.ACCESS_REVOKED,
            target_user=permission.user,
            previous_access_level=permission.access_level,
            **{resource_field: resource},
        )


def _record_visibility_change(actor, resource_field, resource, previous_visibility):
    """Records that ``actor`` changed ``resource``'s visibility, if the save
    just made did. Call in the save's transaction."""
    if resource.visibility != previous_visibility:
        AuditEvent.objects.record(
            actor,
            AuditVerb.VISIBILITY_CHANGED,
            visibility=resource.visibility,
            **{resource_field: resource},
        )


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
            return [
                IsOrganizationAdmin(),
                HasVerifiedEmail(),
                MeetsTwoFactorRequirement(),
                HasActiveSubscription(),
            ]
        return [
            IsAuthenticated(),
            HasVerifiedEmail(),
            MeetsTwoFactorRequirement(),
            HasActiveSubscription(),
        ]

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
    permission_classes = (
        IsAuthenticated,
        HasVerifiedEmail,
        MeetsTwoFactorRequirement,
        HasProjectAccess,
        HasActiveSubscription,
    )

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

        previous_visibility = serializer.instance.visibility
        with transaction.atomic():
            project = serializer.save()
            _record_visibility_change(
                self.request.user, "project", project, previous_visibility
            )


class ProjectRestoreAPIView(APIView):
    """Reverses a soft-delete. Admin-only, like project creation - not gated
    on the project's own ProjectPermission rows. Cross-organization and
    already-active projects are both a 404."""

    permission_classes = [
        IsOrganizationAdmin,
        HasVerifiedEmail,
        MeetsTwoFactorRequirement,
        HasActiveSubscription,
    ]

    @extend_schema(request=None, responses={200: ProjectSerializer})
    def post(self, request, pk):
        project = get_object_or_404(
            Project.objects.inactive_for_organization(request.user.organization)
            .with_access_level(request.user)
            .select_related("created_by"),
            pk=pk,
        )
        with transaction.atomic():
            project.is_active = True
            project.save(update_fields=["is_active"])
            AuditEvent.objects.record(request.user, AuditVerb.RESTORED, project=project)

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
    """Lists the documents the caller can open (``?search=`` matches title and
    content, case-insensitively; ``?project=`` narrows to one project) without
    their content, but with an excerpt of where a search matched it; creates
    one either under a project the caller has at least Editor access to, or -
    with no ``project`` given - as a personal document any org member may
    create. The creator always becomes Owner."""

    filter_backends = (SearchFilter,)
    search_fields = ("title", "content")

    def get_serializer_class(self):
        if self.request.method == "POST":
            return DocumentSerializer
        return DocumentListSerializer

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["search_terms"] = SearchFilter().get_search_terms(self.request)
        return context

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
            DocumentVersion.objects.record(document, user)


_EDIT_CONFLICT = OpenApiResponse(
    description="`base_revision` is older than the document's revision: nothing "
    "was saved. The body has `detail`, `code` (`edit_conflict`) and the current "
    "`document`."
)


@extend_schema_view(
    put=extend_schema(responses={200: DocumentSerializer, 409: _EDIT_CONFLICT}),
    patch=extend_schema(responses={200: DocumentSerializer, 409: _EDIT_CONFLICT}),
)
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
    permission_classes = (
        IsAuthenticated,
        HasVerifiedEmail,
        MeetsTwoFactorRequirement,
        HasDocumentAccess,
        HasActiveSubscription,
    )

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

        previous_visibility = serializer.instance.visibility
        with transaction.atomic():
            self._save(serializer)
            _record_visibility_change(
                self.request.user, "document", serializer.instance, previous_visibility
            )

    def _save(self, serializer):
        """Saves the update, as a new revision and version when it changes
        the text - refused if it was based on an older revision. Call inside
        a transaction."""
        base_revision = serializer.validated_data.pop("base_revision", None)
        changes_text = any(
            field in serializer.validated_data
            and serializer.validated_data[field] != getattr(serializer.instance, field)
            for field in DOCUMENT_TEXT_FIELDS
        )
        if not base_revision and not changes_text:
            serializer.save()
            return

        # Locked, so two saves based on the same revision can't both pass the
        # check, and each text change gets a revision number of its own.
        current = (
            Document.objects.select_for_update(of=("self",))
            .select_related("created_by")
            .get(pk=serializer.instance.pk)
        )
        current.user_access_level = serializer.instance.user_access_level
        if base_revision and base_revision != current.revision:
            raise EditConflict(
                DocumentSerializer(current, context=self.get_serializer_context()).data
            )
        serializer.instance = current
        if changes_text:
            document = serializer.save(revision=current.revision + 1)
            DocumentVersion.objects.record(document, self.request.user)
        else:
            serializer.save()


def _document_for_history(request, pk):
    """The document ``pk`` if the caller may see its history: Editors and
    Owners. Viewers see only the current text - anything removed from it
    stays removed for them - so for them it's a 403; a document they can't
    open at all is a 404 as everywhere else."""
    document = _visible_document(request, pk)
    if not access_permits(document.user_access_level, Action.WRITE):
        raise PermissionDenied(HISTORY_NEEDS_EDITOR_MESSAGE)
    return document


class DocumentVersionListAPIView(generics.ListAPIView):
    """A document's versions, newest first - one per revision, the first
    being how it was created and the latest matching it now. Without their
    content; read one with ``DocumentVersionRetrieveAPIView``. Restoring one
    is an ordinary update with its title and content, which makes a new
    version."""

    serializer_class = DocumentVersionSerializer

    def get_queryset(self):
        document = _document_for_history(self.request, self.kwargs["pk"])
        return document.versions.select_related("created_by").order_by("-revision")


class DocumentVersionRetrieveAPIView(generics.RetrieveAPIView):
    """One version of a document, with its content."""

    serializer_class = DocumentVersionDetailSerializer

    def get_object(self):
        document = _document_for_history(self.request, self.kwargs["pk"])
        return get_object_or_404(
            document.versions.select_related("created_by"),
            revision=self.kwargs["revision"],
        )


def _document_for_attachments(request, pk, action):
    """The document ``pk`` if the caller may ``action`` its files: anyone who
    can open it may list and download them (``Action.READ``); attaching and
    deleting files (``Action.WRITE``) is for its Editors and Owners. A
    document they can't open is a 404, like everywhere else."""
    document = _visible_document(request, pk)
    if not access_permits(document.user_access_level, action):
        raise PermissionDenied(ATTACHING_NEEDS_EDITOR_MESSAGE)
    return document


def _lock_organization_of(document):
    """Locks the document's organization row until the transaction ends, so
    uploads to it are checked against its quota one at a time - two at once
    would otherwise both fit into the same free space."""
    organization_model = document._meta.get_field("organization").related_model
    organization_model.objects.select_for_update().get(pk=document.organization_id)


class DocumentAttachmentListCreateAPIView(generics.ListCreateAPIView):
    """A document's attached files, newest first, and attaching a new one -
    within the size limit, of an allowed kind (checked by content), and
    within the organization's storage quota."""

    serializer_class = AttachmentSerializer
    parser_classes = [MultiPartParser]

    def get_queryset(self):
        document = _document_for_attachments(
            self.request, self.kwargs["pk"], Action.READ
        )
        return document.attachments.select_related("uploaded_by").order_by(
            "-created", "-pk"
        )

    @extend_schema(
        request={"multipart/form-data": AttachmentUploadSerializer},
        responses={
            201: AttachmentSerializer,
            400: OpenApiResponse(
                description="Too large, not an allowed kind of file, or over the "
                "organization's storage quota."
            ),
        },
    )
    def post(self, request, pk):
        document = _document_for_attachments(request, pk, Action.WRITE)
        serializer = AttachmentUploadSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        upload = serializer.validated_data["file"]

        with transaction.atomic():
            _lock_organization_of(document)
            used = Attachment.objects.bytes_used_by(document.organization_id)
            if used + upload.size > ORGANIZATION_ATTACHMENT_QUOTA_BYTES:
                raise ValidationError({"detail": ATTACHMENT_QUOTA_MESSAGE})
            attachment = Attachment.objects.create(
                document=document,
                uploaded_by=request.user,
                file=upload,
                name=serializer.validated_data["name"],
                content_type=serializer.validated_data["content_type"],
                size=upload.size,
            )
            AuditEvent.objects.record(
                request.user,
                AuditVerb.ATTACHMENT_ADDED,
                document=document,
                file_name=attachment.name,
                size=attachment.size,
            )

        return Response(
            AttachmentSerializer(attachment).data, status=status.HTTP_201_CREATED
        )


class DocumentAttachmentDownloadAPIView(APIView):
    """One attached file, always as a download - never shown in the browser,
    which with ``nosniff`` never runs it either."""

    @extend_schema(responses={(200, "application/octet-stream"): OpenApiTypes.BINARY})
    def get(self, request, pk, attachment_id):
        document = _document_for_attachments(request, pk, Action.READ)
        attachment = get_object_or_404(document.attachments, pk=attachment_id)

        response = FileResponse(
            attachment.file.open("rb"),
            as_attachment=True,
            filename=attachment.name,
            content_type=attachment.content_type,
        )
        # Only for whoever may open the document: never kept by a shared cache.
        response["Cache-Control"] = "private, no-store"
        return response


class DocumentAttachmentDestroyAPIView(generics.DestroyAPIView):
    """Deletes an attached file, for the document's Editors and Owners."""

    def get_object(self):
        document = _document_for_attachments(
            self.request, self.kwargs["pk"], Action.WRITE
        )
        return get_object_or_404(document.attachments, pk=self.kwargs["attachment_id"])

    @extend_schema(responses={204: None})
    def delete(self, request, *args, **kwargs):
        return super().delete(request, *args, **kwargs)

    def perform_destroy(self, instance):
        """The row goes now; the stored file once that's committed, so a
        rolled-back delete never leaves a row pointing at nothing."""
        storage, name = instance.file.storage, instance.file.name
        with transaction.atomic():
            instance.delete()
            AuditEvent.objects.record(
                self.request.user,
                AuditVerb.ATTACHMENT_DELETED,
                document=instance.document,
                file_name=instance.name,
            )
        transaction.on_commit(lambda: storage.delete(name))


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

        with transaction.atomic():
            document.is_active = True
            document.save(update_fields=["is_active"])
            AuditEvent.objects.record(
                request.user, AuditVerb.RESTORED, document=document
            )

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

        with transaction.atomic():
            _lock_access(project)
            permission, changed = _grant_access(
                request.user,
                ProjectPermission,
                "project",
                project,
                **serializer.validated_data,
            )
        if changed:
            send_project_shared_email_task.delay(permission.pk)

        return Response(ProjectPermissionSerializer(permission).data)


class ProjectShareRevokeAPIView(APIView):
    """Revokes a ``ProjectPermission`` outright (row deletion, not a
    soft-delete). Owner-level access required; refuses to remove the
    project's last remaining Owner."""

    @extend_schema(request=None, responses={204: None})
    def delete(self, request, pk, user_id):
        project = get_object_or_404(Project.objects.visible_to(request.user), pk=pk)
        check_can_share(request.user, project, "project", resolve_project_access)
        _revoke_access(request.user, ProjectPermission, "project", project, user_id)
        return Response(status=status.HTTP_204_NO_CONTENT)


class DocumentShareAPIView(mixins.ListModelMixin, generics.GenericAPIView):
    """Lists a document's ``DocumentPermission`` grants, or grants/updates
    one for a target user - same convention as ``ProjectShareAPIView``.
    Owner-level access is resolved via ``resolve_access`` (explicit grant, or
    implicit Viewer on a public document - never enough to share, since
    sharing needs ``Action.RESHARE``)."""

    serializer_class = DocumentPermissionSerializer

    def _get_document(self):
        return _visible_document(self.request, self.kwargs["pk"])

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

        with transaction.atomic():
            _lock_access(document)
            permission, changed = _grant_access(
                request.user,
                DocumentPermission,
                "document",
                document,
                **serializer.validated_data,
            )
        if changed:
            send_document_shared_email_task.delay(permission.pk)

        return Response(DocumentPermissionSerializer(permission).data)


class DocumentShareRevokeAPIView(APIView):
    """Revokes a ``DocumentPermission`` outright (row deletion, not a
    soft-delete); access then falls back to implicit Viewer if the document is
    public, or to nothing. Owner-level access required; refuses to remove the
    document's last Owner."""

    @extend_schema(request=None, responses={204: None})
    def delete(self, request, pk, user_id):
        document = get_object_or_404(Document.objects.visible_to(request.user), pk=pk)
        check_can_share(request.user, document, "document", resolve_access)
        _revoke_access(request.user, DocumentPermission, "document", document, user_id)
        return Response(status=status.HTTP_204_NO_CONTENT)


class DocumentAccessRequestListCreateAPIView(generics.ListCreateAPIView):
    """Lists a document's pending access requests (Owner-only), or files a new
    one. A Viewer who can see the document - typically because it's public -
    may request Editor access; a document the caller can't resolve any access
    to is a 404, same as everywhere else private resources are hidden."""

    serializer_class = DocumentAccessRequestSerializer

    def _get_document(self):
        return _visible_document(self.request, self.kwargs["pk"])

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

        with transaction.atomic():
            access_request = serializer.save(document=document, requested_by=user)
            Notification.objects.notify(
                active_owners(document),
                user,
                NotificationVerb.ACCESS_REQUESTED,
                document=document,
            )
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
            AuditEvent.objects.record(
                request.user,
                AuditVerb.ACCESS_REQUEST_APPROVED,
                target_user=access_request.requested_by,
                document=access_request.document,
            )
            Notification.objects.notify(
                [access_request.requested_by],
                request.user,
                NotificationVerb.ACCESS_REQUEST_APPROVED,
                document=access_request.document,
            )

        send_access_request_approved_email_task.delay(access_request.pk)

        return Response(DocumentAccessRequestSerializer(access_request).data)


class DocumentAccessRequestDenyAPIView(APIView):
    """Owner-only. Marks the request denied without touching permissions."""

    @extend_schema(request=None, responses={200: DocumentAccessRequestSerializer})
    def post(self, request, pk, request_id):
        access_request = _get_pending_access_request_to_review(
            request.user, pk, request_id
        )
        with transaction.atomic():
            access_request.status = AccessRequestStatus.DENIED
            access_request.reviewed_by = request.user
            access_request.save(update_fields=["status", "reviewed_by", "modified"])
            AuditEvent.objects.record(
                request.user,
                AuditVerb.ACCESS_REQUEST_DENIED,
                target_user=access_request.requested_by,
                document=access_request.document,
            )
            Notification.objects.notify(
                [access_request.requested_by],
                request.user,
                NotificationVerb.ACCESS_REQUEST_DENIED,
                document=access_request.document,
            )

        send_access_request_denied_email_task.delay(access_request.pk)

        return Response(DocumentAccessRequestSerializer(access_request).data)


class ProjectTrashListAPIView(generics.ListAPIView):
    """Soft-deleted projects in the admin's organization, most recently
    deleted first - the list ``ProjectRestoreAPIView`` restores from, and
    admin-only for the same reason."""

    serializer_class = ProjectSerializer
    permission_classes = [
        IsOrganizationAdmin,
        HasVerifiedEmail,
        MeetsTwoFactorRequirement,
        HasActiveSubscription,
    ]

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

    permission_classes = [
        IsOrganizationAdmin,
        HasVerifiedEmail,
        MeetsTwoFactorRequirement,
        HasActiveSubscription,
    ]

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
