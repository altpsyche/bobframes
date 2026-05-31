# c05 — derive table/entity/report lists from a single source     release: v0.2 · phase: De-hardcoding

## Goal
Kill the duplicate lists that must be hand-synced. `schemas.TABLES` becomes the source for table and
entity lists; `reports/__init__.ALL_REPORTS` for the report list.

## Depends on
[c04](c04_paths_constants.md).

## Files
- `schemas.py` — **migrate each `TABLES` value from the raw 3-tuple `(cols, size_class, is_entity)` to a
  named record** (a `NamedTuple` / small dataclass: `cols, size_class, is_entity, category`). The
  `category` access this commit needs (`schemas.TABLES[stem].category`, H-11) requires a *named* field,
  not a 4th positional slot — and v0.5/[c33](../v05/c33_data_driven_columns.md) adds an `api` field on
  the **same** record, so reserve it now (`api="core"` default) to avoid a positional-tuple expansion
  later. Update the unpackers (`parquetize`, the c13 replay-drift test, `is_entity_table`,
  `size_class`) to read named fields. Add `entity_tables()` (reuse `is_entity_table()`).
- `global_entities.py` — replace `_ENTITY_TABLES` literal with `schemas.entity_tables()` (H-9).
- `catalog.py` — replace `_CATALOG_TABLE_KEYS` with `tuple(schemas.TABLES.keys())` (H-10).
- `html/template.py` — read groupings from `schemas.TABLES[*].category` instead of `_CATEGORY_MAP` (H-11).
- `reports/__init__.py` — NEW `ALL_REPORTS`; `orchestrator` (`_REPORT_MODULES`) and `ab`
  (**`_MODULES`** — note the different name, D-1) both consume it (H-8). **Make it runtime-augmentable**
  — expose the report list via a small accessor (e.g. `all_reports()` returning base + any registered
  extras) rather than a frozen literal tuple, so v0.6/[c38](../v06/c38_plugins.md) plugins (M-1) and the
  new v0.4 reports ([c28](../v04/c28_texture_usage_report.md)/[c31](../v04/c31_mesh_material_report.md))
  register without re-touching this module.

## Changes
Derive, don't duplicate. Order must be preserved exactly (catalog column order, category display
order) so golden parity holds. The tuple→named-record migration is mechanical and must keep field
order/values identical — the `.cols`/`.is_entity`/`.size_class` reads return exactly today's values.

## Done when
Golden parity + schema green. Adding a hypothetical table in a scratch branch shows it auto-appears
in catalog + entities + template without editing those modules.

## Closes
H-8, H-9, H-10, H-11 · D-1. Sets up M-1/M-2 (auto-discovery, c38) and the named-record `api` field
(c33) for later — the registry becomes the single seam the breadth epics extend.
