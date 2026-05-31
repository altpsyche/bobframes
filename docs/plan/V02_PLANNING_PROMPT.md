# bobframes v0.2+ planning prompt

> The brief for the **next planning session** — the one that turns the v0.2+ vision into a
> commit-by-commit spine. Paste §0-§7 below into a fresh planning agent (it begins by reading
> [STATE.md](STATE.md)). The session's job is to produce plan docs (MIGRATION spine, per-commit docs,
> a ROADMAP, ADRs), not code.
>
> **Why this exists:** v0.1.0 shipped Windows-only / OpenGL-only / Unreal-tuned. The goal for v0.2+
> is the best RenderDoc data + reporting tool for a *wide* audience. Three breadth axes are deeply
> hardcoded today (graphics API in `replay/replay_main.py`; engine in the classifier; platform in the
> tool harness), and several cheap, high-leverage audience gaps exist (CI `--json`/gating, isolated
> stages, query ergonomics, the unused `texture_usage` report). This prompt embeds a **recommended
> release sequence** (validate specifics with the user) and keeps **all three breadth axes on the
> roadmap**.

---

## 0. How to work (in order)
1. **Read [STATE.md](STATE.md) first** (resume anchor: `active_release`, `current`, `next_action`,
   session log). Then [MIGRATION.md](MIGRATION.md) (commit spine), [ARCHITECTURE.md](ARCHITECTURE.md)
   + [DECISIONS.md](DECISIONS.md) (FROZEN, append-only; 13 ADRs), and
   [reference/FINDINGS.md](reference/FINDINGS.md) / [HARDCODE.md](reference/HARDCODE.md) /
   [QUALITY_GATES.md](reference/QUALITY_GATES.md).
2. **Reuse existing seams; do not invent parallel ones.** Extend these:
   - `bobframes/schemas.py` `TABLES` (single table registry; `expected_columns`/`is_entity_table`),
     `ID_COLS`, `SCHEMA_VERSION`.
   - c05 report-registry target (`reports/orchestrator._REPORT_MODULES` + `reports/ab._MODULES` ->
     one `ALL_REPORTS`).
   - c09 classifier-TOML target (collapses `derive_post_merge._classify_draw` +
     `replay/replay_main._classify_draw` + `formatters.pass_short` + `chrome.DRAW_CLASSES` into one
     preset).
   - c06 tool resolver (`config.resolve_tool()`: env > config > PATH > known-paths glob).
   - `paths.py` constants (c04), TOML config (c07), design tokens TOML (c08).
3. **Prefer extending the eight planned v0.2 commits (c04-c10, c16)** over parallel work.
4. **Every commit is one unit** with a verify command + a "Done when" gate, kept behind the golden
   parity gate. Update STATE.md/MIGRATION.md each session; tick FINDINGS/HARDCODE rows closed.
5. **Commit numbers are fixed and never renumbered**; new phases append new `cNN` in new `vXX/`
   folders.

## 1. Vision & measurable success (write into a new `docs/plan/ROADMAP.md`)
"Best RenderDoc tool for a wide audience" — graphics engineers, tech artists, perf leads/producers,
CI/automation. Define "best" measurably per persona, e.g.:
- **Breadth:** works on >=2 graphics APIs and >=2 engines, and runs on >=1 non-Windows OS.
- **Engineers:** isolated-stage debug verbs, integrity verify, queryable Parquet (SQL + schema
  introspection), shader-source links.
- **Artists:** mesh/material workflow, overdraw heatmap, per-material trend.
- **Leads:** configurable regression gating, historical multi-drop dashboard, custom KPIs.
- **CI:** `--json` everywhere, exit-code gating, `--dry-run`, `export`, `diff`, isolated stages.
- **Adoptability:** install + first report against a public sample capture in <5 min; documented
  extension points.
Turn each into a concrete acceptance signal phases are graded against.

## 2. Dimensions to plan across (organize the plan by these)
**(a) Breadth — ALL THREE axes are in scope (sequence them; drop none):**
1. *Graphics API.* `replay/replay_main.py` uses only `ctrl.GetGLPipelineState()`; GL-specific
   shader/buffer/sampler model, std140 UBO decode, `GL_*_ATTACHMENT` names, `_CLEAR_CHUNK_NAMES`
   (glClear*), and `FRAME_TOTALS_COLS` (`glX_count`). RenderDoc exposes
   `GetVulkanPipelineState`/`GetD3D12PipelineState`/etc. Seam: an **`APIReplayAdapter`** dispatched on
   `ctrl.API()` + **data-driven schema columns** (move `glX_count` to API-specific optional columns;
   generate `draws_by_class_*` from a class list). New API = NEW extraction; GL Parquet stays
   byte-identical.
2. *Engine.* `_classify_draw` (in BOTH `replay_main.py` and `derive_post_merge.py`) + `pass_short` are
   UE-tuned (basepass/shadow/prepass/slate/`FRDGBuilder::Execute`/`MobileSceneRender`/
   `/Engine/EngineMaterials`/`Frame N` prefix); `chrome.DRAW_CLASSES` is a 3rd copy of the class enum
   (H-5). c09 externalizes to a classifier TOML + UE preset + presets dir — extend with
   Unity/Godot/generic presets + a pluggable pass normalizer.
3. *Platform.* `qrd_harness.py`/`rdcmd.py` hardcode the Windows Arm Performance Studio 2026.2 path,
   `.exe`, and `taskkill` tree-kill. Cross-platform = per-OS tool locator (extends c06) + non-Windows
   process-tree kill (`os.killpg`/job-object) + RenderDoc discovery.

**(b) Audience features:** `--dry-run` (G-1), `diff` (G-2), `verify` (G-4), `export` (G-5), `--json`
(G-9), isolated-stage `parse`/`replay` (G-10), exit-code regression gating (thresholds are hardcoded
in `reports/trend_table.py` -> make config-driven via c07); DuckDB/SQL query verb + `schema`
introspection; ship the already-derived-but-unused `texture_usage` report; overdraw heatmap;
mesh/material workflow; historical multi-drop dashboard.

**(c) Foundation map (which de-hardcoding unblocks what):** c05 -> data-driven API columns + report
auto-discovery; c06 -> cross-platform tool location; c07 -> configurable thresholds/timeouts/regex;
c09 -> engine breadth. State each feature's foundation prerequisite explicitly.

**(d) Reliability/scale:** R-10..R-15; S-1 sequential replay (600s x N, the big one), S-2 single-thread
merge, S-3 catalog full scan, S-4 global_entities scan, S-5 derive read-modify-write. Plan as
**measure-then-optimize**, not speculative.

**(e) Extensibility/plugins:** auto-discovery for reports/derives/classifier-presets/API-adapters
(M-1 `pkgutil.iter_modules` + `build()` convention; M-2 schema-table registration). Define the plugin
**security posture** (open decision).

**(f) Distribution/onboarding:** public sample capture + sample `_data/` so a new user gets a report
in minutes (repo stays data-free — decide where sample lives); per-persona quickstarts; extension
guide.

**(g) Test strategy for multi-API/engine:** repo is data-free; synthetic fixture drives CI;
real-`.rdc` full ingest is self-hosted/nightly (no GPU on CI). **Each new API and each new engine
needs a new synthetic fixture + new golden** (anonymized from a real ingest, ADR-6/ADR-8). Define how
those fixtures are produced and how per-API/per-engine golden parity is maintained.

## 3. Recommended release sequence (embed as the default; validate specifics with the user)
- **v0.2 — De-hardcoding foundation (M).** Finish c04-c10, c16 (parity-gated, output byte-identical).
  Closes D-1/H-1..H-23/H-30/Q-3/R-13/Q-9. Unblocks everything; budget most time on c09 (most
  invasive) + the TOML round-trip parity surface. No SCHEMA_VERSION bump.
- **v0.3 — CI/automation surface (S-M). THE high-leverage next step.** `--json` FIRST (additive; no
  HTML-golden impact; version it with its own `json_schema_version`), then config-driven regression
  gating (depends on c07), isolated-stage verbs (G-10), `--dry-run` (G-1), `verify` (G-4), `diff`
  (G-2), `export` (G-5). Widest, cheapest audience; builds the substrate automated quality needs
  *before* the API epic churns schemas.
- **v0.4 — Engine breadth + engineer/artist ergonomics (S-M).** Unity/Godot/generic classifier presets
  (cheap post-c09; each gated behind a real-`.rdc` smoke from that engine; ship "generic" as honest
  default) + `texture_usage` report + overdraw heatmap + DuckDB/SQL query verb + `schema`
  introspection + mesh/material report. New reports add golden fixtures; no schema bump.
- **v0.5 — Graphics-API adapter epic (XL).** Refactor GL extraction behind a `PipelineStateAdapter`
  (GL adapter = today's code, parity-clean, no output change) as a SEPARATE commit BEFORE any
  schema-widening; then a second API (recommend **Vulkan** first — cross-vendor, aligns with the
  cross-platform epic; D3D12 validates the abstraction). New synthetic fixture + golden PER API;
  schema-widening commits bump `SCHEMA_VERSION` (forces golden refresh + bobframes MINOR pre-1.0).
- **v0.6+ — Cross-platform + leads + plugins (L).** Linux/macOS tool locator (extends c06) +
  non-Windows tree-kill; historical/trend dashboard + regression alerts (leads); custom report
  plugins (gated on M-1/M-2 + security model); optional Figma token sync. New nightly real-`.rdc` lane
  per OS.

Each phase entry in the plan must list: theme, the `cNN` commits, FINDINGS/HARDCODE rows closed, the
success criteria satisfied, and dependencies on prior phases.

## 4. Open decisions to put to the user (do not pre-decide; pose before locking each epic)
1. **First graphics API — Vulkan vs D3D12** (recommend Vulkan; confirm against the user's actual
   captures).
2. **Schema shape for multi-API — unified core + small per-API extension table** (recommended) vs
   per-API tables. Load-bearing; decide before v0.5.
3. **First engine preset order — Unity / Godot / generic** (which real captures exist to validate?).
4. **Cross-platform timing** — v0.6 default; pull into v0.5 only if a Linux/Vulkan shop is the target.
5. **Query ergonomics depth** — bundled DuckDB dep (new dep -> ADR) vs documented "point your own
   DuckDB at the Parquet" vs introspection-only.
6. **Plugin security model** — trusted-local-only vs sandboxed/signed; acceptable import/`eval`
   surface.
7. **Sample-data hosting** — released GH asset vs separate repo vs download-on-demand (repo stays
   data-free).
8. **`--json` as a versioned contract** — commit to an independent `json_schema_version` from day one.

## 5. Output artifacts of the planning session
- Updated [MIGRATION.md](MIGRATION.md) spine (new `cNN` entries grouped by phase).
- Per-commit docs `docs/plan/commits/vXX/cNN_*.md` (context, seam extended, exact files, verify
  command, "Done when" referencing the parity gate).
- New ADRs appended to [DECISIONS.md](DECISIONS.md) for ANY frozen-doc divergence (new API path;
  schema add -> SCHEMA_VERSION bump; cross-platform; new dep; plugin model), with the frozen section
  annotated by a pointer (follow the ADR-10/11/12/13 pattern — never rewrite frozen text).
- [FINDINGS.md](reference/FINDINGS.md) / [HARDCODE.md](reference/HARDCODE.md) rows added/updated
  (`resolved-by` = new commits).
- New `docs/plan/ROADMAP.md` (vision + measurable success + the §3 phasing).
- [STATE.md](STATE.md) `next_action` + a session-log line.

## 6. Hard rules (carry into every planned commit)
- **Golden HTML parity gate green every commit.** Byte-parity pinned to canonical env py3.12+pa21
  (ADR-11); functional gates run the full matrix. Output-changing commits MUST intentionally refresh
  the golden in the same PR and say so in "Done when". New computed/aggregated output risks the same
  cross-env divergence that bit c17 (parquet-size by pyarrow writer; 1-ULP % by numpy) — bake new
  goldens on the canonical cell.
- **ARCHITECTURE.md + DECISIONS.md FROZEN, append-only.** Change behavior only via a new ADR +
  annotation.
- **`SCHEMA_VERSION=3` + `ID_COLS=(area,drop_date,drop_label,capture)` are a frozen v1 contract
  (H-29).** Any schema add/rename -> SCHEMA_VERSION bump (pre-1.0 = MINOR) + golden refresh. New
  API-specific columns must be optional/additive + data-driven, never edits to GL output.
- **Data-extraction guarantee:** identical Parquet for identical `.rdc`. De-hardcoding must not change
  extraction; a new API path is new extraction with GL byte-identical.
- **Repo data-free (ADR-8);** synthetic fixture drives CI; real-`.rdc` is self-hosted/nightly. New
  APIs/engines need new fixtures + golden.
- **No new heavy runtime deps without an ADR** (current dep: pyarrow only). DuckDB/etc. is an ADR.
- **CLI conventions (ARCHITECTURE §4):** positional `<root>` default `.`, long-flags only, exit codes
  0/1/2/3/4, stdlib logging.
- **Test-file naming:** default pytest discovery only collects `test_*.py` (no `python_files`
  override) — name new tests `test_*.py`.

## 7. Deliverable shape
A phased roadmap + per-commit spine an implementer can execute commit-by-commit: every commit
parity-gated, every frozen-doc divergence backed by a new ADR, the §4 decisions posed to the user
before each breadth epic is locked, and — wherever a new API/engine/OS is involved — the
**fixture + golden** work named as its own gated step.
