# c07 — TOML config layer     release: v0.2 · phase: De-hardcoding

## Goal
A `tomllib`-based config with bundled defaults that reproduce today's behavior **byte-identically**;
power users override via per-project `.bobframes.toml`. Lifts timeouts, weights, limits, banlist, and
the drop-folder regex out of code.

## Depends on
[c06](c06_tool_resolver.md).

## Files
- `config.py` — full TOML loader returning a dataclass; lookup precedence per [ARCHITECTURE §6](../../ARCHITECTURE.md).
- `_default_config.toml` — NEW: full default schema.
- Readers switch to the config singleton: `qrd_harness` (`replay_timeout_s`), `rdcmd`
  (`convert_timeout_s`), `lint` (`extra_banned`), `derive_post_merge` (`[scoring.complexity]`),
  `formatters` (`id_short_n`, `text_trunc_max`), `delta` (`delta_fmt`, `bar_label_min_pct`),
  `discovery` (`drop_folder_regex`), `formatters._BANNED_CHROME_CHARS` (banlist TOML).

## Changes
Each literal reads from config with the default equal to today's value.

## Done when
- **Parity gate is the hard part** ([ADR-6](../../DECISIONS.md)): defaults must reproduce current
  output byte-identically. Add assertions that the config-loaded **regex `.pattern`** equals the
  original and that **complexity-weight float formatting** is unchanged. Golden parity + schema green.
- A scratch `.bobframes.toml` overriding a timeout takes effect; precedence CLI > env > config >
  default verified.

## Closes
H-12, H-13, H-14, H-16, H-17, H-21, H-22, H-23, H-30 · Q-3.
