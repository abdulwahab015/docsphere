from rest_framework.permissions import SAFE_METHODS, BasePermission

from projects.choices import Action
from projects.mappings import ALLOWED_ACTIONS
from projects.models import DocumentPermission, ProjectPermission


def resolve_access(user, document):
    """Return ``user``'s effective ``AccessLevel`` on ``document``, or ``None``.

    A ``DocumentPermission`` wins outright when present - even if it grants less
    than the parent ``ProjectPermission`` would. Otherwise the project permission
    applies; with neither, there is no access.
    """
    document_level = (
        DocumentPermission.objects.filter(user=user, document=document)
        .values_list("access_level", flat=True)
        .first()
    )
    if document_level:
        return document_level

    return (
        ProjectPermission.objects.filter(user=user, project_id=document.project_id)
        .values_list("access_level", flat=True)
        .first()
    )


def access_permits(access_level, action):
    """Whether ``access_level`` (from :func:`resolve_access`, or ``None``) allows
    ``action``."""
    if not access_level:
        return False

    return action in ALLOWED_ACTIONS.get(access_level, frozenset())


class HasDocumentAccess(BasePermission):
    """Object-level permission for document views: safe methods need Viewer,
    writes need Editor, DELETE needs Owner. Re-share isn't an HTTP verb, so
    share actions must call ``access_permits(level, Action.RESHARE)`` directly.
    """

    def has_object_permission(self, request, view, obj):
        user = request.user
        if not user or not user.is_authenticated:
            return False

        action = Action.READ if request.method in SAFE_METHODS else Action.WRITE
        if request.method == "DELETE":
            action = Action.DELETE

        return access_permits(resolve_access(user, obj), action)
