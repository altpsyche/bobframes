# c18 — README + CHANGELOG + LICENSE     release: v0.1 · phase: Finalize

## Goal
Ship user-facing docs. README from the §13 outline; CHANGELOG in Keep-a-Changelog format; MIT LICENSE.

## Depends on
[c14](c14_rename.md) (final names) — ideally near the end so the CLI surface is settled.

## Files
- `README.md`, `CHANGELOG.md`, `LICENSE` — at repo root (NOT in the package, NOT in `docs/plan/`).

## Changes
README sections (from the carved §13 outline; the full outline lives in
[CLI_PLAN.archive.md](../../CLI_PLAN.archive.md) §13):
- Requirements (Windows 10+, Python 3.10+, RenderDoc / Arm Performance Studio)
- Install (`pipx install bobframes`; `bobframes check`)
- Quickstart (`cd captures` → `ingest .` → `serve .`)
- Subcommands table (from [ARCHITECTURE §4](../../ARCHITECTURE.md))
- External tools (RenderDoc requirement + config section)
- Output layout (tree from `paths.py` docstring)
- **Migrating from `_analysis`** (command map from [DECISIONS](../../DECISIONS.md))
- Troubleshooting (renderdoccmd not found / qrenderdoc hangs / lint fail / schema mismatch →
  `ingest --force` (G-3) / permission denied on `_data`)
- Advanced (custom probes `probes/whatif.py`, A/B workflow, config file, programmatic API)

CHANGELOG: `v0.1.0` section with the `KEY_VERSION=1` key-format note and the Windows-only / hard-rename
callouts. LICENSE: standard MIT.

## Done when
- `bobframes lint README.md CHANGELOG.md` passes the banlist (no em-dash/smart-quote/arrow chars).
- Links resolve; the migration command map matches the real verbs.

## Rollback
Remove the three files.

## Closes
Documents G-3 (`ingest --force` as the v0.1 schema-migration path).
