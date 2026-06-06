# v0.2.6-4 -- 5 tabled detail reports adopt the Column+data_table family     release: v0.2.6 · phase: redesign

> The THIRD surface-redesign commit and -- UNLIKE byte-neutral -2/-3 -- the first that BREAKS byte-parity
> on purpose. The 5 tabled detail reports (overdraw / draws_by_class / shader_hotlist /
> instancing_opportunities / trend_table) drop their hand-written `<table>` markup and adopt the c16x
> table component family (`chrome.Column` + `data_table`, ADR-42). `data_table` NORMALIZES the markup
> (attr order, cell shape, inline col-groups), which is exactly why c16x x4 BUILT-NOT-ADOPTED the family
> -- a byte-identical migration of the ~117 sites was infeasible. The golden refresh here ABSORBS that
> normalization (ADR-43 replacement gate; this is the contract, not a narrowing). pass_gpu is a detail
> surface but has NO table (bar-rows + treemap); it is eyeball-only this commit (its `el` long-tail
> stays for -5). Plan: `~/.claude/plans/bobframes-v0-2-6-visual-enumerated-bachman.md` (v0.2.6-4 row +
> "Full componentization"). No new ADR -- rides ADR-43 (replacement gate) + ADR-42 (component system) +
> ADR-44 (visual language).

## Goal
The 5 tabled reports render every table through `data_table(columns, rows, table_key=..., ...)` with
declarative `Column`s -- idiosyncrasies preserved BEHAVIORALLY (not byte-for-byte): overdraw's per-area
tables sharing one index-keyed col-groups spec; shader_hotlist's wide-clip `src` on an inner `<a>` with
the copy-button OUTSIDE the clip + the identity/cost/history col-groups + the `<details>` secondary +
the resolved table; instancing's 3-table family; the `.delta`/`delta-latest` comparison cells across 4
reports. The golden refresh absorbs the normalization; the data path stays FROZEN.

## The byte shape (verified against current source)
- **NOT byte-neutral.** `data_table` emits a CONSISTENT attribute order + uniform cell shape; the
  hand-written tables varied (e.g. overdraw emits `class="num"` th but the matching delta td is
  `class="delta"`; trend joins parts with `\n`; captions/headers pre-escape inline with `base.h`). So
  the rendered HTML for these reports CHANGES (markup shape only) and the golden is refreshed to match.
- **Escape discipline (single-escape, mirrors the -3 R1 fix).** `el`/`static_table` escape captions /
  plain headers / plain cells ONCE by construction. So captions drop their inline `base.h(...)` (pass the
  PLAIN string); plain headers pass plain (`f'samples@{k}'`); MARKUP headers (shader_hotlist multi-drop
  `uses<span class="dim">@{k}</span>`) pass `base.raw(f'...{base.h(k)}...')` (el splices `_Raw` verbatim;
  we escape `k` ourselves). A pre-escaped string would double-escape (`&amp;amp;`). **Upside:** captions
  embedding `area` are byte-NEUTRAL (`base.h(area)` vs el-escape both yield `ui &amp; hud`).
- **Data path FROZEN.** `data_table` is a markup transform; cell VALUES, row order (reports pre-sort),
  and column order are unchanged. `_pagedata/*.js` + `digests.json` + `golden_parquet` BYTE-UNCHANGED;
  `health.py`/`aggregates.py` untouched. NEVER `make_parquet_golden`.
- **Proven, not assumed (the keystone).** -2/-3 proved correctness via "byte-identical outside `<style>`";
  -4 can't (the tables change). Instead a data-preservation harness renders each report BEFORE + AFTER
  and asserts the ordered `<th>`/`<td>` text sequence + colgroups indices are IDENTICAL per report+page
  (synthetic 2-drop covers deltas/`delta-latest`/`_kpi_matrix`/history-colgroup; real Perf covers the
  3-drop trend column). Result recorded in the as-built.

## Scope
- **reports/chrome.py (component extensions; document in-code).**
  - NEW frozen `Column` fields: `cell_class: '_Callable | None' = None` (`cell_class(value,row)->str`,
    extra per-row td classes) + `header_class: str = ''` (extra th classes). `_table_th` (chrome.py:467)
    -> `classes('num' if col.numeric else '', col.header_class) or None`; `_table_td` (chrome.py:472) ->
    `classes('num' if numeric, 'mono' if mono, col.cell_class(value,row) if col.cell_class else '') or None`.
    Both default off -> every existing call site (summary/-3 dashboard) byte-unchanged. Docstring notes
    the callable-vs-str asymmetry (cell varies per row; header static per column instance).
  - `data_table` emits the `col-groups` bar div when `colgroups` truthy -- a sibling
    `<div class="col-groups" role="group" aria-label="column groups"></div>` BEFORE `table-wrap`
    (matches shader_hotlist.py:225 / overdraw.py:340). NEW `emit_colgroups_script: bool = True`: when
    `False` the div emits but the `<script>` does NOT (overdraw shares ONE spec across N per-area tables;
    it emits the single script itself). `colgroups` cols built from `enumerate(columns)` POSITIONS via a
    small `colgroups_from(columns, opens: dict)` helper keyed on the EXISTING (vestigial) `Column.group`
    field -- no hand counter (kills off-by-one); verified single-group-per-column holds (shader_hotlist
    ci appends each index to exactly one group). Groups ordered by `opens` insertion order; empty groups
    dropped.
- **reports/delta.py.** NEW `delta_parts(curr, prev, *, lower_is_better, fmt, regression_threshold_pct)
  -> (css_class, text)` factoring `delta_cell`'s shared logic; `delta_cell` + `delta_pill` refactored onto
  it BYTE-IDENTICALLY (their unit tests stay green). NEW `delta_column(key, header='delta', *,
  lower_is_better, fmt, regression_threshold_pct=None, latest=False, latest_cell=False) -> Column` factory
  (value = the `(cls,text)` tuple; render reads `base.h(value[1])`, cell_class reads
  `classes('delta', value[0], 'delta-latest' if latest_cell else '')`, header_class
  `classes('num', 'delta-latest' if latest else '')` -- NO closure over loop vars). `latest`-only:
  overdraw/instancing/shader (th border). `latest`+`latest_cell`: trend `_kpi_matrix` (th + td border,
  per trend_table.py:230 + 255-256). `delta_cell` kept (re-exported/unit-tested) but now UNUSED BY REPORTS
  (recorded here per ADR-23, not silent). pass_gpu's `delta_pill` (bar-rows) untouched.
- **reports/base.py.** Re-export `delta_column` (+ `delta_parts`) from `.delta`; add to `__all__`.
- **The 5 reports -> data_table.** Each table's `Column` list mirrors today's header order; `render=`
  lambdas reproduce the inner HTML (rank pills, links + `clip_attrs`/`clip_span`, copy-buttons OUTSIDE the
  clip, icons, heatmap cells, sparklines); `clip=`/`mono=`/`numeric=`/`title=`/`cell_title` set per column;
  every `if not rows: empty_state(...)` guard kept.
  - **overdraw.py** (~234-349): per-area `data_table(columns, rows, table_key='overdraw',
    colgroups=spec, emit_colgroups_script=False)` (col-groups div per area; ONE shared
    `window.__colgroups_overdraw` script emitted once at page end, as today line 348). Columns: rt label
    (render `clip_span(label)+h(swap)`), format (`clip='narrow'`), dims + 5 pct + samples (`numeric`),
    rejection bar (render `_rejection_bar(row)`), per drop samples@k (`numeric`) + `delta_column(..., latest=...)`.
  - **draws_by_class.py** (`_build_table` ~51-87): `data_table(table_key='draws_by_class',
    default_sort='opaque', default_dir='desc', caption='raw draw counts per class, per area and drop')`,
    NO colgroups. area/drop (`clip=''`), total (`numeric`, render heatmap), per-class x DRAW_CLASSES
    (`numeric`), `prepass / opaque` (`numeric`, `title=`). build() drops its manual host wrap (184-188).
  - **shader_hotlist.py** -- main (~218-316): `data_table(table_key='shader_hotlist',
    default_sort='cost proxy', default_dir='desc', colgroups=<identity/cost/history>)`. shader (render
    rank pill + optional `<a target=_blank>` + copy-button OUTSIDE), complexity (`numeric`, render
    heatmap), uses (current) (`numeric`), per-drop uses (markup header via `base.raw` when multi,
    `numeric`; -> cost group single / history multi) + `delta_column`, trend (`numeric`, render sparkline,
    >=3 drops), cost proxy (`numeric`, render heatmap), flags (plain), **src** (`mono`, render
    `<a ...>`+`clip_span(path,'wide')`+`icon('file')`+`</a>`+`<rdc-copy-button data-value="<full path>"
    data-label="copy src path">` -- pinned by `test_c16m_copy_and_link_payloads_keep_full_value`). The
    report STOPS hand-emitting the col-groups div + the script (data_table does both). secondary
    (~319-344): `data_table(table_key='shader_secondary')` inside the existing `<details><summary>`
    (the `<details>` stays -- structural leaf, -5). resolved (~360-378): `data_table(table_key='shader_resolved')`.
  - **instancing_opportunities.py** -- main (~227-291): `data_table(table_key='instancing_main')`, NO
    colgroups. mesh (render rank pill + `<a{clip_attrs(label)} data-link-kind=drill>` + copy-button
    OUTSIDE), per-drop repeat/repeat@k (PLAIN header -- no `<span>`, `numeric`) + `delta_column`, trend
    (sparkline >=3), areas (`clip=''`), dominant pass (`clip='narrow'`), indices typical (`numeric`),
    wasted indices (`numeric`, render heatmap). resolved (~306-327) + batching (~343-358): plain/numeric.
  - **trend_table.py** -- `_kpi_matrix` (~211-265): `data_table(table_key=f'trend_{kpi}')`; area
    (`clip=''`), per-drop value (`numeric`) + `delta_column(..., latest=last, latest_cell=last)`, trend
    (sparkline >=3). `_single_drop_matrix` (~268-303): `data_table(table_key='trend_matrix')`; area +
    per-KPI heatmap-or-plain (render). `_class_count_matrix` (~306-331): `data_table(table_key='trend_class_counts')`;
    area + per-(drop x class) `numeric`.
- **NOT touched:** pass_gpu.py (no table; eyeball-only); preview.py (`_table_block` is a standalone mini
  sample, not a `data_table`, so the gallery + `make_preview_golden` are byte-unchanged); CSS/tokens (no
  new token; reuses `.delta`/`.delta-latest`/`.col-groups`/`.clip`); overdraw `<p class="note">` (230) +
  shader `<details><summary>` (structural leaves, -5); fonts/density (already global from 1a/1b).

## Gates (§21.1v replacement-gate set)
- **(a) Data path FROZEN.** `test_parquet_parity` GREEN; `_pagedata/*.js` + `digests.json` +
  `golden_parquet` BYTE-UNCHANGED; NEVER `make_parquet_golden`. **+ the data-preservation proof**
  (ordered cell-text + colgroups indices IDENTICAL pre/post, per report+page, synthetic 2-drop + real Perf).
- **(b) Structural / component asserts.** th count == `scope="col"` count; `<caption>` present;
  `<rdc-table data-mode="static">` + `<table class="data">`; clip classes (`clip-wide` src,
  `clip-narrow` format/dominant-pass, default clip area/label/mesh); shader_hotlist
  `__colgroups_shader_hotlist=[...]` (identity/cost first, int cols) + the `col-groups` div + the src
  copy-payload regex (clip display == copy value); delta sign explicit (+/-, color additive) +
  `delta-latest`; `aria-sort`/`wireSortHeader(` stay in `_compose_js()` (untouched); search `aria-label`
  (untouched); no DOM reorder; pass_gpu keeps `'<rdc-table' not in`. `test_table_component` EXTENDED
  in-commit: `cell_class`/`header_class` emit, `data_table` col-groups div + `emit_colgroups_script`,
  single-escape of a caption/header, AND the `delta_column` factory (th/td classes for
  latest/latest_cell + a multi-row closure-bug guard).
- **(c) Token guard** -- `chrome.undefined_tokens() == set()` on chrome + template; NO new token.
- **(d) Browser matrix -- MANDATORY, sign-off BEFORE goldens.** headless Chrome over `file://`, synthetic
  + real Perf `c:/tmp/perf` (re-render render-only first; newest run's drill), light/dark/print: the 5
  normalized tables read right, delta colors + `delta-latest` border legible light+dark, clip+hover-reveal
  on src/area/mesh, col-groups toggles work (overdraw + shader_hotlist), heatmap shading intact, the
  3-drop trend sparkline column (real Perf), print drops chrome, pass_gpu unchanged.
- **(e) Lint / ASCII / determinism** -- per-page `_lint_or_raise`, whole-page ASCII, render-twice
  identical; no `Math.random`/`Date`/`fetch`/`type="module"`; no new dep/build step (ADR-37).

**Golden discipline (ADR-23 bounded).** On the canonical `.venv` (py3.12/pyarrow21, golden_env/ADR-11 --
NEVER system py3.14): `make_golden` -> `make_preview_golden` (expect 0 diff) -> `make_package_golden`.
Then `git status --short` + `git diff --stat`: the changed SET = {chrome.py, delta.py, base.py, the 5
reports} + {test_table_component.py (+ test_report_structure.py only if a literal genuinely shifts)} +
{the refreshed report HTML goldens (top-level + per-older-run) + golden_package shared/redacted/
shared_redacted report HTML}. `_pagedata/*.js` + `digests.json` + `golden_parquet` MUST be byte-unchanged
(do NOT assert a fixed file count -- the diff IS the gate). A file outside that set = undeclared coupling
-> root-cause it.

## Done when
The 5 tabled reports render via `Column`+`data_table` (idiosyncrasies preserved -- overdraw shared
col-groups, shader src wide-clip + copy-outside + identity/cost/history groups, instancing 3-table family,
`.delta`/`delta-latest` across 4 reports); the data-preservation proof is GREEN (cell-text + colgroups
identical pre/post on synthetic + real Perf); `_pagedata`/`digests.json`/`golden_parquet` BYTE-UNCHANGED;
`test_parquet_parity` + extended `test_table_component` + full `-m "not browser"` suite GREEN; token guard
0 undefined; lint/ASCII/determinism clean; browser matrix SIGNED OFF before the bake; goldens refreshed on
`.venv`; QUALITY_GATES §21.1v + FINDINGS (table-adoption row ticked; `el` long-tail stays open for -5) +
STATE.md updated; `current -> v0.2.6-5`.

## As-built (DONE 2026-06-06)
- **All 5 tabled reports adopt `data_table`** (overdraw/draws_by_class/shader_hotlist/instancing_opportunities/
  trend_table; ~11 logical tables). pass_gpu untouched (bar-rows, no table; eyeball-only). Idiosyncrasies
  preserved BEHAVIORALLY: overdraw's N per-area tables share ONE index-keyed `__colgroups_overdraw` spec
  (each emits its `.col-groups` div via `emit_colgroups_script=False`; the one shared script emitted once);
  shader_hotlist's wide-clip `src` on the inner `<a>` + copy-button OUTSIDE + identity/cost/history groups +
  `<details>` secondary + resolved; instancing's 3-table family; `.delta`/`delta-latest` across 4 reports
  (trend's `_kpi_matrix` puts delta-latest on BOTH th + td via `latest`+`latest_cell`).
- **Component extensions (chrome.py):** `Column.cell_class` (per-row td class callable) + `header_class`
  (extra th class str) -- the intentional asymmetry that reproduces the delta column's split th/td classes;
  `data_table` emits the `.col-groups` div when `colgroups` set + NEW `emit_colgroups_script` toggle; NEW
  `colgroups_from(columns, opens)` derives the index spec from each `Column.group` BY POSITION (kills the
  off-by-one of a hand counter; makes the formerly-vestigial `group` field load-bearing); `Column.clip=
  'default'` for the default 320px tier (the field's `''` still means NO clip). **delta.py:** NEW
  `delta_parts(...) -> (css_class, text)`; `delta_cell`/`delta_pill` refactored onto it BYTE-IDENTICALLY
  (their unit tests unchanged); NEW `delta_column(...)` factory (cell value = the `(cls,text)` tuple;
  render/cell_class read the PASSED value, NOT a captured loop var -> the closure-bug guard). `delta_cell`
  kept but NOW UNUSED BY REPORTS (recorded per ADR-23). All extensions default-off -> summary/-3 dashboard
  table sites byte-unchanged.
- **Escape discipline (single-escape, mirrors -3 R1):** captions / plain headers / plain cells pass PLAIN
  (dropped inline `base.h`) so `el` escapes ONCE; the markup header (shader_hotlist multi-drop
  `uses<span class="dim">@k</span>`) passes `base.raw(...)`. shader_hotlist's now-unused `import json`
  removed.
- **Keystone gate -- data-preservation proof (the -4 analogue of -2/-3's byte-identity, which -4 can't use):**
  a scratch harness rendered each report BEFORE + AFTER and asserted the ordered `<th>`/`<td>` text +
  colgroups indices IDENTICAL per page. **GREEN on synthetic** (2-drop -> covers deltas/`delta-latest`/
  `_kpi_matrix`/the shader history colgroup; 13 pages / 1859 cells; deterministic across 6 incremental
  re-runs). The real-Perf proof surfaced a **PRE-EXISTING** overdraw row-order nondeterminism
  (`set(by_area[area])` tie-break on equal sample counts; two POST-migration renders disagreed on DIFFERENT
  cells -> confirmed pre-existing, not the migration, which kept the selection+sort verbatim) -> recorded
  FINDINGS **R-19** (deferred; the fix is golden-neutral on synthetic so needs a multi-tie fixture).
- **Gates.** `test_parquet_parity` + `_pagedata/*.js` + `digests.json` + `golden_parquet` BYTE-UNCHANGED (data
  FROZEN; NO `make_parquet_golden`). `test_table_component` EXTENDED in-commit (cell_class/header_class, the
  col-groups div + `emit_colgroups_script`, `colgroups_from`, `delta_parts`/`delta_column` incl. per-row
  independence, the `'default'` clip) -> 7->13. `test_report_structure` held with NO edit (the faithful
  migration preserved every substring/count + clip-class + colgroups + src-copy-payload assert). **348
  passed** (`-m "not browser"`, was 342); token guard 0 undefined; lint/ASCII/determinism clean. Browser
  matrix light/dark/print synthetic + real Perf (54 PNGs) SIGNED OFF by the user before bake.
- **Golden refresh + scope.** Baked on the `.venv` (make_golden 17 HTML + 27 `_pagedata`; make_preview_golden;
  make_package_golden 49/45/49). `git diff --stat`: 8 source (base/chrome/delta + the 5 reports) +
  `test_table_component` + 9 report HTML goldens + 27 golden_package HTML + 2 docs; **net -827 lines**
  (declarative columns replaced the hand-written markup). `_pagedata`/`digests.json`/`golden_parquet` +
  `golden_preview` BYTE-UNCHANGED (0 data drift; preview gallery `_table_block` is a standalone mini, not a
  `data_table`). Nothing outside the declared scope. No new ADR (rides ADR-43 replacement gate + ADR-42 +
  ADR-44); QUALITY_GATES §21.1v + FINDINGS (R-19 NEW, G-32 -4 note) + STATE updated. UNPUSHED on plan/v0.2.6.

## Next
v0.2.6-5 (catalog/drill wide layout + route the virtual hosts through the component + finish the `el`
long-tail; `_pagedata/*.js` byte-stable).
