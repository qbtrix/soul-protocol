# exceptions.py — Journal engine error hierarchy.
# Created: feat/journal-engine — Workstream A slice 2 of Org Architecture RFC (#164).
# All journal failures raise a subclass of JournalError so callers can catch
# a single base class if they don't care which specific failure happened.

from __future__ import annotations


class JournalError(Exception):
    """Base class for all journal engine failures."""


class SchemaError(JournalError):
    """Raised when the on-disk schema version is incompatible with this engine."""


class IntegrityError(JournalError):
    """Raised when an append would violate an invariant (tz, monotonic ts, …)."""


class NotFoundError(JournalError):
    """Raised when a requested event / seq / id is not present."""
