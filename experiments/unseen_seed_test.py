"""Compare real held-out scenario seeds with explicitly declared seen seeds."""

from __future__ import annotations

import argparse
from pathlib import Path

from reporting import average_by, scored_sessions, write_bar_chart, write_csv


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, required=True, help="Local trainer SQLite database")
    parser.add_argument(
        "--seen-seeds", required=True, help="Comma-separated seed values used in training"
    )
    parser.add_argument("--out", type=Path, required=True, help="Directory for CSV and SVG output")
    args = parser.parse_args()

    seen_seeds = {int(value.strip()) for value in args.seen_seeds.split(",") if value.strip()}
    if not seen_seeds:
        raise SystemExit("Provide at least one explicitly seen seed.")
    records = scored_sessions(args.db)
    labelled = []
    for record in records:
        label = "seen" if int(record["seed"]) in seen_seeds else "unseen"
        labelled.append({**record, "group": label})
    grouped = average_by(labelled, "group")
    groups = {group for group, _, _ in grouped}
    if not {"seen", "unseen"}.issubset(groups):
        raise SystemExit("Need real scored records for both seen and unseen seed groups.")

    write_csv(args.out / "unseen-seed.csv", ["group", "average_score", "sessions"], grouped)
    write_bar_chart(
        args.out / "unseen-seed.svg",
        "Average score on declared seen vs unseen seeds",
        [(group, score) for group, score, _ in grouped],
    )


if __name__ == "__main__":
    main()
