"""Deterministic local unit-trend queries over completed score reports."""

from __future__ import annotations

import json
from collections import defaultdict
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from core.db.models import Role, TrainingSessionRecord, User
from core.db.security import AuthorizationError, require_role


@dataclass(frozen=True)
class TrendPoint:
    """Aggregate score data for one local selection mode."""

    selection_mode: str
    completed_sessions: int
    average_score: float
    rating_eligible_sessions: int


@dataclass(frozen=True)
class UnitTraineeSummary:
    """One trainee's scored-session summary inside a local unit."""

    trainee_id: str
    completed_sessions: int
    average_score: float | None
    rating_eligible_sessions: int


@dataclass(frozen=True)
class UnitSummary:
    """No-network aggregate suitable for the unit dashboard panel."""

    unit_id: str
    trainees: tuple[UnitTraineeSummary, ...]
    trends: tuple[TrendPoint, ...]


def unit_trends(
    *,
    session_factory: sessionmaker[Session],
    actor_id: str,
    unit_id: str | None = None,
) -> tuple[TrendPoint, ...]:
    """Return authorized local aggregate trends without telemetry.

    An instructor is restricted to their own persisted ``unit_id``. An admin
    may request a named unit or all local units when no filter is supplied.
    """
    with session_factory() as db:
        actor = require_role(db.get(User, actor_id), [Role.INSTRUCTOR, Role.ADMIN])
        effective_unit_id = _authorized_unit_id(actor, unit_id)
        rows = _scored_rows(db, effective_unit_id)
        return _trend_points(rows)


def unit_summary(
    *,
    session_factory: sessionmaker[Session],
    actor_id: str,
    unit_id: str,
) -> UnitSummary:
    """Return per-trainee and per-mode scored summaries for one local unit."""
    with session_factory() as db:
        actor = require_role(db.get(User, actor_id), [Role.INSTRUCTOR, Role.ADMIN])
        effective_unit_id = _authorized_unit_id(actor, unit_id)
        if effective_unit_id is None:
            raise AuthorizationError("unit_id is required for a unit summary")
        trainees = tuple(
            db.scalars(
                select(User)
                .where(User.unit_id == effective_unit_id, User.role == Role.TRAINEE.value)
                .order_by(User.user_id)
            )
        )
        rows = _scored_rows(db, effective_unit_id)
        summaries = _trainee_summaries(trainees, rows)
        return UnitSummary(
            unit_id=effective_unit_id,
            trainees=summaries,
            trends=_trend_points(rows),
        )


def _authorized_unit_id(actor: User, requested_unit_id: str | None) -> str | None:
    if actor.role == Role.INSTRUCTOR.value:
        if requested_unit_id is not None and requested_unit_id != actor.unit_id:
            raise AuthorizationError("instructors may only read their own unit")
        return actor.unit_id
    return requested_unit_id


def _scored_rows(db: Session, unit_id: str | None) -> tuple[TrainingSessionRecord, ...]:
    query = (
        select(TrainingSessionRecord)
        .join(User, TrainingSessionRecord.trainee_id == User.user_id)
        .where(TrainingSessionRecord.score_json.is_not(None))
        .order_by(TrainingSessionRecord.selection_mode, TrainingSessionRecord.session_id)
    )
    if unit_id is not None:
        query = query.where(User.unit_id == unit_id)
    return tuple(db.scalars(query))


def _trend_points(rows: tuple[TrainingSessionRecord, ...]) -> tuple[TrendPoint, ...]:
    totals: dict[str, list[float]] = defaultdict(list)
    eligible: dict[str, int] = defaultdict(int)
    for row in rows:
        score = json.loads(row.score_json or "{}")
        totals[row.selection_mode].append(float(score.get("total_score", 0.0)))
        if row.rating_eligible:
            eligible[row.selection_mode] += 1
    return tuple(
        TrendPoint(
            selection_mode=mode,
            completed_sessions=len(scores),
            average_score=round(sum(scores) / len(scores), 6),
            rating_eligible_sessions=eligible[mode],
        )
        for mode, scores in sorted(totals.items())
    )


def _trainee_summaries(
    trainees: tuple[User, ...],
    rows: tuple[TrainingSessionRecord, ...],
) -> tuple[UnitTraineeSummary, ...]:
    scores_by_trainee: dict[str, list[float]] = defaultdict(list)
    eligible_by_trainee: dict[str, int] = defaultdict(int)
    for row in rows:
        score = json.loads(row.score_json or "{}")
        scores_by_trainee[row.trainee_id].append(float(score.get("total_score", 0.0)))
        if row.rating_eligible:
            eligible_by_trainee[row.trainee_id] += 1
    return tuple(
        UnitTraineeSummary(
            trainee_id=trainee.user_id,
            completed_sessions=len(scores_by_trainee[trainee.user_id]),
            average_score=(
                round(
                    sum(scores_by_trainee[trainee.user_id])
                    / len(scores_by_trainee[trainee.user_id]),
                    6,
                )
                if scores_by_trainee[trainee.user_id]
                else None
            ),
            rating_eligible_sessions=eligible_by_trainee[trainee.user_id],
        )
        for trainee in trainees
    )
