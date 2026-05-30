# BobFrames

RenderDoc capture pipeline extracted from a project-embedded `_analysis/` package into a standalone,
pip-installable CLI. Windows-only in v1.

## How to work in this repo (plan-driven)

Implementation runs commit-by-commit across many sessions.

**ALWAYS start by reading `docs/plan/STATE.md`.** It names the `active_release` and the `current`
commit.

1. Open `docs/plan/commits/<active_release>/<current>.md` and do **exactly that one commit**.
2. Stop when its **"Done when"** gate is green (run the verify command(s) listed there).
3. Before ending the session, update `docs/plan/STATE.md`: set the commit's status, advance
   `current` if finished, and rewrite `last_session` + `next_action`. Append a one-line session-log entry.

- `docs/plan/INDEX.md` is the map of all plan docs.
- `docs/plan/ARCHITECTURE.md` and `docs/plan/DECISIONS.md` are **frozen** — change them only by
  appending a new ADR to DECISIONS.md.
- Findings burndown: `docs/plan/reference/FINDINGS.md` (`R-/Q-/D-/G-*`) and `HARDCODE.md` (`H-*`);
  tick a row's `resolved-by` when its commit lands.
- Every change must keep the golden-snapshot parity gate green — see
  `docs/plan/reference/QUALITY_GATES.md`. Output is byte-identical unless a commit explicitly
  refreshes the golden.
- The package is named `bobframes` from the start (decided at scaffold — see DECISIONS ADR-7; the
  old c14 rename is collapsed). Do not work from `docs/plan/CLI_PLAN.archive.md` — superseded.

## Layout
- `bobframes/` — the package (source copied from the capture-project `_analysis/` tree).
- `docs/plan/` — the implementation plan (repo root, not in the package).
- Product files at root: `pyproject.toml`, `README.md`, `CHANGELOG.md`, `LICENSE`.
