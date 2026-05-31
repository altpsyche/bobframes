# c28 — surface the `texture_usage` report     release: v0.4 · phase: Engine breadth + ergonomics

## Goal
`derives/texture_usage.build` already runs in the pipeline and its rows are tracked in the catalog —
but the data is never shown. Add the report that surfaces it (G-13).

## Depends on
[c05](../v02/c05_registry_consolidation.md) (`reports/__init__.ALL_REPORTS` registry).

## Seam extended
`reports/__init__.ALL_REPORTS` (c05), `cli._REPORTS` name map, `reports/ab._MODULES`,
`reports/cli.run_report(build_fn, module_name)`, `reports/cache` loaders. The `texture_usage` parquet
is already produced — no new derive.

## Files
- `reports/texture_usage.py` — NEW: `build(root, *, drops=None, ab=None) -> str` following the existing
  report convention; reads `texture_usage.parquet`; emits via `chrome.report_page`.
- `reports/__init__.py` — add `report_texture_usage` to `ALL_REPORTS` (orchestrator + ab pick it up).
- `cli.py` — add `'texture-usage' -> 'texture_usage'` to `_REPORTS`.
- `tests/data/golden/_reports/texture_usage.html` — NEW golden (additive report → golden refresh).

## Changes
New report changes rendered output → **refresh the golden in this PR** and review the diff. Empty-state
message (no sampled textures → friendly message, per c16) so sparse drops render cleanly.

## Done when
- `bobframes report texture-usage <root>` renders; appears in `render` (orchestrator) + `ab`.
- HTML lint-clean (`lint.lint_file` zero hits).
- **Golden refreshed + reviewed; parity green against the new golden.**

## Closes
G-13 (texture_usage surfaced). Serves the artist persona.
