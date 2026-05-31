# c32 — `PipelineStateAdapter` refactor (GL adapter = today)     release: v0.5 · phase: Graphics-API epic

## Goal
Put the graphics-API epic on rails: refactor the GL-only extraction behind a `PipelineStateAdapter`
abstraction with **zero output change**. This is a SEPARATE commit BEFORE any schema-widening so the
refactor's parity is proven in isolation. The GL adapter is exactly today's code.

## Depends on
v0.4 complete. [ADR-15](../../DECISIONS.md) (Vulkan is the next API, but lands in c34 — not here).

## Seam extended
`replay/replay_main` `GetGLPipelineState` call sites (`_read_draw_state`, `_extract_draw_aux`,
`_snapshot_uniforms`), the GL chunk-name sets (`_CLEAR_CHUNK_NAMES`, `STATE_CHANGE_CHUNK_NAMES`,
`_INDIRECT_CHUNK_NAMES`), `_decode_ubo_member` (std140), `GL_*_ATTACHMENT` naming. **`ctrl.API()`
dispatch is introduced here** (none exists today).

## Files
- `replay/adapters/__init__.py` — NEW: `PipelineStateAdapter` base (interface: pipeline-state read,
  draw-aux, uniforms/UBO decode, clear/state/indirect chunk sets, attachment naming) + `select(ctrl)`
  that dispatches on `ctrl.API()`.
- `replay/adapters/gl.py` — NEW: `GLAdapter` — the **current** GL paths moved verbatim behind the
  interface (GetGLPipelineState, std140 decode, GL chunk sets, `GL_*_ATTACHMENT`).
- `replay/replay_main.py` — call `adapters.select(ctrl)` and route extraction through the adapter;
  the `*_COLS` tuples stay (still guarded by the c13 drift test).

## Changes
Pure move-behind-interface. No column changes, no new tables, **no schema bump**. The replay-side
`*_COLS` duplication policy (H-6, c13) is unchanged — the adapter does not alter emitted columns.

## Done when
- Synthetic GL golden **byte-identical** (parity green).
- Replay-drift test (c13) still green (columns unchanged).
- `adapters.select(ctrl)` returns `GLAdapter` on a GL capture (`ctrl.API()` dispatch live).
- **No `SCHEMA_VERSION` change.**

## Closes
Opens the API epic. Begins H-36 (GL-only pipeline-state reads now isolated in `GLAdapter`).
