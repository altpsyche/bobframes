# c16n — truncation coverage tail + dashboard print     release: v0.2 · phase: De-hardcoding

> **Status: DONE (2026-06-03).** 188 -> 190 green (+`test_c16n_draws_by_class_area_drop_clip`,
> +`test_c16n_dashboard_mini_print_fullwrap`). `draws_by_class` area/drop now clip via the inner `.clip`
> (default tier) - all 5 tabled reports consistent; a `@media print` rule in `_RDC_TABLE_CSS` releases the
> bare dashboard/preview minis (`a.dash-card table.data` + the direct-child `.table-wrap > table.data`
> preview mini) to full-wrap on paper - the mini analogue of the static rdc-table print rule. Mini `title=`
> kept UNCONDITIONAL (responsive widths, no deterministic server clip point - ADR-23 documented scoping, no
> heuristic shipped; no new ADR). All HTML goldens refreshed (engine CSS inline on every page;
> `draws_by_class` also gains the `<span class="clip">` markup); `_pagedata`/`digests.json`/`golden_parquet`
> BYTE-UNCHANGED, `test_parquet_parity` green NO refresh (§21.9). `bobframes smoke` render-only 15 pages lint
> clean exit 0. Browser-verified offline (headless Chrome, `file://`): `draws_by_class` area/drop carry the
> `.clip` spans + the Expand-cells toggle now injects (a `.clip` cell exists), no JS errors; the dashboard
> print-to-PDF shows every mini cell + header in FULL (headers wrap, nothing clipped). QUALITY_GATES §21.1o
> extended. Commits on `v0.2-roadmap-c04`, UNPUSHED. current -> c16o.

> **ADR-38 (tail).** c16m landed the controllable-truncation contract on the ONE `rdc-table` engine and the
> 4 named report builders + the bare dashboard minis. c16n closes the last coverage gaps so EVERY tabled
> surface behaves identically: the one report table c16m's scope skipped, and printing the dashboard.

## Goal
Finish the c16m truncation story. Two consistency gaps remain: (1) the `draws_by_class` report's raw
per-(area,drop) table never got the clip+`title=` treatment (c16m scoped only overdraw/instancing/
shader_hotlist/trend); (2) the bare dashboard/preview minis are `table-layout:fixed` + `overflow:hidden`, so
on **paper** they print clipped with no tooltip (print has no `title=` hover) — the dashboard's mini data is
hidden when printed.

## Depends on
`c16m` (the clip helpers `base.clip_span`/`clip_attrs`, the `.clip` CSS, the dashboard-mini fit). ADR-38.

## Scope
1. **`draws_by_class` report table.** Wrap the `area` + `drop` text cells (`reports/draws_by_class.py`, the
   raw per-(area,drop) class-count table) in `base.clip_span` (default tier), matching the other tabled
   reports. After this, all 5 tabled reports + the catalog/drill virtual tables clip + hover-reveal
   consistently — no tabled surface left un-clipped.
2. **Dashboard + preview mini print.** Add a `@media print` rule releasing the bare minis
   (`a.dash-card table.data`, and the preview-gallery minis) to `white-space:normal; overflow:visible`
   (+ `overflow-wrap:anywhere`) so the dashboard prints its mini cells **and headers** in full — nothing
   hidden on paper. (The static-report full-wrap print rule is `rdc-table`-scoped and does NOT cover bare
   minis; this is the mini analogue.)
3. **Mini `title=` de-noise (evaluate, don't force).** Today every mini text cell/header carries `title=`
   even when it isn't clipped (mild screen-reader double-read). Gate it ONLY if a deterministic gate is
   clean; column widths are responsive (server can't know the pixel clip point), so if a char-length
   heuristic would drop the `title` on a genuinely-clipped short cell, **keep unconditional + record the
   rationale (ADR-23)** rather than ship a fragile heuristic.

## Constraints (do not regress)
- Presentation-only; `test_parquet_parity` untouched (§21.9, no digests refresh). ASCII (CSS ellipsis
  keyword). Offline + byte-deterministic. The clip rides on the inner element / bare-mini td exactly as
  c16m established; copy/link payloads stay the full value (c16c).

## Done when
- `draws_by_class`'s area/drop cells clip + reveal full value on hover like the other reports.
- Printing the dashboard (browser print-preview) shows full mini cell + header values (nothing clipped).
- Golden refreshed + reviewed; `test_parity` green; `test_parquet_parity` green with no digests refresh;
  `bobframes smoke` lint clean; browser-verified offline.
- `test_report_structure`/`test_design_tokens` gain c16n guards (draws_by_class clip present; mini print
  rule present).

## Closes
The c16m truncation-coverage tail (every tabled surface consistent; dashboard printable).
