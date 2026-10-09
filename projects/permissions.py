from django.contrib.auth import get_user_model
from django.db import models
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import SAFE_METHODS, BasePermission

from projects.choices import AccessLevel, Action, Visibility
from projects.mappings import ALLOWED_ACTIONS
from projects.models import DocumentPermission, ProjectPermission

User = get_user_model()


def resolve_access(user, document):
    """Return ``user``'s effective ``AccessLevel`` on ``document``, or ``None``.

    A ``DocumentPermission`` wins outright when present, whatever level it grants.
    Otherwise a public document grants every member of its organization an implicit
    Viewer level. A parent project's ``ProjectPermission`` never applies here - it
    only gates who may create a document inside that project, not who may read or
    write it once created.
    """
    document_level = (
        DocumentPermission.objects.filter(user=user, document=document)
        .values_list("access_level", flat=True)
        .first()
    )
    if document_level:
        return document_level

    if (
        document.visibility == Visibility.PUBLIC
        and document.organization_id == user.organization_id
    ):
        return AccessLevel.VIEWER

    return None


def openable_by(user, resource_field):
    """A condition on rows that refer to a project or document through
    ``resource_field`` (``"project"`` or ``"document"``): whether ``user``
    could open it, were it live - it's public, or shared with them at any
    level. The same rule as :func:`resolve_access`, for a whole queryset;
    callers scope to the user's organization."""
    permission_model = {"project": ProjectPermission, "document": DocumentPermission}[
        resource_field
    ]
    return models.Q(**{f"{resource_field}__visibility": Visibility.PUBLIC}) | models.Q(
        models.Exists(
            permission_model.objects.filter(
                **{resource_field: models.OuterRef(resource_field)}, user=user
            )
        )
    )


def active_owners(document):
    """The active users who hold Owner on ``document``: the ones who answer
    its access requests."""
    return User.objects.filter(
        document_permissions__document=document,
        document_permissions__access_level=AccessLevel.OWNER,
        is_active=True,
    )


def access_permits(access_level, action):
    """Whether ``access_level`` (from :func:`resolve_access`, or ``None``) allows
    ``action``."""
    if not access_level:
        return False

    return action in ALLOWED_ACTIONS.get(access_level, set())


def resolve_project_access(user, project):
    """Return ``user``'s effective ``AccessLevel`` on ``project``, or ``None``.

    A ``ProjectPermission`` wins outright when present, whatever level it grants.
    Otherwise a public project grants every member of its organization an implicit
    Viewer level.
    """
    project_level = (
        ProjectPermission.objects.filter(user=user, project=project)
        .values_list("access_level", flat=True)
        .first()
    )
    if project_level:
        return project_level

    if (
        project.visibility == Visibility.PUBLIC
        and project.organization_id == user.organization_id
    ):
        return AccessLevel.VIEWER

    return None


def check_can_share(user, resource, resource_field, resolve_access_fn):
    """Owner-level ``Action.RESHARE`` is required to view or change sharing."""
    if not access_permits(resolve_access_fn(user, resource), Action.RESHARE):
        raise PermissionDenied(
            f"You must have Owner access to this {resource_field} to share it."
        )


def _action_for_method(method):
    """Maps an HTTP method to the ``Action`` it represents: safe methods read,
    ``DELETE`` deletes, everything else writes."""
    if method == "DELETE":
        return Action.DELETE
    return Action.READ if method in SAFE_METHODS else Action.WRITE


class HasProjectAccess(BasePermission):
    """Object-level permission for project views: safe methods need Viewer,
    writes need Editor, DELETE needs Owner. Assumes ``IsAuthenticated`` (or
    equivalent) already ran - DRF only calls ``has_object_permission`` once
    every view-level permission has passed, so every view using this must
    also list an authentication permission."""

    def has_object_permission(self, request, view, obj):
        action = _action_for_method(request.method)
        return access_permits(resolve_project_access(request.user, obj), action)


class HasDocumentAccess(BasePermission):
    """Object-level permission for document views: safe methods need Viewer,
    writes need Editor, DELETE needs Owner. Re-share isn't an HTTP verb, so
    share actions must call ``access_permits(level, Action.RESHARE)`` directly.
    Assumes ``IsAuthenticated`` (or equivalent) already ran - DRF only calls
    ``has_object_permission`` once every view-level permission has passed, so
    every view using this must also list an authentication permission.
    """

    def has_object_permission(self, request, view, obj):
        action = _action_for_method(request.method)
        return access_permits(resolve_access(request.user, obj), action)
