# c06a — de-harden writer-dependent bytes out of the drill HTML (D-8)   release: v0.2 · phase: De-hardcoding

## Goal
Stop the rendered HTML from carrying pyarrow-writer-dependent bytes, so the golden snapshot can hold
across the pyarrow version range instead of only the canonical cell. This removes the **fixable half**
of the divergence that forced [ADR-11](../../DECISIONS.md)'s one-env parity pin (D-8). Follows the
no-patch-fix rule ([ADR-23](../../DECISIONS.md)): fix the content, do not keep masking the gate.

## Depends on
[c06](c06_tool_resolver.md). Audit-opened (2026-06-01). Output-changing → refreshes the golden.

## Root cause
`html.template._file_size_label(path)` renders `os.path.getsize(<table>.parquet/.csv)` as `KB`/`MB`
into the per-drop drill page; render-only rewrites the derived Parquet with the *local* pyarrow, so
the on-disk size differs by writer version (pa17 `15.1 KB` vs pa21 `12.3 KB`). A second size render
(`os.path.getsize(...) // 1024` → `…K`) exists in the same module — both must be swept.

## Files
- `html/template.py` — replace every on-disk-size render that reaches the golden HTML with a
  **deterministic, data-derived** figure. Preferred: **row count** (already available from the table
  metadata; meaningful and writer-independent). Audit all `os.path.getsize` callsites in this module
  (`_file_size_label` + the `// 1024` label) and confirm none of the survivors feed rendered HTML.
- `tests/data/golden/**` — refresh the affected drill page(s) on the canonical cell (py3.12 + pa21).

## Changes
- Swap size-on-disk → row count (or another deterministic value) in the drill table rows.
- Re-bake the golden for the changed pages; document the byte delta in the commit body.

## Done when
- No `os.path.getsize`-derived value reaches any rendered `.html` (grep gate over `html/`).
- Golden refreshed; `test_parity` green. NOTE: parity stays pinned to one cell for now — the
  `pass_gpu` `pct_share` 1-ULP-at-`.2f` divergence is numpy-build-level and remains accepted under
  ADR-11; D-8 only removes the writer-KB half. Record that the KB divergence is gone.
- The `--ignore=test_parity` matrix split (ci.yml) is unchanged this commit (still needed for the
  float half); note in the commit body whether the floor for un-pinning is now just D-(float).

## Closes
D-8 (the writer-dependent-bytes half). Shrinks the ADR-11 divergence surface to the float-ULP case.
