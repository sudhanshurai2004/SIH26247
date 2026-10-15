"""SQLite persistence, local PIN hashing, and authorization primitives."""

from core.db.backup import BackupError, backup_sqlite_database
from core.db.database import create_session_factory, create_sqlite_engine, initialize_database
from core.db.models import (
    DoctrineRecord,
    Role,
    SessionStatus,
    SkillRatingRecord,
    TraineeEventRecord,
    TrainingSessionRecord,
    User,
)
from core.db.security import (
    AuthorizationError,
    PinValidationError,
    hash_pin,
    require_role,
    verify_pin,
)

__all__ = [
    "AuthorizationError",
    "BackupError",
    "DoctrineRecord",
    "PinValidationError",
    "Role",
    "SessionStatus",
    "SkillRatingRecord",
    "TraineeEventRecord",
    "TrainingSessionRecord",
    "User",
    "backup_sqlite_database",
    "create_session_factory",
    "create_sqlite_engine",
    "hash_pin",
    "initialize_database",
    "require_role",
    "verify_pin",
]
