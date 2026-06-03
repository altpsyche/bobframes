# Quality gates

> Carved from CLI_PLAN §11 (testing strategy) + §21 (safeguards). These run in CI on every push and
> are the contract behind "output as good or better than today." The golden-parity gate is the
> backbone that makes every refactor safe.

## Testing tiers (§11)

| Tier | What | Where | When |
|---|---|---|---|
| Unit | lint banlist; schema dtype inference; path helpers; discovery regex; stable_keys; classifier | `tests/unit_*.py` | pytest local + CI per push |
| Render smoke | render-only against bundled synthetic `_data/` | `bobframes smoke` (no `--data`) | CI per push |
| Full smoke | ingest + render against real `.rdc` corpus | `bobframes smoke --data <path>` | manual / nightly; needs Windows + RenderDoc |
| Schema regression | every parquet's columns match `schemas.expected_columns(stem)` exactly | inside smoke | both tiers |
| Lint regression | every emitted HTML passes `lint.lint_file` | report build (already enforced) | both tiers |

**Test corpus:** real `.rdc` corpus not bundled (size); README documents internal-share download +
SHA256. Synthetic bundled corpus ~500KB at `tests/data/synthetic/`, mimics `SCHEMA_VERSION=3`.
**Per [ADR-6](../DECISIONS.md): generate the synthetic by anonymizing/down-sampling a real ingest,
not by hand** — verify it exercises every `class_order` bucket and every `[pass_strip]` rule before
freezing the golden, or the parity gate gives false confidence on unexercised paths.

## 21.1 Golden-snapshot parity (byte-identical HTML before/after every refactor)

```
tests/data/
  synthetic/          # tiny _data/ tree (~500KB), SCHEMA_VERSION=3
    _data/<area>/<drop>/*.parquet   _data/_catalog.parquet
  golden/             # frozen expected HTML output
    index.html  _reports/*.html  _reports/drill/<area>/<drop>/index.html
```
`tests/parity.py`: copy synthetic → tmp, `bobframes render`, assert each `golden/**.html` byte-equal.
**Refresh** (only on intentional output change): re-render synthetic → copy to `golden/` → review
diff in PR.

## 21.1b Parquet-output parity (G-14) — see [c06b](../commits/v02/c06b_parquet_parity_gate.md)
`test_parity` gates **HTML only** (it skips `_data`/`_cache`), so a data-path regression — e.g.
c05's `_global_entities` row-order shift — is invisible to it. `tests/test_parquet_parity.py` closes
that: render synthetic → walk every `_data/**/*.parquet` → compare a **writer-independent logical
digest** (schema + row order + cell values) against `tests/data/golden_parquet/digests.json`.
The digest hashes `Table.to_pydict()` in schema column order (non-finite floats → fixed sentinels),
**NOT on-disk bytes** — those vary by pyarrow writer version (the D-8 trap). Because the digest is
logical, this gate runs on the **FULL matrix** (proven identical py3.10/pa17 ↔ py3.13/pa21), unlike
HTML parity which [ADR-11](../DECISIONS.md) pins to the canonical cell. **Refresh** (only on
intentional data-path change): `python -m bobframes.tests.make_parquet_golden` → review diff in PR.

## 21.1c Config defaults reproduce literals (c07, ADR-6) — see [c07](../commits/v02/c07_toml_config.md)
The c07 TOML config lifts timeouts, the drop-folder regex, the lint banlist, the chrome-scrub regex,
complexity weights, and delta/formatter knobs out of code. Bundled defaults (`_default_config.toml` +
`lint_banlist.toml`) must reproduce today's output **byte-identically**, so `tests/test_config.py`
asserts: regex `.pattern` equality (`dated_re`, `chrome_scrub_chars`), `delta.fmt` string identity,
and **bit-for-bit** floats (`struct.pack('>d', …)`) for every complexity weight + threshold + timeout
(tomllib must parse `0.3`/`2.0`/`8.0` to the same double as the Python literal). The banlist TOML
round-trips to the exact original 15-entry `lint.BANNED` (patterns + flags + order). Because the
defaults are bit-identical, **`test_parity` + `test_parquet_parity` stay green with no golden refresh**.
The **CI matrix is unchanged** (3.10 retained, ADR-26): the loader runs under `tomli` on the 3.10 cell
and stdlib `tomllib` on 3.12/3.13, and the digest gates assert identical loaded values across cells —
proving `tomli`↔`tomllib` equivalence, not assuming it. Spawn-safety: the convert timeout is threaded
into the pool worker as an argument (not read from a child-side singleton), gated by
`test_convert_timeout_threaded_as_argument`.

## 21.1d Design-token + preview parity (c08, ADR-6/27) — see [c08](../commits/v02/c08_design_tokens.md)
c08 lifts the `chrome` CSS token VALUES + the base layout literals into `reports/design_tokens.toml`,
routing them through a value-only `string.Template` skeleton (ADR-27), so the emitted `:root` block and
layout rules are byte-identical — **`test_parity` stays green with no golden refresh**.
`tests/test_design_tokens.py` adds focused, golden-independent guards: substitution leaves no `$`
placeholder; the hand-aligned color lines (incl. the 3-space `--c-other` alignment) and every layout
literal land verbatim; `sparkline_svg` defaults are `(60, 14)` from `[layout]`; the bundled TOML is
ASCII; and `export-tokens --format {toml,json,css}` round-trips. The new `preview` gallery has a
dedicated byte-golden at `tests/data/golden_preview/_chrome_preview.html` (OUTSIDE `golden/` so the
`test_parity` file-set walk is unaffected; refresh via `python -m bobframes.tests.make_preview_golden`)
and is asserted deterministic (no build timestamp). Q-6's `chrome.report_page(...)` extraction is
covered transitively by `test_parity` (the 6 reports + dashboard route through it byte-identically).

## 21.1e Classifier parity + the D-6 deletion (c09, ADR-6/29) — see [c09](../commits/v02/c09_classifier.md)
c09 lifts UE draw classification + pass-strip + frame-prefix + GPU-counter aliases into TOML presets
(`derives/draw_classifier.toml` = UE default) behind one analysis-layer API (`derives/classifier.py`),
a **state-capable** rule engine (`when{}` over any draw column; markers are a refinement). Bundled
defaults reproduce today's output **byte-identically** — `test_parity` + `test_parquet_parity` stay
green with **no golden refresh**. `tests/test_classifier.py` adds golden-independent guards: the UE
preset matches a frozen copy of the former `derive_post_merge._classify_draw` over a 300+ case oracle
battery (every rule + sub-pattern + blend/depth precedence); `frame_prefix_re().pattern` /
`pass_strip()` / `gpu_duration_aliases()` / `class_order()` equal the former literals; every
`--c-<name>` for name in `class_order` is present in the emitted `:root` block (H-5 names↔order); a
`when{}`-only mini-spec classifies without markers (the c27 generic-preset path); a Unity preset
reclassifies a Unity-style marker; and `replay_main` no longer defines `_classify_draw`. **D-6
collapse:** the drifted replay-side classifier (fed only the dead `passes.draws_by_class_*`, superseded
by `pass_class_breakdown`) is **deleted**, so the replay stage emits facts only (§21.9 by
construction); those 9 columns stay zeroed under the frozen schema (the §21.3 replay-drift gate stays
green), full removal deferred to c35. Real-`.rdc` re-validation that replay still runs is the
self-hosted/nightly smoke (CI never runs replay, §21.6).

## 21.1f Report-quality polish (c16, ADR-6/32) — see [c16](../commits/v02/c16_report_quality.md)
c16 adds hero KPI strips, insight callouts (`chrome.callout`, config `[report]` thresholds), heatmap
shading (`chrome.heatmap_cell`), a header provenance/device strip (`chrome.provenance_strip`, deterministic
via the synthetic manifest's stub `host_info`/`tool_versions`; the `bobframes` version is deliberately
**not** rendered, so a release bump never churns the golden), and icon empty-states — across all reports.
This **changes rendered HTML**, so the golden is **refreshed** here (reviewed: the only drill/root deltas
are the D-11b dead-CSS removal + the shared `.callout`/`.empty-state` rules). `test_parquet_parity` stays
green with **no** `digests.json` refresh (extraction untouched, §21.9). The manifest schema-version guard
(D-7) is **parity-neutral**: a current-version synthetic manifest passes, so every render gate stays green;
`test_manifest_guard` forces the mismatch. Cache integrity (R-13) is covered by `test_cache` (SHA256 sidecar
+ corrupt→warn→None + missing-column tolerance), empty-state by `test_report_polish` (a 0-row synthetic
render shows the friendly message), and sparkline null-gaps by `test_delta` (golden-independent; the live
series never emits `None` today, G-16).

## 21.1g Inline-SVG chart determinism (c16b, ADR-6/33) — see [c16b](../commits/v02/c16b_report_viz.md)
c16b leads each of the 6 reports with a visualization from `reports/charts.py` — deterministic,
dependency-free server-side inline SVG (fixed-precision coords mirroring `delta.sparkline_svg`, no
`random`/`Date`/timestamps), themed from `design_tokens.toml` `[chart]` (sizes) + existing CSS `var(--...)`
colors, with the detail table kept directly below as the exact/accessible fallback. Because the SVG is
logically deterministic it **rides the golden byte-parity gate** like the rest of the HTML (no `<canvas>`,
no vendored JS lib that would force a parity carve-out — the ADR-11 trap). The output-changing render means
the HTML golden is **refreshed here** (`python -m bobframes.tests.make_golden`, reviewed page-by-page:
the 6 reports gain a `<figure class="chart">` + the shader column-diet reshape; index/dashboard/drill change
only by the shared chart CSS). `test_parquet_parity` stays green with **no** `digests.json` refresh
(presentation only, §21.9). `test_charts` adds golden-independent guards (determinism = same input → same
bytes; SVG structure = `role="img"`/`<title>`/`<desc>`; token theming; empty-series → safe `''`; an
ASCII-only guard since chart `<text>`/`<title>`/`<desc>` ride **outside** `<table>` and are therefore linted
— labels are scrubbed via `safe_chrome_text`). Chart-first + table-as-fallback is the report pattern. The
restructure (section framing, copy buttons, dashboard small-multiples, fuller a11y) is
[c16c](../commits/v02/c16c_report_restructure.md).

## 21.1h Report restructure: framing + copy + a11y (c16c, ADR-6/32/33) — see [c16c](../commits/v02/c16c_report_restructure.md)
c16c routes every report section through `chrome.section_card` wrapped in `<rdc-sticky-h2>` (the
component's `querySelector` was relaxed `h2[id]` -> `h2` so a card's id-less header h2 still drives the
in-view highlight; section ids stay the anchor targets, so `#area`/`#gpu`/`#class_counts` resolve
unchanged). Copyable IDs carry `<rdc-copy-button data-value=...>` — the **full** value (mesh hash / shader
stable_key + src path / pass path), routed through `safe_chrome_text` even though it rides inside `<td>`.
The instancing "material batching" section is **fill-or-hide** (no bare heading over an empty-state).
Accessibility: every report `<table>` gets a `<caption>` + `scope="col"` on every `<th>` (zero bare
`<th>` left in reports + dashboard), and the trend gpu-delta KPI prints an explicit sign so regression
direction is not tone-colour-only. The dashboard gains a per-card small-multiple (mini bars; a class-share
donut on draws-by-class, matching its flagship), an insight subtitle, and a cross-report nav. The card
framing CSS lives in `_CHROME_CSS_TMPL` (literal `var()`, no `$`), so drill/root/preview change **only** by
that shared CSS (no structural churn). Output-changing -> the HTML golden + preview golden are **refreshed
here** and reviewed page-by-page (per-report structural-marker diff: cards/sticky/copy/caption/scope in,
bare h2/th out). `test_parquet_parity` stays green with **no** `digests.json` refresh (presentation only,
§21.9). `test_report_structure` adds golden-independent guards (section_card + sticky wrap present; the 3
named reports carry copy buttons with full-length payloads; tabled reports balance `<th >` with
`scope="col"` and have a `<caption>`; instancing hides `id="batching"`; the dashboard has 6 mini charts +
6 subtitles + the nav; a whole-page ASCII guard). `test_design_tokens` pins the new card/caption CSS.

## 21.1i Report visual language: depth, type, chart finish, motion (c16d, ADR-6/27/34) — see [c16d](../commits/v02/c16d_report_aesthetics.md)
c16d is the design-language pass over the c16/c16b/c16c info-design, shipped as **four reviewable
sub-commits** (a depth+tokens / b type+Inter / c chart-finish / d micro+pacing), each refreshing the golden
with one review hypothesis (the minified report pages are NOT line-diffable, so each refresh is checked by
structural-marker counts **plus a real browser render** in light/dark/reduced-motion/print). **Depth over
borders:** cards/chrome read by `var(--surface-1)` + a soft `var(--elev-1/2/3)` shadow (a new `[shadow]`
token block through the ADR-27 skeleton, asserted byte-exact in `test_design_tokens`), tables are
horizontal-rule only, severity is a `color-mix` box tint, and the sticky-h2 in-view cue is a `::before`
marker (the h2 left-accent is gone — verified by forcing `aria-current`). **Type:** a **vendored Inter
subset** (29 KB woff2, base64-inlined `@font-face`, ADR-34) gives KPI/summary display numbers + headings a
real geometric sans with `tabular-nums`; data tables stay monospace. `test_fonts` pins that the woff2 ships
(wheel: 162/162 unique entries, ADR-10 holds), is inlined offline (no `http(s)://` in the CSS), ASCII, on
both CSS paths, and base64-deterministic. **Chart finish:** gradient fills (deterministic, caller-threaded
`chart_id` gradient ids — NO `hash()`/counter), dimmed axes (`[chart].axis_color` -> `--border-1`), and
per-datum `<title>` tooltips; `test_charts` adds gradient-present/unique-per-page/deterministic +
per-datum-title + axis-dim guards while the existing element-count/theming/determinism asserts stay green.
**Motion:** hover `scale(var(--hover-scale))` + spring **no-ops under `prefers-reduced-motion`** by
construction (reduced-motion `:root` sets `--hover-scale: 1` + `--motion-spring: 0s`); print kills shadows
and re-adds a thin paper border. Output-changing -> golden HTML + preview **refreshed** across all four
sub-commits; `test_parquet_parity` stays green with **no** `digests.json` refresh (presentation only,
§21.9); `test_report_structure` stays green (CSS/token-first, DOM unchanged). 115 -> 128 green.

## 21.1j Per-run truth: the run model (c16e, ADR-6/35) — see [c16e](../commits/v02/c16e_run_model.md)
c16e makes the dashboard + the five single-state reports report ONE current run (default newest) instead of
the cumulative union of all runs (G-19). The model has a single implementation — `reports/discovery.py`
`current_run` / `baseline_run` / `RunContext`, resolved per build via `run_context` and threaded into
`report_page`/`header` as one `run=` argument — so a new report obtains per-run truth + the run-naming header
by passing its `RunContext`, and cannot silently re-introduce the cumulative bug. **`test_run_model`**
(golden-independent) pins the model: the resolver primitives (`current_run` defaults newest, override by
label/date, `[]`->None; `baseline_run` = immediately-prior, None for single/oldest; `RunContext.ordinal`/
`is_newest`/`n_runs`); the **dashboard "total draws" equals the newest drop's `frame_totals` sum and is
strictly less than the cross-run sum** (the flaw, caught numerically); the **invariant** that every LIVE
instancing candidate (its full mesh-hash via the copy button) is a subset of the current run's drawn meshes
(so a removed mesh can never linger as live), plus a skip-guarded check that a baseline-only mesh is absent;
and that each single-state report + the dashboard name their current run in the header while `trend_table`
(the across-run view) does not. `test_report_structure` adds `test_header_names_current_run` +
`test_resolved_since_separated_from_live` (resolved-since is a distinct `section.card`, never nested in the
live list). Output-changing -> the HTML golden (dashboard + 5 reports) is **refreshed + browser-reviewed**
(light/dark); drill/root/preview goldens are **unchanged** (the new params do not reach
`template.render_drop`/`render_root`); `test_parquet_parity` stays green with **no** `digests.json` refresh
(aggregation/presentation only, extraction untouched, §21.9). 132 -> 142 green.

## 21.1k Multi-run UX: the run selector (c16f, ADR-6/35) — see [c16f](../commits/v02/c16f_multirun_ux.md)
c16f layers the navigation/comparison UX on the c16e run model (G-18). Mechanism = **pre-rendered per-run
pages**: top-level `_reports/<report>.html` is the newest run (the default); each OLDER run gets a
self-contained page set under `_reports/run/<run_key>/` (mirroring `_reports/ab/<pair>/`), bounded by
`[report] max_prerendered_runs` (default 10) with the orchestrator **logging** anything dropped beyond the cap
(no silent truncation, ADR-23; overflow stays reachable via `trend_table`, which is NOT pre-rendered per run).
A **run selector** reuses the `rdc-ab-picker` web component (a static `<select>` whose `value` is a relative
link - no network, no new JS; a distinct `rdc-run-select` id so it coexists with the A/B picker); links are
depth-prefixed so they resolve from both the top level and `run/<key>/`. A fixed (immediately-prior) baseline
drives a **"current vs baseline" banner** (reusing the `.ab-strip` chrome, baseline dimmed via `.dim`); a
**"viewing an older run" callout** appears only on non-newest pages and links back to the newest. Selection
**persists dashboard -> per-report** because each `run/<key>/` dir is a self-contained sibling set (the
dashboard's report links stay bare; only `trend_table` + the A/B index point up to the top level). **A/B pages
suppress** the run selector + banner (`ab is not None`). **`test_run_model`** gains the c16f gate: the per-run
page set is emitted (5 single-state reports + dashboard per older run; trend_table excluded), the picker lists
every run + marks the current one + its links resolve from both depths, the older-run cue shows only on
non-newest, the baseline banner shows current+prior (and is absent on the oldest run), nav persists within
`run/<key>/`, and an A/B page has no run picker. `test_config` pins `max_prerendered_runs == 10`. Output-changing
-> the HTML golden gains the 6 per-run pages + the picker/banner on the 6 top-level pages, **refreshed +
browser-reviewed** (light/dark, top-level + per-run); drill/root/preview goldens unchanged; `test_parquet_parity`
green with **no** `digests.json` refresh (§21.9). 142 -> 148 green. (G-20, collapsing the per-drop columns at
3+ runs, is deferred - no 3+-run data to verify; see FINDINGS.)

## 21.1l Catalog + drill readability + heavy-data decoupling: the html/template.py layer (c16i + c16j, ADR-6/27/34/37) — see [c16i](../commits/v02/c16i_catalog_drill_readability.md), [c16j](../commits/v02/c16j_data_decoupling.md)
c16i brings the c16d treatment to the STATIC catalog (root `index.html`) + per-drop drill (`html/template.py`),
the layer the reports pass (c16b-f) never touched (G-21 **readability half**; the heavy-data half is c16j). Four
parts, all server-rendered + deterministic, no contract change: (1) **type split** - `table.data` defaults to the
Inter sans stack at line-height 1.3; mono + `tabular-nums` is re-asserted ONLY on numeric/`.mono` BODY cells
(headers stay sans; **longhands**, not the `font` shorthand, to preserve line-height), with a name-keyed `monoCols`
set keeping ID/hash/path columns mono. (2) **roomier rows** - `ROW_H` is single-sourced from a Python `_ROW_H=32`
(sentinel-substituted into the JS; the JS constant is the SOLE virtual-scroll driver, the CSS sets NO row height -
a `tr{height}` rule would fight the dynamically-sized spacers); 6px padding; 14px x 1.3 + 12px + 1px = 31.2 <= 32
so a row never overflows ROW_H and the scroll stays aligned. (3) **client-side heatmap** - numeric MAGNITUDE
columns (excludes ID/`event_id`/`labelCols` + single-value) shade the whole cell by relative value via
`background-IMAGE` only (a UNIFORM `color-mix(in oklch, var(--accent-data) 0-30%, transparent)`, no gradient edge),
so the class-driven `background-color` zebra/hover still shows through; deterministic (no `random`/`Date`),
aria-labelled, number always on top. (4) **collapsible column groups** (catalog only) - a deterministic
group->column map from `schemas.table_category` (Metadata/Workload/Resources/Samples; Metadata+Workload open)
emitted as `window.__colgroups_catalog`; the VTable builds real `<button aria-pressed>` toggles + a `hiddenCols`
set, with the sort-arrow loop keyed on `th.dataset.ci` so it stays correct when columns are hidden. Plus:
`.table-scroll` sizes to content capped at 60vh (small tables stop reserving an empty 60vh box; folds in the
never-applied `.short` variant), and a drill **visual hierarchy** - `details.category` becomes a left-anchored
bold-accent group LABEL + nesting rail (not a box), each `section.table-section` becomes a card; these override the
shared chrome in `_PER_DROP_CSS` so the reports/dashboard goldens stay byte-unchanged. **`test_report_structure`**
gains 6 c16i guards (type split, ROW_H/padding lockstep, heatmap determinism/offline + no `background=` shorthand,
column-group exact-partition, reports-layer-untouched, deterministic render). Output-changing -> the root
`index.html` + the drill golden are refreshed + **browser-reviewed** (light/dark, synthetic + real Perf);
reports/dashboard/per-run goldens byte-unchanged; `test_parquet_parity` green with **no** `digests.json` refresh
(§21.9). 165 -> 171 green.

**c16j - heavy-data decoupling (the ~21 MB TTI fix; static, ADR-37).** Each VTable's row payload (formerly
inlined as `<script>window.__data_<key>={...}</script>`) is now written to its own `_pagedata/<key>.js`
(`window.__data_<key>={...};`, same compact `json.dumps(separators=(',',':'))`) and referenced by a CLASSIC,
file://-safe `<script defer src="_pagedata/<key>.js">` - so the HTML shell paints first and the data streams
as its own resource (real Perf heaviest drill: a ~17.6 MB single HTML file -> a 134 KB shell + 17.5 MB across
28 `.js`). `_pagedata/` is a NEW dir sibling to each page's `index.html` (catalog `<root>/_pagedata/`; drill
`<root>/_reports/drill/<area>/<drop>/_pagedata/`), deliberately NOT `_data/` (the parquet/data contract) - so
the `src` is always literally `_pagedata/<key>.js` (no relpath, no collision); this refines the c16j doc's
loose `_data/<key>.js`. Only the HEAVY `__data_*` moves; the small `__colgroups_catalog`/`__labels` + the
shared `_JS` VTable code stay INLINE. Offline-safe: classic script (NO ES modules - Chrome blocks `file://`
modules), NO `fetch`/XHR; byte-deterministic; the bootstrap reads `window.__data_*` only inside its
`DOMContentLoaded` listener, which fires AFTER all `defer` scripts -> no race. A CSS-only
`.table-scroll:empty::before{content:'loading...'}` (in `_PER_DROP_CSS`, catalog/drill only) shows until the
VTable injects rows. The parity harness gains `_render_util.rendered_page_data_files` (walks `_pagedata/*.js`)
+ a second `test_parity` block (file-set equality + raw byte-compare, no normalize) + `make_golden` writes the
`.js` companions; `test_report_structure` repoints its `__data_catalog` read to the companion + adds 5 c16j
guards. **Reports/dashboard/per-run/A-B goldens BYTE-UNCHANGED** (they bake rows into HTML, never used
`__data_*`; only the catalog `index.html` + each drill `index.html` change, plus the added `_pagedata/*.js`);
`test_parquet_parity` green with NO `digests.json` refresh (§21.9). 171 -> 176 green; browser-verified offline
(headless Chrome, `file://`, real Perf): the catalog + heaviest drill populate their VTable from
`_pagedata/*.js` with c16i's type split + heatmap + column groups intact.

## 21.1m The unified `rdc-table` component: two data-delivery modes (c16k, ADR-38) — see [c16k](../commits/v02/c16k_unified_table_component.md)
c16k replaces the two divergent table ENGINES (the catalog/drill VTable + the reports' `rdc-sortable-table`)
with ONE bespoke `rdc-table` (no third-party grid — ADR-6/37). It is a single IIFE in `reports/chrome.py`
(`_RDC_TABLE_CSS` + `_RDC_TABLE_JS`, exposed as `rdc_table_css()`/`rdc_table_js()`/`rdc_table_assets()`,
re-exported via `base.py`): shared `cmpVals` (natural-numeric per ADR-24, comma-stripping so it is correct for
both raw JSON numbers and comma-formatted display text) + shared `tintImage` (the c16i uniform-tint
`color-mix(in oklch, var(--accent-data) 0-30%, transparent)` heatmap), a `VTable` class (the **virtual** mode:
windowed, rows from `window.__data_<key>`/`_pagedata/*.js`) and a `StaticTable` class (the **static** mode:
parses the server-baked `<table class="data">`, sorts by reordering the live `<tr>` nodes, tints existing
`<td>`s, toggles column visibility via `display`). It is bootstrapped from ONE `DOMContentLoaded` pass
(`querySelectorAll('rdc-table[data-mode]')`, branch on `data-mode`), NOT a `customElements`/`connectedCallback`
— so it dodges the parse-time empty-children + `defer`-script race and matches the old VTable timing.
**The contract (both modes):** offline (classic `<script>`, NO `fetch`/XHR/ES-modules), byte-deterministic
(NO `random`/`Date` in the rendered output; the runtime `Math.random` live-region id is the *separate*
`rdc-sortable-table`, never serialized), ASCII, `file://`-safe, ZERO new dependency, one CSS class
(`table.data`).
- **`static`** (a report, e.g. shader_hotlist; the ADR-37 guarantee): rows are **server-baked into the HTML**
  → **golden-visible**, render with **JS disabled**, **print all rows**, and **Ctrl-F finds an off-screen row**
  (the static engine NEVER windows — every `<tr>` stays in the DOM; sort/heatmap/column-groups are pure
  in-place enhancement). The `<td>` row **content** stays byte-stable (only the wrapper/markup/classes move);
  report `class="num"` cells are aliased to the `table.data` numeric/mono treatment by CSS (no cell reclassing,
  so the shared delta/heatmap/sparkline helpers are untouched). Column groups are declared per report as
  `window.__colgroups_<key>` keyed by **column index** (report header text can repeat, e.g. multi-drop
  `delta`). The engine ships **opt-in** via `report_page(rdc_table=True)` → `page_open` appends
  `rdc_table_assets()` to `<head>`; default-False leaves the shared `_compose_css/_compose_js` bundle
  byte-identical, so every report/dashboard/A-B/per-run page NOT migrated this commit stays **byte-unchanged**.
- **`virtual`** (catalog + drill): rows stream from `_pagedata/*.js` (the c16j contract, **byte-identical**)
  and the DOM is windowed (`ROW_H=32`). The old `template._JS`/`_JS_TMPL`/`_ROW_H` were DELETED (subsumed into
  `rdc-table`, zero dead code); the host `div.table-scroll` → `<rdc-table data-mode="virtual" class="table-scroll">`.
`test_report_structure` gains 4 c16k guards (rdc-table virtual on catalog/drill with both engine classes
present + offline; the static proof's server-baked rows un-windowed + index-keyed colgroups + the empty
toggle-bar; static coexists with the still-present `rdc-sortable-table`; the other reports carry NO
`<rdc-table>`), and `test_c16i_reports_layer_untouched` is relaxed to allow shader_hotlist's own
`__colgroups_shader_hotlist`. **Output-changing → refreshed EXACTLY** the catalog `index.html`, the one drill
`index.html`, and both `shader_hotlist.html` variants (top-level + per-run); `_pagedata/*.js`, the other 5
reports + dashboard + per-run/A-B goldens, and `digests.json` are **byte-unchanged**; `test_parquet_parity`
green with NO digests refresh (presentation only, §21.9). 176 -> 180 green. Browser-verified offline (headless
Chrome, `file://`, real Perf): virtual catalog/drill still build/scroll/sort/search with heatmap + column
groups; static shader_hotlist shows all rows server-baked (JS-off/print/Ctrl-F safe) with client sort +
column-groups + heatmap (the static auto-heatmap + natural-numeric sort + group-collapse paths proven on a
crafted varying-data table — real Perf's `uses`/`cost` are all 0, so the auto-tint correctly no-ops while
`complexity` shades via `rdc-heatmap-cell`). **G-23 is NOT closed here** — the BUILD half only; the rollout +
deletion of `rdc-sortable-table` is c16l, truncation is c16m.

## 21.1n The `rdc-table` rollout: ONE table system (c16l, ADR-38, G-23 resolved) — see [c16l](../commits/v02/c16l_unified_table_rollout.md)
c16l rolls the `static` mode onto **every** remaining tabular surface and **deletes** the old second system, so
the codebase has ONE table engine (G-23 fully resolved). **Engine now always-on:** `_RDC_TABLE_CSS`/`_RDC_TABLE_JS`
fold into `chrome._compose_css/_compose_js`, so every report/dashboard/A-B/per-run/preview page ships the engine
(the c16k opt-in `report_page(rdc_table=True)` + `page_open(rdc_table=)` + `rdc_table_assets()` are DELETED;
`rdc_table_css()`/`rdc_table_js()` stay — `template.py` still composes its own catalog/drill bundle, so the fold
does NOT double-include). **Reports migrated:** every `<rdc-sortable-table><table class="report">` →
`<rdc-table data-mode="static" data-table="<key>"><table class="data">` (overdraw, draws_by_class, instancing ×3,
shader_hotlist secondary+resolved, trend ×3); `<td>` content stays byte-stable (only wrapper/class moves), so the
type-split + auto-heatmap + client sort come **free** and ADR-37 holds (rows server-baked → JS-off / print /
Ctrl-F / golden-as-output). `class="report"` retired for `class="data"`; the report-table semantics `table.data`
lacked (styled `<caption>`, first-child emphasis) move into `_RDC_TABLE_CSS` scoped to `rdc-table[data-mode="static"]`,
and the 380px cell clip is **opted out** there (report cells hold copy-buttons / sparklines / links — c16m owns
controllable truncation). The print + narrow-viewport `table.report` rules are re-homed (static-scoped) so
catalog/drill (virtual) gain no new render churn. **Column groups** added to `overdraw` (a separable current /
per-drop-history split, history collapsed) alongside shader_hotlist; instancing / trend / draws_by_class ship as
clean sort+heatmap tables — they have no separable wall (a collapse would hide the headline metric), a deliberate
ADR-23 scoping. **a11y:** the `StaticTable` now sets `aria-sort` on headers (none→ascending/descending), restoring
the sort-state announcement the deleted `rdc-sortable-table` provided; `<caption>` + `scope="col"` + real `<th>` +
`<button aria-pressed>` column toggles intact. **Dashboard/preview minis** become bare `<table class="data">`
(NOT wrapped) — a 3-row preview inside a card-link `<a>` must not gain sortable headers (sort + navigate conflict);
they get the unified styling, no enhancement. **Deleted:** `rdc-sortable-table` (web component + CSS + JS class +
`customElements.define`) and the now-dead `table.report` CSS — grep-clean (no `rdc-sortable-table` / `RdcSortableTable`
/ `class="report"` anywhere). `test_report_structure` swaps the c16k coexistence guards for c16l guards (sortable
GONE everywhere; every tabled report on `static` rdc-table with server-baked `<tr>`; pass_gpu has none; dashboard
minis bare `table.data`; engine in the shared bundle; `aria-sort` present); `test_design_tokens` re-points the caption
assert to `rdc_table_css()`. **Output-changing → refreshed** all 6 reports + dashboard + 6 per-run + catalog + drill +
the preview gallery (reports/dashboard by markup+bundle; catalog/drill by the dead-byte removal + the inert
static-scoped CSS the engine string carries). `_pagedata/*.js`, `digests.json`, `golden_parquet` **byte-unchanged**;
`test_parquet_parity` green with NO digests refresh (presentation only, §21.9). 181 green. `bobframes smoke`
render-only 15 pages lint clean exit 0. Browser-verified offline (headless Chrome, `file://`): static reports show
all rows JS-off, enhance in place (sort + `aria-sort` + auto-heatmap + real column-group toggle buttons, no JS
errors, no clipped widgets); dashboard minis stay un-enhanced; catalog/drill virtual unchanged.

## 21.1o Cell truncation + hover-reveal: the unified `rdc-table` truncation contract (c16m, ADR-38) — see [c16m](../commits/v02/c16m_cell_truncation_hover.md)
c16m adds **controllable per-column truncation** to the one `rdc-table` engine, replacing the c16l no-clip
stopgap (`rdc-table[data-mode="static"] table.data tbody td { max-width:none … }`) with a real policy.
**One mechanism, both modes:** the clip lives on an **inner element** — an in-cell `<a class="clip…">` or a
`<span class="clip…">` — **never the `<td>`**, so a trailing `rdc-copy-button` / sparkline / `rdc-heatmap-cell`
/ `.lbl` label rides OUTSIDE the clip and stays visible + clickable (the reason c16l opted the td out). The
td-level 380px clip is removed from the global `table.data tbody td` rule (the `white-space:nowrap` stays);
truncation is `display:inline-block; overflow:hidden; text-overflow:ellipsis` on the `.clip` element. **Three
width tiers** as CSS custom props on `table.data`: `--clip-cap` 320px (`.clip`, default), `--clip-cap-narrow`
200px (`.clip-narrow` — flag/format/pass cols), `--clip-cap-wide` 560px (`.clip-wide` — src paths, hashes,
stable_keys). **The full value is always recoverable:** the real DOM text inside `.clip` is the untruncated
value (Ctrl-F / selection-copy), and a server-set (static) / JS-set (virtual) `title=` reveals it on hover —
**length-gated** (a deterministic char-threshold proxy for "will clip": narrow 24 / default 40 / wide 64),
so short cells skip `title=` (no screen-reader double-read; synthetic + real-Perf src paths are short, so the
golden carries no src `title=` — correct-for-data, NOT a gamed threshold, ADR-23). **Copy/link payloads keep
the FULL value** — `rdc-copy-button data-value=` and link `href=` are never the clipped display (c16c
contract). **Application differs by mode, mirroring `mono`/`numeric`:** static report builders emit the
`.clip…` class + `title=` on the named long cells (shader src — wide, on the `<a>` so the file icon + copy
ride outside; instancing mesh-label/areas — default, dominant-pass — narrow; overdraw RT-label — default,
format — narrow; trend area — default); the `VTable.cellNode` wraps every **non-numeric** windowed cell in a
`.clip` element (wide for `_path`/`_hash`/`_hex`/`stable_key`, else default) and re-applies it on every
recycled render — numeric cells are never clipped (keep right-aligned tabular-nums). **Global expand/wrap
toggle:** the engine builds a real `<button class="rdc-expand-toggle" aria-pressed>Expand cells</button>`
(JS, both modes, only when the table has a `.clip` cell — no dead button) into a JS `.rdc-controls` bar
before the host; click flips `data-expand` on the host. Default = **truncated**. Release is mode-aware: full
width **single line** in both modes (`data-expand="true"` → `.clip{max-width:none}` — single line keeps the
VTable's fixed `ROW_H` valid so windowing never desyncs), and static **additionally wraps** to multi-line
(`white-space:normal; overflow-wrap:anywhere`) since static rows auto-size. **Print (static only):** the
table is constrained to the page (`width:100%`, overriding `width:max-content` which would overflow + clip
the paper edge) and every `.clip…` flows `display:inline; white-space:normal; overflow-wrap:anywhere` so long
unbroken paths **wrap within the page — nothing hidden on paper** (no `title=` tooltips in print); virtual
pages are windowed and never print-complete (ADR-37), so the print rule stays static-scoped. ASCII (ellipsis
via the CSS keyword, no literal U+2026); offline + byte-deterministic. `test_report_structure` gains the c16m
guards (long report cells carry the inner `.clip…` element; the src clip span's text == the copy `data-value`
== the full path; the toggle is a real `<button aria-pressed>` flipping `data-expand`; the helper's `title=`
is length-gated) + `test_design_tokens` asserts the clip contract lives in `_RDC_TABLE_CSS` and the c16l
stopgap is gone. **Output-changing → refreshed** every HTML golden (the engine CSS/JS is inline on every page,
the c16l scope) + the static reports' new `.clip…`/`title=` markup; `_pagedata/*.js`, `digests.json`, and
`golden_parquet` are **byte-unchanged** (virtual clip is JS-applied at render; presentation-only),
`test_parquet_parity` green with NO digests refresh (§21.9). 181 -> 188 green. `bobframes smoke` render-only
15 pages lint clean exit 0. Browser-verified offline (headless Chrome, `file://`): a crafted long src path
clips with ellipsis (copy button visible outside the clip), the **Expand cells** toggle reveals the full
value, print full-wraps within the page; the real heaviest drill (Commercial district 2026-06-01_r110788,
123,052 rows / 28 tables) recycles windowed rows with `marker_path`/`marker_path_norm` clipped + `.lbl`
labels preserved + the toggle injected, no JS errors, `ROW_H` intact. **Truncation model:** the 380px
td-clip is the DEFAULT (kept for the un-enhanced bare dashboard/preview minis, which have no rdc-table host
+ no inner `.clip`); `rdc-table` cells opt OUT (`rdc-table table.data tbody td { max-width:none }`) and clip
via the inner `.clip`. The **dashboard mini tables** additionally pin `table-layout:fixed; width:100%`
(numeric columns compact, text columns flex) so a long label can't push the mini past its card and cut the
rightmost column at the narrow 3-up grid width — a **pre-existing** overflow (the minis' `width:max-content`
overran the card regardless of c16m), fixed here + guarded by `test_design_tokens`. The minis are bare
(not engine-hosted - a sortable/interactive header inside the card-link `<a>` would fight navigation, c16l),
so they carry no inner `.clip`/JS `title`; the **builder sets a server-side `title=` on the minis' text
cells + headers** so a clipped value still reveals in full on hover (cell text stays inline → the td ellipsis renders +
Ctrl-F matches). The `pass_gpu` mini's `marker` column was builder-truncated (`trunc_left`, which DISCARDED
the value so hover could never reveal it) - now it emits the FULL marker (CSS clips the display, `title=`
reveals), consistent with every other mini text column. Guarded by `test_report_structure`. 186 -> 188 green.
**Completes the c16k–c16m table-unification epic (ADR-38).**

**c16n — truncation-coverage tail + dashboard print (ADR-38 tail) — see [c16n](../commits/v02/c16n_clip_coverage_print.md).**
c16n closes the last two consistency gaps so EVERY tabled surface behaves identically. (1) **`draws_by_class`**
was the only tabled report c16m's scope skipped: its raw per-(area,drop) table's `area` + `drop` text cells now
wrap in the default-tier `base.clip_span` (`draws_by_class.py` `_build_table`), so all **5 tabled reports** +
the catalog/drill virtual tables clip + hover-reveal consistently - no tabled surface left un-clipped. (2) **The
bare dashboard/preview minis printed CLIPPED on paper:** they have NO `rdc-table` host (so the c16m static
print full-wrap, which is `rdc-table[data-mode="static"]`-scoped, never reached them) and rely on the global
380px td-clip + (dashboard) `table-layout:fixed; overflow:hidden`, with no `title=` hover in print. A new
`@media print` rule in `_RDC_TABLE_CSS` (co-located with the 380px clip it releases) releases both bare-mini
contexts to `max-width:none; overflow:visible; white-space:normal; overflow-wrap:anywhere` over cells AND
headers: `a.dash-card table.data` (the dashboard minis) + `.table-wrap > table.data` (the preview-gallery mini -
a DIRECT child of `.table-wrap`; report tables interpose `<rdc-table>`, so the child combinator excludes them
and matches the preview mini only). `table-layout:fixed` is deliberately KEPT (the 2-up print `.dash-grid`
bounds each card; `table-layout:auto` could overflow it) - the wrap rules alone leave nothing hidden. (3) **Mini
`title=` kept UNCONDITIONAL (ADR-23 documented scoping):** `_card_table` sets `title=` on every mini text cell +
header; mini column widths are responsive (`table-layout:fixed` + the 3-up `auto-fit/minmax` grid), so the
server has **no deterministic pixel clip point** - a char-length gate would drop `title=` on a genuinely-clipped
short cell in a narrow card. Per ADR-23 the unconditional `title=` is kept and the rationale recorded here rather
than shipping a fragile heuristic; no new ADR (rides ADR-38 + ADR-23). `test_report_structure` gains
`test_c16n_draws_by_class_area_drop_clip` (a clean False->True flip - the page carried no server-baked
`class="clip"` before c16n; the engine JS applies clip via `.className`, never the literal); `test_design_tokens`
gains `test_c16n_dashboard_mini_print_fullwrap` (both bare-mini print selectors present in `_RDC_TABLE_CSS`,
ASCII). **Output-changing -> refreshed** every HTML golden (the new print bytes ride the always-on engine CSS
inline on every page; `draws_by_class` additionally gains the `<span class="clip">` markup); `_pagedata/*.js`,
`digests.json`, `golden_parquet` **byte-unchanged**, `test_parquet_parity` green with NO digests refresh (§21.9).
188 -> 190 green. `bobframes smoke` render-only lint clean exit 0. Browser-verified offline (headless Chrome,
`file://`): `draws_by_class` area/drop clip with ellipsis + reveal full value on hover (and the Expand-cells
toggle now appears, since a `.clip` cell exists); the dashboard print-preview shows full mini cell + header
values - nothing clipped.

## 21.1p Table a11y parity: both `rdc-table` modes at sort/filter a11y parity (c16o, ADR-38 a11y tail) — see [c16o](../commits/v02/c16o_table_a11y_parity.md)
c16o closes the **G-23 a11y tail**: a feature added once to the ONE engine now behaves the same in BOTH modes.
c16l restored `aria-sort` on the `StaticTable` engine (parity with the deleted `rdc-sortable-table`), but the
`VTable` (catalog/drill, virtual) never got it, and **neither** mode's sort header was keyboard-operable (a bare
`<th>` + click listener). c16o fixes both at the root. **(1) VTable `aria-sort` (virtual parity):**
`VTable.buildHead` seeds `aria-sort` from the current `sortCol`/`sortDir` (so a group-toggle rebuild keeps it
correct) and `VTable.sort` flips it none→ascending/descending per header, mirroring `StaticTable._paintSort` —
screen readers now announce sort state on catalog/drill too. **(2) Keyboard-operable sort headers (BOTH modes):**
a single shared free function `wireSortHeader(th, ci, onSort)` (authored once in the engine IIFE, alongside
`cmpVals`/`tintImage`) sets `tabindex="0"` + a click + an Enter/Space `keydown` handler (`e.preventDefault()`,
matching the `RdcCopyButton` pattern) that calls the mode's own `sort(ci)`; both `VTable.buildHead` and
`StaticTable._wireHeaders` call it, so sort is reachable by keyboard everywhere. `<th>` keeps its implicit
`role="columnheader"` (where `aria-sort` belongs — `role="button"` would WRONGLY strip it), and `cursor:pointer`
already comes from the `table.data thead th` CSS (not re-set in JS). The **sort RESULT and row content are
unchanged** — only how sort is reached + announced. **(3) Search-input `aria-label`:** the virtual filter
`<input type="search">` gains an `aria-label` (`filter <table>` per drill table; `filter catalog` on the catalog)
in `html/template.py` — a placeholder is not a label substitute. `test_c16l_engine_in_shared_report_bundle` is
extended (slices `_compose_js()` at the two class boundaries and asserts `aria-sort` + `wireSortHeader(` appear in
BOTH `VTable` and `StaticTable`, plus `function wireSortHeader` / `tabindex` / `Enter` are present — `_minify_js`
is comment/whitespace-only so the substrings survive); `test_c16o_search_input_labelled` asserts every catalog +
drill search input carries an `aria-label`. **Output-changing → refreshed** all 15 HTML goldens + the preview
(the engine JS is inline on every page — the c16l scope; catalog/drill additionally gain the search `aria-label`
markup); `_pagedata/*.js`, `digests.json`, `golden_parquet` **byte-unchanged** (behavior/markup only; the VTable
DOM is JS-built at runtime, not in the golden), `test_parquet_parity` green with NO digests refresh (§21.9).
190 → 191 green. `bobframes smoke` render-only 15 pages lint clean exit 0. **Browser-verified offline (headless
Chrome over CDP, `file://`, real Perf):** static report — 19 headers all `tabindex=0`, exactly 1 default-sort
column announces `aria-sort`, header focusable via `el.focus()`, a real **Enter** key flips `aria-sort=ascending`
+ reorders rows, the Expand-cells toggle flips `data-expand=true`; virtual catalog — 25 client-built headers all
`tabindex=0` + **all carry `aria-sort`** (the gap closed in the live DOM), search input `aria-label="filter
catalog"`, header focusable, Enter sorts + arrow shows; dark-mode body background differs light↔dark. No new ADR
(rides ADR-38 a11y tail). **Closes the G-23 a11y tail — both modes of the one engine at sort/filter a11y parity.**

## 21.2 Schema regression
Every parquet column list equals `schemas.expected_columns(stem)` (catches alphabetization drift,
dropped column, dtype slip). Skip `_`-prefixed (`_catalog`, `_global_entities`). Runs on synthetic +
any drop touched in CI.

## 21.3 Replay-side schema drift detector — see [c13](../commits/v01/c13_replay_drift_ci.md)
Guards H-6. **Corrected** test (the original was a no-op — [ADR-5](../DECISIONS.md)):

```python
_REPLAY_STEM = {   # var (sans _COLS) -> schemas stem; identity unless listed
    "RT": "render_targets", "RT_TIMELINE": "rt_event_timeline",
    "STATE_CHANGE": "state_change_events", "COUNTERS": "counters_per_event",
}
_EXPECTED_REPLAY_TABLES = 21

def test_replay_main_schema_in_sync():
    tree = ast.parse((PKG / "replay" / "replay_main.py").read_text())
    replay_tables = _extract_col_tuples(tree, suffix="_COLS", skip={"ID_COLS"})
    assert len(replay_tables) >= _EXPECTED_REPLAY_TABLES, "guard must not match zero"
    for var, cols in replay_tables.items():
        base = var[:-len("_COLS")]
        stem = _REPLAY_STEM.get(base, base.lower())
        assert cols == schemas.expected_columns(stem), f"{var} drifted"
```

## 21.4 Determinism + lint + performance
- **Determinism:** render synthetic twice; outputs byte-identical (catches dict ordering, timestamps).
- **Lint:** every rendered HTML passes `lint.lint_file` (zero hits).
- **Perf:** synthetic render < 2s on CI; flag regressions.

## 21.5 Quality-improving items (opt-in, off by default to preserve parity)
Misclassified UE draws → classifier TOML adds rules (c09); empty-state messages (c16); sparkline
null-gaps (already in `delta.py`, golden-verified); manifest `tool_versions`+`host_info` (c03);
cache SHA256 validation (R-13, c16).

## 21.6 CI matrix (v0.1)
```yaml
strategy:
  matrix:
    os: [windows-latest]
    python: ["3.10", "3.12", "3.13"]     # 3.14 dropped — no pyarrow 17 cp314 wheel (ADR-6)
    pyarrow: ["17", "21"]                # lower + upper of pin range
jobs:
  test:
    steps:
      - pytest tests/unit_*.py
      - pytest tests/parity.py           # golden snapshots
      - pytest tests/schemas.py          # schema regression
      - pytest tests/replay_drift.py     # H-6 drift detector (corrected)
      - pytest tests/determinism.py
      - pytest tests/perf.py
      - bobframes smoke                  # render-only against synthetic
      - bobframes lint tests/data/golden/**/*.html
```

> **Refined by [ADR-11](../DECISIONS.md):** golden byte-parity (`test_parity`) is **pinned to the
> canonical cell** (py3.12 + pyarrow 21) — the rendered HTML embeds env-variable bytes (parquet
> on-disk size by pyarrow version; a percentage's last `.2f` digit by numpy build), so it is only
> byte-identical on the env the golden was baked in. Every other gate (incl. `determinism`, which is
> within-env stable) runs on the full matrix. Real test files are `test_*.py`, not `unit_*.py`.
**Gap (ADR-6):** no GPU/RenderDoc on `windows-latest` → CI never exercises the **ingest** path. The
c03 hardening gets a **mocked-subprocess** unit test so kill/skip/atomic-rename ship tested; full
ingest smoke is self-hosted/nightly (v0.2).

## 21.7 Pre-merge checklist (per PR touching the package)
- [ ] Golden snapshots updated? (only if intentional output change)
- [ ] Schema regression green
- [ ] Replay-drift green
- [ ] Determinism green
- [ ] Lint green
- [ ] Perf within budget
- [ ] CHANGELOG entry if user-visible

## 21.9 Data-extraction guarantee
De-hardcoding does **not** change extraction (renderdoccmd export, qrenderdoc replay, parsers,
parquetize) — identical Parquet for identical `.rdc`. Improvements are in classification correctness,
report polish, operational reliability, and configurability. Parquet contents stay byte-identical
(verified by schema regression + golden tests).
