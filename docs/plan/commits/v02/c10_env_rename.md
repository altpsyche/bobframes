# c10 — rename env vars `RDC_*` → `BOBFRAMES_*`     release: v0.2 · phase: De-hardcoding

## Goal
Bring env vars under the `BOBFRAMES_` namespace with a one-release legacy fallback, and finish the
`RDC_ROOT` removal started in c03 (R-5).

## Depends on
v0.2 chain ([c07](c07_toml_config.md) for the config precedence story).

## Files
- `pipeline`, `qrd_harness`, `replay_main` — env var reads.

## Changes
- `RDC_KEEP_STAGE` → `BOBFRAMES_KEEP_STAGE`; `RDC_PIXEL_GRID` → `BOBFRAMES_PIXEL_GRID` (legacy names
  accepted one release with a one-shot deprecation log).
- `RDC_ROOT` → **eliminated**; pass `--project-root` as an explicit CLI arg to `parse_init_state`
  (completes R-5; resolves the Q-5 positional-vs-env comment mismatch).
- `RDC_INSIDE_ARGS` → **kept verbatim** (qrenderdoc ↔ harness wire protocol — do not rename).

## Done when
- Ingest works with `BOBFRAMES_*`; legacy `RDC_*` still works + logs a deprecation once.
- No `RDC_ROOT` reads remain; `parse_init_state` takes the path as an arg.
- Golden parity green.

## Closes
H- (env portion) · R-5 (completes) · Q-5.
