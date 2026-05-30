# c15 — rewrite `tests/smoke.py` + unit tests     release: v0.1 · phase: Finalize

## Goal
Replace the brittle hardcoded smoke test with a `--data`-driven one that defaults to the bundled
synthetic corpus, and add the unit tests that pin the load-bearing helpers.

## Depends on
[c13](c13_replay_drift_ci.md) + [c02](c02_golden_harness.md) (synthetic corpus). (c14 collapsed —
the tree is already named `bobframes`, ADR-7.)

## Files
- `tests/smoke.py` — **full rewrite.**
- `tests/unit_keys.py`, `tests/unit_schemas.py`, `tests/unit_discovery.py` — NEW.

## Changes
1. Eliminate `AREA='Chor bazar'`, `DROP_LABEL='r110565'`, `DROP_DATE='2026-05-27'`, and the
   `__file__`-walked `ROOT` (G-12).
2. New shape: `smoke` takes `--data DIR`, defaults to bundled `tests/data/synthetic/`.
   - No `--data` → **render-only** against synthetic Parquet (no `.rdc`, no qrenderdoc).
   - `--data` given → **full ingest** using `discovery.find_drops` to auto-select area + latest drop.
3. Unit tests:
   - `stable_keys` — key stability + `KEY_VERSION` prefix (from c03).
   - `schemas.expected_columns` — round-trips every stem in `TABLES`.
   - `discovery.parse_single_drop_arg` (correct name — **not** `_parse_drop_dirname`) + `find_drops`.
   - _(classifier + config-loader unit tests ship with their v0.2 commits c09/c07.)_

## Done when
- `bobframes smoke` (no `--data`) → exit 0, render-only against synthetic.
- `bobframes smoke --data <real>` → exit 0, ingest + render.
- `pytest tests/unit_*.py` green. Golden parity green.

## Rollback
Restore previous `smoke.py`; delete new unit files.

## Closes
G-12.
