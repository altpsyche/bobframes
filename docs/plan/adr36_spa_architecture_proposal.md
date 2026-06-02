# ADR-36 (PROPOSED) — Reports become an offline static SPA (app folder), with a single-file export

> **Status: PROPOSED — awaiting signoff.** On approval this is appended verbatim to
> [DECISIONS.md](DECISIONS.md) as **ADR-36** and the commit epic below is authored. It **amends**
> ADR-6 (single-file → app-folder + export) and ADR-34 (font location), and **supersedes** the c16i
> static-template approach. Nothing here is implemented yet.

## Context
Three design reviews ([overall_overhaul_proposal](overall_overhaul_proposal.md),
[readability_and_presentation_review](readability_and_presentation_review.md),
[report_roadmap](report_roadmap.md)) called for an SPA + decoupled data + shared assets to kill
eye-strain, the ~21 MB inline-data drill TTI, and the per-file CSS/font duplication. The naive form
(`fetch('_data/*.json')` + external `/assets/` + a CDN font) **breaks the offline contract**: `fetch`
of a local file fails on a `file://` page (CORS), so a double-clicked report would never load
(ADR-6), and a CDN font breaks ADR-34.

**The unlock:** browsers load `<script src>` and `<link href>` from `file://` (they are not subject to
the `fetch`/XHR same-origin block). So we can decouple data + share assets **without a server** and
still open by double-click — provided we load via injected `<script src>`, never `fetch`. The cost is
that the output becomes a **folder** rather than a single file.

**Decisions taken (user, 2026-06-02):**
1. **Offline mechanism:** static SPA via `<script src>` (no server; stays double-click-openable; byte-deterministic; output is a folder).
2. **Scope:** the **whole output** becomes the app — catalog + drill + dashboard + all 6 reports are SPA views.
3. **Single-file export retained:** still emit a deterministic self-contained `.html` (today's format) as a share/archive export, alongside the app folder.

## Decision (proposed)

### 1. `bobframes render` emits an **app folder** (the primary output)
```
<root>/
  index.html              # tiny SPA shell: <link _assets/app.css> + mount + <script src=_assets/app.js>
  _assets/
    app.css               # the ENTIRE design system, ONCE: design_tokens :root + chrome CSS +
                          #   the base64-inlined Inter subset (ADR-34 font, relocated + de-duplicated)
    app.js                # the SPA engine (static, deterministic): hash router + view loader +
                          #   the existing components (VTable, copy/search/sticky web components, run nav)
  _views/                 # one pre-rendered HTML FRAGMENT per route, server-rendered by the SAME
    dashboard.html        #   Python renderers (chrome.py / charts.py / reports/* / template.py) - NO
    report_pass_gpu.html  #   JS reimplementation of the presentation layer
    run_<key>_<report>.html
    catalog.html          # the catalog VTable shell (no rows baked in)
    drill_<area>_<drop>.html
    ...
  _data/                  # the HEAVY payloads, decoupled + lazy-loaded via <script src>
    catalog.js            # window.__bf_data['catalog'] = {...};
    drill_<area>_<drop>.js
    ...
```
- **SPA shell + hash router** (`#/dashboard`, `#/catalog`, `#/report/<name>`, `#/run/<key>/<report>`,
  `#/drill/<area>/<drop>`): on navigation, `app.js` injects the route's `_views/*.html` fragment into
  the mount and, for data-heavy views (catalog, drill), injects `<script src=_data/<key>.js>` once,
  then mounts the VTable over `window.__bf_data[...]`. No full-page reload; shared CSS/JS/font loaded
  once. This **fixes the 21 MB TTI** (only the current view's data loads) and the **per-file
  duplication** (one asset bundle).
- **Server-side rendering is REUSED, not reimplemented.** Views are rendered by the existing
  `reports/chrome.py`, `reports/charts.py`, the report modules, and `html/template.py` — emitted as
  fragments instead of whole pages. The c16b-f work (charts ADR-33, run model ADR-35, A/B, c16d
  aesthetics) is **re-homed as views**, not rewritten in JS.

### 2. Single-file static export (retained)
`bobframes export --single-file <view>` (and/or `render --single-file`) emits today's self-contained
HTML: the same view renderer with **data inlined** (`<script type=application/json>` / `window.__data`)
+ CSS/JS/font inlined, in one file. One renderer, two emit modes (external-`<script src>` for the app,
inlined for the export), parameterized by a `DataSink` (external file vs inline block). Lets a single
report be emailed/archived as one byte-deterministic file.

### 3. Offline + byte-determinism preserved (the non-negotiables)
- **No network, ever:** all loads are `<script src>` / `<link href>` of local relative files (work on
  `file://`); no `fetch`/XHR; font base64-inlined in `app.css`. Opens by double-click.
- **Byte-deterministic:** every emitted file (shell, `app.css`, `app.js`, each `_views/*.html`, each
  `_data/*.js`, the single-file export) is static, deterministic text (no `random`/`Date`/timestamps;
  the existing token/skeleton + fixed-precision discipline carries over). ASCII lint applies to all
  emitted text.
- **Golden gate restructures, discipline holds:** the parity gate extends from "the rendered HTML
  files" to "the app folder file-set + each file's bytes + the single-file export." `test_parquet_parity`
  is untouched (presentation only, §21.9).

## Amends / supersedes
- **ADR-6** (offline byte-deterministic single HTML file): amended to **"offline byte-deterministic app
  folder, double-click-openable via `<script src>` (no server), plus a single-file export."** The
  offline + determinism guarantees are preserved; the "single file" property moves to the export.
- **ADR-34** (vendored inlined Inter): font stays vendored + base64-inlined, **relocated** from per-page
  into `_assets/app.css` (loaded once). A CDN/network font remains forbidden. Net size **improves**
  (font no longer duplicated per page).
- **c16i** ([catalog + drill readability](commits/v02/c16i_catalog_drill_readability.md)): **superseded
  / folded in.** Its readability goals (type split, roomier rows, heatmap cells, collapsible column
  groups) are delivered **inside the SPA's catalog/drill views**, not as a separate static
  `template.py` pass. (G-21 will be closed by the SPA epic; G-22 is now ACCEPTED, not deferred.)

## Consequences (honest accounting)
- **This is the largest change in the project** and re-homes just-finished work (c16b-f) into views +
  adds a router/loader + restructures the golden gate + a second emit mode. It is **bigger than the
  rest of v0.2 combined**, and lands it **before the v0.2 tag** (your call), which materially delays
  the tag. Phasing below lets you choose how much lands pre-tag vs slips.
- **Output is a folder.** "Hand someone one file" now means the single-file export (or zip the folder).
  Tooling/links that assumed `_reports/<x>.html` paths change (the run-model per-run pages become
  routes, not files).
- **Risk concentrated in the golden-gate restructure + the data/view split.** Mitigated by migrating
  one view first (catalog) end-to-end before the rest, and by keeping the single-file export green
  throughout (proves the renderer still works standalone).
- **a11y + reduced-motion + print (c16c/c16d)** must survive the SPA: route changes manage focus +
  announce (`aria-live`), `noscript` shows a link to the single-file export, print still works per view.

## Proposed commit epic (phased; numbers to assign on approval, e.g. c16j–c16o)
1. **App spine + asset bundle + golden restructure.** Emit the shell + `_assets/app.{css,js}` (the
   design system + components + a minimal hash router) and migrate **one** view (catalog) end-to-end as
   a `_views/` fragment + `_data/catalog.js`. Restructure the golden to gate the folder. Proves offline
   double-click + determinism + the gate.
2. **Decouple the heavy data + lazy-load.** Move catalog + every drill payload to `_data/*.js` injected
   on navigation; the VTable mounts over `window.__bf_data`. Kills the 21 MB TTI.
3. **Re-home the reports + dashboard + run model as views/routes.** Dashboard, the 6 reports, A/B, and
   the c16e/c16f run model become hash routes (`#/run/<key>/<report>` replaces the per-run files).
4. **Single-file export path.** The `DataSink` abstraction (external vs inline) + `export --single-file`
   + its own golden. Keeps the standalone-file use case.
5. **Catalog/drill readability in the SPA (the c16i goals).** Type split, roomier rows, heatmap cells,
   collapsible column groups — now as SPA view features (closes G-21).
6. **Close-out:** re-ingest validation on the real Perf data (app folder + export), then tag v0.2.

## Open decisions (smaller; need a yes/no before authoring the commit docs)
1. **View fragments pre-rendered server-side (recommended, reuses Python renderers) vs client-rendered
   from data (a full JS reimplementation of charts/run-model — much larger, not recommended).** I
   recommend pre-rendered fragments; confirm.
2. **Routing: hash (`#/...`, zero-config on `file://`, recommended) vs History API (needs a server).**
   Hash, given the no-server decision; confirm.
3. **Does the SPA fully replace the current flat files now, or ship alongside them for one release**
   (SPA + the existing static `_reports/` during a transition)? Replace-now is cleaner; alongside is
   safer but doubles the golden temporarily.
4. **Tag timing:** land the whole epic before the v0.2 tag, or tag v0.2 at the close-out (c16e-h done)
   and ship the SPA as **v0.3** so it isn't rushed? (You asked for v0.2; flagging the cost so it's a
   deliberate choice.)
