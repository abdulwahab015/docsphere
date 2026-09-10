"""Lookup tables for the projects app."""

from projects.choices import AccessLevel, Action

ALLOWED_ACTIONS = {
    AccessLevel.VIEWER: frozenset({Action.READ}),
    AccessLevel.EDITOR: frozenset({Action.READ, Action.WRITE}),
    AccessLevel.OWNER: frozenset(
        {Action.READ, Action.WRITE, Action.DELETE, Action.RESHARE}
    ),
}
