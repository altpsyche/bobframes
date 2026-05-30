# c04 — centralize path literals in `paths.py`     release: v0.2 · phase: De-hardcoding

## Goal
Remove the scattered directory/file-name literals; make `paths.py` the single source. Pure cleanup —
the layout strings keep their current values, parity must stay byte-identical.

## Depends on
v0.1 shipped. Operates on the renamed `bobframes/` package.

## Files
- `paths.py` — add module constants: `DATA_DIR='_data'`, `REPORTS_DIR='_reports'`, `CACHE_DIR='_cache'`,
  `STAGE_DIR='_stage'`, `TMP_SUFFIX='_tmp'`, `DRILL_DIR='drill'`, `AB_DIR='ab'`,
  `MANIFEST_NAME='_manifest.json'`, `DONE_MARKER='done.marker'`, `INDEX_HTML='index.html'`.
- All modules using those literals (`pipeline`, `parquetize`, `manifest`, `catalog`, …) import them.

## Changes
Replace inline literals with the constants. Values unchanged (layout frozen per H-18/H-19,
[HARDCODE](../../reference/HARDCODE.md)).

## Done when
Golden parity + schema green (pure rename; output identical). `grep` shows no remaining bare
`'_data'`/`'_reports'`/`'_manifest.json'`/`'done.marker'` literals outside `paths.py`.

## Closes
H-18, H-19.
