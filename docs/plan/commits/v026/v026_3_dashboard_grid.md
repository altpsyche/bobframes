# v0.2.6-3 -- dashboard grid: shadcn-flat + Grafana-dense cards + static_table minis     release: v0.2.6 · phase: redesign

> The SECOND surface-redesign commit and the first DENSE one. The reports dashboard is a grid of
> small-multiple cards; decision #4 makes everything-except-the-summary Grafana-dense. The cards pack
> tighter (`dash_grid_min` 360->300, tighter gap/padding) and gain a subtle always-on 2px left accent rail
> (a 30% accent tint); the mini tables adopt `chrome.static_table` (the c16x table family, ADR-42) and the last dashboard-local bespoke builders
> (`_card`, the two `chip_cluster` strips) roll onto the `el` builder -- ticking the FINDINGS G-32
> `chip_cluster` leaf. Plan: `~/.claude/plans/bobframes-v0-2-6-visual-enumerated-bachman.md` (v0.2.6-3 row +
> decisions #2/#4). No new ADR -- rides ADR-44 (v0.2.6 visual language) + ADR-42 (component system).

## Goal
Make the dashboard read as a dense Grafana panel grid (shadcn-flat, more cards/row, hairline + a subtle
always-on 2px accent rail) while **the componentization is byte-neutral** (the mini-table + card + chip
markup does not change a byte on the golden data) -- so the ONLY golden delta is the CSS density block
(it refreshes the inlined `<style>` on every page, like 1b/-2; `_pagedata`/`digests`/`parquet` stay
byte-unchanged).

## The byte shape (verified against current source)
- **Componentization is byte-NEUTRAL on the golden.** `base.h` == `el`'s child escape == `el`'s attr
  escape (all `html.escape`). So passing each dashboard-mini cell's **plain** source value through
  `static_table`/`el` reproduces today's bytes exactly: content == today's `base.h(...)` and the per-cell
  `title=` == today's `title="..."`, single-escaped. The two `chip_cluster` strips + `_card` are
  attribute-order-identical rebuilds (`class="dash-card"` x6, `<nav class="chip-cluster" aria-label=
  "reports">`, `<div class="chip-cluster">` preserved).
- **The CSS density block is the SOLE output change.** `dash_grid_min` 360->300, `.dash-grid` gap
  sp-6->sp-4, `a.dash-card` padding sp-4->sp-3 + inner gap sp-3->sp-2 + a SUBTLE always-on 2px left rail
  `box-shadow: inset 2px 0 0 color-mix(in oklch, var(--accent-primary) 30%, transparent)` (a 30% tint --
  full-strength was too high-contrast; hover keeps the rail + adds `--elev-2`). These live in chrome.css/
  the token, inlined into every page's `<style>` -- the same all-page blast as 1b. Body markup + data path
  untouched.

## Scope
- **reports/chrome.py (Column gains `cell_title`)** -- NEW frozen field `cell_title: bool = False` on
  `Column`; `_table_td` adds a `'title'` attr to its `el('td', {...})` dict, sourced from the **plain** row
  value, when `col.cell_title and value` (a `_Raw`/pre-escaped value would double-escape -- so the
  dashboard passes plain values only). Attr order `class`->`title` matches the hand-built `<td{cls}{title}>`.
  The `Column` docstring documents `cell_title` as the dashboard-mini's *always-on* hover-reveal (responsive
  `table-layout:fixed` minis have no deterministic pixel clip -> unconditional title, c16m/c16n) -- NOT a
  general truncation knob (`clip` is that). `cell_title=False` (every summary/-4 report site) omits the
  attr -> those tables are byte-unchanged.
- **reports/formatters.py (scrub seam)** -- NEW `scrub_chrome_text(s)` (config-driven scrub, NO
  HTML-escape); `safe_chrome_text` refactored to `_html.escape(scrub_chrome_text(s))` (DRY, byte-identical:
  `None`->`''` preserved). Re-exported via `base` (import block + `__all__`). Lets the pass_gpu marker keep
  its banned-char scrub while `el` does the single escape (no double-escape; the marker lives inside a
  `<table>`, where scrub-then-el-escape is the table-correct path -- `safe_chrome_text`'s docstring says
  "outside `<table>`").
- **reports/dashboard.py (de-bespoke; byte-neutral)**
  - `_card_table` (dashboard.py:312-342) -> delegates to `base.static_table`. Keep the
    `if not rows: return base.empty_state('no data yet')` guard. Map the existing `(name, fn, num)` columns
    -> `Column(key=str(i), header=name, numeric=num, title=name, cell_title=(not num))` and rows -> dicts
    `{str(i): <plain value>}`. Text cols pass the raw string (drop `base.h`); numeric cols pass `base.fmt_*`
    (digit-strings); the marker passes `base.scrub_chrome_text(r[1])`. All 6 call sites verified to use only
    plain cells (no composite HTML).
  - `_card` (dashboard.py:345-352) -> `el('a', {'class':'dash-card','href':href}, el('h3', None, title),
    <sub>, base.raw(chart), base.raw(table))`; `<sub>` = `el('p', {'class':'dash-sub'},
    base.raw(base.safe_chrome_text(subtitle)))` if subtitle else omitted.
  - cross-report nav strip (dashboard.py:411-414) -> `el('nav', {'class':'chip-cluster','aria-label':
    'reports'}, *[el('a', {'href':href,'data-link-kind':'primary'}, lbl) ...])`.
  - A/B strip (dashboard.py:551-558) -> `el('div', {'class':'chip-cluster'}, *[el('a', {'href':
    f'ab/{pair}/{f}','data-link-kind':'primary'}, f[:-5]) ...])`. (`pair-list`/`pair-group` stay for the
    v0.2.6-5 long-tail close.)
- **reports/design_tokens.toml** -- `[layout] dash_grid_min '360px' -> '300px'` (update the inline comment
  to note the Grafana-dense drop).
- **reports/assets/chrome.css** -- `.dash-grid { gap: var(--sp-6) -> var(--sp-4) }`;
  `a.dash-card { padding: var(--sp-4) -> var(--sp-3); gap: var(--sp-3) -> var(--sp-2);
  box-shadow: inset 2px 0 0 color-mix(in oklch, var(--accent-primary) 30%, transparent); }` (subtle
  always-on rail); `a.dash-card:hover { box-shadow: var(--elev-2) -> var(--elev-2), inset 2px 0 0
  color-mix(...30%...); }` (rail + the elev lift).
  Radius-lg, the 1px `--border`, `:focus-visible`/`:active`, responsive/print rules UNCHANGED.
- **NOT touched:** fonts. Dashboard hero `summary_bar` stays `--fs-h1` (sticky.css:33), KPI strip
  `--fs-display`; `--fs-hero` is summary-only and must not leak here. print.css drops the rail via the
  existing `a.dash-card { box-shadow: none; }`; cards keep the 1px #888 print frame.

## Gates (§21.1v replacement-gate set)
- **(a) Data path FROZEN.** `test_parquet_parity` GREEN; `_pagedata/*.js` + `digests.json` +
  `golden_parquet` BYTE-UNCHANGED; **NEVER** `make_parquet_golden`.
- **(b) Structural / component asserts (golden-independent).** `test_report_structure` chip-cluster nav
  string + `count('class="dash-card"') == 6` hold under el; `test_table_component` gains a `cell_title`
  assert (text col emits `<td title=...>`, numeric/`cell_title=False` omits it, single-escapes an
  `&`-bearing value -- the R1 double-escape guard); `<th scope="col">` count, `class="num"`, no DOM reorder
  preserved.
- **(c) Token guard** -- `chrome.undefined_tokens() == set()`; the rail reuses `--accent-primary`
  (already defined), so NO new token to declare.
- **(d) Browser matrix -- MANDATORY, sign-off BEFORE goldens.** headless Chrome over `file://`, synthetic +
  real Perf `c:/tmp/perf` (newest run), light/dark/print: 300px packs more cards/row, the subtle always-on
  2px accent rail reads as a soft left edge (not high-contrast) in light+dark, dark legibility, print keeps
  the #888 frame (rail dropped), mini tables clip + hover-reveal title (single-escaped), long real-Perf area
  names legible via hover at 300px (R4), mini caption reads right in the denser card (R5).
- **(e) Lint / ASCII / determinism** -- per-page `_lint_or_raise`, whole-page ASCII, render-twice identical;
  no `Math.random`/`Date`/`fetch`/`type="module"`. No new dep / build step (ADR-37 holds).

**Golden discipline (ADR-23 bounded):** order `make_golden` -> `make_preview_golden` -> `make_package_golden`
on the canonical `.venv` (py3.12/pyarrow21, golden_env/ADR-11). After: `git status --short` + `git diff
--stat` -- the changed SET must be exactly {17 HTML goldens + golden_preview + golden_package shared/
redacted/shared_redacted HTML + `_assets/{report,catalog}.css` + the 6 source files (chrome.css/chrome.py/
dashboard.py/design_tokens.toml/formatters.py + base.py for the `scrub_chrome_text` re-export) + the
touched tests}. A file outside that set = undeclared coupling -> root-cause it.

## Done when
The dashboard grid is Grafana-dense (300px min, sp-4 gap, sp-3 card padding, sp-2 inner gap) with a subtle
always-on 2px accent rail (30% tint); the mini tables render via `chrome.static_table`, `_card` + both `chip_cluster`
strips build via `el` (Python diff byte-neutral -- mini/card/chip markup unchanged on the golden); the CSS
density block is the only golden delta; `_pagedata`/`digests.json`/`golden_parquet` BYTE-UNCHANGED;
`test_parquet_parity` + full `-m "not browser"` suite GREEN; token guard 0 undefined; lint/ASCII/
determinism clean; browser matrix SIGNED OFF before the bake; goldens refreshed on `.venv`; QUALITY_GATES
§21.1v + the el-long-tail FINDINGS G-32 (`chip_cluster` ticked) + STATE.md updated.

## As-built (DONE 2026-06-06)
- **Density (CSS, the SOLE output change).** `design_tokens.toml [layout] dash_grid_min 360->300px`;
  `chrome.css .dash-grid gap sp-6->sp-4`; `a.dash-card padding sp-4->sp-3` + inner gap `sp-3->sp-2`. Radius-lg
  + the 1px `--border` hairline + `:focus-visible`/`:active`/responsive/print rules UNCHANGED. Browser matrix:
  real Perf packs **4 cards/row at 1600px** (was 3 at 360px); legible.
- **Accent rail = SUBTLE always-on 30% tint (user-confirmed).** Iterated: full-strength `--accent-primary`
  read too high-contrast (a near-black/near-white 2px bar); a `color-mix(... 30% ..., transparent)` tint
  tames it to a soft left edge that still re-hues under `[theme]`/`--accent`. A hover-only variant was tried
  but the user preferred the (lighter) always-on rail, so the rail stays on the resting `a.dash-card`
  (`box-shadow: inset 2px 0 0 color-mix(in oklch, var(--accent-primary) 30%, transparent)`); `:hover` keeps
  the rail + adds the `--elev-2` lift. Print drops it (cards keep the #888 frame). Confirmed light+dark in
  the browser matrix.
- **Componentization byte-NEUTRAL on the golden.** `_card_table` -> `base.static_table` (Columns built from
  the existing `(name, fn, num)` tuples; every cell a PLAIN value -- text raw, numeric `fmt_*`, marker
  `scrub_chrome_text`). `_card` + both `chip_cluster` strips (cross-report `<nav>` + A/B `<div>`) -> `el`.
  PROVEN: a fresh render diffed byte-identical to the pre-bake golden on all 17 pages OUTSIDE `<style>` (the
  ONLY golden delta is the CSS); `test_report_structure` (chip-cluster nav string + 6x `class="dash-card"`)
  held under `el` with NO edit.
- **NEW `Column.cell_title` (chrome.py) + `formatters.scrub_chrome_text`.** `cell_title` emits the dashboard
  mini's always-on per-cell `title=` from the PLAIN value so `el` escapes it once -- the review caught that
  the original plan (passing a pre-escaped `_Raw`) would DOUBLE-escape the marker title [R1]; `scrub_chrome_text`
  (scrub-only; `safe_chrome_text` now wraps it, byte-identical) feeds the marker plain so scrub + single-escape
  both hold. `cell_title=False` (every summary/-4 report site) omits the attr -> unchanged. Re-exported via `base`.
- **Gate.** `test_parquet_parity` GREEN; `_pagedata/*.js` + `digests.json` + `golden_parquet` BYTE-UNCHANGED
  (NO `make_parquet_golden`). NEW `test_design_tokens.test_v026_3_dashboard_grafana_dense` (300px, sp-4 gap,
  sp-3 padding, the 30%-tint rail on BOTH rest + hover -- `count == 2`); NEW `test_table_component` `cell_title`
  (single-escapes an `&`-bearing value -- the R1 guard); `test_c16d_depth_over_borders_css` hover pin updated
  in-commit. `pytest -m "not browser"` = **342 passed**, 1 deselected; token guard 0 undefined. Goldens
  refreshed on the `.venv` (17 HTML + preview + package shared/redacted/shared_redacted -- shared/shared_redacted
  changed ONLY in `_assets/{report,catalog}.css`, bodies byte-unchanged). Browser matrix light/dark/print
  synthetic + real Perf `c:/tmp/perf` SIGNED OFF before bake. Scope confirmed via `git status`/`diff --stat`:
  6 source + 2 tests + the declared goldens, nothing outside. No new ADR (rides ADR-44 + ADR-42); §21.1v gets
  the -3 as-built; FINDINGS G-32 `chip_cluster` ticked.

## Next
v0.2.6-4 (6 detail reports: adopt the Column+data_table family across overdraw/instancing/shader_hotlist/
trend/draws_by_class).
