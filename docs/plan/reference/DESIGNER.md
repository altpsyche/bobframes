# Designer tooling track (v0.2)

> Carved from CLI_PLAN §18. Per [ADR-1](../DECISIONS.md) this is **v0.2** — Track A ships with the
> design-tokens work in [c08](../commits/v02/c08_design_tokens.md). Recorded here so the target is
> visible while v0.1 ships. Problem today: tokens are a hardcoded Python string in `chrome`; no
> preview page, no export, no hot-reload — a non-Python designer can't iterate.

## Track A — v0.2 deliverables (ship with c08)

1. **Extract design tokens to TOML** — `reports/design_tokens.toml` (`[color]`, `[spacing]`,
   `[type]`, `[motion]`, `[layout]`). `chrome` loads via `tomllib.load(files('bobframes.reports')
   .joinpath('design_tokens.toml'))` and emits a `:root { --color-accent-primary: …; }` block.
   Designer edits TOML; no Python edit. CSS var names map 1:1 to TOML keys
   (`color.accent_primary` → `--color-accent-primary`).
2. **`bobframes preview`** — emits `_reports/_chrome_preview.html` with every visual primitive in
   isolation (swatches, KPI cards, section cards, bar styles, delta pills, sparklines incl. null
   gaps, footer/header, table rows, pagination/filter chrome, modal/drill/hover examples). No data
   dependency; renders <100ms.
3. **`bobframes render --watch`** — stdlib `os.stat` mtime poll (500ms) on `design_tokens.toml`,
   `chrome.py`, `formatters.py`, `delta.py`; re-runs render-only on change. No `watchdog` dep; alpha.
4. **`bobframes export-tokens --format <toml|json|css>`** — stdout round-trip (`toml` identity,
   `json` nested default, `css` `:root` block). `figma-tokens` format deferred to Track B.
5. **README "Customizing reports"** — designer-targeted: edit TOML → `preview` → `render`;
   DevTools live-edit for prototyping; token naming convention.

> **Parity caveat (ADR-6):** routing tokens (floats, regex) through TOML must stay byte-identical —
> the c08 parity gate asserts the emitted CSS is unchanged against the golden.

## Track B — deferred (roadmap)

| Item | Why deferred |
|---|---|
| Figma Token Studio export | verify schema vs current Token Studio; not urgent |
| Bidirectional Figma → TOML sync | needs Figma API auth + plugin/webhook |
| Custom report plugins (`~/.bobframes/reports/*.py`) | plugin security surface; wait for M-1/M-2 |
| Per-area / per-project token overrides | precedence complexity; wait for real request |
| Theme variants (dark/light/high-contrast) | `[color.dark]`/`[color.light]`; defer schema choice |
| `bobframes report --watch` (per-report) | global `--watch` is enough |
| Inline edit UI in `serve` | scope creep; serve stays static in v1 |

## Designer iteration workflow (after Track A)
```
pipx install bobframes
bobframes preview                          # opens _chrome_preview.html
edit reports/design_tokens.toml            # change a color
bobframes preview                          # <1s; reload browser
bobframes render C:\captures               # ~10s; apply to real reports from existing parquet
```
Designer never touches `.py`.
