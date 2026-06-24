# v029_11 -- favicon     release: v0.2.9 · phase: ui  (LOW)

> LOW finding: the panel served no favicon, so the browser tab showed a broken icon and the console
> logged a `/favicon.ico` 404. Serve a tiny inline SVG. Zero new dep; no report HTML (golden untouched).

## Scope
- **`server.py`** -- a `_FAVICON` constant (a neutral rounded-square + "b" SVG, ~250 bytes) served at
  `GET /favicon.ico` (`image/svg+xml`, no token -- static); a `<link rel="icon" href="/favicon.ico">` in
  the shell head so the browser uses it deterministically.

## Gates / Done when
- `GET /favicon.ico` -> 200 with `image/svg+xml`; the page links the favicon.
- `node --check` green (panel.js unchanged -- standing); the `browser` populate-smoke still green;
  `pytest -m "not browser"` green; `pytest -m golden_env` byte-parity unchanged, NO golden refresh.
  No new runtime dependency.

## As-built (DONE 2026-06-24)
- `server.py`: `_FAVICON` SVG + `GET /favicon.ico` route + `<link rel="icon">` in `_SHELL`.
- VERIFIED: `test_ui_favicon` (2) -- `/favicon.ico` -> 200 `image/svg+xml` with `<svg` body; the page
  links it. `node --check` clean; `-m browser` green (2); `-m "not browser"` **432 passed / 4 deselected**
  (was 430 at v029_10; +2); `-m golden_env` **5 passed BYTE-UNCHANGED, NO golden refresh**; no new dep.
