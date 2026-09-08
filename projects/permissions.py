from rest_framework.permissions import SAFE_METHODS, BasePermission

from projects.choices import AccessLevel
from projects.models import DocumentPermission, ProjectPermission

_ACCESS_RANK = {
    AccessLevel.VIEWER: 1,
    AccessLevel.EDITOR: 2,
    AccessLevel.OWNER: 3,
}


class Action:
    """Things a user can attempt against a document. DELETE and RESHARE
    require Owner; WRITE requires Editor; READ requires Viewer."""

    READ = "read"
    WRITE = "write"
    DELETE = "delete"
    RESHARE = "reshare"


_ACTION_MIN_LEVEL = {
    Action.READ: AccessLevel.VIEWER,
    Action.WRITE: AccessLevel.EDITOR,
    Action.DELETE: AccessLevel.OWNER,
    Action.RESHARE: AccessLevel.OWNER,
}


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
    if document_level is not None:
        return document_level

    return (
        ProjectPermission.objects.filter(user=user, project_id=document.project_id)
        .values_list("access_level", flat=True)
        .first()
    )


def access_permits(access_level, action):
    """Whether ``access_level`` (from :func:`resolve_access`, or ``None``) allows
    ``action`` under the Owner > Editor > Viewer ranking."""
    if access_level is None:
        return False

    return _ACCESS_RANK[access_level] >= _ACCESS_RANK[_ACTION_MIN_LEVEL[action]]


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
