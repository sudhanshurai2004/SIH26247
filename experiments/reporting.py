"""Shared, dependency-free reporting helpers for real local session data."""

from __future__ import annotations

import csv
import html
import json
import sqlite3
from collections import defaultdict
from collections.abc import Iterable
from pathlib import Path


class ExperimentDataError(ValueError):
    """Raised when an experiment has no qualifying real session data."""


def scored_sessions(database_path: Path) -> list[dict[str, object]]:
    """Read completed score reports; no synthetic rows are created."""
    if not database_path.is_file():
        raise ExperimentDataError(f"database does not exist: {database_path}")
    with sqlite3.connect(database_path) as connection:
        rows = connection.execute(
            """
            SELECT session_id, trainee_id, scenario_id, scenario_json, selection_mode,
                   rating_eligible, score_json
            FROM training_sessions
            WHERE score_json IS NOT NULL
            ORDER BY session_id
            """
        ).fetchall()
    records: list[dict[str, object]] = []
    for row in rows:
        scenario = json.loads(row[3])
        score = json.loads(row[6])
        records.append(
            {
                "session_id": row[0],
                "trainee_id": row[1],
                "scenario_id": row[2],
                "seed": scenario.get("seed"),
                "selection_mode": row[4],
                "rating_eligible": bool(row[5]),
                "total_score": float(score.get("total_score", 0.0)),
            }
        )
    if not records:
        raise ExperimentDataError("no scored sessions found; run real local sessions first")
    return records


def average_by(records: Iterable[dict[str, object]], key: str) -> list[tuple[str, float, int]]:
    """Return stable key/count/mean aggregates from supplied real records."""
    values: dict[str, list[float]] = defaultdict(list)
    for record in records:
        values[str(record[key])].append(float(record["total_score"]))
    return [
        (group, round(sum(scores) / len(scores), 6), len(scores))
        for group, scores in sorted(values.items())
    ]


def write_csv(path: Path, headers: list[str], rows: Iterable[Iterable[object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as output:
        writer = csv.writer(output)
        writer.writerow(headers)
        writer.writerows(rows)


def write_bar_chart(path: Path, title: str, bars: Iterable[tuple[str, float]]) -> None:
    """Write a small self-contained SVG chart, preserving source values in labels."""
    values = list(bars)
    if not values:
        raise ExperimentDataError("no values available to chart")
    width = 760
    height = 100 + 70 * len(values)
    max_value = max(max(value, 0.0) for _, value in values) or 1.0
    fragments = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" role="img">',
        '<rect width="100%" height="100%" fill="#07151f"/>',
        f'<text x="30" y="38" fill="#eff8fb" font-size="22">{html.escape(title)}</text>',
    ]
    for index, (label, value) in enumerate(values):
        y = 65 + index * 70
        bar_width = max(1.0, 500.0 * max(value, 0.0) / max_value)
        label_text = html.escape(label)
        fragments.extend(
            [
                (f'<text x="30" y="{y + 22}" fill="#c9dde4" font-size="15">{label_text}</text>'),
                f'<rect x="210" y="{y}" width="{bar_width:.2f}" height="30" fill="#7ae0dc"/>',
                (
                    f'<text x="720" y="{y + 22}" text-anchor="end" fill="#eff8fb" '
                    f'font-size="15">{value:.2f}</text>'
                ),
            ]
        )
    fragments.append("</svg>")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(fragments), encoding="utf-8")
