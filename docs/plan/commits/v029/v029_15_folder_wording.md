# v029_15 -- unify "Project folder" wording     release: v0.2.9 · phase: ui

> Test feedback (user): the status line said "Project root:" while the v029_2 input was labelled
> "Project folder" -- two labels for the same directory. Unify on "folder" (friendlier for the
> non-terminal QA/product audience; matches the panel's plain-language ethos). Display-only; zero dep;
> no report HTML (golden untouched).

## Scope
- **`assets/panel.js` `render()`** -- the status line now reads "Project folder:" (was "Project root:"),
  matching the input label. Internal names (`s.root`, `#root`, `--root`, `bobframes_root`) are unchanged.

## Gates / Done when
- No user-facing "Project root" remains in `bobframes/ui/`; the status line + input label agree.
- `node --check` green; the `browser` populate-smoke still green (`#root` still shows the path);
  `pytest -m "not browser"` green; `pytest -m golden_env` byte-parity unchanged, NO golden refresh.
  No new dependency.

## As-built (DONE 2026-06-24)
- `panel.js`: "Project root:" -> "Project folder:". `grep "Project root" bobframes/ui/` -> none.
- VERIFIED: `node --check` clean; `-m browser` populate-smoke green; `-m "not browser"` **432 passed /
  6 deselected**; `-m golden_env` **5 passed BYTE-UNCHANGED, NO golden refresh**; no new dep.
