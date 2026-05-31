# c35 — register Vulkan extension tables + `SCHEMA_VERSION` 3→4     release: v0.5 · phase: Graphics-API epic

## Goal
Formally widen the schema for multi-API: register the Vulkan extension tables in `schemas.TABLES`,
bump `SCHEMA_VERSION` 3→4, and refresh **both** goldens. This is the one intentional schema bump of
the epic; GL output bytes change only because the version stamp moves — the GL *data columns* are
unchanged.

## Depends on
[c34](c34_vulkan_extraction.md). [ADR-14](../../DECISIONS.md) (unified core + extension tables; the
bump is isolated here).

## Seam extended
`schemas.TABLES` (register the `api="vk"` extension tables + move `gl*_count` to a `api="gl"`
`frame_totals_gl` table per H-37, if chosen — state the exact relocation in the PR), `schemas.SCHEMA_VERSION`,
the manifest compatibility check (`render`/`catalog`/`ab` refuse on `manifest.schema_version !=
SCHEMA_VERSION` → exit 1; fix = `ingest --force`).

## Files
- `schemas.py` — register Vulkan extension tables; bump `SCHEMA_VERSION = 4`; (optionally) relocate
  `gl*_count` into `frame_totals_gl` (`api="gl"`) per H-37.
- `tests/data/golden/**` + `tests/data/golden-vk/**` — **refresh both** on the canonical cell
  py3.12+pa21 ([ADR-11](../../DECISIONS.md)).
- `CHANGELOG.md` — note the `SCHEMA_VERSION` 3→4 bump (pre-1.0 ⇒ bobframes MINOR) + the `ingest --force`
  migration (G-3).
- README — `bobframes version` now prints `schema 4`.

## Changes
Output-changing by design. **Refresh the golden in this PR and review the diff** (the version stamp +
any `gl*_count` relocation). New API columns are additive/optional and never edit GL *data*; ID_COLS
(H-29) stays frozen as the extension-table join key.

## Done when
- `bobframes version` prints `schema 4`.
- **Both goldens refreshed + reviewed; parity green** against the new goldens (GL + VK), baked on the
  canonical cell.
- Stale-manifest refusal works: `render`/`catalog`/`ab` exit 1 on a `schema_version=3` manifest; fix is
  `ingest --force`.
- Schema regression + replay-drift green for both APIs.

## Closes
H-37 (gl-count relocation, if taken). Completes the ≥2-graphics-APIs breadth criterion. First
post-v0.1 `SCHEMA_VERSION` bump (G-3 migration documented; `bobframes migrate` flagged for v1.0).
