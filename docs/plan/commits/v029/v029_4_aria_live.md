# v029_4 -- aria-live on the progress + result regions     release: v0.2.9 · phase: ui

> MED finding (a11y): a non-sighted QA/product user gets no feedback that a long ingest finished or that
> an action produced a result -- the panel updates regions silently. Mark the progress + result regions
> `aria-live` so a screen reader announces them. Pure markup; zero new dep; no report HTML (golden untouched).

## Scope
- **`server.py` (`_SHELL`)** -- `aria-live="polite"` on the job-progress phase regions (`#phase`,
  `#phase_share`, `#phase_ab` -- announce "done" / "failed" / "cancelled"), the result boxes
  (`#share_result`, `#ab_result`), and the action status lines (`#sc_msg`, `#config_msg`, `#root_msg`,
  `#ab_hint`). The streaming log `<pre>`s are deliberately **NOT** aria-live -- announcing every log line
  would flood a screen reader.
- **Scoping (ADR-23, documented not silent):** the plan noted "assertive for the error path." Errors
  render *into these same polite regions* (e.g. `<span class="bad">` in `#share_result`), so they ARE
  announced -- politely (not interrupting). A true interrupting `assertive`/`role="alert"` would need
  per-message region swapping in every error handler for marginal benefit; deferred deliberately. The
  core finding ("announce completion") is fully met.

## Gates / Done when
- The phase + result + action-status regions carry `aria-live="polite"`; the streaming logs do not.
- The browser populate-smoke confirms the attribute reaches the live DOM (`#phase` -> `polite`).
- `node --check` green (panel.js unchanged -- standing regression); `pytest -m "not browser"` green;
  `pytest -m golden_env` byte-parity unchanged, NO golden refresh. No new runtime dependency.

## As-built (DONE 2026-06-24)
- `_SHELL`: `aria-live="polite"` on phase x3 + share_result/ab_result + sc_msg/config_msg/root_msg/ab_hint;
  logs left non-live.
- VERIFIED: `test_ui_aria` (2) -- the 9 regions are aria-live, the 3 log panes are not. `test_ui_browser`
  extended -> `#phase` is `polite` in the live DOM. `node --check` clean; `-m browser` green;
  `-m "not browser"` **415 passed / 3 deselected** (was 413 at v029_3; +2); `-m golden_env` **5 passed
  BYTE-UNCHANGED, NO golden refresh**; no new dep.
