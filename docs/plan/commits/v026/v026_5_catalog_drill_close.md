# v0.2.6-5 -- catalog/drill wide layout + virtual hosts through the component + close the el long-tail     release: v0.2.6 · phase: redesign

> The FOURTH (and LAST) componentization commit of the v0.2.6 redesign epic. It does three things in one
> commit: (1) widens the catalog/drill layout (the densest data surface, max data-per-screen); (2) routes
> the catalog/drill VIRTUAL `rdc-table` hosts -- hand-concatenated in `html/template.py` -- through NEW
> escape-by-construction chrome table-family primitives; (3) FINISHES the `el` long-tail so NOTHING
> rendered is bespoke markup, closing FINDINGS G-32. Plan:
> `~/.claude/plans/continue-bobframes-v0-2-6-on-cheerful-eich.md` (+ the epic plan
> `bobframes-v0-2-6-visual-enumerated-bachman.md`, the v0.2.6-5 row + "Full componentization"). Mirrors the
> shape of `v026_4_detail_reports.md`. No new ADR -- rides ADR-42 (component system) + ADR-43 (replacement
> gate) + ADR-44 (visual language) + ADR-23 (documented scoping).

## Goal
The catalog index + per-drop drill pages get a wider body (~2400px cap) and render their virtual hosts via
`chrome.virtual_table_section`/`virtual_host`/`table_controls` (built through `el`) instead of hand-written
f-string markup; every remaining hand-concatenated chrome/template leaf rolls onto `el`/`raw` (byte-neutral
where the leaf is not normalized), plus the two leaves deferred from -4 (shader_hotlist's
`<details><summary>`, overdraw's `<p class="note">`). After -5, "everything is a component" is true modulo
ONE documented, irreducible page-scaffold floor (`page_open`'s doctype + open `<html>/<head>/<body>` +
favicon `<link>` + `<svg>` sprite). The rdc-table ENGINE + the catalog/drill `_pagedata` payloads stay
FROZEN.

## The byte shape (verified against current source)
- **Report pages: BYTE-UNCHANGED.** Reports never load `per_drop.css`, and every `el` leaf migration is
  byte-IDENTICAL (Strategy A, strict byte-neutral -- mirrors -2/-3). So NO report HTML golden refreshes;
  any report-page byte delta = a migration that was not byte-neutral -> root-cause (ADR-23), do not bake.
- **Catalog/drill: golden ABSORBS two intended deltas only.** (a) the `<style>` block (the `per_drop.css`
  `body { max-width }` bump [+ optional `.table-scroll { max-height }`]); (b) the virtual-host region
  reshaped by routing through the component (the host's internal `\n`s collapse since `el` empty-joins its
  children -- accepted because catalog/drill goldens refresh anyway; the JS-coupled substrings + attribute
  order are preserved exactly, so the engine + the c16i/k/o guards stay green). `_assets/catalog.css`
  (package) shifts with the `<style>`. NOTHING else.
- **Data path FROZEN.** `_write_page_data`/`_table_payload` untouched -> `_pagedata/*.js` + `digests.json`
  + `golden_parquet` BYTE-UNCHANGED; `health.py`/`aggregates.py` untouched. NEVER `make_parquet_golden`.
- **Engine FROZEN.** `reports/assets/rdc_table.{css,js}` (incl. `--clip-cap*`, `wireSortHeader`, aria-sort,
  `VTable`/`StaticTable`) NOT touched -- it is loaded by BOTH families, so a change would churn report
  goldens AND break the engine-frozen invariant. (Verified: `.table-scroll` sizing lives in `per_drop.css`,
  NOT `rdc_table.css`, so the optional scroll bump is engine-safe.)
- **Proven, not assumed.** Strategy A's byte-neutrality is proven by a per-group byte-diff of a fresh
  synthetic render against a pre-edit snapshot (report pages == ZERO bytes after each migration group). The
  catalog/drill DATA (client-rendered, not in the HTML) is proven by the extended cell-text harness
  (`bf_v0265_cells.py`) which parses the FROZEN `_pagedata/<key>.js` `window.__data_<key>={cols,rows}` per
  page + the `__colgroups_*` specs and asserts them identical pre/post (synthetic 2-drop + real Perf).

## Scope
- **reports/chrome.py (NEW table-family primitives + leaf migrations).**
  - NEW `table_controls(csv_href, parquet_href, *, filter_label, placeholder, dl_link_kind=None) -> _Raw`:
    the search-filter `<input>` + `.ct.visible-count` span + CSV/parquet `.dl` links bar shared by the
    catalog + drill virtual hosts (`dl_link_kind` -> `data-link-kind` on the `<a>`s: catalog `'inline'`,
    drill `None` -> attr omitted). Built via `el`/`el_void`.
  - NEW `virtual_host(table_key, *, col_groups=False) -> _Raw`: the empty windowed
    `<rdc-table class="table-scroll" data-mode="virtual" data-table=KEY>` host (+ the optional empty
    `<div class="col-groups" role="group" aria-label="column groups">` toggle bar the engine fills --
    catalog only). Rows stream client-side from the FROZEN `_pagedata/<key>.js`.
  - NEW `virtual_table_section(table_key, *, title, meta, csv_href, parquet_href, filter_label,
    placeholder) -> _Raw`: the DRILL per-table host -- `<section class="table-section" id=KEY>` +
    `<header class="table-header">`(h2 + `.table-meta`) + `table_controls(...)` + `virtual_host(table_key)`.
  - **Attribute dict ORDER is load-bearing** (reproduces the exact substrings the guards assert):
    `rdc-table` -> `{class, data-mode, data-table}`; `<input>` -> `{type, aria-label, placeholder}`;
    col-groups div -> `{class, role, aria-label}`; dl `<a>` -> `{class, href, data-link-kind}`.
  - **Clean leaf migrations** (`''.join`/single f-string, no internal `\n`; byte-identical el rebuild):
    `summary_bar`, `callout`, `empty_state`, `heatmap_cell`, `provenance_strip`, `ab_picker`, `run_picker`,
    `run_compare_banner`, `link`, `kpi_strip`, `section_card`, `ab_strip`.
  - **`\n`-joined structural leaves** (Strategy A -- build each sibling via `el`, keep the leaf's top-level
    `'\n'.join`; where an element wraps newline-separated children, inject the `\n` via
    `raw('\n' + '\n'.join(...) + '\n')` so the bytes match): `header`, `legend`.
  - **`page_open` LEFT AS-IS (the documented irreducible-raw floor, ADR-23).** `el` cannot emit a doctype
    (not a tag) nor leave `<html>/<head>/<body>` open; the favicon data-URI (`'`/`%23`) would be re-encoded
    by `el`'s `quote=True`; the `_ICON_SPRITE` is a fixed multi-symbol `<svg>` constant. These are fixed
    safe scaffolding with a single already-escaped `title` interpolation -- escape-by-construction adds zero
    safety, so migrating buys ~nothing while adding byte-risk to EVERY page. Recorded as the rationalized
    exception; G-32 still closes ("no bespoke" = "no UNJUSTIFIED bespoke").
- **reports/base.py.** Re-export `table_controls`, `virtual_host`, `virtual_table_section` (the
  `from .chrome import (...)` list + `__all__`) so `html/template.py` calls them as `reports_base.X`
  (matching its existing `reports_base.summary_bar` usage).
- **html/template.py (route the hosts + finish the template-local leaves).**
  - `_inline_table_with_data` (drill, ~318-331) -> one `reports_base.virtual_table_section(table_name,
    title=table_name, meta=f'{n_total:,} rows, {n_cols} cols', csv_href=..., parquet_href=...,
    filter_label=f'filter {table_name}', placeholder=f'filter {table_name}...')` call.
  - `render_root` catalog block (~732-743) -> compose inline: `el('section', None, el('h2', None,
    'catalog'), reports_base.table_controls(csv, pq, filter_label='filter catalog', placeholder='filter',
    dl_link_kind='inline'), reports_base.virtual_host('catalog', col_groups=True))`. The
    `window.__colgroups_catalog` `<script>` + the `_pagedata` defer ref stay emitted SEPARATELY after the
    section (745-748) -- data, frozen.
  - **Template-local `\n`-joined leaves -> Strategy A `el`:** `_toc`, `_category_block`, `_sidecar_category`,
    + the inline page-assembly fragments in `render_drop` (the `<header class="strip">` + fact spans, the
    crumb `<nav>`) and `render_root` (the dashboard chip-cluster, catalog-grid, pair-list, pair-group --
    STILL hand-concat in render_root; there is NO shared `chip_cluster` helper [the -3 migration was in
    dashboard.py], so el-build them inline matching dashboard.py's `base.el('div', {'class':'chip-cluster'},
    ...)` pattern). The favicon `<link>` lines (519/641) stay literal (the page_open floor rule).
- **reports/shader_hotlist.py + overdraw.py (the -4-deferred leaves).** shader_hotlist
  `<details class="secondary-metrics"><summary>secondary metrics</summary>...` -> `el('details',
  {'class':'secondary-metrics'}, el('summary', None, 'secondary metrics'), data_table(...))`. overdraw
  `<p class="note">no pixel_history rows in drops: {msg}</p>` -> `el('p', {'class':'note'},
  raw('no pixel_history rows in drops: ' + msg))` -- `msg` is ALREADY-escaped (`', '.join(base.h(k)...)`)
  so it is spliced via `raw()` (single-escape; the -3 R1 class).
- **reports/assets/per_drop.css (the ONLY catalog/drill `<style>` golden delta).** `body { max-width:
  1800px }` -> `~2400px`; optionally `.table-scroll { max-height: 60vh }` -> `~72vh`. Exact px nailed at
  browser-matrix sign-off. `rdc_table.css` (engine) FROZEN.
- **NOT touched:** `data_table`/`static_table`/`Column` (the -4 static contract + its tests stay frozen);
  `_write_page_data`/`_table_payload`; the engine `rdc_table.{css,js}`; `dashboard.py`/`summary.py` leaves
  (already el from -2/-3); `page_open` (documented floor); `preview.py` (gallery unaffected -> preview
  golden byte-unchanged).

### Reliability gotcha -- the engine's same-`<section>` DOM contract (invisible to the tests)
`rdc_table.js` finds its controls by DOM traversal, NOT by id: `host.closest('section')` then
`section.querySelector('input[type=search]' / '.ct.visible-count' / '.col-groups')` (bootstrap 646-648,
`buildGroupBar` 193-194, `jumpToTable` 588-593); `buildExpandToggle` does
`host.parentNode.insertBefore(bar, host)` (624). So the `<input>`, the `.ct.visible-count` span, the
`.col-groups` div, and the `<rdc-table>` host MUST stay descendants of ONE shared `<section>`, with the host
a DIRECT child of that section, and the drill section nested inside `<details class="category">` (so
`host.closest('details')` toggle->render still resolves). The substring tests pass even if these split
across sections -- ONLY the browser matrix catches a break. The new builders preserve all of it; the
browser-matrix FUNCTIONAL checklist (search filters / visible-count updates / col-groups toggles /
cross-link jumps / expand toggle appears) is the net.

## Gates (§21.1v replacement-gate set)
- **(a) Data path FROZEN.** `test_parquet_parity` GREEN; `_pagedata/*.js` + `digests.json` +
  `golden_parquet` BYTE-UNCHANGED; NEVER `make_parquet_golden`. **+ the data-preservation proof** extended
  to catalog/drill via `bf_v0265_cells.py` (parses the frozen `_pagedata` payloads + `__colgroups_*`;
  identical pre/post on synthetic + real Perf).
- **(b) Structural / ARIA asserts (KEEP green, the routing regression net).**
  `test_c16k_virtual_hosts_on_catalog_and_drill` (`<rdc-table class="table-scroll" data-mode="virtual"
  data-table=`); `test_c16i_column_groups_catalog_only` (EXACTLY 1 `<div class="col-groups" role="group"
  aria-label="column groups">` on catalog, 0 on drill); `test_c16o_search_input_labelled`
  (`aria-label="filter` on every search input); `test_table_scope_and_caption` (`th` count == `scope="col"`
  count); `aria-sort` + `wireSortHeader(` stay in `_compose_js()` (engine untouched); `test_c16l_*`; no DOM
  reorder. `test_table_component` EXTENDED in-commit: `virtual_table_section` drill-host shape (attr order,
  `aria-label`/`placeholder`, no dl `data-link-kind`, no col-groups), `virtual_host(col_groups=True)` emits
  exactly one col-groups div, `table_controls(dl_link_kind='inline')` catalog flavor, escape-by-construction
  on a `&`/`"` table_key. Optional `test_header_byte_shape`/`test_legend_byte_shape` locking the Strategy-A
  `\n` placement.
- **(c) Token guard** -- `chrome.undefined_tokens() == set()` on chrome + template; NO new token.
- **(d) Browser matrix -- MANDATORY, sign-off BEFORE goldens.** headless Chrome over `file://`, synthetic +
  real Perf `c:/tmp/perf` (re-render render-only first; newest run's drill), light/dark/print: the wider
  ~2400px catalog/drill reads right (no ultra-wide over-stretch), print drops chrome, AND the FUNCTIONAL
  net -- search filters rows, `N / M visible` count updates, catalog col-groups toggle hides/shows columns,
  a catalog cell cross-link jumps + filters the target drill table, the "Expand cells" toggle appears on
  clip tables, Ctrl-F + JS-off surface every row.
- **(e) Lint / ASCII / determinism** -- per-page `_lint_or_raise`, whole-page ASCII, render-twice identical;
  no `Math.random`/`Date`/`fetch`/`type="module"`; no new dep/build step (ADR-37).

**Golden discipline (ADR-23 bounded).** On the canonical `.venv` (py3.12.13/pyarrow21, golden_env/ADR-11 --
NEVER system py3.14): `make_golden` -> `make_preview_golden` (expect 0 diff) -> `make_package_golden`. Then
`git status --short` + `git diff --stat`: the changed SET = {per_drop.css, chrome.py, base.py, template.py,
shader_hotlist.py, overdraw.py} + {test_table_component.py (+ test_report_structure.py only if a byte-shape
assert is added)} + {the catalog/drill HTML goldens (top-level + per-older-run) + their golden_package twins
+ `_assets/catalog.css`} + {3 docs}. Report HTML goldens + `_pagedata/*.js` + `digests.json` +
`golden_parquet` + `golden_preview` MUST be BYTE-UNCHANGED (the diff IS the gate; do NOT assert a fixed file
count). A file outside that set = undeclared coupling -> root-cause it.

## Done when
Catalog/drill render through `chrome.virtual_table_section`/`virtual_host`/`table_controls` (the engine's
same-`<section>` DOM contract preserved) and carry the wider ~2400px layout; every remaining hand-concat
chrome/template leaf is on `el`/`raw` (Strategy A byte-neutral) + the two -4-deferred leaves done +
`page_open`'s scaffold floor documented; FINDINGS **G-32 CLOSED**; report HTML goldens + `_pagedata`/
`digests.json`/`golden_parquet`/`golden_preview` BYTE-UNCHANGED; `test_parquet_parity` + extended
`test_table_component` + full `-m "not browser"` suite GREEN; the `bf_v0265_cells.py` data-preservation
proof GREEN (synthetic + real Perf); token guard 0 undefined; lint/ASCII/determinism clean; browser matrix
(incl. the functional checklist) SIGNED OFF before the bake; goldens refreshed on `.venv`; QUALITY_GATES
§21.1v + FINDINGS (G-32 ☑; R-19 stays open) + STATE.md updated; `current -> v0.2.6-6` (the close-out/ship).

## As-built (DONE 2026-06-06)
- **Wide layout:** `per_drop.css` `body { max-width: 1800 -> 2400px }` + `.table-scroll { max-height:
  60 -> 72vh }` (catalog/drill only). Engine `rdc_table.{css,js}` (incl. `--clip-cap*`) FROZEN; verified
  `.table-scroll` lives in per_drop.css NOT the engine, so the scroll bump is engine-safe.
- **Virtual hosts routed through NEW chrome table-family primitives:** `table_controls(csv, parquet, *,
  filter_label, placeholder, dl_link_kind=None)` + `virtual_host(table_key, *, col_groups=False)` +
  `virtual_table_section(table_key, *, title, meta, csv_href, parquet_href, filter_label, placeholder)`,
  re-exported via `base.py`. `_inline_table_with_data` (drill) collapses to one `virtual_table_section`
  call; `render_root` composes the catalog inline from `table_controls` + `virtual_host('catalog',
  col_groups=True)`. `_write_page_data`/`_table_payload` untouched -> `_pagedata` byte-stable. **Engine
  same-`<section>` DOM contract preserved** (the gotcha invisible to the substring tests): browser matrix
  confirmed the filter count populated (`14/14 visible`), col-group toggles built, Expand-cells present.
- **`el` long-tail CLOSED (G-32):** the 12 clean chrome leaves + the `\n`-joined structural leaves
  (`header`/`legend`; template `_toc`/`_category_block`/`_sidecar_category` + the inline render_drop/
  render_root page fragments incl. catalog chip-cluster/catalog-grid/pair-list/pair-group) migrated to
  `el`/`raw` **byte-IDENTICALLY** (Strategy A: internal `\n` preserved via `raw('\n'...)` where an element
  wraps newline-separated children); the two -4-deferred leaves (`shader_hotlist` `<details><summary>`,
  `overdraw` `<p class="note">`) done. **Documented floor (ADR-23):** `page_open`'s scaffold (doctype +
  `<meta>`/`<title>` + favicon `<link>` data-URI + open `<html>/<head>/<body>` + `_ICON_SPRITE`) left as-is
  -- fixed safe markup `el` cannot build; "no bespoke" = no UNJUSTIFIED bespoke.
- **Strategy A proven:** a fresh synthetic render diverged from golden on EXACTLY 2 pages (root
  `index.html` + the drill page -- the intended host reshape + wide `<style>`); all 15 report HTML goldens
  BYTE-UNCHANGED (a scratch all-files diff against golden, `c:/tmp/bf_v0265_diff.py`).
- **Data FROZEN:** `test_parquet_parity` green; `_pagedata/*.js` + `digests.json` + `golden_parquet` +
  `golden_preview` BYTE-UNCHANGED (NOT in the diff). The cell-text harness extended to catalog/drill
  (`c:/tmp/bf_v0265_cells.py` parses the FROZEN `_pagedata/<key>.js` `window.__data_<key>={cols,rows}` +
  `__colgroups_*`): GREEN on synthetic. The real-Perf overdraw rt-row diff is **R-19 only** (reconfirmed
  self-nondeterministic: same NEW code, two re-renders disagreed on DIFFERENT tied-rt cells; synthetic
  deterministic -> not this commit).
- **Tests:** `test_table_component` EXTENDED +4 (virtual_table_section drill shape; virtual_host col-groups
  catalog-only / exactly 1 div; table_controls link-kind catalog-vs-drill; escape-by-construction on a
  `&`/`"` key) -> **352 passed** (`-m "not browser"`, was 348); token guard 0; `test_report_structure`
  (c16i/k/l/o substrings + th==scope + search aria-label) held with NO edit.
- **Browser matrix** light/dark/print on synthetic + real Perf (catalog + newest-run drill) SIGNED OFF by
  the user before bake.
- **Golden refresh + scope.** Baked on `.venv` (make_golden 17 HTML + 27 `_pagedata`; make_preview_golden
  [0 diff]; make_package_golden 49/45/49). `git diff --stat`: 6 source (per_drop.css/chrome.py/base.py/
  template.py/shader_hotlist.py/overdraw.py) + `test_table_component` + 2 render goldens (catalog + drill)
  + 6 golden_package goldens (catalog/drill HTML twins + `_assets/catalog.css` on shared/shared_redacted)
  + 3 docs. `report.css` / report HTML goldens / `_pagedata` / `digests.json` / `golden_parquet` /
  `golden_preview` BYTE-UNCHANGED. Nothing outside the declared scope. No new ADR (rides ADR-42/43/44 +
  ADR-23). QUALITY_GATES §21.1v + FINDINGS (G-32 ☑ CLOSED; R-19 re-confirmed, stays deferred) + STATE
  updated. UNPUSHED on plan/v0.2.6.

## Next
v0.2.6-6 (close-out + ship to PyPI: `_version 0.2.0->0.2.6`, ONE CHANGELOG `[0.2.6]` covering c16q->redesign,
full matrix incl `-m browser` + `golden_env`, clean-wheel post-install verify, tag + PyPI ONLY after
explicit authorization).
