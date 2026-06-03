# c16l — roll `rdc-table` out to every report surface; delete the old systems     release: v0.2 · phase: De-hardcoding

> **STATUS: DONE 2026-06-03** (single commit per user choice). Engine folded always-on; all reports +
> per-run + trend + dashboard-mini + preview migrated to `static` rdc-table; `rdc-sortable-table` +
> `table.report` CSS DELETED (grep-clean); `aria-sort` sort-state restored on the static engine; column
> groups added to overdraw; 181 green; browser-verified offline. G-23 fully resolved. See QUALITY_GATES §21.1n.

> **ADR-38.** Second of three. **c16k** built `rdc-table` + both modes (proven on catalog/drill + one
> report). c16l migrates ALL remaining table surfaces onto it and removes the old `rdc-sortable-table` +
> VTable scaffolding. **c16m** then adds truncation + hover. Reports stay static (ADR-37).

## Goal
Migrate every remaining tabular surface onto the one `rdc-table` component (static mode) and **delete** the
now-dead second system, so the codebase has ONE table engine (G-23 fully resolved).

## Depends on
`c16k` (`rdc-table` + `static`/`virtual` modes). `reports/chrome.py` (the report builders + the
`rdc-sortable-table` web component to remove), `reports/*` (the 6 reports + dashboard + A/B + per-run +
`trend_table`), `html/template.py`. ADR-38.

## Scope
1. **Migrate the remaining static surfaces** onto `rdc-table` (static mode, server-baked rows): the other 5
   reports (`pass_gpu`/`overdraw`/`draws_by_class`/`shader_hotlist`/`instancing_opportunities` minus the
   c16k proof one), `trend_table`, the A/B pages, the per-run pages, and the dashboard small-multiples/mini
   tables. Each keeps its server-baked `<td>` row content byte-stable; the wrapper/classes/enhancement move
   to `rdc-table`. Carry over per-report specifics: area-break grouping, in-cell links + copy-buttons,
   `<caption>` + `scope="col"`, the dash-card mini variant (no pointer events), severity tints.
2. **Bring the richer features to reports where they help** (optional per surface, decided in review): client
   filter/search, the uniform-tint heatmap on ranked numeric columns, collapsible column groups on wide
   tables. Server-baked rows mean these stay progressive enhancements (JS-off still shows the full table).
3. **Delete the dead system.** Remove `rdc-sortable-table` (web component + its CSS) and any VTable
   scaffolding now superseded by `rdc-table`; collapse duplicated sort/numeric-detection/type-split/heatmap
   logic into the one engine (D-11 dead-code discipline). No two code paths left.
4. **Golden + structure.** Full HTML golden refresh (most pages change wrapper/markup); review per-page
   (structural-marker diff, precedent c16c/c16d). Split into sub-commits (a/b/…) if the golden balloons.

## Constraints (do not regress)
- **ADR-37 preserved:** every report/dashboard/A-B/per-run/trend page keeps server-baked rows →
  golden-visible, JS-optional, printable, Ctrl-F-able, single-file. Verify each renders rows JS-off.
- Offline + byte-deterministic (no `random`/`Date` in output), ASCII; `test_parquet_parity` untouched
  (§21.9). No third-party grid (ADR-38).
- The catalog/drill `virtual` mode (c16k) stays intact; `_pagedata/*.js` contract (c16j) unchanged.
- A11y preserved/improved: `<caption>`, `scope="col"`, real `<th>` headers, sort state via `aria-sort`,
  column-group toggles as real `<button aria-pressed>` (c16i/c16c parity).

## Done when
- Every tabular surface renders through `rdc-table`; `rdc-sortable-table` + the old VTable scaffolding are
  GONE (grep clean); no duplicated table logic remains.
- All reports/dashboard/A-B/per-run/trend render their rows with JS disabled (server-baked); golden refreshed
  + reviewed page-by-page; `test_parity` green; `test_parquet_parity` green with no digests refresh;
  `bobframes smoke` lint clean exit 0; browser-verified offline (light + dark; JS-off rows present; print +
  Ctrl-F work on a report).
- `test_report_structure` updated: every report uses `rdc-table` with server-baked `<tr>` rows; no
  `rdc-sortable-table` remains; a11y markers intact.

## Closes
The rollout half of **G-23** (G-23 fully resolved with c16k + c16l). Implements **ADR-38**. Folds into
QUALITY_GATES §21.1m.
