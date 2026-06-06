# v0.2.6-6 -- close-out + ship to PyPI     release: v0.2.6 · phase: redesign (FINAL)

> The release commit. v0.2.6-0..-5 are DONE (dev tooling/gates, token lift, flat surfaces, theme override,
> summary, dashboard, detail reports, catalog/drill + the full componentization closing G-32). This commit
> bumps the version, writes the ONE CHANGELOG entry covering the whole arc (c16q foundation -> the redesign),
> runs the full matrix incl `-m browser` + the `golden_env` byte-gate, and proves a clean wheel installs +
> renders STYLED. Per ADR-43 there is NO standalone 0.2.5 -- 0.2.6 is the next PyPI release and `_version`
> jumps `0.2.0 -> 0.2.6`. **TAG + PyPI happen ONLY after explicit user authorization** (outward / irreversible).
> No new ADR.

## Goal
`bobframes 0.2.6` is releasable: `_version 0.2.0 -> 0.2.6` (SCHEMA_VERSION stays 3 -- no data-format change),
ONE `## [0.2.6]` CHANGELOG entry, the full test matrix GREEN on the canonical env (incl. `-m browser` +
`golden_env`), and a clean-built wheel installs into a fresh venv and renders a STYLED report (the
`reports/assets/*` package-data resolves) with a working `.bobframes.toml [theme]` override from outside the
package. The tag + PyPI upload are gated on explicit authorization.

## Scope
- **bobframes/_version.py.** `__version__ = "0.2.0" -> "0.2.6"`. (Dynamic version: `pyproject.toml`
  `[tool.hatch.version] path = "bobframes/_version.py"`.) `schemas.SCHEMA_VERSION` stays **3** (no data change).
- **CHANGELOG.md.** A single `## [0.2.6]` section (newest first, under `## [Unreleased]`) summarizing the arc
  since 0.2.0: the build-health one-pager + verdict module (c16q/ADR-39), the `package` verb + shared-assets +
  redact (c16s/t/u, ADR-40/41), the per-frame + aggregates correctness spine (c16v/y), the server-side
  component system + token guard + preview gallery (c16x/ADR-42), and the v0.2.6 visual redesign + full
  componentization (ADR-43/44/45: flat/neutral shadcn surfaces, Grafana density, hero-on-summary type, the
  `--radius` scale, the user theme override, table-family adoption across reports, the `el` long-tail closed
  [G-32]). Note: no schema change (still 3); parquet digests byte-identical to 0.1.0/0.2.0 on the same captures.
  `lint CHANGELOG.md` clean.
- **Verification (no production code change beyond the version bump + CHANGELOG).** Full `pytest` on the
  canonical `.venv` (py3.12/pyarrow21): `-m "not browser"` + `-m golden_env` (the byte-identical HTML golden
  gate, canonical-env-only per ADR-11) + `-m browser` (headless-Chrome matrix, needs Chrome). Clean-wheel
  post-install verify (build sdist+wheel, install into a throwaway venv, `bobframes version`, render the
  synthetic, assert the report is STYLED [assets resolved] + a `[theme]` accent override applies).
- **Docs.** STATE.md (`current` -> released/next), QUALITY_GATES §21.1v close note, this commit doc as-built.

## Gates / Done when
- `_version` == 0.2.6; `bobframes version` prints `bobframes 0.2.6  schema 3  pyarrow 21...`.
- ONE `## [0.2.6]` CHANGELOG entry; `lint CHANGELOG.md` clean.
- Full matrix GREEN on the canonical env: `-m "not browser"` + `-m golden_env` + `-m browser`.
- Clean wheel installs in a fresh venv and renders a STYLED report (assets resolve); a `[theme]` override
  from outside the package re-hues the accent.
- STATE + QUALITY_GATES updated; commit on plan/v0.2.6.
- **TAG + PyPI ONLY after explicit authorization** (NOT part of the green gate; outward/irreversible).

## As-built (DONE 2026-06-06 -- release-ready; tag + PyPI await authorization)
- **Version:** `_version.py` `0.2.0 -> 0.2.6`; `bobframes version` prints `bobframes 0.2.6  schema 3  pyarrow
  21.0.0`. SCHEMA_VERSION unchanged (3).
- **CHANGELOG:** ONE `## [0.2.6] - 2026-06-06` entry (Added/Changed/Fixed) covering the arc since 0.2.0 --
  build-health one-pager (ADR-39), `package`/shared-assets/redact (ADR-40/41), component system + token guard
  + preview gallery (ADR-42), per-frame/aggregates spine, and the visual redesign + full componentization
  (ADR-43/44/45, G-30, G-32). `bobframes lint CHANGELOG.md` exit 0.
- **Full matrix GREEN on the canonical `.venv` (py3.12.13/pyarrow21):** `-m golden_env` 5 passed (the
  byte-identical HTML golden gate, ADR-11); `-m browser` 1 passed (Chrome found + ran); `-m "not browser"`
  352 passed (353 tests total; post version-bump, nothing broke).
- **Clean-wheel post-install verify:** `uv build --wheel` -> `bobframes-0.2.6-py3-none-any.whl` (contains all
  15 `reports/assets/*` + `_version.py`). Installed into a FRESH venv (`uv venv` + `uv pip install` -> only
  `bobframes==0.2.6` + `pyarrow==21`): `bobframes version` -> 0.2.6; a render of the synthetic produced a
  STYLED report (`@font-face` base64 font + the `--accent-primary` token present -> the `reports/assets/*` +
  `design_tokens.toml` package-data resolved from the installed wheel); a `.bobframes.toml [theme]
  accent_primary = "oklch(0.55 0.2 250)"` dropped OUTSIDE the package re-hued the render (the override value
  appears in the emitted `:root`) -> the ADR-45 pip-user theme path works on a clean install.
- **REMAINING (gated on explicit authorization, NOT in the green gate):** `git tag v0.2.6` -> push -> build
  -> `twine upload` to PyPI. Outward + irreversible; do NOT run until the user says so.
- **No production code change** beyond the version bump (the redesign shipped in -0..-5). No new ADR. STATE +
  QUALITY_GATES updated; commit on plan/v0.2.6 (UNPUSHED). CARRY-OVER: FINDINGS R-19 (deferred, own commit).

## Next
After authorization: `git tag v0.2.6` -> push -> build -> `twine upload` to PyPI; then v0.2.7 (the user's
feedback report) + the R-19 fix (own commit, needs a multi-tie fixture).
