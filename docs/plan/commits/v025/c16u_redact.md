# c16u — `--redact` at the data seam     release: v0.2.5 · phase: packaging

> Scrub sensitive provenance (gpu/driver/cpu/os + tool versions) and absolute paths from a shared bundle,
> at the structured DATA seam (not an HTML regex), strip-by-default so it stays usable on real captures.
> Rides ADR-40.

## Goal
`bobframes package --redact` produces a bundle safe to share externally: no device/host provenance values,
no absolute paths, with no false positives and no "can't redact this capture" footgun.

## Depends on
c16s (the `package` verb) + c16r (the seam, reused for provenance re-emission).

## Scope
1. **Provenance at the data seam.** Give `chrome.provenance_strip(host_info, tool_versions, *, redact=False)`
   a redact mode that emits `<div class="device-strip">redacted</div>` (or omits the fields). The packager
   re-emits the affected pages' provenance from the manifest's `host_info`/`tool_versions` via this seam -
   keyed on data we own, zero regex, no false positives. Scrubs gpu/gpu_driver/cpu/os + renderdoccmd/
   qrenderdoc in one shot, and the drill's `gl_renderer` reuse of `.device-strip` (intentional - device info).
2. **Absolute paths, strip-by-default.** A `[A-Za-z]:\\[^\s"'<>|]+` (+ UNC `\\\\...`) token is STRIPPED to
   `<path redacted>` by default (usable on a real capture that carries a path in a driver/renderer string),
   replacing only the matched token, never surrounding bytes, never inside the base64 font / `_assets`.
   `--redact-paths=fail` is the explicit CI mode (report-and-fail on any residual). The scan is a post-scrub
   **completeness assertion** (did the device-strip scrub miss a path hiding in a value?), not a
   links-are-relative guard.
3. **Composes with `--shared-assets`** (the `shared_redacted` combination is exercised).
4. **Tests:** extend `tests/test_package.py` + `make_package_golden.py` with the `redacted/` golden tree.
   Assert: no page carries a device field value (`gpu <strong>`, `driver <strong>`, cpu/os/tool versions);
   the fixture's known device values appear nowhere; the abs-path completeness scan is clean;
   `--redact-paths=fail` exits nonzero on a PLANTED leak. If the synthetic provenance is empty (renders no
   device strip), add a unit test on crafted input (a device-strip + an abs path) so the scrub is exercised,
   and record the fixture gap (G/finding) per ADR-23.

## Constraints
- Redact at the structured source, NOT by re-parsing rendered HTML; default render untouched.
- Deterministic, fixed-pattern string ops; ASCII; the redacted tree gets its own golden.
- Default `--redact` STRIPS (does not fail) so it is usable on real captures; fail-closed only in CI mode.

## Done when
- `bobframes package --redact <synthetic>` produces the `redacted/` tree matching golden.
- `pytest tests/test_package.py` green: no device value present; abs-path completeness clean;
  `--redact-paths=fail` exits nonzero on a planted leak; `shared_redacted` combination green.
- QUALITY_GATES §21.1s extended (redacted variant).

## Closes
The privacy/redaction gap for external sharing. Next: c16v (multi-capture per-frame normalization).

## As-built (2026-06-04; rides ADR-40, no new ADR; recorded per ADR-23)
- **Provenance at the data seam.** `chrome.provenance_strip(host_info, tool_versions, *, redact=False)`
  emits `<div class="device-strip">redacted</div>`; `redact` threaded through the SAME render seam as
  c16t's sink/build_ts — `orchestrator.render_all_reports` -> the 8 `build()` + dashboard + per-run,
  `ab.render_pair`, `template.render_drop` (the drill `gl_renderer` strip), and `trend_table`'s in-body
  per-drop device chips. All default `False` -> default render BYTE-IDENTICAL (test_parity +
  test_parquet_parity green, NO refresh; the `shared/` golden is byte-unchanged).
- **Whole-tree, drop-sidecars (the planning design fork; user-chosen).** The bundled raw `_data` also
  leaks device values, so a redacted bundle EXCLUDES `_manifest.json` + `frame_metadata.jsonl` wholesale
  (no viewable page links them; robust to manifest schema growth). Verified on real Perf: `grep` of the
  extracted tree for the device values + drive-letter paths is clean; 0 sidecars present.
- **`--redact` FORCES a re-render** (structural transform): `--inline --redact` re-renders at the INLINE
  sink + pinned `build_ts` (its "built" line now shows the run date, a new divergence vs the non-redact
  `--inline` copy — recorded). `_render_shared` was generalized to `_render_tree(sink, build_ts,
  redact)` (assets written only for the REF sink); `(REF, redact=False)` is byte-identical to c16t. The
  standalone summary stays self-contained + redacted (the INLINE staging copy; a dedicated INLINE render
  for the shared bundle, done after the REF copy is zipped so the bundle keeps the REF summary).
- **Abs-path strip — drive-letter only (build-time correction, recorded).** The c16u doc said "+ UNC
  `\\…`", but real-Perf data exposed that JSON-escaping makes a blanket UNC match a FALSE POSITIVE: a
  relative shader ref `"shader_src\\2192.glsl"` (file bytes `shader_src\\2192.glsl`) was mangled to
  `shader_src<path redacted>`. The c16u goal demands "no false positives", so `_ABS_PATH` matches
  drive-letter `[A-Za-z]:\\…` ONLY (unambiguously absolute; base64/`data:`/`http:` and relative
  backslash paths are never touched). UNC + forward-slash drive paths + binary-parquet path columns are
  recorded limitations (FINDINGS G-31). `strip` (default) rewrites tokens across all bundled text;
  `fail` (CI) scans the rendered surface (HTML + `_pagedata`) and raises BEFORE the zip is written.
- **Tests:** 262 -> 277 green (+15 in `tests/test_package.py`): redacted + shared_redacted golden-match
  (new `golden_package/{redacted,shared_redacted}/` via `make_package_golden`), generic no-device-value
  scan (footgun net for a future report forgetting `redact=`), sidecar-exclusion + no-dangling-links,
  the `_data`-text denylist→tripwire, strip-clean, redacted determinism + non-mutation, and crafted-input
  units (drive stripped + relative/UNC/font preserved; `fail` raises on a planted leak; `--redact-paths=fail`
  requires `--redact`; `provenance_strip(redact=True)`).
- **Verified:** real-Perf `bobframes package c:/tmp/perf --redact` — 2701 files, 0 device-value/abs-path/
  sidecar residuals across 967 text files, shader refs preserved; `--redact-paths=fail` exit 0 (clean) and
  raises on a planted leak. Browser (headless Chrome, file://): the shader_hotlist report renders with the
  `redacted` strip + styled tables; a drill builds 493 VTable rows (JS intact) with its `gl_renderer`
  device strip reading `redacted`. QUALITY_GATES §21.1s extended; FINDINGS G-31 added.
