"""Show real repeated-attempt score trends without fabricating learning data."""

from __future__ import annotations

import argparse
from collections import defaultdict
from pathlib import Path

from reporting import ExperimentDataError, scored_sessions, write_bar_chart, write_csv


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, required=True, help="Local trainer SQLite database")
    parser.add_argument("--out", type=Path, required=True, help="Directory for CSV and SVG output")
    args = parser.parse_args()

    records = scored_sessions(args.db)
    grouped: dict[tuple[str, str], list[dict[str, object]]] = defaultdict(list)
    for record in records:
        grouped[(str(record["trainee_id"]), str(record["scenario_id"]))].append(record)

    attempt_scores: dict[int, list[float]] = defaultdict(list)
    for attempts in grouped.values():
        for index, record in enumerate(attempts, start=1):
            attempt_scores[index].append(float(record["total_score"]))
    repeated = [(index, scores) for index, scores in sorted(attempt_scores.items()) if index > 1]
    if not repeated:
        raise ExperimentDataError(
            "need at least one trainee/scenario pair with repeated real attempts"
        )

    rows = [
        (attempt, round(sum(scores) / len(scores), 6), len(scores))
        for attempt, scores in sorted(attempt_scores.items())
    ]
    write_csv(args.out / "rote-learning.csv", ["attempt", "average_score", "sessions"], rows)
    write_bar_chart(
        args.out / "rote-learning.svg",
        "Average score by repeated attempt on identical scenario IDs",
        [(f"attempt {attempt}", average) for attempt, average, _ in rows],
    )


if __name__ == "__main__":
    main()
