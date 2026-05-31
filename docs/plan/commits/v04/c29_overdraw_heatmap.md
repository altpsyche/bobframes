# c29 — overdraw heatmap     release: v0.4 · phase: Engine breadth + ergonomics

## Goal
Give tech artists a visual overdraw signal. The `overdraw` report exists; add a per-render-target
overdraw heatmap so hotspots are visible at a glance.

## Depends on
[c08](../v02/c08_design_tokens.md) (layout tokens / chrome primitives), the existing `reports/overdraw.py`.

## Seam extended
`reports/overdraw.py` + `reports/chrome` heatmap/cell primitives + `[layout]` design tokens (c08). The
overdraw data is already derived — this is presentation only.

## Files
- `reports/overdraw.py` — add a heatmap section (per-RT grid colored by overdraw factor) using chrome
  layout primitives.
- `reports/chrome` — a small heatmap-cell helper if not already present (token-driven colors, c08).
- `tests/data/golden/_reports/overdraw.html` — refresh (additive visual → golden refresh).

## Changes
Additive visual on the existing report. Colors come from `[layout]`/`[color]` design tokens (c08) so a
designer can retune without code. Heatmap must be deterministic (sorted RTs, fixed bucketing).

## Done when
- Overdraw heatmap renders on the synthetic drop; deterministic across two renders.
- HTML lint-clean.
- **Golden refreshed + reviewed; parity green.**

## Closes
Serves the artist "overdraw heatmap" criterion.
