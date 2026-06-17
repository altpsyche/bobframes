# v0.2.7-4 -- record Q-13 + close out the aggregation-consistency burndown     release: v0.2.7 · phase: aggregation-consistency (FINAL)

> Docs + a naming-regression test only -- NO production code change. Records Q-13 (overdraw correct as
> designed), adds the ADR-46 naming gate as a test, and writes the QUALITY_GATES §21.1w gate summary +
> the AGGREGATION_FINDINGS resolution table. Closes the burndown opened by the 2026-06-16 audit.

## Goal
Make the policy and its gates durable: every aggregation finding is intaken, resolved or explicitly
recorded, and protected by a test so the vague "avg"/median framing cannot creep back.

## Scope
- **bobframes/reports/preview.py** -- the component-gallery demo KPI labels `avg draws / frame` /
  `avg gpu / frame` -> `pooled mean ...` (the gallery is the living catalog; keep it consistent with
  ADR-46). Preview golden refreshed.
- **bobframes/tests/test_report_structure.py** -- NEW `test_no_vague_estimator_labels` (the ADR-46
  naming gate): no rendered LABEL (kpi-label / th / caption) uses "avg"/"average"/"(med)"/"typical";
  scoped to label contexts so the base64 font blob (an incidental "Avg") is ignored.
- **docs/plan/reference/QUALITY_GATES.md** -- NEW §21.1w: the v0.2.7 gate summary (frame-count owner,
  per-frame regression parity, cross-report consistency, true-median, naming gate; data path frozen).
- **docs/plan/reference/AGGREGATION_FINDINGS.md** -- resolution table (audit ID -> real ID -> commit).
- **FINDINGS.md** -- Q-13 already recorded as correct-as-designed (☑ "n/a documented") at intake.

## Q-13 (recorded, NOT changed)
`overdraw._worst_overdraw` reject% = `1 - Sigma passed / Sigma samples` is a pooled micro-average over
pixel samples (correct); the summary "worst overdraw" is a MAX selection (correctly labeled "worst").
Both are right as designed -- recorded so neither is "fixed" into a mean by mistake (ADR-46 clause 7).

## Done when
- The naming gate test is green and would FAIL on a reintroduced "avg"/"(med)"/"typical" label. ✔
- §21.1w + the AGGREGATION_FINDINGS resolution table written; all audit findings ☑ (Q-13 documented). ✔
- Preview golden refreshed; `golden_parquet`/`_pagedata` BYTE-UNCHANGED; full `-m "not browser"` green. ✔

## As-built (DONE 2026-06-17)
- Preview demo labels updated -> ADR-46-consistent; preview golden rebaked (`make_preview_golden`); the
  17 report goldens + data path BYTE-UNCHANGED by this commit. NEW naming-gate test green.
- §21.1w + AGGREGATION_FINDINGS resolution table + this doc written. Suite **362 passed**, 1 deselected.
- The v0.2.7 aggregation burndown is COMPLETE (D-13..D-16 / Q-10..Q-13 / H-41 all ☑; ADR-46 frozen).
- **Browser visual pass** on summary / dashboard / pass_gpu / draws_by_class / trend recommended before
  the PR (label + magnitude changes; not run unattended this session).

## Addendum (post-render eyeball, 2026-06-17) -- dashboard mini-card bare totals folded in (D-16 extension)
Rendering the real corpus surfaced two dashboard mini-card columns still showing bare cross-capture
totals while the rest of the dashboard leads per-frame:
- **pass-gpu card** `gpu (s)` (per-pass total) -> `total gpu (s)` (chart title + caption likewise): a
  per-pass GPU is a cross-capture total (the pass report's native basis), so it is now labeled as a
  total, not left bare.
- **draws-by-class card** `draws` (per-area total) -> **`mean draws / frame`** (per-frame via the
  `area_frames` count from `aggregates.frame_counts`, the D-15 owner), so the same area's draws read
  consistently with summary's By-area column and the trend card (no two different per-area draw numbers
  on one page).
NEW `area_frames` computed once in `dashboard.build`. Golden refresh confined to `_reports/index.html`
(+ per-run twin); `golden_parquet`/`_pagedata` BYTE-UNCHANGED. Suite still **362 green** (the naming
gate covers it). Other mini-card values were checked and are already correct (shader `cost proxy` is
per-frame via c16v; overdraw `rejected %` is the Q-13 pooled micro; instancing `repeat` is the c16v
per-frame atom).

## Next
The v0.2.7 RELEASE ship (a separate commit, like v026_6): `_version -> 0.2.7`, `## [0.2.7]` CHANGELOG
(the aggregation-consistency arc, ADR-46), full matrix + clean-wheel verify, then TAG + PyPI on explicit
authorization. R-19 (overdraw tie-iteration nondeterminism) remains a carry-over (own commit).
