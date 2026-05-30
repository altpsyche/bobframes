# c08 — design tokens TOML + `preview` (Track A)     release: v0.2 · phase: De-hardcoding

## Goal
Let a non-Python designer iterate: tokens move to TOML, a `preview` page shows every primitive, and
`render --watch` + `export-tokens` close the loop. See [DESIGNER](../../reference/DESIGNER.md).

## Depends on
[c07](c07_toml_config.md).

## Files
- `reports/design_tokens.toml` — NEW (`[color]`, `[spacing]`, `[type]`, `[motion]`, `[layout]`).
- `chrome` — load tokens via `tomllib`, emit `:root { --color-…: … }`; layout literals (bar heights,
  grid widths, sparkline `60x14`) read from `[layout]` (H-20). `_BANNED_CHROME_CHARS` → banlist TOML (H-16).
- `cli.py` — new verbs: `preview`, `export-tokens` (`toml|json|css`), `render --watch` (mtime poll).

## Changes
CSS var names map 1:1 to TOML keys (`color.accent_primary` → `--color-accent-primary`). `preview`
emits `_reports/_chrome_preview.html` with no data dependency.

## Done when
- `bobframes preview` opens a page showing all primitives; renders < 100ms.
- **Parity:** emitted `:root` CSS is byte-identical to today's inline tokens (golden green) — the TOML
  round-trip must not reformat values ([ADR-6](../../DECISIONS.md)).
- `export-tokens --format css` round-trips.

## Closes
H-15, H-20, H-16 · Q-6 (via `chrome.report_page` if extracted here). Designer Track A.
