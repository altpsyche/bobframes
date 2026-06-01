# c16c — report restructure (section framing + copy + dashboard small-multiples + a11y)     release: v0.2 · phase: De-hardcoding

## Goal
Finish the report info-design overhaul started in [c16](c16_report_quality.md) (polish) and
[c16b](c16b_report_viz.md) (charts). c16b made every report lead with a visualization; c16c does the
heavier **restructure** that the chart-first layout enables, taking the reports the rest of the way to
10/10. Split out of c16b so each golden refresh stays reviewable page-by-page (precedent: c06a/c06b,
c16/c16b; ADR-23).

## Depends on
[c16b](c16b_report_viz.md) — uses the `charts` toolkit (including the already-shipped `icicle` /
`stacked_bar` primitives) and the `chrome` builders `section_card` / `rdc-sticky-h2` / `rdc-copy-button`
(CSS + JS already defined, wired in few/no reports today).

## Files
- **Section framing**: route multi-section reports through `chrome.section_card`
  ([chrome.py](../../../bobframes/reports/chrome.py)) and spread `rdc-sticky-h2` beyond `trend_table`
  (`pass_gpu` / `overdraw` per-area sections, `draws_by_class`, `shader_hotlist`, `instancing`).
- **Copy buttons**: `rdc-copy-button` on copyable IDs — mesh hash (`instancing`), shader id / src path
  (`shader_hotlist`), pass path (`pass_gpu`). The web component already exists (chrome JS); just emit it.
- **Dashboard** (`reports/dashboard.py`): **small-multiples** — a mini chart per card (reuse `charts`
  with smaller `[chart]` sizes); **insight subtitles** ("why it matters" + top finding + drill link);
  cross-report nav.
- **Fill-or-hide**: the instancing "material batching" empty section — render real content when present,
  hide the section header when empty (no bare empty-state under a heading).
- **Accessibility**: `<caption>` on report tables, `scope="col"` on `th`, non-color-only status glyphs
  (the charts' `role/title/desc` already landed in c16b); re-verify print + reduced-motion.

## Changes
Output-changing → **refresh the golden snapshot** (`python -m bobframes.tests.make_golden` +
`make_preview_golden`) and review the diff page-by-page (ADR-23). Data extraction is untouched →
`test_parquet_parity` stays green with no `digests.json` refresh (§21.9).

## Done when
- Multi-section reports use `section_card` + sticky `h2`; copyable IDs carry `rdc-copy-button`.
- Dashboard cards show a mini chart + insight subtitle + cross-report nav.
- The instancing "material batching" section is filled or hidden (no bare empty heading).
- Tables carry `<caption>` + `scope="col"`; status is not color-only.
- Golden refreshed + reviewed; `test_parity` green; `test_parquet_parity` unchanged; `bobframes smoke`
  (render-only, 9 pages, lint clean) exit 0.

## Closes
**G-15 (report info-design overhaul) — restructure half** (the charts half is
[c16b](c16b_report_viz.md)) · remaining report-polish items from
[QUALITY_GATES §21.1g](../../reference/QUALITY_GATES.md). Builds on [c16](c16_report_quality.md)
(ADR-32) + the chart model (ADR-33).
