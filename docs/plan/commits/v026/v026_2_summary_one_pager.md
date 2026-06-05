# v0.2.6-2 -- summary one-pager: restrained type + hero numerals (summary-scoped)     release: v0.2.6 · phase: redesign

> The FIRST surface-redesign commit. The build-health summary is the ONE airy / exec surface (decision #4:
> Grafana-dense everywhere EXCEPT here). It gets its **hero numerals** -- the ~2.75rem treatment scoped to
> the 4 summary KPI values via `[data-page-kind="summary"]` (decision #3) -- and finishes de-bespoking its
> own markup: the by-area table adopts `chrome.static_table` (the c16x table family, ADR-42) and the
> summary-local hand-concat leaves roll onto the `el` builder. Plan:
> `~/.claude/plans/bobframes-v0-2-6-visual-enumerated-bachman.md` (v0.2.6-2 row + decisions #3/#4). No new
> ADR -- rides ADR-44 (v0.2.6 visual language) + ADR-42 (component system).

## Goal
Give the exec one-pager its hero numerals (summary-scoped, never leaking to dashboard/reports) and replace
its remaining bespoke markup with the promoted components -- such that **the componentization is byte-neutral**
(the body goldens do not change) and **the hero CSS is the only output delta** (it refreshes the inlined
`<style>` on every page, like 1b, while `_pagedata`/`digests`/`parquet` stay byte-unchanged).

## The byte shape (verified against current source -- the whole reviewability story)
- **Componentization is byte-NEUTRAL.** `chrome.static_table` (chrome.py:478) emits
  `<table class="data"><caption>By area</caption><thead>...` with `_table_th` (chrome.py:461) producing
  `<th class="num" scope="col">` / `<th scope="col">` in the EXACT attribute order of the hand-built table
  (summary.py:268-290); `el` is byte-identical by the c16x parity contract. So adopting `static_table` +
  rolling `_change_list`/`_change_line`/`_pct_pill`/the kpi-strip wrapper onto `el`/`raw` changes zero output
  bytes -- the summary body in the golden is unchanged; the Python diff is proven correct BY the goldens not
  moving in the body.
- **The hero numeral is the SOLE output change.** A new `fs_hero` token + one `[data-page-kind="summary"]`
  scoped rule alter the `:root` block + components CSS, which are inlined into every page's `<style>` -- the
  same all-page blast as 1b. Body markup + data path untouched.

## Scope
- **reports/summary.py (byte-neutral componentization)**
  - By-area table (summary.py:268-290) -> `chrome.static_table(columns, rows, caption='By area')`. Columns
    (order fixed): `Column('area')`, `Column('draws', numeric=True)`, `Column('gpu', numeric=True)`,
    `Column('overdraw', numeric=True)`, `Column('status')`. Rows are dicts whose composite cells are
    `chrome.raw(...)` so they splice verbatim (numeric cells `raw(f'{fmt} {pill}')`; `status` is the
    `status_badge` `_Raw`; `area` a plain str -> `el` escapes it). Keep
    `base.section_card('by_area', 'By area', table, count=n_areas)`. Bare `static_table` (NOT `data_table`)
    -- the exec sheet has no sort/heatmap host.
  - kpi-strip wrapper (summary.py:251) -> `el('div', {'class': 'kpi-strip'}, *kpis)`.
  - `_change_line` (summary.py:144) `<li>` + `_change_list` (summary.py:154) `<ul class="change-list">` /
    `<p class="note dim">` -> `el`/`raw` (byte-identical: single-space joins preserved).
  - `_pct_pill` (summary.py:55) the two literal `<span class="delta-pill ...">` branches -> `el`; the
    `base.delta_pill` fallback path is unchanged.
  - DEFER the shared chrome leaves (`summary_bar`/`callout`/`empty_state`) to the el long-tail's natural
    close (v0.2.6-5): el-ifying them risks attribute-order drift on OTHER pages (callout in reports,
    summary_bar on every page) -> out-of-scope golden churn. Recorded deliberate scoping (ADR-23).
- **reports/design_tokens.toml** -- NEW `[type]` key `fs_hero = '2.75rem'` (after `fs_display`); update the
  now-stale `fs_display` comment to name `fs_hero` as the summary hero.
- **reports/assets/design_tokens.css** -- add `--fs-hero: ${fs_hero};` after the `--fs-display` line (:root).
- **reports/assets/components.css** -- under the existing `[data-page-kind="summary"]` block:
  `[data-page-kind="summary"] .kpi-chip .kpi-value { font-size: var(--fs-hero); }`. `tabular-nums` +
  weight-600 + `-0.02em` tracking are already on the base `.kpi-value` (chrome.css:89) and inherited --
  weight stays <= 600 (the `test_fonts` hard rule + its pinned `font:` shorthand line are untouched). Net:
  dashboard/reports carry no `.kpi-chip` -> unaffected; the summary 4 KPIs + the preview kpi demo (already
  `data-page-kind="summary"`-wrapped) render at 2.75rem.
- **reports/preview.py** -- add `'fs-hero'` to `_TYPE_STEPS` (preview.py:26) so the living catalog documents
  the new token.

## Gates
- **(a) Data path FROZEN.** `test_parquet_parity` GREEN; `_pagedata/*.js` + `digests.json` + `golden_parquet`
  BYTE-UNCHANGED; **NEVER** `make_parquet_golden`.
- **(b) Structural / component asserts updated IN-COMMIT** (golden-independent): `test_summary.py`
  `test_by_area_table` (caption "By area", every `<th scope="col">`, one `<tr>` per area, delta-pill,
  status badge) + `test_four_headline_kpis` PASS UNCHANGED under the byte-neutral markup; add an assert that
  the summary scope carries the hero rule (`var(--fs-hero)` present in the components CSS). Redesign-invariant
  a11y holds (th == scope=col count; delta sign explicit; no DOM reorder).
- **(c) Token guard** -- `chrome.undefined_tokens() == set()` (auto-covers `--fs-hero`, defined + used);
  `test_subst_keys_...` auto-covers the `fs_hero` placeholder (it is in `token_subst()` from `[type]`).
- **(d) Browser matrix -- MANDATORY, sign-off BEFORE goldens.** headless Chrome over `file://`, synthetic +
  real Perf `c:/tmp/perf` (newest run), light / dark / print: hero numerals (no wrap, tabular-nums aligned,
  <=600 weight), by-area table unchanged, dark legibility, print drops chrome + hero prints black/clean.
- **(e) Lint / ASCII / determinism** -- per-page `_lint_or_raise`, whole-page ASCII, render-twice identical;
  no `Math.random`/`Date`/`fetch`/`type="module"`. No new dep / build step (ADR-37 holds).

**Golden discipline (ADR-23 bounded):** order `make_golden` -> `make_preview_golden` -> `make_package_golden`
on the canonical `.venv` (py3.12/pyarrow21, golden_env/ADR-11). After: `git status --short` + `git diff --stat`
-- the changed SET must be exactly {17 HTML goldens + golden_preview + golden_package shared/redacted/
shared_redacted HTML + `_assets/{report,catalog}.css` + the 4 source files + the touched tests}. A file outside
that set = undeclared coupling -> root-cause it.

## Done when
By-area renders via `chrome.static_table` and the summary-local leaves are on `el` (Python diff byte-neutral
-- body goldens unchanged); the 4 summary KPIs render at `var(--fs-hero)` 2.75rem
(`[data-page-kind="summary"]`-scoped, dashboard/reports normal); the hero CSS is the only golden delta;
`_pagedata`/`digests.json`/`golden_parquet` BYTE-UNCHANGED; `test_parquet_parity` + full `-m "not browser"`
suite GREEN; token guard 0 undefined; lint/ASCII/determinism clean; browser matrix SIGNED OFF before the bake;
goldens refreshed on `.venv`; QUALITY_GATES §21.2 + the el-long-tail FINDINGS row + STATE.md updated.

## As-built (DONE 2026-06-05)
- **reports/summary.py (byte-neutral componentization)** — the by-area table now builds via
  `base.static_table([Column('area','area'), Column('draws',...,numeric=True), Column('gpu',...,numeric=True),
  Column('overdraw',...,numeric=True), Column('status','status')], trows, caption='By area')`; numeric/composite
  cells are `base.raw(f'{fmt} {pill}')`, `status` the `status_badge` `_Raw`, `area` a plain str (escaped by el).
  The kpi-strip wrapper (`base.el('div', {'class':'kpi-strip'}, *kpis)`), `_change_line` (`<li>`), `_change_list`
  (`<ul class="change-list">` / `<p class="note dim">`), and the two literal `_pct_pill` branches all moved onto
  `el`. The shared chrome leaves (`summary_bar`/`callout`/`empty_state`) were DEFERRED to the el long-tail close
  (v0.2.6-5, FINDINGS G-32) to avoid off-page golden churn.
- **Hero numeral (sole output change)** — NEW `[type]` token `fs_hero = '2.75rem'`; emitted as `--fs-hero` in
  `design_tokens.css` (:root); the rule `[data-page-kind="summary"] .kpi-chip .kpi-value { font-size:
  var(--fs-hero); }` added to `components.css` under the existing summary scope. `tabular-nums` + weight-600 +
  `-0.02em` tracking inherited from the base `.kpi-value` — weight stays <=600 (`test_fonts` untouched).
  dashboard/reports carry no `.kpi-chip` so they are unaffected.
- **Gallery** — `preview._TYPE_STEPS` gains `'fs-hero'`; the type-scale demo + the (already
  `data-page-kind="summary"`-wrapped) kpi demo document the hero token.
- **Byte-neutrality PROVEN** — a fresh render diffed against the pre-bake golden was byte-identical on all 17
  pages OUTSIDE `<style>`; the ONLY style delta is `--fs-hero:2.75rem;` (:root) + the single scoped rule.
  Package shape confirms it: `redacted` (inline) HTML refreshed (CSS inlined), but `shared`/`shared_redacted`
  changed ONLY in `_assets/{report,catalog}.css` (their HTML links external CSS -> bodies byte-unchanged).
- **Gate** — `test_parquet_parity` GREEN; `_pagedata/*.js` + `digests.json` + `golden_parquet` BYTE-UNCHANGED
  (NO `make_parquet_golden`). NEW `test_design_tokens.test_v026_2_summary_hero_numeral`; `test_summary`
  (by-area + four-KPI structural asserts) PASS UNCHANGED; token guard 0 undefined. Goldens refreshed on the
  `.venv` (17 HTML + preview + package shared/redacted/shared_redacted). `pytest -m "not browser"` = 340 passed,
  1 deselected (browser smoke); the new `test_v026_2_summary_hero_numeral` is included. Browser matrix
  light/dark/print on synthetic + real Perf `c:/tmp/perf` SIGNED OFF before the bake. No new ADR (rides
  ADR-44 + ADR-42). §21.1v gets the -2 as-built; FINDINGS G-32 opened.

## Next
v0.2.6-3 (dashboard grid: shadcn-flat Grafana-dense cards; adopt static_table for the mini tables).
