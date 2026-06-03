# c16w — v0.2.5 close-out: full verify + release     release: v0.2.5 · phase: close-out

> The v0.2.5 wrap. Validates the one-pager + packaging on the real corpus + the CI matrix, bumps the
> version + CHANGELOG, pushes for CI, merges to `main`, and tags v0.2.5 -> PyPI + GitHub Release. Mirrors
> the c16p / c19 release flow.

## Goal
Ship v0.2.5: tag `v0.2.5` -> PyPI + GitHub Release (OIDC, the c19/ADR-13 path), after validating the new
surfaces on real data and the full matrix.

## Depends on
c16q-c16v (one-pager + health.py + package verb + shared-assets + redact + multi-capture normalization).
All prior v0.2.x commits.

## Scope (ordered - release steps, do not reorder)
1. **Re-render + eyeball real Perf** (`C:\tmp\perf`): the new `_reports/summary.html` (+ per-run) renders;
   the verdict reads correctly on real 2-run data (current-vs-baseline gpu regression, worst overdraw,
   worst shader) and is NOT UNKNOWN where inputs exist; the dashboard nav + crumb reach summary;
   `bobframes package <perf> --shared-assets --redact` opens offline from `file://` (catalog + a report + a
   drill render, JS enhances from `_assets/`, no device values, smaller than plain). Light + dark.
2. **Version bump** `bobframes/_version.py` `0.2.0` -> `0.2.5` (the provenance strip omits the version -
   golden-safe).
3. **CHANGELOG** `[Unreleased]` -> `## [0.2.5] - <date>`: the exec one-pager + health verdict + direction
   (c16q), the `head_assets` seam (c16r), the `package` verb + shared-assets + redact (c16s-c16u), the
   multi-capture per-frame normalization (c16v). `lint CHANGELOG.md`.
4. **Push** -> CI GREEN on the full matrix (py3.10/pa17 .. py3.13/pa21): the new `test_health`/`test_summary`/
   `test_package` tiers + the existing parity/parquet/drift/schema/unit tiers.
5. **Merge** to `main`; **tag `v0.2.5`** (outward + IRREVERSIBLE - AUTHORIZE FIRST) -> OIDC publish -> PyPI
   (wheel + sdist) + GitHub Release. **Post-install verify** from a clean PyPI install: `version` (0.2.5,
   schema 3), `report summary`, `package --shared-assets` all exit 0.

## Constraints
- No schema bump; `SCHEMA_VERSION` stays 3. Extraction output stable where the pipeline is unchanged (§21.9).
- No source change beyond `_version.py` + `CHANGELOG.md` (+ any genuine CI-matrix fix surfaced by the push).
- Push + tag are authorized, outward, partly irreversible - confirm before each.

## Done when
- Real-Perf re-render + package eyeballed (light+dark); summary verdict correct; bundle opens offline.
- Version `0.2.5`; CHANGELOG `[0.2.5]` lints clean.
- CI green on push (full matrix). Merged to `main`.
- `v0.2.5` tagged -> published (PyPI wheel+sdist + GH Release) -> post-install verify green.

## Closes
**v0.2.5.** Next: c20 (`--json` output, v0.3) - which consumes `health.verdict()` (G-25 ties c21 to it).
