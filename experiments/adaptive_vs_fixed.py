"""Compare real adaptive and fixed-session score groups."""

from __future__ import annotations

import argparse
from pathlib import Path

from reporting import average_by, scored_sessions, write_bar_chart, write_csv


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, required=True, help="Local trainer SQLite database")
    parser.add_argument("--out", type=Path, required=True, help="Directory for CSV and SVG output")
    args = parser.parse_args()

    records = scored_sessions(args.db)
    grouped = average_by(records, "selection_mode")
    modes = {mode for mode, _, _ in grouped}
    if not {"adaptive", "fixed"}.issubset(modes):
        raise SystemExit("Need scored real sessions from both adaptive and fixed modes.")

    write_csv(args.out / "adaptive-vs-fixed.csv", ["mode", "average_score", "sessions"], grouped)
    write_bar_chart(
        args.out / "adaptive-vs-fixed.svg",
        "Average score by real selection mode",
        [(mode, score) for mode, score, _ in grouped],
    )


if __name__ == "__main__":
    main()
