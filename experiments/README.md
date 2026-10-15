# Pilot experiment scripts

These scripts operate only on **real scored rows** in a local trainer SQLite
database. They refuse to fabricate missing groups or learning data.

```bash
# Adaptive vs fixed sessions; requires both recorded selection modes.
PYTHONPATH=. .venv/bin/python experiments/adaptive_vs_fixed.py \
  --db data/trainer.sqlite3 --out out/experiments

# Declare the seed values actually used in training; all other observed seeds
# are treated as held-out/unseen.
PYTHONPATH=. .venv/bin/python experiments/unseen_seed_test.py \
  --db data/trainer.sqlite3 --seen-seeds 11,42,73 --out out/experiments

# Requires repeated real attempts by a trainee on an identical scenario ID.
PYTHONPATH=. .venv/bin/python experiments/rote_learning_test.py \
  --db data/trainer.sqlite3 --out out/experiments
```

Each script writes CSV plus self-contained SVG charts. Generated output is
ignored by Git through `out/`.
