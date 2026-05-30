# CLAUDE.md router snippet

At repo bootstrap (BOOTSTRAP.md), paste the block below into the repo-root `CLAUDE.md` so every
fresh session is oriented automatically. Keep it short — it only routes; the detail lives in the
plan docs.

---

```markdown
## How to work in this repo (plan-driven)

This repo is **bobframes** — a RenderDoc capture pipeline extracted from a project-embedded
`_analysis/` package. Implementation runs commit-by-commit across many sessions.

**ALWAYS start by reading `docs/plan/STATE.md`.** It names the `active_release` and the `current`
commit.

1. Open `docs/plan/commits/<active_release>/<current>.md` and do **exactly that one commit**.
2. Stop when its **"Done when"** gate is green (run the verify command(s) listed there).
3. Before ending the session, update `docs/plan/STATE.md`: set the commit's status, advance
   `current` if finished, and rewrite `last_session` + `next_action`. Append a one-line session-log
   entry.

- `docs/plan/INDEX.md` is the map of all plan docs.
- `docs/plan/ARCHITECTURE.md` and `docs/plan/DECISIONS.md` are **frozen** — do not change them
  except by appending a new ADR to DECISIONS.md.
- Findings burndown lives in `docs/plan/reference/FINDINGS.md` (`R-/Q-/D-/G-*`) and
  `HARDCODE.md` (`H-*`); tick a row's `resolved-by` when its commit lands.
- Every change must keep the golden-snapshot parity gate green — see
  `docs/plan/reference/QUALITY_GATES.md`. Output is byte-identical unless a commit explicitly
  refreshes the golden.
- Do not work from `docs/plan/CLI_PLAN.archive.md` — it is the superseded source, kept for
  provenance only.
```
