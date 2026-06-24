# BobFrames

RenderDoc capture pipeline: ingest, analyze, render. Point it at a folder of `.rdc` captures and it
produces `_data/` (Parquet tables) plus `_reports/` -- static, offline, `file://`-safe HTML you can
browse: a one-page **build-health summary**, a reports dashboard, per-aspect reports (overdraw, shader
hotlist, instancing, draws-by-class, pass-GPU, cross-run trend), and a per-drop drill-down data browser.
Reports are self-contained, printable, Ctrl-F-able, and work with JavaScript off. Windows-only in v1.

> Built for **Mayhem Studios** -- see [Built for Mayhem Studios](#built-for-mayhem-studios) below.

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

## Guided mode (recommended for QA / product)

Not comfortable in a terminal? `bobframes ui` opens a local-web control panel in your browser that
drives the whole pipeline point-and-click: detect the RenderDoc tools, pick a capture folder, ingest
with live per-capture progress, then open / serve / package the report or compare two runs.

```
pipx install bobframes
bobframes ui             # opens http://127.0.0.1:8765 in your browser
```

The panel binds `127.0.0.1` only and carries a one-time session token in the opened URL, so only your
own browser can drive it. It is stdlib-only -- one `pipx install` gives every feature, no extra setup --
and it emits no report files of its own; it just runs the same verbs as the CLI.

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
| `render [root] [--area X] [--label Y] [--accent OKLCH] [--accent-data OKLCH] [--watch]` | Rebuild HTML and catalog from existing Parquet. `--accent`/`--accent-data` re-hue the theme for this render (ADR-45). `--watch` re-renders on `design_tokens.toml`, chrome, or `.bobframes.toml` edits (alpha). |
| `ab [root] --baseline-label X --compare-label Y` | All reports for one drop pair under `_reports/ab/<pair>/`. |
| `report [root] <name>` | Build one named report (summary, draws-by-class, trend, instancing, pass-gpu, shader, overdraw, dashboard). `summary` is the exec build-health one-pager. |
| `catalog [root]` | Rebuild `_data/_catalog.parquet` only. |
| `lint <file>...` | Check HTML or markdown against the banlist. |
| `check` | Print resolved tool paths; non-zero when a tool is missing. |
| `serve [root] [--port 8000] [--bind 127.0.0.1]` | Static preview via the stdlib HTTP server. |
| `ui [root] [--port 8765] [--bind 127.0.0.1] [--no-open]` | Guided local-web control panel (ADR-47): ingest / render / package / A-B / open / serve / scaffold from a browser, with live progress. Localhost-bound + per-session token; emits no report output of its own. |
| `package [root] [--inline] [--light] [--redact] [--redact-paths {strip,fail}] [--out PATH] [--run KEY] [--no-summary-file] [--stage]` | Bundle a rendered tree into a shareable `<project>-<rundate>-report.zip` + a standalone `<project>-<rundate>-summary.html`, both written OUTSIDE `<root>` (non-mutating). `--redact` scrubs device/host provenance + absolute paths for external sharing. |
| `preview [root] [--accent OKLCH] [--accent-data OKLCH]` | Render the chrome gallery to `_reports/_chrome_preview.html`; no capture data needed. `--accent` previews a theme override before you commit it. |
| `export-tokens [--format toml\|json\|css] [--theme-template]` | Print the design tokens to stdout in the chosen format. `--theme-template` emits a paste-ready `[theme]` block for `.bobframes.toml`. |
| `smoke [--data DIR]` | End-to-end check; render-only against the bundled fixture when `--data` is omitted. |
| `version` | Print `bobframes`, schema, and pyarrow versions. |

`<root>` is positional and defaults to `.`. Flags are long-form only. Exit codes: `0` success,
`1` pipeline or build failure, `2` usage error, `3` external tool missing, `4` interrupted.

## Sharing a report

`bobframes package <root>` turns a rendered tree into two friendly artifacts beside it (it only READS
`<root>`):

- `<project>-<rundate>-report.zip` -- the full explorable tree. **Extract the whole folder before
  opening** (`index.html`, then the Build Health Summary): the pages link each other and a shared
  `_assets/` folder by relative path, so opening one file straight out of the zip breaks those links.
- `<project>-<rundate>-summary.html` -- a standalone, self-contained one-pager. Email it, double-click
  it, or `Ctrl-P -> Save as PDF`; no unzip needed. (Its deep links into the reports only resolve when
  the zip is shipped alongside.)

The zip DEFAULTS to **shared assets**: the ~95 KB of chrome (font + CSS + JS) lives once in `_assets/`
and every page links it, so a multi-run bundle is markedly smaller. Because the pages share that
folder, **no single page is portable on its own** -- keep the extracted folder together, or send the
standalone `summary.html` when you need just one file. `--inline` opts out and makes each page
self-contained (larger, but any single report file is portable). `--light` bundles only `index.html`
+ the top-level reports (no drill pages or data) for a quick "read, don't drill" share.

### Sharing externally -- `--redact`

`bobframes package <root> --redact` produces a bundle safe to hand to someone outside your team. It
scrubs the GPU / driver / CPU / OS + capture-tool versions from every page's device strip (replaced with
`redacted`), drops the raw provenance sidecars (`_manifest.json`, `frame_metadata.jsonl`) from the
bundle, and replaces absolute Windows paths (`C:\...`) with `<path redacted>` across the pages and the
downloadable CSVs. Redaction re-renders the tree, so `--inline --redact` is no longer a fast copy.

- `--redact-paths=strip` (default) -- replace the path tokens; the bundle stays usable on a real capture.
- `--redact-paths=fail` -- a CI completeness check: exit nonzero (don't write the zip) if any absolute
  path remains in a rendered page, so a leak fails the build.

**Caveat:** the pages and the downloadable CSVs are sanitized, but the **binary `.parquet`** tables still
contain resource paths (they can't be string-edited safely) -- strip `_data/` if the parquet itself must
leave your team. UNC (`\\host\share`) and forward-slash (`C:/...`) paths are not auto-stripped.

## Customizing reports

The look is shadcn-clean, neutral, and flat by default. Two ways to re-color it:

### Pip installs -- re-hue without editing source (recommended)

`pip install bobframes` puts the design tokens in site-packages, where edits are lost on upgrade -- so
re-hue the accent / status / chart colors through the config cascade instead:

- **Persistent:** add a `[theme]` section to `.bobframes.toml` in your capture root (or
  `%APPDATA%/bobframes/config.toml`). `bobframes export-tokens --theme-template` prints a ready-to-paste
  starter with just the overridable color knobs.
- **One-shot:** `bobframes render . --accent '<oklch>'` (and `--accent-data '<oklch>'`) -- the top
  precedence tier (CLI > env > config > bundled default). `bobframes preview --accent '<oklch>'` previews
  it with no capture data.

Only color hues (accent, the four status colors, the draw-class + chart palette) are overridable; layout,
spacing, type, and the table engine stay bundled, so an override can never desync the rendering. A bad or
non-color value warns and is ignored. `--watch` live-reloads on `.bobframes.toml` edits too.

### Source checkouts -- edit the bundled tokens

The full palette lives in `bobframes/reports/design_tokens.toml` (colors, spacing, type, motion, radius,
and base layout sizes). The CSS variable name is fixed by its key: `surface_0` becomes `--surface-0`,
`accent_primary` becomes `--accent-primary`.

```
bobframes preview                 # writes _reports/_chrome_preview.html (every component, no data)
# edit a value in design_tokens.toml
bobframes preview                 # under a second; reload the page in a browser
bobframes render C:\captures      # apply the change to real reports from existing Parquet
```

`bobframes render --watch` re-runs render-only whenever `design_tokens.toml`, a chrome module, or
`.bobframes.toml` changes (alpha; a 500ms poll, no extra dependency). `bobframes export-tokens --format
css` prints the live `:root` block; `--format json` the nested table; `--format toml` the file itself.

## External tools

The export stage runs `renderdoccmd convert`; the replay stage runs `qrenderdoc --python`. bobframes
resolves both from (in order) a config file (`.bobframes.toml`), version-globbed Arm Performance Studio
install paths, and `PATH`. Install RenderDoc / Arm Performance Studio anywhere on those, or point a
config entry at it. Run `bobframes check` to see what was resolved.

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
- TOML config (`.bobframes.toml`), an externalized draw classifier, and design-token theming
  (`[theme]` / `--accent`) shipped in v0.2.6. `bobframes package` produces shareable, optionally
  redacted bundles (see [Sharing a report](#sharing-a-report)).

## Built for Mayhem Studios

BobFrames is built and maintained for **Mayhem Studios** -- it powers the studio's GPU
capture-analysis and frame-performance work, and is open-sourced here for the wider RenderDoc and
graphics community.

If BobFrames helps your work, please **support Mayhem Studios** -- the studio that makes this tool
possible. Follow the studio, play and wishlist our games, and tell a friend who fights frame times.
A on the [GitHub repo](https://github.com/altpsyche/bobframes) helps too. Thank you.

## License

MIT. See [LICENSE](LICENSE).
