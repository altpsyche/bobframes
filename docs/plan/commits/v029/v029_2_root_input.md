# v029_2 -- root-path input (repoint without relaunching)     release: v0.2.9 · phase: ui

> MED finding: the panel's root is fixed at launch, so switching capture folders meant restarting
> `bobframes ui` from a terminal -- the exact thing a non-terminal user can't do. Add a path input that
> repoints the panel live. Zero new dep; no report HTML (golden untouched).

## Scope
- **`server.py`** -- `POST /api/root {path}` (token-gated) -> `_set_root`: validates the path is an
  existing directory, updates `httpd.bobframes_root` (abspath), returns fresh `panel_state` so the client
  re-renders tools/drops/runs. Missing / non-directory path -> 400. Single-user local action (ADR-47
  localhost+token). A job already running keeps its original root (its argv was fixed at spawn).
- **`assets/panel.js` + shell** -- a "Project folder" input + "Open folder" button near the root line;
  the handler POSTs `/api/root` and `render(s)`s the returned state (no separate reload).
- **Hardening (caught in-commit):** `_SHELL` is now an **r-string**. The first cut used a `C:\path\to\..`
  placeholder in the plain-string shell, and Python turned `\t` into a TAB (SyntaxWarning) -- the same
  Python-string-escape class v028_8 removed for the JS. Fixed: a forward-slash placeholder **and** the
  shell r-prefixed so no future literal backslash in an attribute can be mangled. Guarded: the package
  imports clean under `-W error` (a SyntaxWarning would now fail).

## Gates / Done when
- `POST /api/root` to a valid dir flips `state.root` + `drops`; a fresh `/api/state` reflects the new
  root; a non-existent / non-dir path -> 400; missing token -> 403.
- `import bobframes.ui.server` emits no SyntaxWarning (clean under `-W error`).
- `node --check bobframes/ui/assets/panel.js` green; the `browser` populate-smoke still green;
  `pytest -m "not browser"` green; `pytest -m golden_env` byte-parity unchanged, NO golden refresh.
- No new runtime dependency.

## As-built (DONE 2026-06-24)
- `server.py`: `POST /api/root` -> `_set_root` (dir-validated; updates root; returns fresh state).
  `panel.js` + shell: folder input + "Open folder" -> `render()` of the returned state. `_SHELL`
  r-prefixed + forward-slash placeholder (the `\t`-in-a-plain-string bug, caught by a SyntaxWarning and
  fixed in-commit).
- VERIFIED: `test_ui_root` (3) -- repoint flips root + drops and a fresh `/api/state` reflects it;
  non-dir -> 400; missing token -> 403. `import ... -W error` clean (no SyntaxWarning); `no tab in page`.
  `node --check` clean; `-m browser` populate-smoke green; `-m "not browser"` **411 passed / 3
  deselected** (was 408 at v029_1; +3); `-m golden_env` **5 passed BYTE-UNCHANGED, NO golden refresh**;
  no new dep.
