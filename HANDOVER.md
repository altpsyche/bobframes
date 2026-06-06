# HANDOVER — bobframes v0.2.6 (release-ready), continuing on a new PC

_Written 2026-06-06. Delete this file once v0.2.6 is shipped._

## TL;DR

**v0.2.6 is code-complete and RELEASE-READY.** All commits (`v0.2.6-0` … `v0.2.6-6`) are on branch
**`plan/v0.2.6`**, currently **UNPUSHED**. The only work left is the **outward / irreversible release tail**
(push → tag → PyPI), which is deliberately **gated on your explicit go-ahead**. Nothing else is pending for
0.2.6.

> First thing on the new PC: read `docs/plan/STATE.md` (the resumption anchor — `current` / `last_session` /
> `next_action`). This file is the cross-PC bootstrap; STATE is the source of truth.

## Get the new PC in sync

1. **Push the branch from the OLD PC first** (it holds the unpushed commits):
   `git push -u origin plan/v0.2.6` (pushing the *branch* is safe; it is NOT the gated tag/PyPI step).
   _Note:_ the planning file lives at `~/.claude/plans/continue-bobframes-v0-2-6-on-cheerful-eich.md` and the
   scratch proof harnesses are under `c:/tmp/` (`bf_v0265_cells.py`, `bf_v0265_diff.py`) — these are
   **machine-local and do NOT transfer**; they are scratch, not needed to ship. The commit docs under
   `docs/plan/commits/v026/` are the durable record.
2. **On the NEW PC:** `git clone` (or `git fetch && git checkout plan/v0.2.6`).
3. **Recreate the canonical env (ADR-11 — golden bakes + the `golden_env` gate require it):**
   **Python 3.12 + pyarrow 21** in the repo `.venv`. This project uses **`uv`** (the `.venv` has no `pip`):
   - `uv venv --python 3.12 .venv`
   - `uv pip install -e ".[dev]"` (or `uv sync` if a lockfile is present) — pulls pyarrow 21 + pytest.
   - Verify: `.venv\Scripts\python.exe -c "import sys,pyarrow; print(sys.version.split()[0], pyarrow.__version__)"`
     must print `3.12.x 21.0.0`. A different Python/pyarrow will **fail `-m golden_env`** (byte goldens are
     env-pinned) — that's expected off-canonical; do not "fix" by re-baking on the wrong env.
   - For the `-m browser` matrix you also need **Google Chrome** installed (the `tools/shoot.py` harness finds
     it automatically; the one `browser` test skips cleanly if Chrome is absent).

## Verify on the new PC before shipping (re-run the green gate)

All from the repo root, using the canonical `.venv` python (`PY=.venv\Scripts\python.exe`):

```
$PY -m pytest -q -m "not browser"   # expect 352 passed, 1 deselected
$PY -m pytest -q -m golden_env      # expect 5 passed  (the byte-identical HTML golden gate)
$PY -m pytest -q -m browser         # expect 1 passed  (needs Chrome)
$PY -m bobframes.cli version        # expect: bobframes 0.2.6  schema 3  pyarrow 21.0.0
$PY -m bobframes.cli lint CHANGELOG.md   # exit 0
```

Clean-wheel sanity (proves the wheel ships `reports/assets/*` and renders styled):
```
uv build --wheel                                            # -> dist/bobframes-0.2.6-py3-none-any.whl
uv venv c:/tmp/bf-wheel-venv
uv pip install --python c:/tmp/bf-wheel-venv/Scripts/python.exe dist/bobframes-0.2.6-py3-none-any.whl
c:/tmp/bf-wheel-venv/Scripts/python.exe -m bobframes.cli version   # 0.2.6
```
(The full styled-render + `[theme]`-override check was done on the old PC — see
`docs/plan/commits/v026/v026_6_closeout_ship.md` "As-built". Re-run only if you changed packaging.)

## The release tail — DO ONLY AFTER YOU DECIDE TO SHIP (outward / irreversible)

```
# 1. push the work (if not already)
git push -u origin plan/v0.2.6
# 2. (per your release flow) merge plan/v0.2.6 -> main, OR release straight from the branch
# 3. tag + push the tag
git tag v0.2.6
git push origin v0.2.6
# 4. build + upload to PyPI
uv build                       # sdist + wheel into dist/
twine upload dist/*            # needs PyPI credentials (~/.pypirc or TWINE_* env)
# 5. post-publish smoke (clean venv, from PyPI)
uv venv c:/tmp/bf-pypi-smoke
uv pip install --python c:/tmp/bf-pypi-smoke/Scripts/python.exe bobframes==0.2.6
c:/tmp/bf-pypi-smoke/Scripts/python.exe -m bobframes.cli version
```
Precedent: bobframes 0.1.0 shipped to PyPI 2026-05-31; tag `v0.2.0` -> 765a4db on main. Mirror that flow.

## What 0.2.6 contains (for the release notes / your sanity)

The whole arc since 0.2.0 (per ADR-43 there is no standalone 0.2.5): build-health one-pager (ADR-39),
`package`/shared-assets/redact (ADR-40/41), the server-side component system + token guard + preview gallery
(ADR-42), the per-frame/aggregates correctness spine, and the visual redesign + full componentization
(ADR-43/44/45, G-30, G-32). See `CHANGELOG.md` `## [0.2.6]` and `docs/plan/commits/v026/*`.

## Carry-over (NOT blocking 0.2.6 — own commits, post-ship or parallel)

- **FINDINGS R-19** — `reports/overdraw.build` `set(by_area[area])` row-order nondeterminism on real multi-RT
  data (tied sample counts iterate set-order, varies by `PYTHONHASHSEED`). Pre-existing; reconfirmed at -5
  (two same-code re-renders of real Perf disagreed on different tied-rt cells). Golden-neutral on the
  synthetic (no ties), so the fix needs a **multi-tie fixture** + a determinism regression. Fix sketch:
  `for label in sorted(set(by_area[area]))` (or a `(-n_samples, label)` sort key); audit the other
  set-iterating reports at fix time. Its own commit.
- **0.2.7 feedback report** — the visual/UX feedback you said you'd write after the redesign; lands in 0.2.7.

## House rules (don't trip these)

- **No patch-fixes (ADR-23):** root-cause or record explicitly (FINDINGS/HARDCODE row + rationale); never
  narrow a gate to go green.
- **Golden bakes ONLY on the canonical env** (py3.12/pyarrow21). `make_golden` / `make_preview_golden` /
  `make_package_golden` run as modules: `$PY -m bobframes.tests.make_golden` etc.
- **`make_parquet_golden` is NOT run** in the 0.2.6 line (no data-format change; schema stays 3).
- Work is **plan-driven**: read `docs/plan/STATE.md` first every session; do exactly the `current` commit;
  update STATE before stopping.
