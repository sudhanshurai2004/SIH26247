"""Doctrine loading and deterministic training scoring."""

from core.scoring.doctrine import (
    DoctrineValidationError,
    load_doctrine,
    parse_doctrine_text,
    validate_doctrine,
)
from core.scoring.engine import NodeResult, ScoreReport, ScoringError, score_scenario
from core.scoring.golden_v1_adapter import GoldenV1AdapterReport, score_proposed_golden_case_with_v1
from core.scoring.proposed_golden import (
    ProposedGoldenScore,
    ProposedGoldenSpecError,
    load_proposed_golden_doctrine,
    score_proposed_golden_case,
    validate_proposed_golden_doctrine,
)
from core.scoring.repository import DoctrineRepository, DoctrineUploadResult

__all__ = [
    "DoctrineRepository",
    "DoctrineUploadResult",
    "DoctrineValidationError",
    "GoldenV1AdapterReport",
    "NodeResult",
    "ProposedGoldenScore",
    "ProposedGoldenSpecError",
    "ScoreReport",
    "ScoringError",
    "load_doctrine",
    "load_proposed_golden_doctrine",
    "parse_doctrine_text",
    "score_proposed_golden_case",
    "score_proposed_golden_case_with_v1",
    "score_scenario",
    "validate_doctrine",
    "validate_proposed_golden_doctrine",
]
