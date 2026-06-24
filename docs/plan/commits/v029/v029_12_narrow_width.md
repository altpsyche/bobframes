# v029_12 -- narrow-width responsive check     release: v0.2.9 · phase: ui  (LOW)

> LOW finding: the panel was only checked at desktop width; fixed-width inputs could push the page wider
> than a narrow viewport. Add a breakpoint + a narrow-viewport overflow gate. CSS-only; zero new dep; no
> report HTML (golden untouched). Last feature before the v0.2.9 close-out.

## Scope
- **`assets/panel.css`** -- a `@media (max-width: 560px)` breakpoint: smaller body margins + step padding,
  `input, select { max-width: 100%; box-sizing: border-box }` (fixed-width fields reflow), and
  `table { display: block; overflow-x: auto }` (a wide table scrolls instead of forcing page overflow).

## Gates / Done when
- At a 480px viewport the page has no horizontal overflow (`scrollWidth <= innerWidth`), asserted by a
  new `browser`-marked smoke driving Chrome with `Emulation.setDeviceMetricsOverride`.
- `node --check` green (panel.js unchanged -- standing); `pytest -m "not browser"` green;
  `pytest -m golden_env` byte-parity unchanged, NO golden refresh. No new runtime dependency.

## As-built (DONE 2026-06-24)
- `panel.css`: the `<=560px` breakpoint (reflow inputs, scrollable table, tighter spacing).
- VERIFIED: `test_ui_browser.test_narrow_viewport_has_no_horizontal_overflow` (browser) -- at 480px
  `scrollWidth - innerWidth <= 1` (no overflow); populate + RUN-dedup smokes still pass (3 browser tests).
  `node --check` clean; `-m "not browser"` **432 passed / 5 deselected** (unchanged count -- the new test
  is browser-marked; +1 deselected); `-m golden_env` **5 passed BYTE-UNCHANGED, NO golden refresh**;
  no new dep.
