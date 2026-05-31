# c21 — config-driven regression gating + exit code     release: v0.3 · phase: CI/automation

## Goal
Let CI fail a build on a perf/quality regression, with thresholds the user controls. Today the
thresholds are hardcoded in `reports/trend_table.KPIS`; move them into the c07 config layer and add a
gate mode that returns a non-zero exit code.

## Depends on
[c07](../v02/c07_toml_config.md) (TOML config layer), [c20](c20_json_output.md) (`--json` verdicts).

## Seam extended
`reports/trend_table.KPIS` (the `(col, label, fmt, lower_is_better, pct)` tuples) → c07 config
`[scoring.regression]` / `[gating]`. The c07 config singleton + precedence (CLI > env > config >
default). No parallel threshold store.

## Files
- `config.py` (c07) — add `[gating]` / `[scoring.regression]` defaults equal to today's KPI thresholds
  (10 / 15 / 20%).
- `reports/trend_table.py` — read thresholds from config instead of the inline `KPIS` literals; keep
  the KPI list shape.
- `cli.py` — `report trend --gate` (and `ab --gate`) → exit 1 when any KPI regresses past its
  configured threshold; `--json` emits per-KPI verdicts (`{kpi, prev, cur, pct, threshold, regressed}`).

## Changes
Defaults reproduce today's behavior **byte-identically** (the c07 parity surface, [ADR-6](../../DECISIONS.md)
— assert the threshold float formatting is unchanged). The gate is opt-in (`--gate`); without it,
behavior and HTML are unchanged. Any on-page "regression" badge stays additive/off until a golden
refresh.

## Done when
- `report trend --gate` exits 1 on a synthetic regression beyond threshold, 0 otherwise.
- A scratch `.bobframes.toml` overriding a threshold takes effect; precedence verified.
- `--json` emits per-KPI verdicts carrying `json_schema_version`.
- **Golden parity green** — report HTML unchanged (gate is exit-code only unless golden refreshed).

## Closes
Serves the leads "configurable regression gating" + "custom KPIs" criteria. Lifts the
`trend_table.KPIS` hardcode into config.
