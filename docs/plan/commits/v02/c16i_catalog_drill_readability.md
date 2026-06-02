# c16i — catalog + drill readability pass (the html/template.py layer)     release: v0.2 · phase: De-hardcoding

> **SUPERSEDED by ADR-36 (2026-06-02).** The reports are moving to an offline static SPA; the catalog +
> drill readability goals below (type split, roomier rows, heatmap cells, collapsible column groups, G-21)
> are now delivered **inside the SPA** at [c16n](c16n_catalog_drill_readability_spa.md), not as a static
> `html/template.py` pass. This doc is kept for provenance — the feature spec still applies, just in the
> SPA VTable instead. Do NOT execute this commit; do c16j..c16n instead.

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
- **Out of scope (frozen-contract conflict — see below):** the reviews' SPA / `fetch()`-JSON /
  external-`/assets/` / Google-Fonts architecture.

## Explicitly OUT of scope (a product-contract fork; needs a new ADR + signoff, NOT this commit)
The reviews' headline architecture **must not** be implemented here — each item breaks a frozen,
deliberately-chosen constraint:
- **SPA + async `fetch('_data/*.json')`** — a `file://` page cannot fetch local JSON (browser CORS), so
  a double-clicked report would render an empty skeleton forever. Breaks **ADR-6** (offline,
  self-contained single file).
- **External `/assets/style.css` + `/assets/app.js`** — breaks the single-file contract (a copied/
  emailed report would be dead). The CSS/font duplication the reviews flag is a *known, accepted*
  tradeoff (ADR-34: offline + byte-determinism chosen over size).
- **Google-Fonts / external web font** — directly contradicts **ADR-34** (CDN font forbidden with
  explicit signoff; the Inter subset is vendored + inlined precisely to stay offline + deterministic).

These target a real problem (the 21MB inline-data drill TTI — drill bakes every table's rows as
`<script>window.__data_<table>=…`, `template.py`). If a *served viewer* is ever wanted, that is a
different product than "an offline file you open" and needs its own ADR + signoff. Recorded as a
finding (below), not silently dropped (ADR-23). c16i does NOT touch the data-coupling.

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
**G-21 (catalog + drill readability: the html/template.py layer never got the c16b-f report design pass)**.
Records **G-22 (decoupled/served-viewer architecture — SPA + async data — is a product-contract fork
that breaks the offline single-file + byte-deterministic contract; needs a dedicated ADR + signoff)** as
explicitly deferred, not adopted. No new ADR for c16i itself (rides ADR-6/27/32/33/34). Add
**QUALITY_GATES §21.1l** when it lands.
