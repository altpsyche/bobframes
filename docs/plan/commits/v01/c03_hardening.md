# c03 — reliability hardening     release: v0.1 · phase: Safety net

## Goal
Make the ingest path crash-safe and observable: atomic writes, subprocess hygiene, replay-failure
isolation, versioned keys, single UTC timestamp, and manifest provenance. No rendered-output change.

## Depends on
[c02](c02_golden_harness.md) (parity gate must exist to prove "no output change").

## Files (symbol-anchored — no line numbers)
- `manifest.write_manifest` — atomic write (R-1)
- `parquetize._write_pair` — stage Parquet+CSV to `.tmp`, atomic rename, rollback both on either failure (R-2)
- `pipeline` done.marker write — tmp + `os.replace()` (R-3)
- `pipeline._do_parse` — save/restore `RDC_ROOT` around parse (R-5); always log stderr regardless of rc (R-7)
- `pipeline` replay loop — single capture failure → skip + manifest `capture_status='replay_failed'`, do not abort drop (R-6)
- `qrd_harness` timeout `except` — reap the **process tree** (R-4, [ADR-4](../../DECISIONS.md))
- `rdcmd` convert — log stderr tail (~400 chars) on `TimeoutExpired` before re-raise (R-8)
- `stable_keys` — add `KEY_VERSION = 1`; prepend version byte to `_sha` input (H-27 / G-11)
- `manifest` + `cli` timestamps — single `now_iso()` UTC helper; drop the local-time variant (H-28)
- `manifest` (ingest) — add `tool_versions` (`renderdoccmd --version`, `qrenderdoc --version`) + `host_info` (GPU/driver via `Get-CimInstance Win32_VideoController`, CPU, OS, bobframes version) (G-6, G-7)
- `catalog._per_capture_row_counts` — **NO CHANGE.** R-9 withdrawn ([ADR-3](../../DECISIONS.md)); `+= 1` per row is correct.

## Changes
Apply each fix above. For R-4, prefer a Win32 job object with `JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE`,
or `taskkill /T /F /PID` as the simpler route — **not** a bare `proc.kill()` (misses grandchildren).
Add a **mocked-subprocess unit test** ([ADR-6](../../DECISIONS.md)) driving the kill-on-timeout,
replay-skip, and tmp→`os.replace` atomic-rename branches with fakes — CI has no GPU, so this is the
only automated coverage these branches get in v0.1.

## Done when
- New `tests/unit_hardening.py` (mocked subprocess) green: timeout kills tree, replay failure skips +
  records status, atomic writes leave no partial file on simulated mid-write crash.
- Golden parity + schema + determinism green (provenance fields are stubbed in synthetic per c02, so
  output stays byte-identical).
- `KEY_VERSION` documented in CHANGELOG (key-format upgrade note).

## Rollback
Revert per-file; each fix is independent.

## Closes
R-1, R-2, R-3, R-4, R-5, R-6, R-7, R-8 · H-27, H-28 · G-6, G-7, G-11.  (R-9 explicitly **not** a fix.)
