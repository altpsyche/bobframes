# v029_13 -- close-out: version + CHANGELOG + docs     release: v0.2.9 · phase: ui

> Closes the v0.2.9 `bobframes ui` panel-polish track (v029_0..12 all DONE). Version bump + CHANGELOG +
> doc close-out; confirm the golden gate is byte-unchanged and the wheel ships the panel assets. The
> release itself (PR -> tag -> PyPI) is GATED on user authorization.

## Scope
- **`bobframes/_version.py`** -- `0.2.8 -> 0.2.9` (SCHEMA_VERSION stays 3).
- **`CHANGELOG.md`** -- a `## [0.2.9] - 2026-06-24` section (Added: cancel, write-config, root input,
  ingest estimate, A/B all-pair links, reveal, log copy/download, serve list/stop, favicon; Changed:
  aria-live, RUN-column de-dup, narrow-width, pruned job registry) + the `[Unreleased]`/`[0.2.9]`
  compare link-refs.
- **STATE / INDEX / ROADMAP** -- close-out (v0.2.9 feature-complete / release-ready).

## Gates / Done when
- `bobframes version` -> `0.2.9 schema 3`; `bobframes lint CHANGELOG.md` exit 0.
- `pytest -m golden_env` byte-parity unchanged, **NO golden refresh** (the version bump appears in no
  rendered HTML -- the panel emits none); `pytest -m "not browser"` green.
- `uv build --wheel` -> `bobframes-0.2.9-py3-none-any.whl` ships `bobframes/ui/assets/panel.{js,css}` and
  bakes `_version` 0.2.9; no new runtime dependency.

## As-built (DONE 2026-06-24)
- VERIFIED: `bobframes version` -> `bobframes 0.2.9  schema 3  pyarrow 21.0.0`; `lint CHANGELOG.md`
  exit 0; `-m golden_env` **5 passed BYTE-UNCHANGED, NO golden refresh**; `-m "not browser"` **432
  passed / 5 deselected**; clean wheel `bobframes-0.2.9-py3-none-any.whl` ships `ui/assets/panel.{js,css}`
  + bakes `_version 0.2.9`; favicon is inline (no asset file); no new dependency; no new ADR
  (rides ADR-47/45/23).
- **v0.2.9 epic COMPLETE / RELEASE-READY.** REMAINING (GATED on user authorization): the v0.2.9 PR off
  `feat/v029-panel-polish` -> `main`; before tag run `pytest -m browser` (Chrome) as sign-off; tag
  `v0.2.9` -> ci.yml publish -> PyPI + GitHub Release; verify clean-venv `uv pip install bobframes==0.2.9`.
