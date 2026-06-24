# v029_6 -- reveal output folder     release: v0.2.9 · phase: ui  (LOW)

> LOW finding: after packaging, a non-terminal user has the zip path but no quick way to get to it. Add a
> "Reveal in folder" action that opens the output dir in the OS file explorer. Zero new dep; no report
> HTML (golden untouched). First commit of the v0.2.9 LOW tier.

## Scope
- **`server.py`** -- `POST /api/reveal {kind}` (token-gated) -> `_reveal`: `kind=package` opens the dir
  BESIDE the project (root's parent, where `package` writes the zip); otherwise the project root. No
  client path -> no traversal surface. `os.startfile` (Windows-only; 501 elsewhere, 409 if the dir is
  gone).
- **`assets/panel.js`** -- the package result gains a "Reveal in folder" link -> `revealFolder("package")`
  -> `POST /api/reveal`; on success Explorer opens and the zip-path result is left intact.

## Gates / Done when
- `POST /api/reveal {kind:'package'}` calls `os.startfile` on root's parent; default kind -> root;
  missing `os.startfile` -> 501; missing token -> 403.
- `node --check` green; the `browser` populate-smoke still green; `pytest -m "not browser"` green;
  `pytest -m golden_env` byte-parity unchanged, NO golden refresh. No new runtime dependency.

## As-built (DONE 2026-06-24)
- `server.py`: `POST /api/reveal` -> `_reveal` (kind=package -> parent; else root; `os.startfile`,
  501/409 guards). `panel.js`: a "Reveal in folder" link on the package result -> `revealFolder`.
- VERIFIED: `test_ui_reveal` (4) -- package -> beside-project; default -> root; no `os.startfile` -> 501;
  missing token -> 403. `node --check` clean; `-m browser` green; `-m "not browser"` **423 passed / 3
  deselected** (was 419 at v029_5; +4); `-m golden_env` **5 passed BYTE-UNCHANGED, NO golden refresh**;
  no new dep.
