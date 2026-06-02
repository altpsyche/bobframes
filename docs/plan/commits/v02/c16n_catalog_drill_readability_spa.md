# c16n — catalog + drill readability, in the SPA (ADR-36, phase 5; folds in c16i / G-21)     release: v0.2

## Goal
Deliver the readability goals that [c16i](c16i_catalog_drill_readability.md) scoped for the static
`html/template.py` layer — now **inside the SPA's catalog + drill views** (c16i is superseded by ADR-36).
This is where the three design reviews' eye-strain fixes actually land.

## Depends on
[c16j](c16j_spa_spine.md)–[c16l](c16l_rehome_reports.md) (the catalog/drill are SPA views over `_data/*.js`).
ADR-36. Carries the c16d design language into the data-browser.

## Scope (the c16i feature set, in the VTable views)
1. **Type split:** the VTable's `table.data` stops being all-monospace — headers + text columns (area /
   date / status / label / pass names) render in the Inter sans stack; mono + `tabular-nums` only for
   numeric cells, IDs, hashes (the column's dtype/role decides; the VTable already tags `numeric`).
2. **Roomier rows:** bump the VTable row height from `ROW_H = 22` + `2px` padding to ~`32-34px` / `6-8px`.
   **Coordinate the JS `ROW_H` constant with the CSS row height** (it drives the virtual-scroll offset
   math) or rows misalign. Keep zebra (`tr.alt`) + hover; soft left border on the sticky first column.
3. **Heatmap / data-bar cells** on numeric columns: a soft relative-value bar behind each numeric cell,
   computed **client-side** in the VTable from the loaded `_data` (per-column max) so outliers are
   scannable; colour is not the only signal (the number stays). Light-dark token palette.
4. **Collapsible column groups** on the wide catalog: toggle column sets (Metadata / Workload / Resources
   / Samples) to tame the column wall; the group→column map is a static deterministic table.

## Constraints (do not regress)
- Offline + byte-deterministic (client computation is deterministic — no `random`/`Date`); golden gates
  the view fragments + JS bytes. `test_parquet_parity` untouched (§21.9). ASCII lint; a11y (sortable/
  scope/keyboard) + reduced-motion + print preserved.
- **VTable correctness:** the `ROW_H`/CSS row-height pair is coupled — verify scrolling on the real Perf
  data (no row misalignment) after the height change.

## Done when
- The catalog + drill render with the Inter/mono split, roomier rows, numeric heatmap cells, and
  collapsible column groups — visibly less eye-straining, browser-verified light/dark on synthetic + real
  data; VTable scrolls correctly at the new height. Golden green; parquet parity unchanged; smoke lint clean.

## Closes
**G-21** (catalog + drill readability) — delivered in the SPA. **G-22** (the served/decoupled architecture)
is closed across the ADR-36 epic. Last code commit before the v0.2 close-out (re-ingest validation of the
app folder + single-file export on real data) and the tag.
