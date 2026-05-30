<!-- ============================================================================
  SUPERSEDED — provenance only. Do not edit. Do not execute from this file.
  This is the original monolith that the plan doc set was carved from.
  The live plan lives in docs/plan/ — start at INDEX.md, then STATE.md.
  Note: §-numbers and "commit N" references BELOW are this file's own internal
  history; the live numbering is cNN (see ../plan/MIGRATION.md). Corrections from
  the review (R-9 withdrawn, R-4 process-tree kill, §21.3 drift-test rewrite,
  stale names) were applied here before the carve and are reflected in DECISIONS.md.
============================================================================ -->

# BobFrames — extract `_analysis/` → standalone CLI  (SUPERSEDED — see [INDEX.md](INDEX.md))

## Context

`_analysis/` Python pipeline lives embedded in one project tree at `c:/Users/vsiva/Downloads/RDC mainline r110565 25-05-2026/`. Invoked via `python -m _analysis.run --root .`. Goal this session: lift it out, package as installable CLI `bobframes`, runnable against any folder of RenderDoc captures. Single-tool ingestion path (Windows + RenderDoc required); no cross-platform fallback in v1; no backwards-compat shim — hard rename.

## 1. Tool identity

| Field | Value |
|---|---|
| Display name | BobFrames |
| PyPI package | `bobframes` |
| Import name | `bobframes` |
| Binary | `bobframes` (single, subcommands) |
| Elevator | "RenderDoc capture pipeline: ingest, analyze, render. Folder of `.rdc` in → `_data/` + `_reports/` out." |
| License | MIT |
| Python | `>=3.10,<3.15` (qrenderdoc embeds 3.10; host on 3.14) |
| Platform | **Windows only in v1**. macOS/Linux deferred. |

PyPI availability check at execution time (not now):
```
pip index versions bobframes
curl -s https://pypi.org/pypi/bobframes/json
```
Fallbacks if taken: `bob-frames`, `bobframescope`.

## 2. Package layout

Flat layout (no `src/`). Same on disk as installed; one-to-one with `_analysis/`.

```
bobframes/                          # repo root
  pyproject.toml
  README.md
  CHANGELOG.md
  LICENSE                           # MIT
  .github/workflows/ci.yml
  bobframes/
    __init__.py                     # from ._version import __version__
    _version.py                     # __version__ = "0.1.0"
    cli.py                          # NEW: argparse dispatcher
    pipeline.py                     # WAS run.py
    errors.py                       # NEW: ToolNotFound, PipelineError, exit_code map
    config.py                       # NEW: TOML loader, tool resolution
    schemas.py                      # frozen v3
    paths.py                        # frozen (16 public funcs)
    lint.py                         # frozen
    discovery.py
    rdcmd.py                        # tool discovery via config
    qrd_harness.py                  # tool discovery via config
    catalog.py
    global_entities.py
    parquetize.py
    derive_post_merge.py
    manifest.py
    query_examples.py
    resource_labels.py
    stable_keys.py
    parsers/
      __init__.py
      parse_init_state.py           # callable via `python -m bobframes.parsers.parse_init_state`
      derive_program_transitions.py
    replay/
      __init__.py                   # NEW: replay_script_path() via importlib.resources
      replay_main.py                # frozen; schema duplication preserved
    derives/
      __init__.py
      pass_class_breakdown.py
      texture_usage.py
    html/
      __init__.py
      template.py                   # per-drop browser + root index (stays here)
    reports/
      __init__.py
      cli.py                        # run_report dispatch (kept)
      base.py  chrome.py  formatters.py  delta.py
      discovery.py  cache.py
      orchestrator.py
      ab.py
      _dashboard.py                 # underscore kept (no churn)
      draws_by_class.py  trend_table.py  instancing_opportunities.py
      pass_gpu.py  shader_hotlist.py  overdraw.py
    probes/
      __init__.py
      whatif.py                     # kept; manual qrenderdoc-side; not a CLI verb
    tests/
      __init__.py
      smoke.py                      # rewritten — no Chor bazar hardcoding
      data/synthetic/               # tiny synthetic _data/ tree (~500KB)
```

## 3. `pyproject.toml`

```toml
[build-system]
requires = ["hatchling>=1.25"]
build-backend = "hatchling.build"

[project]
name = "bobframes"
dynamic = ["version"]
description = "RenderDoc capture pipeline: ingest, analyze, render."
readme = "README.md"
requires-python = ">=3.10,<3.15"
license = { text = "MIT" }
authors = [{ name = "Siva Subramanyam", email = "sivasubramanyam@mayhem-studios.com" }]
keywords = ["renderdoc", "gpu", "profiling", "parquet"]
classifiers = [
  "Development Status :: 3 - Alpha",
  "Environment :: Console",
  "License :: OSI Approved :: MIT License",
  "Operating System :: Microsoft :: Windows",
  "Programming Language :: Python :: 3.10",
  "Programming Language :: Python :: 3.11",
  "Programming Language :: Python :: 3.12",
  "Programming Language :: Python :: 3.13",
  "Programming Language :: Python :: 3.14",
  "Topic :: Software Development :: Debuggers",
  "Topic :: Multimedia :: Graphics",
]
dependencies = [
  "pyarrow>=17,<22",
]

[project.optional-dependencies]
dev = ["build", "twine", "hatchling"]

[project.scripts]
bobframes = "bobframes.cli:main"

[project.urls]
Homepage  = "https://github.com/mayhem-studios/bobframes"
Issues    = "https://github.com/mayhem-studios/bobframes/issues"
Changelog = "https://github.com/mayhem-studios/bobframes/blob/main/CHANGELOG.md"

[tool.hatch.version]
path = "bobframes/_version.py"

[tool.hatch.build.targets.wheel]
packages = ["bobframes"]

[tool.hatch.build.targets.wheel.force-include]
"bobframes/replay/replay_main.py" = "bobframes/replay/replay_main.py"
"bobframes/tests/data" = "bobframes/tests/data"

[tool.hatch.build.targets.sdist]
include = ["bobframes/", "README.md", "CHANGELOG.md", "LICENSE", "pyproject.toml"]
exclude = ["**/__pycache__", "**/*.pyc"]
```

Hatchling chosen: single-file dynamic version, no `setup.py`, native force-include for `replay_main.py` (importlib.resources needs real on-disk path).

## 4. CLI surface

Single binary, argparse subparsers. `<root>` is **positional, default `.`**, consistent across all verbs. Long-flag-only (no `-r`/`-a`).

| Verb | Args | Behavior | Example |
|---|---|---|---|
| `ingest` | `[root=.] [--area X] [--label Y] [--capture N] [--force] [--workers K] [--pixel-grid 4] [--render-only] [--verbose]` | Full pipeline: export, parse, replay, parquetize, derive, manifest, commit, catalog, render | `bobframes ingest .` |
| `render` | `[root=.] [--area X] [--label Y]` | Render-only; rebuild HTML + catalog from existing Parquet | `bobframes render .` |
| `ab` | `[root=.] --baseline-label X --compare-label Y [--baseline-date D] [--compare-date D]` | All 6 reports for one drop pair under `_reports/ab/<pair>/` | `bobframes ab . --baseline-label r110565 --compare-label r110600` |
| `report` | `[root=.] <name>` (name ∈ draws-by-class, trend, instancing, pass-gpu, shader, overdraw, dashboard) | Build one named report | `bobframes report . shader` |
| `catalog` | `[root=.]` | Rebuild `_data/_catalog.parquet` only | `bobframes catalog .` |
| `lint` | `<file>...` | Lint HTML/MD against banlist | `bobframes lint _reports/*.html` |
| `check` | `[--write-config]` | Print resolved paths for `renderdoccmd` + `qrenderdoc`; non-zero on missing. `--write-config` emits stub config | `bobframes check` |
| `version` | (none) | `bobframes 0.1.0  schema 3  pyarrow 17.0.0` | `bobframes version` |
| `serve` | `[root=.] [--port 8000] [--bind 127.0.0.1]` | `http.server`-based static preview | `bobframes serve .` |
| `smoke` | `[--data DIR]` | End-to-end against `--data` (defaults to bundled synthetic) | `bobframes smoke` |

Not exposed: `probes/whatif.py` (manual qrenderdoc-side; documented in README "Advanced"), no `init`/`config` verb (config optional; `check --write-config` covers it).

**Defaults**:
- `bobframes` (no args) → `--help`, exit 0.
- `bobframes <verb>` → defaults `root=.`.
- ANSI color: **off by default; auto-enable when `sys.stdout.isatty()` and `NO_COLOR` unset**. No `colorama` dep — raw ANSI; Win10+ conhost handles.
- Progress: keep `[HH:MM:SS] message` log lines. No bars/spinners.
- Logging: stdlib `logging`, level INFO default, `--verbose` per-subparser → DEBUG.

**Exit codes**:
- `0` success
- `1` pipeline/build failure (lint hit, replay nonzero, schema mismatch)
- `2` user error (argparse-native)
- `3` external tool missing
- `4` interrupted (Ctrl+C, timeout)

## 5. External tool discovery

Single resolver in `bobframes/config.py`. Both `rdcmd.py` and `qrd_harness.py` call into it.

```
resolve_tool(name)  where name ∈ {"renderdoccmd", "qrenderdoc"}
  1. env var      BOBFRAMES_RENDERDOCCMD / BOBFRAMES_QRENDERDOC
                  (legacy RENDERDOCCMD / RENDERDOC_QRENDERDOC accepted with one-shot deprecation log)
  2. config file  [tools] section, key = name
  3. PATH         shutil.which(name + ".exe")
  4. known paths  Windows install paths (below)
  5. raise        bobframes.errors.ToolNotFound  (exit code 3)
```

**Known install paths (Windows)**:
- `C:/Program Files/Arm/Arm Performance Studio 2026.2/renderdoc_for_arm_gpus/{renderdoccmd,qrenderdoc}.exe`
- `C:/Program Files/RenderDoc/{renderdoccmd,qrenderdoc}.exe`
- `%LOCALAPPDATA%/Programs/RenderDoc/{renderdoccmd,qrenderdoc}.exe`

**Error message (exit 3)**:
```
bobframes: renderdoccmd not found.

Tried (in order):
  $BOBFRAMES_RENDERDOCCMD                                      (unset)
  config: tools.renderdoccmd in C:\Users\you\AppData\...       (unset)
  PATH                                                          (not on PATH)
  C:\Program Files\Arm\Arm Performance Studio 2026.2\...        (not present)
  C:\Program Files\RenderDoc\renderdoccmd.exe                   (not present)

Fix one of:
  $env:BOBFRAMES_RENDERDOCCMD = 'C:\path\to\renderdoccmd.exe'
  bobframes check --write-config        # writes a stub config
  Install RenderDoc: https://renderdoc.org/builds
```

## 6. Config + state

**Config file** (optional; defaults work without one):

Lookup precedence — first found wins, no merging:
1. `$BOBFRAMES_CONFIG`
2. `<root>/.bobframes.toml` (per-project)
3. `%APPDATA%/bobframes/config.toml` (Windows-native)

Format (TOML via stdlib `tomllib`):
```toml
schema_version = 1                  # config schema (not data schema)

[tools]
renderdoccmd = "C:/Program Files/Arm/.../renderdoccmd.exe"
qrenderdoc   = "C:/Program Files/Arm/.../qrenderdoc.exe"

[pipeline]
workers     = 4
pixel_grid  = 4
keep_stage  = false

[render]
ansi_color  = "auto"                # "auto" | "always" | "never"
```

**State / cache**:
- `_reports/_cache/*.parquet` — per-project (unchanged).
- No per-user cache dir.
- Env var renames (legacy accepted one release):
  - `RDC_KEEP_STAGE` → `BOBFRAMES_KEEP_STAGE`
  - `RDC_PIXEL_GRID` → `BOBFRAMES_PIXEL_GRID`
  - `RDC_ROOT` → **eliminated**; pass `--project-root` as explicit CLI arg to `parse_init_state`.
  - `RDC_INSIDE_ARGS` → **kept verbatim** (qrenderdoc ↔ harness wire protocol).

Precedence rule: CLI flag > env var > config file > built-in default. Documented in `bobframes check` output.

## 7. Distribution

PyPI primary; GitHub Releases mirror wheel + sdist.

**One-time setup**:
- Reserve `bobframes` on PyPI; upload `0.0.0` placeholder. Get API token. Store as GH secret `PYPI_API_TOKEN`.
- Create GH repo `mayhem-studios/bobframes`.

**Per-release flow**:
```
# bump bobframes/_version.py + CHANGELOG.md
git tag v0.1.0
git push origin v0.1.0
```

`.github/workflows/ci.yml` job `publish` on `v*` tag:
1. `python -m build` → `dist/bobframes-0.1.0-py3-none-any.whl` + `.tar.gz`
2. `twine upload dist/*`
3. Create GH Release with two artifacts + CHANGELOG section as body.

End-user install:
```
pipx install bobframes              # recommended; isolated venv
pip install --user bobframes        # alternative
```

No conda-forge, no Homebrew tap, no self-update mechanism. `pipx upgrade bobframes` is the answer.

## 8. Versioning

- **SemVer 2.0**:
  - PATCH: bug fix; no CLI flag change, no output change.
  - MINOR: new verb, new optional flag, new optional column in non-frozen output.
  - MAJOR: breaking CLI rename, output layout change, dropped Python version, schema bump.
- **`SCHEMA_VERSION`** lives in `bobframes.schemas`, separate int. Bumps independently. Rule: any `SCHEMA_VERSION` bump forces a `bobframes` MAJOR (pre-1.0 exception: forces MINOR; documented in CHANGELOG).
- **`bobframes version`** prints both: `bobframes 0.1.0  schema 3  pyarrow 17.0.0`.
- **Manifest compatibility** (`_manifest.json.schema_version`):
  - `render`/`catalog`/`ab` refuse to operate when `manifest.schema_version != schemas.SCHEMA_VERSION`. Exit 1; fix is `bobframes ingest --force`.
  - `ingest --force` blows away and rebuilds.
- **Deprecation cadence**: rename/removal lives one MINOR with `DeprecationWarning`, gone in next MINOR (0.x) or next MAJOR (1.0+).

## 9. Portability + path audit

| File | Change |
|---|---|
| `bobframes/__init__.py` | `from ._version import __version__` |
| `bobframes/_version.py` | NEW: `__version__ = "0.1.0"` |
| `bobframes/pipeline.py` (was `run.py`) | L143: `'-m', '_analysis.parsers.parse_init_state'` → `'-m', 'bobframes.parsers.parse_init_state'`. L149/166: drop `RDC_ROOT` env dance; pass `--project-root` as explicit CLI arg. L183: replace `os.path.join(project_root, '_analysis', 'replay', 'replay_main.py')` with `bobframes.replay.replay_script_path()`. L232/329/276: rename `RDC_PIXEL_GRID`/`RDC_KEEP_STAGE` → `BOBFRAMES_*` (legacy fallback). |
| `bobframes/replay/__init__.py` | NEW: `replay_script_path()` returns real on-disk path via `importlib.resources.files('bobframes.replay').joinpath('replay_main.py')`. For zip-import safety, wrap in `as_file()` context manager (extracts to temp if zipped). |
| `bobframes/rdcmd.py` | Replace `find_renderdoccmd()` body with `config.resolve_tool('renderdoccmd')`. Drop hardcoded path constant. |
| `bobframes/qrd_harness.py` | Same as rdcmd. Keep `_SEP` + `RDC_INSIDE_ARGS` wire protocol unchanged. |
| `bobframes/replay/replay_main.py` | **No code change.** Schema column tuples remain duplicated by design (qrenderdoc-side import unreliable). Add top-of-file comment citing policy. Host-side parquetize verifies headers against `schemas.expected_columns()` — drift caught at merge. |
| `bobframes/probes/whatif.py` | No code change; README documents new path `python -m bobframes.probes.whatif` (run inside qrenderdoc). |
| `bobframes/tests/smoke.py` | **Full rewrite.** Eliminate `AREA='Chor bazar'`, `DROP_LABEL='r110565'`, `DROP_DATE='2026-05-27'`, `__file__`-walked ROOT. New shape: takes `--data DIR`; defaults to bundled `bobframes/tests/data/synthetic/`. When `--data` absent, runs render-only against synthetic Parquet (no `.rdc`, no qrenderdoc needed). When `--data` given, full ingest using `bobframes.discovery.find_drops` to auto-select area + latest drop. |
| `bobframes/reports/cli.py` | L82: `prog=f'_analysis.reports.{module_name}'` → `f'bobframes.reports.{module_name}'`. Positional `root` default `.` (matches §4). |
| `bobframes/reports/ab.py` | L40: prog string update. Change `--root` flag to positional default `.` to align with §4 (argparse `--root` accepted as hidden alias for one release). |

## 10. Backwards-compat

**Decision: hard rename, no shim.** (User-selected.)

- `_analysis/` deleted entirely at commit 6.
- `python -m _analysis.run` → `ModuleNotFoundError` after install. Users must switch to `bobframes ingest`.
- README "Migrating from `_analysis`" section maps old commands → new:
  ```
  python -m _analysis.run --root . --area X --label Y
    → bobframes ingest . --area X --label Y
  python -m _analysis.reports.ab --root . --baseline-label X --compare-label Y
    → bobframes ab . --baseline-label X --compare-label Y
  python -m _analysis.lint <file>
    → bobframes lint <file>
  python -m _analysis.tests.smoke
    → bobframes smoke
  ```
- Existing project tree gets `_analysis/` deleted in the migration commit. The repo containing this CLI_PROMPT.md becomes a sample data folder consumed by `bobframes`, not a Python package host.

## 11. Testing strategy

| Tier | What | Where | When |
|---|---|---|---|
| Unit | lint banlist; schema dtype inference; path helpers; discovery regex; stable_keys | `bobframes/tests/unit_*.py` (new) | `pytest` local + CI per push |
| Render smoke | render-only against bundled synthetic `_data/` | `bobframes smoke` (no `--data`) | CI per push |
| Full smoke | ingest + render against real `.rdc` corpus | `bobframes smoke --data <path>` | Manual / nightly; needs Windows + RenderDoc |
| Schema regression | every parquet's columns match `schemas.expected_columns(stem)` exactly | inside `smoke.py` | Both smoke tiers |
| Lint regression | every emitted HTML passes `lint.lint_file` | inside report build (already enforced) | Both smoke tiers |

**CI matrix**: `{windows-latest} × {3.10, 3.12, 3.14}` for unit + render-smoke. Full smoke only on self-hosted Windows runner with Arm Performance Studio (deferred to v0.2; v0.1 ships without).

**Test corpus distribution**: not bundled (size). README documents "download from internal share" with SHA256. Synthetic bundled corpus is ~500KB, lives at `bobframes/tests/data/synthetic/`, mimics SCHEMA_VERSION=3 output of a real ingest.

## 12. Cross-platform

**v1 is Windows-only.** Documented in README, classifier, error message.

- `bobframes check` on non-Windows: exit 3 with message `bobframes v1 is Windows-only (qrenderdoc replay requirement). Track GH issue #N for Linux/macOS support.`
- `pyproject.toml` classifier `Operating System :: Microsoft :: Windows` only.
- No `--no-replay` flag; no static-only mode. v0.2+ may revisit.
- Path separators: code uses `os.path.join` everywhere; `paths.drop_dir_rel` already normalizes via `.replace('\\', '/')` for catalog storage. No change.

## 13. Documentation

`README.md` outline:

```
# BobFrames
One-line pitch.

## Requirements
- Windows 10+
- Python 3.10+
- RenderDoc 1.x+ (or Arm Performance Studio with renderdoccmd + qrenderdoc)

## Install
  pipx install bobframes
  bobframes check                          # verify RenderDoc tools found

## Quickstart
  cd C:\path\to\captures
  bobframes ingest .                       # ~5min/drop, ~10 captures
  bobframes serve .                        # http://127.0.0.1:8000

## Subcommands
  table from §4

## External tools
  RenderDoc requirement + install link + config file section

## Output layout
  ASCII tree from paths.py docstring

## Migrating from _analysis
  command map from §10

## Troubleshooting
  - renderdoccmd not found        → §5 error message + fixes
  - qrenderdoc hangs               → check Arm vs vanilla RenderDoc; timeout; retry
  - lint fails on render           → which file/line, edit chrome.py
  - schema_version mismatch        → bobframes ingest --force
  - permission denied on _data     → close qrenderdoc, retry

## Advanced
  - Custom probes (probes/whatif.py pattern; run inside qrenderdoc)
  - A/B workflow
  - Config file
  - Programmatic API: `from bobframes import pipeline, schemas, paths`
```

`CHANGELOG.md`: Keep-a-Changelog format; section per release; link to GH compare view.

## 14. Migration plan (independently shippable commits)

Each commit leaves working state. Commit 8 is the disruptive rename (do on quiet day). Commits 1-7 keep `_analysis` name; hardening + extraction happens in-tree first; rename is atomic.

**De-hardcoding scope: v0.1 now absorbs all P0/P1 items from §20** (per user request). Strategy: bundle TOML config files inside the wheel as defaults; current UE+Arm behavior preserved byte-identically. Power users override via per-project `.bobframes.toml`. **Every commit verified by golden-snapshot parity** (see §21 — synthetic `_data/` renders to byte-identical HTML before and after each commit).

1. **chore: add `__version__` to `_analysis/__init__.py` + `_version.py`** — empty file gains version; zero behavior change.
2. **test: install golden-snapshot harness** — bundle synthetic `_data/` (~500KB) + frozen expected HTML output under `_analysis/tests/data/golden/`. New `_analysis/tests/parity.py` re-renders against synthetic and diffs against golden; CI fails on mismatch. **This guardrail enables every subsequent refactor without regression risk.** Includes schema regression assertions (every parquet's columns ↔ `schemas.expected_columns()`) and determinism check (render twice; diff must be empty).
3. **fix: reliability hardening pass** (P0 from §17):
   - `manifest.py`: atomic write `.tmp` → `os.replace()`.
   - `parquetize.py`: Parquet + CSV pair staged to `.tmp`, atomic rename, rollback both on either failure.
   - `run.py:285`: `done.marker` tmp + `os.replace()`.
   - `run.py:166`: save/restore `RDC_ROOT` around `_do_parse`.
   - `qrd_harness.py:73,86`: on `TimeoutExpired`, reap the whole **process tree** (`taskkill /T /F /PID` or a Win32 job object). `subprocess.run(timeout=)` already kills the *direct* child before raising — the residual risk is qrenderdoc's GPU/replay grandchildren, which `run()` does not reap and which hold file locks for the next run.
   - `rdcmd.py:46`: capture + log stderr on timeout.
   - `run.py:198`: single capture replay failure → skip + manifest `capture_status='replay_failed'`.
   - ~~`catalog.py:83`: `+= 1` → `+= t.num_rows`.~~ **WITHDRAWN (false positive — see R-9):** `_per_capture_row_counts` iterates the full per-row `capture` column, so `+= 1` per row is already the correct per-capture row count. `+= t.num_rows` would over-count. No change.
   - `run.py:155`: always log stderr regardless of returncode.
   - `stable_keys.py`: add `KEY_VERSION = 1`; prepend version byte to hash input (H-27).
   - Single `now_iso()` UTC helper; remove `cli.py:16-17` local-time variant (H-28).
4. **refactor: centralize file/dir literals in `paths.py`** (H-18, H-19) — new module constants `DATA_DIR='_data'`, `REPORTS_DIR='_reports'`, `CACHE_DIR='_cache'`, `STAGE_DIR='_stage'`, `TMP_SUFFIX='_tmp'`, `DRILL_DIR='drill'`, `AB_DIR='ab'`, `MANIFEST_NAME='_manifest.json'`, `DONE_MARKER='done.marker'`, `INDEX_HTML='index.html'`. All other modules import from there. Pure rename; parity test must pass.
5. **refactor: derive table/entity lists from `schemas.TABLES`** (H-8 through H-11):
   - `global_entities.py:33-40`: replace `_ENTITY_TABLES` literal with `schemas.entity_tables()` helper.
   - `catalog.py:27-39`: replace `_CATALOG_TABLE_KEYS` with `tuple(schemas.TABLES.keys())`.
   - `html/template.py:27-39`: move `_CATEGORY_MAP` to `schemas.TABLES` as `category` field per table entry; template reads from schema.
   - `reports/__init__.py`: new `ALL_REPORTS = (...)` exported once; `orchestrator.py` and `ab.py` import from there. Future-proofs for auto-discovery (M-1, M-2).
6. **refactor: introduce `_analysis.config.resolve_tool()` + `_analysis.errors`** — new modules; `rdcmd.py` + `qrd_harness.py` call into resolver; legacy env-var names still accepted. **`resolve_tool()` glob-fallback** for H-7: `glob.glob('C:/Program Files/Arm/Arm Performance Studio */renderdoc_for_arm_gpus/{tool}.exe')`, pick latest by directory-name sort. Same for vanilla RenderDoc paths.
7. **feat: TOML-driven config layer** (consolidates H-12, H-13, H-14, H-16, H-17, H-21, H-22, H-23, H-30):
   - `bobframes/config.py` gains full TOML loader returning a dataclass.
   - Defaults bundled at `bobframes/_default_config.toml` (full schema from §20); user `.bobframes.toml` merges on top.
   - Wire: timeouts (`pipeline.replay_timeout_s`, `pipeline.convert_timeout_s`), lint extras (`lint.extra_banned`), scoring weights (`scoring.complexity.*`), formatting limits (`formatting.id_short_n`, `text_trunc_max`), bar threshold (`layout.bar_label_min_pct`), delta format (`formatting.delta_fmt`), drop-folder regex (`discovery.drop_folder_regex`).
   - `derive_post_merge.py:250-259` (complexity weights), `formatters.py:43,62,74` (trunc lengths), `delta.py:34,118` (format + threshold), `discovery.py:18` (regex), `rdcmd.py:31` + `qrd_harness.py:39` (timeouts), `lint.py:16-31` (banlist) all read from config singleton instead of literals.
   - **Parity gate**: defaults must reproduce current behavior byte-identically (golden snapshot test).
8. **feat: design tokens TOML** (H-15, H-20 per §18 Track A) — `bobframes/reports/design_tokens.toml`; `chrome.py` reads via `tomllib`, emits `:root` CSS block. Includes layout dims (bar heights, grid widths, sparkline `60x14`). `formatters.py:9` `_BANNED_CHROME_CHARS` moved to `[lint.chrome_banned_chars]` regex list. Add `bobframes preview` verb emitting `_chrome_preview.html`.
9. **feat: engine-agnostic classifier (H-1, H-2, H-3, H-5)**:
   - New `bobframes/derives/classifier.py` loads `bobframes/derives/draw_classifier.toml`. Schema:
     ```toml
     [meta]
     preset = "ue"                # name of bundled preset
     class_order = ["opaque", "prepass", "shadow", "translucent",
                    "additive", "decal", "ui", "postprocess", "other"]

     frame_prefix_regex = "^Frame\\s+\\d+/?"

     [[draw_class]]
     pattern = "(?i)shadow"
     class   = "shadow"

     [[draw_class]]
     pattern = "(?i)prepass|depthonly"
     class   = "prepass"
     # ... all 9 current rules transcribed verbatim from _classify_draw

     [pass_strip]
     prefixes = ["FRDGBuilder::Execute", "MobileSceneRender"]
     contains_remove = ["/Engine/EngineMaterials"]
     fname_collapse = true
     ```
   - `derive_post_merge.py:35-62` `_classify_draw()` replaced by 10-line classifier walker reading rules.
   - `formatters.py:84-114` `pass_short()` reads `[pass_strip]` rules.
   - `chrome.py:1081-1087` `DRAW_CLASSES` derived from `classifier.class_order` at import time (single source of truth).
   - **Ship UE preset = byte-identical to today**. New `bobframes/derives/presets/{ue,unity,godot,custom-template}.toml` shipped; user picks via `[classifier] preset = "unity"`.
   - Counter name aliases (H-4): `[counters] gpu_duration_aliases = ["GPU Duration", "GPU Time", ...]`; `pass_class_breakdown.py:46` walks aliases until one resolves.
   - **Parity gate**: synthetic golden must reproduce current draw_class column byte-identically.
10. **refactor: rename env vars `RDC_*` → `BOBFRAMES_*` with legacy fallback** — touches `run.py`, `qrd_harness.py`, `replay_main.py`. Keep `RDC_INSIDE_ARGS` (wire protocol).
11. **feat: add `_analysis/cli.py` dispatcher; install `[project.scripts]`** — wire `pyproject.toml`; CLI verbs from §4 callable as `python -m _analysis.cli`. `python -m _analysis.run` still works.
12. **refactor: replay script discovery via `importlib.resources`** — `run.py:183` replaced; `replay/__init__.py` gains `replay_script_path()`.
13. **test: CI replay-schema drift guardrail (H-6)** — new test parses literal column tuples out of `replay/replay_main.py` and diffs against `schemas.TABLES`. Build fails on mismatch. Documents the duplication constraint while making drift immediately visible.
14. **refactor: rename `_analysis` → `bobframes` (atomic)** — `git mv _analysis bobframes`; update all imports + `-m _analysis.parsers.parse_init_state` literal + all `prog=` strings. Delete `_analysis/` tree; no shim. Binary name `bobframes` installable.
15. **feat: rewrite `tests/smoke.py`** — `--data` flag, defaults to bundled synthetic; add unit tests for `stable_keys`, `schemas.expected_columns`, `discovery.parse_single_drop_arg` (NOT `_parse_drop_dirname` — that name does not exist) + `discovery.find_drops`, `classifier.classify()`, config-loader precedence.
16. **feat: report-quality enhancements** (data extraction stays identical; report polish only — see §21 for quality bar):
   - Empty-state messages on every report (no draws → friendly message, not empty table).
   - Missing-column tolerance in cache.py (R-2 fix): graceful degradation with warning, not index error.
   - Sparkline null-gap rendering (already in delta.py:131-167) — verify on synthetic with null entries; add to golden.
   - Add manifest `tool_versions` block (G-6, G-7): renderdoccmd `--version`, qrenderdoc `--version`, GPU model + driver (Windows: `Get-CimInstance Win32_VideoController`), CPU + OS, bobframes version. Recorded at ingest; surfaced in `_dashboard.py` footer.
17. **feat: CI workflow** `.github/workflows/ci.yml` — unit + render-smoke + golden parity + schema regression + replay drift on every push; publish on `v*` tag.
18. **chore: README + CHANGELOG + LICENSE**.
19. **release: tag v0.1.0** → CI publishes to PyPI + GH Release.

Commits 2 (golden harness) and 3 (hardening) ship first so the legacy in-tree install gets safety net + reliability immediately. Commits 4-9 are the de-hardcoding wave; each guarded by parity test. Commit 14 is the atomic rename; commits 15-19 finalize.

## 15. Risks & mitigations

| Risk | Mitigation |
|---|---|
| `bobframes` name taken on PyPI | Verify before commit 6; fall back to `bob-frames` or `bobframescope`. |
| Replay schema duplication drifts from `schemas.py` | Host-side parquetize verifies headers against `schemas.expected_columns()`; mismatch fails ingest with exact column diff. Already enforced. Document duplication policy in `replay_main.py` top comment. |
| `importlib.resources` path breaks under zipped wheels | Hatchling produces non-zip wheels by default. Safety net: `replay_script_path()` uses `as_file()` context manager — extracts to temp if zipped. |
| `pyarrow` major breaks column-by-column writes | Pin `pyarrow>=17,<22` (4-major window). CI matrix tests pyarrow 17 + latest. Bump bound per release. |
| qrenderdoc subprocess hangs (Windows handle inheritance) | Already mitigated: writes to file handle directly, not PIPE (`qrd_harness.py` comment block). Keep unchanged. |
| Old `python -m _analysis.run` invocations in shell history fail | Hard error after migration; README "Migrating" section provides command map. User chose this tradeoff. |
| Config file format diverges from CLI flags | One-way precedence: CLI > env > config > default. Documented in `bobframes check` output. |
| Atomic-rename commit (commit 6) bisects badly | Single commit, no half-state. Reviewer checks: all `from ._analysis` removed, `_analysis/` directory gone, `pyproject.toml` exists, `bobframes check` runs. |
| Non-Windows user installs from PyPI | `bobframes check` exits 3 with Windows-only message immediately. Classifier limits visibility to Windows. |

## 16. Verification

Sequential post-install sanity checks. Each one command; objective pass criterion.

```
pipx install bobframes                              # exit 0
bobframes version                                    # bobframes 0.1.0  schema 3  pyarrow X.Y.Z
bobframes check                                      # exit 0; prints resolved paths
bobframes smoke                                      # exit 0; render-only against synthetic
cd "C:\path\to\captures"                             # any folder with <area>/<drop>/*.rdc
bobframes ingest . --area "Chor bazar" --label r110565 --force
                                                     # exit 0
                                                     # _data/Chor bazar/2026-05-27_r110565/*.parquet exist
                                                     # _reports/drill/Chor bazar/2026-05-27_r110565/index.html exists
                                                     # index.html at root
bobframes render .                                   # exit 0; same outputs regenerated, faster
bobframes serve .                                    # opens; manual: visit /index.html + one drill page
```

Negative checks:
```
$env:BOBFRAMES_RENDERDOCCMD = 'C:/nope.exe'; bobframes check    # exit 3, error from §5
bobframes ingest /nonexistent                                    # exit 2, argparse error
```

Schema-mismatch check (after manually editing a `_manifest.json.schema_version` to 99):
```
bobframes render .                                   # exit 1; message points to `bobframes ingest --force`
```

## Critical files

- [`_analysis/run.py`](_analysis/run.py) → `bobframes/pipeline.py`. L143 subprocess literal + L183 replay path are load-bearing.
- [`_analysis/qrd_harness.py`](_analysis/qrd_harness.py) — tool discovery refactor; `RDC_INSIDE_ARGS` wire kept.
- [`_analysis/rdcmd.py`](_analysis/rdcmd.py) — tool discovery refactor mirror.
- [`_analysis/replay/replay_main.py`](_analysis/replay/replay_main.py) — frozen; resolved via `importlib.resources` from new `bobframes/replay/__init__.py`.
- [`_analysis/tests/smoke.py`](_analysis/tests/smoke.py) — full rewrite; eliminate hardcoded `Chor bazar` / `r110565` / `2026-05-27`; gain `--data` + synthetic fallback.
- [`_analysis/reports/cli.py`](_analysis/reports/cli.py) — prog string + positional `root` alignment.
- [`_analysis/reports/ab.py`](_analysis/reports/ab.py) — prog string + `--root` flag → positional with hidden alias.

## Reused functions (no duplication)

- `_analysis.config.resolve_tool()` (NEW; replaces inline discovery in rdcmd + qrd_harness).
- `_analysis.reports.cli.run_report(build_fn, module_name)` — already exists; reused by all 6 report verbs and `bobframes report <name>`.
- `_analysis.reports.orchestrator.render_all_reports(root, log)` — already exists; reused by `bobframes render`.
- `_analysis.discovery.find_drops(...)` — reused by new `smoke.py` and all verbs that accept `--area`/`--label`.
- `_analysis.lint.lint_file(path)` — reused by `bobframes lint` and inline by report builds.
- `_analysis.schemas.expected_columns(stem)` — reused by parquetize verification and new smoke schema assertions.
- `_analysis.paths.*` (16 funcs) — frozen; reused throughout. Treat as public API surface (`bobframes.paths`).

---

## 17. Code Review Findings

Findings collected by review pass across pipeline core, reports + designer surface, and supporting modules. P0 = ship-blocker; folded into commit 2 of §14. P1 = should land in v0.1.x. P2 = backlog post-1.0.

### Reliability (P0 — atomic writes + subprocess hygiene)

| ID | File:line | Finding | Fix |
|---|---|---|---|
| R-1 | `manifest.py:46-50` | `_manifest.json` written non-atomically; crash mid-write corrupts; catalog rebuild skips drop silently → data loss invisible | Write to `.tmp` then `os.replace()` |
| R-2 | `parquetize.py:203-207` | Parquet + CSV pair written sequentially; Parquet committed even if CSV write fails (split-brain pair) | Stage both to `.tmp`, replace atomically; rollback both on either failure |
| R-3 | `run.py:285` | `done.marker` bare-write after commit; crash → re-process duplicate next run | tmp + `os.replace()` |
| R-4 | `qrd_harness.py:69,83` | `TimeoutExpired` caught; `subprocess.run` already kills the **direct** child, but qrenderdoc's GPU/replay **grandchildren** survive and hold file locks for the next run | Reap the process **tree**: `taskkill /T /F /PID` (Windows) or launch under a Win32 job object with `JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE`. Not a bare `proc.kill()` — that misses the children. |
| R-5 | `run.py:166` | `os.environ['RDC_ROOT']` set globally, never restored; sequential drops inherit stale value | Save/restore around `_do_parse`; or pass as explicit subprocess arg (already planned for `BOBFRAMES_*` rename) |
| R-6 | `run.py:198` | Single capture replay failure raises and aborts whole drop merge | Skip + record `capture_status='replay_failed'` in manifest (parse-side already skips) |
| R-7 | `run.py:155` | `_do_parse` only returns stderr when `rc != 0`; parse failures that return 0 lose stderr | Always log stderr to log file regardless of rc |
| R-8 | `rdcmd.py:46` | `subprocess.run(timeout=)` on hang fires `TimeoutExpired` but `capture_output=True` means stderr lost | Wrap in try/except, log stderr tail (last 400 chars) before re-raise |
| ~~R-9~~ | `catalog.py:85` | **WITHDRAWN — false positive.** Original claim said `result[c][table] += 1` undercounts and should be `+= t.num_rows`. But `caps = t.column('capture').to_pylist()` yields one entry **per row**, and `for c in caps: result[c][table] += 1` therefore sums to the correct per-capture row count. `+= t.num_rows` would assign the whole table's row count to every row → over-count. **No fix; existing code is correct.** |

### Reliability (P1 — quality of life)

| ID | File:line | Finding | Fix |
|---|---|---|---|
| R-10 | `parquetize.py:53-54` | CSV reads accumulate full table in memory (`list[list[str]]`) | Stream via `pyarrow.csv.read_csv()` chunked; defer; revisit only if OOM observed |
| R-11 | `parquetize.py:230-235` | `_copy_sidecars` overwrites without lock; two drops processing same shader race | Acceptable in single-process run.py; document constraint |
| R-12 | `run.py:275-277` | Stage dir deletion `ignore_errors=True` swallows lock failures; stale tmp at line 68 next run | Log warning on failure; `paths.drop_data_dir_tmp` cleanup safer on next run |
| R-13 | `cache.py:16-23` | Corrupted cache parquet silently returns empty dict; no hash validation | Add SHA256 sidecar; invalidate on mismatch |
| R-14 | `parse_init_state.py:51-72` | `errors='replace'` on XML open silently substitutes bad UTF-8; partial CSV emit if truncated | Validate expected chunk count post-parse; manifest records `parse_status='partial'` |
| R-15 | `replay_main.py` (full) | Crash mid-run leaves stage dir half-written; re-run reads incomplete CSVs | Stage to per-capture tmp dir; rename atomic on `os._exit(0)` path |

### Code Quality (P1)

| ID | File:line | Finding | Fix |
|---|---|---|---|
| Q-1 | `parquetize.py:100-158` | `_apply_stable_key` is 60-line if-elif chain; each branch duplicates `columns.get(col) or [''] * n` | Loop over `dict[table → (cols, key_fn)]` config; collapse to ~20 lines |
| Q-2 | `parquetize.py:74-115` | `_cast_value` swallows coercion errors silently; data silently → 0 / 0.0 | Aggregate failure counts per table, log summary after merge |
| Q-3 | `derive_post_merge.py:250-259` | Hardcoded complexity weights (2.0, 0.5, 50.0...) as magic numbers | Module-level constant dict `_COMPLEXITY_WEIGHTS = {...}`; revisit if designer needs to tune |
| Q-4 | `derive_post_merge.py:80-81` | `zip(blend_en, depth_w, parent, bsc, bdc)` no length assertion; silent truncation on drift | `assert len(blend_en) == len(depth_w) == ...` or `strict=True` (Py3.10+) |
| Q-5 | `run.py:140-155` | `_parse_one` passes args both via positional + `RDC_ROOT` env; comment + code disagree | Pick one (positional preferred per §6); update comment |
| Q-6 | Multiple report emitters | Header/ab_strip/page_open/page_close boilerplate duplicated across 6 reports | Extract `chrome.report_page(title, ab_strip, content_fn)` helper |
| Q-7 | `cache.py` + 6 callers | `{c: t.column(c).to_pylist() for c in t.column_names}` repeated | Move to `cache._to_dict_of_lists(table)` |
| Q-8 | `parse_init_state.py:530` | Noop self-assignment `acc.buffers[rid]['target_history'] = acc.buffers[rid]['target_history']` | Delete or implement intended labeling |
| Q-9 | `_dashboard.py` | Underscore prefix suggests private but module is a full report consumed by orchestrator | Rename `dashboard.py` (deferred; do at commit 8 with rename batch since no churn cost there) |

### System Design (P1)

| ID | Finding | Action |
|---|---|---|
| D-1 | The 6-report list is duplicated: `orchestrator.py:20` (named `_REPORT_MODULES`) and `ab.py:29` (named **`_MODULES`** — different name, same content) — adding a report touches 3 files | Single source of truth: `reports/__init__.py` exports `ALL_REPORTS` list; both import from there |
| D-2 | `parquetize.py` tightly couples to `schemas.py`; no schema-version negotiation | Add `schemas.expected_columns()` already exists; parquetize must verify and raise SchemaMismatch with diff (currently silently coerces) |
| D-3 | `run.py` imports `reports.orchestrator` at top — fine after rename (same package) but reports/cache.py imports schemas → tight coupling acceptable, document as expected |
| D-4 | `manifest.py:90-91` `.get('captures') or .get('stems')` shows schema drift between old/new manifests | Manifest gains `manifest_schema_version`; reader dispatches by version; old form rejected with clear error in v1.0 |
| D-5 | `derive_post_merge.py` callable on arbitrary dirs with no guard against partial data | Add precondition check: required `*.parquet` files present, manifest exists; else exit 1 |

### Scalability (P2 — defer unless measured)

| ID | Finding | Action |
|---|---|---|
| S-1 | Replay is SEQUENTIAL (`run.py:179-200`) — 600s timeout × N captures = 600N worst case | Investigate parallel qrenderdoc instances in v0.2; needs per-instance log dir + GPU contention measurement |
| S-2 | `parquetize.py:256-268` merge single-threaded across tables | ProcessPoolExecutor over tables in v0.2; deferred until profiled |
| S-3 | `catalog.py:112-147` full scan every run | Incremental: track `_manifest.json` mtime; rescan only modified drops. v0.2. |
| S-4 | `global_entities.py:47-92` full scan + O(n) memory; reads 7 tables fully | Same incremental approach; v0.2 |
| S-5 | `derive_post_merge.py` full read-modify-write per table | Vectorize via pyarrow compute kernels in v0.2 |

### Concurrency (P0 covered; P2 below)

| ID | Finding | Action |
|---|---|---|
| C-1 | `run.py:283` `os.replace(tmp, out)` race window between exists-check (281) and replace | Acceptable single-user CLI; document non-concurrent assumption. v0.2 may add `fcntl`/`msvcrt.locking` file lock at `_data/<area>/<drop>/.lock` |

### Modularity (P2)

| ID | Finding | Action |
|---|---|---|
| M-1 | New `derives/` module requires manual import in `derive_post_merge.py` + `run.py` | Auto-discovery: `derives/__init__.py` enumerates submodules via `pkgutil.iter_modules`; each exports `build(tmp_dir) -> int` |
| M-2 | New schema table requires central edit in `schemas.py` + `catalog.py:_CATALOG_TABLE_KEYS` | Register via decorator: `@register_table('tessellation_events', columns=(...))` populating a module-level registry |
| M-3 | `probes/whatif.py` not CLI-exposed; manual qrenderdoc launch | Not in v1 (CLI surface kept minimal); document as advanced pattern |

### Gaps / Misses (Production CLI checklist)

| ID | Gap | Plan |
|---|---|---|
| G-1 | No `--dry-run` flag | Add to `ingest` in v0.2: enumerate work, print plan, exit 0 |
| G-2 | No `--diff` between manifests / drops | New verb `bobframes diff <root> --baseline X --compare Y` in v0.2; emits text + HTML diff of catalog rows |
| G-3 | **No schema migration path** — `SCHEMA_VERSION` bump strands all existing `_data/` | New verb `bobframes migrate <root>` in v1.0 (when first bump happens); for v0.1, document `ingest --force` as only path |
| G-4 | No integrity check verb | New verb `bobframes verify <root>` in v0.2: stable_key uniqueness, manifest ↔ parquet row count parity, schema match, sidecar presence |
| G-5 | No CSV export for non-Python users | CSV pairs already written next to Parquet (parquetize); document; add `bobframes export <root> --format csv` in v0.2 as convenience |
| G-6 | Manifest does not record `renderdoccmd` version | Capture `renderdoccmd --version` into manifest at ingest; commit 2 includes this (cheap) |
| G-7 | Manifest does not record host GPU/driver/CPU | Add `host_info` block: GPU model + driver + CPU + OS; commit 2 (cheap; one `wmic`/`Get-WmiObject` call on Windows) |
| G-8 | Single global log level | Switch to stdlib `logging` with per-module loggers (already planned in §4); `--verbose` enables DEBUG for `bobframes.*`; `--very-verbose` enables third-party too |
| G-9 | No `--json` structured output for CI | Add `--json` to `ingest`, `render`, `verify` in v0.2: emit summary JSON to stdout, log lines to stderr |
| G-10 | No isolated-stage testing | Each pipeline stage is already a separable function; add `bobframes parse <stage-args>`, `bobframes replay <stage-args>` verbs in v0.2 |
| G-11 | `stable_keys.py` SHA256 has no version prefix; rule change orphans existing keys | Add `KEY_VERSION = 1` constant; `_sha()` prepends version byte; document upgrade path in CHANGELOG |
| G-12 | `tests/smoke.py` brittle hardcoded constants (Chor bazar / r110565 / 2026-05-27) | Fixed in commit 9 (§14) |

### XSS / safety (no findings — record)

- All HTML emit paths use `chrome.h()` or `html.escape()`. No raw f-string concat with user data found. `safe_chrome_text()` in `formatters.py:54-59` adds banned-token scrubbing on top of escape. Lint catches escapes that slip through. **No fix needed.**

---

## 18. Designer Tooling Track

Findings: tokens hardcoded as Python string in `chrome.py:10-77`; no preview page; no export; no hot-reload; no way for a designer (non-Python) to iterate. Track A in this section; ships as commit 7 of §14.

### Track A — v0.1 deliverables (in scope this release)

1. **Extract design tokens to TOML**: `bobframes/reports/design_tokens.toml`.
   ```toml
   [color]
   accent_primary = "#5B8DEF"
   accent_data    = "#3FA17B"
   surface_0      = "#0E1116"
   text_primary   = "#E6E8EB"
   # ... full token set extracted from chrome.py:10-77

   [spacing]
   xxs = "2px"
   xs  = "4px"
   sm  = "8px"

   [type]
   family_mono = "JetBrains Mono, Consolas, monospace"
   family_ui   = "Inter, system-ui, sans-serif"

   [motion]
   fast = "120ms"
   med  = "240ms"
   ```
   `chrome.py` loads via `tomllib.load(files('bobframes.reports').joinpath('design_tokens.toml'))` and emits CSS `:root { --color-accent-primary: ...; }` block. Designer edits TOML; no Python edit needed.

2. **New verb: `bobframes preview`** — emits `_reports/_chrome_preview.html` containing every visual primitive in isolation:
   - All color swatches with token name + hex
   - KPI cards (4 variants: positive delta, negative, neutral, no-baseline)
   - Section card open/close with title slot
   - All bar styles (single, stacked, segmented)
   - Delta pills (every magnitude band)
   - Sparkline samples (3-point, 12-point, with null gaps)
   - Footer + header
   - Table row variants
   - Pagination + filter chrome
   - Modal / drill link / hover-card examples (if used)
   No data dependency — pure layout demo. Renders in <100ms. Open in browser, edit TOML, re-run `bobframes preview` (sub-second).

3. **`bobframes render --watch`** — polling watcher (stdlib `os.stat` mtime check every 500ms on `design_tokens.toml`, `chrome.py`, `formatters.py`, `delta.py`). On change, re-run render-only for the current root. No `watchdog` dep. Documented as alpha; OK if it misses an edit (worst case: re-run manually).

4. **Token export**: `bobframes export-tokens --format <toml|json|css>` — emits to stdout:
   - `toml` — round-trip of `design_tokens.toml` (identity transform, useful for verification)
   - `json` — flat or nested JSON; nested is default (matches TOML structure)
   - `css` — `:root { --foo: bar; }` block, ready to paste into a non-bobframes stylesheet
   - Future format `figma-tokens` — emit Figma Token Studio JSON format; deferred to Track B

5. **README "Customizing reports" section** — designer-targeted; explains:
   - Edit `design_tokens.toml` to change colors/spacing/fonts
   - Run `bobframes preview` to verify
   - Run `bobframes render .` against any project to apply
   - Live-edit via browser DevTools `Ctrl+I` for prototyping (changes lost on refresh — for permanent edits, update TOML)
   - Token naming convention (`color.accent_*`, `spacing.*`, `type.family_*`, `motion.*`)

### Track B — v0.2+ deliverables (out of scope this release; on roadmap)

| Item | Why deferred |
|---|---|
| Figma Token Studio export | Need to verify schema against Token Studio current version; not urgent |
| Bidirectional sync (Figma → TOML) | Requires Figma API auth, plugin or webhook story; out of scope |
| Custom report plugins (auto-discovery of `~/.bobframes/reports/*.py`) | Plugin security surface; defer until M-1 + M-2 done |
| Per-area / per-project token overrides | Adds precedence complexity; wait for real user request |
| Theme variants (dark/light/high-contrast) | TOML can support via `[color.dark]`/`[color.light]` sections; defer schema choice |
| `bobframes report --watch` (per-report scope) | `--watch` global is good enough; per-report adds CLI noise |
| Inline edit UI (`bobframes serve` gains a `/edit` panel) | Scope creep; serve stays static-file in v1 |

### Designer iteration workflow (after Track A)

```
# One-time
pipx install bobframes
bobframes preview                          # opens _reports/_chrome_preview.html

# Iterate
edit bobframes/reports/design_tokens.toml  # change color
bobframes preview                          # <1s; reload browser
# Happy with tokens? Apply to a real report:
bobframes render C:\captures               # ~10s to re-emit HTML from existing parquet
```

Designer never touches `.py`. Token round-trips via TOML. CSS variable names map 1:1 to TOML keys (`color.accent_primary` → `--color-accent-primary`). Browser DevTools edits map back to TOML key by name.

---

## 19. Repo Bootstrap

User wants version control from the start. Create `bobframes` repo as its own folder; the existing capture project (`c:\Users\vsiva\Downloads\RDC mainline r110565 25-05-2026\`) becomes a sample-data consumer only.

### Location

`c:\Users\vsiva\dev\bobframes\` (matches existing `c:\Users\vsiva\dev\bobreview` pattern).

### Bootstrap steps

```powershell
# 1. Create empty directory + git init
mkdir c:\Users\vsiva\dev\bobframes
cd c:\Users\vsiva\dev\bobframes
git init -b main

# 2. Copy current _analysis/ tree (still named _analysis at this point)
robocopy "c:\Users\vsiva\Downloads\RDC mainline r110565 25-05-2026\_analysis" `
         "c:\Users\vsiva\dev\bobframes\_analysis" `
         /E /XD __pycache__ /XF *.pyc

# 3. Add bootstrap files (created by hand; templates in §3 + §13)
#    pyproject.toml      (per §3, with name='_analysis' for commit 1; rename at commit 8)
#    README.md           (per §13)
#    LICENSE             (MIT, standard text)
#    CHANGELOG.md        (Keep-a-Changelog header + Unreleased section)
#    .gitignore          (see below)
#    .github/workflows/  (empty until commit 10)

# 4. First commit
git add .
git commit -m "Initial commit: extract _analysis pipeline from RDC mainline r110565

Source: c:\Users\vsiva\Downloads\RDC mainline r110565 25-05-2026\_analysis
At schema_version=3, schema_keys version=1 (post-extraction baseline).
"

# 5. Create remote (do this manually in GH UI or via gh CLI)
gh repo create mayhem-studios/bobframes --private --source=. --remote=origin --push
# (or for public: --public)
```

### `.gitignore`

```
# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
*.egg-info/
.eggs/
*.egg
build/
dist/
wheels/
pip-wheel-metadata/

# Virtual env
.venv/
venv/
env/

# Editor
.idea/
.vscode/
*.swp
.DS_Store

# Test artifacts
.pytest_cache/
.coverage
htmlcov/
.tox/

# Project-specific: never commit user data, manifests, or rendered output
**/_data/
**/_reports/
**/_stage/
**/_tmp/
**/index.html
**/*.parquet
**/*.rdc
**/*.zip.xml
**/_manifest.json
**/done.marker

# Exception: bundled synthetic test data
!bobframes/tests/data/synthetic/
!bobframes/tests/data/synthetic/**/*.parquet

# Bobframes config
.bobframes.toml

# Generated docs
docs/_build/

# OS
Thumbs.db
```

### Commit-by-commit sequence (mirrors §14)

Each numbered commit in §14 maps to a single PR. PR titles use Conventional Commits (`feat:`, `fix:`, `refactor:`, `chore:`). After commit 8 (rename), all subsequent PRs target the renamed `bobframes/` tree.

```
git log --oneline                          # after all commits land:
v0.1.0
chore: README + CHANGELOG + LICENSE
feat: CI workflow
feat: rewrite tests/smoke.py
refactor: rename _analysis -> bobframes
feat: designer-tooling foundation (Track A)
refactor: replay script discovery via importlib.resources
feat: add cli.py dispatcher; install [project.scripts]
refactor: rename env vars RDC_* -> BOBFRAMES_*
refactor: introduce _analysis.config.resolve_tool() + _analysis.errors
fix: reliability hardening pass (atomic writes, subprocess kill, env restore)
chore: add __version__ to _analysis/__init__.py
Initial commit: extract _analysis pipeline from RDC mainline r110565
```

### Source-project cleanup (separate, after repo bootstrap)

In the existing capture project (`c:\Users\vsiva\Downloads\RDC mainline r110565 25-05-2026\`):

```powershell
# After bobframes v0.1.0 is installed via pipx:
pipx install bobframes
bobframes check
bobframes ingest "c:\Users\vsiva\Downloads\RDC mainline r110565 25-05-2026" --force
# Verify identical output to the legacy embedded run.

# Then delete the embedded tree:
Remove-Item -Recurse -Force "c:\Users\vsiva\Downloads\RDC mainline r110565 25-05-2026\_analysis"
```

The capture project becomes a pure data folder; no Python in it.

### Branch protection (suggested, do via GH UI)

- `main` requires PR review (when team grows; OK to disable for solo work).
- `main` requires CI green.
- Tags `v*` trigger publish workflow; only push from local after CHANGELOG bumped.

### Two-week migration checklist

| Day | Action |
|---|---|
| 1 | Bootstrap repo (this section), commit 1 |
| 2 | Commit 2 (reliability hardening — biggest risk) |
| 3 | Commit 3 + 4 (config + env rename) |
| 4 | Commit 5 (cli dispatcher) |
| 5 | Commit 6 (replay discovery) |
| 6 | Commit 7 (designer tooling foundation) |
| 7-8 | Soak: run hardened legacy pipeline against real captures; verify no regressions |
| 9 | Commit 8 (the rename — atomic, full day) |
| 10 | Commit 9 (smoke rewrite) |
| 11 | Commit 10 (CI workflow); first PR run |
| 12 | Commit 11 (docs) |
| 13 | Reserve PyPI name; upload 0.0.0 placeholder |
| 14 | Tag v0.1.0; verify CI publishes; smoke-test `pipx install bobframes` on a clean machine |

---

## 20. Hardcoded Patterns — Inflexibility Catalog

Audit pass: every literal, magic number, and baked-in assumption that limits the tool to its current shape (UE + Arm Performance Studio 2026.2 + 6 reports + 9 draw classes + UE pass naming). Priority by user-impact: **P0** = limits adoption beyond current project (engine, vendor, schema); **P1** = friction (version locks, dual-edit lists); **P2** = cosmetic / future-proofing.

### P0 — Engine / vendor lock-in

| ID | File:line | Hardcoded | Why it matters | Remediation |
|---|---|---|---|---|
| H-1 | `derive_post_merge.py:35-62` | `_classify_draw()` keyword switch: `'basepass'`, `'shadow'`, `'prepass'`, `'depthonly'`, `'slate'`, `'ui'`, `'postprocess'`, `'tonemap'`, `'bloom'`, `'eyeadapt'`, `'decal'`, `'translucen'` | UE-specific. Breaks on Unity / Godot / proprietary engines. New engine = code patch. | Externalize to `bobframes/derives/draw_classifier.toml`: ordered list of `{pattern = "regex", class = "shadow"}`. `_classify_draw()` becomes a 10-line walker. Ship UE preset + Unity preset; user can supply `--classifier <path>` to override. |
| H-2 | `formatters.py:84-114` | `pass_short()` strips `'FRDGBuilder::Execute'`, `'MobileSceneRender'`, `'/Engine/EngineMaterials'`, FName redundancy collapsing | UE-specific marker normalization. Other engines see un-stripped paths. | Pattern list to TOML alongside H-1: `[pass_strip] patterns = ["FRDGBuilder::Execute", ...]`. Default to UE preset. |
| H-3 | `derive_post_merge.py:26` | `_RE_FRAME_PREFIX = re.compile(r'^Frame\s+\d+/?')` | UE convention `"Frame N/PassName"`. Other engines emit different prefixes. | Same TOML; `frame_prefix_regex = "^Frame\\s+\\d+/?"`. |
| H-4 | `pass_class_breakdown.py:46` | Counter name literal `'GPU Duration'` | Arm-specific counter naming. Adreno Profiler emits `'GPU Time'`; Snapdragon Profiler differs. Breaks if vendor varies. | Counter name lookup in config: `[counters] gpu_duration = "GPU Duration"`. Resolver falls through aliases (`"GPU Time"`, `"GPU Total Duration"`). |
| H-5 | `chrome.py:1081-1087` + `derive_post_merge.py:35-62` | `DRAW_CLASSES` enum list duplicated in two places (color tokens in chrome, classifier in derive) | Two sources of truth; adding a class touches two files; silent drift if they diverge. | Single source: `bobframes/derives/draw_classifier.toml` exports `class_order = [...]`; chrome.py iterates it to emit `--c-<name>` tokens dynamically. |
| H-6 | `replay/replay_main.py:32-181` | Schema column tuples duplicated from `schemas.py` (qrenderdoc import-unreliable) | Drift risk on every schema change; only caught at parquetize header-verify. | Already documented (§9, R-15). Acceptable; add CI check: parse `replay_main.py` literals, diff against `schemas.py`. Fail build on mismatch. |

### P1 — Tool version lock + dual-edit lists

| ID | File:line | Hardcoded | Why it matters | Remediation |
|---|---|---|---|---|
| H-7 | `qrd_harness.py:16-18`, `rdcmd.py:14` | Path: `c:/Program Files/Arm/Arm Performance Studio 2026.2/renderdoc_for_arm_gpus/{qrenderdoc,renderdoccmd}.exe` | Version `2026.2` baked. Arm releases quarterly. Path breaks every 3 months. | Already addressed by config.toml + `resolve_tool()` (§5); also: glob `C:/Program Files/Arm/Arm Performance Studio */renderdoc_for_arm_gpus/*.exe`, pick latest by directory name sort. |
| H-8 | `orchestrator.py:20-27` (`_REPORT_MODULES`) + `ab.py:29-36` (**`_MODULES`**) | 6-report list duplicated under two different names | Adding a report = edit two files + `reports/__init__.py`. (Already noted D-1, §17.) | Single registry in `bobframes/reports/__init__.py`: `ALL_REPORTS = [...]`; both consumers import from there. Future: `pkgutil.iter_modules` auto-discovery with `build()` convention. |
| H-9 | `global_entities.py:33-40` | `_ENTITY_TABLES` hardcodes `[(table, id_col, kind), ...]` for 7 tables | Adding entity table requires edit here + schemas.py + catalog.py. | Derive at import time from `schemas.TABLES` filtered by `is_entity_table()` predicate. Single source of truth. |
| H-10 | `catalog.py:27-39` | `_CATALOG_TABLE_KEYS` list of 29 table names | Must stay in sync with `schemas.TABLES` manually. | Derive from `schemas.TABLES.keys()` at import time. Drop the literal. |
| H-11 | `html/template.py:27-39` | `_CATEGORY_MAP` table groupings (`'aggregates'`, `'entities'`, `'actions'`, `'samples'`) | Adding a table requires categorizing it manually here. | Move categorization to `schemas.TABLES` as `category` field per entry; template reads from schema. |
| H-12 | `qrd_harness.py:39` | `timeout_s: float = 600.0` (replay timeout) | 10 min may not fit huge captures (e.g. 4K G-Buffer with 5000 draws). User can't tune. | `[pipeline] replay_timeout_s = 600` in config; CLI flag `--replay-timeout`. |
| H-13 | `rdcmd.py:31` | `timeout_s: float = 120.0` (convert timeout) | Same. Large .rdc files (>500MB) may need longer. | `[pipeline] convert_timeout_s = 120` in config; CLI flag. |
| H-14 | `lint.py:16-31` | `BANNED` list inline | Adding/removing a lint rule = code edit. Local override impossible. | Move to `bobframes/lint_banlist.toml`; allow `[lint] extra_banned = ["pattern", ...]` in user config to extend. |
| H-15 | `chrome.py:14-68` | All design tokens (spacing, type, motion, color) inline as Python multiline string | Designer must edit `.py` (covered in §18 Track A — fix via `design_tokens.toml`). | Already planned in §18. |
| H-16 | `formatters.py:9` | `_BANNED_CHROME_CHARS = re.compile(r'[—–…""''→←↑↓×·]')` | Inline regex; can't be extended without code edit. | Move to `lint_banlist.toml` alongside H-14. |
| H-17 | `derive_post_merge.py:250-259` | Complexity score weights (`2.0`, `0.5`, `2.0`, `0.3`, `0.5`, `0.3`, `50.0`) as inline literals | Tuning the shader complexity metric requires code change. | Move to `[scoring.complexity] alu = 2.0, ...` in config; document each weight. |
| H-18 | `paths.py:33,48,56,90` + scattered uses | Directory literals: `'_data'`, `'_reports'`, `'_cache'`, `'_stage'`, `'_tmp'`, `'drill'`, `'ab'` | Repeated literals across `paths.py`, `run.py`, `parquetize.py`. Renaming any of these is a multi-file search-and-replace. | Centralize as module constants in `paths.py`: `DATA_DIR='_data'`, `REPORTS_DIR='_reports'`, etc. All other files import these. (Layout still frozen per CLAUDE constraints; just remove the duplication.) |
| H-19 | `manifest.py:47`, `catalog.py:58`, `run.py:78,285` | Literals: `'_manifest.json'`, `'done.marker'` | Same as H-18; rename pain. | Add to paths.py constants. |
| H-20 | `chrome.py:160,196,245,255,261` + `delta.py:131-144` | Inline layout literals: bar heights (`18px`, `6px`), grid column widths (`240px`, `90px`), sparkline dimensions (`60x14`) | Designer can't tune layout without Python edit. | Lift into `design_tokens.toml` under `[layout]` section. |
| H-21 | `delta.py:118` | `if pct >= 8.0:` minimum bar segment width for label | Cosmetic threshold; designer might want to tune. | `[layout] bar_label_min_pct = 8.0`. |
| H-22 | `delta.py:34` | `fmt: str = '{:+,.0f}'` default delta number format | Locale-insensitive; no decimals. | Config + per-call override (already a parameter; expose in config as default). |
| H-23 | `formatters.py:43,62,74` | `n=12` (ID shorten), `max_len=60` (trunc_mid + trunc_left) | Default-but-rigid; reports built-in pass values, but no config layer. | `[formatting] id_short_n = 12`, `text_trunc_max = 60`. |

### P1 — Wire protocol + subprocess

| ID | File:line | Hardcoded | Why it matters | Remediation |
|---|---|---|---|---|
| H-24 | `qrd_harness.py:20` + `replay_main.py:29` | `_SEP = '\x1f'` separator | Must agree at both ends; if RenderDoc Python sandbox ever rejects `\x1f`, both endpoints update. | Keep literal but expose as `bobframes.wire.SEP` constant imported by both (replay_main can't import — duplicate with assertion comment). |
| H-25 | `rdcmd.py:38-44` | Command literal `['renderdoccmd', 'convert', '-f', ..., '-i', 'rdc', '-c', fmt]` | If RenderDoc CLI flag scheme ever changes (renderdoc 2.0?), one-place update needed. | Acceptable; minimize abstraction. Add comment with renderdoccmd version known-compatible range. |
| H-26 | `qrd_harness.py:65,79` | `[qrd, '--python', script_path]` | Same. | Same. |

### P1 — Stable-key + manifest

| ID | File:line | Hardcoded | Why it matters | Remediation |
|---|---|---|---|---|
| H-27 | `stable_keys.py:34` | SHA256 with no version/salt prefix | Rule change → all existing keys orphaned (G-11 in §17). | Add `KEY_VERSION = 1`; prepend version byte to hash input. Bumping KEY_VERSION forces re-ingest but doesn't silently corrupt. |
| H-28 | `manifest.py:18-19` + `cli.py:16-17` | Two timestamp helpers (`utc_now_iso()` and `now_iso()`) — UTC vs local mixed | Manifest timestamps could be UTC or local depending on writer. Sorting / diff brittle. | Single `bobframes.config.now_iso()`; always UTC; document. |
| H-29 | `schemas.py:9` | `ID_COLS = ('area', 'drop_date', 'drop_label', 'capture')` four required keys | Layout assumption; breaks if a new project organizes captures differently (e.g., by build hash, by branch). | Frozen for v1 (schema constraint). Document as v1 contract; v2 may relax. |
| H-30 | `discovery.py:18` | `DATED_RE = r'^(\d{4}-\d{2}-\d{2})(?:_(.*))?$'` drop folder format | Locks to `YYYY-MM-DD[_label]`. Some teams use `r12345_2026-05-27` or just numeric. | `[discovery] drop_folder_regex = "..."` in config; default to current regex; user can override per project. |
| H-31 | All hardcoded English strings | `'draws by class'`, `'areas'`, `'builds'`, `'opaque'`, etc. across `chrome.py`, report emitters, `_dashboard.py` | i18n impossible without grep-and-replace. | Not a v1 concern. Track in roadmap. If touched, lift to `bobframes/reports/strings.toml`; reports lookup by key. |

### P2 — Cosmetic / low-impact

| ID | File:line | Hardcoded | Note |
|---|---|---|---|
| H-32 | `run.py:42-43` | `_ts()` format `'%Y%m%dT%H%M%S'` | Used only for rotation suffix; OK. |
| H-33 | `run.py:46-47` | `_log()` timestamp `'%H:%M:%S'` | Hours:minutes:seconds; date implicit. OK for short-lived CLI; deferred. |
| H-34 | `chrome.py:69-76` | Reduced-motion media query zeroes all `--motion-*` durations | Accessibility-correct; not a problem. |
| H-35 | `html/template.py:40-41` | `_CATEGORY_ORDER` + `_DEFAULT_OPEN = {'aggregates'}` | Display preference; OK. Could move to design_tokens.toml `[browser]`. |

### Summary

**The largest flexibility limits are UE-coupling (H-1 through H-5) and Arm-Studio coupling (H-7).** Both are addressable in v0.2 with config-driven classifier + glob-based version detection — no architectural rework. The next-largest is the **duplicate-list problem** (H-8, H-9, H-10, H-11) — pure cleanup; ship in v0.2 alongside the classifier refactor.

### Roadmap remediation (revised — full P0/P1 sweep in v0.1)

| Release | Items addressed |
|---|---|
| **v0.1.0** (this plan) | **All P0 + P1**: H-1, H-2, H-3, H-4, H-5 (engine-agnostic classifier with UE preset bundled), H-7 (glob version detection), H-8, H-9, H-10, H-11 (registry consolidation from `schemas.TABLES`), H-12, H-13 (configurable timeouts), H-14, H-16 (lint TOML), H-15, H-20 (design tokens TOML — §18 Track A), H-17 (scoring weights TOML), H-18, H-19 (paths.py constants), H-21, H-22, H-23 (layout/format config), H-27 (KEY_VERSION=1), H-28 (single UTC timestamp), H-30 (configurable drop regex) |
| **v0.1.0 — CI guardrail** | H-6 (replay schema duplication: drift detector, not removed) |
| **v1.0+** | H-29 (relax `ID_COLS` schema contract), H-31 (i18n; only if requested) |
| **Permanent / out-of-scope** | H-24, H-25, H-26 (wire protocol literals: `\x1f`, `--python`, `renderdoccmd convert` flags — change only if RenderDoc itself does), H-32, H-33, H-34, H-35 (cosmetic timestamp formats, accessibility motion query, browser display order — leave as-is) |

### Items that stay hardcoded by design (and why)

| ID | What stays | Reason |
|---|---|---|
| H-6 | `replay_main.py` schema duplication | qrenderdoc's embedded Python cannot reliably import the outer package. Guarded by CI drift detector (commit 13 of §14). |
| H-24 | `_SEP = '\x1f'` | Wire protocol; both endpoints must agree; unit separator is the right choice and not user-tunable. |
| H-25 | `renderdoccmd convert -f ... -c <fmt>` literal | RenderDoc CLI contract; if renderdoc 2.0 changes scheme, single-place fix. |
| H-26 | `qrenderdoc --python <path>` | Same — RenderDoc-defined invocation. |
| H-29 | `ID_COLS = ('area', 'drop_date', 'drop_label', 'capture')` | Schema v3 contract per CLAUDE constraint; layout invariant. |
| H-18/H-19 directory names (`_data`, `_reports`, `drill`, `ab`, `_cache`) | The strings themselves | Output layout frozen per CLAUDE constraint; H-18/H-19 only centralizes the literals (no longer scattered) — value still `'_data'` etc. |

### Config-driven layer (post-v0.2)

After v0.2 remediation, the per-project `.bobframes.toml` schema grows to:

```toml
schema_version = 1

[tools]
renderdoccmd = "C:/Program Files/Arm/.../renderdoccmd.exe"
qrenderdoc   = "C:/Program Files/Arm/.../qrenderdoc.exe"

[pipeline]
workers              = 4
pixel_grid           = 4
keep_stage           = false
replay_timeout_s     = 600
convert_timeout_s    = 120

[discovery]
drop_folder_regex    = "^(\\d{4}-\\d{2}-\\d{2})(?:_(.*))?$"

[render]
ansi_color           = "auto"

[classifier]
preset               = "ue"               # ue | unity | godot | custom
custom_path          = ""                 # path to a TOML if preset = "custom"

[counters]
gpu_duration_aliases = ["GPU Duration", "GPU Time", "GPU Total Duration"]

[lint]
extra_banned         = []                 # additional regex patterns

[scoring.complexity]
alu                  = 2.0
texture_samples      = 0.5
control_flow         = 2.0
constant_load        = 0.3
discards             = 0.5
varyings             = 0.3
register_pressure    = 50.0

[formatting]
id_short_n           = 12
text_trunc_max       = 60
```

This shape ships in v0.1; bundled `_default_config.toml` reproduces current behavior exactly. Designers, perf engineers, and downstream teams can tune any layer without touching code.

---

## 21. Quality safeguards — "as good or better"

Removing hardcoded patterns introduces regression risk. To guarantee data extraction + reports stay **as good or better than today**, ship four layered safeguards. All run in CI on every commit.

### 21.1 Golden-snapshot parity

**Goal**: byte-identical HTML output before and after every refactor commit.

```
bobframes/tests/data/
  synthetic/                        # tiny _data/ tree (~500KB), SCHEMA_VERSION=3
    _data/<area>/<drop>/*.parquet
    _data/_catalog.parquet
  golden/                           # frozen expected HTML output
    index.html
    _reports/dashboard.html
    _reports/draws_by_class.html
    _reports/trend_table.html
    _reports/instancing_opportunities.html
    _reports/pass_gpu.html
    _reports/shader_hotlist.html
    _reports/overdraw.html
    _reports/drill/<area>/<drop>/index.html
```

`bobframes/tests/parity.py`:
```python
def test_render_matches_golden(tmp_path):
    shutil.copytree(SYNTHETIC, tmp_path / "data")
    subprocess.run(["bobframes", "render", str(tmp_path)], check=True)
    for golden in GOLDEN_DIR.rglob("*.html"):
        rel = golden.relative_to(GOLDEN_DIR)
        actual = (tmp_path / rel).read_text()
        expected = golden.read_text()
        assert actual == expected, f"Diverged: {rel}"
```

Refresh procedure (when an intentional output change ships): `bobframes render bobframes/tests/data/synthetic` → copy result to `tests/data/golden/` → review diff in PR.

### 21.2 Schema regression

**Goal**: every Parquet column list matches `schemas.expected_columns(stem)` exactly. Catches alphabetization drift, accidental column drop, dtype slip.

```python
def test_synthetic_parquet_schemas():
    for parquet in (SYNTHETIC / "_data").rglob("*.parquet"):
        stem = parquet.stem
        if stem.startswith("_"):  # _catalog, _global_entities — skip
            continue
        expected = schemas.expected_columns(stem)
        actual = tuple(papq.read_schema(parquet).names)
        assert actual == expected, f"{parquet.name}: {set(actual) ^ set(expected)}"
```

Also runs against post-ingest output of any drop touched in CI.

### 21.3 Replay-side schema drift detector

**Goal**: catch the H-6 duplication risk. `replay/replay_main.py` has hardcoded column tuples (lines 34-189) duplicated from `schemas.py` because qrenderdoc import is unreliable.

> **CORRECTION (review):** the earlier draft of this test was a silent no-op and is replaced below.
> Two bugs in the old version: (1) it matched **prefix** `_COLS_`, but the real variables are
> **suffix** form (`DRAWS_COLS`, `PASSES_COLS`, …) → zero matches → test passes vacuously; and
> (2) `name.lower()` does not map to the schema stem — several names are abbreviated
> (`RT_COLS`→`render_targets`, `RT_TIMELINE_COLS`→`rt_event_timeline`,
> `STATE_CHANGE_COLS`→`state_change_events`, `COUNTERS_COLS`→`counters_per_event`). A clean
> lowercase would `KeyError`. The corrected test matches the suffix, uses an explicit alias map for
> the abbreviated names, and **asserts a minimum match count** so a future rename can't silently
> re-disable it.

```python
# Replay var name (sans trailing _COLS) -> schemas.TABLES stem.
# Identity for most; explicit only where they differ. ID_COLS is the shared base, not a table.
_REPLAY_STEM = {
    "RT": "render_targets", "RT_TIMELINE": "rt_event_timeline",
    "STATE_CHANGE": "state_change_events", "COUNTERS": "counters_per_event",
}
_EXPECTED_REPLAY_TABLES = 21  # number of *_COLS table tuples in replay_main.py today

def test_replay_main_schema_in_sync():
    replay_src = (PKG / "replay" / "replay_main.py").read_text()
    tree = ast.parse(replay_src)
    # {VARNAME: (literal string tuple)} for every top-level `<NAME>_COLS = (...)`,
    # resolving `ID_COLS + (...)` concatenations. Skip the bare ID_COLS base itself.
    replay_tables = _extract_col_tuples(tree, suffix="_COLS", skip={"ID_COLS"})
    assert len(replay_tables) >= _EXPECTED_REPLAY_TABLES, (
        f"only {len(replay_tables)} *_COLS tuples found — did replay_main.py rename them? "
        f"This guard must not silently match zero."
    )
    for var, cols in replay_tables.items():
        base = var[:-len("_COLS")]                       # DRAWS_COLS -> DRAWS
        stem = _REPLAY_STEM.get(base, base.lower())      # alias map, else lowercase
        expected = schemas.expected_columns(stem)
        assert cols == expected, f"replay_main.{var} drifted: {set(cols) ^ set(expected)}"
```

Runs on every push. Build fails immediately if a `schemas.py` edit isn't mirrored in
`replay_main.py` — **or** if the `*_COLS` naming convention changes without updating this test
(the min-count assert is the tripwire). Cheaper alternative worth considering: **rename the replay
vars to match stems exactly** (`RENDER_TARGETS_COLS`, …) so the alias map disappears.

### 21.4 Determinism + lint + performance

```python
def test_determinism():
    # Render synthetic twice; output must be byte-identical (catches dict ordering, timestamps)
    out1 = _render(SYNTHETIC, tmp_a)
    out2 = _render(SYNTHETIC, tmp_b)
    for a, b in zip(sorted(out1), sorted(out2)):
        assert a.read_bytes() == b.read_bytes(), f"Non-deterministic: {a.name}"

def test_no_lint_hits():
    for html in (SYNTHETIC.parent / "rendered" / "_reports").rglob("*.html"):
        hits = lint.lint_file(html)
        assert not hits, f"{html.name}: {hits}"

def test_render_perf():
    # Synthetic render must complete in <2s on CI hardware; flag regressions.
    t0 = time.monotonic()
    _render(SYNTHETIC, tmp_path)
    assert time.monotonic() - t0 < 2.0, "Render slow regression"
```

### 21.5 Quality-improving items (not just parity)

The de-hardcoding gives us hooks to improve report quality — opt-in, off by default to preserve parity:

| Item | Today | After v0.1 (opt-in via config) |
|---|---|---|
| Misclassified UE draws bucketed to `'other'` | ~5-10% of draws fall to `'other'` per the keyword switch | Classifier TOML adds new rules (e.g. `(?i)gbuffer` → `'opaque'`, `(?i)velocity` → `'prepass'`); designer iterates without code change. Drop in `'other'` measurable in dashboard. |
| Empty reports for sparse data | Report shows blank table | Empty-state message with reason ("no draws with `--area=X`"). Already in commit 16. |
| Sparkline data gaps | None rendered as zero | Null-gap rendering (already in `delta.py:131-167`); golden tests verify. |
| Manifest provenance | Build timestamp only | Adds `tool_versions`, `host_info` (GPU/driver/CPU); footer surfaces in dashboard. Powers cross-machine A/B contextualization. |
| Cache validation | Silent on corruption (R-13) | SHA256 sidecar; corrupted cache rebuilds with warning instead of returning empty. |

### 21.6 CI matrix updated for v0.1

```yaml
strategy:
  matrix:
    os: [windows-latest]
    python: ["3.10", "3.12", "3.14"]
    pyarrow: ["17", "21"]                 # lower + upper of pin range
jobs:
  test:
    steps:
      - pytest bobframes/tests/unit_*.py        # ~30s
      - pytest bobframes/tests/parity.py        # golden snapshots
      - pytest bobframes/tests/schemas.py       # schema regression
      - pytest bobframes/tests/replay_drift.py  # H-6 drift detector
      - pytest bobframes/tests/determinism.py   # render-twice diff
      - pytest bobframes/tests/perf.py          # <2s render
      - bobframes smoke                          # render-only against synthetic
      - bobframes lint bobframes/tests/data/golden/**/*.html
```

CI runtime budget: <3 minutes per matrix cell. Total v0.1 CI: ~9 matrix cells × 3 min = ~30 min wall clock, parallel.

### 21.7 Pre-merge checklist (per PR touching `bobframes/`)

- [ ] Golden snapshots updated? (only if intentional output change)
- [ ] Schema regression green
- [ ] Replay-drift green
- [ ] Determinism green
- [ ] Lint green
- [ ] Perf within budget
- [ ] CHANGELOG entry added if user-visible

### 21.8 Updated 21-day timeline (was 14)

| Day | Action |
|---|---|
| 1 | Bootstrap repo (§19), commit 1 |
| 2 | Commit 2 (golden harness + parity tests) |
| 3 | Commit 3 (reliability hardening) |
| 4 | Commit 4 (paths.py constants) |
| 5 | Commit 5 (table/entity registry consolidation) |
| 6 | Commit 6 (config.resolve_tool + glob version detection) |
| 7 | Commit 7 (TOML config layer + defaults) |
| 8 | Commit 8 (design tokens TOML + preview verb) |
| 9-10 | Commit 9 (engine-agnostic classifier; **2 days** — most invasive refactor; parity test critical) |
| 11 | Commit 10 (env var rename) |
| 12 | Commit 11 (cli.py dispatcher) |
| 13 | Commit 12 (replay importlib.resources) |
| 14 | Commit 13 (replay drift CI test) |
| 15 | Commit 14 (the atomic rename — full day) |
| 16 | Commit 15 (smoke + unit tests) |
| 17 | Commit 16 (report-quality enhancements + manifest provenance) |
| 18 | Commit 17 (CI workflow) |
| 19 | Commit 18 (docs) |
| 20 | Reserve PyPI name; upload 0.0.0 placeholder; CHANGELOG bump |
| 21 | Tag v0.1.0; verify CI publishes; smoke-test `pipx install bobframes` on clean machine |

### 21.9 Data-extraction quality (unchanged guarantee)

**Important clarification**: de-hardcoding does NOT change the data extraction pipeline (renderdoccmd export, qrenderdoc replay, parsers, parquetize). Those produce identical Parquet for identical `.rdc` input. Quality improvements are in:
- **Classification correctness** (fewer `'other'` draws; designer-tunable rules)
- **Report polish** (empty states, sparkline gaps, provenance footer)
- **Operational quality** (atomic writes, subprocess cleanup, schema validation)
- **Configurability** (everything tunable without code edit; bundled defaults match today)

The Parquet contents themselves remain byte-identical for the same `.rdc` input (verified by schema regression + golden tests against the synthetic `_data/`).

---

## 22. Review addendum (judgment calls — decide before commit 1)

These are not factual errors in the plan; they are scope/risk decisions surfaced by review.
The four code-level corrections (drift test §21.3, R-9 withdrawal, R-4 reframe, stale names) are
already applied inline above. The items below need a human call.

### 22.1 v0.1 scope — recommend pure extraction, defer de-hardcoding to v0.2 (HIGH)

The stated session goal was *extraction*. §14 then folded **all P0+P1 de-hardcoding** (engine
classifier, full TOML config layer, design-tokens TOML, `preview`/`--watch`) **plus** the designer
track **plus** quality safeguards into v0.1 — and the timeline grew 14→21 days, with the classifier
(commit 9) flagged as 2 days / "most invasive." §20's own roadmap *originally* scheduled these for
v0.2. This bundling is the single biggest risk to shipping anything.

**Recommended split:**
- **v0.1 (extraction only):** commits 1 (version), 2 (golden harness), 3 (hardening), 11 (cli.py),
  12 (replay importlib), 13 (replay-drift CI), 14 (rename), 15 (smoke), 17 (CI), 18 (docs), 19 (tag).
  ~11–13 days. Ships a working, installable, tested `bobframes` with byte-identical output.
- **v0.2 (de-hardcoding):** commits 4–10 (paths constants, registry consolidation, config layer,
  design tokens, engine classifier, env rename) + designer Track A. Each still guarded by the
  golden parity gate that v0.1 establishes.

If the de-hardcoding must ship in v0.1, accept the 21-day timeline explicitly and treat commit 9 as
the schedule pole.

### 22.2 CI cannot exercise the ingest path in v0.1 (HIGH)

CI is `windows-latest` with no GPU/RenderDoc → it only runs render-only + parity + unit. The
**highest-value** reliability work (atomic writes, R-4 tree-kill, R-6 replay-skip) lives entirely
on the **ingest** path and gets **zero automated coverage**; full smoke is deferred to a self-hosted
runner (v0.2). Mitigation: add a small **mocked-subprocess** unit test that drives the
kill-on-timeout, replay-failure-skip, and tmp+`os.replace` atomic-rename branches with fakes, so the
hardening isn't shipped wholly untested. Add to commit 3.

### 22.3 `py3.14 × pyarrow 17` matrix cell will fail to install (MED)

`requires-python = ">=3.10,<3.15"` + classifiers/CI list 3.14, but `pyarrow>=17` has no cp314
wheels (pyarrow 17 predates 3.14). The low-pin cell `{3.14, pyarrow 17}` can't install. Fix one of:
drop 3.14 from the low-pin leg of the matrix; raise the pyarrow floor on 3.14 via an environment
marker (`pyarrow>=18; python_version>='3.14'`); or drop 3.14 from v0.1 entirely and add it once the
wheel exists. Reconcile §3 classifiers + §21.6 matrix together.

### 22.4 Synthetic golden data: generate from a real ingest, not by hand (MED)

The parity gate is only as good as the synthetic corpus. A hand-authored tree risks **not
exercising** a classifier keyword or pass-strip rule — and the classifier refactor (commit 9) is
exactly where an unexercised path gives false-green parity. Recommend **deriving** the synthetic
`_data/` by down-sampling + anonymizing a real Chor-bazar ingest (truncate row groups, scrub
absolute paths/shader source), so coverage mirrors production. Verify the synthetic actually hits
every `class_order` bucket and every `[pass_strip]` rule before freezing the golden.

### 22.5 TOML round-trip is the riskiest parity surface (MED)

"Byte-identical" must survive routing values through TOML in commits 7 & 9:
- **Floats:** `2.0` parsed from TOML must format identically to the inline literal in any emitted
  string (watch `repr`/`%g` vs `{:.1f}`).
- **Regex:** TOML strings need doubled escapes (`"^Frame\\s+\\d+/?"`); a single-backslash slip
  compiles to a *different* pattern that still "looks right." Add a parity assertion that the
  config-loaded regex `.pattern` equals the original compiled pattern, and that complexity-weight
  formatting is unchanged, as part of the commit-7/9 parity gate.

### 22.6 Internal commit-numbering is self-contradictory (LOW)

The doc was revised in layers: §10 and §15 call the rename "commit 6"; §14 lists it as **commit
14**; §19's git-log shows it 5th-from-top; §14 has 19 commits while §19's log lists 12. Pick §14 as
canonical, renumber, and fix every back-reference ("commit 6"→"commit 14", "commit 8"→"commit 14",
etc.) so the migration is unambiguous when executed.

