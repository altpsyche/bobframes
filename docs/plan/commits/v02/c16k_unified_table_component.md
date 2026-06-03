# c16k — the unified `rdc-table` component (bespoke, progressive-enhancement)     release: v0.2 · phase: De-hardcoding

> **ADR-38.** First of three commits unifying the two table systems (G-23). c16k BUILDS the one component and
> proves BOTH modes; **c16l** rolls it out everywhere + deletes the old scaffolding; **c16m** adds
> truncation + hover. Bespoke, no third-party grid (ADR-6/37); reports stay static (ADR-37).

## Goal
Replace the two divergent table systems — the reports' server-baked `table.report` + `rdc-sortable-table`
web component, and the catalog/drill `html/template.py` **VTable** — with ONE bespoke component, `rdc-table`,
that is **progressive-enhancement** with two data-delivery modes (ADR-38):
- **`static`** — rows server-baked into the HTML; JS *enhances* (sort/filter/heatmap/column-groups). JS-off,
  print, Ctrl-F, single-file, golden-as-output all hold. (reports)
- **`virtual`** — rows stream from `_pagedata/*.js`, DOM windowed (today's VTable). (catalog + drill)
c16k builds the component + both modes, migrates the catalog + drill (virtual) onto it, and migrates **one**
report (static, e.g. `overdraw` or `pass_gpu`) as the static-mode proof. The rest follow in c16l.

## Depends on
`html/template.py` (the VTable engine + `_JS` + `_pagedata/*.js` delivery, c16i/c16j), `reports/chrome.py`
(the `table.report` CSS + `rdc-sortable-table` web component + print/sticky CSS). ADR-38, ADR-37, ADR-24.

## Scope
1. **Build `rdc-table`.** Merge the VTable engine (sort, numeric/type detection, type-split classes,
   uniform-tint heatmap, collapsible column groups, virtual windowing ROW_H=32) with `rdc-sortable-table`
   (progressive-enhancement over a server-baked `<table>`). One shared engine; `data-mode="static|virtual"`
   picks data delivery. Consolidate the CSS onto one table class (recommend `table.data`; keep the report
   look). Keep it offline, byte-deterministic (NO `random`/`Date` in output), ASCII, file://-safe, zero-dep.
2. **`virtual` mode = today's drill/catalog.** Catalog (root `index.html`) + per-drop drill render through
   `rdc-table` reading `_pagedata/*.js` (c16j contract unchanged). Behaviour byte-stable where possible; the
   wrapper element/classes may change (golden refresh, reviewed).
3. **`static` mode = server-baked progressive enhancement.** `rdc-table` wraps a server-baked `<table>`
   whose rows are IN the HTML; JS enhances. JS-off → a plain readable/printable/Ctrl-F-able table. Migrate
   ONE report onto it as proof; it gains client sort/filter + (optionally) heatmap/column-groups while its
   `<td>` row **content** stays byte-stable.
4. **Shared behaviour contract.** Sort = natural-numeric (ADR-24); numeric detection + `.numeric`/`.mono`
   type-split classes; uniform-tint `background-image` heatmap on numeric magnitude cells (excl.
   id/event_id/labelCols + single-value); column groups from `schemas.table_category`; search/filter. The
   same code path serves both modes (truncation lands in c16m).

## Constraints (do not regress)
- **ADR-37 preserved for reports:** the migrated report keeps server-baked rows → **golden-visible**,
  **JS-optional**, **printable**, **Ctrl-F-able**, single-file. A static-mode page MUST render its rows with
  JS disabled.
- **Offline + deterministic:** classic script, NO `fetch`/modules, NO `random`/`Date` in rendered output;
  ASCII lint; `test_parquet_parity` untouched (§21.9, presentation only).
- **No third-party grid** (ADR-38). Bespoke engine only.
- Non-migrated reports + dashboard + A/B + per-run + trend goldens **byte-unchanged** until c16l touches
  them (scope c16k to: catalog, drill, + the one proof report).

## Done when
- `rdc-table` renders the catalog + drill in `virtual` mode (parity with c16i/c16j behaviour: type split,
  heatmap, column groups, scroll/sort/search) AND the one proof report in `static` mode (rows server-baked +
  golden-visible + readable JS-off + printable + Ctrl-F, with client sort/filter enhancing).
- Golden refreshed + reviewed for exactly those surfaces; all OTHER report/dashboard/A-B/per-run goldens
  byte-unchanged; `test_parity` green; `test_parquet_parity` green with no digests refresh; `bobframes smoke`
  lint clean exit 0; browser-verified offline (light + dark; the proof report renders rows with JS disabled).
- `test_report_structure` gains guards: `rdc-table` present, static report has server-baked `<tr>` rows in
  the HTML (golden-visible) AND degrades JS-off, virtual drill/catalog still externalize via `_pagedata/*.js`.

## Closes
The build half of **G-23** (rollout = c16l, truncation = c16m). Implements **ADR-38**. Add QUALITY_GATES
§21.1m (the `rdc-table` contract: two modes, static-mode golden-visible + JS-optional, virtual-mode
offline) when c16k–c16m land.
