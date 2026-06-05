# v0.2.6-1b — flat surfaces + radius + states + responsive + print     release: v0.2.6 · phase: redesign

> The visual half of the all-chrome lift, landed back-to-back with v0.2.6-1a. 1a re-tuned token VALUES
> (neutral palette, AA, new tokens DEFINED); 1b edits the CSS-rule bodies to APPLY them: flat/border-led
> surfaces (reverse ADR-34), the `--radius` scale over the hardcoded literals, focus/active states,
> responsive, and print. Plan: `~/.claude/plans/bobframes-v0-2-6-visual-enumerated-bachman.md`.

## Goal
Make the chrome actually LOOK flat + shadcn: replace elevation shadows with hairline-border separation,
apply the `--radius-sm/--radius/--radius-lg` scale, add `:focus-visible` rings + reduced-motion-safe
`:active` micro-scale, responsive `@container` rules, and a corrected print layout.

## Scope (CSS-rule edits in `reports/assets/*.css`)
- **Flat / border-led (reverse ADR-34).** Re-tune `--elev-1/2/3` toward flat (drop the ambient blur; keep
  at most a hairline contact ring) and switch `section.card` / `kpi-chip` / `dash-card` / `details.*` /
  `pair-group` / `sticky-h2` / per_drop `table-section` from `box-shadow: var(--elev-*)` to a 1px
  `--border` + `--radius`. Update the pinned `test_c16d_shadow_and_motion_tokens_emitted` +
  `test_c16d_depth_over_borders_css` IN-COMMIT (they currently assert the depth design).
- **Radius scale applied.** Replace the ~21 hardcoded `2px/3px/4px` `border-radius` literals with
  `var(--radius-sm)` (minis/pills/inputs/toggles), `var(--radius)` (cards/sections), `var(--radius-lg)`
  (hero cards).
- **States.** `:focus-visible` ring driven off `--ring`/`--accent`; `:active` micro-scale gated under
  `prefers-reduced-motion`; `tabular-nums` on numeric cells/KPIs; uppercase `--fs-micro` eyebrows.
- **Responsive.** `@container page (max-width:600px)` -> `.kpi-strip` 2x2; sidecar wall columns.
- **Print (FIX -- flagged at the 1a sign-off).** **The printed page currently has NO outer margin: content
  hugs the paper edge (cards flush to x=0, header in the top-left corner).** This is pre-existing
  `print.css` behavior surfaced by the 1a gallery print capture. Add an `@page { margin }` (or restore the
  container/body padding in print) so content sits inside a sane page margin; keep the flat surfaces
  readable on paper (re-add a thin rule where a borderless card would vanish; severity rails stay).

## Gates
The full v0.2.6 replacement set (QUALITY_GATES §21.1v): data path frozen; structural/ARIA + do-not-rename;
token guard; contrast; **browser matrix light/dark/print on synthetic + real Perf, signed off BEFORE
goldens**; lint/ASCII/determinism. `make_golden`+`make_preview_golden`+`make_package_golden` on the
canonical `.venv`. The print capture must show a proper page margin (the 1a regression closed).

## Done when
Cards/minis render flat with hairline borders + the radius scale; focus rings + reduced-motion-safe states
present; the print capture has a sane outer margin (no edge-hugging); pinned `test_c16d_*` updated
in-commit; full suite green; screenshots signed off.

## Next
v0.2.6-1c (user theme override: `[theme]` + `--accent`, ADR-45).
