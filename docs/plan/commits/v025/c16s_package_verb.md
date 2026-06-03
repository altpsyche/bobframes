# c16s — the `package` verb + the shareable bundle     release: v0.2.5 · phase: packaging

> One command turns the rendered tree into a friendly shareable artifact set: a `.zip` bundle PLUS a
> standalone single-file one-pager, with smart defaults + a recipient README so a non-expert gets the
> right thing without knowing any flags. Non-mutating, deterministic, output OUTSIDE the read tree.
> ADR-40 (packaging model + verb taxonomy + the friendly-UX defaults).

## Goal
`bobframes package <root>` produces, by default: `<project>-<rundate>-report.zip` (the full viewable tree)
AND `<project>-<rundate>-summary.html` (a self-contained one-pager you can email / double-click / print to
PDF without unzipping). Tier-0 (the standalone verdict) and tier-1 (the explorable bundle) in one command.

## Depends on
c16q (`summary.html` + `health.py` exist), c16r (the `head_assets` seam). Reuses `paths.*`,
`discovery._list_areas` underscore-skip, the current-run drop date (run model, ADR-35), the typed-error
path in `cli.main`, the `parquet_digest` + `normalize` golden helpers.

## Scope
1. **`bobframes/package.py`** `build(root, *, out=None, inline=False, light=False, redact=False,
   summary_file=True, stage=False, run=None) -> tuple[zip_path, summary_path]`. A non-mutating STREAM
   transform: read `<root>`, write a reproducible `.zip` (HTML transformed in memory, parquet/sidecars/
   `_pagedata` raw from source; no physical 2x staging unless `--stage`). c16s default delivery = **inline**
   (each page self-contained); c16t flips the default to shared-assets.
2. **Standalone one-pager (default ON).** Also write `<project>-<rundate>-summary.html` BESIDE the zip: a
   fully self-contained copy of the one-pager via `head_assets(INLINE)` (assets inlined, no `_assets/` link).
   The verdict / averaged KPIs / by-area table / inline-SVG charts all read standalone; its deep links (to
   the 6 reports / drill) resolve only when the bundle is shipped alongside (recorded - the page is
   self-contained for READING, not for drilling). `--no-summary-file` opts out.
3. **README.txt at the zip root** (ASCII, deterministic): "Extract this folder first - do NOT open files
   from inside the zip (links break). Then open index.html and start at the Build Health Summary."
4. **Run-derived naming:** `<project>-<rundate>-report.zip` + `<project>-<rundate>-summary.html` where
   project = `os.path.basename(root)` and rundate = the current run's `drop_date` (deterministic data from
   the run model, NOT wall-clock; filenames are not golden-gated). `--out` overrides the zip path/name.
5. **`--light` preset:** bundle only `index.html` + `_reports/*.html` (summary + 6 reports + dashboard),
   EXCLUDING `drill/` + `_pagedata/` + `_data/` -> a small "read, do not drill" bundle. Default = the full
   viewable tree. (One friendly choice replacing raw `--no-drill --no-data`, which stay as power-user
   escape hatches.)
6. **CLI:** `_cmd_package` next to `serve`: `package [root] [--inline] [--light] [--redact] [--out]
   [--no-summary-file] [--stage] [--run KEY]`. **No `--format` flag, ever** (taxonomy invariant, ADR-40).
   `--shared-assets` is accepted here as opt-in (becomes the default at c16t). Reproducible zip: sorted `/`
   arcnames, fixed `ZipInfo.date_time=(1980,1,1,0,0,0)`, pinned `ZIP_DEFLATED`, per-entry `writestr`.
   Prints ONE summary line: file count, bundle bytes, duplicated-chrome bytes (the ADR-37/41 measurement),
   the standalone-summary path, the zip path.
7. **ADR-40** appended: the non-mutating stream-transform model + the four-contract output-verb taxonomy +
   the friendly-UX defaults (shared-assets default [c16t], standalone summary, README, run-naming,
   `--light`) + the accurate-usage facts (extract-first; which files are portable).
8. **Tests:** `tests/test_package.py` + `tests/make_package_golden.py`. Goldens = trees EXTRACTED from the
   produced zips for `inline/` (default) + `light/`. Assert: tree == golden; source `<root>` digest
   unchanged before/after (non-mutation); build twice == itself; zip round-trips; `--format` rejected by
   argparse; **the standalone summary is self-contained** (no `_assets/` link, no `fetch(`/`type="module"`,
   no external ref); README present + ASCII; the zip + summary names match `<project>-<rundate>-...`;
   `--light` tree has no `drill/`/`_pagedata/`/`_data/`.

## Constraints
- Non-mutating: source tree byte-unchanged; both artifacts land OUTSIDE `<root>`.
- Gate the extracted tree, not zip bytes (zlib/Python variance); round-trip the zip in a lighter check.
- Deterministic naming: rundate from the run model's drop_date, never wall-clock. ASCII README.
- No new dependency (stdlib `zipfile`); the only wall-clock is the `[HH:MM:SS]` log prefix.

## Done when
- `bobframes package <synthetic>` writes the zip + the standalone summary OUTSIDE `<root>`; source digest
  unchanged before/after.
- `pytest tests/test_package.py` green: `inline/` + `light/` tree goldens; standalone summary self-contained;
  README + naming present; non-mutation; round-trip; `--format` rejected.
- The summary line reports the duplicated-chrome measurement + both artifact paths.
- ADR-40 appended; QUALITY_GATES §21.1s opened (inline + light + standalone-summary variants).

## Closes
The share-a-folder gap (the friendly tier-0 + tier-1 artifacts). Next: c16t (shared-assets default).
