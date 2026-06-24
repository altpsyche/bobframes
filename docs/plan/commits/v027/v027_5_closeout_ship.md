# v0.2.7-5 -- close-out + ship to PyPI     release: v0.2.7 · phase: aggregation-consistency (FINAL)

> The release commit. v0.2.7-0..-4 are DONE (frame-count single source of truth + divergence warning,
> regression unification per-frame + config thresholds + ADR-46, cross-report GPU consistency + named
> estimators, median + total-basis disclosure, the Q-13 record + naming-gate close-out) plus three
> report/sharing correctness fixes found while sharing the real corpus (R-20 run-selector init, R-21
> detached one-pager dead nav, R-22 older-run cross-drop scope). This commit bumps the version, writes
> the ONE CHANGELOG entry for the release, runs the full gate suite incl. the `golden_env` byte-gate,
> and proves a clean wheel bakes 0.2.7. `_version` `0.2.6 -> 0.2.7`. No new ADR.
> **TAG + PyPI happen ONLY after explicit user authorization** (outward / irreversible).

## Goal
`bobframes 0.2.7` is releasable: `_version 0.2.6 -> 0.2.7` (SCHEMA_VERSION stays 3 -- no data-format
change), ONE `## [0.2.7]` CHANGELOG entry, the gate suite GREEN on the canonical env (incl.
`golden_env`), and a clean-built wheel bakes `0.2.7` with `replay_main.py` force-included. The tag +
PyPI upload are gated on explicit authorization.

## Scope
- **bobframes/_version.py.** `__version__ = "0.2.6" -> "0.2.7"`. (Dynamic version: `pyproject.toml`
  `[tool.hatch.version] path = "bobframes/_version.py"`.) `schemas.SCHEMA_VERSION` stays **3** (no data change).
- **CHANGELOG.md.** A single `## [0.2.7]` section (newest first, under `## [Unreleased]`) summarizing the
  release: the canonical aggregation policy + named estimators (ADR-46; D-13..D-16, Q-10..Q-13),
  regression unification per-frame + config thresholds (H-41), the `statistics.median` fix, the
  `aggregates.frame_counts` single owner + divergence warning, and the R-20/R-21/R-22 report/sharing
  fixes. No schema change (still 3); parquet digests byte-identical on the same captures. The stale
  bottom link-refs (Unreleased pointed at `v0.1.0`) corrected. `lint CHANGELOG.md` clean.
- **Verification (no production code change beyond the version bump + CHANGELOG).** Full `pytest` on the
  canonical `.venv` (py3.12/pyarrow21): `-m "not browser"` (includes `-m golden_env`, the byte-identical
  HTML golden gate, canonical-env-only per ADR-11). Clean-wheel build verify (`uv build --wheel`,
  inspect the wheel: `_version.py` == 0.2.7, `replay_main.py` present).
- **Docs.** STATE.md (`current` -> released/next), this commit doc as-built.

## Gates / Done when
- `_version` == 0.2.7; `bobframes version` prints `bobframes 0.2.7  schema 3  pyarrow 21...`.
- ONE `## [0.2.7]` CHANGELOG entry; `lint CHANGELOG.md` clean.
- Gate suite GREEN on the canonical env: `-m "not browser"` (incl. `golden_env`).
- Clean wheel bakes 0.2.7 with `replay_main.py` force-included.
- STATE updated; commit on `main`.
- **TAG + PyPI ONLY after explicit authorization** (NOT part of the green gate; outward/irreversible).

## As-built (DONE 2026-06-24 -- release-ready; tag + PyPI await authorization)
- **Version:** `_version.py` `0.2.6 -> 0.2.7`; `bobframes version` prints `bobframes 0.2.7  schema 3
  pyarrow 21.0.0`. SCHEMA_VERSION unchanged (3).
- **CHANGELOG:** ONE `## [0.2.7] - 2026-06-24` entry (Changed/Fixed) covering the aggregation-consistency
  pass (ADR-46) + the R-20/R-21/R-22 fixes; bottom link-refs repaired. `bobframes lint CHANGELOG.md`
  exit 0.
- **Gate suite GREEN on the canonical `.venv` (py3.12.13/pyarrow21):** `python -m pytest bobframes/tests
  -m "not browser"` -> 365 passed, 2 deselected (the byte-identical HTML golden gate runs here on the
  canonical env, ADR-11; post version-bump nothing broke). `-m browser` not run unattended (needs Chrome).
- **Clean-wheel verify:** `uv build --wheel` -> `bobframes-0.2.7-py3-none-any.whl`; inspected:
  `bobframes/_version.py` == `__version__ = "0.2.7"`, `replay/replay_main.py` force-included (ARCHITECTURE
  §3). CI re-builds + `twine check` on the publish runner.
- **REMAINING (gated on explicit authorization, NOT in the green gate):** `git tag v0.2.7` -> push ->
  the ci.yml `publish` job builds + uploads to PyPI (Trusted Publishing / OIDC, ADR-13) + cuts a GitHub
  Release. Outward + irreversible; do NOT run until the user says so.
- **No production code change** beyond the version bump + CHANGELOG. No new ADR. CARRY-OVER: FINDINGS
  R-19 (overdraw tie nondeterminism, own commit, needs a multi-tie fixture).

## Next
After authorization: `git tag v0.2.7` -> push -> the tag-triggered CI publish (PyPI + GitHub Release);
verify `pip install bobframes==0.2.7` from live PyPI. Then v0.2.8 (the `bobframes ui` control panel;
approved plan ~/.claude/plans/lets-plan-on-improving-bubbly-bumblebee.md) on a fresh
`feat/v028-ui-control-panel` branch, and the R-19 fix (own commit).
