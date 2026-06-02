# c16i — catalog + drill readability pass (the html/template.py layer)     release: v0.2 · phase: De-hardcoding

> **REVIVED + ACTIVE (ADR-37, 2026-06-02).** This commit was briefly superseded by the SPA (ADR-36), which
> a lifespan review then rejected (ADR-37): the reports stay server-rendered + static, so this static
> `html/template.py` readability pass is exactly the right shape after all. Pairs with **c16j** (decouple
> the heavy catalog/drill data into `<script src>`'d `_data/*.js` — the ~21 MB TTI fix); together they are
> the whole catalog/drill improvement, with NO SPA. The durable data investment lives in c20/c30, not here.

## Goal
Bring the **catalog (root `index.html`) and per-drop drill browser** — everything built by
`bobframes/html/template.py` — up to the readability + design bar the **reports** already reached in
c16b/c16c/c16d/c16e/c16f. The reports layer (`reports/chrome.py` + `reports/*`) got charts, section
cards, depth, a vendored-Inter type split, and the run model. The `template.py` layer never did, so
the wide multi-column catalog VTable and the drill table dumps are still dense, all-monospace, and
visually flat — the eye-strain the three plan-folder reviews describe
([report_roadmap.md](../../report_roadmap.md), [readability_and_presentation_review.md](../../readability_and_presentation_review.md),
[overall_overhaul_proposal.md](../../overall_overhaul_proposal.md)) is almost entirely in **this** layer.

This commit harvests the **buildable-within-constraints** subset of those reviews. It is presentation
only: server-rendered + deterministic client JS, **no** change to the offline single-file contract.

## Context — read before scoping
The reviews treat the output as one UI; it is two separately-built layers. Triage (verified against the
code, 2026-06-02):
- **Already done in the reports layer (do NOT redo here):** typography split (c16d), depth/shadows +
  soft severity tints (c16d), heatmap/data-bar cells (`chrome.heatmap_cell`, c16), drop-compare/diffs
  (A/B `ab.py` + `trend_table` deltas + c16e/c16f run model + resolved-since), sparklines
  (`delta.sparkline_svg`), collapsible secondary metrics (`<details>`, c16b).
- **The real gap = `html/template.py`:** `table.data` uses `var(--fs-mono)` for **headers AND every
  cell** (`template.py` `_PER_DROP_CSS`), the VTable row height is `ROW_H = 22` with `2px` cell padding,
  and the wide catalog is a flat column wall. Zebra (`tr.alt`) + per-table category `<details>`
  (`details.category`) already exist — build on them.
- **The heavy-data fix is a SIBLING commit, not this one:** the ~21 MB inline-data drill/catalog TTI is
  fixed by **c16j** (decouple the VTable payload into a `<script src>`'d `_data/*.js`), STATIC, per ADR-37.
  c16i is the readability pass only; c16j is the data decoupling; together = the whole catalog/drill
  improvement, no SPA.

## Architecture decided (ADR-37 — read this, it settles the earlier SPA question)
The reviews' headline SPA (router + `fetch()`-JSON + external `/assets/` + Google-Fonts) was evaluated
(ADR-36) and **rejected on a lifespan review (ADR-37)**: a bespoke offline SPA is a perpetual
web-framework maintenance tax, weakens the golden-as-correctness gate, loses JS-optional content, and
constrains the v0.6 plugin / cross-platform future; `fetch` of local JSON also dies on `file://` (CORS).
**Settled direction:** reports stay **server-rendered + static + self-contained** (JS-optional + single-file
+ golden-as-output preserved); the ONLY real perf problem (the heavy drill/catalog data) is decoupled
**statically** in c16j via `<script src>` (those pages were never portable/JS-optional anyway); and the
durable data investment goes to the **data contract** (c20 `--json` + c30 schema/query), not a presentation
engine. So c16i below is on the **static `html/template.py`** layer — the right shape, not a stopgap.

## Depends on
The reports design system (c16d tokens/Inter/depth, ADR-27/34), `html/template.py` (the catalog + drill
renderer + the VTable JS), `chrome_css`/`design_tokens_css` (shared, imported by `template._compose_css`).

## Scope — prioritized (split into sub-commits if the golden balloons; precedent c16d)
1. **Typography split (highest signal, lowest risk).** In `_PER_DROP_CSS`, stop using `--fs-mono` for the
   whole `table.data`. Headers (`thead th`), text columns (area / date / status / label / pass names) and
   the TOC/controls render in the Inter sans stack; **mono + `tabular-nums` stays only for numeric cells,
   IDs, and hashes** (`td.numeric`, id/hash columns). Mirrors the c16d reports split. Per-column
   sans-vs-mono is decided from the column's dtype/role (the VTable already tags `numeric`).
2. **Spacing + tracking.** Bump the VTable row height from `22px` and the `2px` cell padding to a roomier
   value (~`32-34px` / `6-8px`). **Coordinate JS + CSS:** `ROW_H` in `_JS` drives the virtual-scroll
   offset math, so the constant and the CSS row height MUST match exactly or rows misalign. Keep the
   existing zebra (`tr.alt`) + hover; optionally add a soft left border on the sticky first column.
3. **Heatmap / data-bar cells on numeric catalog columns.** Overlay a soft relative-value bar behind
   numeric cells so outliers are scannable (the reviews' strongest readability ask). Compute **client-side
   in the VTable JS** from the already-inline data (per-column max) so the emitted HTML payload is
   unchanged and only the static `_JS` text moves — keeps the parity diff tiny + deterministic (no
   `random`/`Date`). Reuse the reports heatmap palette via CSS vars (light-dark aware).
4. **Collapsible column groups on the wide catalog.** Group the catalog's columns into toggleable sets
   (Metadata / Workload / Resources / Samples) with a header control, so the "wall of columns" collapses
   to what the user wants. VTable feature (show/hide column sets); the group->column map is a static,
   deterministic table in `template.py`. (Drill per-table sections already collapse via `details.category`.)
5. **(Optional, if cheap) Card-based area landing on the root index** — a master-detail summary (one card
   per area: latest status + a mini sparkline + "open catalog") above the full table. Defer if it balloons
   the golden; not required for the gate.

## Constraints (do not regress)
- **Offline + byte-deterministic single file (ADR-6).** No network, no `fetch`, no external asset/font.
  All JS stays inline + static; any client computation is deterministic (no `random`/`Date`/timestamps).
- **Golden parity (ADR-6/32/33).** Output-changing -> refresh the HTML golden (root `index.html` + the
  drill page move; reports pages should be UNCHANGED — verify). Pages are minified single-line: review
  via structural-marker counts AND a real browser render (light/dark, the c16d discipline).
  `test_parquet_parity` stays GREEN with **no** `digests.json` refresh (presentation only, §21.9).
- **Tokens via ADR-27** (no new raw literals — extend the token skeleton); **ASCII-only lint**; keep the
  c16c a11y posture (`scope`/caption/keyboard/reduced-motion) and c16d visual language (depth, Inter,
  gradients, motion). Heatmap colour must not be the only signal (keep the number).
- **VTable correctness:** the `ROW_H` JS constant and the CSS row height are a coupled pair — changing one
  without the other breaks virtual-scroll offset math. Verify scrolling in a browser on the real data.
- Do not touch the inline-data coupling (the 21MB question is the deferred fork above), and do not
  regress the reports layer (c16e/c16f run model, c16d aesthetics).

## Changes
Output-changing -> refresh golden + review. New deterministic VTable behaviour (type-class per column,
heatmap bars, column-group toggle) is static JS -> the data payload is unchanged, only `_JS`/`_CSS` move.
Tests: extend the structure/parity guards for the new catalog chrome (column-group control present + its
group->column map; numeric cells carry the heatmap class; the type split = headers/text not mono, numbers
mono); a determinism guard (same input -> same emitted bytes); ASCII guard already covers it. Confirm the
**reports** goldens are byte-unchanged (this commit is the template.py layer only).

## Done when
- The catalog + drill render with the Inter/mono type split, roomier rows, numeric heatmap cells, and
  collapsible column groups on the wide catalog — visibly less eye-straining, verified in a real browser
  (light + dark) on BOTH the synthetic golden AND the real Perf data.
- Reports-layer goldens are UNCHANGED; root + drill goldens refreshed + reviewed; `test_parity` green;
  `test_parquet_parity` unchanged (no digests refresh); `bobframes smoke` (render-only, lint clean) exit 0.
- The VTable scrolls correctly at the new row height (ROW_H/CSS coupled), no row misalignment.
- The SPA/fetch/external-asset/web-font architecture is NOT adopted; its product-contract fork is recorded.

## Closes
**G-21 (catalog + drill readability: the html/template.py layer never got the c16b-f report design pass)** —
the readability half; the heavy-data half (G-22's real problem) is the sibling **c16j**. **G-22** is resolved
by **ADR-37** (SPA rejected; heavy-data decoupling done statically in c16j; durable data contract = c20/c30).
No new ADR for c16i itself (rides ADR-6/27/32/33/34 + ADR-37). Add **QUALITY_GATES §21.1l** when c16i + c16j land.
