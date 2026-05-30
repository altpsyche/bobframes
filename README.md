# BobFrames

RenderDoc capture pipeline: ingest, analyze, render. Point it at a folder of `.rdc` captures and it
produces `_data/` (Parquet tables) plus `_reports/` (static HTML you can browse). Windows-only in v1.

## Requirements

- Windows 10 or later (the replay stage drives `qrenderdoc`, which is Windows-only in v1).
- Python 3.10 - 3.13.
- RenderDoc 1.x, or Arm Performance Studio, providing `renderdoccmd` and `qrenderdoc` on disk.

## Install

```
pipx install bobframes
bobframes check
```

`bobframes check` prints the resolved paths for `renderdoccmd` and `qrenderdoc` and exits non-zero if
either is missing, so you can confirm the toolchain before a long ingest.

## Quickstart

```
cd path\to\captures      # a folder of <Area>\<YYYY-MM-DD[_label]>\*.rdc
bobframes ingest .       # export, parse, replay, parquetize, derive, render
bobframes serve .        # open a local static preview of the reports
```

`ingest` writes Parquet under `_data/` and HTML under `_reports/`. Re-run `bobframes render .` any
time to rebuild the HTML from existing Parquet without re-replaying captures.

## Commands

| Command | Purpose |
|---|---|
| `ingest [root] [--area X] [--label Y] [--capture N] [--force] [--pixel-grid 4] [--render-only]` | Full pipeline: export, parse, replay, parquetize, derive, manifest, commit, catalog, render. |
| `render [root] [--area X] [--label Y]` | Rebuild HTML and catalog from existing Parquet. |
| `ab [root] --baseline-label X --compare-label Y` | All reports for one drop pair under `_reports/ab/<pair>/`. |
| `report [root] <name>` | Build one named report (draws-by-class, trend, instancing, pass-gpu, shader, overdraw, dashboard). |
| `catalog [root]` | Rebuild `_data/_catalog.parquet` only. |
| `lint <file>...` | Check HTML or markdown against the banlist. |
| `check` | Print resolved tool paths; non-zero when a tool is missing. |
| `serve [root] [--port 8000] [--bind 127.0.0.1]` | Static preview via the stdlib HTTP server. |
| `smoke [--data DIR]` | End-to-end check; render-only against the bundled fixture when `--data` is omitted. |
| `version` | Print `bobframes`, schema, and pyarrow versions. |

`<root>` is positional and defaults to `.`. Flags are long-form only. Exit codes: `0` success,
`1` pipeline or build failure, `2` usage error, `3` external tool missing, `4` interrupted.

## External tools

The export stage runs `renderdoccmd convert`; the replay stage runs `qrenderdoc --python`. v1 looks
for both at a baked Arm Performance Studio install path and on `PATH`. A config file and a
tool-resolver with version globbing arrive in v0.2; until then, install RenderDoc where v1 expects it
or put the executables on `PATH`. Run `bobframes check` to see what was resolved.

## Output layout

```
<root>/
  index.html                          root catalog view
  <area>/<drop>/                      raw RDC inputs (left untouched)
  _data/                              pipeline outputs
    _catalog.parquet (+ .csv, .json)
    _global_entities.parquet (+ .csv)
    _query_examples.md
    <area>/<drop>/                    per-drop data (29 Parquet tables)
      *.parquet (+ matching .csv)
      _manifest.json, _resource_labels.json
      shader_src/*.glsl, jsonl sidecars
      done.marker
  _reports/                           rendered HTML
    *.html (dashboard + reports)
    ab/<pair>/*.html
    drill/<area>/<drop>/index.html    per-drop browser
    _cache/
```

The catalog stores each drop's path relative to `<root>` for portability.

## Migrating from `_analysis`

v1 is a hard rename of the older project-embedded `_analysis` package, with no compatibility shim:
`python -m _analysis.*` stops working once `bobframes` is installed. Map old invocations to new ones:

| Old (`_analysis`) | New (`bobframes`) |
|---|---|
| `python -m _analysis.run --root . --area X --label Y` | `bobframes ingest . --area X --label Y` |
| `python -m _analysis.reports.ab --root . --baseline-label X --compare-label Y` | `bobframes ab . --baseline-label X --compare-label Y` |
| `python -m _analysis.lint <file>` | `bobframes lint <file>` |
| `python -m _analysis.tests.smoke` | `bobframes smoke` |

## Troubleshooting

| Symptom | Resolution |
|---|---|
| `renderdoccmd not found` (exit 3) | Install RenderDoc or Arm Performance Studio, or put the executable on `PATH`; confirm with `bobframes check`. |
| `qrenderdoc` replay hangs | v1 kills the replay process tree on timeout and records `capture_status='replay_failed'` for that capture; the rest of the drop still completes. Re-run with `--force` to retry. |
| Lint failure during render | The emitted HTML contains a banned token. Run `bobframes lint <file>` to see the line and label. |
| `schema mismatch` (exit 1) | A drop's `_manifest.json` schema version differs from the installed schema. Rebuild it with `bobframes ingest --force` (the v1 schema-migration path; see G-3). |
| Permission denied on `_data` | Close any viewer holding a Parquet open, then re-run; writes are staged and renamed atomically. |

## Advanced

- A/B reports: `bobframes ab . --baseline-label OLD --compare-label NEW` builds a side-by-side set.
- Programmatic use: import `bobframes.schemas`, `bobframes.discovery`, and `bobframes.paths` to drive
  table lookups, drop discovery, and path resolution from your own scripts.
- `bobframes/probes/whatif.py` is a manual qrenderdoc-side probe and is not wired as a CLI command.
- A TOML config file, an externalized draw classifier, and design-token theming are planned for v0.2.

## License

MIT. See [LICENSE](LICENSE).
