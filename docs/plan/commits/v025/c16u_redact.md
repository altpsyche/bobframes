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
