# c02 — golden-snapshot harness     release: v0.1 · phase: Safety net

## Goal
Install the safety net that makes every later refactor regression-proof: a tiny synthetic `_data/`
tree, frozen expected HTML (golden), and the parity/schema/determinism/perf tests. **This guardrail
is the precondition for c03 onward.** See [QUALITY_GATES](../../reference/QUALITY_GATES.md) §21.1–21.4.

## Depends on
[c01](c01_version.md).

## Files
- `tests/data/synthetic/_data/<area>/<drop>/*.parquet`, `tests/data/synthetic/_data/_catalog.parquet` — NEW (~500KB)
- `tests/data/golden/**.html` — NEW (frozen expected output)
- `tests/parity.py`, `tests/schemas.py`, `tests/determinism.py`, `tests/perf.py` — NEW

## Changes
1. **Generate synthetic from a real anonymized ingest** ([ADR-6](../../DECISIONS.md)) — down-sample a
   Chor-bazar ingest, scrub absolute paths/shader source, truncate row groups to ~500KB. Do **not**
   hand-author. Verify it hits every `class_order` bucket and every `[pass_strip]` rule, plus at
   least one null-sparkline entry.
2. **Stub nondeterministic manifest fields** in the synthetic (`host_info`, `tool_versions`, build
   timestamps) to fixed values so golden HTML — if the dashboard footer surfaces them (G-7) — stays
   byte-deterministic.
3. Render synthetic once; copy result into `tests/data/golden/`; review.
4. `parity.py`: copy synthetic→tmp, `render`, assert each golden `*.html` byte-equal.
5. `schemas.py`: every parquet's columns == `schemas.expected_columns(stem)` (skip `_`-prefixed).
6. `determinism.py`: render twice; outputs byte-identical. `perf.py`: render < 2s.

## Done when
- `pytest tests/parity.py tests/schemas.py tests/determinism.py tests/perf.py` all green.
- Coverage check noted in PR: synthetic exercises every draw-class + pass-strip rule (else parity is
  false-confidence on unexercised paths).

## Rollback
Remove `tests/data/` + the four test files.

## Closes
None directly — it is the gate every other commit reports against. Relates G-12 (kills the brittle
smoke constants once c15 builds on this synthetic).
