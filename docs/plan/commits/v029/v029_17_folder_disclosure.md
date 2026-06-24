# v029_17 -- one project-folder line; change-box behind a disclosure     release: v0.2.9 · phase: ui

> Test feedback (user): the panel showed the folder twice -- a read-only "Project folder: <path>" line
> AND an always-visible empty input for changing it. Show the folder ONCE; tuck the change-box behind a
> "Change folder" disclosure (the panel's existing pattern for Options / Create-a-capture-folder).
> Shell-only; zero dep; no report HTML (golden untouched).

## Scope
- **`server.py` (`_SHELL`)** -- the `root_input` + "Open folder" button + `root_msg` now live inside a
  `<details><summary>Change folder</summary>` (collapsed by default); the input is relabelled "New
  folder". Default view: just the read-only "Project folder: <path>" line -- no redundant empty box. The
  ids (`root_input`, `set_root`, `root_msg`) are unchanged, so the v029_2 wiring + `/api/root` are intact.

## Gates / Done when
- Default view shows one folder (the read-only line); the empty change-box is hidden until "Change
  folder" is expanded.
- `node --check` green (panel.js unchanged -- standing); the 5 `browser` smokes still green (`#root`
  populate unaffected); `pytest -m "not browser"` green; `pytest -m golden_env` byte-parity unchanged,
  NO golden refresh. No new dependency.

## As-built (DONE 2026-06-24)
- `_SHELL`: change-box wrapped in a `<details>` "Change folder"; input relabelled "New folder".
- VERIFIED: `node --check` clean; `-m browser` 5 smokes green; `-m "not browser"` **432 passed / 7
  deselected**; `-m golden_env` **5 passed BYTE-UNCHANGED, NO golden refresh**; no new dep.
