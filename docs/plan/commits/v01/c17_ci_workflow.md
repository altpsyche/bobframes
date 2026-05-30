# c17 — CI workflow     release: v0.1 · phase: Finalize

## Goal
`.github/workflows/ci.yml`: run the full gate suite on every push, publish on a `v*` tag.

## Depends on
[c15](c15_smoke_tests.md) (tests exist), [c13](c13_replay_drift_ci.md) (drift test).

## Files
- `.github/workflows/ci.yml` — NEW.

## Changes
Per [QUALITY_GATES §21.6](../../reference/QUALITY_GATES.md):
- Matrix `windows-latest` × python `["3.10","3.12","3.13"]` × pyarrow `["17","21"]`.
  **3.14 omitted** — no pyarrow 17 cp314 wheel ([ADR-6](../../DECISIONS.md)).
- `test` job steps: `pytest tests/unit_*.py`, `tests/parity.py`, `tests/schemas.py`,
  `tests/replay_drift.py`, `tests/determinism.py`, `tests/perf.py`, then `bobframes smoke` and
  `bobframes lint tests/data/golden/**/*.html`.
- `publish` job on `v*` tag: `python -m build` → `twine upload dist/*` → create GH Release with
  wheel + sdist + CHANGELOG section. Secret `PYPI_API_TOKEN`.

## Done when
- A push turns CI green across all matrix cells.
- The `publish` job is wired and dry-validated (do not actually publish until [c19](c19_release.md)).

## Rollback
Delete the workflow file.

## Closes
Operationalizes every gate. **Known gap (ADR-6):** no GPU/RenderDoc on the runner → the ingest path
is never exercised in CI; the c03 mocked-subprocess test is the stand-in until a self-hosted runner
(v0.2). Note this in the workflow comments.
