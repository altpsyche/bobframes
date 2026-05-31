# c31 — mesh / material report     release: v0.4 · phase: Engine breadth + ergonomics

## Goal
Give tech artists a per-material / per-mesh workflow view: which materials drive the most draws,
vertices, and instances. Built from existing draw/binding data — no new extraction.

## Depends on
[c05](../v02/c05_registry_consolidation.md) (registry), [c28](c28_texture_usage_report.md) (report
pattern). Reads existing `draws` / `draw_bindings` / entity tables.

## Seam extended
`reports/__init__.ALL_REPORTS`, `cli._REPORTS`, `reports/cli.run_report`, `reports/cache` loaders. The
underlying columns already exist in the schema — aggregation only.

## Files
- `reports/mesh_material.py` — NEW: `build(root, *, drops=None, ab=None) -> str`; aggregates per-material
  draw counts + vertex/instance totals (and a per-material trend column when multiple drops present).
- `reports/__init__.py` — add `report_mesh_material` to `ALL_REPORTS`.
- `cli.py` — add `'mesh-material' -> 'mesh_material'` to `_REPORTS`.
- `tests/data/golden/_reports/mesh_material.html` — NEW golden (additive → refresh).

## Changes
Deterministic aggregation (sorted by material key). Empty-state message for drops without material
data (c16 pattern). New report → golden refresh in this PR.

## Done when
- `bobframes report mesh-material <root>` renders; appears in `render` + `ab`.
- HTML lint-clean; deterministic across two renders.
- **Golden refreshed + reviewed; parity green.**

## Closes
Serves the artist "mesh/material workflow" + "per-material trend" criteria.
