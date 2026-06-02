# c16d — report aesthetics + UX polish (depth, type hierarchy, chart finish, micro-interactions)     release: v0.2 · phase: De-hardcoding

> **STATUS: DONE 2026-06-02** (G-17 closed; ADR-34; QUALITY_GATES §21.1i). Shipped as four reviewable
> sub-commits on `v0.2-roadmap-c04` (UNPUSHED): **a** `9079013` depth + elevation tokens · **b** `d67c5c2`
> vendored Inter subset + dual sans/mono type · **c** `783840e` chart finish (gradients/dim-axes/titles) ·
> **d** `20b82c7` micro-interactions + pacing + secondary-data dimming. 115 -> 128 green; golden refreshed +
> browser-reviewed (light/dark/reduced-motion/print); `test_parquet_parity` untouched (§21.9). STATE is the
> source of truth.

## Goal
Take the reports from correct-but-utilitarian ("data dump") to a curated analytical experience.
[c16](c16_report_quality.md) / [c16b](c16b_report_viz.md) / [c16c](c16c_report_restructure.md) made
the reports complete and well-structured (KPI strips, charts, section cards, copy buttons, a11y);
c16d is the **visual-design pass** over that structure: depth instead of wireframe borders, a real
type hierarchy, finished charts, physical micro-interactions, and more breathing room. Presentation
only — no data / extraction change.

## Depends on
[c16c](c16c_report_restructure.md) (section cards, dashboard small-multiples, a11y) + the design-token
skeleton ([c08](c08_design_tokens.md), ADR-27) + the chart toolkit ([c16b](c16b_report_viz.md),
ADR-33). All visual; rides ADR-32 (report contract).

## Scope — the five moves

### 1. Depth over borders (de-wireframe)
Right now nearly every element is separated by `1px solid var(--border-1)`; the eye processes the
lines as much as the data.
- Drop the outline on `.card` / `section.card`; differentiate by **surface** (card background a step
  off the page `--bg`, e.g. `--surface-1`) plus a **soft, diffused elevation shadow** instead of a line.
- `.dash-card` + sticky page chrome get a slightly sharper shadow (they sit "above" the page flow).
- `table.report`: drop the vertical borders and the heavy `.table-wrap` outline; keep only a subtle
  row `border-bottom` to guide the eye across, and lean on the existing `--row-hover`.
- NEW elevation tokens in `design_tokens.toml` (e.g. a `[shadow]` block or `--elev-1/--elev-2`),
  light/dark-aware, threaded through the value-only Template skeleton (ADR-27 mechanism — no `$` leak,
  non-`:root` blocks stay out of the CSS golden like `[chart]`).

### 2. Typography + hierarchy
- KPI display numbers (`.kpi-value`) + the summary `.sb-headline`: use the geometric **sans** stack
  (`'Inter', 'Segoe UI', system-ui, sans-serif`) with `tabular-nums`, NOT `ui-monospace`. Reserve
  `ui-monospace` strictly for inline code paths (`shadow/p8`) and dense table columns.
- **DECISION CHANGED (c16d-b, ADR-34, user signoff 2026-06-02):** this doc originally said "Do NOT
  load a web font" (keep the named-fallback stack). The user re-opened the dependency posture and
  chose to **VENDOR a subset of Inter** (Latin + tabular figures, wght 400-600) baked into the wheel
  and inlined as a base64 `@font-face` data URI — pixel-identical type on every OS. This stays
  offline + byte-deterministic (a committed woff2, no network); the cost (wheel + ~40KB/page) was
  accepted. A *CDN*/network web-font is still forbidden. See `reports/assets/README.md` + ADR-34.
- Mute the noise: dim secondary data (raw index counts, dates, drop keys) to `var(--text-3)`; keep the
  actionable columns (cost proxy, wasted indices, reject %) at `var(--text-1)`.
- Remove `border-left: 3px solid var(--accent)` from in-card `h2`. Reserve the left-accent rule for
  top-level page alerts / nav only. **Watch-out:** the `rdc-sticky-h2` in-view highlight recolors that
  h2 border-left (`h2[aria-current="section"]`) — replace it with a different in-view cue (e.g. a faint
  background tint or a small leading marker) so the sticky highlight survives the border removal.

### 3. Chart finish (`figure.chart`)
The inline-SVG charts read like debug output.
- Bar / scatter fills: subtle SVG `<linearGradient>` (CSS `var()` stops) instead of flat rectangles/dots.
- Axes / ticks / gridlines: dim to the lightest border var so they recede behind the data.
- Tooltips: add a per-datum SVG `<title>` (native browser hover tooltip — static, deterministic, no JS)
  carrying the exact value, so tight inline value labels can be lightened or dropped where a bar is
  short. Keeps the existing `role="img"` / chart `<title>` / `<desc>` a11y. Route tooltip text through
  `safe_chrome_text`.

### 4. Micro-interactions (the feel)
- Spring-ish easing token + `transform: scale(1.01)` on `.dash-card` / drill-row hover. **Must no-op
  under `prefers-reduced-motion`** (the reduced-motion reset already exists — extend it to zero the
  transform/transition).
- Resting affordance: `rdc-copy-button` and primary inline links get a faint resting background tint so
  they read as clickable before hover (today they vanish into the background until hovered).
- Callouts: tint the WHOLE `.callout.sev-*` box a faint, transparent severity color (faint red for
  alarm, yellow for warn, green/blue for ok/info) instead of a stark box + colored rule. Keep the icon
  and the non-color status text (a11y — c16c).

### 5. Pacing + progressive disclosure
- Bump standard card padding `--sp-4` → `--sp-6` (or `--sp-8` where it helps); let data breathe.
- `shader_hotlist`: the secondary instruction-mix table already lives in `<details class="secondary-metrics">`
  — confirm it defaults collapsed and lead with the top offenders only; apply the same collapse to any
  other overwhelming secondary table surfaced during the pass.

## Constraints (do not regress)
- **Determinism**: no `random` / `Date` / timestamps; gradients, shadows, and `<title>` tooltips are
  static markup. No web-font fetch (offline + byte-stable).
- **Lint**: ASCII only; route any data-derived text (incl. SVG tooltip `<title>`) through
  `safe_chrome_text` — chart text rides outside `<table>` and is linted.
- **Token mechanism (ADR-27)**: new tokens go through `design_tokens.toml` + the value-only
  `string.Template` skeleton; never leak `$`; keep non-`:root` blocks out of the CSS golden.
- **Parquet parity (§21.9)**: extraction untouched → `test_parquet_parity` GREEN with NO `digests.json`
  refresh.
- **reduced-motion + print**: scale / shadow / transition disabled under reduced-motion; shadows must
  not bleed into the print stylesheet.

## Changes
Output-changing → **refresh the golden** (`python -m bobframes.tests.make_golden` +
`make_preview_golden`) and review page-by-page (ADR-23). This is a broad, CSS-heavy visual diff — the
shared chrome CSS hits drill / root / preview too; keep it intentional. Extend `test_design_tokens` for
any new token block (e.g. `[shadow]`), extend `test_charts` for gradient + per-datum `<title>` presence,
and keep `test_report_structure` green (DOM structure is unchanged — this is styling, not restructure).

## Done when
- Cards read by **surface + shadow**, not outlines; report tables are horizontal-rule only.
- KPI numbers use the sans stack (`tabular-nums`); secondary data dimmed to `--text-3`; in-card `h2`
  has no left-accent **and** the sticky in-view highlight still works.
- Charts use gradient fills + dimmed axes + per-datum `<title>` tooltips.
- Hover scale + resting affordances + tinted severity callouts present; **all no-op under
  reduced-motion**.
- Card padding increased; secondary tables collapsed by default.
- Golden refreshed + reviewed; `test_parity` green; `test_parquet_parity` unchanged (no digests
  refresh); `bobframes smoke` (render-only, 9 pages, lint clean) exit 0.

## Closes
**G-17 (report visual-design / aesthetic pass)** — the design-language layer over the c16/c16b/c16c
info-design. Builds on ADR-27 (tokens) + ADR-32 (report contract) + ADR-33 (charts). Append a new ADR
(candidate **ADR-34**) for the visual-language shift (depth-over-borders + tinted severity + no
web-font load) if the pass locks a real frozen decision. Add **QUALITY_GATES §21.1i** when it lands.
