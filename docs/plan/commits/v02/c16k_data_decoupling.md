# c16k — decouple the heavy data + lazy-load (ADR-36, phase 2)     release: v0.2

## Goal
Kill the ~21 MB inline-data TTI: move every heavy VTable payload (the catalog rows + each per-drop
drill table) out of the page and into `_data/*.js`, lazy-loaded via an injected `<script src>` only
when its route is opened. The shell + light views stay tiny; opening a drill loads only that drill's data.

## Depends on
[c16j](c16j_spa_spine.md) (the shell + router + `_data` loader + golden restructure). ADR-36.

## Scope
- Emit each per-drop drill's table payloads as `_data/drill_<area>_<drop>.js`
  (`window.__bf_data['drill_<area>_<drop>']={...}`) — the same per-table JSON the drill VTable consumes
  today (`html/template.py` `window.__data_<table>`), relocated out of the page. The drill `_views/`
  fragment is the VTable shell only (no rows baked).
- Router: on `#/drill/<area>/<drop>`, inject the view fragment + its `_data` script once, then mount the
  VTable over `window.__bf_data[...]`. Cache loaded `_data` keys so re-navigation is instant.
- Same treatment confirmed for the catalog (from c16j) and any other VTable view.
- This addresses the **D-8 lineage** indirectly: the heavy payload is isolated to its own file, so its
  size no longer blocks the shell/other views. (Trimming WHAT is baked is still a separate question; not
  required here.)

## Constraints (do not regress)
- Offline `<script src>` only (no `fetch`); byte-deterministic `_data/*.js`; opens by double-click.
- Golden gates the `_data/*.js` file-set + bytes; `test_parquet_parity` untouched (§21.9). a11y/print kept.
- Verify on the **real Perf data**: the shell + catalog are instant; opening a drill loads only that
  drill's data (measure: the shell no longer carries the 21 MB).

## Done when
- No view bakes its heavy rows inline; each loads its `_data/*.js` on navigation; shell + light views are
  small; drill TTI is paid only when a drill is opened. Golden green (file-set + bytes); parquet parity
  unchanged; smoke lint clean; browser-verified on synthetic + real data.

## Closes
ADR-36 phase 2. Extends QUALITY_GATES §21.1l (lazy `_data` loading).
