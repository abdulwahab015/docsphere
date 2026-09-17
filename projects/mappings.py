"""Lookup tables for the projects app."""

from projects.choices import AccessLevel, Action

ALLOWED_ACTIONS = {
    AccessLevel.VIEWER: {Action.READ},
    AccessLevel.EDITOR: {Action.READ, Action.WRITE},
    AccessLevel.OWNER: {Action.READ, Action.WRITE, Action.DELETE, Action.RESHARE},
}
