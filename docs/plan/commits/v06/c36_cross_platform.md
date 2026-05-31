# c36 — cross-platform tool locator + non-Windows tree-kill     release: v0.6 · phase: Cross-platform + leads + plugins

## Goal
Run BobFrames on Linux/macOS. Extend the c06 resolver with per-OS RenderDoc locations, drop the
Windows-only assumptions (`.exe`, `taskkill`, the `sys.platform` gate), and platform-dispatch the
process-tree teardown. Windows behavior stays byte-identical.

## Depends on
[c06](../v02/c06_tool_resolver.md) (`config.resolve_tool`). v0.5 complete. [ADR-18](../../DECISIONS.md)
(cross-platform lands v0.6).

## Seam extended
`config.resolve_tool` (known-paths step) — add Linux/macOS install locations and drop the hardcoded
`.exe`. `qrd_harness._kill_tree` — platform dispatch. `cli._cmd_check` — relax the
`sys.platform!='win32'` gate (H-38).

## Files
- `config.py` — per-OS known paths (Linux: package/manual RenderDoc; macOS: `.app` bundle); resolve the
  tool name without a forced `.exe` suffix.
- `bobframes/proctree.py` (or `qrd_harness`) — `kill_process_tree(pid)`: Windows `taskkill`/job object
  (unchanged); POSIX `os.killpg` with `start_new_session=True` on Popen.
- `qrd_harness.py` — launch with the per-OS new-session flag; call `kill_process_tree`.
- `cli.py` `_cmd_check` — only exit 3 when no tool resolves on the current OS (not unconditionally on
  non-Windows); update the message.
- CI — add a per-OS **nightly** real-`.rdc` lane (self-hosted; ADR-6).

## Changes
Windows path is byte-for-byte unchanged (same resolution, same taskkill). POSIX is new. The `.rdc`
extraction itself is RenderDoc's job — no data change.

## Done when
- `bobframes check` resolves `renderdoccmd`/`qrenderdoc` on Linux/macOS when installed; exit 3 with the
  updated message when not.
- `kill_process_tree` reaps the tree on POSIX (per-OS mocked-subprocess unit test) and Windows
  (unchanged).
- **Windows golden parity green** (byte-identical); the rendered output is OS-independent.

## Closes
H-38 (platform process model). Serves the ≥1-non-Windows-OS breadth criterion. Supersedes
ARCHITECTURE §12 "Windows only in v1" for v0.6+ (annotated via [ADR-18](../../DECISIONS.md)).
