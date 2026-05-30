# Changelog

All notable changes to this project are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Repo scaffold: package layout, `pyproject.toml`, plan doc set under `docs/plan/`.
- CLI dispatcher (c11): single `bobframes` binary with subcommands `ingest`, `render`, `ab`,
  `report`, `catalog`, `lint`, `check`, `serve`, `smoke`, `version`. Positional `root` (default `.`)
  across verbs; long-flag-only; exit codes 0/1/2/3/4. stdlib `logging` (INFO default,
  `--verbose` → DEBUG, `[HH:MM:SS]` lines; G-8).
- Replay script located via `importlib.resources` (c12, `bobframes.replay.replay_script_path`) so
  replay works from an installed wheel, not just an in-tree checkout.
- Reliability hardening (c03): atomic writes for `_manifest.json`, Parquet+CSV pairs, and
  `done.marker` (`.tmp` + `os.replace`, rollback on failure); process-tree kill (`taskkill /T /F`)
  when qrenderdoc replay times out; per-capture replay-failure isolation
  (`capture_status='replay_failed'` instead of aborting the whole drop); subprocess stderr now
  logged on convert-timeout and on every parse; manifest provenance fields `tool_versions`
  (renderdoccmd/qrenderdoc) and `host_info` (GPU/driver/CPU/OS/bobframes version).
- Mocked-subprocess unit tests (`bobframes/tests/test_hardening.py`) covering the hardening
  branches the GPU-less CI cannot exercise.

### Changed
- **Stable-key format upgrade:** stable keys now carry a `KEY_VERSION = 1` version byte in the hash
  input. Keys produced before c03 are not comparable with c03+ keys; rebuild affected data with
  `bobframes ingest --force`. Bump `KEY_VERSION` on any future key-derivation rule change.
- Timestamps unified to a single UTC `now_iso()` helper (`bobframes.manifest.now_iso`); the
  local-time variant in `reports/cli` was dropped.

[Unreleased]: https://github.com/mayhem-studios/bobframes/commits/main
