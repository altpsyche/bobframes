# bobframes v0.2.5 proposal — report packaging + exec one-pager

> The design doc for the v0.2.5 minor (between v0.2.0 and v0.3/c20). Living. Produced 2026-06-03 from
> the v0.2.5 planning prompt + an adversarial design review (4 grounded critics + synthesis). The route
> is in [MIGRATION.md](MIGRATION.md) (c16q-c16w); per-commit detail in [commits/v025/](commits/v025/);
> the decisions are frozen in [DECISIONS.md](DECISIONS.md) ADR-39/40/41. Mirrors the depth of
> [report_roadmap.md](report_roadmap.md).

## 1. Why

bobframes 0.2.0 is live on PyPI. Output is a multi-file static HTML tree (catalog + 6 reports +
dashboard + per-drop drill + per-run + A/B + `_pagedata/*.js` + `_data/`). Two gaps block real use:

- **Sharing is awkward.** A user has "a folder of HTML on my machine" and no first-class way to hand it
  to a colleague. The tree is also fat: the base64 Inter font + the CSS + the table JS are inlined and
  **duplicated on every page**. Measured: 30 inlined report pages zip to **1.30 MB**, vs **48 KB** when
  the ~95 KB of chrome (`_compose_css()` 65 KB incl. 39 KB font + `_compose_js()` 30 KB) is a single
  shared asset. A zip's per-file DEFLATE compresses each entry independently and does NOT collapse
  cross-page duplication, so the duplication survives zipping. report_roadmap.md flagged this as
  "duplicates megabytes" across many runs.
- **No exec / non-technical read.** Every page is engineer-facing. report_roadmap.md calls the dashboard
  "flat, functional, developer-oriented." A perf lead or producer has no one-screen health read.

v0.2.5 adds **(A)** a `package` verb that turns the tree into a shareable zip, and **(B)** a print-first
exec one-pager. Both are compositions of existing primitives; the static / golden-as-output / JS-optional
report model (ADR-37) is preserved, and the default `render` output stays byte-identical.

## 2. Non-negotiable constraints (carried from ADR-6/23/37)

Offline, byte-deterministic (no `random`/`Date`/timestamps in rendered output), ASCII-only (the lint
banlist), file://-safe (no `fetch`, no ES-modules). No new heavy/runtime dependency, no headless browser,
no PDF engine (browser print-to-PDF only). ADR-37 holds literally: reports stay static, server-rendered,
JS-optional, printable, Ctrl-F-able, golden-as-output, and the default render output does NOT change.
Every output change keeps the golden parity gate green; no scope-narrowing to go green (ADR-23).

## 3. Goal A — packaging (`bobframes package`)

### 3.1 Model: a deterministic, non-mutating, stream transform
`package` reads an already-rendered `<root>` and writes a reproducible `.zip`. It never re-renders and
never edits the source tree, so `render`/`ingest` still emit byte-identical single-file inlined pages and
`test_parity` stays green. New module `bobframes/package.py`; a thin lazy-importing `_cmd_package` in
`cli.py`, slotted next to `serve` (both post-render consumers).

**Stream from source; do not stage a 2x copy.** Entries are streamed straight into the zip from source,
transforming HTML in memory (HTML is small) and writing parquet/sidecars/`_pagedata` as raw bytes read
directly from source. The golden gate reads entries back out of the produced zip, so nothing needs
materializing on disk. A materialized tree is the opt-in `--stage`, not the default. This removes the 2x
peak-disk hit on exactly the multi-GB trees that motivate sharing.

**Two tiers, one command, friendly defaults.** Shipping a folder is the friction; a non-technical reader
needs the verdict, not the tree. So `package` emits TWO artifacts in one run, both OUTSIDE the read tree:
- **Tier 0 (friendliest):** a standalone single-file `<project>-<rundate>-summary.html` (the one-pager with
  assets inlined via `head_assets(INLINE)`) - email it, double-click it, `Ctrl-P -> Save as PDF`, no unzip,
  no folder. Self-contained for READING (verdict/averages/by-area/charts all inline); its deep links to the
  reports/drill resolve only if the bundle is shipped too. `--no-summary-file` opts out.
- **Tier 1 (explorable):** `<project>-<rundate>-report.zip` - the full viewable tree. DEFAULTS to
  shared-assets (small; `--inline` is the opt-out, see 3.2), carries a root `README.txt` ("extract first,
  open index.html, start at the Build Health Summary"), and a `--light` preset bundles only summary + the 6
  reports (no drill/`_data`) for a small "read, do not drill" share.

Names come from the project (`os.path.basename(root)`) + the current run's `drop_date` (deterministic data
from the run model, NOT wall-clock; filenames are not golden-gated). `--out` overrides the zip path.
(`paths.ASSETS_DIR='_assets'` is added for the shared-asset layout. No `_dist/` inside the read root;
`discovery._list_areas` already skips `_`-prefixed entries, so there is no "ignore set" to maintain.)

**Scope = the whole VIEWABLE tree.** Root `index.html`; the whole `_reports/` subtree (`*.html`,
`drill/.../index.html`, `ab/...`, `run/...`, `_pagedata/*.js`); and the `_data/` files the HTML actually
links (catalog csv/parquet downloads, `shader_src/*.glsl`, histograms) so links resolve offline. Always
excludes `_reports/_cache/`, `.tmp`/`.stage`/rotation-backup siblings, and raw `*.rdc`.

### 3.2 Shared-asset bundle (the DEFAULT; `--inline` opts out) via a one-source-of-truth seam
Extract the (per-family) identical chrome into `_assets/` and link it depth-relative. The byte-identical
property holds only within the `chrome.page_open()` family (6 reports + dashboard + ab + run); the
catalog/drill pages (`html/template.py`) use a different unminified CSS bundle and split JS tags, so
extraction is per-family: `_assets/report.css` + `_assets/report.js` (page_open family),
`_assets/catalog.css` + `_assets/catalog.js` (template family; the identical `rdc_table_js` tag is the
biggest-count win across drill pages). The unique `__labels` inline + per-page `_pagedata/*.js` stay.

**Mechanism: a `head_assets(sink, depth)` seam, not a scrape.** The head emission in `page_open()` (and
the template equivalent) is refactored into one helper: `head_assets(INLINE)` returns today's exact
`<style>{_compose_css()}</style>{script}` (render default -> byte-identical golden, ADR-37 untouched);
`head_assets(REF, depth)` returns `<link rel="stylesheet" href="{'../'*depth}_assets/report.css">` +
`<script defer src=".../report.js">`. The packager produces the linked variant by calling the SAME helper
and writes each `_assets/*` file once from the composer output. The asset boundary is therefore one source
of truth, **zero-drift by construction** (no needle, no `str.replace`, no "exactly one replacement"
tripwire). `depth = rel.count('/')` over the file's path. All four ADR-37 contracts survive (file://-safe
links, JS-optional server-baked bodies, print CSS rides in the extracted CSS, Ctrl-F text untouched - all
AFTER extraction; see 3.6). `--inline` reproduces the per-page self-contained bundle (each page carries its
own chrome) for the rare "I want every file portable on its own" case. The package summary line emits the
measured win (total bundle bytes + duplicated-chrome bytes) so ADR-37's "measured size problem" is on
record, not assumed.

### 3.3 Redaction (`--redact`) at the data seam, strip-by-default
Scrub at the structured source, not the rendered HTML. `chrome.provenance_strip(...)` gains a `redact`
mode (emit a `<div class="device-strip">redacted</div>` placeholder / omit fields) and the packager
re-emits the affected pages' provenance from the manifest's `host_info`/`tool_versions` via the same
seam, keyed on data we own (zero regex, no false positives). For absolute paths the matched token
(`[A-Za-z]:\\...` / UNC) is **stripped by default** so the bundle is usable on real captures that carry a
path in a driver/renderer string; fail-closed is reserved for an explicit `--redact-paths=fail` CI mode.
The abs-path scan is a post-scrub completeness assertion (did redaction miss a path hiding in a value?),
not a links-are-relative guard. `host_info` is only gpu/gpu_driver/cpu/os (+ the omitted bobframes
version); there is no host/hostname field.

### 3.4 Zip determinism: gate the extracted tree
Reproducible zip: sorted `/` arcnames, fixed `ZipInfo.date_time=(1980,1,1,0,0,0)`, pinned
`ZIP_DEFLATED`+compresslevel, fixed external attrs, per-entry `writestr` (never `zip.write(path)`). The
golden is the tree extracted from the produced zip (HTML masked by `normalize()`, parquet via the logical
`parquet_digest`); zip bytes are not byte-stable across zlib/Python builds, so they are round-tripped, not
byte-compared.

### 3.5 The output-verb taxonomy (fixes the c26 collision now)
`package`'s default zip would otherwise collide with the roadmapped c26 `export --format csv|json|zip`.
ADR-40 fixes four orthogonal output contracts and assigns every current + roadmapped verb:
- **PRESENTATION** (humans; emit HTML; never `--format`; never machine data; never an asset-build engine
  beyond the render-time sink): `render`, `package`, `serve`.
- **DATA** (machines; versioned contract per ADR-16; never HTML): `export` (`--format csv|json`),
  `--json` (stdout), `schema`/`query`. `export` is the only verb that bundles `_data` as a data artifact.
- **ANALYSIS / GATING** (exit-code-bearing; consume `health.Verdict`): `diff`, `verify`, `report --gate`.
- **PIPELINE**: `ingest`/`parse`/`replay`/`catalog`.

Invariant: a presentation verb may relocate/bundle already-rendered bytes but may NOT become a data
emitter or an asset-build engine; durable capability lives in the data contract (c20/c30). Concretely,
**`package` never gains `--format`**; its artifact is unmistakably "a viewable thing."

### 3.6 Usage (accurate) - producing and reading

**Produce.** One command; defaults are the friendly choice, so a non-expert needs no flags:

| Intent | Command | Gives |
|---|---|---|
| Share everything (default) | `bobframes package C:\captures` | small shared-asset `.zip` + standalone `summary.html` |
| Email just the verdict | use the emitted `<project>-<rundate>-summary.html` | one self-contained file; `Ctrl-P -> PDF` |
| Small "read, don't drill" zip | `bobframes package C:\captures --light` | summary + 6 reports only (no drill/`_data`) |
| Share outside the studio | `bobframes package C:\captures --redact` | provenance + abs paths scrubbed |
| Every page portable alone | `bobframes package C:\captures --inline` | bigger zip, each page self-contained |

**Read (recipient).** The contract a recipient relies on - stated precisely:
- **Extract the zip FIRST**, then open `index.html`. Do NOT open files from inside the zip: Windows' in-zip
  preview extracts a single file without its siblings, so the relative `_assets/`/`_pagedata/` links break.
  After extraction, everything works offline from `file://` (the existing `_pagedata` `<script src>` already
  proves cross-folder relative loading).
- Inside, the path is `index.html` (directory) -> the promoted **Build Health Summary** -> the 6 reports /
  drill for detail.
- **Which files are portable alone:** in `--inline`, the summary / 6 reports / dashboard are each
  self-contained, but DRILL pages need their `_pagedata/` siblings; in the default shared-asset bundle NO
  page is portable alone (every page needs `_assets/`) - which is exactly why the standalone
  `summary.html` exists for the email-one-file case.
- **PDF** is the recipient-friendliest format but a manual `Ctrl-P -> Save as PDF` on the one-pager (no
  runtime PDF dependency); the page is print-tuned (one manageable page, chrome hidden, inline-SVG charts
  print as vectors).

## 4. Goal B — exec one-pager + the health verdict

### 4.1 `bobframes/health.py` — the verdict as a presentation-independent contract
The verdict ("is my frame healthy") is the tool's most durable output. ADR-37 says durable logic belongs
in the data contract, not a presentation page, and the roadmap already wires the consumers the right way
(c20 `--json`, c21 `report --gate` exit code, c37 alerts). So the verdict lives in a
presentation-independent `bobframes/health.py` (peer of the future `jsonout.py`/`export.py`, NOT under
`reports/`):

```
class State(enum.Enum): OK; AT_RISK; ALARM; UNKNOWN          # stable wire identifiers
@dataclass(frozen=True) class Trigger: rule; input; value; threshold; fired: bool; present: bool
@dataclass(frozen=True) class AreaMetrics: overdraw_pct|None; gpu_regression_pct|None;
    shader_cplx|None; mesh_repeat|None; avg_draws_per_frame: float; avg_gpu_per_frame: float
@dataclass(frozen=True) class HealthMetrics: per_area: dict[str, AreaMetrics]; has_baseline: bool
@dataclass(frozen=True) class Verdict: state: State; triggers: list[Trigger];
    worst_area: str|None; area_verdicts: dict[str, State]
class Direction(enum.Enum): IMPROVING; MIXED; REGRESSING; UNKNOWN
@dataclass(frozen=True) class Change: metric: str; area: str|None; delta_pct: float|None; kind: str  # improved|regressed|resolved|new
@dataclass(frozen=True) class Trend: direction: Direction; improvements: list[Change]; regressions: list[Change]
def area_verdict(am: AreaMetrics, cfg: ReportCfg) -> Verdict      # one area, first-match
def verdict(metrics: HealthMetrics, cfg: ReportCfg) -> Verdict    # WHERE we are: state = max(area_verdicts)
def trend(current: HealthMetrics, baseline: HealthMetrics|None) -> Trend   # WHICH WAY: direction + ledger
```

- **Per area, then roll up.** `area_verdict` scores ONE area first-match (from `ReportCfg` ONLY, no new
  threshold): `ALARM` if `overdraw_pct >= overdraw_reject_alarm_pct` or `gpu_regression_pct >=
  gpu_regression_pct`; `AT_RISK` if `overdraw_pct >= overdraw_reject_warn_pct` or `shader_cplx >=
  shader_complexity_high` or `mesh_repeat >= instancing_repeat_min`; else `OK`. `verdict()` scores every
  area, sets `state = max(area_verdicts)`, names `worst_area`, and exposes `area_verdicts` so the one-pager
  + c20 JSON render "N of M areas needs attention" rather than a single global tier one bad area paints red.
  Each comparison mirrors a source report, so the verdict cannot disagree; maxima use `n=999`.
- **Data-aware, no false-green.** An absent input (no baseline -> `gpu_regression_pct=None`; empty
  pixel_history -> `overdraw_pct=None`) is `present=False` and contributes `UNKNOWN`, never `OK`. The
  rollup surfaces `UNKNOWN` distinctly. A confident "Healthy" from missing data (the worst failure mode,
  the ADR-23 swallow-the-symptom pattern) is structurally prevented.
- **Averages convey, the worst verdict catches.** The one-pager's headline KPIs are AVERAGES (mean
  `draws/frame`, `gpu/frame`) so the numbers stay calm and per-frame-meaningful; the verdict, however,
  fires on the WORST area (overdraw/shader are MAX), so averaging the headline can never quietly bury a
  fire. The remaining asymmetry (only overdraw/gpu have an ALARM band, since config gives a warn+alarm pair
  only there) is recorded; what stays deferred is a per-dimension warn+alarm `[gating]` config table that
  lifts `shader_hotlist`'s inline `*1.25` band (G-25, H-40).
- **Direction (which way), not cumulative.** A peer `trend(current, baseline)` answers "are draws reducing /
  is there a regression": a `Direction` (IMPROVING/MIXED/REGRESSING/UNKNOWN; lower-is-better, net of the
  headline deltas) + ranked `Change` items split into improvements / regressions (incl. resolved/new counts
  from a current-vs-baseline item-set compare). It NEVER sums runs (the G-19 flaw); the long arc is the
  sparkline, the full matrix is `trend_table`. This makes the one-pager dual-use - execs read the verdict,
  tech leads glance the movement.
- **Consumers.** `summary.py` renders verdict + trend; c20 emits `state` + `area_verdicts` + `direction` +
  the `improvements`/`regressions` ledger as JSON; c21 `report --gate` maps `state` AND `direction` to an
  exit code (the "fail on regression" gate); c37 alerts + the dashboard hero (eventually) consume the same
  object. One evaluator.

### 4.2 `reports/summary.py` — pure composition + render
`build(root, *, drops=None, ab=None, run_label=None, run_date=None) -> str`, mirroring every report.
`base.output_path(root,'summary',ab,run=rc)` already routes to `_reports/summary.html` +
`_reports/run/<key>/summary.html`. It builds per-area `AreaMetrics` by reusing dashboard's current-run
helpers directly (`_top_areas_gpu` with `n=999` keyed on area, `_worst_overdraw`, `_top_shaders`,
`_top_meshes`) plus per-area frame counts from the run's drops (`avg = area total / area captures`),
assembles a `HealthMetrics`, calls `health.verdict()`, and renders. There is no new aggregation; the
`reports/aggregates.py` extraction is deferred to the 3rd consumer (G-26), guarded by a parity test that the
average KPIs reconcile with the dashboard's current-run totals / frame count.

- **Stable enum vs label.** `Verdict.state` is the contract key; the banlist-safe human labels
  (`Healthy` / `Needs attention` / `Action needed` / a distinct UNKNOWN label) are a presentation dict in
  `summary.py`/`chrome`, never in `health.py`. The lint banlist governs only presentation.
- **Layout.** verdict `summary_bar(headline=label[state], tone=ok|warn|alarm|neutral)` + a scope line
  "N of M areas needs attention - <worst_area>" + a **Direction tag** (IMPROVING/MIXED/REGRESSING) -> a
  restating `callout` -> 4 headline KPIs as AVERAGES (`avg draws/frame`, `avg gpu/frame`, `worst overdraw`
  MAX+area, `worst shader` MAX+area), each with a **colored vs-prior delta + a micro-sparkline** (so
  reducing-vs-rising is glanceable), run total small/grey for scale -> a **Movement since <baseline>** card
  (baseline-gated): Improvements (green) | Regressions (red), top ~3 named each + a "N resolved / N newly
  un-instanced" count -> a **By area** `section_card` (a bare `table.data`, ALL areas sorted worst-first:
  area | avg draws/frame (+ colored vs-prior %) | avg gpu/frame (+ colored vs-prior %) | overdraw |
  per-area status from `area_verdicts`; caption + `scope="col"`). The By-area deltas answer "which areas are
  reducing/regressing"; the Movement card is the tech-lead glance; the verdict + scope + Direction are the
  exec glance.
- **Multi-run (run model ADR-35 - NEVER cumulative).** summary reports ONE current run and never sums runs
  (the G-19 flaw). **1 run:** no baseline -> deltas + what-changed hidden, gpu-regression input UNKNOWN (no
  false-green). **2 runs:** current=newest vs the older baseline; deltas + what-changed + a 2-point
  sparkline. **3+ runs:** current=newest vs the immediately-prior run (the run picker, c16f, can re-point
  current/baseline); an N-point trend sparkline shows the arc; the full matrix stays in `trend_table`; each
  older run also gets `_reports/run/<key>/summary.html`. Current + delta + sparkline (not a column-per-run)
  scales past 2 runs cleanly - G-20 does not bite the one-pager.
- **Discoverability (the orphan fix).** Add a `summary` chip to `dashboard._NAV`; render a promoted
  `summary` link in the root-index dashboard `<section>` and EXCLUDE `summary` from the auto-listed report
  grid (the pattern that excludes `INDEX_HTML`); extend `chrome.header`'s `current_page` vocabulary to know
  `summary`. These deliberately refresh `index.html` + `dashboard.html` bytes (a reviewed golden delta) so
  the one-pager is reachable from the surfaces that mirror its data, not an orphan (ADR-23).
- **Print-friendly, one manageable page (NOT constrained to A4).** Reuse the shared `_PRINT_CSS` (hides
  chrome; inline-SVG charts print as vectors); emit `body_attrs={'data-page-kind':'summary'}` as a hook. The
  page is ONE manageable page that lists ALL areas - it is deliberately not cram-to-one-A4-screen, so the
  full By-area table prints in full regardless of area count. No per-area collapse. The scoped print rule
  (deferred) is now only about clean printing, not fitting one screen.
- **Multi-capture (multiple .rdc per area/drop) - how the numbers are computed.** Per-capture rows are
  preserved (keyed by `capture`); "frames" = captures. The headline `avg draws/frame` + `avg gpu/frame` are
  `sum-over-captures / capture-count` (the dashboard's existing `avg_*_frame`), so they are
  CAPTURE-COUNT-INDEPENDENT - 3 `.rdc` for an area do not inflate the average. The small total line shows
  the frame count for transparency ("7 areas, 12 frames, 4,417 draws total"). Overdraw % is a pooled rate
  (capture-independent); the verdict uses shader COMPLEXITY (per-shader max), NOT cost, and gpu-regression
  on avg/frame - all capture-independent. The one capture-count-SENSITIVE input is mesh repeat-count (and
  shader cost), summed across frames - mirrors the instancing/shader reports, but multi-capture inflates it
  (G-29). Per-drop TOTALS (the grey line, the detailed reports' pass-GPU/draw counts) are sums over the
  captured frames by design.
- **Build-time lint.** `write_report` raises on a banned word. Safe set: `build health`, `Healthy`,
  `Needs attention`, `Action needed`, `Direction`, `improving`/`mixed`/`regressing`, `Movement since`,
  `Improvements`, `Regressions`, `By area`, `resolved`, `newly un-instanced`, `gpu cost`, `worst overdraw`,
  `worst shader`, `draw calls`, `over the complexity budget`. Avoid: Key findings, Overview, Insight(s),
  Highlights, Significant/Notable, Overall, "this report shows", "as you can see", the word cap/caps
  (use budget/limit).

## 5. The converged surface model (recorded end-state)

After v0.2.5 there are three overview surfaces; their roles are fixed so they converge rather than accrete:
- **root `index.html` = the directory.** File-tree entry: catalog + links out to the two roll-ups + the
  six reports. Owns breadth of navigation, not metrics.
- **`summary.html` = the human / exec landing + verdict.** The "what is the state of the build" read:
  `health.Verdict` banner + 4 verdict-driving KPIs + the short action list + what changed. Print-first.
- **`dashboard.html` = the engineer drill-board.** Per-report small-multiples that fan out to the six
  reports. Convergence target: the dashboard hero `summary_bar` (today `tone='neutral'`, "worst gpu area")
  eventually consumes `health.verdict()` so the verdict shows on both surfaces from one source (deferred,
  G-27; it would churn `dashboard.html`). The longer-term option is summary as a `@media print` view of
  the dashboard rather than a permanent second file (recorded, not chosen).

## 6. Commit spine (c16q .. c16w)

| Commit | Leaves working state of |
|---|---|
| [c16q](commits/v025/c16q_health_and_onepager.md) | `bobframes/health.py` (verdict + UNKNOWN) + `reports/summary.py` print-first one-pager + discoverability nav (ADR-39) |
| [c16r](commits/v025/c16r_head_assets_seam.md) | `head_assets(sink)` one-source-of-truth seam in chrome + template; render BYTE-UNCHANGED (zero-output refactor) |
| [c16s](commits/v025/c16s_package_verb.md) | `bobframes package` -> shareable `.zip` + standalone single-file `summary.html` + root README + `--light` preset + run-derived naming; verb taxonomy (ADR-40) |
| [c16t](commits/v025/c16t_shared_assets.md) | shared-assets becomes the DEFAULT bundle delivery via the seam (`--inline` opts out); revisits ADR-37 (ADR-41) |
| [c16u](commits/v025/c16u_redact.md) | `--redact` at the provenance data seam, strip-by-default; abs-path completeness scan |
| [c16v](commits/v025/c16v_multicapture_normalize.md) | per-frame normalization of instancing repeat + shader cost across reports + dashboard + verdict (G-29); golden-neutral on 1-capture data |
| [c16x](commits/v025/c16x_component_system.md) | server-side component system: `chrome` components (`kpi_card`/`trendline`/`status_badge`) + one owned stylesheet + a token-validity guard + a preview-gallery catalog; migrates the c16q one-pager off its inline `<style>` (ADR-42, G-30). Added AFTER the spine; runs before the close-out |
| [c16w](commits/v025/c16w_v025_closeout.md) | v0.2.5 close-out (LAST): 0.2.0 -> 0.2.5, CHANGELOG, full re-ingest verify, tag v0.2.5 -> PyPI |

## 7. Rejected alternatives

- **A SPA / single-file-export bundle (ADR-36).** Already rejected by ADR-37 (web-framework tax, weakens
  golden-as-correctness, loses JS-optional). Not re-proposed. The shareable bundle lives inside the static
  model.
- **`package` scrapes its own rendered HTML** (re-import `_compose_css()`, reconstruct the inlined block,
  `str.replace` it out, guard with "exactly one replacement or fail"). Rejected: an inversion that couples
  `package` to the exact minified bytes of the composers, so any chrome edit silently breaks packaging.
  Replaced by the `head_assets(sink)` seam (ADR-41).
- **A render-time-only `render --shared-assets` (a second render-default golden tree).** Cleanest
  long-term but bigger scope; the `head_assets(sink)` seam is render-time-capable yet keeps the INLINE
  default byte-identical, so a second render golden is not needed in v0.2.5.
- **A single combined `_assets/style.css` across both page families.** Rejected: the page_open family and
  the catalog/drill family emit different CSS bundles; one shared file would require fragile substring
  surgery. Per-family asset files instead.
- **Fail-closed-only redaction (abs-path scan fails the whole package on any match).** Rejected: a real
  capture can legitimately carry a path in a driver/renderer string, making the headline feature unusable.
  Strip-by-default; fail-closed only in a CI mode.
- **`package` output under `<root>/_dist/`.** Rejected: write-into-what-you-read undercuts the
  non-mutation property at the directory level. Default output is outside the read tree.
- **Transforming the dashboard into the exec view.** Rejected for v0.2.5 (would churn `dashboard.html` and
  the verdict/aggregates are not extracted yet). Recorded as the deferred convergence target (G-27).
- **The verdict inside `reports/summary.py`.** Rejected: it is the tool's most durable output and would be
  trapped in one HTML page, colliding with the c20/c21 verdict contract. Hoisted to `bobframes/health.py`.

## 8. Open questions (resolved this session)

1. Shared-asset dedup: KEEP in v0.2.5 via the `head_assets(sink)` seam; ADR-41 revisits ADR-37 with the
   measurement.
2. Verdict home: `bobframes/health.py` (presentation-independent; seeds c20/c21).
3. Bundle scope: the whole VIEWABLE tree (HTML + `_pagedata` + linked `_data`); the data-zip is c26.
4. Redaction: data-seam scrub, strip-by-default; fail-closed only in a CI mode.
5. ADR count: three at design time (ADR-39 one-pager + verdict + IA, ADR-40 packaging + taxonomy, ADR-41
   shared-asset seam); a fourth (ADR-42, the component system) was added during c16q execution - see §9.

## 9. Added during execution — the component system (c16x, ADR-42)

c16q exposed that report styling is **brute-forced**: the one-pager shipped its look as a page-scoped
inline `<style>` (keyed on `body[data-page-kind="summary"]`) plus bespoke markup helpers (`_kpi`,
`_trendline`, a status badge, the Movement layout) that re-implement card/kpi patterns chrome already
half-owns. The untyped inline CSS bit immediately: a typo'd `var(--sp-5)` (no such token - the scale is
1/2/3/4/6/8/12) made the padding shorthand invalid, which computes to `0`, silently zeroing the chip
padding until a visual review caught it (G-30). Every new surface would repeat this pattern against one
big inlined CSS string, with no reusable + testable component layer and no guard that a referenced token
exists.

**c16x** adds a small **server-side component system** (ADR-42) - plain `chrome` render helpers
(`kpi_card`, `trendline`, `status_badge`, beside the existing `section_card`/`callout`/`summary_bar`) +
ONE owned stylesheet (the shared chrome CSS / ADR-41's `_assets/report.css`, never per-page `<style>`) +
a **token-validity guard** (reject any `var(--…)` not in the design-token scale) + a **preview-gallery
catalog** (each component rendered once into `_chrome_preview.html`, with a structural test). It is NOT a
CSS framework / build step / new dependency - ADR-37 holds. It migrates the c16q one-pager off its inline
`<style>` as the first consumer (visual parity, a reviewed golden refresh). Sequenced after c16t (so the
component CSS rides the single shared asset) and before the c16w close-out; the close-out stays last.
