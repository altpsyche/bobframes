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
