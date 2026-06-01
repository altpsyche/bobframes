# c06b — Parquet-output parity gate (G-14)   release: v0.2 · phase: De-hardcoding

> **DONE 2026-06-01.** `tests/test_parquet_parity.py` gates a writer-independent logical digest
> (schema + row order + cell values) over every rendered `_data/**/*.parquet` vs committed
> `tests/data/golden_parquet/digests.json` (58 tables incl. `_global_entities`). Chose approach
> **(a)**. Non-finite floats (legit `vbo_samples.as_f32_*` NaN) → fixed sentinels, NOT `allow_nan`
> masking (ADR-23). Proven digest-identical across py3.10/pa17 ↔ py3.13/pa21 → runs on the full
> matrix (no `ci.yml --ignore`). Negative test: reversing `build_global_entities`' glob sort fails
> the gate naming `_global_entities.parquet` (the exact c05 regression). 38 tests green; HTML parity
> untouched. Refresh via `python -m bobframes.tests.make_parquet_golden`.

## Goal
Extend the golden gate so it catches **data-path** regressions, not just HTML render-logic. Today
`test_parity` walks `.html` only and skips `_data`/`_cache`, so "byte-parity green" silently allows
Parquet output to change — c05's `_global_entities` row-order shift slipped through and was "accepted"
(G-14). Close that hole. Follows [ADR-23](../../DECISIONS.md) (no silent coverage gaps).

## Depends on
[c06](c06_tool_resolver.md); pairs with [c06a](c06a_drill_size_dehardcode.md). Audit-opened (2026-06-01).
Relates [c21](../v03/c21_regression_gating.md) (regression gating reuses this surface).

## Approach
Add a Parquet-snapshot assertion over the synthetic fixture's rendered `_data/` outputs. Gate
**schema + row order + cell values** deterministically. Two candidate mechanisms (pick in-commit):
- **(a) committed golden manifest** — a small per-table digest file (sorted schema + a stable
  content hash computed with a fixed, writer-independent canonicalization, e.g. hash the logical
  pyarrow table via `to_pydict`, not the on-disk bytes). Robust across pyarrow versions.
- **(b) golden Parquet** — commit reference Parquet and compare logical contents (NOT on-disk bytes —
  those are writer-dependent, the same trap as D-8).
Prefer (a): writer-independent, runs on the full matrix (unlike HTML parity), tiny to commit.

## Files
- `tests/test_parquet_parity.py` — NEW: render the fixture, load each `_data/**/*.parquet`, assert
  schema + row order + a canonical content hash vs the committed golden digest.
- `tests/_render_util.py` — add a `rendered_parquet_files()` helper (mirror of `rendered_html_files`).
- `tests/data/golden_parquet/**` (or `*.digest`) — committed reference.
- `reference/QUALITY_GATES.md` — append the new gate to §21 (the golden set now includes Parquet).

## Done when
- A deliberate row-order or value change in any gated table makes `test_parquet_parity` fail.
- The c05 `_global_entities` ordering is now pinned (re-deriving it must be intentional + golden-refreshed).
- Gate runs green on the full matrix (writer-independent canonicalization), not just the canonical cell.
- Full suite green; HTML parity untouched.

## Closes
G-14. Makes "byte-parity green" mean *all gated outputs unchanged*, not HTML-only.
