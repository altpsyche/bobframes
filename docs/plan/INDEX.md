# BobFrames implementation plan — index

This folder is the plan for extracting the `_analysis/` RenderDoc pipeline into the standalone
`bobframes` CLI. It is **plan-driven across sessions**: you should never need to read everything to
make progress. Open two or three small files and go.

## Read order (every session)

1. **[STATE.md](STATE.md)** — where we are. Names the active release + the current commit. **Start here.**
2. **[commits/](commits/)** `<release>/<current>.md` — the one unit of work to do now. Has its own
   "Done when" gate; stop when it's green.
3. Update **STATE.md** before you stop (status, `last_session`, `next_action`).

Everything else is reference — open it only when a commit doc points you there.

## Map

| Doc | Role | Touch frequency |
|---|---|---|
| [STATE.md](STATE.md) | Live progress tracker — the resumption anchor | Every session |
| [ROADMAP.md](ROADMAP.md) | Vision + measurable per-persona success + the v0.2→v0.6 phasing. The "where we are going" doc. | When planning / prioritizing |
| [MIGRATION.md](MIGRATION.md) | The commit spine: phases, ordered list, links to each commit doc | Read often; edit rarely |
| [V02_PLANNING_PROMPT.md](V02_PLANNING_PROMPT.md) | The brief that produced the v0.2+ roadmap (executed 2026-05-31 → ROADMAP.md + commits/v03–v06). Provenance. | Provenance |
| [commits/v01/](commits/v01/) | One doc per v0.1 commit (extraction). The execution units. | The daily driver |
| [commits/v02/](commits/v02/) | One doc per v0.2 commit (de-hardcoding) | Next to execute (from c04) |
| [commits/v025/](commits/v025/) | One doc per v0.2.5 commit (c16q–c16x, then the c16w close-out last): report packaging + exec one-pager + report-correctness (c16y single-source `aggregates.py` [G-26, zero-output] → c16v multi-capture per-frame normalization [G-29]) + a server-side component system (c16x, ADR-42, added after the spine — stop brute-forcing per-page CSS). A code-review of c16v produced a sequenced review-fix roadmap (G-26-first; then v0.3 quality C3–C6 + a designer-tooling epic C7–C10) — in the approved plan file. Continues the c16 report-epic letters (c17–c19 are shipped v0.1; no free integers before c20). See [v025_packaging_and_onepager_proposal.md](v025_packaging_and_onepager_proposal.md) + DECISIONS ADR-39/40/41/42. | After v0.2, before v0.3 |
| [commits/v026/](commits/v026/) | The v0.2.6 **visual redesign** epic (anchor: shadcn/ui; ADR-43). **v0.2.5 is NOT released** — c16q–c16x is invisible plumbing, so 0.2.6 is the next PyPI release and carries the foundation + the redesign (`_version` 0.2.0 → 0.2.6). Direction brief: [v026_visual_redesign_brief.md](commits/v026/v026_visual_redesign_brief.md). Implementation is planned in a fresh chat. | Next (after the c16x foundation) |
| [commits/v03/](commits/v03/) … [v06/](commits/v06/) | One doc per v0.3–v0.6 commit (c20–c39): CI/automation → engine+ergonomics → Vulkan adapter epic → cross-platform+plugins | After v0.2.6 |
| [ARCHITECTURE.md](ARCHITECTURE.md) | **Frozen** contract: tool identity, package layout, pyproject, CLI surface, tool discovery, config, portability | Reference; change = ADR |
| [DECISIONS.md](DECISIONS.md) | **Frozen** rationale: versioning, backwards-compat, risks, and the review ADRs | Reference; append-only |
| [BOOTSTRAP.md](BOOTSTRAP.md) | One-time repo setup, `.gitignore`, source-project cleanup | Once, then history |
| [reference/FINDINGS.md](reference/FINDINGS.md) | Code-review findings (R/Q/D/S/C/M/G). Ticked as resolved. | Burndown |
| [reference/HARDCODE.md](reference/HARDCODE.md) | Hardcode/inflexibility catalog (H-*). Mostly v0.2. | Burndown |
| [reference/QUALITY_GATES.md](reference/QUALITY_GATES.md) | Testing strategy, golden-parity, schema/drift/determinism gates, CI matrix, pre-merge checklist | Reference each PR |
| [reference/DESIGNER.md](reference/DESIGNER.md) | Designer-tooling track (v0.2) | Reference (v0.2) |
| [adr36_spa_architecture_proposal.md](adr36_spa_architecture_proposal.md) | The SPA proposal (ADR-36) — **SUPERSEDED by ADR-37** on a lifespan review (bespoke SPA = a web-framework maintenance tax; weakens golden-as-correctness; loses JS-optional; hurts plugins/cross-platform). Kept for the decision trail. **The live direction (ADR-37):** reports stay static; decouple only the heavy data ([c16j](commits/v02/c16j_data_decoupling.md)); readability ([c16i](commits/v02/c16i_catalog_drill_readability.md)); durable data contract = c20/c30. | Provenance (superseded) |
| [report_roadmap.md](report_roadmap.md) · [readability_and_presentation_review.md](readability_and_presentation_review.md) · [overall_overhaul_proposal.md](overall_overhaul_proposal.md) | The three design reviews (2026-06-02) that led to ADR-36/37 + c16i/c16j. | Provenance |
| [CLI_PLAN.archive.md](CLI_PLAN.archive.md) | **SUPERSEDED.** The original monolith this set was carved from. Provenance only — do not edit, do not execute from it. | Never |

## Conventions

- **Commits are `cNN`** — numbers are fixed from the original migration plan and never renumbered.
  v0.1 deliberately skips `c04`–`c10` (those are v0.2); the gaps are intentional.
- **No line numbers** anywhere — they rot. Anchor to module + symbol name (e.g.
  `derive_post_merge._classify_draw`).
- **ID ownership** — each catalog owns its IDs: `R-/Q-/D-/S-/C-/M-/G-*` live in FINDINGS, `H-*` in
  HARDCODE. Every P0/P1 row carries `resolved-by: cNN` so the catalogs double as the burndown.
- **Frozen vs living** — ARCHITECTURE and DECISIONS are frozen; change them only by appending a new
  ADR to DECISIONS.md. STATE, MIGRATION, commit docs, and reference catalogs are living.

## Scope at a glance

- **v0.1 = pure extraction.** Package + CLI + tests + CI + release. Output byte-identical to today.
  Package named `bobframes` from the scaffold (c14 rename collapsed — [DECISIONS](DECISIONS.md) ADR-7).
  Keeps the hardcoded Arm tool path (ADR-2).
- **v0.2 = de-hardcoding.** Config layer, engine-agnostic classifier, design tokens, registry
  consolidation, env-var rename, report polish, designer track. **Unblocks v0.3+.**
- **v0.3+ = breadth + audience** (see [ROADMAP.md](ROADMAP.md)). v0.3 CI/automation (`--json`, gating,
  verify/diff/export, isolated stages) → v0.4 engine breadth + ergonomics → v0.5 Vulkan adapter epic
  (first post-v0.1 `SCHEMA_VERSION` bump 3→4 at c35) → v0.6 cross-platform + plugins. Commit numbers
  c20–c39; ADR-14..22 record the frozen-doc divergences.
