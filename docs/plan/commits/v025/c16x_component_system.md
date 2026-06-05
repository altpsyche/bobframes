# c16x — server-side component system (stop brute-forcing CSS)     release: v0.2.5 · phase: components

> Promote the ad-hoc one-pager styling into reusable, tested `chrome` components backed by ONE owned
> stylesheet, and add a token-validity guard so an undefined `var(--…)` can never silently zero a
> property again. ADR-42. Picks up after the v0.2.5 spine; lands before the c16w close-out.

## Goal
A small component layer so pages COMPOSE styled components instead of each hand-rolling markup + a
page-scoped `<style>`. Born from c16q: the exec one-pager shipped its styling inline (a `<style>` keyed
on `body[data-page-kind="summary"]`) with bespoke helpers (`summary._kpi`, `_trendline`, a status
badge, the Movement layout), and a typo'd `var(--sp-5)` (no such token) silently zeroed the chip
padding (G-30). NOT a CSS framework / build step / new dependency - plain server-rendered helpers + one
shared stylesheet + a guard + gallery coverage (ADR-37 holds).

## Depends on
c16t (shared-assets default) so the now-larger shared chrome CSS is a single packaged `_assets/report.css`
rather than re-inlined bloat; the `render` default still inlines it per page (ADR-41), so the golden
refresh spans the chrome-family pages (visual parity). c16q (the primitives being promoted).

## Scope
1. **Components in `reports/chrome.py`** (its existing home): promote c16q's one-pager primitives into
   composable, documented helpers beside `section_card`/`callout`/`summary_bar`/`kpi_chip`:
   - `kpi_card(label, value, *, delta=None, trend=None, note=None, tone=…)` - the rich KPI chip c16q
     hand-built (a delta that is NOT escaped, a trend strip on its own row, a scale note). Supersedes
     `summary._kpi`.
   - `trendline(values, *, tone=…)` - the filled-area mini sparkline (polygon fill + polyline + endpoint
     dot, uniform-scaled, flat-series centered). Supersedes `summary._trendline`. Distinct from the
     shared `delta.sparkline_svg` (a different, smaller primitive other reports use) - or unify if the
     gallery review shows they should be one. 
   - `status_badge(state_name, label)` - the colored verdict badge.
2. **One owned stylesheet, no per-page `<style>`:** move the component classes (`.kpi-*` trend rules,
   `.bh-*` -> renamed to component classes, `.movement`/`.change-list`, `.bh-status`) OUT of
   `summary.py`'s inline `<style>` and INTO the shared chrome CSS (`_CHROME_CSS_TMPL` / the bundle ADR-41
   extracts). Delete `summary._SUMMARY_CSS`. summary.py becomes pure composition.
3. **Token-validity guard:** a `_tokens` accessor or a `lint` rule that scans the composed CSS (and any
   emitted `style=`/`<style>`) for `var(--NAME)` references and RAISES on any NAME not in the declared
   design-token scale (the c16q `--sp-5` class of bug). Add the missing-token regression as a unit test.
4. **Preview gallery = component catalog:** render one instance of each new component into the existing
   `_chrome_preview.html` gallery (c08, `make_preview_golden`), so every component is visually reviewable
   in isolation and carries a golden.
5. **Migrate summary.py** to the components (first consumer); re-render.

## Constraints
- ADR-37 holds: static / server-baked / JS-optional / printable / Ctrl-F-able / file://-safe / offline /
  byte-deterministic / ASCII (lint banlist); no new runtime dependency; no build step.
- ADR-23: no patch-fixes. The token guard must catch the real failure class, not just `--sp-5`.
- VISUAL PARITY: the migrated one-pager must render visually identical to c16q's reviewed output (the
  component CSS is the SAME rules, relocated + named); diffs are byte-level (class names / shared-bundle
  placement), reviewed page-by-page.

## Done when
- `summary.py` carries NO inline `<style>` and NO bespoke `_kpi`/`_trendline`/badge; it composes
  `chrome.kpi_card`/`trendline`/`status_badge`. `bobframes report summary <synthetic>` renders + is
  lint-clean + prints as ONE page; the one-pager is visually unchanged from c16q.
- The token guard RAISES on an undefined `var(--…)` (unit test); a deliberate `--sp-5` would now fail the
  build, not silently zero a property.
- Each new component appears once in `_chrome_preview.html` (gallery golden refreshed via
  `make_preview_golden`); a structural test asserts each component's markers (mirror
  `tests/test_report_structure.py`).
- Golden: a REVIEWED refresh of the chrome-family HTML goldens (the component CSS now rides the always-on
  bundle) + the preview gallery; `_pagedata/*.js` + `test_parquet_parity` UNCHANGED (presentation only,
  §21.9). The refresh is bounded to CSS-bundle bytes + summary's markup; report BODIES are byte-stable
  apart from summary.
- ADR-42 recorded; QUALITY_GATES section added; FINDINGS G-30 ticked.

## Closes
G-30 (brute-forced per-page CSS + the undefined-token footgun). Next: c16w (v0.2.5 close-out).

---

## As-built (c16x-1..-5, 2026-06-05; EXPANDED per the approved plan `bobframes-v0-2-5-continue-staged-octopus`)

The scope was expanded (user decisions): *everything is a component* (escape-by-construction, subsumes the
roadmap's C6), *look & feel must improve* (a deliberate deviation from ADR-42's visual parity — split into a
**v0.2.5 safe foundation at parity** [this commit] and a **v0.2.6 bold visual epic, ADR-43, own mini-release**),
*all-chrome-first* ordering for v0.2.6, *no hard-to-dig CSS* (extract CSS/JS to real files), and *make the unified
table a component*. c16x shipped as a 5-step sub-sequence on `plan/v0.2.5` (all green, 285→319, commits
`90bd874`/`cfa3e91`/`09d366e`/`01cb63d`/`ee9b7ff`):

- **c16x-1 — CSS/JS extraction (zero-output).** The ~1,800 lines of CSS/JS string literals moved to real files
  under `reports/assets/` (`design_tokens.css`, `chrome.css`, `sticky.css`, `link_kind.css`, `container.css`,
  `print.css`, `components.css`, `rdc_table.css`, `per_drop.css`, `components.js`, `rdc_table.js`,
  `icon_sprite.html`), loaded via `importlib.resources` (the `design_tokens.toml` precedent) through
  `chrome._read_asset` / `template._read_asset`; `${token}` + `__ROW_H__` substitution preserved. Byte-identical
  output → `test_parity`/`test_design_tokens`/`test_parquet_parity` unchanged, NO refresh. NEW `tests/test_assets.py`
  (files exist; CSS ASCII — `rdc_table.js` exempt, its sort-arrow glyph in a `<script>` body is lint-exempt;
  constants == file contents; substitution complete). Wheel-inclusion verified by the woff2 precedent (assets not
  gitignored); the full clean-install smoke runs in CI at c16w.
- **c16x-2 — element builder (subsumes C6).** `chrome.el` / `el_void` / `raw` / `classes` (+ the `_Raw` marker):
  text children + attribute values escape by construction; `_Raw` children splice verbatim; `None`/`False` skip;
  unsafe attribute names raise. Double-quoted, `html.escape(quote=True)` — matches the chrome house style, so an
  `el` rebuild of a double-quoted leaf is byte-identical. `icon` + `kpi_chip` migrated as the byte-identical
  demonstration; the remaining hand-concat leaves adopt `el` opportunistically (v0.2.6). NEW `test_element_builder.py`.
- **c16x-3 — token-validity guard (closes the G-30 footgun class).** `chrome._undefined_token_refs` /
  `undefined_tokens`: declared = (TOML `:root` scale) ∪ (every `--x:` definition scanned from the composed CSS, so
  in-body props `--crumb-h`/`--hdr-offset`/`--clip-cap*` are not false-flagged); referenced = `var(--NAME)` across
  the composed CSS **+ the bundle JS** (the rdc-heatmap tint reads `var(--accent-data)` from JS) **+ emitted
  `style=`** fragments. Kept as a CI test (not an import-time raise — would crash `version` on a styling typo);
  `bobframes preview` warns non-fatally so a designer sees the typo in their own loop. Both live bundles clean. NEW
  `test_token_guard.py`.
- **c16x-4 — table component family (built, adopted in v0.2.6).** `Column` + `data_table` (the static rdc-table
  host) + `static_table` (the bare `<table class="data">`), NORMALIZED + built through `el`. **Finding (recorded,
  user-confirmed):** a byte-identical migration of the existing ~117 hand-written table sites is **infeasible** — the
  current markup is inconsistent (attribute order differs across reports, per-report cells, inline col-groups), so
  one normalized component necessarily normalizes bytes, which only fits a golden-refreshing commit. The reports
  therefore **adopt** the component in v0.2.6 (the bold-visual epic, where the refresh absorbs the normalization);
  c16x-4 lands it as ready foundation with ZERO production migration (parity green). NEW `test_table_component.py`.
- **c16x-5 — summary migration + gallery (closes G-30).** `summary._kpi`→`chrome.kpi_card`,
  `summary._trendline`→`delta.trendline`, the verdict span→`chrome.status_badge`, the Movement layout→`chrome.movement`
  (all via `el`). `summary._SUMMARY_CSS` (a mid-body `<style>`) relocated into the owned bundle
  (`reports/assets/components.css`), renamed `.bh-trend*`→`.trendline*`, kept `[data-page-kind="summary"]`-scoped
  (inert elsewhere). `summary.py` is now pure composition + the metric-policy helpers (`_pct_pill`/`_dir_tone`/
  `_change_*`). The by-area + dashboard mini tables keep their inline markup (they adopt `static_table`/`data_table`
  in v0.2.6 with the rest). Gallery extended (kpi_card / trendline / status_badge / movement + the
  previously-ungalleried callout / empty_state). NEW `test_components.py`; `test_summary` class asserts updated in-commit.

**Golden delta (c16x-5 only; x1-x4 are zero-output).** A BOUNDED reviewed refresh, VISUAL PARITY: summary.html (the
trend SVG class rename + the mid-body `<style>` removed) + every page's inlined bundle grows by the inert scoped
summary rules (minified on report pages, verbatim on catalog/drill) + the preview gallery + `golden_package`
`report.css`/`catalog.css`. `_pagedata/*.js` + `golden_parquet/digests.json` **BYTE-UNCHANGED**
(`test_parquet_parity` green, NO refresh). The `.trendline` CSS == the old `.bh-trend` CSS, so rendering is
pixel-identical.

**Deviations from the original doc (above), recorded per ADR-23:** (1) CSS/JS source extraction (c16x-1) was added
(the "no hard-to-dig CSS" decision); (2) the token guard is a CI test + `preview` warning, not an import-time raise,
and its declared set is TOML-scale ∪ in-CSS `--x:` defs (ADR-42's "declared SCALE" wording is too narrow — to be
reconciled in ADR-43); (3) the table became its own component (c16x-4), **built but adopted in v0.2.6** (byte-identical
migration infeasible); (4) the LOOK-AND-FEEL improvement is intentionally **deferred to v0.2.6** (ADR-43) — this
commit is the parity-preserving foundation. QUALITY_GATES §21.1u added.
