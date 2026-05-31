# c39 — optional Figma token sync (designer Track B)     release: v0.6 · phase: Cross-platform + leads + plugins

## Goal
Close the designer loop with Figma Token Studio. Optional, low-priority tail of the roadmap — the c08
design tokens already round-trip to `toml|json|css`; this adds a Figma format and an optional sync.

## Depends on
[c08](../v02/c08_design_tokens.md) (design tokens TOML + `export-tokens`). See
[DESIGNER.md](../../reference/DESIGNER.md) Track B.

## Seam extended
`cli.py` `export-tokens` (c08) — add a `figma` format; `reports/design_tokens.toml` as the source of
truth. No core dependency change — any Figma API/sync is behind an optional extra or a documented
manual flow.

## Files
- `reports/tokens_figma.py` — NEW: map `design_tokens.toml` ↔ Figma Token Studio JSON schema.
- `cli.py` — `export-tokens --format figma`; optional `--sync` behind a `[figma]` extra (no core dep).
- Docs — DESIGNER Track B: the Figma export/sync workflow.

## Changes
Purely additive and optional. Default install gains nothing heavy; the Figma path is opt-in.

## Done when
- `bobframes export-tokens --format figma` round-trips the tokens to Token Studio JSON.
- Bidirectional sync (if implemented) is behind the `[figma]` extra; core install unaffected.
- **Golden parity green** (no core output change).

## Closes
Designer Track B (Figma export). Roadmap tail — lowest priority.
