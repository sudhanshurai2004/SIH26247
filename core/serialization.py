"""Canonical JSON helpers shared by deterministic core components."""

from __future__ import annotations

import json
from typing import Any


def canonical_json(value: Any) -> str:
    """Serialize JSON-compatible data to a stable, byte-comparable string.

    Scenario generation and scoring use this instead of ordinary ``json.dumps``
    so key ordering and whitespace cannot make an identical logical scenario
    differ on disk or in a replay fixture.
    """
    return json.dumps(
        value,
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )


def canonical_json_bytes(value: Any) -> bytes:
    """Return UTF-8 bytes for a canonical JSON value."""
    return canonical_json(value).encode("utf-8")
