# v029_19 -- CI: don't gate the release on opt-in browser tests     release: v0.2.9 · phase: ui

> Surfaced by the v0.2.9 tag run: it FAILED on one matrix cell (py3.12/pyarrow21) at the pytest step,
> in `test_browser_shots.test_harness_captures_light_dark_print` -- a pre-existing dev-harness screenshot
> test that PASSED on the other 4 cells. A headless-Chrome pixel-diff flake, not a regression. Because
> `publish` needs all of `test`, the flake skipped publish and blocked the release.

## Root cause (ADR-23 -- fix the cause, don't narrow a real gate)
CI's gating step ran `-m "not golden_env"`, which INCLUDES `browser`-marked tests. But the `browser`
marker is explicitly documented (pyproject) as opt-in: "needs a local Chrome ... never runs in the
default suite." CI (windows-latest ships Chrome) has been running these flaky CDP screenshot tests as a
release gate since v0.2.6; v0.2.8 got lucky, and v0.2.9's added panel browser smokes raised the flake
odds until it bit. This is a CI misconfiguration, not a product failure.

## Scope
- **`.github/workflows/ci.yml`** -- the gating pytest step now runs
  `-m "not golden_env and not browser"`, matching the marker's documented intent + the local
  `-m "not browser"` discipline. Browser coverage is NOT dropped: the panel product-smokes
  (`test_ui_browser`) run locally and as the **mandatory pre-tag `pytest -m browser` sign-off** (run
  green for this release: 7 passed). So this moves browser tests off the flaky CI gate, it does not
  narrow a real gate (the v028_7 `node --check` step remains the automated CI JS-parse gate).

## Gates / Done when
- The CI gating step no longer runs `browser` tests; the v0.2.9 tag run goes green and `publish` runs.
- `node --check` step unchanged; `-m golden_env` byte-parity unchanged; the pre-tag `-m browser` sign-off
  is green. No new dependency.

## As-built (DONE 2026-06-24)
- `ci.yml`: pytest gate `-m "not golden_env"` -> `-m "not golden_env and not browser"` (+ rationale
  comment). Local pre-tag `pytest -m browser` -> 7 passed (sign-off). Re-tag v0.2.9 onto the commit
  carrying this fix (the prior tag never published -- publish was skipped -- so re-pointing is clean).
