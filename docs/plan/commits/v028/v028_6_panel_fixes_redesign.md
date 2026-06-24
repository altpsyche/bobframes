# v028_6 -- panel bug fixes + guided UI redesign + browser sign-off     release: v0.2.8 · phase: ui

> Surfaced by the first real end-to-end browser test against a live rendered corpus. Two latent bugs
> (the panel JS never ran in ANY browser; the A/B result link vanished) plus the user-approved full UI
> redesign and the browser visual sign-off that v028_5 had deferred. Still zero deps; still no report
> HTML (golden gate / ADR-37 untouched).

## Why this commit exists
The v028_1..-5 panel passed every pytest because the tests exercise the HTTP surface in Python; NONE
executed the page's JavaScript. The first time a human opened the panel in a browser, it was broken.
This commit is the "actually run it" pass (ADR-23: don't claim done without the real gate).

## Bugs fixed (root-caused, with regression locks)
- **Panel JS failed to parse in every browser (since v028_2).** `control_page()` was a normal
  triple-quoted string, so the embedded JS `"\n"` was turned by Python into a REAL newline mid-string-
  literal -> the entire `<script>` was a syntax error -> `loadState()` never ran -> tools/drops/runs/A-B
  all stuck at placeholders. Fix: the page literal is now an **r-string** (`_CONTROL_PAGE = r"""..."""`).
  Lock: `test_ui_smoke.test_control_page_js_string_literals_are_not_broken_by_python_escapes` parses the
  served `<script>` and asserts no double-quoted JS literal is split by a raw newline (a known-broken
  fragment must carry a literal backslash-n); the JS is also `node --check`-validated during dev.
- **A/B result link vanished.** The generic stream "done" handler called `loadState()` on success, which
  rebuilt the A/B card (`renderRuns` cleared `ab_msg`) ~50 ms AFTER the link was written, so it flashed
  and disappeared. Fix: the generic handler no longer refreshes; callers refresh where state actually
  changes (ingest/render/package via `refreshOnOk`), and A/B's `onDone` shows the link without a refresh.
- **`/api/open` generalized** to accept an optional relative `path` (normalized + validated to stay
  inside root; traversal -> 400; default = root index) so the A/B card can open the pair's
  self-contained `_reports/ab/<base>_vs_<cmp>/summary.html`. Tests: `test_open_relative_path_opens_ab_page`
  + `test_open_rejects_path_traversal`.

## Guided UI redesign (user-approved: "full layout redesign")
The control page was reworked from a flat stack of look-alike cards into a clear top-to-bottom flow:
- **Hierarchy:** section cards (RenderDoc tools / Captures / Generate / Share & explore / Compare) each
  with a header + a status **badge** (`READY` / `7 AREAS` / `missing` / `empty`); **primary** (filled)
  vs **secondary** (outline) buttons so each section has one obvious action. Step numbers were added then
  removed per user feedback.
- **Plain language:** "Ingest captures" / "Rebuild reports only" / "Open report" / "Package for sharing";
  jargon (`force`, `workers`, accent) moved behind an **Options** disclosure; the scaffold behind
  **Create a capture folder**; the `...` placeholder dots replaced by real status.
- **Results surfaced:** every finished action writes a prominent **result box** -- Package shows the zip
  path (parsed from the streamed log), Serve a clickable URL, A/B the persistent "open comparison" link.
- **Progress co-located:** each streamed action (ingest/render/package/ab) logs into ITS OWN progress
  panel directly under the button clicked (the old single shared log lived in a far-away card).
- **Final-review polish:** action buttons **disable** when their inputs are absent (Ingest needs tools +
  captures; the report actions need ingested data) with explanatory `title` tooltips; tool paths are
  `os.path.normpath`-tidied for display (mixed `/`+`\` -> consistent).
- Styling stays on the shared design tokens (`chrome.design_tokens_css()`, v028_5); neutral theme.

## Gates / Done when
- The panel runs in a real browser: state loads, all five sections work, the A/B link persists and opens.
- `pytest -m "not browser"` green; `pytest -m golden_env` byte-parity unchanged (panel emits no report HTML).

## As-built (DONE 2026-06-24)
- VERIFIED: `node --check` of the served `<script>` (dev) -> clean; ui suite green (test_ui_share 9 +
  test_ui_smoke incl. the JS-integrity lock + test_ui_ab_theme 10 + state/security); full
  `pytest -m "not browser"` -> **401 passed / 2 deselected** (was 398 at v028_4; +3). `-m golden_env`
  unaffected; no golden refresh; no new dependency.
- **BROWSER SIGN-OFF (completes v028_5's deferred item):** drove the screenshot harness (`tools/shoot.py`)
  against the LIVE panel over http (not a static file) on the real corpus
  `C:\Users\vsiva\Downloads\RDCs\RDC mainline  capture` (7 areas, 4 runs) -- light + dark both clean
  (numbered + final layouts captured and reviewed). Manual end-to-end on the already-rendered tree (no
  ingest): state loads, A/B render + open-comparison link works, open/serve/package drive the verbs.
- No new ADR (rides ADR-47/45/23).

## v0.2.8 epic -- COMPLETE (release-ready, browser-verified)
Spine v028_0..-6 all DONE. Next (gated on authorization): the v0.2.8 PR off
`feat/v028-ui-control-panel` -> tag `v0.2.8` -> ci.yml publish -> PyPI. CARRY-OVER: R-19 (own commit).
