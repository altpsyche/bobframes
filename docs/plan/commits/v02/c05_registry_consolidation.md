# c05 — derive table/entity/report lists from a single source     release: v0.2 · phase: De-hardcoding

## Goal
Kill the duplicate lists that must be hand-synced. `schemas.TABLES` becomes the source for table and
entity lists; `reports/__init__.ALL_REPORTS` for the report list.

## Depends on
[c04](c04_paths_constants.md).

## Files
- `schemas.py` — add `entity_tables()` helper (reuse existing `is_entity_table()` predicate); add a
  `category` field per `TABLES` entry (for H-11).
- `global_entities.py` — replace `_ENTITY_TABLES` literal with `schemas.entity_tables()` (H-9).
- `catalog.py` — replace `_CATALOG_TABLE_KEYS` with `tuple(schemas.TABLES.keys())` (H-10).
- `html/template.py` — read groupings from `schemas.TABLES[*].category` instead of `_CATEGORY_MAP` (H-11).
- `reports/__init__.py` — NEW `ALL_REPORTS = (...)`; `orchestrator` (`_REPORT_MODULES`) and `ab`
  (**`_MODULES`** — note the different name, D-1) both import from it (H-8).

## Changes
Derive, don't duplicate. Order must be preserved exactly (catalog column order, category display
order) so golden parity holds.

## Done when
Golden parity + schema green. Adding a hypothetical table in a scratch branch shows it auto-appears
in catalog + entities + template without editing those modules.

## Closes
H-8, H-9, H-10, H-11 · D-1. Sets up M-1/M-2 (auto-discovery) for later.
