# v028_4 -- A/B + theming + scaffold     release: v0.2.8 · phase: ui

> The exploration controls. With ingest + share in place, this adds the last interactive verbs:
> compare two runs (A/B), re-hue a report by accent without a config edit (theming), and create a
> convention-correct capture folder for users who can't get the `<Area>/<date[_label]>/` layout right
> by hand. Still zero deps; still no report HTML (golden gate / ADR-37 untouched).

## Scope
- **bobframes/ui/jobs.py.** `build_render_argv(root, accent, accent_data)` (mirrors `cli._cmd_render`:
  `python -m bobframes.run --render-only` + the optional ADR-45 accent overrides, which run.py accepts
  directly) and `build_ab_argv(root, baseline_label, compare_label, baseline_date, compare_date)`
  (mirrors `cli._cmd_ab` -> `bobframes.cli ab`).
- **bobframes/ui/server.py.**
  - `panel_state` gains `runs` (`reports.discovery.discover_drops` -> `{key,label,date,n_captures}`;
    `[]` before any ingest/render) -- the source for the A/B picker.
  - `POST /api/render` now coerces accent / accent-data (`_render_opts`) and spawns `build_render_argv`
    (so the v028_3 endpoint gains theming; blank fields omit the flag).
  - `POST /api/ab` (token-gated; `_ab_opts`): requires baseline + compare labels (400 otherwise);
    spawns a streamed `bobframes ab` job (`spawn_cli`).
  - `POST /api/scaffold` (token-gated; opt-in): `os.makedirs(<root>/<area>/<date[_label]>/)` via
    `paths.drop_dirname`. Names are validated against path traversal (no `/` `\` `..` `:`) and the date
    against a strict ISO `YYYY-MM-DD`; returns `{created, path}` (idempotent).
  - Control page: a **Create a capture folder** form in the drops card, accent / accent-data inputs in
    the Share card (applied by Re-generate), and an **A/B comparison** card whose two selects are
    populated from `state.runs` (defaulting to prior-vs-newest; hidden with a hint when < 2 runs).
- **tests.** `test_ui_ab_theme.py` (10): the two argv builders; render threads accent into the spawn
  (blank -> omitted); ab spawns the `ab` verb + streams; ab 400s without both runs; `/api/state` lists
  runs (mocked `discover_drops`) and is empty without a catalog; scaffold creates the convention folder
  (+ idempotent) and rejects a bad date / traversal; ab + scaffold are token-gated.

## Gates / Done when
- An A/B pair and an accent re-render complete from the UI (here: the spawn seam is mocked -- the argv
  carries the right verb + options, and the SSE relays to a `done` rc).
- The A/B picker is fed by `/api/state.runs`; `/api/ab` 400s without two runs; `/api/scaffold` creates
  a convention-correct folder and refuses traversal / non-ISO dates; both are token-gated.
- `pytest -m "not browser"` green (no regression; no golden refresh -- panel emits no report HTML).

## As-built (DONE 2026-06-24)
- jobs builders + the three endpoints + `runs` state + the picker / accent / scaffold UI implemented as
  scoped. No GPU/RenderDoc: render/ab exercised with a monkeypatched `spawn`/`spawn_cli` (ADR-6); the
  run list via a mocked `discover_drops`; scaffold against a real tmp root.
- DECISION (ADR-23): `package` rejects `--accent` (a PRESENTATION verb, ADR-40/45), so theming rides
  `/api/render` only -- the panel never sends accent to `/api/package`. The A/B picker requires non-empty
  LABELS (the `ab` verb's required flags); a label-less run can't be A/B-picked from the UI in v1
  (recorded scope, not hidden -- such runs still render + appear in the run list).
- VERIFIED: 10/10 new (`test_ui_ab_theme`); full `pytest -m "not browser"` -> 398 passed / 2 deselected
  (was 388; +10). No new dependency; no golden refresh.

## Next
v028_5: polish + docs -- on-brand styling via `chrome.design_tokens_css()`; README "Guided mode" (pipx)
+ a screenshot; STATE/INDEX/ROADMAP updates; CHANGELOG; confirm the golden gate unchanged.
