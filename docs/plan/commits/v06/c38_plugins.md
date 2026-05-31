# c38 — plugin auto-discovery (trusted-local)     release: v0.6 · phase: Cross-platform + leads + plugins

## Goal
Let users extend BobFrames without forking: auto-discover user-supplied reports, derives,
classifier-presets, and API-adapters. **Trusted-local-only** ([ADR-19](../../DECISIONS.md)) — discovered
code runs in-process; the security posture is "you run code you install", no sandbox.

## Depends on
v0.5 complete (the adapter + extension-table seams are extension points). Relates to
[c05](../v02/c05_registry_consolidation.md) (registry) and [c27](../v04/c27_engine_presets.md) (presets).

## Seam extended
`reports/__init__.ALL_REPORTS` (M-1 auto-discovery via `pkgutil.iter_modules` + a `build()` convention),
`schemas.TABLES` registration (M-2 — a decorator/registration call so a plugin table auto-appears in
catalog/entities/template), `derives/presets/` (custom presets via `custom_path`, already in c09),
`replay/adapters` (custom API adapters).

## Files
- `bobframes/plugins.py` — NEW: discover plugins from a documented user dir + an entry-point group
  (`bobframes.reports`, `bobframes.derives`, `bobframes.presets`, `bobframes.adapters`); register via
  the `build()` convention (M-1) and a `register_table()` call (M-2).
- `reports/__init__.py` — `ALL_REPORTS` merges discovered report plugins.
- `schemas.py` — `register_table(stem, cols, ...)` so a plugin table flows through catalog/entities/
  template (built on c05's derivation).
- Docs — an extension guide (write a report / derive / preset / adapter); the trusted-local security
  note.

## Changes
Discovery is opt-in (a user dir / installed entry points). No sandbox, no signing — documented as
trusted-local ([ADR-19](../../DECISIONS.md)). Core output is unchanged when no plugins are present.

## Done when
- A sample plugin in the user dir auto-registers a report **and** a schema table without editing core;
  the table appears in catalog/entities/template (the c05 derivation proves out).
- The extension guide documents reports/derives/presets/adapters + the trusted-local posture.
- **Golden parity green** with no plugins present (core output unchanged).

## Closes
M-1, M-2. Serves the adoptability "documented extension points" criterion. Establishes
[ADR-19](../../DECISIONS.md) (trusted-local plugin model).
