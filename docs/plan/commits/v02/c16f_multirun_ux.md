# c16f — multi-run UX: run selector + comparison affordances     release: v0.2 · phase: De-hardcoding

## Goal
Make it **obvious which run you are looking at** and **trivial to switch / compare runs**. On the real
Perf ingest (2 runs x 7 areas) it was hard to tell run1 from run2: the only run cue is a bare drop key
(`2026-05-25_r110565`) buried in columns, there is no way to pick "show me run 1" without editing
folders, and "current vs baseline" is implicit. c16f is the **navigation + comparison UX** layered on
the per-run-truth model from [c16e](c16e_run_model.md).

## Depends on
[c16e](c16e_run_model.md) (the run model: a report has a CURRENT run + baselines). Reuses the existing
A/B picker (`chrome.ab_picker` / `ab_picker_for`, `reports/ab.py`) and the c16d visual language.

## Scope - the moves
1. **Run selector (pick the CURRENT run).** A header control to switch which run the report is rendered
   for (drives c16e's `current_run` override). Default = newest. Reuse/extend the A/B picker pattern
   (`chrome.ab_picker_for`) so it is one consistent control, not a new bespoke widget. Deterministic +
   offline (static `<select>`/links, no JS fetch); pre-rendered per-run pages OR a client-side switch
   over already-emitted run data - pick the byte-stable option in the plan.
2. **Baseline selector (what you compare against).** When >1 run exists, let the user choose the baseline
   for deltas / the "resolved since" section (default = immediately-prior run). Surface the chosen pair
   as a clear **"current 2026-06-01 r110788  vs  baseline 2026-05-25 r110565"** banner.
3. **Distinct run identity.** Give each run a stable, legible label + visual chip (date + label + a
   short ordinal "run 2/2"), used consistently in headers, columns, trend axes, and nav - so a column
   header reads as a run, not an opaque key. Dim non-current runs (c16d `--text-3` / the `.dim` util);
   accent the current run.
3a. **Run count + "newer run available".** Show how many runs exist and, when not viewing the newest,
   a clear "you are viewing run 1 of 2 (an older run); newest is r110788" cue so an exec is never
   accidentally reading stale data as current.
4. **Cross-report consistency.** The selected current/baseline pair persists across the dashboard ->
   per-report navigation (carry it in links), so switching run on the dashboard keeps you in that run
   when you drill into pass_gpu / instancing / etc.
5. **Trend entry points.** From any single-state report, a clear link to the `trend_table` view scoped
   to the current+baseline pair (the across-run story lives there; the single-state reports stay
   per-run).

## Constraints (do not regress)
- **Determinism / offline / parity**: any run selector must keep reports **byte-deterministic** and
  **open offline** (no network). If switching runs means emitting multiple pre-rendered pages, keep the
  filenames/links deterministic; if it is a client-side toggle, the emitted data + DOM must be static.
  Refresh the golden + review. `test_parquet_parity` GREEN, **no** digests refresh.
- Reuse the A/B picker / `resolve_drop_set` plumbing rather than inventing a parallel selector.
- Lint ASCII-only (run labels via `safe_chrome_text`); keep c16c a11y (the selector is keyboard- +
  screen-reader-usable, `scope`/labels intact) + c16d visual language + reduced-motion/print behavior.

## Changes
Output-changing -> refresh golden + review page-by-page (the selector + per-run labeling touch the
shared chrome -> drill/root/preview too; keep intentional). Tests: the run selector lists all runs +
marks the current; links carry the current+baseline pair across reports; "older run" cue appears when
not newest; ASCII + a11y guards. Extend `test_report_structure` + `test_design_tokens` for any new chrome.

## Done when
- A header **run selector** switches the current run; default is the newest; an "older run" cue shows
  when viewing a non-newest run.
- A **baseline selector** + a clear "current vs baseline" banner drive the deltas / resolved-since view.
- Each run has a distinct, legible label/chip; the current run is accented, baselines dimmed; the
  selected pair persists dashboard -> per-report.
- A/B + `trend_table` integrate with (not duplicate) the selector; `test_parity` green;
  `test_parquet_parity` unchanged; `bobframes smoke` (render-only, lint clean) exit 0; visually verified
  on the real Perf data (you can tell the runs apart + switch in a few clicks).

## Closes
**G-18 (multi-run UX: hard to distinguish / switch / compare runs)**. Builds on **ADR-35** (run model,
from c16e). Add **QUALITY_GATES §21.1k** when it lands.
