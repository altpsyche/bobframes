# BobFrames — implementation state

> The resumption anchor. A fresh session reads this first, then opens the `current` commit doc.
> Update the three live fields (`current`, `last_session`, `next_action`) and the checklists before
> you stop. This file is the single source of truth for progress — commit docs mirror status but
> defer to this.

```
active_release: v0.2    (v0.1 COMPLETE — bobframes 0.1.0 live on PyPI 2026-05-31)
current:        c16o_table_a11y_parity    (status: not-started. c16n DONE 2026-06-03 - the c16k-c16n
                table-unification + truncation EPIC is COMPLETE. Authored close-out ORDER: c16n DONE ->
                c16o (table a11y parity: the VTable catalog/drill sort still has NO aria-sort - a
                pre-existing gap noted at c16l - so c16o adds aria-sort + keyboard-operable sort headers
                to BOTH rdc-table modes + a search-input aria-label) -> c16p (v0.2 close-out: FULL
                re-ingest + version 0.2.0 + CHANGELOG + push/CI/merge/tag) -> c20. c16n closed the last
                truncation-coverage gaps (ADR-38 tail): (1) draws_by_class area/drop cells now clip via the
                inner `.clip` (default tier, base.clip_span) - all 5 tabled reports + catalog/drill virtual
                consistent; (2) a `@media print` rule in `_RDC_TABLE_CSS` releases the bare dashboard/preview
                minis (`a.dash-card table.data` + the direct-child `.table-wrap > table.data` preview mini) to
                full-wrap on paper - the mini analogue of the static rdc-table print rule, which is
                data-mode=static-scoped + never reached the bare minis (table-layout:fixed KEPT - the 2-up
                print grid bounds each card); (3) mini `title=` kept UNCONDITIONAL (responsive widths, no
                deterministic server clip point - ADR-23 documented scoping in §21.1o, no heuristic, no new
                ADR). 188 -> 190 green; ALL 15 HTML goldens + preview refreshed (engine CSS inline on every
                page; draws_by_class also gains the `<span class="clip">` area/drop markup);
                `_pagedata`/digests/golden_parquet BYTE-UNCHANGED, parquet parity NO digests refresh (§21.9);
                smoke render-only 15 pages lint clean exit 0; browser-verified offline (draws_by_class clip
                spans + Expand-cells toggle injects, no JS errors; dashboard print-to-PDF shows every mini cell
                + header FULL, nothing clipped). QUALITY_GATES §21.1o extended. G-20 (3+-run column collapse)
                still deferred - no 3+-run data. ADR-37 governs (reports static); SPA VOIDED.)
last_session:   2026-06-03 — c16n DONE (truncation-coverage tail + dashboard print; ADR-38 tail; rides
                ADR-37/6/24/c16c/ADR-23). Two coverage gaps closed so EVERY tabled surface is consistent.
                (1) draws_by_class - the only tabled report c16m's scope skipped - now wraps its raw
                per-(area,drop) table's area + drop text cells in base.clip_span (default tier), so all 5
                tabled reports + the catalog/drill virtual tables clip + hover-reveal alike. (2) The bare
                dashboard/preview minis printed CLIPPED on paper: they have NO rdc-table host, so the c16m
                static print full-wrap (rdc-table[data-mode=static]-scoped) never reached them, and they rely
                on the global 380px td-clip + (dashboard) table-layout:fixed overflow:hidden, with no title=
                hover in print. A NEW @media print rule in _RDC_TABLE_CSS (co-located with the 380px clip it
                releases) frees BOTH bare-mini contexts to max-width:none; overflow:visible; white-space:normal;
                overflow-wrap:anywhere over cells AND headers: `a.dash-card table.data` (dashboard) +
                `.table-wrap > table.data` (the preview mini - a DIRECT child of .table-wrap; report tables
                interpose <rdc-table>, so the child combinator excludes them - they already have the static
                rule). table-layout:fixed is KEPT (the 2-up print grid bounds each card; auto could overflow).
                (3) Mini title= kept UNCONDITIONAL - mini column widths are responsive (table-layout:fixed + the
                3-up auto-fit grid), so the server has NO deterministic pixel clip point; a char-gate would drop
                title= on a genuinely-clipped short cell in a narrow card -> per ADR-23 the unconditional title=
                is kept + the rationale recorded in §21.1o (no fragile heuristic, no new ADR - rides ADR-38 +
                ADR-23). HARNESS: test_report_structure +test_c16n_draws_by_class_area_drop_clip (a clean
                False->True flip - the page carried no server-baked class="clip" before c16n; the engine JS
                applies clip via .className, never the literal); test_design_tokens
                +test_c16n_dashboard_mini_print_fullwrap (both bare-mini print selectors present in
                _RDC_TABLE_CSS, ASCII). PARITY (ADR-6/37/38): ALL 15 HTML goldens + the preview REFRESHED (the
                new print bytes ride the always-on engine CSS inline on every page; draws_by_class additionally
                gains the <span class="clip"> area/drop markup); `_pagedata/*.js` + digests.json + golden_parquet
                BYTE-UNCHANGED (git status scope); test_parquet_parity GREEN, NO digests refresh (§21.9). 188 ->
                190 green. smoke render-only 15 pages lint clean exit 0. BROWSER-VERIFIED OFFLINE (headless
                Chrome, file://): draws_by_class area/drop carry the .clip spans (4) + the Expand-cells toggle
                now injects (a .clip cell exists) with NO JS errors; the dashboard print-to-PDF shows every mini
                cell + header in FULL (headers wrap - "avg draws / frame", "complexity", "cost proxy" - nothing
                clipped). QUALITY_GATES §21.1o extended for the c16n coverage. No new ADR (mechanism within
                ADR-38; the title-keep within ADR-23, recorded in §21.1o). Commits on v0.2-roadmap-c04,
                UNPUSHED. current -> c16o.
former_last_c16m: 2026-06-03 — c16m DONE (controllable cell truncation + `title=` hover-reveal on the ONE
                `rdc-table` engine; ADR-38, FINAL of the c16k-c16m table-unification epic; rides ADR-37/6/24/c16c).
                ONE truncation mechanism, both modes: the clip lives on an INNER element - an in-cell
                `<a class="clip…">` or a `<span class="clip…">` (chrome.clip_attrs/clip_span helpers, re-exported
                via base) - NEVER the `<td>`, so a trailing rdc-copy-button / sparkline / rdc-heatmap-cell / `.lbl`
                label rides OUTSIDE the clip + stays visible/clickable (the reason c16l opted the td out). REMOVED
                the c16l no-clip stopgap (`rdc-table[data-mode=static]…td{max-width:none}`) + the td-level 380px
                clip from the global `table.data tbody td` rule (KEPT `white-space:nowrap`). THREE width tiers as
                CSS custom props on table.data: --clip-cap 320 (.clip) / --clip-cap-narrow 200 (.clip-narrow) /
                --clip-cap-wide 560 (.clip-wide). Full value ALWAYS in the DOM (Ctrl-F / selection-copy) + a
                length-gated `title=` reveals on hover (server-set static / JS-set virtual; thresholds narrow 24 /
                default 40 / wide 64 - short cells skip title to avoid SR double-read; synthetic+real src paths are
                short so the golden carries NO src title= - correct-for-data, NOT a gamed threshold, ADR-23). Copy
                `data-value=` + link `href=` keep the FULL value (c16c). Static builders emit `.clip…`/`title=` on
                the named long cells (shader_hotlist src=wide on the <a> so file-icon+copy ride outside;
                instancing mesh-label=default on the <a>, areas=default span, dominant-pass=narrow span; overdraw
                RT-label=default, format=narrow; trend area=default x3). VTable.cellNode wraps every NON-numeric
                windowed cell in a `.clip` (wide for _path/_hash/_hex/stable_key via new wideCols set, else
                default) + re-applies on every recycled render; numeric cells never clipped; the `.lbl`/heatmap
                stay on the td (outside clip); link nav-title NOT clobbered. GLOBAL expand/wrap toggle: the engine
                builds a real `<button class="rdc-expand-toggle" aria-pressed>Expand cells</button>` in JS (both
                modes, only when a `.clip` cell exists - no dead button) into a `.rdc-controls` bar before the
                host; click flips `data-expand`. Default = TRUNCATED; release is mode-aware: full-width SINGLE
                LINE both modes (so the VTable's fixed ROW_H stays valid - windowing would desync on multi-line),
                static ALSO wraps (`white-space:normal; overflow-wrap:anywhere`). PRINT (static only): table
                constrained to the page (`width:100%`, overriding width:max-content which else overflows+clips the
                paper edge) + `.clip…` flow `display:inline; white-space:normal; overflow-wrap:anywhere` so long
                unbroken paths WRAP within the page - nothing hidden on paper (no title tooltips in print);
                virtual is windowed/never print-complete so print stays static-scoped. ASCII (CSS ellipsis
                keyword). HARNESS: test_report_structure +4 c16m guards (long report cells carry the inner .clip…;
                src clip-span text == copy data-value == full path; toggle is a real <button aria-pressed> flipping
                data-expand; helper title= length-gated); test_design_tokens +2 (clip contract in _RDC_TABLE_CSS;
                dashboard-mini fit). TRUNCATION MODEL (review-fix): the 380px td-clip is the DEFAULT (kept for the
                un-enhanced bare dashboard/preview minis - no rdc-table host, no inner .clip); rdc-table cells opt
                OUT (`rdc-table table.data tbody td{max-width:none}`) + clip via the inner .clip. The dashboard mini
                tables also pin `table-layout:fixed; width:100%` (numeric cols compact, text cols flex) so a long
                label can't push the mini past its card + cut the rightmost column at the narrow 3-up grid width - a
                PRE-EXISTING overflow (minis' width:max-content overran the card regardless of c16m), fixed +
                guarded. MINI HOVER (review-fix): the minis are bare (not engine-hosted - sortable header in the
                card-link <a> would fight nav), so the BUILDER (dashboard._card_table) sets a server-side title= on
                their text cells + headers -> clipped mini values reveal in full on hover (cell text inline -> td ellipsis +
                Ctrl-F still work); the pass_gpu mini's marker column was builder-truncated (trunc_left, which
                DISCARDED the value so hover could never reveal it) -> now emits the FULL marker (CSS clips, title
                reveals), consistent with every other mini text column. PARITY (ADR-6/37/38): ALL HTML goldens refreshed (the engine CSS/JS is
                inline on every page - the c16l scope) + the static reports' new .clip…/title= markup;
                `_pagedata/*.js` + digests.json + golden_parquet BYTE-UNCHANGED (virtual clip is JS-applied at
                render; presentation-only); test_parquet_parity GREEN, NO digests refresh (§21.9). 181 -> 188
                green. smoke render-only 15 pages lint clean exit 0. BROWSER-VERIFIED OFFLINE (headless Chrome,
                file://): a crafted 162-char src path clips with ellipsis (copy button visible OUTSIDE the clip),
                the Expand-cells toggle reveals the full value (button injected aria-pressed=false, no data-expand
                by default), print full-wraps the path across lines within the page; the real heaviest drill
                (Commercial district 2026-06-01_r110788, 123,052 rows / 28 tables) recycles windowed rows with
                marker_path/marker_path_norm CLIPPED (…ellipsis) + 3026 .clip spans + 150 .lbl labels preserved +
                28 toggles injected, NO JS errors, ROW_H intact. QUALITY_GATES §21.1o added (the rdc-table
                truncation contract); ADR-38 epic COMPLETE (no new ADR - mechanism within ADR-38 scope, the
                deliberate single-line-virtual + correct-for-data title gating recorded in §21.1o per ADR-23).
                Commits on v0.2-roadmap-c04, UNPUSHED. current -> v0.2 close-out.
former_last_c16l: 2026-06-03 — c16l DONE (roll `rdc-table` out + delete the old systems; ADR-38, G-23 ROLLOUT
                half -> G-23 FULLY RESOLVED; single commit per user choice; rides ADR-37/6/24). Folded the
                engine CSS/JS into the ALWAYS-ON report bundle (chrome._compose_css/_compose_js gain
                _RDC_TABLE_CSS/_RDC_TABLE_JS); DELETED the c16k opt-in (the `rdc_table=` param on
                report_page/page_open + rdc_table_assets() + its base re-export) - kept rdc_table_css()/
                rdc_table_js() since template.py still composes the catalog/drill bundle itself (so NO
                double-include; template.py UNTOUCHED). MIGRATED every remaining static surface
                `<rdc-sortable-table><table class=report>` -> `<rdc-table data-mode=static data-table=<key>>
                <table class=data>`: overdraw, draws_by_class (default-sort moved to host), instancing x3,
                shader_hotlist secondary+resolved, trend x3; <td> CONTENT byte-stable (only wrapper/class
                moved) so type-split + auto-heatmap + client sort come FREE and ADR-37 holds (rows
                server-baked, JS-off/print/Ctrl-F/golden). The report-table semantics table.data lacked
                (styled <caption> [GLOBAL so bare minis get it too], first-child emphasis [static-scoped])
                moved into _RDC_TABLE_CSS; the 380px cell-clip is OPTED OUT in static mode (report cells hold
                copy-buttons/sparklines/links - c16m owns real truncation); the table.report print + narrow-
                viewport rules re-homed STATIC-SCOPED so catalog/drill virtual gain no render churn. COLUMN
                GROUPS added to overdraw (a separable current/per-drop-history split, history collapsed,
                index-keyed __colgroups_overdraw shared across the per-area tables via the section-scoped bar
                lookup) alongside shader_hotlist; instancing/trend/draws_by_class kept as clean sort+heatmap -
                they have no separable wall so a collapse would hide the headline metric (deliberate ADR-23
                scoping, recorded). A11Y: StaticTable now sets aria-sort none->ascending/descending on headers,
                restoring the sort-state announcement the deleted rdc-sortable-table provided (the unified
                engine never had it - a c16k gap; fixed at root). DELETED rdc-sortable-table (web component +
                CSS + RdcSortableTable JS class + customElements.define) and the now-dead table.report CSS
                (main block + a/caption/dash-card/responsive/print) - grep-clean (no rdc-sortable-table /
                RdcSortableTable / class="report" anywhere in source). DASHBOARD/PREVIEW minis -> bare
                `<table class=data>` (NOT wrapped: a sortable header inside the card-link <a> would both sort
                and navigate); unified styling, no enhancement. HARNESS: test_report_structure swapped the 2
                c16k coexistence guards for c16l guards (test_c16l_sortable_table_deleted = grep-clean over
                every page; test_c16l_all_tabled_reports_on_static_rdc_table = every tabled report static +
                server-baked <tr>, pass_gpu none, dashboard minis bare; test_c16l_engine_in_shared_report_bundle
                = engine in _compose_*, aria-sort present, rdc_table_assets gone, no rdc_table param);
                test_c16i_reports_layer_untouched widened col-groups exemption to {shader_hotlist, overdraw};
                test_design_tokens caption assert re-pointed to rdc_table_css() (table.data > caption). PARITY
                (ADR-6/37/38): REFRESHED all 6 reports + dashboard + 6 per-run + catalog index + drill index +
                the preview gallery (reports/dashboard by markup+bundle; catalog/drill by the dead-byte removal
                + the inert static-scoped CSS the embedded engine string now carries - verified ZERO body-markup
                change, virtual host intact); _pagedata/*.js + digests.json + golden_parquet BYTE-UNCHANGED (git
                status scope); test_parquet_parity GREEN, NO digests refresh (presentation only, §21.9). 180 ->
                181 green. smoke render-only 15 pages lint clean exit 0. BROWSER-VERIFIED OFFLINE (headless
                Chrome, file://): static reports show all rows JS-off + enhance in place (sort + aria-sort
                desc on shader_hotlist/draws_by_class default-sort cols + auto-heatmap [shader_hotlist 125 tinted
                cells; overdraw/trend no-tint = correct-for-data, 1 area / flat cols] + real column-group toggle
                BUTTONS [3 on shader_hotlist + overdraw, 0 elsewhere], NO JS errors, no clipped widgets); dashboard
                minis stay un-enhanced; catalog/drill virtual unchanged. QUALITY_GATES §21.1n added; G-23 ticked
                FULLY DONE. NOTE (minor, recorded): the VTable (catalog/drill) sort still has no aria-sort -
                pre-existing, separate a11y pass. Commits on v0.2-roadmap-c04, UNPUSHED. current -> c16m.
former_last_c16k: 2026-06-03 — c16k DONE (build the unified `rdc-table` component; ADR-38, G-23 BUILD half;
                rides ADR-37/6/24). Replaced the two divergent table systems' ENGINES with ONE bespoke
                `rdc-table` (NO third-party grid). It lives in reports/chrome.py (_RDC_TABLE_CSS +
                _RDC_TABLE_JS + rdc_table_css/js/assets(), re-exported via base.py) and is a SINGLE IIFE:
                shared cmpVals (natural-numeric ADR-24, comma-strip so it's correct for raw JSON numbers
                AND comma-formatted display text) + shared tintImage (the uniform-tint color-mix heatmap),
                a `VTable` class (the SUBSUMED virtual engine: windowed, data from window.__data_<key>) and
                a NEW `StaticTable` class (in-place: parses the server-baked <table class=data>, sorts by
                reordering live <tr> nodes, tints existing <td>s, toggles column visibility via display).
                Bootstrapped from ONE DOMContentLoaded pass (querySelectorAll('rdc-table[data-mode]'), branch
                on data-mode) - NOT a customElements/connectedCallback (dodges the parse-time empty-children +
                defer-script race; matches the old VTable timing). The host element <rdc-table data-mode=
                "static|virtual"> picks delivery (an explicit attribute, ADR-38). VIRTUAL (catalog/drill,
                html/template.py): the old _JS/_JS_TMPL/_ROW_H were DELETED (referenced only here -> zero
                dead code) and the engine emitted via reports_base.rdc_table_js(); the host div.table-scroll
                -> <rdc-table class=table-scroll data-mode=virtual data-table=...>; jumpToTable selector
                follows; the c16j _pagedata/*.js payload + the inline __colgroups_catalog/__labels are
                UNCHANGED (byte-identical, the k1 correctness check). The table.data/col-groups/type-split
                CSS + the --th-bg/--th-bg-active/--label :root vars MOVED from template._PER_DROP_CSS into
                chrome._RDC_TABLE_CSS (so ONE class serves both contexts); template._compose_css() now =
                design_tokens + chrome_css + rdc_table_css + the _PER_DROP_CSS remainder (drill-only
                hierarchy/toc/controls/table-scroll+loading-hint). STATIC (the proof = shader_hotlist main
                table): wrapper rdc-sortable-table -> <rdc-table data-mode=static data-default-sort="cost
                proxy" data-table=shader_hotlist>; table.report -> table.data; column-groups spec
                window.__colgroups_shader_hotlist keyed by COLUMN INDEX (multi-drop repeats the "delta"
                header, so name-keying would collide) - identity+cost open, the per-drop history wall
                collapsed (empty -> dropped on single-drop); src cell gets class=mono. Cells KEEP class="num"
                (not reclassed to numeric) - a NEW `table.data ... .num` CSS ALIAS in _RDC_TABLE_CSS gives
                them the numeric/mono treatment WITHOUT touching the shared delta/heatmap/sparkline cell
                helpers (cleaner than reclassing; <td> text byte-stable). The engine is emitted OPT-IN via
                report_page(rdc_table=True) -> page_open appends rdc_table_assets() to <head>; default-False
                keeps the shared _compose_css/js() bundle UNTOUCHED so the 4 non-migrated reports + dashboard
                + per-run/A-B goldens stay BYTE-IDENTICAL. rdc-sortable-table is KEPT ALIVE (still wraps the
                shader_hotlist secondary + resolved tables and the 4 other reports) - c16l deletes it. A
                sticky-in-card guard (section.card table.data thead th{position:static}) prevents the c16c
                floating-header bug on the report; a static-only nth-child zebra replaces the virtual .alt.
                HARNESS: test_report_structure +4 c16k guards (rdc-table virtual on catalog/drill; static
                proof server-baked rows un-windowed + index-keyed colgroups + col-groups bar; static coexists
                with rdc-sortable-table; other reports carry NO rdc-table) + test_c16i_reports_layer_untouched
                updated to exclude shader_hotlist's legit col-groups. PARITY (ADR-6/37): refreshed EXACTLY
                catalog index.html + the one drill index.html + BOTH shader_hotlist.html variants (top-level +
                the per-run one, same build()); _pagedata/*.js BYTE-IDENTICAL (payload shape unchanged); the
                other 5 reports + dashboard + per-run + digests.json BYTE-UNCHANGED (git status scope);
                test_parquet_parity GREEN, NO digests refresh (presentation only, §21.9). 176 -> 180 green.
                smoke render-only 15 pages lint clean exit 0. BROWSER-VERIFIED OFFLINE (headless Chrome,
                file://): real Perf catalog (1 built table.data, heatmap+col-groups) + heaviest drill
                (Commercial district 2026-06-01_r110788: 28 built tables, windowed rows, 2026 heatmap cells)
                still scroll/sort/search in VIRTUAL; shader_hotlist STATIC has 50 server-baked rows UN-WINDOWED
                (JS-off/print/Ctrl-F safe), 3 col-group toggles (multi-drop incl history), sort arrows,
                rdc-heatmap-cell shading. The static auto-heatmap + natural-numeric sort + group-collapse code
                paths PROVEN on a crafted varying-data table (real Perf's uses/cost are all 0 -> no variance ->
                no auto-tint, which is correct-for-data; complexity is shaded via rdc-heatmap-cell). ADD
                QUALITY_GATES §21.1m. G-23 NOT ticked yet (resolves at c16l). Commits on v0.2-roadmap-c04,
                UNPUSHED. current -> c16l.
former_last_c16j: 2026-06-03 — c16j DONE (decouple the heavy catalog/drill data; the html/template.py layer;
                the ~21MB TTI fix; STATIC per ADR-37, NO SPA; no new ADR - rides ADR-6/27/34/37). Moved each
                VTable's heavy row payload OUT of the HTML into its own _pagedata/<key>.js
                (window.__data_<key>={...};, same compact json.dumps(separators=(',',':'))) referenced by a
                CLASSIC file://-safe <script defer src> (NO fetch, NO ES modules - Chrome blocks file:// module
                loading). NEW paths.PAGEDATA_DIR='_pagedata': a sibling dir of each page's index.html (catalog
                <root>/_pagedata/; drill <root>/_reports/drill/<area>/<drop>/_pagedata/), deliberately NOT _data/
                (the parquet/data contract) - so the src is ALWAYS literally _pagedata/<key>.js (no relpath, no
                collision); a deliberate, user-confirmed refinement of the c16j doc's loose _data/<key>.js. NEW
                template._write_page_data writes the .js + returns the src; _inline_table_with_data now returns
                (section, key, payload) and the CALLER (render_drop/render_root) does the file I/O. Only the
                HEAVY __data_* moves; the small __colgroups_catalog/__labels + the shared _JS VTable code stay
                INLINE (small vs MB of data; avoids a depth-aware shared-asset path). The data scripts are
                <script defer src> at end of <body>; the inline _JS just registers the DOMContentLoaded listener
                (reads __data_* ONLY inside it) -> defer files run after parse + before DCL -> shell paints first,
                NO onload race. CSS-only .table-scroll:empty::before{content:'loading...'} in _PER_DROP_CSS
                (catalog/drill only) shows until the VTable injects rows. HARNESS:
                _render_util.rendered_page_data_files (walks _pagedata/*.js by parent-dir basename); make_golden
                writes the .js companions raw (LF, no normalize); test_parity gains a 2nd block (file-set
                equality + byte-compare, no normalize); test_report_structure's `rendered` fixture also loads the
                .js, the __data_catalog read is repointed to the companion, +5 c16j guards (catalog/drill
                externalized, .js deterministic+offline+ASCII, reports have no _pagedata, loading-hint
                catalog/drill-only). PARITY (ADR-6/37): ONLY the catalog index.html + the one drill index.html
                refreshed + the added _pagedata/*.js (1 catalog + 26 drill = 27); reports/dashboard/per-run/A-B
                goldens BYTE-UNCHANGED + digests.json untouched (verified by git status scope);
                test_parquet_parity GREEN, NO digests refresh (presentation only, §21.9). 171 -> 176 green (+5
                c16j guards). smoke render-only 15 pages lint clean exit 0. BROWSER-VERIFIED OFFLINE (headless
                Chrome, file://, real Perf at C:\tmp\perf): the catalog + the heaviest FRESHLY-RENDERED drill
                (Commercial district 2026-06-01_r110788: ~17.6MB single file -> 134KB shell + 17.5MB across 28
                _pagedata/*.js) populate their VTable from the .js with c16i's type split + heatmap + column
                groups intact - the TTI win is real. NOTE (not a c16j bug, pre-existing): render-only re-renders
                ONLY the current-run drop per area, so OLDER-run drills (e.g. Commercial district
                2026-05-25_r110565) stay STALE 29MB inline-data files until the v0.2 close-out FULL re-ingest
                regenerates them. QUALITY_GATES §21.1l consolidated (c16i + c16j); G-21 ticked FULLY DONE + G-22
                resolved (SPA rejected; heavy data decoupled statically). Commits on v0.2-roadmap-c04, UNPUSHED.
                current -> v0.2 close-out.
former_last_c16i: 2026-06-03 — c16i DONE (catalog + drill readability; the html/template.py layer; G-21
                readability half; no new ADR - rides ADR-6/27/32/33/34/37). Brought the c16d treatment to the
                STATIC catalog (root index) + per-drop drill VTable: (1) TYPE SPLIT - table.data defaults to
                the Inter sans stack at line-height 1.3, mono+tabular-nums re-asserted ONLY on numeric/.mono
                BODY cells via LONGHANDS (headers stay sans; a name-keyed monoCols set keeps id/hash/path cols
                mono). (2) ROOMIER ROWS - ROW_H single-sourced from Python _ROW_H=32 (sentinel-substituted
                into _JS; JS is the SOLE virtual-scroll driver, CSS sets NO row height or it fights the dynamic
                spacers), 6px padding (14px x 1.3 + 12 + 1 = 31.2 <= 32 -> no overflow -> no scroll drift).
                (3) HEATMAP - numeric MAGNITUDE cells (excl. id/event_id/labelCols + single-value) shade the
                WHOLE cell by relative value via background-IMAGE only (uniform color-mix(--accent-data
                0-30%); user rejected the first length+gradient bar as "looks like an artifact"), so the class
                background-color zebra/hover shows through; deterministic, aria-labelled. (4) COLUMN GROUPS
                (catalog only) - deterministic group->col map from schemas.table_category (Metadata/Workload/
                Resources/Samples, Metadata+Workload open) as window.__colgroups_catalog; VTable builds real
                <button aria-pressed> toggles + hiddenCols, sort-arrow loop keyed on th.dataset.ci so it stays
                correct with hidden cols. POST-FEEDBACK fixes: .table-scroll sizes to content capped at 60vh
                (small tables stop reserving an empty 60vh box; folded in the never-applied .short variant);
                drill VISUAL HIERARCHY - details.category became a left-anchored bold-accent group LABEL +
                nesting rail (the count was centering because the +/- marker was a 3rd space-between flex item)
                and each section.table-section became a CARD; all hierarchy/card CSS lives in _PER_DROP_CSS so
                the reports/dashboard goldens stay byte-unchanged. test_report_structure +6 c16i guards. PARITY
                (ADR-6): root index.html + the one drill golden refreshed + BROWSER-reviewed (light/dark,
                synthetic AND real Perf at C:\tmp\perf, 14 drops/16 captures, headless screenshots + injected
                color-scheme); reports/dashboard/per-run goldens BYTE-UNCHANGED; test_parquet_parity GREEN with
                NO digests refresh (presentation only, §21.9). 165 -> 171 green. QUALITY_GATES §21.1l added;
                G-21 readability half ticked (heavy-data half = c16j); G-23 OPENED (two table systems - reports
                table.report/rdc-sortable-table vs the drill VTable - unify post-v0.2, likely with c20/c30).
                Commits on v0.2-roadmap-c04, UNPUSHED. current -> c16j.
former_last_c16f: 2026-06-02 — c16f DONE (multi-run UX: the run selector; G-18 closed; builds on ADR-35).
                Layered the navigation UX on c16e's run model. Mechanism = PRE-RENDERED per-run pages: the
                top-level _reports/<report>.html is the newest run (default); each OLDER run gets a
                self-contained set under _reports/run/<run_key>/ (mirrors _reports/ab/<pair>/), bounded by NEW
                config [report] max_prerendered_runs (default 10), orchestrator LOGS anything dropped beyond
                the cap (no silent truncation, ADR-23; overflow reachable via trend_table, which is NOT
                pre-rendered per run). NEW chrome: run_picker/run_picker_for (reuse the rdc-ab-picker web
                component - a static <select> whose value is a relative link, no network/new JS; distinct
                rdc-run-select id; depth-prefixed so links resolve from both top-level and run/<key>/),
                run_compare_banner ("current <x> vs baseline <y>", reuse .ab-strip, baseline dimmed via .dim),
                and an "viewing an older run" callout (non-newest only, links to newest). report_page emits
                them from the same run= RunContext (+ a run_nav_key so the dashboard, which carries no
                report_key, drives the picker as 'index'); A/B pages suppress the picker+banner (ab not None);
                top-level pages keep the A/B picker, per-run pages omit it. Selection PERSISTS dashboard ->
                per-report (each run/<key>/ is a self-contained sibling set; only trend_table + the A/B index
                point up via depth-prefix). cli: output_path/crumb_depth take run=, NEW run_subdir,
                run_report --run-label/--run-date; orchestrator renders the per-run set; all 6 build()s gain
                run_label/run_date. VERIFIED in a browser (light+dark, top-level: picker + "current vs
                baseline" banner; per-run older dashboard: "run 1 of 2", its OWN numbers (total draws 7,957
                not the newest's 4,417), the older-run cue, the picker - the c16d visual language holds with
                the new chrome). NOTE (not a bug): the synthetic's OLDER drop lacks pass_class_breakdown
                (make_synthetic SKIPS it; render-only regenerates derived tables for the newest scope only),
                so the per-run older dashboard's pass-gpu + draws-by-class CARDS show "no data yet" - the
                TRUTHFUL per-run result (it does NOT borrow the newest run's pass data; that borrowing was the
                very G-19 flaw). Real ingests carry pass_class_breakdown on every drop. PARITY (ADR-6/35):
                golden gained 6 per-run pages + the picker/banner on the 6 top-level pages; trend_table/drill/
                root/preview goldens UNCHANGED; test_parquet_parity GREEN, NO digests refresh (§21.9). 142 ->
                148 green (+6 test_run_model c16f: per-run set, picker lists+marks+resolves, older-run cue,
                banner, nav persistence, A/B suppresses picker; +1 test_config max_prerendered_runs). smoke
                15 pages lint clean exit 0. QUALITY_GATES §21.1k added; G-18 ticked. G-20 (per-drop column
                collapse at 3+ runs) DEFERRED - no 3+-run data exists to verify + a 3-run golden fixture
                cannot be added without a forbidden digest refresh; rationale recorded in FINDINGS (ADR-23).
                Commits on v0.2-roadmap-c04, UNPUSHED. current -> v0.2 close-out.
former_last_c16e: 2026-06-02 — c16e DONE (per-run truth; the run model; G-19 closed; ADR-35). The real Perf
                2-run ingest exposed that the dashboard + 5 single-state reports defaulted to
                discover_drops=ALL drops and aggregated CUMULATIVELY, so work removed in the newer run still
                showed (total draws = run1+run2 summed; instancing listed a run1-only mesh as live; the
                draws-by-class donut summed both). FIX = a single run model: NEW reports/discovery.py
                current_run/baseline_run + a RunContext carrier (resolved per build via run_context,
                re-exported via base), threaded into chrome.report_page/header as ONE run= arg -> every
                report names its run ("run 2 of 2: <key>") and a new report gets per-run truth for free
                (can't silently re-introduce the bug). Rerouted dashboard (_global_kpis + _top_* helpers
                scoped to [current]; the 2 cache-readers _top_meshes/_top_shaders filter the global cache by
                (drop_date,drop_label)) + instancing (live = current-run meshes; batching ALSO scoped -
                corrected on review; per-drop repeat/delta cols kept; resolved-since card) + draws_by_class
                (donut/headline = current run; raw per-(area,drop) table keeps both) + shader_hotlist (rank
                shaders PRESENT in current run by current cost; resolved-since by presence; KPIs over
                present; uses-total col -> "uses (current)") + pass_gpu (hero/treemap/ranking off the
                current-run bucket not cross-drop max; per-drop GPU cols kept) + overdraw (live RTs = current
                run; rep/latest bucket = current not oldest; renamed a shadowing loop-var `cur`->`cur_n` to
                protect the RunContext - the D-12 class of bug). trend_table + A/B UNTOUCHED (across-run
                views; A/B's pair makes current=compare for free). VERIFIED numerically (dashboard total
                draws 4,417 = newest drop only, not 12,374 summed) + by EYE in a real browser (light + dark,
                all 6 reports: each names its run, donut centre 60 = current run while the raw table keeps
                both 60+60, resolved-since renders as a separate card on instancing + shaders). PARITY
                (ADR-6/35): HTML golden REFRESHED (dashboard + 5 reports ONLY; trend_table/drill/root/preview
                + parquet digests BYTE-UNCHANGED - exactly the predicted scope); test_parquet_parity GREEN,
                NO digests refresh (§21.9). 132 -> 142 green (+8 test_run_model resolver/invariant/header,
                +2 test_report_structure header+resolved). smoke render-only 9 pages lint clean exit 0.
                ADR-35 appended; G-19 ticked + G-20 opened (3+-run column collapse -> c16f); QUALITY_GATES
                §21.1j added. Commits on v0.2-roadmap-c04, UNPUSHED. current -> c16f.
former_last_c16d: 2026-06-02 — c16d DONE (report VISUAL OVERHAUL / design-language pass; G-17 closed; ADR-34).
                Shipped as 4 reviewable sub-commits, each golden-refreshed + BROWSER-reviewed (light/dark/
                reduced-motion/print via Chrome headless; minified pages are not line-diffable). (a) DEPTH
                over borders [9079013]: cards/chrome read by surface + soft elevation shadow (NEW [shadow]
                block --elev-1/2/3 via the ADR-27 skeleton; two-layer ring+drop, tuned for light since dark
                rides surface-lightening), report tables horizontal-rule only, severity = color-mix box tint
                (not a left rule), sticky-h2 in-view cue moved to a ::before accent marker (h2 left-accent
                gone; JS unchanged - verified by forcing aria-current), reduced-motion safety via
                --hover-scale:1 + --motion-spring:0s, print re-adds a 1px #888 paper border + box-shadow:none.
                (b) TYPE [d67c5c2]: VENDORED Inter subset (reports/assets/inter-subset.woff2, 29KB, Latin +
                tnum, wght 400-600) baked into the wheel + base64-inlined @font-face at import (offline +
                byte-deterministic; NO CDN - ADR-34 overrides the c16d-doc "no web font" with user signoff);
                KPI/summary display numbers + headings now Inter sans + tabular-nums, data tables stay mono.
                (c) CHART FINISH [783840e]: gradient fills on bar/histogram/scatter (deterministic
                caller-threaded chart_id ids - NO hash/counter), dimmed axes (axis_color -> --border-1),
                per-datum <title> tooltips on bar + per-series on line. (d) MICRO + PACING [20b82c7]:
                dash-card hover scale(var(--hover-scale)) + spring lift, copy-button resting tint,
                section.card padding sp-4 -> sp-6, .dim utility on shader drop-key suffixes. PARITY
                (ADR-6/27/34): golden HTML + preview REFRESHED all 4 commits, structural-marker + browser
                reviewed; test_parquet_parity GREEN with NO digests refresh (presentation only, §21.9).
                115 -> 128 green (+test_fonts x5, +test_charts gradients/titles/axis x5, +test_design_tokens
                shadow/motion/depth/micro x3). smoke render-only 9 pages lint clean exit 0. Wheel verified:
                ships inter-subset.woff2 + Inter-OFL.txt + README, 162/162 unique entries (ADR-10 holds).
                ADR-34 appended; G-17 ticked; QUALITY_GATES §21.1i added; c16d doc move #2 updated. Commits
                on v0.2-roadmap-c04, UNPUSHED. current -> v0.2 close-out (full-area ingest + tag).
former_last_c16c: 2026-06-02 — c16c DONE (report RESTRUCTURE; G-15 FULLY closed - both halves landed). Routed
                every report section through chrome.section_card wrapped in <rdc-sticky-h2> (relaxed the
                component selector h2[id] -> h2 so a card's id-less header h2 still drives the in-view
                highlight; section ids stay the anchors, so #area/#gpu/#class_counts resolve unchanged).
                Per-area section cards in pass_gpu + overdraw; 2 cards in draws_by_class + instancing; 1 in
                shader_hotlist; 6 in trend_table (KPIs + class_counts). rdc-copy-button on the 3 named
                copyable IDs (FULL value, via safe_chrome_text even inside <td>): mesh hash (instancing),
                shader stable_key + src path (shader_hotlist), pass path (pass_gpu). Instancing "material
                batching" is now FILL-OR-HIDE (no bare heading over an empty-state; synthetic has none ->
                id="batching" gone from golden). A11Y: <caption> + scope="col" on every report + dashboard
                table (zero bare <th> left); trend gpu-delta KPI prints an explicit sign (regression
                direction not tone-colour-only); print + reduced-motion media queries already cover the new
                card border + copy-button transition. DASHBOARD small-multiples: a mini chart per card (mini
                bars for trend/instancing/pass/shader/overdraw; a class-share DONUT for draws_by_class,
                matching its flagship - user-chosen "match each flagship") + an insight subtitle per card +
                a cross-report chip nav. NEW card-framing CSS in _CHROME_CSS_TMPL (literal var(), no $) ->
                drill/root/preview change ONLY by that shared CSS. PARITY (ADR-6/32/33): HTML golden (9
                pages) + preview REFRESHED, reviewed via a per-report structural-marker diff (cards/sticky/
                copy/caption/scope IN, bare h2/th OUT; fill-or-hide batching 1->0); test_parquet_parity GREEN
                with NO digests refresh (presentation only, §21.9). 108 -> 115 green (+7 NEW
                tests/test_report_structure.py: section_card+sticky present, full-length copy payloads on the
                3 reports, th/scope balance + caption on tabled reports, instancing fill-or-hide, dashboard 6
                mini charts + 6 subtitles + nav, whole-page ASCII guard) + test_design_tokens c16c card-CSS
                asserts. smoke render-only 9 pages lint clean exit 0. No new ADR (card framing rides ADR-32
                report contract + ADR-33 chart model; the c16b->c16b+c16c split already recorded). G-15
                ticked FULLY DONE; QUALITY_GATES §21.1h added. POST-COMMIT REVIEW FIXES (user
                eyeballed rendered pages, 3 follow-up commits, golden re-refreshed each, 115 green):
                480bfaa - delta alarm gated to regressions only (was abs()-magnitude -> red border on
                -100% improvements; -24 false red bars in instancing), sticky thead made static inside
                section.card/a.dash-card (a pinned header detached and floated over a framed card,
                stranding the first row above it), inner .table-wrap goes borderless (card is the single
                frame, no box-in-box), bar-label clip made width-aware. b88f055 - dashboard mini chart
                transparent+borderless (was a boxed panel above the borderless table). 3801a13 - bar_chart
                label column now sized to the LONGEST actual label (was fixed W*0.36 -> dead space between
                text and bar) so the bar starts right after the text on every chart; minis show full
                labels again. current -> v0.2 CLOSE-OUT (NOT c20 yet; ingest + tag pending).
former_last_c16b: 2026-06-02 — c16b DONE (report CHARTS; G-15 charts half; ADR-33 implemented). c16b was
                NARROWED in execution (user-chosen): ships the chart slice + the shader column diet; the
                heavier restructure split into NEW c16c (section-cards/sticky spread, copy-buttons,
                dashboard small-multiples, fill-or-hide, fuller a11y) so the golden stays reviewable
                (ADR-23 documented scoping). NEW reports/charts.py = deterministic dependency-free
                inline-SVG toolkit (bar/stacked/pct_stacked/donut/scatter+bubble/treemap/icicle/
                histogram/multi-series line + a figure() wrapper), extends delta.sparkline_svg
                (fixed-precision coords, NO random/Date/timestamps); colors are CSS var() refs (light-dark
                aware), draw-class series via class_color_var; ALL emitted text routed through
                safe_chrome_text (scrub+escape) so data-derived labels can never trip the page lint
                (charts ride OUTSIDE <table> → linted). NEW [chart] block in design_tokens.toml (sizes +
                var() palette) + _tokens.chart() accessor (NOT a :root section, never leaks to CSS/golden).
                Chart wrapper CSS (figure.chart/.chart-svg/details.secondary-metrics) added to
                _CHROME_CSS_TMPL (literal var()-based, no $); re-exported via base.py. FLAGSHIP per report
                above its table (table kept as exact/accessible fallback): pass_gpu treemap GPU-by-pass +
                top-pass bars; draws_by_class class-share donut + per area/drop pct_stacked (replaced the
                old class_segments_bar bar-rows); shader_hotlist complexity-vs-cost scatter (bubble=src
                bytes) + complexity histogram; overdraw reject%-per-RT bars with config warn/alarm
                rule-lines; instancing wasted-index bars; trend_table per-KPI line lead. shader_hotlist
                COLUMN DIET: 13 → 7-col primary (shader/complexity/uses/cost/flags/src) + collapsible
                <details class="secondary-metrics"> table (branches/loops/discards/dfdx-dfdy/tex
                samples/src bytes). NEW tests/test_charts.py (golden-independent: determinism, SVG
                structure role/title/desc, token theming, empty-series→'', element counts, ASCII guard) +
                test_design_tokens [chart]-block + chart-CSS asserts. NEW tests/make_golden.py (repeatable
                HTML-golden refresh: render_fresh→normalize ts→LF, mirrors make_preview_golden). PARITY
                (ADR-6/32/33): golden HTML REFRESHED (9 pages; reviewed page-by-page — 6 reports gain
                <figure class="chart">, drill/root/dashboard change only by shared chart CSS) + preview
                golden; test_parquet_parity GREEN with NO digests refresh (presentation only, §21.9).
                99 → 108 green; smoke render-only 9 pages lint clean exit 0. No new ADR (ADR-33 covers
                charts; the c16b→c16b+c16c split recorded in STATE + both commit docs, mirroring the
                un-ADR'd c16/c16b split). G-15 (charts half) ticked; QUALITY_GATES §21.1g fleshed; c16c
                authored. current → c16c.
former_last_c16: 2026-06-01 — c16 DONE (report-quality polish + mechanics; user pushed reports 5/10 → aim
                10/10, so the work SPLIT into c16 + NEW c16b). MECHANICS: R-13 (reports/cache SHA256
                sidecar + new load_cached → corrupt/missing/mismatch logs a warning + returns None so
                readers fall back to a live scan, never silent-empty; missing-column tolerant; routed
                shader/instancing/dashboard readers through it). Q-9 (_dashboard.py → dashboard.py +
                4 refs: cli/orchestrator/ab/in-file). D-4 + D-7 (manifest.check_schema_version +
                assert_compatible: render+catalog guarded via catalog.build_catalog, ab via ab.main →
                PipelineError exit 1 + `ingest --force` hint; synthetic manifest is schema v3 so the
                guard is PARITY-NEUTRAL). D-11b dead-code swept (chrome.footer_legend + base re-export,
                html.template._row_count, dead footer.legend + .sidecar-list span CSS, replay `if False`
                rt_double). PRESENTATION POLISH: NEW chrome builders kpi(existing)/callout/heatmap_cell/
                provenance_strip/empty_state + report_page device=; config [report] thresholds (ReportCfg,
                H-39). All 6 reports + dashboard now lead with a hero KPI strip + an insight callout
                (severity from thresholds) + a header provenance/device strip (GPU/driver/CPU/OS +
                renderdoccmd/qrenderdoc from the newest drop's manifest; bobframes version OMITTED so a
                release bump never churns the golden) + heatmap-shaded ranked columns + readable labels
                (ASCII `x` not `*`/`×` — `×` is in the lint banlist; draws/verts; cost-proxy/wasted
                tooltips) + icon empty-states. Synthetic manifests gained fixed host_info/tool_versions
                stubs (+ make_synthetic). PARITY (ADR-6/32): golden HTML REFRESHED (9 pages, ts-normalized
                to <TS>, LF; reviewed — drill/root deltas are only the D-11b dead-CSS removal + the shared
                .callout/.empty-state rules) + preview golden; test_parquet_parity GREEN with NO digests
                refresh (extraction untouched, §21.9). 74 → 99 green (+test_delta/test_manifest_guard/
                test_cache/test_report_polish, +test_config [report], +test_design_tokens c16 CSS). smoke
                render-only 9 pages lint clean exit 0. ADR-32 (report contract) + ADR-33 (inline-SVG chart
                model, for c16b) appended; QUALITY_GATES §21.1f/§21.1g. R-13/Q-9/D-4/D-7 + H-39 ticked;
                D-11b DONE; G-15 (report info-design) + G-16 (sparkline-null unreachable in live path)
                opened. c16b authored (commits/v02/c16b_report_viz.md): inline-SVG chart toolkit + flagship
                chart per report + column-diet/section-cards/copy-buttons.
former_last_c10: 2026-06-01 — c10 DONE (env-var rename RDC_*→BOBFRAMES_*; completes R-5 + resolves Q-5;
                ADR-31). NEW config.getenv_legacy(canonical, legacy, default) = the SINGLE source for the
                one-release legacy cadence, reusing c06's _warn_legacy_once + _warned_legacy one-shot
                machinery. RDC_KEEP_STAGE→BOBFRAMES_KEEP_STAGE (run.py _do/process_drop cleanup gate) +
                RDC_PIXEL_GRID→BOBFRAMES_PIXEL_GRID (host sets it in main + _do_replay so the qrenderdoc
                child inherits it via os.environ; host reads back via getenv_legacy; replay_main reads
                BOBFRAMES_PIXEL_GRID or RDC_PIXEL_GRID INLINE — embedded py3.10 can't import config, H-6).
                RDC_ROOT ELIMINATED (ADR-31, user picked the cleaner route): investigation found
                parse_init_state is cwd-INDEPENDENT (consumes no project root; writes only under the
                absolute capture_stage), so RDC_ROOT was only ever the parse-child cwd and _do_parse always
                set it = project_root (triple-dirname fallback dead) → threaded project_root into
                _parse_one's args (now a 7-tuple) as the explicit subprocess cwd; deleted the global
                os.environ['RDC_ROOT'] set/restore (R-5). NO --project-root flag added to parse_init_state
                (would be dead surface — ADR-23). RDC_INSIDE_ARGS kept verbatim (3 consumers:
                qrd_harness/replay_main/probes.whatif — the qrenderdoc↔harness wire). 70→74 green (+3
                getenv_legacy precedence/warn-once/default, +1 _do_parse env-untouched R-5 lock; fixed
                test_hardening _parse_one 6→7-tuple). PARITY (ADR-6): golden HTML + Parquet BYTE-IDENTICAL,
                git clean, NO refresh; smoke render-only 9 pages lint clean exit 0; grep RDC_ROOT = only
                comments/test asserts, ZERO reads. Q-5 ticked; ADR-31 appended.
former_last_c09: 2026-06-01 — c09 DONE (engine-agnostic classifier; H-1/H-2/H-3/H-4/H-5 + D-6). NEW
                derives/classifier.py = the SINGLE, analysis-layer draw-classification API: a
                state-capable rule engine (ADR-29) — a rule matches if any marker predicate
                (marker_contains/marker_suffix) hits OR all `when` field conditions (over any draws
                column: blend/depth/...) hold; first match wins; else fallback_class. Markers are a
                REFINEMENT, not the foundation. NEW derives/draw_classifier.toml (UE default) +
                presets/{unity,godot,custom-template}.toml (unity/godot ILLUSTRATIVE, manual-check
                only per ADR-21; no dup ue.toml — ADR-30). Reuses c07/c08 tomllib/tomli shim (ADR-26,
                3.10-safe) + importlib.resources. config.py +[classifier] preset/custom_path. Host
                wiring: derive_post_merge (classify + frame_prefix_re, H-1/H-3), formatters.pass_short
                ([pass_strip], H-2), pass_class_breakdown (gpu_duration_aliases, H-4), chrome.DRAW_CLASSES
                = classifier.class_order() (H-5). DEEP REVIEW changed the direction (user pushed twice):
                a first plan would push a shared classifier INTO the embedded-3.10 replay via JSON — but
                investigation found the replay-side _classify_draw is DEAD (feeds only passes.draws_by_
                class_*, 9 cols, ZERO readers, superseded by pass_class_breakdown). So D-6 COLLAPSE =
                DELETE the dead replay copy (not feed it): replay_main._classify_draw + draw_classes
                plumbing removed; the 9 cols stay ZEROED (PASSES_COLS frozen v3; replay-drift gate green);
                full removal deferred to c35 (D-11). Replay now emits FACTS ONLY → §21.9 holds by
                construction. PARITY (ADR-6, hard part): UE preset reproduces the former host
                _classify_draw BYTE-FOR-BYTE — proven by a 300+ case oracle battery in NEW
                tests/test_classifier.py (11 tests: frame_prefix/.pattern, pass_strip, gpu_aliases,
                class_order==old literal, every --c-<name> in :root, oracle battery, marker-beats-blend
                precedence, state-only spec classifies w/o markers, unity reclassify, custom_path
                override, replay has no _classify_draw). 59→70 green; test_parity + test_parquet_parity
                GREEN, golden BYTE-IDENTICAL (git clean, NO refresh); smoke render-only 9 pages lint
                clean; wheel ships classifier.py + 4 TOMLs, 150/150 unique 0 dups (ADR-10). Dead-code
                sweep (3 agents): only true redundancy = passes.draws_by_class_* (handled); ~30
                "dead" cols are NOT dead (drill browser surfaces every col); genuinely-dead
                fns/CSS/branch (footer_legend, _row_count, footer.legend+.sidecar-list CSS, replay
                `if False`) recorded → c16; col removal → c35. ADR-29/30; HARDCODE H-1..5 ticked; D-6
                ticked; D-10 (marker-first fragility → c27) + D-11 (dead-code sweep) opened;
                QUALITY_GATES §21.1e; ARCHITECTURE §3 annotated. REAL-INGEST VALIDATED (Chor bazar,
                5 captures, junctioned C:\tmp root, Downloads read-only): export+parse+replay(5×rc=0,
                182-225s)+parquetize(597199 rows)+derives(pass_class_breakdown=4245, texture_usage=5)+
                catalog(1 drop/5 caps)+global_entities(16651)+6 reports+dashboard+root = `smoke --data`
                exit 0, lint clean; atomic commit survived (R-16). Counts BYTE-IDENTICAL to the pre-c09
                baseline (597199 / 4245 / 16651) → §21.9 holds on REAL data. D-6 confirmed on output
                parquet: passes.draws_by_class_* ALL ZERO (dead replay classifier gone); draws.draw_class
                fully populated, 0 empty (opaque 2710/prepass 2705/ui 384/shadow 62/translucent 15/
                postprocess 15) via the host TOML walker.
former_last_c08: 2026-06-01 — c08 DONE (design tokens TOML + preview + Q-6; H-15/H-20/Q-6). NEW
                reports/design_tokens.toml (designer-editable [color]/[spacing]/[type]/[motion]/[layout])
                + reports/_tokens.py loader (tomllib/tomli shim ADR-26, bundled-only, NO deep-merge —
                Track A edits the packaged file; per-project overrides are Track B). PARITY (ADR-6/27, the
                hard part): template.py embeds the :root block UN-MINIFIED on drill/root pages, so the
                hand-aligned bytes (1/2/3-space gaps inside light-dark to column-align the dark oklch) are
                in the golden and NOT reconstructable from values. Fix: keep the alignment SKELETON in
                chrome.py with string.Template $key placeholders, source only VALUES from TOML
                (_DESIGN_TOKENS_TMPL / _CHROME_CSS_TMPL / _STICKY_CSS_TMPL) → byte-identical, NO golden
                refresh. H-20 layout literals (bar 18px, ibar 80x6, kpi 88px, grid floors 150/180/360px +
                bar-row/summary-bar tracks, sticky 120/36px) same mechanism; delta.sparkline_svg defaults
                60/14 from [layout]. Var NAMES preserved (--accent-primary not --color-*; the DESIGNER 1:1
                rename would force a 9-page golden refresh → deferred, ADR-28). Q-6: NEW chrome.report_page()
                dedups open/header/strip/close; routed 5 identical reports (report_key strip, '' when no ab)
                + dashboard (current_page) + trend_table (bespoke capture-suffix strip rides in body);
                trend_table empty-state left as-is (direct concat, ungated). NEW verbs: preview
                (_reports/_chrome_preview.html gallery, no data, deterministic), export-tokens --format
                toml|json|css (stdout), render --watch (alpha 500ms mtime poll → fresh-subprocess re-render).
                NEW tests/test_design_tokens.py (12: substitution complete, exact aligned lines incl. 3-space
                --c-other, layout literals, sparkline 60/14, subst keys cover placeholders, ascii toml,
                export round-trips, preview golden + determinism) + tests/data/golden_preview/
                _chrome_preview.html + make_preview_golden.py + _render_util.render_preview(). 47→59 green;
                test_parity + test_parquet_parity GREEN, golden BYTE-IDENTICAL (git status clean, NO
                refresh); smoke render-only 9 pages lint clean; wheel ships design_tokens.toml + _tokens.py
                + preview.py, 0 dups (ADR-10). ADR-27/28 appended; ARCHITECTURE §3/§4 annotated;
                QUALITY_GATES §21.1d; H-15/H-20/Q-6 ticked. Scoping (ADR-23): responsive @container/print
                grid overrides + component widths (copy 28/22, search 280, catalog 200) left inline as
                breakpoint constants (HARDCODE H-20 note). PRIOR: c07 DONE (TOML config layer).
audit-2026-06-01: Lifecycle quality audit + standing rule. ADR-23 "no patch-fixes" (root-cause or
                record explicitly; never narrow a gate to go green) — mirrored in CLAUDE.md "How to
                work" + a cross-session memory. Opened 3 findings from the audit: D-8 (drill HTML bakes
                writer-dependent Parquet KB via html.template._file_size_label → the real root behind
                ADR-11's one-env parity pin; fix the content to drop env-sensitive bytes, then parity
                can hold across pyarrow), G-14 (golden parity gates rendered HTML only — Parquet
                ungated, so c05's _global_entities row-order change slipped; add a Parquet-snapshot
                gate), D-9 (_TABLE_DISPLAY_ORDER pinned empirically, origin unrecorded). c06's Arm
                sort hardened to natural-numeric (ADR-24) before commit. SEQUENCING (user-confirmed):
                FOUNDATION FIRST — c06a (D-8) then c06b (G-14) BEFORE c07. Both commit docs written.
REAL-INGEST-2026-06-01: DONE (ADR-6) — ran Chor bazar (5 captures) full ingest on the real drop in
                C:\Users\vsiva\Downloads\RDC mainline r110565 25-05-2026. export+parse+replay(5×rc=0,
                177-220s)+parquetize(597199 rows)+derives(program_transitions 415, pass_class_breakdown
                4245, texture_usage 5)+resource_labels ALL GREEN. parquetize 597199 + global_entities
                16651 are BYTE-IDENTICAL to the prior pre-release validation → c04+c05+c06 don't change
                ingest output. The atomic COMMIT (os.replace tmp→final) failed [WinError 5] — adb server
                (respawns, inherits the inheritable _harness.log handle that lives inside <drop>.tmp\
                _stage) held the dir. Filed R-16 (keep harness log outside the committed .tmp / open
                non-inheritable; broader than R-4 — holder is a 3rd-party proc). Salvaged: killed adb,
                dropped _stage, completed the rename, ran `render` (exit 0: catalog 1/5, 6 reports +
                dashboard + root index, lint clean). Validation GREEN with R-16 noted.
next_action:    c16m DONE (2026-06-03) - the c16k-c16m table-unification EPIC is COMPLETE (ADR-38). Controllable
                cell truncation + `title=` hover-reveal landed on the ONE rdc-table engine (both modes): inner
                `.clip…` element (never the td) so widgets/labels stay visible; THREE tiers (320/200/560px); full
                value in the DOM (Ctrl-F) + length-gated title; copy/link payloads full (c16c); Expand-cells
                toggle (default truncated, single-line release in virtual to protect ROW_H, static also wraps);
                print full-wraps within the page. 181 -> 188 green, parquet parity NO digests refresh (§21.9),
                smoke lint clean, browser-verified offline (crafted long path + real heaviest drill). QUALITY_GATES
                §21.1o; ALL HTML goldens refreshed, _pagedata/digests/golden_parquet byte-unchanged. AUTHORED the
                3 close-out commits (user-requested). DO c16n NEXT (commits/v02/c16n_clip_coverage_print.md):
                (c16n) truncation-coverage tail - clip+title the one tabled report c16m skipped (draws_by_class
                area/drop) + a @media print rule so the bare dashboard/preview minis full-wrap on paper (today
                they print clipped, no tooltip). Presentation-only, golden refresh, no digests refresh.
                (c16o) table a11y parity (commits/v02/c16o_table_a11y_parity.md) - VTable (catalog/drill) gains
                aria-sort (the c16l-noted gap), sort headers become keyboard-operable in BOTH modes (tabindex +
                Enter/Space), virtual search input gets an aria-label. Golden refresh, no digests refresh.
                (c16p) v0.2 CLOSE-OUT + RELEASE (commits/v02/c16p_v02_closeout.md):
                (1) FULL re-ingest of real Perf (NOT render-only - regenerates EVERY drill, clearing the stale
                29MB inline-data OLDER-run drills render-only leaves; exercises R-16 adb-handle commit + R-17
                replay crash-on-teardown salvage; re-test the 6 manual-flipped r110788 captures). Working root
                C:\tmp\perf (hardlinks; Downloads read-only). Replay ~150-220s/capture, sequential. Eyeball all
                reports + drills (light+dark); counts stable where extraction unchanged (§21.9).
                (2) version 0.1.0->0.2.0 (_version.py; provenance strip omits version so golden-safe); CHANGELOG
                [Unreleased]->[0.2.0] summarizing c04-c16o; lint CHANGELOG.
                (3) PUSH branch -> CI GREEN on the FULL matrix (FIRST CI run for c04-c16o; 48 commits ahead of
                origin/main, never matrix-validated). (4) MERGE v0.2-roadmap-c04 -> main. (5) TAG v0.2.0 (outward
                + IRREVERSIBLE - AUTHORIZE FIRST) -> OIDC publish (c19 path) -> PyPI + GH Release -> post-install verify.
                THEN c20 (--json output, v0.3): open commits/v03/c20_json_output.md and do exactly that one
                commit. NOTE for c27/c35: the c09 classifier is already STATE-CAPABLE (when{} over any draw
                column), so the state-first generic preset (D-10) is a preset not a rewrite; c35 removes the
                zeroed passes.draws_by_class_* + slims passes (D-11a). GIT: still on branch v0.2-roadmap-c04
                (off main; c07 + c08 + c09 + c10 + c16 + c16b-c16l UNPUSHED). Post-release nit
                (non-blocking): bump CI actions off Node20 (checkout@v5/setup-python@v6 before 2026-06-16).
DONE-2026-05-31: c19 — bobframes 0.1.0 PUBLISHED. tag v0.1.0 -> CI publish job green (OIDC trusted
                publishing, ubuntu). Live on PyPI (wheel + sdist) + GitHub Release with both assets.
                Post-install verify from a clean PyPI install: version (0.1.0 schema 3 pyarrow 21.0.0),
                check (tools resolve), smoke render-only (9 pages, lint clean) all exit 0.
former_next:    c19 release-ops. CI GREEN confirmed after ADR-11 parity-pinning. Remote is
                github.com/altpsyche/bobframes; repointed pyproject [project.urls] + CHANGELOG refs
                mayhem-studios -> altpsyche (ADR-12) so PyPI metadata links resolve. REMAINING:
                (1) push the ADR-12 URL-fix commit; (2) set PYPI_API_TOKEN secret in altpsyche/
                bobframes via OIDC Trusted Publishing (ADR-13 — NO token/secret; publish job moved to
                ubuntu + id-token: write + pypa/gh-action-pypi-publish); (3) `git tag v0.1.0 &&
                git push origin v0.1.0` -> publish job (outward+IRREVERSIBLE — authorize first);
                (4) post-install verify per c19 Done-when.
blockers:       c19 needs the PyPI pending publisher saved (altpsyche/bobframes/ci.yml) + an authorized
                irreversible tag push. CI green; URLs fixed; PyPI name free; no token needed (ADR-13).
blockers:       none. (Run tests via: .venv\Scripts\python -m pytest bobframes/tests)
```

## v0.1 — extraction (ships first)

| | Commit | Status |
|---|---|---|
| ☑ | [c01 version](commits/v01/c01_version.md) | **done** — `import bobframes` → 0.1.0 |
| ☑ | [c02 golden harness + parity](commits/v01/c02_golden_harness.md) | **done** — 4 tests green (parity/schema/determinism/perf), commit f8cf833 |
| ☑ | [c03 reliability hardening](commits/v01/c03_hardening.md) | **done** — atomic writes, tree-kill, replay-skip, KEY_VERSION=1, provenance; 11 tests green |
| ☑ | [c11 cli.py dispatcher](commits/v01/c11_cli_dispatcher.md) | **done** — full subcommand CLI + stdlib logging (G-8); 11 tests green |
| ☑ | [c12 replay importlib.resources](commits/v01/c12_replay_importlib.md) | **done** — `replay_script_path()` resolves from wheel; 11 tests green |
| ☑ | [c13 replay-drift CI guardrail](commits/v01/c13_replay_drift_ci.md) | **done** — `test_replay_drift.py` ast-diffs replay `*_COLS` vs `schemas.py` (Option A / ADR-9); 12 tests green |
| ✗ | [c14 rename](commits/v01/c14_rename.md) | **COLLAPSED** — package is `bobframes` from scaffold (ADR-7) |
| ☑ | [c15 smoke rewrite + unit tests](commits/v01/c15_smoke_tests.md) | **done** — `--data`-driven smoke (render-only default) + 3 unit files (`test_stable_keys`/`test_schemas_unit`/`test_discovery`); 32 tests green |
| ☑ | [c17 CI workflow](commits/v01/c17_ci_workflow.md) | **done** — `.github/workflows/ci.yml`: gate matrix + tag-gated publish; YAML+gate cmds validated, build dry-checked |
| ☑ | [c18 README + CHANGELOG + LICENSE](commits/v01/c18_docs.md) | **done** — README (§13) + CHANGELOG [0.1.0] + MIT LICENSE; `lint README.md CHANGELOG.md` green |
| ☑ | [c19 tag v0.1.0](commits/v01/c19_release.md) | **done** — bobframes 0.1.0 live on PyPI + GH Release (OIDC); post-install verify green |

## v0.2 — de-hardcoding (deferred)

| | Commit | Status |
|---|---|---|
| ☑ | [c04 paths.py constants](commits/v02/c04_paths_constants.md) | **done** — 10 layout constants in paths.py; literals swept from all modules + tests; 32 green, byte-parity (H-18/H-19) |
| ☑ | [c05 registry from `schemas.TABLES`](commits/v02/c05_registry_consolidation.md) | **done** — TableSpec record (api reserved); catalog/entities/template/reports all derive; 32 green, byte-parity (H-8/9/10/11, D-1) |
| ☑ | [c06 tool resolver + glob version detect](commits/v02/c06_tool_resolver.md) | **done** — `config.resolve_tool()` + `errors.py` (§4 exit-map) + Arm glob (H-7, ADR-24 natural-sort); `check` real (0/3 + §5); 36 green, byte-parity |
| ☑ | [c06a drill-size de-harden](commits/v02/c06a_drill_size_dehardcode.md) | **done** — D-8: dropped getsize size-spans from drill HTML; 37 green, golden refreshed (writer-KB gone) |
| ☑ | [c06b Parquet parity gate](commits/v02/c06b_parquet_parity_gate.md) | **done** — G-14: writer-independent logical digest over `_data/**/*.parquet` (58 tables), full matrix; 38 green |
| ☑ | [c07 TOML config layer](commits/v02/c07_toml_config.md) | **done** — tomllib config (tomli<3.11); timeouts/regex/banlist/chrome-scrub/weights/delta lifted; 47 green, byte-parity (H-12/13/14/16/17/21/22/23/30,Q-3) |
| ☑ | [c08 design tokens TOML + preview](commits/v02/c08_design_tokens.md) | **done** — design_tokens.toml + value-only Template skeleton (H-15/H-20, ADR-27/28); report_page (Q-6); preview/export-tokens/render --watch verbs; 59 green, byte-parity (no golden refresh) |
| ☑ | [c09 engine-agnostic classifier](commits/v02/c09_classifier.md) | **done** — single state-capable classifier API (H-1..H-5); dead replay copy deleted (D-6); 70 green, byte-parity (no refresh) |
| ☑ | [c10 env-var rename `RDC_*`→`BOBFRAMES_*`](commits/v02/c10_env_rename.md) | **done** — `getenv_legacy` one-release fallback; `RDC_ROOT` eliminated (R-5/Q-5, ADR-31); 74 green, byte-parity (no refresh) |
| ☑ | [c16 report-quality polish](commits/v02/c16_report_quality.md) | **done** — mechanics (R-13/Q-9/D-4/D-7/D-11b) + polish slice (KPI strips, callouts, heatmaps, provenance strip, labels); 99 green, golden refreshed (ADR-32) |
| ☑ | [c16b report charts](commits/v02/c16b_report_viz.md) | **done** — inline-SVG toolkit (charts.py, ADR-33) + flagship chart per report + shader column-diet; 108 green, golden refreshed |
| ☑ | [c16c report restructure](commits/v02/c16c_report_restructure.md) | **done** — section-cards + sticky-h2 + copy-buttons + dashboard small-multiples + caption/scope a11y + fill-or-hide; 115 green, golden refreshed (G-15 fully closed) |
| ☑ | [c16d report aesthetics](commits/v02/c16d_report_aesthetics.md) | **done** — visual-design pass in 4 sub-commits (a depth+tokens / b vendored-Inter+type / c chart-finish / d micro+pacing); G-17 closed, ADR-34; 128 green, golden refreshed + browser-reviewed |
| ☑ | [c16e run model (per-run truth)](commits/v02/c16e_run_model.md) | **done** — killed the cumulative-union flaw (G-19, ADR-35): dashboard + 5 single-state reports report ONE current run (default newest) via discovery.current_run/baseline_run/RunContext threaded as report_page(run=); removed items drop out or move to a separated "resolved since <baseline>" card; trend_table + A/B unchanged. 132 -> 142 green; golden refreshed (dashboard + 5 reports only); parquet digests untouched; QUALITY_GATES §21.1j |
| ☑ | [c16f multi-run UX](commits/v02/c16f_multirun_ux.md) | **done** — run selector via pre-rendered per-run pages (_reports/run/<key>/, reuse rdc-ab-picker) + fixed prior baseline + "current vs baseline" banner + distinct run chips + "viewing an older run" cue + dashboard->report persistence (G-18); bounded by [report] max_prerendered_runs. 142 -> 148 green; golden +6 per-run pages, no digests refresh; QUALITY_GATES §21.1k. G-20 (3+-run col collapse) deferred (no 3+-run data to verify) |
| ☑ | c16g quality sweep | **done** — pre-tag, behaviour-neutral: Q-1 (stable_key dict-of-builders, oracle-locked), Q-2 (cast-failure tally + warn), Q-4 (zip strict on derive), Q-7 (`_to_dict_of_lists` callers), Q-8 (dead buffers no-op deleted), D-3 (coupling doc), D-9 (`_TABLE_DISPLAY_ORDER` origin recovered + recorded). 148 -> 160 green; golden + digests frozen; no new ADR |
| ☑ | c16h reliability sweep | **done** — R-12 (`_best_effort_rmtree` logs held-handle cleanup failures), R-14 (UTF-8 U+FFFD warning in `iter_chunks`), R-11 (single-process sidecar doc), R-15 (`parquetize` skips markerless/incomplete-replay captures so half-written CSVs never merge). R-10 deferred (OOM-gated). 160 -> 165 green; golden + digests frozen; no new ADR |
| ☑ | [c16i catalog + drill readability](commits/v02/c16i_catalog_drill_readability.md) | **done** (revived, ADR-37) — STATIC `html/template.py` pass: Inter/mono type split, roomier VTable rows (ROW_H=32 single-source), client-side uniform-tint heatmap on numeric magnitude cells, collapsible column groups on the wide catalog, `.table-scroll` sizes to content, drill visual hierarchy (category=group-label+rail / table-section=card). 165→171 green; root+drill golden refreshed, reports byte-unchanged, no digests refresh; QUALITY_GATES §21.1l. G-21 readability half (heavy-data half = c16j); G-23 opened (two table systems) |
| ☑ | [c16j decouple heavy data](commits/v02/c16j_data_decoupling.md) | **done** (ADR-37) — moved the catalog/drill VTable rows out of the HTML into `<script defer src>`'d `_pagedata/*.js` (a sibling dir, NOT `_data/`; file://-safe classic script) so the shell paints first; real Perf heaviest drill 17.6MB→134KB shell + 17.5MB streamed. 176 green, reports byte-unchanged, browser-verified offline; G-21/G-22 closed, §21.1l consolidated |
| ✗ | ~~c16k–c16n SPA epic~~ | **VOIDED** — the SPA (ADR-36) was rejected on a lifespan review (ADR-37); reports stay static. The `c16k`/`c16l`/`c16m` SLOTS are REUSED below for the table-unification epic (ADR-38); the SPA `c16n` is dropped. Trail in ADR-36/37 + the proposal doc |
| ☑ | [c16k unified rdc-table component](commits/v02/c16k_unified_table_component.md) | **done** (ADR-38) — ONE bespoke `rdc-table` engine BUILT in chrome.py (shared cmpVals/tintImage; `VTable` virtual + new `StaticTable`; DCL-bootstrapped, no customElements). Catalog/drill migrated to `virtual` (old `_JS` subsumed, zero dead code); shader_hotlist main table migrated to `static` (server-baked rows, opt-in via `report_page(rdc_table=True)`) as the ADR-37 proof. 176→180 green; refreshed only catalog+drill+both shader_hotlist; `_pagedata`/other goldens/digests byte-unchanged; browser-verified offline both modes |
| ☑ | [c16l unified table rollout](commits/v02/c16l_unified_table_rollout.md) | **done** (ADR-38) — rolled `static` rdc-table onto every report/A-B/per-run/trend/dashboard-mini surface, folded the engine into the always-on shared bundle, DELETED the old rdc-sortable-table + table.report (grep-clean), restored aria-sort, overdraw got column groups; one table system (G-23 fully resolved); 181 green, golden refreshed, no digests refresh; QUALITY_GATES §21.1n |
| ☑ | [c16m cell truncation + hover](commits/v02/c16m_cell_truncation_hover.md) | **done** (ADR-38) — controllable per-column truncation on the ONE engine: inner `.clip…` element (never the td, so widgets/labels stay visible), 3 tiers (320/200/560px), full value in the DOM (Ctrl-F) + length-gated `title=`, copy/link payloads full (c16c), Expand-cells `<button aria-pressed>` toggle (default truncated; single-line release in virtual to keep ROW_H, static also wraps), print full-wrap. EPIC COMPLETE; 181→188 green, all HTML goldens refreshed, `_pagedata`/digests/parquet byte-unchanged; QUALITY_GATES §21.1o |
| ☐ | [c16n clip coverage + dashboard print](commits/v02/c16n_clip_coverage_print.md) | **next** (ADR-38 tail) — close the c16m truncation-coverage gaps: clip+`title=` the one tabled report c16m skipped (`draws_by_class` area/drop), and a `@media print` rule so the bare dashboard/preview minis full-wrap on paper (today they print clipped, no tooltip). Presentation-only; golden refresh; no digests refresh |
| ☐ | [c16o table a11y parity](commits/v02/c16o_table_a11y_parity.md) | planned (ADR-38 a11y tail) — bring the VTable (catalog/drill) to a11y parity with StaticTable: `aria-sort` on virtual headers (the c16l-noted gap), keyboard-operable sort headers in BOTH modes (`tabindex`+Enter/Space), an `aria-label` on the virtual search input. Golden refresh; no digests refresh |
| ☐ | [c16p v0.2 close-out + release](commits/v02/c16p_v02_closeout.md) | planned — FULL re-ingest of real Perf (regenerates stale older-run drills; exercises R-16/R-17) + eyeball; version 0.1.0→0.2.0; CHANGELOG [0.2.0]; push → CI green (full matrix, first run for c04–c16o); merge → main; **tag v0.2.0** (outward+IRREVERSIBLE — authorize). Then c20 |

## v0.3 — CI/automation surface (planned — [ROADMAP](ROADMAP.md))

| | Commit | Status |
|---|---|---|
| ☐ | [c20 --json output](commits/v03/c20_json_output.md) | **next** (after v0.2 close-out ingest + tag) |
| ☐ | [c21 regression gating](commits/v03/c21_regression_gating.md) | planned |
| ☐ | [c22 isolated stages](commits/v03/c22_isolated_stages.md) | planned |
| ☐ | [c23 --dry-run](commits/v03/c23_dry_run.md) | planned |
| ☐ | [c24 verify](commits/v03/c24_verify.md) | planned |
| ☐ | [c25 diff](commits/v03/c25_diff.md) | planned |
| ☐ | [c26 export](commits/v03/c26_export.md) | planned |

## v0.4 — Engine breadth + ergonomics (planned)

| | Commit | Status |
|---|---|---|
| ☐ | [c27 engine presets](commits/v04/c27_engine_presets.md) | planned |
| ☐ | [c28 texture_usage report](commits/v04/c28_texture_usage_report.md) | planned |
| ☐ | [c29 overdraw heatmap](commits/v04/c29_overdraw_heatmap.md) | planned |
| ☐ | [c30 schema + query](commits/v04/c30_query_schema.md) | planned |
| ☐ | [c31 mesh/material report](commits/v04/c31_mesh_material_report.md) | planned |

## v0.5 — Graphics-API adapter epic (planned — SCHEMA_VERSION 3→4 at c35)

| | Commit | Status |
|---|---|---|
| ☐ | [c32 PipelineStateAdapter](commits/v05/c32_pipeline_state_adapter.md) | planned |
| ☐ | [c33 data-driven columns](commits/v05/c33_data_driven_columns.md) | planned |
| ☐ | [c34 Vulkan extraction](commits/v05/c34_vulkan_extraction.md) | planned |
| ☐ | [c35 schema widening](commits/v05/c35_schema_widening.md) | planned |

## v0.6+ — Cross-platform + leads + plugins (planned)

| | Commit | Status |
|---|---|---|
| ☐ | [c36 cross-platform](commits/v06/c36_cross_platform.md) | planned |
| ☐ | [c37 historical dashboard](commits/v06/c37_historical_dashboard.md) | planned |
| ☐ | [c38 plugins](commits/v06/c38_plugins.md) | planned |
| ☐ | [c39 Figma sync](commits/v06/c39_figma_sync.md) | planned |

## Status legend
`not-started` → `doing` → `done`. Use `blocked: <reason>` when stuck and record it under `blockers`.

## Session log (append newest on top; one line each)
- 2026-06-03 — c16n DONE (truncation-coverage tail + dashboard print; ADR-38 tail). draws_by_class area/drop
  cells now clip via the inner `.clip` (base.clip_span, default tier) - all 5 tabled reports consistent; a
  `@media print` rule in `_RDC_TABLE_CSS` releases the bare dashboard/preview minis (`a.dash-card table.data` +
  the direct-child `.table-wrap > table.data` preview mini) to full-wrap on paper (the mini analogue of the
  static rdc-table print rule); mini `title=` kept UNCONDITIONAL (responsive widths, no server clip point -
  ADR-23, recorded in §21.1o, no new ADR). 188 -> 190 green (+test_c16n in test_report_structure +
  test_design_tokens); ALL 15 HTML goldens + preview refreshed (engine CSS inline everywhere; draws_by_class
  also gains `<span class="clip">`); `_pagedata`/digests/golden_parquet BYTE-UNCHANGED, parquet parity NO
  refresh (§21.9); smoke render-only lint clean; browser-verified offline (draws_by_class clip + Expand toggle
  injects, no JS errors; dashboard print-to-PDF mini cells + headers FULL). QUALITY_GATES §21.1o extended.
  v0.2-roadmap-c04, UNPUSHED. current -> c16o.
- 2026-06-03 — AUTHORED the v0.2 close-out commits (c16n/c16o/c16p), pulled forward at the user's request after a
  pre-tag "do you foresee anything else?" review. The review surfaced: (a) minor presentation/a11y consistency
  gaps left by the c16k-c16m epic, and (b) release mechanics not yet done (48 commits ahead of origin/main +
  NEVER CI-matrix-validated; version still 0.1.0; CHANGELOG [Unreleased] empty). Split: c16n = truncation-coverage
  tail (draws_by_class report table clip+title - the one tabled report c16m's scope skipped; + a @media print
  rule so the bare dashboard/preview minis full-wrap on paper, since the static print rule is rdc-table-scoped).
  c16o = table a11y parity (VTable/catalog-drill gains aria-sort = the c16l-noted gap; sort headers become
  keyboard-operable in BOTH modes via tabindex+Enter/Space; virtual search input gets an aria-label). c16p =
  v0.2 close-out + release (FULL real-Perf re-ingest regenerating stale older-run drills + exercising R-16/R-17;
  version 0.1.0->0.2.0; CHANGELOG [0.2.0]; push->CI-green full matrix; merge->main; tag v0.2.0 OIDC-publish,
  authorize first). Re-sequenced current -> c16n -> c16o -> c16p -> c20. Docs-only; no code, no golden change.
- 2026-06-03 — c16m DONE (controllable cell truncation + `title=` hover-reveal on the ONE `rdc-table` engine;
  ADR-38, FINAL of the c16k-c16m table-unification epic). One mechanism both modes: clip on an INNER element
  (in-cell `<a class="clip…">` / `<span class="clip…">` via new chrome.clip_attrs/clip_span), never the td, so
  copy-buttons / sparklines / `.lbl` ride OUTSIDE + stay visible. Removed the c16l no-clip stopgap + the
  td-level 380px clip (kept nowrap). THREE tiers (--clip-cap 320 / -narrow 200 / -wide 560 px); full value in
  the DOM (Ctrl-F) + a length-gated server/JS `title=` (short cells skip it - synthetic+real src paths short,
  so golden has no src title=, correct-for-data not gamed, ADR-23); copy/link payloads keep the FULL value
  (c16c). Static builders emit `.clip…`/title on long cells (shader src=wide on the <a>; instancing
  mesh/areas/pass; overdraw RT-label/format; trend area); VTable.cellNode wraps every non-numeric windowed cell
  (wideCols for path/hash/stable_key) + re-applies on recycle; numeric never clipped; link nav-title kept.
  Expand-cells `<button aria-pressed>` toggle flips data-expand (default truncated; release single-line both
  modes to keep VTable ROW_H, static also wraps); print = static full-wrap within the page (table width:100%,
  display:inline + overflow-wrap:anywhere - nothing hidden on paper). test_report_structure +4 + test_design_tokens
  +1. PARITY: all HTML goldens refreshed (engine inline on every page) + static .clip…/title markup;
  _pagedata/digests.json/golden_parquet BYTE-UNCHANGED; test_parquet_parity GREEN NO refresh (§21.9). 181 -> 188
  green. smoke 15 pages lint clean. BROWSER-VERIFIED OFFLINE (headless Chrome, file://): crafted 162-char path
  clips+ellipsis (copy outside clip) / Expand reveals / print wraps within page; real heaviest drill (Commercial
  district 2026-06-01_r110788, 123,052 rows/28 tables) recycles with marker_path clipped, 3026 .clip spans, 150
  .lbl preserved, 28 toggles, no JS errors, ROW_H intact. QUALITY_GATES §21.1o; ADR-38 epic COMPLETE (no new ADR).
  UNPUSHED on v0.2-roadmap-c04. current -> v0.2 close-out.
- 2026-06-03 — c16l DONE (roll `rdc-table` out + delete the old systems; ADR-38; single commit). ONE table
  system: engine folded ALWAYS-ON into chrome._compose_css/_compose_js; the c16k opt-in (rdc_table= param +
  rdc_table_assets()) DELETED (rdc_table_css/js kept for template.py); every remaining report (overdraw,
  draws_by_class, instancing x3, shader_hotlist secondary+resolved, trend x3) + dashboard/preview minis
  migrated off rdc-sortable-table/table.report onto static rdc-table/table.data (<td> content byte-stable);
  rdc-sortable-table component + dead table.report CSS DELETED (grep-clean); aria-sort sort-state restored on
  StaticTable; overdraw gained column groups (separable current/history) - instancing/trend/draws_by_class
  kept clean sort+heatmap (no separable wall, ADR-23 scoping); 380px clip opted out in static (c16m owns real
  truncation); minis bare (not wrapped - sort-vs-navigate conflict). Refreshed 6 reports + dashboard + 6 per-run
  + catalog + drill + preview goldens; _pagedata/digests/parquet BYTE-UNCHANGED; 181 green; smoke 15 pages lint
  clean; browser-verified offline. QUALITY_GATES §21.1n; G-23 FULLY RESOLVED. UNPUSHED on v0.2-roadmap-c04.
  current -> c16m.
- 2026-06-03 — AUTHORED the table-unification epic (ADR-38 + c16k/c16l/c16m), pulled into the v0.2 close
  (user-requested). Resolves G-23 (two table systems: reports' server-baked table.report + rdc-sortable-table
  vs the drill VTable). ADR-38: unify on ONE bespoke `rdc-table` (merge the two engines; NO third-party grid -
  ADR-6/37 anti-framework), progressive-enhancement with `static` (reports - rows SERVER-BAKED, JS enhances;
  ADR-37's golden-as-output/JS-optional/print/Ctrl-F PRESERVED, not reversed) + `virtual` (catalog/drill -
  windowed from _pagedata/*.js) modes. c16k builds the component + both modes + migrates catalog/drill + 1
  proof report; c16l rolls out to all remaining report/A-B/per-run/trend/mini surfaces + DELETES the old
  rdc-sortable-table + VTable scaffolding; c16m adds controllable truncation + `title=` hover-reveal (both
  modes). Re-sequenced: c16k -> c16l -> c16m -> v0.2 close-out -> tag. current -> c16k. Docs-only commit; no
  code, no golden change. Reused the voided SPA c16k-c16m slots; SPA c16n dropped.
- 2026-06-03 — c16j DONE (decouple the heavy catalog/drill data; html/template.py layer; the ~21MB TTI fix;
  STATIC per ADR-37, NO SPA; no new ADR). Each VTable's heavy rows moved OUT of the HTML into its own
  _pagedata/<key>.js (window.__data_<key>={...};, same compact json.dumps) loaded by a CLASSIC file://-safe
  <script defer src> (NO fetch, NO ES modules). NEW paths.PAGEDATA_DIR='_pagedata' (sibling dir of each page's
  index.html, NOT _data/ the parquet/data contract -> src always literally _pagedata/<key>.js, no relpath/
  collision; user-confirmed refinement of the doc's loose _data/<key>.js). NEW template._write_page_data;
  _inline_table_with_data returns (section,key,payload) + caller writes; only the HEAVY __data_* moves
  (__colgroups_catalog/__labels + shared _JS stay INLINE). defer + DOMContentLoaded bootstrap = shell paints
  first, no onload race. CSS-only .table-scroll:empty::before loading hint (catalog/drill _PER_DROP_CSS only).
  Harness: rendered_page_data_files + make_golden .js companions + a 2nd test_parity block + test_report_structure
  repoint & +5 c16j guards. PARITY (ADR-6/37): only catalog + 1 drill index.html refreshed + 27 added
  _pagedata/*.js; reports/dashboard/per-run/A-B goldens + digests.json BYTE-UNCHANGED; test_parquet_parity GREEN
  no refresh. 171->176 green; smoke 15 pages lint clean exit 0. BROWSER-VERIFIED OFFLINE (headless Chrome,
  file://, real Perf): catalog + heaviest fresh drill (Commercial district 2026-06-01_r110788: 17.6MB->134KB
  shell + 17.5MB/28 .js) populate from the .js with c16i type split/heatmap/column-groups intact. §21.1l
  consolidated; G-21 FULLY DONE + G-22 resolved. Commits on v0.2-roadmap-c04, UNPUSHED. current -> v0.2 close-out.
- 2026-06-03 — c16i DONE (catalog + drill readability; G-21 readability half; html/template.py layer; no new
  ADR). Type split (Inter sans default, mono on numeric/.mono body cells), ROW_H=32 single-sourced, uniform-tint
  client-side heatmap on numeric magnitude cells (user rejected the first length-bar as artifact-looking),
  catalog column groups (schema-category-derived, Metadata+Workload open), .table-scroll sizes to content, and
  a drill visual-hierarchy pass (category=group-label+rail, table-section=card) - all in _PER_DROP_CSS so
  reports goldens stay byte-unchanged. 165->171 green; root+drill golden refreshed + browser-reviewed
  (light/dark, synthetic + real Perf); no digests refresh; QUALITY_GATES §21.1l; G-23 opened (unify the two
  table systems). Commits on v0.2-roadmap-c04, UNPUSHED. current -> c16j.
- 2026-06-02 — ADR-37: SPA REJECTED on a lifespan review; reverted to static + data-decoupling (user-trusted
  "what's truly better for the tool's lifespan?"). Stepped back from the ADR-36 SPA (decided hours earlier,
  NO code) and judged it a local maximum: a bespoke offline SPA is a perpetual web-framework maintenance tax,
  shifts correctness into JS the byte-golden can't see, loses JS-optional content, and constrains the v0.6
  plugin / cross-platform future. Durability hierarchy: data (parquet + versioned JSON) > server-rendered
  static HTML (file IS the output -> golden proves correctness) > bespoke SPA. The tool's trajectory is toward
  MACHINE consumers (v0.3 --json/gating/verify/diff, v0.4 query, v0.5 schema), so the durable investment is
  the DATA CONTRACT (c20/c30, already roadmapped), not a presentation engine. DECISION (ADR-37, supersedes
  ADR-36): reports + dashboard stay self-contained STATIC single files (JS-optional + single-file +
  golden-as-output PRESERVED; per-page font dup accepted); fix ONLY the ~21MB drill/catalog by decoupling its
  VTable data into a <script src>'d _data/*.js (static, file://-safe, classic+defer, no router - those pages
  were never portable/JS-optional anyway); catalog/drill readability stays the static c16i pass. Epic
  RE-SCOPED to TWO small static commits: c16i (readability, REVIVED) + c16j (data decoupling, REPURPOSED from
  "SPA spine"); the SPA commits c16k-c16n are VOIDED (docs removed; trail in ADR-36/37 + the proposal). ADR-36
  marked superseded; proposal doc marked superseded; FINDINGS G-21 (via c16i+c16j) + G-22 (resolved by ADR-37:
  SPA rejected, static decoupling, data contract c20/c30); INDEX/MIGRATION rewired. current -> c16i. NO code.
- 2026-06-02 — ADR-36 DECIDED + SPA epic AUTHORED (user signoff). The 3 design reviews -> a real product
  decision: the reports become an OFFLINE STATIC SPA. The offline unlock: browsers load <script src>/<link>
  from file:// (unlike fetch), so data + assets decouple with NO server and the output still opens by
  double-click - output becomes an app FOLDER (shell index.html + _assets/app.{css,js} + _views/*.html
  fragments + _data/*.js lazy-loaded). Whole output moves in (catalog + drill + dashboard + 6 reports as
  routes), reusing the Python renderers (pre-rendered fragments, NOT a JS reimplementation); a single-file
  export is retained (DataSink: inline vs external). Decisions: SPA lands IN v0.2 before the tag
  (user-chosen despite the cost - it is the largest change in the project + re-homes c16b-f); replace-now;
  hash routing. Amends ADR-6 (single file -> app folder + export) + ADR-34 (font relocated to _assets/app.css,
  once); supersedes c16i; ACCEPTS G-22. Authored ADR-36 (DECISIONS) + proposal doc + 5 commit docs
  (c16j spine -> c16k data decoupling -> c16l re-home reports -> c16m single-file export -> c16n catalog/drill
  readability/G-21). Offline + byte-determinism + parquet parity (§21.9) + a11y/print preserved; golden gate
  restructures to the app-folder file-set. current -> c16j; c16i SUPERSEDED. NO code yet. UNPUSHED.
- 2026-06-02 — c16i AUTHORED (catalog + drill readability; G-21). Reviewed three plan-folder design
  proposals (overall_overhaul_proposal / readability_and_presentation_review / report_roadmap) against the
  code + the frozen contract. Verdict: good design instincts but they (a) conflate two layers and (b)
  ignore ADR-6/ADR-34. Reframe: the reports layer (reports/chrome.py) already got the c16b-f treatment
  (type split, depth, heatmap cells, drop-compare, sparklines); the REAL eye-strain is the catalog + drill
  layer (html/template.py) - all-monospace table.data, ROW_H=22, flat 37-col wall. Wrote
  commits/v02/c16i_catalog_drill_readability.md = the buildable-within-constraints subset: Inter/mono type
  split, roomier rows (coordinate ROW_H+CSS), client-side deterministic heatmap cells on numeric columns,
  collapsible column groups on the wide catalog; server-rendered, offline, byte-deterministic, no data
  decoupling. The reviews' SPA + fetch('_data/*.json') + external /assets/ + Google-Fonts architecture is
  EXPLICITLY OUT of scope (G-22): fetch fails on file:// (CORS) -> breaks ADR-6 offline single file;
  external assets/font break ADR-34 - a product-contract fork needing a dedicated ADR + signoff, not an
  inferred overhaul (recorded, not silently dropped, ADR-23). Opened G-21 (c16i) + G-22 (deferred fork);
  current -> c16i; v0.2 close-out + tag now come AFTER c16i. NO code yet.
- 2026-06-02 — c16h DONE (v0.2 reliability sweep; R-11/R-12/R-14/R-15 closed, R-10 deferred). Pre-tag,
  golden + Parquet digests frozen. R-12: NEW run._best_effort_rmtree replaces the two silent
  `shutil.rmtree(..., ignore_errors=True)` stage-cleanup sites - still best-effort (a held handle must
  not fail the commit, R-16) but LOGS a named warning so a stale stage is not invisible. R-14:
  parse_init_state.iter_chunks tallies U+FFFD substitutions (chr(0xfffd)) and logs a per-file warning,
  so bad/truncated UTF-8 is surfaced instead of silently parsed into partial rows (the richer manifest
  parse_status='partial' is a noted follow-up). R-15: chose a cleaner host-side fix over the finding's
  per-capture-tmp - parquetize._list_stage_dirs(require_marker=True) SKIPS any capture lacking
  REPLAY_COMPLETE_MARKER, so a replay that crashed mid-write (no marker) never folds half-written CSVs
  into the committed drop; ok + salvaged dirty-exit (R-17) both write the marker, so this keeps exactly
  the trustworthy captures - matching the report layer's ok_capture_set. R-11: documented the
  single-process-per-drop + content-addressed-filename assumption that makes the lockless sidecar
  overwrite idempotent. R-10 DEFERRED (intentional): no OOM measured, streaming would change the read
  path with no need. 160 -> 165 green (+5 test_hardening: markerless skip + raw-list, UTF-8 warn +
  clean, best-effort-rmtree log + tolerate-missing). test_parquet_parity GREEN, NO digests refresh;
  smoke 15 pages lint clean exit 0. No new ADR. FINDINGS R-11/R-12/R-14/R-15 ticked, R-10 noted.
  UNPUSHED. NEXT: v0.2 close-out re-ingest (validates R-15 + the manual-salvaged run2 captures on real
  data) + tag.
- 2026-06-02 — c16g DONE (v0.2 quality sweep; Q-1/Q-2/Q-4/Q-7/Q-8 + D-3/D-9 closed). Pre-tag cleanup,
  all behaviour-neutral (golden + Parquet digests frozen). Q-1: collapsed parquetize._apply_stable_key's
  60-line if/elif into a dict-of-builders + a per-row get() accessor (byte-identical; oracle-locked in
  NEW test_parquetize against stable_keys.*). Q-2: _cast_value gained a `fails` accumulator + a per-table
  warn summary (empty cells are NOT failures) so silent coercion-to-0 is surfaced. Q-4: zip(..., strict=True)
  on derive_post_merge's 3 sites (same-table/num_rows lengths -> asserts drift, never changes output;
  exercised by test_parquet_parity). Q-7: routed the 6 full-column report callers through
  base._to_dict_of_lists (discovery left inline - a discovery->cache import would cycle). Q-8: deleted the
  dead `buffers target_history` no-op (buffers have no label column per BUFFERS_COLS). D-3: documented the
  one-way run->reports.orchestrator coupling at the import. D-9: RECOVERED + recorded _TABLE_DISPLAY_ORDER's
  origin (a deliberate editorial within-category relevance/pipeline-flow order, not derivable; per-category
  rationale in the template.py comment; new tables tail their category; golden-gated). 148 -> 160 green
  (+12 test_parquetize). test_parquet_parity GREEN, NO digests refresh; smoke 15 pages lint clean exit 0.
  No new ADR. FINDINGS Q-1/Q-2/Q-4/Q-7/Q-8 + D-3/D-9 ticked. UNPUSHED. NEXT: c16h reliability sweep, then
  v0.2 close-out re-ingest + tag.
- 2026-06-02 — c16f DONE (multi-run UX: the run selector; G-18 closed; builds on ADR-35). Layered the
  navigation UX on c16e's run model via PRE-RENDERED per-run pages: top-level _reports/<report>.html = newest
  (default); each OLDER run gets a self-contained set under _reports/run/<run_key>/ (mirrors _reports/ab/),
  bounded by NEW [report] max_prerendered_runs (default 10; orchestrator LOGS drops beyond the cap - no silent
  truncation, ADR-23; overflow via trend_table, which is NOT pre-rendered per run). NEW chrome run_picker_for
  (reuse the rdc-ab-picker component: static <select>, value=relative link, no network/JS; distinct
  rdc-run-select id; depth-prefixed links resolve from both top-level + run/<key>/), run_compare_banner
  ("current vs baseline", reuse .ab-strip, baseline dimmed), + an "viewing an older run" callout (non-newest
  only). report_page emits them from the run= RunContext (+ run_nav_key so the dashboard drives the picker as
  'index'); A/B pages suppress the picker; per-run pages omit the A/B picker. Persists dashboard->report (each
  run dir is a self-contained sibling set; trend_table + A/B index point up). cli output_path/crumb_depth take
  run=, NEW run_subdir + --run-label/--run-date; orchestrator renders the per-run set; 6 build()s gain
  run_label/run_date. Browser-verified light+dark (top-level picker+banner; per-run "run 1 of 2" with its own
  numbers + older-run cue; c16d language holds). NOTE (not a bug): the synthetic's OLDER drop lacks
  pass_class_breakdown (make_synthetic skips it; render-only regens derived tables for the newest scope only)
  -> the per-run older dashboard's pass-gpu + draws-by-class CARDS show "no data yet", the TRUTHFUL per-run
  result (it does not borrow the newest run's data - that borrowing WAS the G-19 flaw); real ingests carry the
  table on every drop. PARITY (ADR-6/35): golden +6 per-run pages + picker/banner on 6 top-level pages;
  trend_table/drill/root/preview UNCHANGED; test_parquet_parity GREEN, NO digests refresh. 142 -> 148 green
  (+6 test_run_model c16f, +1 test_config). smoke 15 pages lint clean exit 0. QUALITY_GATES §21.1k; G-18
  ticked. G-20 (per-drop col collapse at 3+ runs) DEFERRED - no 3+-run data to verify, 3-run golden fixture
  blocked by the no-digests-refresh constraint (rationale in FINDINGS, ADR-23). UNPUSHED. current -> v0.2
  close-out (still 2-run; tag after).
- 2026-06-02 — c16e DONE (per-run truth; the run model; G-19 closed; ADR-35). Killed the cumulative-union
  flaw the real Perf 2-run ingest exposed: dashboard + 5 single-state reports defaulted to
  discover_drops=ALL drops and summed/unioned them, so removed work lingered (total draws = run1+run2;
  instancing listed a run1-only mesh as live; donut summed both). One run model: NEW discovery.current_run/
  baseline_run + a RunContext carrier (resolved per build via run_context, re-exported via base) threaded
  into chrome.report_page/header as ONE run= arg -> each report names its run + a new report gets per-run
  truth for free. Rerouted dashboard (helpers scoped to [current]; 2 cache-readers filter by
  drop_date/label) + instancing (live=current meshes, batching scoped too, resolved-since card) +
  draws_by_class (donut/headline=current, raw table keeps both) + shader_hotlist (rank present-in-current,
  resolved-since by presence) + pass_gpu (hero/treemap off the current bucket not cross-drop max) + overdraw
  (live RTs=current, rep=current not oldest, renamed a shadowing `cur`->`cur_n`). trend_table + A/B
  untouched. VERIFIED numerically (dashboard total draws 4,417 = newest only, not 12,374) + by EYE in a
  browser (light+dark, all 6: each names its run; donut centre 60=current while raw table keeps 60+60;
  resolved-since a separate card on instancing+shaders). PARITY (ADR-6/35): HTML golden REFRESHED (dashboard
  + 5 reports ONLY; trend_table/drill/root/preview + parquet digests BYTE-UNCHANGED); test_parquet_parity
  GREEN, NO digests refresh (§21.9). 132 -> 142 green (+8 test_run_model, +2 test_report_structure). smoke
  9 pages lint clean exit 0. ADR-35 appended; G-19 ticked + G-20 opened (3+-run col collapse -> c16f);
  QUALITY_GATES §21.1j. UNPUSHED on v0.2-roadmap-c04. current -> c16f.
- 2026-06-02 — c16e + c16f AUTHORED (from the real Perf 2-run ingest; planning + impl in a NEW chat).
  c16e_run_model (G-19, ADR-35): the dashboard + single-state reports default to discover_drops=ALL
  drops and aggregate CUMULATIVELY, so work removed in the newer run still shows (instancing lists a
  run1-only mesh; "total draws" = run1+run2 summed; draws-by-class donut sums both). Fix = anchor each
  report to ONE current run (default newest) as truth; baselines for delta only; absent items drop out
  or move to a separated "resolved since <baseline>" section; trend_table/A-B stay the across-run views.
  c16f_multirun_ux (G-18): run selector + baseline selector + "current vs baseline" banner + distinct run
  labels + "viewing older run" cue, reusing the A/B picker. Both presentation/aggregation-only (golden
  refresh now VISIBLE on the 2-drop synthetic; test_parquet_parity GREEN no digests refresh). Opened
  FINDINGS G-18/G-19; current -> c16e; v0.2 close-out + tag now come AFTER c16f. NO code yet.
- 2026-06-02 — REAL INGEST (user "Perf" drop: 2 runs x 7 areas x 1 rdc). Corrected an INVERTED layout
  (user had root/<run>/<area>/rdc; discovery wants root/<area>/<YYYY-MM-DD[_label]>/rdc) -> restaged in
  C:\tmp\perf via hardlinks (Downloads read-only), runs->dated drops (r110565->2026-05-25, r110788->
  2026-06-01), reconciled the cross-run area-name mismatch (Finanical/Financial District -> Financial
  district; Commerical->Commercial). Surfaced + fixed 2 REAL bugs the synthetic golden never exercised:
  (1) D-12 [afcb07e] trend_table single-drop crash ('str' has no .get - a loop var `kpis` clobbered the
  hero KPI list); (2) R-17 [bd82980] every r110788 replay exited rc=0xC0000005 (qrenderdoc ACCESS
  VIOLATION on the ctrl/cap.Shutdown NATIVE teardown) AFTER writing complete, consistent output, and was
  wrongly discarded as replay_failed -> replay_main now writes a completion sentinel
  (paths.REPLAY_COMPLETE_MARKER) as its last act; run._classify_replay salvages rc!=0+marker as
  replay_dirty_exit -> capture_status ok + manifest replay_dirty_exit record (ADR-23). Replay is ~150-220s
  PER capture (sequential). Rendered the real 2-run 7-area report (14 drops, 39145 entities): GPU delta
  -0.015s, big draw reductions in the June build (Chor bazar 1524->448), Police station/ibo bytes +33.9%
  flagged. 128->132 green; golden + parquet golden untouched (replay not run for synthetic). UNPUSHED.
- 2026-06-02 — dashboard KPI averages (user-requested, post-c16d). The hero strip showed only TOTALS
  (total gpu, total draws) which read as alarming to execs out of context. _global_kpis now pairs each
  total with a PER-FRAME average (avg gpu/frame, avg draws/frame), computed from the same frame_totals
  rows that fed the totals (n_frames = frame-row count -> the average is the true mean, self-consistent).
  Strip = 5 chips (total -> avg adjacency). PER-AREA avg is NOT a headline (one value per area, and
  total/n_areas degenerates to the total when areas=1 - user caught this): _top_areas_gpu now also
  returns avg_draws_frame per area and the dashboard trend-table CARD gained an "avg draws / frame"
  column (one row per area; real 6-area data shows each area's load). Presentation-only (reads existing
  frame_totals): only the dashboard golden moves; test_parquet_parity GREEN no digests refresh;
  129 green (test_report_structure pins the 5-chip label order + the per-area card column). smoke clean.
  UNPUSHED (commits 4f07ed4 + the per-area-card fix).
- 2026-06-02 — c16d DONE (report VISUAL OVERHAUL / design-language pass; G-17 closed; ADR-34). Shipped as 4
  reviewable sub-commits, each golden-refreshed + BROWSER-reviewed (light/dark/reduced-motion/print via
  Chrome headless): (a) 9079013 depth over borders - surface + soft elevation shadows (NEW [shadow] block
  --elev-1/2/3 via the ADR-27 skeleton, two-layer ring+drop tuned for light; dark rides surface-lightening),
  tables horizontal-rule only, severity color-mix box tint, sticky-h2 in-view cue moved to a ::before marker
  (h2 left-accent gone, JS unchanged), reduced-motion safety (--hover-scale:1 + --motion-spring:0s), print
  re-adds a 1px #888 border + box-shadow:none. (b) d67c5c2 type - VENDORED Inter subset (29KB woff2, Latin +
  tnum, wght 400-600) baked into the wheel + base64-inlined @font-face (offline + byte-deterministic, NO CDN;
  ADR-34 overrides the doc's "no web font" with user signoff); KPI/summary numbers + headings -> Inter sans
  tabular-nums, data tables stay mono. (c) 783840e chart finish - gradient fills (deterministic
  caller-threaded chart_id ids, no hash/counter), dimmed axes (axis_color -> --border-1), per-datum <title>
  tooltips. (d) 20b82c7 micro + pacing - dash-card hover scale+spring lift, copy-button resting tint,
  section.card padding sp-6, .dim drop-key suffixes. PARITY: golden HTML + preview REFRESHED all 4 commits;
  test_parquet_parity GREEN, NO digests refresh (§21.9). 115 -> 128 green; smoke 9 pages lint clean. Wheel
  verified ships inter-subset.woff2 + OFL, 162/162 unique (ADR-10 holds). ADR-34 appended; G-17 ticked;
  QUALITY_GATES §21.1i; c16d doc move #2 updated. UNPUSHED on v0.2-roadmap-c04. current -> v0.2 close-out.
- 2026-06-02 — c16d AUTHORED (report AESTHETICS + UX polish; user-requested). Wrote
  commits/v02/c16d_report_aesthetics.md - a presentation-only visual-design pass over the c16/c16b/c16c
  structure: depth over borders (surface + soft elevation shadow, tables horizontal-rule only; NEW
  light/dark shadow tokens via the ADR-27 skeleton), type hierarchy (KPI numbers in the SANS stack -
  NO web-font load since 'Inter' is only named not loaded; dim secondary to --text-3; drop in-card h2
  left-accent but keep the sticky highlight), chart finish (gradient fills + dimmed axes + per-datum
  SVG <title> tooltips), micro-interactions (spring + scale hover no-op under reduced-motion; resting
  affordances; tinted severity callouts), pacing (bigger padding + collapsed secondary tables). Opened
  FINDINGS G-17; added the c16d table row; current -> c16d; v0.2 close-out + tag now come AFTER c16d.
  Planning + impl in a new chat. NO code yet.
- 2026-06-02 — c16c DONE (report RESTRUCTURE; G-15 FULLY closed). Every report section now routes through
  chrome.section_card wrapped in <rdc-sticky-h2> (relaxed the component selector h2[id]->h2 so the card's
  id-less header h2 drives the highlight; section ids stay anchors). rdc-copy-button on the 3 named IDs
  (full value via safe_chrome_text even inside <td>): mesh hash / shader id+src / pass path. Instancing
  "material batching" is FILL-OR-HIDE (no bare heading; synthetic -> id="batching" gone). A11Y: <caption>
  + scope="col" on every report + dashboard table (zero bare <th>); trend gpu-delta KPI prints an explicit
  sign. DASHBOARD small-multiples: mini bars per card + a class-share donut on draws_by_class (user-chosen
  match-each-flagship) + insight subtitles + cross-report nav. NEW card-framing CSS in _CHROME_CSS_TMPL
  (literal var(), no $) -> drill/root/preview change only by shared CSS. PARITY (ADR-6/32/33): HTML + preview
  golden REFRESHED, reviewed via per-report marker diff; test_parquet_parity GREEN, NO digests refresh
  (§21.9). 108->115 green (+7 test_report_structure + test_design_tokens c16c asserts); smoke 9 pages lint
  clean exit 0. No new ADR (rides ADR-32/33). G-15 ticked FULLY DONE; QUALITY_GATES §21.1h added.
- 2026-06-02 — c16c REVIEW FIXES (user eyeballed rendered pages; 3 commits, golden re-refreshed, 115
  green): delta alarm gated to regressions only (was abs()-magnitude, painted red borders on -100%
  improvements; -24 false bars), sticky thead static inside section.card/a.dash-card (pinned header
  floated over the card, stranding row 1 above it), inner .table-wrap borderless (card is the single
  frame), bar_chart label column sized to the longest actual label so the bar starts right after the
  text (was fixed W*0.36 dead space) + dashboard mini chart transparent/borderless. v0.2 NOT closed
  yet - close-out (full-area ingest + tag) is the gate before c20.
- 2026-06-02 — c16b DONE (report CHARTS; G-15 charts half; ADR-33 implemented). NARROWED in execution
  (user-chosen): chart slice + shader column diet now; heavier restructure split into NEW c16c (golden
  stays reviewable, ADR-23). NEW reports/charts.py = deterministic dependency-free inline-SVG toolkit
  (bar/stacked/pct_stacked/donut/scatter+bubble/treemap/icicle/histogram/line + figure() wrapper),
  extends delta.sparkline_svg (fixed-precision coords, NO random/Date/ts); CSS var() colors (light-dark),
  draw-class via class_color_var; ALL text through safe_chrome_text (scrub+escape) so data labels can't
  trip the lint (charts ride OUTSIDE <table>). NEW [chart] design-tokens block (sizes + var() palette) +
  _tokens.chart() (not a :root section → never leaks). Chart wrapper CSS (figure.chart/.chart-svg/
  details.secondary-metrics) in _CHROME_CSS_TMPL (literal, no $); re-export via base.py. FLAGSHIP per
  report above its table: pass_gpu treemap + top-pass bars; draws_by_class donut + pct_stacked (replaced
  class_segments_bar rows); shader_hotlist scatter (bubble=src bytes) + complexity histogram; overdraw
  reject% bars + config warn/alarm rule-lines; instancing wasted-index bars; trend_table per-KPI line.
  shader COLUMN DIET 13→7 primary + <details> secondary metrics. NEW tests/test_charts.py (determinism/
  structure/theming/empty/counts/ASCII) + test_design_tokens [chart]+chart-CSS asserts + tests/
  make_golden.py (repeatable HTML golden refresh). PARITY (ADR-6/32/33): golden HTML + preview REFRESHED
  (reviewed page-by-page: 6 reports gain <figure class="chart">, drill/root/dashboard = shared chart CSS
  only); test_parquet_parity GREEN, NO digests refresh (§21.9). 99→108 green; smoke 9 pages lint clean
  exit 0. No new ADR (ADR-33 covers charts; split recorded in STATE + c16b/c16c docs). G-15 charts half
  ticked; QUALITY_GATES §21.1g fleshed; c16c authored. current → c16c.
- 2026-06-01 — c16 DONE (report-quality polish + mechanics; user pushed 5/10 → 10/10, SPLIT into c16 +
  NEW c16b). R-13 (cache SHA256 sidecar + load_cached: corrupt/missing/mismatch → warn + live-scan
  fallback, missing-col tolerant). Q-9 (_dashboard.py → dashboard.py + 4 refs). D-4 + D-7
  (manifest.check_schema_version/assert_compatible; render+catalog via catalog.build_catalog, ab via
  ab.main; PipelineError exit 1 + `ingest --force`; synthetic v3 → parity-neutral). D-11b dead-code
  swept (footer_legend + base export, _row_count, footer.legend + .sidecar-list span CSS, replay
  `if False`). POLISH: NEW chrome callout/heatmap_cell/provenance_strip/empty_state + report_page
  device=; config [report] thresholds (ReportCfg, H-39). All 6 reports + dashboard lead with a KPI strip
  + insight callout (threshold severity) + header provenance/device strip (GPU/driver/CPU/OS + tool
  versions from newest manifest; bobframes ver omitted → no golden churn) + heatmap-shaded columns +
  readable labels (ASCII `x` not `*`/`×`; `×` is lint-banned) + icon empty-states. Synthetic manifests
  gained fixed host_info/tool_versions stubs (+ make_synthetic). PARITY (ADR-6/32): golden refreshed
  (9 pages, <TS>-normalized, LF; reviewed — drill/root deltas = D-11b dead-CSS + shared .callout/
  .empty-state only) + preview golden; test_parquet_parity GREEN, NO digests refresh. 74→99 green
  (+delta/manifest_guard/cache/report_polish, +config[report], +design_tokens c16 CSS). smoke 9 pages
  lint clean exit 0. ADR-32 (report contract) + ADR-33 (inline-SVG chart model for c16b); QUALITY_GATES
  §21.1f/g. R-13/Q-9/D-4/D-7 + H-39 ticked; D-11b done; G-15 + G-16 opened. c16b authored. current → c16b.
- 2026-06-01 — c10 DONE (env-var rename RDC_*→BOBFRAMES_*; completes R-5, resolves Q-5; ADR-31). NEW
  config.getenv_legacy(canonical, legacy, default) = single source for the one-release legacy cadence,
  reusing c06's _warn_legacy_once + _warned_legacy one-shot machinery. RDC_KEEP_STAGE→BOBFRAMES_KEEP_STAGE
  (run.py stage-cleanup gate) + RDC_PIXEL_GRID→BOBFRAMES_PIXEL_GRID (host sets it in main + _do_replay so
  the qrenderdoc child inherits via os.environ; host reads back via getenv_legacy; replay_main reads
  BOBFRAMES_PIXEL_GRID or RDC_PIXEL_GRID INLINE — embedded py3.10 can't import config, H-6). RDC_ROOT
  ELIMINATED (ADR-31, user chose the cleaner route): parse_init_state is cwd-INDEPENDENT (consumes no
  project root; writes only under the absolute capture_stage), so RDC_ROOT was only ever the parse-child
  cwd and _do_parse always set it = project_root → threaded project_root into _parse_one's args (now a
  7-tuple) as the explicit subprocess cwd; deleted the global os.environ['RDC_ROOT'] set/restore. NO
  --project-root flag added to parse_init_state (dead surface, ADR-23). RDC_INSIDE_ARGS kept verbatim
  (3 consumers: qrd_harness/replay_main/probes.whatif — the qrenderdoc↔harness wire, renamed nowhere).
  70→74 green (+3 getenv_legacy precedence/warn-once/default, +1 _do_parse env-untouched R-5 lock; fixed
  the test_hardening _parse_one 6→7-tuple). PARITY (ADR-6): golden HTML + Parquet BYTE-IDENTICAL, git
  clean, NO refresh; smoke render-only 9 pages lint clean exit 0; grep RDC_ROOT = only comments/test
  asserts, ZERO reads. Q-5 ticked; ADR-31 appended. current → c16.
- 2026-06-01 — c09 DONE (engine-agnostic classifier; H-1/H-2/H-3/H-4/H-5 + D-6). NEW derives/classifier.py
  = the SINGLE analysis-layer draw-classification API: a state-capable rule engine (ADR-29) — rule matches
  if any marker predicate (marker_contains/marker_suffix) hits OR all `when` field conditions (over any
  draws column) hold; first match wins; else fallback_class. Markers are a REFINEMENT, not the foundation.
  NEW derives/draw_classifier.toml (UE default) + presets/{unity,godot,custom-template}.toml (unity/godot
  ILLUSTRATIVE per ADR-21; no dup ue.toml, ADR-30). tomllib/tomli shim (ADR-26, 3.10-safe) +
  importlib.resources. config +[classifier] preset/custom_path. Host: derive_post_merge (classify +
  frame_prefix_re), formatters.pass_short ([pass_strip]), pass_class_breakdown (gpu_duration_aliases),
  chrome.DRAW_CLASSES=class_order(). DEEP REVIEW (user pushed twice) flipped the direction: a first plan
  pushed a shared classifier INTO embedded-3.10 replay via JSON — but the replay _classify_draw is DEAD
  (feeds only passes.draws_by_class_*, 9 cols, ZERO readers, superseded by pass_class_breakdown). So D-6 =
  DELETE the dead replay copy; 9 cols stay ZEROED (PASSES_COLS frozen v3; replay-drift gate green); removal
  → c35 (D-11). Replay emits FACTS ONLY → §21.9 by construction. PARITY (ADR-6): UE preset reproduces the
  former host _classify_draw BYTE-FOR-BYTE — proven by a 300+ case oracle battery in NEW test_classifier.py
  (11 tests). 59→70 green; test_parity + test_parquet_parity GREEN, golden BYTE-IDENTICAL (git clean, NO
  refresh); smoke 9 pages lint clean; wheel ships classifier.py + 4 TOMLs, 150/150 unique 0 dups (ADR-10).
  Dead-code sweep (3 agents): only true redundancy = passes.draws_by_class_* (handled); ~30 "dead" cols
  NOT dead (drill browser surfaces every col); dead fns/CSS/branch (footer_legend/_row_count/footer.legend
  + .sidecar-list CSS/replay `if False`) → c16; col removal → c35. ADR-29/30; H-1..5 + D-6 ticked; D-10
  (marker-first fragility → c27) + D-11 (dead-code) opened; QUALITY_GATES §21.1e; ARCHITECTURE §3 annotated.
  REAL-INGEST VALIDATED (Chor bazar 5 caps, junctioned C:\tmp, Downloads read-only): 5×rc=0,
  parquetize 597199 + pass_class_breakdown 4245 + global_entities 16651 = BYTE-IDENTICAL to pre-c09
  baseline (§21.9 on real data); smoke --data exit 0, lint clean, R-16 commit survived. D-6 confirmed
  on output: passes.draws_by_class_* ALL ZERO; draws.draw_class fully populated (0 empty). current → c10.
- 2026-06-01 — c08 DONE (design tokens TOML + preview + Q-6; H-15/H-20/Q-6). NEW reports/design_tokens.toml
  ([color]/[spacing]/[type]/[motion]/[layout]) + reports/_tokens.py loader (tomllib/tomli shim, bundled-only,
  no deep-merge — Track A edits the packaged file; per-project overrides are Track B). PARITY (ADR-6/27):
  template.py embeds the :root block UN-MINIFIED on drill/root, so the hand-aligned bytes (1/2/3-space
  light-dark gaps) are in the golden and not reconstructable from values → keep the alignment SKELETON in
  chrome.py with string.Template $key placeholders, source only VALUES from TOML → byte-identical, NO golden
  refresh. H-20 layout literals (bar/ibar/kpi/grid floors/sticky) same mechanism; delta.sparkline defaults
  60/14 from [layout]. Var names preserved (--accent-primary; the --color-* rename deferred, ADR-28, would
  force a 9-page golden refresh). Q-6: NEW chrome.report_page() dedups open/header/strip/close across 5
  identical reports (report_key strip) + dashboard (current_page) + trend_table (bespoke strip in body);
  empty-state left as-is (concat, ungated). NEW verbs preview (gallery, no data) / export-tokens
  (toml|json|css, stdout) / render --watch (alpha mtime poll → subprocess re-render). NEW test_design_tokens.py
  (12) + golden_preview/_chrome_preview.html + make_preview_golden.py + _render_util.render_preview().
  47→59 green; test_parity + test_parquet_parity GREEN, golden byte-identical (git clean, no refresh); smoke
  render-only 9 pages lint clean; wheel ships design_tokens.toml + _tokens.py + preview.py, 0 dups (ADR-10).
  ADR-27/28; ARCHITECTURE §3/§4 + QUALITY_GATES §21.1d; H-15/H-20/Q-6 ticked. Scoping (ADR-23): responsive
  @container/print grid overrides + component widths left inline as breakpoint constants. current → c09.
- 2026-06-01 — c07 DONE (TOML config layer; H-12/13/14/16/17/21/22/23/30 + Q-3). NEW config.py loader
  (tomllib + tomli backport python_version<'3.11', ADR-26: qrenderdoc embeds py3.10 — python310.dll on
  box) → frozen Config dataclass; §6 lookup + bundled _default_config.toml SINGLE-SOURCE base DEEP-MERGED
  under the first-found user file (ADR-25: §6 'no merging' = file selection only). NEW _default_config.toml
  + lint_banlist.toml (15-entry, order kept). Readers → config.get_config(): timeouts (qrd_harness/rdcmd +
  --replay-timeout/--convert-timeout; convert_timeout threaded into the spawn pool as an ARG, not a child
  singleton), discovery DATED_RE (_dated_re(); module DATED_RE kept as fallback), lint banlist, formatters
  chrome_scrub/id_short_n/text_trunc_max, delta fmt/bar_label_min_pct, derive complexity weights.
  resolve_tool default → get_config() (empty [tools], c06 unchanged). cli check --write-config = curated
  commented starter (not a dump — keeps deep-merge forward-compat). Defaults BIT-IDENTICAL → test_parity +
  test_parquet_parity green, NO refresh; new test_config asserts struct.pack floats + regex .pattern +
  banlist roundtrip + spawn-arg threading + deep-merge + env-file precedence + write-config skip. _render_util
  scrubs BOBFRAMES_CONFIG (hermetic). 38→47 green; smoke clean; wheel ships both TOMLs 0 dups; py3.10/tomli
  load proven identical. ADR-25/26; ARCHITECTURE §3/§6 + QUALITY_GATES §21.1c. current → c08.
- 2026-06-01 — c06b DONE (G-14: Parquet-output parity gate; no-patch-fix per ADR-23). NEW
  tests/test_parquet_parity.py: render synthetic → walk every rendered _data/**/*.parquet (58 tables
  incl. _catalog + _global_entities) → compare a WRITER-INDEPENDENT logical digest (ordered schema +
  num_rows + sha256 over Table.to_pydict() in schema column order, row order kept; NOT on-disk bytes,
  the D-8 trap) vs committed tests/data/golden_parquet/digests.json. NEW _render_util helpers
  (rendered_parquet_files / parquet_digest / compute_digest_map) + tests/make_parquet_golden.py
  refresh script. NaN HIT root-caused not masked: allow_nan=False tripped on vbo_samples.as_f32_*
  (raw VBO bytes as float32 → legit NaN; pyarrow float64 str is "double" so first scan missed it) →
  canonicalize non-finite floats to fixed sentinels ({"__nf__":...}) so values stay GATED, NOT
  allow_nan. PROVEN full-matrix: digests byte-identical under py3.10/pa17, py3.12/pa21, py3.13/pa21 →
  gate runs every CI cell (not in ci.yml --ignore, unlike ADR-11-pinned HTML parity). Negative test:
  reversing build_global_entities' glob sort fails the gate naming _global_entities.parquet (same
  num_rows, diff rows_sha256 — the exact c05 regression). render-only re-derives only the latest
  discovered drop; older drop served as fixture copies (matches HTML golden's single drill page).
  37→38 green; HTML parity/determinism/schema/perf untouched; smoke + lint golden clean. G-14 ticked
  → c06b; QUALITY_GATES §21.1b added. current → c07.
- 2026-06-01 — c06a DONE (D-8 drill-size de-harden; no-patch-fix per ADR-23). Removed all three
  os.path.getsize-derived values that reached rendered HTML in html/template.py: the per-table
  CSV/parquet download-link size in _inline_table_with_data (the writer-dependent byte behind ADR-11 —
  pa17 15.1KB vs pa21 12.3KB), plus the shader_src `// 1024` size and the jsonl sidecar _file_size_label
  span in _sidecar_category; deleted the now-unused _file_size_label. `grep getsize bobframes/html/` is
  empty. Chose to DROP the span (user: "do what's better for tool lifespan"), not the doc's "row count" —
  the table header already prints {rows:,} rows/{cols} cols (row count would triple it) and csv_sz is
  empty on csv-less tables (a row count would lie about a 404 link). Refreshed the one golden drill page
  via byte-level regex to keep LF + a minimal diff (361 bytes, 26 tables × CSV+parquet; no other line
  changed). 37 green (test_parity on canonical cell), lint clean. Writer-KB divergence is GONE → the
  un-pin floor for test_parity is now just the float-ULP (pass_gpu pct_share); ci.yml --ignore split
  unchanged (still needed for the float half). FINDINGS D-8 ticked → c06a. current → c06b. _row_count
  (already dead) + unused .sidecar-list span/.ct CSS left untouched (out of scope).
- 2026-06-01 — R-16 FIXED (real-ingest commit-lock). Root cause: stage tree (with the inheritable
  _harness.log handle, grabbed by the respawning adb daemon) lived INSIDE <drop>.tmp, and the
  pre-commit `rmtree(stage, ignore_errors=True)` silently swallowed the locked-log failure (R-12), so
  `os.replace(tmp, final)` failed [WinError 5] after a fully green ingest. Fix: NEW
  paths.drop_stage_dir = `<drop>.stage` (SIBLING of the .tmp commit dir, not nested); run.py uses it,
  clears stale stage at start, and moves stage cleanup to AFTER the commit (best-effort). A held log
  handle can no longer be inside the renamed dir. NEW test_hardening.test_stage_dir_is_sibling_not_
  inside_commit_dir locks the invariant. 36→37 green, golden byte-identical. Real end-to-end re-proof
  (commit survives adb) optional (~20min replay). Follows R-4/ADR-4 lineage; no new ADR.
- 2026-06-01 — c06 DONE (tool resolver + errors + glob version detect; H-7). NEW config.py:
  resolve_tool/resolve_tool_verbose over one ordered _candidates list — BOBFRAMES_* env > legacy
  RENDERDOCCMD/RENDERDOC_QRENDERDOC (one-shot deprecation log) > [tools] config > shutil.which > known
  Win paths > ToolNotFound. Arm glob (_ARM_GLOB 'Arm Performance Studio */renderdoc_for_arm_gpus/
  {name}.exe', latest by dir-name reverse sort) kills the baked 2026.2 path; vanilla/LOCALAPPDATA in
  _KNOWN_PATH_TEMPLATES. [tools] read defensively (getattr .tools then dict) → no signature churn when
  c07 passes a dataclass singleton; config=None branch dormant. .exe/Win paths kept hardcoded for
  Windows-only v1 (c36 drops per-OS), commented. NEW errors.py: EXIT_* + BobFramesError/PipelineError/
  ToolNotFound; ToolNotFound.format_message renders the §5 block from attempts. Rewired rdcmd/
  qrd_harness finders to thin resolve_tool wrappers (names kept for manifest + test_hardening
  monkeypatch); dropped _DEFAULT_PATHS/_DEFAULT_QRD; _SEP + RDC_INSIDE_ARGS untouched. cli._cmd_check
  → resolve_tool_verbose (path + 'via <source>' when ≠path; 0/3 + §5); cli.main catches BobFramesError
  → e.exit_code. NEW tests/test_config.py (4 hermetic: env>known precedence, legacy warns-once, Arm
  glob latest-version pick, ToolNotFound exit3+§5). Baseline 32-green before; 36-green after, golden
  byte-identical (no refresh). Live: real Arm 2026.2 resolved via `*` glob (H-7 proven) exit 0;
  forced-miss → §5 block + exit 3. H-7 ticked. current → c07; REAL-INGEST smoke now due (ADR-6).
- 2026-05-31 — c05 DONE (registry consolidation; H-8/9/10/11 + D-1). Migrated schemas.TABLES values to
  a TableSpec NamedTuple (cols, size_class, is_entity, category, api="core" reserved for c33) and
  REORDERED the dict to the old catalog key order so `catalog._CATALOG_TABLE_KEYS = tuple(TABLES.keys())`
  stays byte-identical (render_root bakes catalog column order into the golden root index.html). Added
  table_category()/entity_tables(); helpers read named fields. global_entities now iterates
  entity_tables() with id_col-by-convention + depluralized kind ({render_targets:texture} override).
  template dropped _CATEGORY_MAP — category from the record; within-category DISPLAY order kept as a
  presentation-only _TABLE_DISPLAY_ORDER tuple (empirically a third distinct ordering vs TABLES/catalog,
  so it cannot be derived — exactly one of {catalog,template} must keep an explicit order; user chose
  catalog-derives). reports/__init__ gained all_reports()+register_report() (lazy, runtime-augmentable
  for c38; frozen ALL_REPORTS rejected); orchestrator+ab consume it (dropped _REPORT_MODULES/_MODULES).
  test_schemas_unit fixed for the 5-field record. Baseline 32-green before, 32-green after, byte-identical
  (no golden refresh). In-memory scratch check: a dummy is_entity table auto-appears in catalog +
  entities + template, tailing its category with existing order intact. _global_entities row order shifts
  (ungated parquet, not in golden) — accepted. Verified forward-fit with c06/c33/c38/ADR-14. current → c06.
- 2026-05-31 — c04 DONE (first v0.2 implementation commit). Centralized the layout literals in
  paths.py: 10 module constants (DATA_DIR/REPORTS_DIR/CACHE_DIR/STAGE_DIR/DRILL_DIR/AB_DIR/TMP_SUFFIX/
  MANIFEST_NAME/DONE_MARKER/INDEX_HTML); paths.py funcs + manifest/catalog/run/parquetize/html.template/
  reports.{cache,cli,chrome,_dashboard} + the 5 test fixtures now reference them. Reused existing paths
  funcs (reports_dir, reports_cache_dir) where they matched; added no new functions (API gained only
  constants). render_root's relative-URL strings ('_reports/...', '_data/...') routed through the
  constants too (identical bytes). TMP_SUFFIX='.tmp' (doc said '_tmp' — typo; real value kept for
  parity). Verified: baseline 32-green before, 32-green after (test_parity/schema/determinism/perf/
  hardening/smoke all pass → byte-identical, no golden refresh). Grep gate clean: the 4 gated literals
  remain only in paths.py + two `#` comments. H-18/H-19 ticked. current advances to c05.
- 2026-05-31 — v0.2+ ROADMAP produced (planning session; no code). Turned V02_PLANNING_PROMPT.md into:
  new ROADMAP.md (vision + measurable per-persona success + v0.2->v0.6 phasing); 20 per-commit docs
  c20-c39 under commits/v03..v06/ (CI/automation -> engine+ergonomics -> Vulkan adapter epic ->
  cross-platform+plugins); ADR-14..22 appended to DECISIONS.md (multi-API unified-core+extension schema,
  Vulkan-first, versioned --json, query optional extra, cross-platform@v0.6, trusted-local plugins,
  GH-Release sample, generic-first presets, per-API/engine golden); MIGRATION.md v0.3-v0.6 spine tables;
  FINDINGS (G-1/2/4/5/9/10 repointed to c20-c26, M-1/2->c38, new D-6 classify-draw drift + G-13
  texture_usage, S-1->v0.6) + HARDCODE (new H-36/37 graphics-API, H-38 platform process model) updates;
  ARCHITECTURE §3 (deps) + §12 (cross-platform) annotated by ADR pointer (frozen, not rewritten).
  Mapped all three breadth seams against real code via Explore agents (no line numbers). Strategic
  decisions locked with the user (8 of them). current stays c04 — v0.2 execution is unchanged and next.
- 2026-05-31 — c19 DONE: bobframes 0.1.0 RELEASED. Switched publish to PyPI Trusted Publishing
  (OIDC, ADR-13) — no token; user saved a pending publisher (altpsyche/bobframes/ci.yml). Pushed main
  (CI green on OIDC workflow d11c84e), then tagged v0.1.0 + pushed -> publish job green: build ->
  OIDC upload -> GH Release. Verified live: PyPI bobframes 0.1.0 (wheel + sdist), GH Release v0.1.0
  with both assets. Post-install from clean PyPI install (uv isolated): version / check / smoke
  render-only all exit 0. v0.1 extraction release COMPLETE; v0.2 de-hardcoding (c04+) is next.
- 2026-05-31 — CI green after ADR-11 fix (user confirmed). Release prep: remote is altpsyche/
  bobframes, but pyproject [project.urls] + CHANGELOG link refs pointed at mayhem-studios -> would
  404 on the PyPI page. Repointed all 5 URLs to altpsyche (ADR-12; author email @mayhem-studios.com
  left as the real contact); annotated frozen ARCHITECTURE §3. Lint clean, pyproject parses. c19 now
  gated only on: set PYPI_API_TOKEN + authorize the irreversible tag push.
- 2026-05-31 — CI first-push RED, root-caused + fixed (ADR-11). Matrix failed on {3.10,*} and
  {3.12,pa17}; passed only {3.12,pa21}/{3.13,pa21}. Reproduced each cell locally via `uv run
  --isolated --python X --with pyarrow==Y` rendering synthetic + diffing golden (read-only). Two
  independent env-variable bytes in the golden HTML: (A) drill page prints parquet on-disk KB ->
  differs by pyarrow writer (pa17 15.1 vs pa21 12.3 KB); (B) pass_gpu bar-width pct_share flips
  0.62->0.63 on py3.10 (1-ULP numpy-build diff at .2f boundary). Each cell diverged in exactly 1
  file; all functional gates + determinism (within-env) green everywhere. Fix: pin test_parity to
  canonical cell (py3.12+pa21) in ci.yml (`--ignore=test_parity.py` on all cells + a canonical-only
  test_parity step); appended ADR-11, noted QUALITY_GATES §21.6. Validated split locally: 31 + 1 = 32
  green. Re-push needed to confirm matrix green.
- 2026-05-31 — pre-release real-rdc validation: ran `bobframes smoke --data` on a junctioned temp
  root holding the real Chor bazar/2026-05-27_r110565 drop (5 captures; C:\tmp, Downloads inputs
  read-only via junction, removed safely after). Full pipeline green: parse 5x, live qrenderdoc
  replay 5x rc=0 (~176-218s each), parquetize 597199 rows, program_transitions 415, pass_class_
  breakdown 4245, atomic commit, catalog 1 drop/5 captures, global_entities 16651, 7 reports +
  dashboard + root index, lint clean -> exit 0. This is the first end-to-end run of the packaged
  ingest path (c12 replay_script_path resolution + c03 Popen/taskkill harness had only been mocked);
  schema-match on real parquet validates the H-6 dup beyond the static drift test. PyPI name free.
  c19 left BLOCKED on release-ops (no remote / token / authorized irreversible push).
- 2026-05-31 — c18 done: wrote the user-facing README.md from the §13 outline (requirements, install,
  quickstart, commands table from ARCHITECTURE §4, external tools, output layout from paths.py, the
  _analysis->bobframes migration as an ASCII table, troubleshooting incl. the G-3 `ingest --force`
  schema-migration note, advanced). Finalized CHANGELOG.md to Keep-a-Changelog with a [0.1.0] section
  (KEY_VERSION=1 key-format note, Windows-only + hard-rename `_analysis` removal callouts) and an
  empty [Unreleased]. LICENSE was already standard MIT (no change). Both .md pass the banlist gate
  `bobframes lint README.md CHANGELOG.md` (exit 0) — required dropping every arrow/em-dash and banned
  word (Keep-a-Changelog's "notable" -> reworded; avoided "the following"/"overview"/"etc."). LICENSE
  itself trips lint only because it's non-.md (linted as HTML) and MIT text contains "the following
  conditions" — left as-is (immutable legal text, not in the gate). Not advancing date assertions:
  CHANGELOG [0.1.0] is dated 2026-05-31; c19 confirms at tag. pytest 32 green.
- 2026-05-31 — packaging fix (ADR-10): dropped the redundant `"bobframes/tests/data"` wheel
  force-include in pyproject.toml. The .gitignore negation makes the fixtures tracked, so
  packages=["bobframes"] already ships them; the force-include added a 2nd copy → ~65 duplicate zip
  entries. Verified: wheel now 130/130 unique, 0 dups, still ships replay_main.py + 54 synthetic
  parquet + 2 manifests + 9 golden html; twine check passes. Kept the replay_main.py force-include
  (no dup, §3-justified). Annotated frozen ARCHITECTURE §3 with the ADR-10 pointer (not rewritten).
  pytest 32 green. Not a plan commit — current stays c18.
- 2026-05-31 — c17 done: added .github/workflows/ci.yml. test job runs on push/PR (windows-latest ×
  py{3.10,3.12,3.13} × pyarrow{17,21}); excluded the {3.13,17} cell since pyarrow 17 has no cp313
  wheel (3.13 support landed in pyarrow 18) — a faithful deviation from §21.6's literal grid. Steps:
  install + pin pyarrow, one `pytest bobframes/tests -v` (subsumes §21.6's per-file gate list since
  files are test_*.py — `tests/unit_*.py`→test_stable_keys/test_schemas_unit/test_discovery, etc.),
  `bobframes smoke` (render-only), lint golden via Get-ChildItem enumeration. publish job is v*-tag-
  gated (build → twine upload → softprops GH release), inert until c19. Validated YAML structure and
  ran every gate command locally (pytest 32 green, smoke 0, lint golden 0); dry-validated the build
  (python -m build + twine check → both wheel & sdist PASSED). Found a wheel DUPLICATE-entry warning:
  packages=["bobframes"] already ships tests/data, force-include re-adds it (ARCHITECTURE §3 frozen →
  deferred to an ADR in c18/c19). CI green-on-push not verified (no remote push this session).
- 2026-05-31 — c15 done: full rewrite of tests/smoke.py (G-12). Removed AREA='Chor bazar'/
  DROP_LABEL='r110565'/DROP_DATE + the __file__-walked ROOT. Two modes: no --data → render-only vs
  bundled synthetic via _render_util.render_fresh (CI-safe, no .rdc/GPU); --data DIR → full ingest
  using discovery.find_drops to auto-pick area+latest drop. Both assert schema match + stable_key +
  catalog + lint-clean HTML; CSV-pair check gated to full mode (synthetic is parquet-only, ADR-8).
  Wired --data + pixel_grid through cli._cmd_smoke (§4 surface unchanged). Added 3 unit files named
  test_* (NOT the doc's unit_* — no python_files override, default discovery): test_stable_keys
  (version/normalize/empty-contract/order-invariance), test_schemas_unit (expected_columns roundtrip,
  ID_COLS prefix, dtype totality), test_discovery (latest-drop pick + no-fallback when newest empty,
  filters, capture sort, parse_single_drop_arg). pytest 32 green; `bobframes smoke` exit 0. Full
  --data ingest path needs Windows+RenderDoc (self-hosted/nightly, ADR-6) — not exercised here.
- 2026-05-31 — c13 done: new tests/test_replay_drift.py ast-extracts replay_main.py `*_COLS` (resolves
  `ID_COLS + (...)`), maps var→schema stem (alias map for RT/RT_TIMELINE/STATE_CHANGE/COUNTERS), skips
  ID_COLS, diffs vs schemas.py. ADR-5's literal spec couldn't be green: verified 20 tables (not >=21)
  and events/draws/passes legitimately omit 4 host-derived cols (parent_marker_path_norm /
  parent_pass_path_norm / draw_class / marker_path_norm, added in derive_post_merge). Took Option A
  (pinned-derived allowlist): equality vs schema-minus-_DERIVED_COLS + assert >=20 + allowlist sanity
  check. Appended ADR-9 (correction recorded by append; DECISIONS frozen), added the §9 dup-policy
  comment to replay_main.py (no logic change), ticked H-6 (D-2 stays partial). pytest 12 green.
- 2026-05-30 — c12 done: added bobframes/replay/__init__.py with replay_script_path() (importlib.
  resources files()+as_file context manager); run._do_replay resolves replay_main.py through it and
  no longer walks project_root (param removed; process_drop call + c03 test updated). Confirmed it
  resolves to the real on-disk path from a foreign cwd. pytest 11 green. No new ADR (mitigates the
  zipped-wheel risk in DECISIONS §15).
- 2026-05-30 — c11 done: built full cli.py argparse dispatcher over §4 verbs (ingest/render/ab/
  report/catalog/lint/check/serve/smoke/version), positional root default '.', exit map 0/1/2/3/4,
  heavy imports lazy. run.py `_log` now routes through stdlib `logging` ('bobframes' logger,
  idempotent setup_logging, --verbose→DEBUG, [HH:MM:SS] format kept; G-8). ab.py: positional root
  + hidden --root alias. reports/cli already §4-compliant (no change). Caught+fixed a cp1252
  UnicodeEncodeError from a non-ASCII (→/…) help string. Verified end-to-end render via cli (9
  pages). pytest 11 green. No ADR (follows ADR-7).
- 2026-05-30 — c03 done: ingest hardening (R-1..R-8, H-27/28, G-6/7/11). Atomic tmp+os.replace for
  manifest/parquet-pair/done.marker; qrd_harness now Popen+taskkill tree-kill on timeout; replay
  failure → `replay_failed` (no abort); RDC_ROOT save/restore; stderr always logged; KEY_VERSION=1
  byte in stable-key hash; single UTC `now_iso` (reports/cli delegates). Added test_hardening.py
  (named test_* not unit_* so default pytest collects it — no python_files override). 11 green.
  No new ADR (follows ADR-3/4/6); golden parity untouched (render path never recomputes keys/manifest).
- 2026-05-30 — c02 done: built scrubbed synthetic fixture + golden + 4 parity/schema/determinism/
  perf tests (green); fixed .gitignore to track fixtures; committed f8cf833. Found only 1 render
  nondeterminism (catalog build timestamp) — masked.
- 2026-05-30 — Verified install-ready (uv .venv py3.12, `bobframes version` works); added cli.py
  seed; recorded ADR-8 (repo data-free, tests use external capture _data); made initial git commit.
- 2026-05-30 — Copied source into bobframes/ (46 .py), swept package-name refs, all compile; c01 done.
  Stray dev prompts (CLI_PROMPT.md, reports/OVERHAUL_PROMPT.md) dropped. Noted: `_analysis_out`
  appears in stale comments/examples (real output dir is `_data`) — candidate FINDINGS cleanup.
- 2026-05-30 — Created repo scaffold at c:\Users\vsiva\dev\bobframes (dirs + root product files).
  Package named `bobframes` directly → c14 rename collapsed (ADR-7); STATE/MIGRATION/affected commit
  docs updated. Source not yet copied; git init deferred.
- 2026-05-30 — Carved CLI_PLAN.md into this doc set. Corrections from review already baked in
  (R-9 withdrawn, R-4 → process-tree kill, §21.3 drift-test rewrite, stale names fixed).
