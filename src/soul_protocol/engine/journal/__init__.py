# __init__.py — Public API for the journal engine.
# Created: feat/journal-engine — Workstream A slice 2 of Org Architecture RFC (#164).
# Re-exports Journal, JournalBackend, open_journal, and the exception hierarchy.

from __future__ import annotations

from .backend import JournalBackend
from .exceptions import IntegrityError, JournalError, NotFoundError, SchemaError
from .journal import Journal, open_journal
from .scope import scope_matches, scopes_overlap
from .sqlite import SQLiteJournalBackend

__all__ = [
    "IntegrityError",
    "Journal",
    "JournalBackend",
    "JournalError",
    "NotFoundError",
    "SQLiteJournalBackend",
    "SchemaError",
    "open_journal",
    "scope_matches",
    "scopes_overlap",
]
