# v029_8 -- prune the job registry     release: v0.2.9 · phase: ui  (LOW)

> LOW finding: the panel's `server.bobframes_jobs` dict grows one id->Job entry per job for the life of
> the process and is never reclaimed. Bound it. Server-side only; zero new dep; no report HTML (golden
> untouched).

## Scope
- **`jobs.py`** -- `MAX_REGISTRY = 20` + `prune_registry(registry, keep=MAX_REGISTRY)`: drops the oldest
  FINISHED jobs past the cap (dict insertion order is oldest-first); never removes a running job. Safe
  for in-flight streams -- the SSE handler holds its own `Job` reference, so a pruned registry entry
  never cuts a live stream (a new stream request for a pruned id just 404s, which is correct for an old
  job).
- **`server.py`** -- `_start_job` calls `jobs.prune_registry(registry)` after inserting the new job.

## Gates / Done when
- After many jobs the registry stays at most `MAX_REGISTRY`, keeping the most recent and never dropping
  a running job (unit test).
- `node --check` green (panel.js unchanged -- standing regression); `pytest -m "not browser"` green;
  `pytest -m golden_env` byte-parity unchanged, NO golden refresh. No new runtime dependency.

## As-built (DONE 2026-06-24)
- `jobs.prune_registry` (oldest-finished-first, running-safe) + `MAX_REGISTRY=20`; `_start_job` prunes
  after inserting.
- VERIFIED: `test_ui_prune` (3) -- bounds to 20 keeping the newest; never removes a running job;
  no-op under the cap. `node --check` clean; `-m "not browser"` **427 passed / 3 deselected** (was 424
  at v029_7; +3); `-m golden_env` **5 passed BYTE-UNCHANGED, NO golden refresh**; no new dep.
