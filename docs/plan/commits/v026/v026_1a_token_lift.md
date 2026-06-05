# v0.2.6-1a — token/type/spacing lift: neutral shadcn palette (ADR-44)     release: v0.2.6 · phase: redesign

> The first commit that MOVES PIXELS. Translates the shadcn neutral palette into `design_tokens.toml`
> (VALUES only — no body markup, no CSS-rule change), fixes the WCAG-AA `--text-3` gap, and introduces
> the `--radius`/`--sp-5`/`--sp-10`/`--fs-micro` tokens (defined here, APPLIED in 1b). Byte-parity is
> intentionally broken; the replacement gates (ADR-43) are the contract. Plan:
> `~/.claude/plans/bobframes-v0-2-6-visual-enumerated-bachman.md`.

## Goal
Lift every page to the shadcn-neutral palette at once by re-tuning token VALUES, so the chrome reads
clean/neutral/flat while the semantic data colors (status + draw-class + the data accent) still pop.
Mechanical + reviewable: owns the pinned-byte test churn; 1b then applies flat surfaces + the radius
scale + states + responsive/print.

## Scope (token VALUES + the :root wiring; no CSS-rule edits)
- **Neutral chrome (chroma 0, shadcn):** `--bg` pure white / `oklch(14.5%)` dark; flat `--surface-1`
  (light == bg), `--surface-2` muted fill; hairline `--border` (`0.922` / `white 10%`); `--accent-primary`
  neutral near-black/near-white. Semantic hues KEPT: `--status-*`, `--c-*` draw classes, `--accent-data`
  (the data accent + heatmap tint) — data stays legible.
- **WCAG-AA fix (`--text-3`):** light `60%`→`55%` (3.0→4.85:1), dark tuned to 5.0:1; `--text-2` 48% (6.5:1).
  fg 19.8:1 (AAA). All proven by `test_contrast.py` (its strict-xfail flipped to a normal pass here).
- **New tokens (defined; APPLIED in 1b):** `[radius]` `--radius-sm/--radius/--radius-lg` (6/8/10),
  `--sp-5`/`--sp-10` (legitimizes the `--sp-5` whose absence was G-30 — the guard's planted-typo test moved
  to `--sp-7`), `--fs-micro` (10px eyebrows). `[radius]` added to `_tokens._SUBST_SECTIONS`.
- **Type tune:** `fs_h1` 1.5→1.625, `fs_h2` 1.1→1.1875, `fs_h3` 0.9→0.9375 (restrained); `fs_body`/`fs_mono`
  UNCHANGED (density/Ctrl-F). `fs_display` unchanged (hero numeral is summary-scoped at v0.2.6-2).
- **`kpi_strip_min` 150→170** (hero-numeral headroom).
- **Accent knob seeded:** an "ACCENT KNOB" comment block atop `[color]` names the user-overridable hues +
  points pip users to the `.bobframes.toml [theme]` / `--accent` path (built in v0.2.6-1c) — NOT this file.

## Pinned-byte test updates (in-commit, ADR-23 — never loosened after)
- `test_exact_color_lines_preserved`: `--bg` + `--accent-primary` lines updated to the neutral values;
  `--c-other` + `--sp-1..4` UNCHANGED (c-other was already neutral gray).
- `test_layout_literals_preserved`: `minmax(150px→170px)`.
- `test_contrast.py`: the `--text-3` strict-xfail removed (now a normal AA pass) — the "flip" the -0 marker tracked.
- `test_token_guard.py`: planted typo `--sp-5`→`--sp-7` (sp-5 is now a real token).

## Gates (ADR-43 replacement set; byte-parity intentionally broken)
- **Data path FROZEN:** `test_parquet_parity` + `golden_parquet/digests.json` + the 27 `_pagedata/*.js`
  BYTE-UNCHANGED (verified: absent from `git status`). NO `make_parquet_golden`.
- Token guard `undefined_tokens() == set()` on both bundles (auto-covers the new tokens).
- Contrast audit green (fg AAA; text-2/text-3 AA both themes).
- Browser matrix: gallery shot light/dark/print (`c:/tmp/v026-1a-shots`), reviewed + signed off BEFORE
  the golden refresh.
- Goldens refreshed on the canonical `.venv` (py3.12.13/pyarrow21): `make_golden` (17 HTML + 27 `_pagedata`)
  + `make_preview_golden` + `make_package_golden`. Full suite **327 passed**.

## Done when (all green)
17 golden pages + preview + package refreshed (palette only); `_pagedata`/`digests.json` byte-unchanged;
full suite green on `.venv`; gallery screenshots signed off.

## As-built (2026-06-05)
Shipped as scoped. Sign-off feedback: palette/type "nice"; the **print global-padding** issue (content
hugs the paper edge — pre-existing `print.css`, NOT a 1a token change) is recorded as a **v0.2.6-1b**
must-fix (1b owns print). Surfaces still carry the old shadows + hardcoded 4px radius until 1b. Landed
together with the v0.2.6-0 dev-only tooling in one commit (developed in one tree; `test_contrast.py`'s
text-3 assertion only passes with this commit's token fix). ADR-44 appended; QUALITY_GATES §21.1v added.

## Closes / next
No FINDINGS row. Next: **v0.2.6-1b** (flat surfaces + apply `--radius*` + states + responsive + the print
padding fix), landed back-to-back with this commit.
