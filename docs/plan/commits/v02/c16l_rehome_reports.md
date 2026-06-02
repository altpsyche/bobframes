# c16l — re-home reports + dashboard + run model as SPA views (ADR-36, phase 3)     release: v0.2

## Goal
Move the **whole report output** into the app: the dashboard, the 6 reports, A/B, and the c16e/c16f run
model become hash routes rendered as `_views/*.html` fragments by the **existing** Python renderers
(`reports/chrome.py` / `charts.py` / the report modules) — no JS reimplementation. The flat
`_reports/*.html` files are **removed** (replace-now, ADR-36); their content lives as routes.

## Depends on
[c16j](c16j_spa_spine.md) + [c16k](c16k_data_decoupling.md). ADR-36; reuses ADR-33 charts + ADR-35 run model.

## Scope
- Routes: `#/dashboard`, `#/report/<name>`, `#/run/<key>/<report>` (replaces c16f's pre-rendered per-run
  FILES — same RunContext + run picker, now driving routes not file paths), `#/ab/<pair>/<report>`.
- `report_page` emits a **fragment** (header/strip/picker/banner/cue + body) instead of a full page; the
  shell supplies `<head>`/CSS/JS. The run picker / A/B picker / "older run" cue / baseline banner become
  route links (the c16f navigation, now in-app). The crumb/nav use hash routes.
- The dashboard cards + cross-report nav + trend links become route links (drop the `crumb_depth`/
  `reports_up`/per-run-dir path machinery — routing replaces it).
- Charts (inline SVG, ADR-33) ride inside fragments unchanged (deterministic).

## Constraints (do not regress)
- Preserve the **run model** (ADR-35) exactly — per-run truth, current vs baseline, resolved-since,
  trend_table/A-B as across-run views — now expressed as routes; the `RunContext` logic is unchanged.
- Offline `<script src>` only; byte-deterministic fragments; a11y (focus mgmt + `aria-live` on route
  change), reduced-motion, print per view. Golden gates the fragment file-set + bytes.
- `test_parquet_parity` untouched (§21.9). Migrate the c16e/c16f run-model tests to assert routes/fragments
  instead of files (the model invariants stay: live ⊆ current run, header names the run, etc.).

## Done when
- Dashboard + all 6 reports + A/B + the run model render as in-app routes; flat `_reports/*.html` are
  gone; navigation is hash-routed with no full-page reload; run model verified (synthetic + real data,
  light/dark). Golden green; parquet parity unchanged; smoke lint clean.

## Closes
ADR-36 phase 3. The bulk of G-18/G-19/G-35-era UX now lives in the app (the underlying models unchanged).
