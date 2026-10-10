from django.contrib.auth import get_user_model
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from projects.attachments import UnsupportedFileError, attachment_content_type
from projects.choices import AccessLevel
from projects.constants import (
    MAX_ATTACHMENT_BYTES,
    MEGABYTE,
)
from projects.models import (
    Attachment,
    Document,
    DocumentAccessRequest,
    DocumentPermission,
    DocumentVersion,
    Project,
    ProjectPermission,
)
from projects.permissions import resolve_access, resolve_project_access
from projects.search import content_excerpt

User = get_user_model()


class AccessLevelModelSerializer(serializers.ModelSerializer):
    """Adds the requesting user's own read-only ``access_level`` on the
    resource, so a client knows which actions to offer without probing for
    403s - or ``null`` when they have none (an admin restoring a private
    project nobody granted them). Read from the ``user_access_level``
    annotation ``with_access_level`` adds; a resource loaded any other way is
    resolved with one extra query instead."""

    access_level = serializers.SerializerMethodField()

    resolve_access_fn = None

    @extend_schema_field(
        serializers.ChoiceField(choices=AccessLevel.choices, allow_null=True)
    )
    def get_access_level(self, resource):
        # An annotated ``None`` (no access) is a real answer, not a cue to
        # re-resolve - hence hasattr rather than a truthiness test.
        if hasattr(resource, "user_access_level"):
            return resource.user_access_level
        return self.resolve_access_fn(self.context["request"].user, resource)


class ProjectSerializer(AccessLevelModelSerializer):
    """``created_by`` and ``organization`` are always set server-side from the
    request and never accepted from the client. ``visibility`` is writable, but
    changing it on an existing project is Owner-only (enforced in the view)."""

    resolve_access_fn = staticmethod(resolve_project_access)

    created_by_email = serializers.EmailField(source="created_by.email", read_only=True)
    created_by_name = serializers.CharField(source="created_by.name", read_only=True)

    class Meta:
        model = Project
        fields = [
            "id",
            "name",
            "description",
            "visibility",
            "access_level",
            "created_by",
            "created_by_email",
            "created_by_name",
            "organization",
            "created",
            "modified",
        ]
        read_only_fields = [
            "id",
            "created_by",
            "organization",
            "created",
            "modified",
        ]

    def validate_name(self, value):
        """Enforce per-organization name uniqueness here so a collision returns
        400 rather than surfacing as an IntegrityError. Soft-deleted projects
        still occupy the name (the DB constraint is unconditional), so they're
        included in the check."""
        organization = self.context["request"].user.organization
        clashes = Project.objects.filter(organization=organization, name=value)

        if self.instance:
            clashes = clashes.exclude(pk=self.instance.pk)

        if clashes.exists():
            raise serializers.ValidationError(
                "A project with this name already exists in your organization."
            )
        return value


class DocumentSerializer(AccessLevelModelSerializer):
    """``created_by``, ``organization`` and ``project`` are always set server-side
    in the view (the latter after explicit org-scoped validation, and may be left
    unset entirely for a personal document) and never accepted from the client
    through this serializer. ``visibility`` is writable, but changing it on an
    existing document is Owner-only (enforced in the view)."""

    resolve_access_fn = staticmethod(resolve_access)

    created_by_email = serializers.EmailField(source="created_by.email", read_only=True)
    created_by_name = serializers.CharField(source="created_by.name", read_only=True)
    base_revision = serializers.IntegerField(
        min_value=1,
        required=False,
        write_only=True,
        help_text=(
            "The revision the new title/content was based on. If the document "
            "has changed since, nothing is saved and the response is 409 with "
            "the current document. Leave it out to save regardless."
        ),
    )

    class Meta:
        model = Document
        fields = [
            "id",
            "title",
            "content",
            "visibility",
            "access_level",
            "revision",
            "base_revision",
            "created_by",
            "created_by_email",
            "created_by_name",
            "organization",
            "project",
            "created",
            "modified",
        ]
        read_only_fields = [
            "id",
            "revision",
            "created_by",
            "organization",
            "project",
            "created",
            "modified",
        ]


class ExcerptSegmentSerializer(serializers.Serializer):
    """A run of an excerpt's text; ``match`` marks where a search term is."""

    text = serializers.CharField()
    match = serializers.BooleanField()


class DocumentListSerializer(DocumentSerializer):
    """A row of the documents list: everything but the content, which only a
    single document's page needs. While searching, ``excerpt`` shows where in
    the content the search matched (null when it matched only the title, or
    without a search). The view puts the search terms in the context."""

    excerpt = serializers.SerializerMethodField()

    class Meta(DocumentSerializer.Meta):
        fields = [
            *(
                field
                for field in DocumentSerializer.Meta.fields
                if field not in ("content", "base_revision")
            ),
            "excerpt",
        ]

    @extend_schema_field(ExcerptSegmentSerializer(many=True, allow_null=True))
    def get_excerpt(self, document):
        segments = content_excerpt(document.content, self.context["search_terms"])
        if not segments:
            return None
        return [{"text": text, "match": match} for text, match in segments]


class DocumentVersionSerializer(serializers.ModelSerializer):
    """An entry in a document's history: which revision, its title, and who
    saved it when."""

    created_by_email = serializers.EmailField(source="created_by.email", read_only=True)
    created_by_name = serializers.CharField(source="created_by.name", read_only=True)

    class Meta:
        model = DocumentVersion
        fields = [
            "revision",
            "title",
            "created_by",
            "created_by_email",
            "created_by_name",
            "created",
        ]
        read_only_fields = fields


class DocumentVersionDetailSerializer(DocumentVersionSerializer):
    """One version in full, to read or restore."""

    class Meta(DocumentVersionSerializer.Meta):
        fields = [*DocumentVersionSerializer.Meta.fields, "content"]
        read_only_fields = fields


class AttachmentSerializer(serializers.ModelSerializer):
    """A file attached to a document, as listed: what it is and who added it.
    The file itself is fetched from its download endpoint."""

    uploaded_by_email = serializers.EmailField(
        source="uploaded_by.email", read_only=True
    )
    uploaded_by_name = serializers.CharField(source="uploaded_by.name", read_only=True)

    class Meta:
        model = Attachment
        fields = [
            "id",
            "name",
            "content_type",
            "size",
            "uploaded_by",
            "uploaded_by_email",
            "uploaded_by_name",
            "created",
        ]
        read_only_fields = fields


class AttachmentUploadSerializer(serializers.Serializer):
    """An upload: at most ``MAX_ATTACHMENT_BYTES``, and one of the allowed
    kinds, recognised from its content (``attachment_content_type``)."""

    file = serializers.FileField()

    def validate_file(self, upload):
        if upload.size > MAX_ATTACHMENT_BYTES:
            raise serializers.ValidationError(
                f"Files can be at most {MAX_ATTACHMENT_BYTES // MEGABYTE} MB."
            )
        return upload

    def validate(self, attrs):
        upload = attrs["file"]
        try:
            attrs["content_type"] = attachment_content_type(upload)
        except UnsupportedFileError as error:
            raise serializers.ValidationError({"file": [str(error)]}) from None
        # Django keeps only an upload's base name, cut to 255 characters - never a
        # path someone typed into it.
        attrs["name"] = upload.name
        return attrs


class DocumentCreateSerializer(DocumentSerializer):
    """The create request: ``DocumentSerializer`` plus the optional ``project``
    to file the new document under (omitted or null for a personal document).
    The view resolves and checks that project itself - one the caller can't
    see is a 404, one they can't edit a 403 - so this field only documents
    the input; responses keep using ``DocumentSerializer``."""

    project = serializers.IntegerField(required=False, allow_null=True, write_only=True)
    # A new document has no earlier revision to be based on.
    base_revision = None

    class Meta(DocumentSerializer.Meta):
        fields = [
            field
            for field in DocumentSerializer.Meta.fields
            if field != "base_revision"
        ]


class ShareSerializer(serializers.Serializer):
    """Validates a grant/re-share request: a target user (by id) and the
    ``AccessLevel`` to give them. The target user must belong to the same
    organization as the resource being shared - checked against
    ``context["organization"]``, which the view supplies from the resource
    it already resolved (and therefore already org-scoped) - and be active."""

    user = serializers.PrimaryKeyRelatedField(queryset=User.objects.all())
    access_level = serializers.ChoiceField(choices=AccessLevel.choices)

    def validate_user(self, value):
        organization = self.context["organization"]
        if value.organization_id != organization.id:
            raise serializers.ValidationError(
                "This user does not belong to your organization."
            )
        # Only reported for a member of the organization, so this never says
        # anything about someone else's users.
        if not value.is_active:
            raise serializers.ValidationError("This user has been deactivated.")
        return value


def _permission_serializer(model, resource_field):
    """Builds a read-only ModelSerializer exposing id, resource_field, user,
    user_email, user_name, and access_level - all read-only - for a
    permission model."""
    fields = ["id", resource_field, "user", "user_email", "user_name", "access_level"]
    meta = type(
        "Meta", (), {"model": model, "fields": fields, "read_only_fields": fields}
    )
    user_email = serializers.EmailField(source="user.email", read_only=True)
    user_name = serializers.CharField(source="user.name", read_only=True)
    return type(
        f"{model.__name__}Serializer",
        (serializers.ModelSerializer,),
        {"Meta": meta, "user_email": user_email, "user_name": user_name},
    )


ProjectPermissionSerializer = _permission_serializer(ProjectPermission, "project")
DocumentPermissionSerializer = _permission_serializer(DocumentPermission, "document")


class SoleOwnershipSerializer(serializers.Serializer):
    """How many live projects and documents a member is the only active Owner
    of. Counts only, never names: the admin asking may not be able to see
    those resources at all."""

    projects = serializers.IntegerField(read_only=True)
    documents = serializers.IntegerField(read_only=True)


class DocumentAccessRequestSerializer(serializers.ModelSerializer):
    """Read-only - the view supplies ``document`` and ``requested_by`` from the
    URL and the requester, never from client-submitted data."""

    document_title = serializers.CharField(source="document.title", read_only=True)
    requested_by_email = serializers.EmailField(
        source="requested_by.email", read_only=True
    )
    requested_by_name = serializers.CharField(
        source="requested_by.name", read_only=True
    )
    reviewed_by_email = serializers.EmailField(
        source="reviewed_by.email", read_only=True, allow_null=True
    )
    reviewed_by_name = serializers.CharField(
        source="reviewed_by.name", read_only=True, allow_null=True
    )

    class Meta:
        model = DocumentAccessRequest
        fields = [
            "id",
            "document",
            "document_title",
            "requested_by",
            "requested_by_email",
            "requested_by_name",
            "reviewed_by",
            "reviewed_by_email",
            "reviewed_by_name",
            "status",
            "created",
            "modified",
        ]
        read_only_fields = fields
