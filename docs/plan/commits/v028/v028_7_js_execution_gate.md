# v028_7 -- CI JS-execution guard     release: v0.2.8 · phase: ui

> The HIGH-severity gap the v0.2.8 release itself exposed: pytest exercises the panel's HTTP surface in
> Python but NEVER parses or executes the served `<script>`, so the v028_2 bug (a Python-string newline
> split a JS literal -> the whole script failed to parse) shipped undetected through five commits and was
> only caught by a human opening a browser. This commit makes "the JS actually parses / runs" an
> automated gate. Still zero deps (`node`/Chrome are test/CI tools, never imported, never shipped); still
> no report HTML (golden gate / ADR-37 untouched).

## Why this commit exists
v028_6 fixed the bug and added a structural quote-balance heuristic (`test_ui_smoke`), but **nothing in
CI parses or runs the JS**. The only real verification was a one-time manual browser pass. A release
whose JS is human-verified-only is exactly the fragility ADR-23 forbids. Guard it before the tag.

## Scope (two gate layers with different reach -- ADR-23: be precise about what runs where)
- **`node --check` -- the automated CI gate (syntax/parse).** `tests/test_ui_js_parses.py` extracts the
  served `<script>` body from `control_page()` to a temp file and runs `node --check` (syntax-only, so
  browser globals `document`/`fetch`/`EventSource` are fine). `shutil.which("node")`-guards (skips
  locally when node absent). **Plus** a dedicated, **unconditional** CI step (extract + `node --check`)
  and `node --version` added to the "Resolved versions" step -- so CI (`windows-latest` ships node)
  fails loudly if node is missing or the JS won't parse, and the gate can never silently skip everywhere.
  This is the layer that closes the v028_2/v028_6 bug class (that bug was a parse error).
- **`browser`-marked headless populate-smoke -- opt-in, NOT in the default CI suite.** CI runs
  `-m "not browser"`, so this is a local + release-sign-off gate (mirrors the existing ADR-43 gate-d
  pattern in `test_browser_shots.py`). `tests/test_ui_browser.py` reuses `tools/shoot.py`'s stdlib CDP
  `Chrome` harness (the established `_eval(chrome, expr)` idiom): start the LIVE panel via
  `_ui_util.running()`, navigate Chrome to `/?t=<token>`, wait for load, then `Runtime.evaluate` an
  awaited promise that resolves once `#root` is no longer "Loading..." and asserts the JS ran and
  populated state (`#root` shows the path, `#tools`/`#drops` rendered real rows). Skips when Chrome absent.

Guard-first is deliberate: landing this gate against the current (already-fixed) inline script means the
externalize refactor in v028_8 -- the riskiest JS change in the track -- lands UNDER the gate's
protection rather than unguarded (the exact v028_2 situation). The throwaway `<script>` extraction here
is a small, intended cost; v028_8 retargets the gate at the real `panel.js` file.

## Gates / Done when
- `node --check` of the served script is green in CI and **fails the build** on broken JS (verified by a
  local negative check: break a literal, confirm the gate bites).
- `pytest -m browser` (where Chrome present) asserts the live panel populates `#root`/`#tools`/`#drops`.
- `pytest -m "not browser"` green (incl. the new node-`--check` test, which runs since CI has node).
- `pytest -m golden_env` byte-parity unchanged, NO golden refresh (panel emits no report HTML).
- No new runtime dependency.

## As-built (DONE 2026-06-24)
- **`tests/test_ui_js_parses.py`** -- extracts the served `<script>` from `control_page()` and runs
  `node --check` (skips when `shutil.which('node')` is None). Passes locally (node v25.2.1).
- **`tests/test_ui_browser.py`** (`pytest.mark.browser`) -- starts the LIVE panel via
  `_ui_util.running()`, drives `tools/shoot.py`'s `Chrome` (the established `_eval` idiom from
  `test_browser_shots.py`), navigates to `/?t=<token>`, and asserts via an awaited `Runtime.evaluate`
  promise that `#root`/`#tools`/`#drops` populated (the JS parsed AND ran). Passes locally with Chrome.
- **`ci.yml`** -- `node --version` added to "Resolved versions" (fails loudly if node ever absent) + a
  dedicated **unconditional** "panel JS parses (node --check)" step that extracts the served script and
  `node --check`s it. v028_8 will simplify this to `node --check bobframes/ui/assets/panel.js`.
- **Gate bites (negative check):** injecting `var = TOKEN broken` made `node --check` exit 1 with
  `SyntaxError: Unexpected token '='` -- proves a broken `<script>` fails the build (the v028_2 miss).
- VERIFIED: `-m "not browser"` **402 passed / 3 deselected** (was 401/2 at v028_6; +1 = the node-check
  test passes, +1 deselected = the new browser smoke); `-m browser` 1 passed (the populate smoke);
  `-m golden_env` **5 passed BYTE-UNCHANGED, NO golden refresh**; no new dependency. Working tree: only
  the two new tests + ci.yml + this doc.
- No new ADR (rides ADR-47/23).
