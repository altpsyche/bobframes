# c37 — historical / trend dashboard + regression alerts     release: v0.6 · phase: Cross-platform + leads + plugins

## Goal
Give perf leads a multi-drop historical view plus configurable regression alerts — the lead-facing
complement to the c21 CI gate.

## Depends on
[c21](../v03/c21_regression_gating.md) (gating thresholds in config), [c07](../v02/c07_toml_config.md)
(config), [c16](../v02/c16_report_quality.md) (dashboard rename + provenance footer).

## Seam extended
The c16 `dashboard.py` + `catalog` (full drop history) + the c21 `[gating]`/`[scoring.regression]`
config. The alert thresholds reuse the c21 config — no parallel threshold store.

## Files
- `reports/dashboard.py` (renamed in c16) — add a historical section spanning all drops in the catalog
  (per-KPI sparkline/trend across N drops).
- `reports/` alerts — surface configurable regression alerts (built on the c21 verdicts) on the
  dashboard.
- `tests/data/golden/index.html` (+ dashboard) — refresh (additive → golden refresh); the synthetic
  fixture gains ≥2–3 drops to exercise history deterministically.

## Changes
Additive presentation over existing catalog data. Deterministic (sorted drops, fixed bucketing). New
multi-drop fixture rows → golden refresh in this PR.

## Done when
- The historical dashboard renders across N synthetic drops; deterministic across two renders.
- Regression alerts fire per the c21 config thresholds.
- HTML lint-clean.
- **Golden refreshed + reviewed; parity green.**

## Closes
Serves the leads "historical multi-drop dashboard" + "regression alerts" criteria.
