# BobFrames — architecture (FROZEN)

> The "what we are building" contract. Frozen: change only by appending an ADR to
> [DECISIONS.md](DECISIONS.md) and referencing it here. Carved from CLI_PLAN §1–6, §9, §12.

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
| Platform | **Windows only in v1.** macOS/Linux deferred. |

PyPI availability check at execution time: `pip index versions bobframes` / `curl -s
https://pypi.org/pypi/bobframes/json`. Fallbacks if taken: `bob-frames`, `bobframescope`.

## 2. Package layout

Flat layout (no `src/`). Same on disk as installed; one-to-one with the original `_analysis/`. The
package is named `bobframes` from the scaffold ([ADR-7](DECISIONS.md) — the old c14 rename is
collapsed; source is swept `_analysis`→`bobframes` when copied in, BOOTSTRAP step 2b).

```
bobframes/                          # repo root
  pyproject.toml  README.md  CHANGELOG.md  LICENSE
  .github/workflows/ci.yml
  docs/plan/                        # this plan set (repo root, NOT in the package)
  bobframes/                        # the package
    __init__.py                     # from ._version import __version__
    _version.py                     # __version__ = "0.1.0"
    cli.py                          # NEW: argparse dispatcher
    pipeline.py                     # WAS run.py
    errors.py                       # NEW (v0.2): ToolNotFound, PipelineError, exit_code map
    config.py                       # NEW (v0.2): TOML loader, tool resolution
    schemas.py                      # frozen v3
    paths.py                        # frozen (16 public funcs)
    lint.py                         # frozen
    discovery.py  rdcmd.py  qrd_harness.py  catalog.py
    global_entities.py  parquetize.py  derive_post_merge.py
    manifest.py  query_examples.py  resource_labels.py  stable_keys.py
    parsers/        parse_init_state.py  derive_program_transitions.py
    replay/         __init__.py (NEW: replay_script_path)  replay_main.py (frozen)
    derives/        pass_class_breakdown.py  texture_usage.py
    html/           template.py
    reports/        cli.py base.py chrome.py formatters.py delta.py discovery.py
                    cache.py orchestrator.py ab.py _dashboard.py
                    draws_by_class.py trend_table.py instancing_opportunities.py
                    pass_gpu.py shader_hotlist.py overdraw.py
    probes/         whatif.py       # manual qrenderdoc-side; not a CLI verb
    tests/          smoke.py  data/synthetic/
```

`errors.py` and `config.py` are NEW but **v0.2** (de-hardcoding); in v0.1 the package keeps the
existing inline tool discovery. See the tool-discovery ADR in [DECISIONS.md](DECISIONS.md).

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
  "Topic :: Software Development :: Debuggers",
  "Topic :: Multimedia :: Graphics",
]
dependencies = [
  "pyarrow>=17,<22",
]

[project.optional-dependencies]
dev = ["build", "twine", "hatchling", "pytest"]

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

Hatchling chosen: single-file dynamic version, no `setup.py`, native force-include for
`replay_main.py` (importlib.resources needs a real on-disk path).

> **Superseded by [ADR-10](DECISIONS.md):** the `"bobframes/tests/data"` force-include line above is
> removed in the real `pyproject.toml` — the `.gitignore` negation makes those fixtures tracked, so
> `packages = ["bobframes"]` already ships them and the force-include only created duplicate wheel
> entries. The `replay_main.py` force-include stays.

> **Superseded by [ADR-12](DECISIONS.md):** the `[project.urls]` above (and the CHANGELOG link refs)
> are repointed from `mayhem-studios/bobframes` to `altpsyche/bobframes` in the real files — that is
> the actual remote where CI runs and v0.1.0 publishes. The author email is unchanged.

> **Extended for v0.4+ by [ADR-17](DECISIONS.md):** the core `dependencies` stays **pyarrow only**.
> v0.4/c30 adds `[project.optional-dependencies] query = ["duckdb>=1.0"]` so the SQL `query` verb is an
> opt-in extra (`pip install bobframes[query]`); the `schema` introspection verb ships in the
> pyarrow-only core. This block is annotated, not rewritten (frozen, append-only).

> **Extended for v0.2 by [ADR-26](DECISIONS.md):** the c07 config layer adds
> `tomli>=2.0; python_version<'3.11'` (stdlib `tomllib` is 3.11+; the `>=3.10` floor stays because
> qrenderdoc embeds Python 3.10). `tomli` is a build-time TOML parser, not a data dep — the data path
> stays pyarrow-only. Annotated, not rewritten.

> **Extended for v0.2 by [ADR-27](DECISIONS.md):** c08 ships `reports/design_tokens.toml` (the
> designer-editable CSS palette) + `reports/_tokens.py` loader, loaded with the same `tomllib`/`tomli`
> shim but kept SEPARATE from the c07 config (bundled-only, no deep-merge in v0.2). The wheel ships the
> token TOML the same way as `_default_config.toml` (tracked file under the package, ADR-10; verified
> 0 dups). Annotated, not rewritten.

> **Extended for v0.2 by [ADR-29](DECISIONS.md):** c09 adds `derives/classifier.py` (the single,
> state-capable draw-classification API) + `derives/draw_classifier.toml` (UE default) +
> `derives/presets/{unity,godot,custom-template}.toml`, loaded with the same `tomllib`/`tomli` shim.
> Classification is now an analysis-layer concern: the replay stage's drifted `_classify_draw` (which
> fed only the dead `passes.draws_by_class_*`) is **deleted** — replay emits facts only (§4 ingest →
> render path unchanged; §21.9 holds by construction). The classifier preset TOMLs ship like the other
> bundled TOMLs (tracked under the package, ADR-10; verified 0 dups). Annotated, not rewritten.

> **Python 3.14 caveat (see DECISIONS / QUALITY_GATES):** the `3.14` classifier is intentionally
> omitted above. `pyarrow>=17` has no cp314 wheels, so a `{3.14, pyarrow 17}` install fails. Add
> 3.14 only once a compatible pyarrow floor is set for it. CI matrix tops out at 3.13 for v0.1.

## 4. CLI surface

Single binary, argparse subparsers. `<root>` is **positional, default `.`**, consistent across all
verbs. Long-flag-only (no `-r`/`-a`).

| Verb | Args | Behavior |
|---|---|---|
| `ingest` | `[root=.] [--area X] [--label Y] [--capture N] [--force] [--workers K] [--pixel-grid 4] [--render-only] [--verbose]` | Full pipeline: export, parse, replay, parquetize, derive, manifest, commit, catalog, render |
| `render` | `[root=.] [--area X] [--label Y]` | Render-only; rebuild HTML + catalog from existing Parquet |
| `ab` | `[root=.] --baseline-label X --compare-label Y [--baseline-date D] [--compare-date D]` | All 6 reports for one drop pair under `_reports/ab/<pair>/` |
| `report` | `[root=.] <name>` (draws-by-class, trend, instancing, pass-gpu, shader, overdraw, dashboard) | Build one named report |
| `catalog` | `[root=.]` | Rebuild `_data/_catalog.parquet` only |
| `lint` | `<file>...` | Lint HTML/MD against banlist |
| `check` | `[--write-config]` | Print resolved paths for `renderdoccmd` + `qrenderdoc`; non-zero on missing. (`--write-config` is v0.2, with the config layer.) |
| `version` | (none) | `bobframes 0.1.0  schema 3  pyarrow 17.0.0` |
| `serve` | `[root=.] [--port 8000] [--bind 127.0.0.1]` | `http.server`-based static preview |
| `smoke` | `[--data DIR]` | End-to-end against `--data` (defaults to bundled synthetic) |

Not exposed: `probes/whatif.py` (manual qrenderdoc-side; README "Advanced"). No `init`/`config`
verb. `preview` (gallery, no data) + `export-tokens` (`--format toml|json|css`, stdout) +
`render --watch` (alpha mtime poll) landed in **c08** (designer track, ADR-27).

**Defaults:**
- `bobframes` (no args) → `--help`, exit 0. `bobframes <verb>` → `root=.`.
- ANSI color: off by default; auto-enable when `sys.stdout.isatty()` and `NO_COLOR` unset. No
  `colorama` dep — raw ANSI; Win10+ conhost handles it.
- Progress: keep `[HH:MM:SS] message` log lines. No bars/spinners.
- Logging: stdlib `logging`, INFO default, `--verbose` per-subparser → DEBUG.

**Exit codes:** `0` success · `1` pipeline/build failure (lint hit, replay nonzero, schema
mismatch) · `2` user error (argparse-native) · `3` external tool missing · `4` interrupted
(Ctrl+C, timeout).

## 5. External tool discovery

In v0.1 this stays as the **existing inline discovery** in `rdcmd.py` and `qrd_harness.py` (hardcoded
Arm 2026.2 path + `PATH`). The single-resolver design below is the **v0.2 target**
([c06](commits/v02/c06_tool_resolver.md)); recorded here so the contract is visible.

```
resolve_tool(name)  where name ∈ {"renderdoccmd", "qrenderdoc"}
  1. env var      BOBFRAMES_RENDERDOCCMD / BOBFRAMES_QRENDERDOC
                  (legacy RENDERDOCCMD / RENDERDOC_QRENDERDOC accepted, one-shot deprecation log)
  2. config file  [tools] section, key = name
  3. PATH         shutil.which(name + ".exe")
  4. known paths  Windows install paths (below), glob latest Arm Studio version
  5. raise        bobframes.errors.ToolNotFound  (exit code 3)
```

**Known install paths (Windows):**
- `C:/Program Files/Arm/Arm Performance Studio */renderdoc_for_arm_gpus/{renderdoccmd,qrenderdoc}.exe`
  (glob; pick latest by directory-name sort — fixes the quarterly version bump, H-7)
- `C:/Program Files/RenderDoc/{renderdoccmd,qrenderdoc}.exe`
- `%LOCALAPPDATA%/Programs/RenderDoc/{renderdoccmd,qrenderdoc}.exe`

**Error message (exit 3):**
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

The config layer is **v0.2** ([c07](commits/v02/c07_toml_config.md)). v0.1 runs with built-in
defaults only. Target shape recorded here.

**Config file** (optional). Lookup precedence — first found wins, no merging:
1. `$BOBFRAMES_CONFIG`  2. `<root>/.bobframes.toml`  3. `%APPDATA%/bobframes/config.toml`

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

**State / cache:** `_reports/_cache/*.parquet` — per-project (unchanged). No per-user cache dir.

**Env var renames** (legacy accepted one release; the rename is [c10](commits/v02/c10_env_rename.md)):
- `RDC_KEEP_STAGE` → `BOBFRAMES_KEEP_STAGE`
- `RDC_PIXEL_GRID` → `BOBFRAMES_PIXEL_GRID`
- `RDC_ROOT` → **eliminated**; pass `--project-root` as explicit CLI arg to `parse_init_state`.
- `RDC_INSIDE_ARGS` → **kept verbatim** (qrenderdoc ↔ harness wire protocol).

**Precedence rule:** CLI flag > env var > config file > built-in default.

> **Clarified for v0.2 by [ADR-25](DECISIONS.md):** "first found wins, no merging" governs *user-file
> selection* (pick one of the three locations). The bundled `_default_config.toml` is always the base
> and the selected user file is **deep-merged on top** (per-key; user wins), so a user overrides one
> key without restating the rest. Implemented in c07. Annotated, not rewritten.

## 9. Portability + path audit

Per-file changes are captured in the relevant commit docs (notably
[c11](commits/v01/c11_cli_dispatcher.md), [c12](commits/v01/c12_replay_importlib.md),
[c14](commits/v01/c14_rename.md), and the v0.2 de-hardcoding commits). Anchors of note, by symbol:

- `pipeline.py` (was `run.py`): the `python -m _analysis.parsers.parse_init_state` subprocess
  literal and the `replay_main.py` path construction are load-bearing — see c12/c14.
- `replay/replay_main.py`: **no code change.** Schema column tuples stay duplicated by design
  (qrenderdoc-side import unreliable); drift caught at parquetize header-verify and by the c13 CI
  test. Add a top-of-file comment citing the policy.
- `paths.py`: `drop_dir_rel` already normalizes via `.replace('\\', '/')` for catalog storage. No
  change needed for portability.

## 12. Cross-platform

> **Superseded for v0.6+ by [ADR-18](DECISIONS.md):** the "v1 is Windows-only" statement below holds
> through v0.5. v0.6/c36 adds Linux/macOS support — per-OS tool locator (extends c06 `resolve_tool`) +
> a platform-dispatched process-tree kill (`os.killpg`+`start_new_session` on POSIX) + a relaxed
> `_cmd_check` gate (H-38). See [ROADMAP.md](ROADMAP.md). This section is annotated, not rewritten
> (frozen, append-only).

**v1 is Windows-only.** Documented in README, classifier, error message.
- `bobframes check` on non-Windows: exit 3, message: `bobframes v1 is Windows-only (qrenderdoc
  replay requirement). Track GH issue #N for Linux/macOS support.`
- `pyproject.toml` classifier `Operating System :: Microsoft :: Windows` only.
- No `--no-replay` flag; no static-only mode. v0.2+ may revisit.
- Code uses `os.path.join` everywhere; catalog rel-paths normalized to `/`.
