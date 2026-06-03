# c16p — v0.2 close-out: full re-ingest + release     release: v0.2 · phase: close-out

> The v0.2 wrap. Everything in v0.2 (c04–c16o) is on `v0.2-roadmap-c04`, ~48 commits ahead of `main`, and
> has **never run on CI** (the full py3.10↔3.13 matrix). c16p re-ingests the real corpus end-to-end, bumps
> the version + CHANGELOG, pushes for CI, merges to `main`, and tags v0.2.0. Mirrors the c19 release flow.

## Goal
Validate v0.2 on real data + the CI matrix, then ship it: tag `v0.2.0` → PyPI + GitHub Release (OIDC, the
c19/ADR-13 path).

## Depends on
c16n + c16o (the last presentation/a11y fixes). All prior v0.2 commits (c04–c16o).

## Scope (ordered — release steps, do not reorder)
1. **Full re-ingest of real Perf** (`C:\tmp\perf`, hardlinks; `Downloads` read-only) — NOT render-only.
   Regenerates EVERY drill, clearing the **stale 29 MB inline-data older-run drills** that render-only
   leaves (c16j only refreshes current-run drills; the `2026-05-25_r110565` drills are still pre-c16i/j).
   Exercises **R-16** (adb-handle vs atomic commit — now stage is a sibling of the commit dir) and **R-17**
   (replay crash-on-teardown salvage via `REPLAY_COMPLETE_MARKER`; re-test the 6 manual-flipped r110788
   captures). Replay ~150–220 s/capture, sequential. **Eyeball** all reports + catalog + drills (light+dark):
   c16d–c16o presentation holds on real data; counts stable where extraction is unchanged (§21.9 spirit).
2. **Version bump** `bobframes/_version.py` `0.1.0` → `0.2.0` (dynamic; hatch/PyPI read it). The provenance
   strip OMITS the version (golden-safe), so this does NOT churn the golden.
3. **CHANGELOG** `[Unreleased]` → `## [0.2.0] - <date>`, summarizing the v0.2 epic: de-hardcoding (c04 paths,
   c05 registry, c06 tool-resolver+errors, c06a/b drill-size + parquet-parity gate, c07 TOML config, c08
   design tokens, c09 classifier, c10 env rename), report overhaul (c16 quality, c16b charts, c16c
   restructure, c16d aesthetics, c16e run model, c16f multi-run UX, c16g/c16h quality+reliability sweeps),
   catalog/drill readability + heavy-data decoupling (c16i/c16j), and the table-unification epic
   (c16k–c16o). `lint CHANGELOG.md`.
4. **Push** `v0.2-roadmap-c04` → **CI GREEN on the FULL matrix** (py3.10/pa17 ↔ py3.13/pa21): parquet-digest
   parity runs every cell, HTML golden on the ADR-11 canonical cell, replay-drift + schema + unit tiers.
   Fix any matrix-only divergence before proceeding (first real matrix run for c04–c16o).
5. **Merge** `v0.2-roadmap-c04` → `main` (the tag belongs on `main`). Post-release nit while here: bump CI
   actions off Node20 (`checkout@v5`/`setup-python@v6`) — non-blocking.
6. **Tag `v0.2.0`** (outward + **IRREVERSIBLE — AUTHORIZE FIRST**). Tag push → CI publish job (OIDC trusted
   publishing, ubuntu) → PyPI (wheel + sdist) + GitHub Release with both assets. **Post-install verify** from
   a clean PyPI install: `version` (0.2.0, schema 3), `check` (tools resolve), `smoke` (render-only 15 pages,
   lint clean) all exit 0.

## Constraints
- The re-ingest must keep extraction output stable where the pipeline is unchanged (§21.9 holds on real
  data, as proven at c09); any count delta must be explained (run-model/derive changes), not silent.
- No source change beyond `_version.py` + `CHANGELOG.md` (+ any genuine CI-matrix fix surfaced by the push).
- Push + tag are authorized, outward, partly irreversible — confirm before each.

## Done when
- Real-Perf FULL ingest green (export→parse→replay→parquetize→derives→catalog→6 reports→dashboard→root) +
  eyeballed (light+dark), older-run drills regenerated (no stale 29 MB inline data).
- Version `0.2.0`; CHANGELOG `[0.2.0]` lints clean.
- CI green on push (full matrix). Merged to `main`.
- `v0.2.0` tagged → published (PyPI wheel+sdist + GH Release) → post-install verify green.

## Closes
**v0.2.** Next: c20 (`--json` output, v0.3).
