# c06 — `config.resolve_tool()` + `errors`; glob version detection     release: v0.2 · phase: De-hardcoding

## Goal
One resolver for `renderdoccmd`/`qrenderdoc`, with env > config > PATH > known-paths precedence and a
helpful exit-3 error. Fixes the quarterly Arm-version path breakage (H-7). Makes `bobframes check`
real. **Candidate to pull forward into v0.1** if portability is needed sooner ([ADR-2](../../DECISIONS.md)).

## Depends on
[c05](c05_registry_consolidation.md). (Full TOML loader is [c07](c07_toml_config.md); this commit
reads `[tools]` if present but works on defaults.)

## Files
- `config.py` — NEW: `resolve_tool(name)` per [ARCHITECTURE §5](../../ARCHITECTURE.md).
- `errors.py` — NEW: `ToolNotFound`, `PipelineError`, exit-code map.
- `rdcmd.py`, `qrd_harness.py` — replace inline discovery with `config.resolve_tool(...)`; keep
  `qrd_harness` `_SEP` + `RDC_INSIDE_ARGS` wire untouched.

## Changes
- Resolution order: `BOBFRAMES_*` env (legacy `RENDERDOCCMD`/`RENDERDOC_QRENDERDOC` with one-shot
  deprecation log) → `[tools]` config → `shutil.which` → known Windows paths → raise `ToolNotFound`.
- **Glob version detection (H-7):** `C:/Program Files/Arm/Arm Performance Studio */renderdoc_for_arm_gpus/<tool>.exe`,
  pick latest by directory-name sort; same idea for vanilla RenderDoc paths.
- `check` prints the resolved paths and the precedence; exit 3 + the §5 error block on miss.

## Done when
- `bobframes check` prints resolved paths; exit 0 when found, 3 with the §5 message when not.
- Renaming the Arm folder to a newer version still resolves via glob.
- Golden parity green (discovery doesn't touch rendered output).

## Closes
H-7. Provides the resolver that ARCHITECTURE §5 specifies as the target.
