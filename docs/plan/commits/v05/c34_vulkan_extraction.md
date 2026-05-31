# c34 — Vulkan extraction (`VulkanAdapter`) + fixture + golden     release: v0.5 · phase: Graphics-API epic

## Goal
Add the second graphics API. A `VulkanAdapter` reads `GetVulkanPipelineState` and emits the shared
core tables plus Vulkan-specific **extension tables**. The GL path is untouched — GL output stays
byte-identical. New synthetic Vulkan fixture + new Vulkan golden.

## Depends on
[c33](c33_data_driven_columns.md) (extension-table mechanism). [ADR-15](../../DECISIONS.md) (Vulkan
first), [ADR-22](../../DECISIONS.md) (per-API fixture+golden).

## Seam extended
`replay/adapters.PipelineStateAdapter` (c32) — add `VulkanAdapter`. `ctrl.API()` dispatch routes
Vulkan captures to it. The `parquetize` auto-fill (missing columns → defaults) means a GL capture
simply has no Vulkan extension rows.

## Files
- `replay/adapters/vulkan.py` — NEW: `VulkanAdapter` reading `GetVulkanPipelineState` (descriptor
  sets/bindings, **std430** UBO decode, `vkCmd*` clear/state/indirect chunk sets, Vulkan attachment
  naming). Emits core tables + Vulkan extension tables (`frame_totals_vk`, …).
- `replay/replay_main.py` — Vulkan `*_COLS` tuples for the extension tables (guarded by an extended
  c13 drift test).
- `tests/data/synthetic-vk/` + `tests/data/golden-vk/` — NEW Vulkan fixture (anonymized from a real
  Vulkan ingest, ADR-6/ADR-8) + NEW Vulkan golden.
- `tests/test_replay_drift.py` — extend to cover the Vulkan `*_COLS` (still asserts a minimum count;
  ADR-5/ADR-9 allowlist pattern).

## Changes
Vulkan is **new extraction**, not an edit to GL. The GL adapter, GL fixture, and GL golden are
unchanged. Vulkan extension tables are registered formally in c35 (this commit emits them; c35 bumps
the schema).

## Done when
- A synthetic Vulkan capture ingests + renders against the **new Vulkan golden** (parity green for VK).
- **GL golden still byte-identical** (parity green for GL).
- Replay-drift covers the Vulkan `*_COLS`.
- `adapters.select(ctrl)` returns `VulkanAdapter` on a Vulkan capture.

## Closes
H-36 (Vulkan path proves the adapter abstraction). Serves the ≥2-graphics-APIs criterion (pending the
c35 schema registration).
