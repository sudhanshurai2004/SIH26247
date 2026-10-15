"""Safe local SQLite backups using SQLite's own backup API."""

from __future__ import annotations

import sqlite3
from pathlib import Path


class BackupError(ValueError):
    """Raised when a local backup path is invalid or unavailable."""


def backup_sqlite_database(database_path: Path, backup_directory: Path, name: str) -> Path:
    """Copy a local SQLite database into a controlled directory.

    ``name`` is constrained to a plain stem to prevent caller-controlled path
    traversal. The backup is local-only and contains no telemetry transport.
    """
    if not database_path.is_file():
        raise BackupError("database does not exist")
    if not name.replace("_", "").replace("-", "").isalnum():
        raise BackupError("backup name must contain only letters, digits, '-' or '_'")
    backup_directory.mkdir(parents=True, exist_ok=True)
    destination = backup_directory / f"{name}.sqlite3"
    with sqlite3.connect(database_path) as source, sqlite3.connect(destination) as target:
        source.backup(target)
    return destination
