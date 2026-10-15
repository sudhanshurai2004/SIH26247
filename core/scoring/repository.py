"""Local validated doctrine persistence for offline evaluation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from core.db.models import DoctrineRecord, Role, User
from core.db.security import require_role
from core.scoring.doctrine import DoctrineValidationError, parse_doctrine_text


@dataclass(frozen=True)
class DoctrineUploadResult:
    """Outcome of an idempotent local doctrine upload."""

    doctrine_id: str
    version: str
    created: bool


class DoctrineRepository:
    """Store only safely parsed and contract-validated doctrine YAML."""

    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory

    def upload(self, *, actor_id: str, yaml_text: str) -> DoctrineUploadResult:
        """Validate YAML before persistence; instructional staff own doctrine edits."""
        if len(yaml_text.encode("utf-8")) > 256_000:
            raise DoctrineValidationError("doctrine upload exceeds 256 KB")
        with self._session_factory.begin() as db:
            require_role(db.get(User, actor_id), [Role.INSTRUCTOR, Role.ADMIN])
            doctrine = parse_doctrine_text(yaml_text)
            existing = db.scalar(
                select(DoctrineRecord).where(
                    DoctrineRecord.doctrine_id == doctrine["doctrine_id"],
                    DoctrineRecord.version == doctrine["version"],
                )
            )
            if existing is not None:
                if existing.yaml_text != yaml_text:
                    raise DoctrineValidationError(
                        "doctrine id/version is already bound to different YAML"
                    )
                return DoctrineUploadResult(
                    doctrine_id=existing.doctrine_id,
                    version=existing.version,
                    created=False,
                )
            db.add(
                DoctrineRecord(
                    doctrine_id=doctrine["doctrine_id"],
                    version=doctrine["version"],
                    yaml_text=yaml_text,
                )
            )
            return DoctrineUploadResult(
                doctrine_id=str(doctrine["doctrine_id"]),
                version=str(doctrine["version"]),
                created=True,
            )

    def get(self, *, actor_id: str, doctrine_id: str, version: str) -> dict[str, Any]:
        """Return a freshly revalidated doctrine for a permitted local actor."""
        with self._session_factory() as db:
            require_role(db.get(User, actor_id), [Role.TRAINEE, Role.INSTRUCTOR, Role.ADMIN])
            record = db.scalar(
                select(DoctrineRecord).where(
                    DoctrineRecord.doctrine_id == doctrine_id,
                    DoctrineRecord.version == version,
                )
            )
            if record is None:
                raise DoctrineValidationError("doctrine does not exist")
            return parse_doctrine_text(record.yaml_text)

    def list(self, *, actor_id: str) -> tuple[dict[str, str], ...]:
        """List local doctrine identities without exposing unvalidated input."""
        with self._session_factory() as db:
            require_role(db.get(User, actor_id), [Role.TRAINEE, Role.INSTRUCTOR, Role.ADMIN])
            records = db.scalars(
                select(DoctrineRecord).order_by(DoctrineRecord.doctrine_id, DoctrineRecord.version)
            )
            return tuple(
                {"doctrine_id": record.doctrine_id, "version": record.version} for record in records
            )
