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

## 21.1q Exec one-pager + health verdict (c16q, ADR-39) -- see [c16q](../commits/v025/c16q_health_and_onepager.md)
Two test files. `tests/test_health.py`: `area_verdict` + the global rollup are deterministic and recomputable
from `get_config().report` (catches a creeping hardcoded threshold, ADR-23); `state == max(area_verdicts)`
and `worst_area` is the worst-scoring area; the `State` + `Direction` enum members are stable wire
identifiers; `trend()` is deterministic and on a single-run / missing-parquet fixture both the verdict and
the `Direction` are `UNKNOWN` (NOT a false-green `OK` / false IMPROVING) with the missing inputs marked
`present=False`; on a 2-run fixture the improvements/regressions ledger is correctly signed (lower-is-better)
and `direction` reflects the net of the headline deltas. `tests/test_summary.py`: `_reports/summary.html`
exists and carries the verdict `summary-bar` + the "N of M areas" scope line + a `Direction` tag + a
`kpi-strip` with >= 4 `kpi-chip` each bearing a vs-prior delta + a sparkline + `id="movement"` (Improvements
+ Regressions lists + a resolved/new count) + `id="by_area"` (one row per area, with per-area vs-prior deltas
+ a per-area status) + a `device-strip`; the headline KPIs are AVERAGES (`avg draws/frame`, `avg gpu/frame`)
whose values reconcile against the dashboard's current-run totals divided by the run frame count, and the
small total line matches the dashboard totals (the coupling contract that lets `aggregates.py` stay
deferred); `lint.lint_file(summary.html)` returns zero hits (the plain-language copy + the
direction/movement labels are banlist-clean). **Golden delta is exactly 5 files** {new
`_reports/summary.html`, new `_reports/run/<k>/summary.html`, intentional root `index.html` (the promoted
"build health summary" chip + summary excluded from the auto-listed grid), and the one `_NAV` "build health"
chip on BOTH dashboard instances -- top-level `_reports/index.html` AND per-run `_reports/run/<k>/index.html`
(the SAME `dashboard.build` emits both, so the chip lands on both; the as-built count is 5, not 4 - recorded
per ADR-23)}; everything else (the 6 reports + their per-run copies, drill, catalog, A/B, `_pagedata/*.js`,
preview, parquet) byte-unchanged; `test_parquet_parity` green with NO digest refresh (§21.9, presentation
only). The `dashboard._top_areas_gpu` 5th element + `_top_{shaders,meshes}_by_area` + the `_run_totals`
factor-out of `_global_kpis` are byte-neutral for `dashboard.build` (verified: the only dashboard golden
change is the chip). Refresh `python -m bobframes.tests.make_golden`; review the 5-file delta.

## 21.1r The `head_assets(sink)` seam parity (c16r) -- see [c16r](../commits/v025/c16r_head_assets_seam.md)
A pure zero-output refactor: the head asset emission is routed through one `head_assets(sink, depth)` helper
(`INLINE` default = today's exact bytes; `REF` = `_assets/` depth-relative links). **No golden refresh** -
all 15 HTML goldens + `_pagedata/*.js` + the preview stay BYTE-UNCHANGED (`pytest tests/test_parity.py` green
by construction), `test_parquet_parity` untouched. `tests/test_head_assets.py` asserts `head_assets(INLINE)`
equals the prior inlined composed string (a snapshot) and `head_assets(REF, d)` emits depth-correct
`_assets/report.{css,js}` (and the template family's `catalog.{css,js}`) links for `d in {0,1,2,4}`. This gate
exists to PROVE the seam introduced no output change before c16t builds on it.

## 21.1s Packaging parity: the `package` verb, shared assets, redaction (c16s-c16u, ADR-40/41) -- see [c16s](../commits/v025/c16s_package_verb.md), [c16t](../commits/v025/c16t_shared_assets.md), [c16u](../commits/v025/c16u_redact.md)
`tests/test_package.py` over the variant golden trees under `tests/data/golden_package/` - `shared/` (the
DEFAULT, c16t), `inline/` (`--inline`, c16s), `light/` (`--light`, c16s), `redacted/` + `shared_redacted/`
(c16u) - where each golden is the tree **extracted from the produced `.zip`** (HTML via `normalize`, parquet
via the logical `parquet_digest`, raw bytes elsewhere - so zlib/parquet-writer drift is not gated). Asserts:
(a) **non-mutation** - the source `<root>` digest is unchanged before/after `build`; (b) **determinism** -
build twice equals itself, and each variant tree equals its golden; (c) **stream + round-trip** - the zip
extracts byte-equal to the gated tree, `ZipInfo.date_time==(1980,1,1,0,0,0)` and the compress type/level are
fixed (the zip bytes themselves are NOT byte-compared); (d) **taxonomy** - `package` argparse rejects a
`--format` flag; (e) **shared-assets (default)** - `_assets/report.css`==`_compose_css()`,
`report.js`==`_compose_js()`, `catalog.css`==`template._CSS`, `catalog.js`==`rdc_table_js()`; the base64 font
head is ABSENT from every page; each page links the depth-correct `_assets/*` for its family; no `fetch(` /
`type="module"` in any HTML or asset; the shared tree is >= `(report_pages-1) * ~95 KB` smaller than
`--inline`, and `--inline` reproduces the `inline/` golden byte-for-byte; (f) **friendly artifacts** - the
standalone `<project>-<rundate>-summary.html` emitted beside the zip is SELF-CONTAINED (no `_assets/` link,
no external ref, no `fetch`/module); a root `README.txt` is present + ASCII; both artifact names match
`<project>-<rundate>-...`; the `light/` tree has no `drill/`/`_pagedata/`/`_data/`; (g) **redaction** - no
page carries a device field value, the abs-path completeness scan is clean by default (strip mode), and
`--redact-paths=fail` exits nonzero on a planted leak (a crafted-input unit test covers the device-strip
scrub if the synthetic provenance is empty). The HTML/asset BYTE gate is pinned to the canonical cell
(py3.12+pa21, ADR-11); structure / round-trip / redaction-marker / self-determinism / `--format`-rejected /
standalone-summary-self-contained run on the full matrix. Refresh `python -m bobframes.tests.make_package_golden`
(c16t onward).

**c16s as-built (rides ADR-40/41; recorded in the c16s doc, ADR-23).** The inline bundle's HTML is a
byte-identical copy of the render output, so `test_package.py` REUSES the render golden (`golden/`) for the
`inline/` + `light/` slices rather than storing duplicate trees (which would force a permanent double-refresh);
parquet is checked by the logical `parquet_digest` against the unchanged source. `--shared-assets` (the
`shared/` golden + asset-byte / font-absent / depth-link / size-win asserts) is c16t and `--redact`
(`redacted/`) is c16u: the flags arrive WITH their features, so c16s neither ships nor tests them, and the
`golden_package/` trees + `make_package_golden.py` are BORN at c16t. The zip nests under one
`<project>-<rundate>/` top folder; default out is the PARENT of `<root>` (guarded outside the read tree).
Render is untouched -> `test_parity` + `test_parquet_parity` stay green with NO refresh; the c16s slice is
non-mutation / determinism / round-trip / inline+light-vs-render-golden / standalone-self-contained / README /
naming / `--format`-rejected (252 green, +15 `tests/test_package.py`).

**c16t as-built (rides ADR-41; recorded in the c16t doc, ADR-23).** Shared-assets is the DEFAULT bundle;
`--inline` is the opt-out (a flag, not `--shared-assets`). The REF form is produced by the render seam, NOT
a scrape: the render layer threads `sink: AssetSink = INLINE` (page_open -> report_page -> the 8 report
`build()` -> render_root -> render_drop -> orchestrator/`ab.render_pair`) + `build_ts` (the 8 `build()` +
orchestrator). **Mechanism pivot (recorded):** the doc's "decoupled read-root/write-root, no `_data` copy"
was abandoned mid-build — a decoupled out-dir makes each report's relative drill/CSV links (computed as
`relpath(target_under_<root>, out_dir_under_staging)`) ESCAPE the bundle into the source tree. The shipped
mechanism COPIES `_data` raw into a temp staging dir and re-renders the whole tree with one `root=staging`
(`sink=REF`), so every relative link resolves IN the bundle; `<root>` is only read (non-mutation holds);
parquet is a raw copy -> digests match source. So `out_root`/`rebuild_cache` were NOT added (dead with the
copy mechanism). **Determinism:** the report family stamps `now_iso()`, so the re-render is given a pinned
`build_ts` (the target run's `drop_date`) -> two packages are byte-identical (the raw-byte determinism gate
holds). Recorded consequence: a shared page's "built" line shows the run date, differing from the `--inline`
copy + the standalone summary (verbatim source copies showing the original wall-clock); `render_root`/drill
keep their catalog/manifest timestamps (already deterministic). The `shared/` golden (born here via
`make_package_golden.py`) stores HTML (normalized) + `_pagedata`/`_assets`/README (raw), minus `_data`
(digest-gated); `inline/`+`light/` still reuse `golden/`. Asserts added: `_assets/{report,catalog}.{css,js}`
== composer output; the base64 font ABSENT from every page; every page carries `head_assets(REF, depth)` for
its family (a generic `all_reports()` footgun guard); no `fetch(`/modules; the shared HTML is `>=
(report_pages-1)*inline_head_bytes` smaller than `--inline`; `--inline` byte-reproduces the render golden;
preview gallery (`_chrome_preview.html`) copied raw so the file-set matches `--inline`. Render UNTOUCHED ->
`test_parity` + `test_parquet_parity` green with NO refresh; browser-verified offline from `file://` on the
real Perf bundle (catalog VTable + a report + a drill all enhance from the shared `_assets/`; 0 unresolved
`_assets` links across 30 pages). 253 -> 262 green (+9 shared asserts). Real Perf: 2.86 MB duplicated chrome
reclaimed (4 shared assets ~206 KB vs ~30 inlined copies).

**c16u as-built (`--redact`; rides ADR-40; recorded in the c16u doc, ADR-23).** `package --redact` produces a
bundle safe to share externally; `--redact-paths={strip,fail}` (default `strip`) controls absolute-path
handling. **Device/host provenance is scrubbed at the structured DATA seam, never an HTML regex:**
`chrome.provenance_strip(host_info, tool_versions, *, redact=False)` gains a redact mode (emits `<div
class="device-strip">redacted</div>`), threaded `redact: bool = False` through the SAME render seam as c16t's
sink/build_ts (orchestrator -> the 8 `build()` + dashboard + per-run, `ab.render_pair`, `render_drop`'s
`gl_renderer` strip, and `trend_table`'s in-body per-drop device chips), so the package re-render emits
redacted provenance BY CONSTRUCTION. **Whole-tree, drop-sidecars (resolved design fork, recorded):** the
bundled raw `_data` also leaks device values — `_manifest.json` (host_info + tool versions) and
`frame_metadata.jsonl` (gl_renderer/driver/vendor) — so a redacted bundle EXCLUDES those two sidecars wholesale
(linked by no viewable page; robust to manifest schema growth, unlike enumerated field-scrub). **Absolute
paths:** a fixed drive-letter `[A-Za-z]:\\…` token pattern — UNAMBIGUOUSLY absolute, so the base64 font /
`data:` URIs / `http:` URLs (no `:\`) and RELATIVE backslash paths (e.g. a `shader_src\2192.glsl` resource ref,
the real-Perf false positive a blanket UNC match caused) are NOT touched (`_assets/*` skipped). `strip`
(default) replaces each token with `<path redacted>` across ALL bundled text (HTML, `_pagedata`, CSV, JSON
sidecars) — share-safe; `fail` (CI) modifies nothing and asserts the RENDERED surface (HTML + `_pagedata`)
carries no residual path, exiting nonzero BEFORE the zip is written. **`--redact` FORCES a re-render** (redaction is a structural transform): `--inline
--redact` re-renders at the INLINE sink + pinned `build_ts` (so its "built" line shows the run date, like
shared — new divergence vs the non-redact `--inline` copy) rather than the fast identity copy; `--inline` alone
stays a copy. The standalone summary stays self-contained + redacted (the INLINE staging copy, or a dedicated
INLINE render for the shared bundle). **Recorded limitations (ADR-23, FINDINGS):** abs-paths inside BINARY
parquet are NOT stripped (the CSV twins + rendered `_pagedata` are; the viewer renders from those, not
parquet); UNC `\\host\share` paths and forward-slash drive paths `C:/…` are out of the token-strip scope (a
JSON-escaped single separator is indistinguishable from a literal UNC in assembled text, and `C:/` would
false-match `http://`). New golden trees `redacted/` (inline+redact) +
`shared_redacted/` (shared+redact) via `make_package_golden.py` (HTML normalized, `_pagedata`/`_assets`/README
raw, `_data` digest-gated). Asserts (g): no device value on any page/`_pagedata` of either tree (generic
footgun net for a future report forgetting `redact=`); the two provenance sidecars excluded + not dangling-
linked; a denylist→tripwire over `_data` text files (CSV twins + `_resource_labels.json` + `_catalog.json`
only); strip-mode abs-path scan clean; `fail` raises on a planted leak; `--redact-paths=fail` requires
`--redact`; redacted determinism + non-mutation; crafted-input units for the strip (drive+UNC replaced, font
untouched) + `provenance_strip(redact=True)`. Render UNTOUCHED (redact defaults `False` everywhere) ->
`test_parity` + `test_parquet_parity` green with NO refresh; the `shared/` golden is byte-unchanged. 262 -> 277
green (+15). Real Perf `--redact`: 1306 abs-path tokens stripped, sidecars excluded, `grep` of the extracted
tree for device values + drive-letter paths is clean.

## 21.1t Single-source aggregation + multi-capture per-frame normalization (c16y + c16v, G-26 + G-29) -- see [c16v](../commits/v025/c16v_multicapture_normalize.md)
Two sequenced commits (G-26 first so normalization lands in ONE place):

**c16y (G-26, ZERO-OUTPUT):** the mesh repeat-count + shader uses/cost atoms (formerly triplicated
across `dashboard._top_meshes`/`_top_meshes_by_area` + `instancing_opportunities` + `shader_hotlist` +
`_top_shaders`/`_top_shaders_by_area`, kept in sync by convention) are extracted to a single
presentation-independent `bobframes/aggregates.py` (peer of `health.py`), keyed per `(drop_key, area,
entity)`, plus the per-`(drop_key, area)` frame count. Both shader cost formulas are exposed as atoms
(`cost_sum` = sum-over-rows(cplx*uses) for the dashboard; `uses`+`cplx` for shader_hotlist's
cplx*sum-uses) so each consumer stays byte-identical. ALL goldens BYTE-UNCHANGED, NO refresh.

**c16v (G-29):** instancing repeat-count + shader cost/uses read PER FRAME via the single helper
`base.per_frame(total, frames)` (returns `total` unchanged when `frames<=1`, so 1-capture data is a
no-op; never float-accumulate — `heatmap_cell` emits the raw value, where a float `6.0` would serialize
`"6.0"`). Normalization is PER AREA (divide each area's count by that area's frame count) then summed
across areas, so cross-area displays stay correct and the verdict (which reads `_top_meshes_by_area`)
can never disagree with the instancing report.

**Frame-count source = the DATA, not `ok_captures` (as-built correction, ADR-23).** The denominator is
the count of distinct `capture` values actually PRESENT in that drop+area's entity data (draws for
meshes, shaders for shaders), guarded `>=1`. On consistent data this equals `ok_captures` =
`frame_totals` rows; but the committed synthetic fixture declares `ok_captures=5` (manifest
`capture_status`) while its draws/shaders populate only `capture='1'` — so `/ok_captures` would (a)
divide every golden value by 5 (breaking parity) and (b) be semantically wrong (1 real frame of draws).
The data-derived count is both golden-neutral (`/1` on the synthetic) and the correct denominator (it
can't average over frames that exported no entity rows). The plan-doc's `/ ok_captures` was the wrong
source; this gate records the data-derived choice.

**Golden-neutral on current data:** the synthetic draws/shaders are single-capture, so `per_frame` is a
no-op -> ALL HTML + parquet goldens BYTE-UNCHANGED (`pytest tests/test_parity.py` + `test_parquet_parity`
green, NO refresh; if a golden moves it's a normalization bug, not a refresh trigger). Proven by
CONSTRUCTED multi-capture tests (`tests/test_aggregates.py` + `tests/test_multicapture_normalize.py`): a
mesh drawn once/frame across 3 captures -> `repeat-per-frame == 1` (not 3); a shader used twice/frame ->
cost normalized (60 not 180), complexity unchanged; a 1-capture mesh drawn 3x -> repeat `== 3` (divisor
is the FRAME count, not the draw count); and the synthetic-skew case (manifest 5 ok, data 1 capture) ->
repeat `== 3` (divided by the 1 data-frame, NOT `ok_captures=5`). `instancing_repeat_min` + shader cost
now carry PER-FRAME semantics (config comment + module docstrings; rendered tooltips unchanged to keep
the golden, accurate for 1-capture display). Runs on the full matrix (no golden dependency).

## 21.1u Component system: CSS/JS extraction + element builder + token guard + table component + summary migration (c16x, ADR-42, G-30) -- see [c16x](../commits/v025/c16x_component_system.md)
c16x is a 5-step sub-sequence; x1-x4 are **zero-output** (`test_parity` + `test_design_tokens` +
`test_parquet_parity` green, NO golden refresh) and x5 is a **bounded reviewed refresh** at visual parity.
- **x1 CSS/JS extraction.** The chrome/template CSS+JS string literals live as real files under
  `reports/assets/*.{css,js,html}`, loaded via `importlib.resources` (`_read_asset`), `${token}`/`__ROW_H__`
  substitution preserved -> byte-identical composed output. `tests/test_assets.py` pins: each asset exists +
  loads, every `.css` is ASCII (`rdc_table.js` exempt: a sort-arrow glyph in a `<script>` body, which the
  whole-page lint banlist already exempts), the module constants == the file contents verbatim, and the composed
  bundles carry no leftover `$` / `__ROW_H__`. Packaging: the assets are not gitignored and ship via the
  `inter-subset.woff2` precedent (`packages=["bobframes"]`); the clean-install wheel smoke runs in CI at c16w.
- **x2 element builder.** `chrome.el`/`el_void`/`raw`/`classes` escape attribute values + text children BY
  CONSTRUCTION (subsumes roadmap C6); `_Raw` children splice verbatim, `None`/`False` skip, unsafe attr names
  raise. `tests/test_element_builder.py` (13 cases) + the byte-identical `icon`/`kpi_chip` migrations gated
  end-to-end by `test_parity`.
- **x3 token guard.** `chrome._undefined_token_refs`/`undefined_tokens`: declared = (TOML `:root` scale) UNION
  (every `--x:` definition scanned from the COMPOSED CSS, so in-body props `--crumb-h`/`--hdr-offset`/`--clip-cap*`
  are NOT false-flagged); referenced = `var(--NAME)` across the composed CSS + the bundle JS + emitted `style=`
  fragments. `tests/test_token_guard.py`: both live bundles clean; a planted `var(--sp-5)` (CSS) / `var(--nope)`
  (style=) / `var(--ghost)` (JS) is caught. A CI test (NOT an import-time raise, which would crash `version` on a
  styling typo); `bobframes preview` warns non-fatally (the designer loop). This is the structural fix for the G-30
  failure class.
- **x4 table component family.** `chrome.Column`/`data_table`/`static_table`, NORMALIZED + built through `el`,
  gated by `tests/test_table_component.py`. **BUILT-NOT-ADOPTED:** a byte-identical migration of the ~117
  hand-written table sites is infeasible (attribute-order / per-report-cell / inline-col-group inconsistency), so
  the reports adopt the component in v0.2.6 where the golden refresh absorbs the normalization (recorded, ADR-23).
  Zero production migration here -> parity green.
- **x5 summary migration + gallery.** `summary._kpi`→`chrome.kpi_card`, `_trendline`→`delta.trendline`, the verdict
  span→`chrome.status_badge`, the Movement layout→`chrome.movement`; `summary._SUMMARY_CSS` (a mid-body `<style>`)
  relocated into `reports/assets/components.css`, renamed `.bh-trend*`→`.trendline*`, kept
  `[data-page-kind="summary"]`-scoped (inert elsewhere). The golden delta is summary.html (the trend SVG class
  rename + the removed mid-body `<style>`) + every page's inlined bundle growing by the inert scoped rules
  (minified on report pages, verbatim on catalog/drill) + the preview gallery + `golden_package`
  `report.css`/`catalog.css`. `_pagedata/*.js` + `golden_parquet/digests.json` **byte-unchanged** (presentation
  only, §21.9). The `.trendline` CSS == the old `.bh-trend` CSS -> pixel-identical (visual parity).
  `tests/test_components.py` + the renamed-class asserts in `test_summary` (updated in-commit). Closes G-30.
The v0.2.6 bold-visual epic (ADR-43) is where the byte-parity gate is intentionally broken and the replacement
gates (structural component tests + token guard + browser matrix on synthetic + real Perf) become the contract.

## 21.1v v0.2.6 visual redesign: the replacement-gate contract (ADR-43/44/45) -- see [v026 commits](../commits/v026/)
Byte-parity is **intentionally broken** for the redesign; these gates are the contract (a documented
replacement, never a silent narrowing -- ADR-23). Every v0.2.6 surface commit holds ALL of:
- **(a) Data path FROZEN (unconditional).** `test_parquet_parity` GREEN; `golden_parquet/digests.json`
  + the 27 `_pagedata/*.js` **byte-unchanged** (confirm via `git status` scope); `health.py`/`aggregates.py`
  import no chrome/base. **Never** `make_parquet_golden`.
- **(b) Structural + ARIA tests** (golden-independent; mirror `test_report_structure`/`test_components`).
  Redesign-invariant a11y holds every commit: `<th>` count == `scope="col"`; `aria-sort` + `wireSortHeader(`
  stay in `_compose_js()`; search inputs keep `aria-label`; delta sign explicit; no DOM reorder. The
  do-not-rename guard (`test_js_coupled_classes.py`) keeps the rdc-table engine classes co-present in
  CSS + JS.
- **(c) Token guard** `chrome.undefined_tokens() == set()` on both bundles; auto-covers new `var(--...)`.
- **(d) Contrast** (`test_contrast.py`, dependency-free oklch->WCAG): fg AAA, text-2/text-3 AA both themes.
- **(e) Browser matrix (MANDATORY per changed surface).** `tools/shoot.py` over headless Chrome `file://`,
  **light/dark/print**, synthetic + real Perf `c:/tmp/perf`; dark/print are invisible to the theme-agnostic
  golden so they are never skipped. Reviewed + **signed off BEFORE goldens bake**.
- **(f) Lint/ASCII/determinism** + no new dep/build step (ADR-37 holds).
**Golden discipline:** order `make_golden` -> `make_preview_golden` -> `make_package_golden` on the
canonical env (py3.12/pyarrow21; the repo `.venv`), then `git status`/`diff --stat` must match the commit's
declared surface scope. **v0.2.6-0** (dev-only): built (e)'s harness + (b)'s rename guard + (d)'s converter;
zero production change, NO refresh. **v0.2.6-1a** (token lift): neutral shadcn palette + WCAG-AA `--text-3`
+ `--radius`/`--sp-5`/`--sp-10`/`--fs-micro` tokens + type tune; pinned-byte tests (`test_exact_color_lines`,
`test_layout_literals`) updated in-commit; the `--text-3` strict-xfail flipped to a pass; goldens refreshed
(palette only; `_pagedata`/`digests.json` byte-unchanged); 327 green.
**v0.2.6-1b** (flat surfaces + radius + states + print): elevation tokens RE-TUNED flat (reverses
ADR-34/c16d -- elev-1 = hairline ring alone, elev-2/3 keep only a whisper of drop for the dash-card
hover); `section.card`/`kpi-chip`/`details`/`callout`/`pair-group`/`summary-bar`/per-drop `table-section`
switched `box-shadow: var(--elev-*)` -> `1px var(--border)` + the `--radius` scale; the ~21 hardcoded
`2/3/4px` `border-radius` literals replaced with `var(--radius-sm)` (pills/inputs/toggles/swatches),
`var(--radius)` (cards/sections), `var(--radius-lg)` (dashboard cards); uppercase `--fs-micro` eyebrows
(kpi-label/sb-label); a shared `:focus-visible` ring (off `--accent-primary`) + a reduced-motion-SAFE
`:active` micro-scale (lives only in `prefers-reduced-motion: no-preference`); `@container page
(max-width:600px)` -> `.kpi-strip` 2x2 + sidecar 2-col; **print FIX** -- `body { padding: var(--sp-6)
var(--sp-8) }` restored so the screenshot harness (print MEDIA emulation, which ignores `@page`) no longer
hugs the paper edge (the 1a regression). Pinned `test_c16d_shadow_and_motion_tokens_emitted` +
`test_c16d_depth_over_borders_css` updated in-commit. Scope = 8 asset CSS + `design_tokens.toml` +
`test_design_tokens.py`; goldens refreshed (HTML/preview/package); `_pagedata`/`digests.json`/`golden_parquet`
byte-unchanged (0 drift); browser matrix light/dark/print synthetic + real Perf signed off BEFORE bake;
327 green; smoke lint-clean. No new ADR (rides ADR-44, which already declared the ADR-34 reversal).
**v0.2.6-1c** (user theme override; ADR-45): byte-neutral -- the `theme=None` path is byte-identical, so
`test_parity`/`test_preview`/package goldens stayed GREEN with NO refresh (0 drift). NEW `config.ThemeCfg` +
the 15-key color allowlist + `chrome.compose_css(theme=None)` (re-substitutes ONLY the `:root` block) threaded
as a 4th optional param on the sink/build_ts/redact seam; `--accent`/`--accent-data`; `export-tokens
--theme-template`; render-time guard; `package` rejects the flags. `test_theme.py` (8) + `test_config` (5);
327 -> 340 green.
**v0.2.6-2** (summary one-pager: hero numerals + componentization): the FIRST surface commit. The 4 summary
KPI values render at a NEW `[type]` `fs_hero = '2.75rem'` token, scoped `[data-page-kind="summary"] .kpi-chip
.kpi-value { font-size: var(--fs-hero); }` (dashboard/reports carry no `.kpi-chip` -> unaffected; weight stays
<=600, `test_fonts` + its pinned `font:` shorthand untouched). The by-area table adopted `chrome.static_table`
and the summary-local leaves (`_change_list`/`_change_line`/`_pct_pill`/the kpi-strip wrapper) rolled onto `el`
-- **byte-NEUTRAL** (the c16x parity contract: `static_table`'s `<th class="num" scope="col">` order + the
`<caption>` position match the hand-built table). PROVEN: a fresh render was byte-identical to the pre-bake
golden on all 17 pages OUTSIDE `<style>`; the ONLY style delta is `--fs-hero:2.75rem;` (:root) + the one scoped
rule. Package shape corroborates -- `redacted` (inline) HTML refreshed, but `shared`/`shared_redacted` changed
only in `_assets/{report,catalog}.css` (HTML links external CSS -> bodies byte-unchanged). `_pagedata`/
`digests.json`/`golden_parquet` BYTE-UNCHANGED (NO `make_parquet_golden`). NEW
`test_design_tokens.test_v026_2_summary_hero_numeral`; `test_summary` structural asserts pass unchanged;
`preview._TYPE_STEPS` gains `fs-hero` (gallery documents it). Goldens refreshed on the `.venv` (17 HTML +
preview + package); 340 green (`-m "not browser"`); browser matrix light/dark/print synthetic + real Perf
SIGNED OFF before bake. No new ADR (rides ADR-44 + ADR-42); FINDINGS G-32 (el long-tail) opened.

**v0.2.6-3** (dashboard grid: shadcn-flat Grafana-dense cards + static_table minis): the SECOND surface
commit, the first DENSE one. CSS density block (the SOLE output change): `[layout] dash_grid_min 360->300px`
(more cards/row -- real Perf 4-up at 1600 vs 3-up), `.dash-grid` gap `sp-6->sp-4`, `a.dash-card` padding
`sp-4->sp-3` + inner gap `sp-3->sp-2`. The 2px left ACCENT RAIL is a SUBTLE always-on
`box-shadow: inset 2px 0 0 color-mix(in oklch, var(--accent-primary) 30%, transparent)` (a 30% tint --
full-strength near-black/near-white read too high-contrast in review; the tint is a soft edge in both
themes + still re-hues under `[theme]`/`--accent`; a hover-only variant was tried but the user preferred
the always-on rail; user-confirmed); hover keeps the rail + adds `--elev-2`; print drops it (cards keep
the #888 frame). Radius-lg + the 1px hairline kept. **Componentization byte-NEUTRAL on the
golden:** `_card_table` -> `chrome.static_table` (via a NEW `Column.cell_title` -- the dashboard mini's
always-on hover-reveal `<td title>`, sourced from the PLAIN value so `el` escapes once: the would-be
double-escape was a review finding [R1], fixed by a NEW `formatters.scrub_chrome_text` feeding the marker
plain); `_card` + both `chip_cluster` strips (cross-report `<nav>` + A/B `<div>`) -> `el`. PROVEN: a fresh
render was byte-identical to the pre-bake golden on all 17 pages OUTSIDE `<style>`; the only delta is the
CSS. Package shape corroborates -- `redacted` (inline) HTML refreshed, `shared`/`shared_redacted` changed
only in `_assets/{report,catalog}.css` (HTML links external CSS -> bodies byte-unchanged).
`_pagedata`/`digests.json`/`golden_parquet` BYTE-UNCHANGED (NO `make_parquet_golden`). NEW
`test_design_tokens.test_v026_3_dashboard_grafana_dense` (300px, sp-4 gap, sp-3 padding, the 30%-tint rail
on both rest + hover -- count==2) + `test_table_component` `cell_title` (single-escape R1 guard); `test_c16d` hover
pin updated in-commit; `test_report_structure` chip-cluster + 6x dash-card hold under `el` (no edit). 342
green (`-m "not browser"`); token guard 0 undefined; browser matrix light/dark/print synthetic + real Perf
SIGNED OFF before bake (resting flat confirmed). Scope = 6 source (chrome.css/chrome.py/dashboard.py/
design_tokens.toml/formatters.py/base.py) + 2 tests + goldens (17 HTML + preview + package redacted HTML +
shared/shared_redacted `_assets/{report,catalog}.css`). No new ADR (rides ADR-44 + ADR-42); FINDINGS G-32
`chip_cluster` ticked.

**v0.2.6-4** (5 tabled detail reports adopt the `Column`+`data_table` family): the THIRD surface commit and
the FIRST to **break byte-parity on purpose** -- `data_table` NORMALIZES the hand-written markup (attr
order / cell shape / inline col-groups), the exact reason c16x x4 BUILT-NOT-ADOPTED the family. The golden
refresh ABSORBS the normalization (the (a)..(f) replacement contract IS exercised, not narrowed -- ADR-43).
overdraw / draws_by_class / shader_hotlist / instancing_opportunities / trend_table render every table via
`data_table`; pass_gpu (bar-rows, no table) is eyeball-only. Idiosyncrasies preserved BEHAVIORALLY:
overdraw's N per-area tables share ONE index-keyed `__colgroups_overdraw` spec (each emits its `.col-groups`
div via `data_table(..., emit_colgroups_script=False)`; the single shared script emitted once); shader_hotlist's
wide-clip `src` on the inner `<a>` + copy-button OUTSIDE + identity/cost/history col-groups + the `<details>`
secondary + resolved; instancing's 3-table family; the `.delta`/`delta-latest` comparison cells across 4
reports. **Component extensions** (chrome.py): `Column.cell_class` (per-row td class) + `header_class`
(extra th class) -- together they reproduce the delta column's split th/td classes; `data_table` emits the
`.col-groups` div when `colgroups` set + a NEW `emit_colgroups_script` toggle; NEW `colgroups_from(columns,
opens)` derives the index spec from each `Column.group` BY POSITION (no hand counter -> no off-by-one) +
makes the formerly-vestigial `group` field load-bearing; `Column.clip='default'` for the default-tier clip.
**delta.py:** NEW `delta_parts(...) -> (css_class, text)` factored out; `delta_cell`/`delta_pill` refactored
onto it BYTE-IDENTICALLY (their tests unchanged); NEW `delta_column(...)` factory (cell value = the
`(cls,text)` tuple; render/cell_class read the PASSED value -> NO closure-over-loop-var bug); `delta_cell`
kept but now UNUSED BY REPORTS (recorded, ADR-23). **Escape discipline** (mirrors -3 R1): captions / plain
headers / plain cells pass PLAIN (drop inline `base.h`) so `el` escapes ONCE; the markup header
(shader_hotlist multi-drop `uses<span class="dim">@k</span>`) passes `base.raw(...)`. **Keystone gate -- the
data-preservation proof** (the -4 analogue of -2/-3's "byte-identical outside `<style>`", which -4 can't
use): a harness renders each report BEFORE + AFTER and asserts the ordered `<th>`/`<td>` text + colgroups
indices are IDENTICAL per page -- GREEN on synthetic (2-drop: covers deltas/`delta-latest`/`_kpi_matrix`/
the shader history colgroup; 13 pages / 1859 cells, deterministic 6x). The real-Perf proof surfaced a
PRE-EXISTING overdraw row-order nondeterminism (`set(by_area[area])` tie-break on equal sample counts; two
post-migration renders disagreed on DIFFERENT cells -> confirmed pre-existing, not the migration) -> recorded
FINDINGS **R-19** (deferred, golden-neutral fix). Gates: `test_parquet_parity` + `_pagedata/*.js` +
`digests.json` + `golden_parquet` BYTE-UNCHANGED (data FROZEN); `test_table_component` EXTENDED in-commit
(cell_class/header_class, the col-groups div + `emit_colgroups_script`, `colgroups_from`, `delta_parts`/
`delta_column` incl. the per-row-independence closure guard, the `'default'` clip) -> 348 green; token guard
0; `test_report_structure` held with NO edit (the faithful migration preserved every substring/count assert).
Browser matrix light/dark/print synthetic + real Perf SIGNED OFF before bake. Scope (`git diff --stat`):
8 source (base/chrome/delta + the 5 reports) + `test_table_component` + 9 report HTML goldens + 27
golden_package HTML; net **-827 lines** (declarative columns replaced the hand-written markup); preview +
`_pagedata`/`digests`/`golden_parquet` byte-unchanged (0 data drift). No new ADR (rides ADR-43 replacement
gate + ADR-42 + ADR-44).

**v0.2.6-5** (catalog/drill wide layout + virtual hosts through the component + CLOSE the `el` long-tail):
the FOURTH (LAST) componentization commit. **(1) Wide layout** -- `per_drop.css` `body { max-width: 1800
-> 2400px }` + `.table-scroll { max-height: 60 -> 72vh }` (catalog/drill only; reports never load
`_PER_DROP_CSS`; the rdc-table ENGINE `rdc_table.{css,js}` incl. `--clip-cap*` stays FROZEN -- verified
`.table-scroll` lives in per_drop.css, NOT the engine). **(2) Virtual hosts routed through NEW chrome
table-family primitives** `table_controls` (search/count/CSV+parquet bar) + `virtual_host(table_key,
col_groups=)` (the row-less windowed `<rdc-table data-mode="virtual">` + the optional empty `.col-groups`
bar) + `virtual_table_section` (the drill per-table card); `render_root` composes the catalog inline from
the same primitives; re-exported via `base.py`. The hand-concatenated hosts in `html/template.py`
(`_inline_table_with_data`, `render_root`) now build through `el`. **Engine DOM contract preserved** (the
gotcha the substring tests miss): `<input type=search>` + `.ct.visible-count` + `.col-groups` + the
`<rdc-table>` host stay under ONE `<section>` (the engine finds them via
`host.closest('section').querySelector(...)`), host a direct child (the expand-toggle `insertBefore`),
drill section still nested in `<details class="category">` -- verified GREEN in the browser matrix
(filter count `14/14 visible` populated + col-group toggles built + Expand-cells present). **(3) `el`
long-tail CLOSED (G-32):** the 12 clean chrome leaves (`summary_bar`/`callout`/`empty_state`/`heatmap_cell`/
`provenance_strip`/`ab_picker`/`run_picker`/`run_compare_banner`/`link`/`kpi_strip`/`section_card`/`ab_strip`)
+ the `\n`-joined structural leaves (`header`/`legend`; template `_toc`/`_category_block`/`_sidecar_category`
+ the inline `render_drop`/`render_root` page fragments incl. the catalog-page chip-cluster/catalog-grid/
pair-list/pair-group) all migrated to `el`/`raw` **byte-IDENTICALLY** (Strategy A: `\n` between/around
el-built siblings preserved); the two -4-deferred leaves (`shader_hotlist` `<details><summary>`, `overdraw`
`<p class="note">`) done. **Documented irreducible floor (ADR-23):** `page_open`'s scaffold (`<!doctype>`
+ `<meta>`/`<title>`(already-escaped) + favicon `<link>` data-URI + open `<html>/<head>/<body>` + the
`_ICON_SPRITE`) is fixed safe markup `el` cannot build (no doctype/open-tag); left as-is, recorded -- "no
bespoke" = no UNJUSTIFIED bespoke. **Strategy A proven:** a fresh synthetic render diverges from golden on
EXACTLY 2 pages (root `index.html` + the drill page -- the intended host reshape + wide-layout `<style>`);
all 15 report HTML goldens BYTE-UNCHANGED (no report leaf migration shifted a byte). Gates: data FROZEN --
`test_parquet_parity` + `_pagedata/*.js` + `digests.json` + `golden_parquet` + `golden_preview`
BYTE-UNCHANGED (NO `make_parquet_golden`); the cell-text harness extended to catalog/drill (parses the
FROZEN `_pagedata/<key>.js` `window.__data_<key>={cols,rows}` + `__colgroups_*`) -- GREEN on synthetic;
the real-Perf overdraw rt-row diff is **R-19 only** (reconfirmed self-nondeterministic: same code, two
renders, DIFFERENT tied-rt cells -> pre-existing, not this commit). `test_table_component` EXTENDED +4
(virtual_table_section drill shape, virtual_host col-groups catalog-only, table_controls link-kind,
escape-by-construction on a `&`/`"` key) -> **352 green**; token guard 0; `test_report_structure`
(c16i/k/l/o substrings) held with NO edit. Browser matrix light/dark/print synthetic + real Perf (catalog
+ newest drill) SIGNED OFF before bake. Scope (`git diff --stat`): 6 source (per_drop.css/chrome.py/base.py/
template.py/shader_hotlist.py/overdraw.py) + `test_table_component` + 2 render goldens (catalog + drill) +
6 golden_package goldens (catalog/drill HTML twins + `_assets/catalog.css` on shared/shared_redacted) + 3
docs; `report.css`/report HTML goldens/`_pagedata`/`digests`/`golden_parquet`/`golden_preview`
BYTE-UNCHANGED. No new ADR (rides ADR-42/43/44 + ADR-23 documented scoping). **G-32 CLOSED.**

**v0.2.6-6** (close-out + ship): `_version 0.2.0 -> 0.2.6` (SCHEMA_VERSION stays 3 -- no data change); ONE
`## [0.2.6]` CHANGELOG covering c16q -> the redesign (ADR-39..45, G-30, G-32), `lint CHANGELOG.md` clean.
**Full matrix GREEN on the canonical `.venv` (py3.12.13/pyarrow21, ADR-11):** `-m golden_env` 5 (the
byte-identical HTML golden gate), `-m browser` 1, `-m "not browser"` 352 (353 total). **Clean-wheel
post-install verify** (the ADR-37 single-file + package-data invariant): `uv build --wheel` ->
`bobframes-0.2.6-py3-none-any.whl` carries all 15 `reports/assets/*`; a FRESH-venv install renders a STYLED
synthetic report (`@font-face` base64 font + `--accent-primary` token resolved from the installed package's
`reports/assets/*` + `design_tokens.toml`) and a `.bobframes.toml [theme]` override from OUTSIDE the package
re-hues it (the ADR-45 pip-user path, on a clean install). No production change beyond the version bump; no
new ADR. **TAG + PyPI gated on explicit authorization** (outward/irreversible -- NOT part of the green gate).

## 21.1w v0.2.7 aggregation consistency: one per-frame basis, named estimators (ADR-46) -- see [v027 commits](../commits/v027/)
The "confusing averages" burndown (audit `reference/AGGREGATION_FINDINGS.md`; D-13..D-16 / Q-10..Q-13 /
H-41). Each commit that changes emitted numbers/labels is a BOUNDED golden refresh (ADR-23 -- intentional,
diff reviewed; never a silent narrowing); the **data path is FROZEN** every commit (`golden_parquet` +
`_pagedata` BYTE-UNCHANGED, NO `make_parquet_golden`). New gates, all in `-m "not browser"`:
- **frame-count single owner (v027_0, D-15):** `test_aggregates` -- `aggregates.frame_counts` owns every
  per-(drop, area) count; `frame_count_divergences` flags ONLY a genuinely skewed (drop, area); the entity
  divisor (`DrawAgg.frames`) is unchanged (c16v held). Golden-NEUTRAL (the warning is `log()`/stderr).
- **per-frame regression parity (v027_1, D-13/H-41):** `test_trend_regression_basis` -- a 7-vs-5-capture run
  at equal per-frame cost -> 0 regressions (was a false +40% from raw totals); a real per-frame rise flags;
  `.bobframes.toml gpu_regression_pct` moves BOTH the heatmap alarm cells and the hero count (config defaults
  reproduce the old `KPIS` literals, `test_config`).
- **cross-report per-frame consistency (v027_2, D-14/D-16):** `test_report_structure.test_cross_report_per_frame_gpu_consistent`
  -- a given area's per-frame GPU reads byte-identically on the dashboard card and the summary By-area table.
- **true median + total/per-frame pair (v027_3, Q-11/Q-12):** `test_draws_by_class_kpis` -- the prepass/opaque
  ratio is `statistics.median` (even-n proof vs the old upper-middle `sorted[n//2]`); "total ... over captures"
  is paired with a per-frame mean.
- **naming gate (v027_4, ADR-46):** `test_report_structure.test_no_vague_estimator_labels` -- no rendered
  LABEL (kpi-label / th / caption) uses the vague "avg"/"average"/"(med)"/"typical"; estimators are NAMED
  ("pooled mean" / "mean ... (per area)" / "median ..." / "total ... over captures"). Scoped to label
  contexts so the base64 font blob (an incidental "Avg") is ignored.
- **Q-13 (recorded, not changed):** overdraw reject% is a pooled micro-average over pixel samples (correct);
  summary "worst overdraw" is a MAX selection (correctly labeled) -- documented so neither is "fixed" into a
  mean by mistake.
Suite 352 -> 362 (`-m "not browser"`). The v0.2.7 RELEASE ship (version bump + CHANGELOG + tag) is a separate
later commit, gated on authorization.

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
