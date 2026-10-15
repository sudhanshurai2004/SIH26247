"""Session lifecycle, role checks, and idempotent trainee-event ingestion."""

from core.sessions.service import (
    EventConflictError,
    EventIngestResult,
    SessionManager,
    SessionManagerError,
    SessionSnapshot,
    SessionSummary,
)

__all__ = [
    "EventConflictError",
    "EventIngestResult",
    "SessionManager",
    "SessionManagerError",
    "SessionSnapshot",
    "SessionSummary",
]
