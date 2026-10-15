# Input pack for SIH 26247 trainer — read this first

## What this is
A **proposed reference spec**, authored by hand. It is NOT data recovered from the Execution Blueprint
(the blueprint's G1-G10 are described in words only, with no numeric inputs or expected scores).
Your agent should adopt these, or change them and say why.

## Contents
- tests/golden/doctrine_generic_demo_v1.yaml : PLACEHOLDER generic doctrine, not real doctrine
- tests/golden/golden_cases.yaml : G1-G10 inputs + hand-computed expected per-target and total scores
- tests/golden/reference_scorer.py : tiny reference implementation (the real core/scoring must match within 0.01)
- tests/golden/test_golden_reference.py : pytest harness (all 10 cases verified passing by plain-Python run)

## Key rules the cases lock in
- delay is measured from t_visible, not scenario start (G5)
- event ingestion is idempotent by event id (G8)
- interrupted sessions are scored but excluded from ratings (G9)
- critical errors: -25 each; engaging a friendly caps the session at 30 (G2, G3, G6, G7)
- invalid doctrine (weights sum != 1) is rejected and the old doctrine stays active (G10)

## NOT supplied (you must provide)
1. The blueprint file: export it yourself from the doc (doc name -> Export -> Markdown) into docs/input/.
2. Godot 4 runtime / target machine and a benchmark spec. The blueprint only says "30 fps on an integrated-graphics laptop"; no exact hardware was defined. Measure and report real numbers, assume none.
3. An approved training-only doctrine. Use the placeholder until you have one.
