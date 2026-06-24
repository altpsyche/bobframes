# v029_7 -- log copy / download     release: v0.2.9 · phase: ui  (LOW)

> LOW finding: the streamed verb log is read-only on screen -- a user can't grab it to paste into a bug
> report or save it. Add Copy + Download controls to each job log pane. Pure client JS, no server change;
> zero new dep; no report HTML (golden untouched).

## Scope
- **`assets/panel.js` + shell** -- each job panel (`job_run` / `job_share` / `job_ab`) gains a "Copy log"
  + "Download" button in its action row. `copyLog(t, btnId)` writes the pane text via
  `navigator.clipboard` (best-effort flash "Copied"); `downloadLog(t, name)` saves it as `<name>.txt` via
  a `Blob` + object-URL anchor. No endpoint -- the log text already lives in the DOM.

## Gates / Done when
- Every log pane has Copy + Download buttons wired (browser smoke confirms they exist in the live DOM;
  the served page carries the 6 button ids and panel.js implements both actions).
- `node --check` green; the `browser` populate-smoke still green; `pytest -m "not browser"` green;
  `pytest -m golden_env` byte-parity unchanged, NO golden refresh. No new runtime dependency.

## As-built (DONE 2026-06-24)
- `panel.js`: `copyLog` (navigator.clipboard) + `downloadLog` (Blob) + 6 button bindings; shell: Copy/
  Download buttons in each job action row.
- VERIFIED: `test_ui_logtools` (1) -- the served page carries the 6 button ids; panel.js uses
  `navigator.clipboard` + `URL.createObjectURL`. `test_ui_browser` extended -> the controls are in the
  live DOM. `node --check` clean; `-m browser` green; `-m "not browser"` **424 passed / 3 deselected**
  (was 423 at v029_6; +1); `-m golden_env` **5 passed BYTE-UNCHANGED, NO golden refresh**; no new dep.
