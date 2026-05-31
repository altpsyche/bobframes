# BobFrames — decisions & rationale (FROZEN, append-only)

> The "why" record. Append new ADRs; do not rewrite existing ones. Carved from CLI_PLAN §8
> (versioning), §10 (backwards-compat), §15 (risks), §22 (review addendum). Review-driven decisions
> are captured as ADR-1…ADR-6 at the bottom.

## Versioning (§8)

- **SemVer 2.0:**
  - PATCH: bug fix; no CLI flag change, no output change.
  - MINOR: new verb, new optional flag, new optional column in non-frozen output.
  - MAJOR: breaking CLI rename, output layout change, dropped Python version, schema bump.
- **`SCHEMA_VERSION`** lives in `bobframes.schemas`, separate int. Any `SCHEMA_VERSION` bump forces a
  `bobframes` MAJOR (pre-1.0 exception: forces MINOR; note in CHANGELOG).
- **`bobframes version`** prints both: `bobframes 0.1.0  schema 3  pyarrow 17.0.0`.
- **Manifest compatibility** (`_manifest.json.schema_version`): `render`/`catalog`/`ab` refuse to
  operate when `manifest.schema_version != schemas.SCHEMA_VERSION` → exit 1; fix is
  `bobframes ingest --force`. `ingest --force` blows away and rebuilds.
- **Deprecation cadence:** a rename/removal lives one MINOR with `DeprecationWarning`, gone in next
  MINOR (0.x) or next MAJOR (1.0+).

## Backwards-compat (§10)

**Decision: hard rename, no shim.** (User-selected.)
- The project-embedded `_analysis/` is deleted after the repo is bootstrapped (BOOTSTRAP.md
  source-cleanup). `python -m _analysis.run` → `ModuleNotFoundError` after install. Users switch to
  `bobframes ingest`.
- README "Migrating from `_analysis`" section maps old→new commands:
  ```
  python -m _analysis.run --root . --area X --label Y      → bobframes ingest . --area X --label Y
  python -m _analysis.reports.ab --root . --baseline-label X --compare-label Y
                                                            → bobframes ab . --baseline-label X --compare-label Y
  python -m _analysis.lint <file>                          → bobframes lint <file>
  python -m _analysis.tests.smoke                          → bobframes smoke
  ```

## Risks & mitigations (§15)

| Risk | Mitigation |
|---|---|
| `bobframes` name taken on PyPI | Verify before c19; fall back to `bob-frames`/`bobframescope`. |
| Replay schema duplication drifts from `schemas.py` | parquetize verifies headers vs `expected_columns()`; c13 CI test diffs literals. Document policy in `replay_main.py`. |
| `importlib.resources` breaks under zipped wheels | Hatchling produces non-zip wheels; `replay_script_path()` uses `as_file()` (extracts to temp if zipped). See c12. |
| `pyarrow` major breaks column writes | Pin `pyarrow>=17,<22`. CI tests low + high of range. Bump per release. |
| qrenderdoc subprocess hangs (Windows handle inheritance) | Already mitigated: writes to file handle, not PIPE. Keep unchanged. Plus c03 process-tree kill on timeout. |
| Old `python -m _analysis.run` invocations fail | Hard error after migration; README "Migrating" map. User chose this tradeoff. |
| Atomic-rename commit (c14) bisects badly | Single commit, no half-state. Reviewer checks: all `_analysis` imports gone, dir gone, `pyproject.toml` present, `bobframes check` runs. |
| Non-Windows install from PyPI | `bobframes check` exits 3 with Windows-only message; classifier limits visibility. |

---

## Review ADRs (from CLI_PLAN §22 — decided during plan review)

### ADR-1 — v0.1 is pure extraction; de-hardcoding deferred to v0.2
**Context:** the original plan folded all P0/P1 de-hardcoding (config layer, engine classifier,
design tokens, registry consolidation) plus the designer track into v0.1, growing the timeline to
~21 days with the classifier as a 2-day "most invasive" commit.
**Decision:** v0.1 ships extraction only — package, CLI, rename, tests, CI, release — output
byte-identical to today. De-hardcoding moves to v0.2, each commit still guarded by the golden parity
gate v0.1 establishes. **Consequence:** v0.1 keeps the hardcoded Arm 2026.2 tool path (see ADR-2).

### ADR-2 — v0.1 keeps the hardcoded Arm tool path
**Context:** the tool resolver (`config.resolve_tool` + glob version detection, H-7) is v0.2/c06.
**Decision:** v0.1 uses the existing inline discovery in `rdcmd.py`/`qrd_harness.py`. So v0.1
`bobframes` only runs where RenderDoc sits at the baked path — acceptable for the author's machine.
**Open option:** the glob fallback (H-7) is cheap; pull it forward into v0.1 if portability is
needed sooner. Tracked as H-7 in [HARDCODE.md](reference/HARDCODE.md).

### ADR-3 — `catalog` row-count "fix" R-9 is WITHDRAWN (false positive)
**Context:** the review claimed `catalog._per_capture_row_counts` undercounts (`+= 1` should be
`+= t.num_rows`). **Decision:** verified against code — `caps = t.column('capture').to_pylist()`
yields one entry **per row**, so `for c in caps: result[c][table] += 1` already sums the correct
per-capture row count. `+= t.num_rows` would assign the whole table's count to every row →
over-count. **No change; existing code is correct.** Do not "fix" this.

### ADR-4 — R-4 timeout handling is process-**tree** teardown, not a bare kill
**Context:** the review claimed qrenderdoc isn't killed on timeout. **Decision:**
`subprocess.run(timeout=)` already kills the *direct* child before raising `TimeoutExpired`. The real
Windows risk is qrenderdoc's GPU/replay **grandchildren**, which `run()` does not reap and which
hold file locks for the next run. c03 reaps the **process tree** (`taskkill /T /F /PID` or a Win32
job object with `JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE`) — not a bare `proc.kill()`.

### ADR-5 — the replay-drift CI test (c13) must assert a minimum match count
**Context:** the originally-drafted §21.3 test grepped a `_COLS_` prefix; the real variables are
suffix form (`DRAWS_COLS`, …), so it matched zero and passed vacuously — leaving H-6 unguarded. Also
`name.lower()` does not map to schema stems for abbreviated names. **Decision:** c13 matches the
`*_COLS` suffix, uses an explicit alias map for the abbreviated names (`RT_COLS`→`render_targets`,
`RT_TIMELINE_COLS`→`rt_event_timeline`, `STATE_CHANGE_COLS`→`state_change_events`,
`COUNTERS_COLS`→`counters_per_event`), skips the shared `ID_COLS` base, and **asserts ≥21 tables
found** so a future rename can't silently re-disable the guard. Cheaper alternative on the table:
rename the replay vars to match stems exactly so the alias map disappears.

### ADR-6 — supporting decisions (CI gap, py3.14, synthetic data, TOML parity)
- **CI cannot exercise the ingest path in v0.1** (no GPU/RenderDoc on `windows-latest`). The c03
  hardening (atomic writes, tree-kill, replay-skip) gets a **mocked-subprocess** unit test so it is
  not shipped wholly untested; full ingest smoke is self-hosted/nightly (v0.2).
- **Python 3.14 dropped from v0.1** — no pyarrow 17 cp314 wheels. Re-add when a compatible floor
  exists (ARCHITECTURE §3 caveat).
- **Synthetic golden data is derived from a real anonymized ingest**, not hand-authored, so coverage
  mirrors production (every draw-class bucket + pass-strip rule exercised). See QUALITY_GATES.
- **TOML round-trip is the riskiest parity surface** for v0.2/c07+c09: float reformatting (`2.0`) and
  regex escaping (`"\\s"`) must stay byte-identical. c07/c09 add a parity assertion that the
  config-loaded regex `.pattern` and weight formatting are unchanged.

### ADR-7 — package named `bobframes` from the scaffold; c14 rename collapsed
**Context:** at repo scaffold (2026-05-30, before `git init`) the user chose to name the package
`bobframes` directly rather than copy it in as `_analysis` and rename later. The original c14 rename
existed to preserve git history of an in-tree move; pre-git there is no history to preserve.
**Decision:** the package is `bobframes` from c01. All imports, the `-m bobframes.parsers.parse_init_state`
subprocess literal, `prog=` strings, and `[project.scripts] bobframes = "bobframes.cli:main"` are
written with the final name from the start. **c14 is collapsed** (marked superseded; file kept so
links resolve). **Consequences:** (1) STATE.md and MIGRATION.md drop c14; (2) c11 wires
`bobframes.cli` directly (no `_analysis.cli` interim); (3) c15 depends on c13 instead of c14; (4) the
source robocopy (BOOTSTRAP step 2) copies the capture-project `_analysis/` tree **into `bobframes/`**.
The hard-break for the *old embedded* `python -m _analysis.run` (backwards-compat ADR above) is
unaffected — that concerns the capture-project copy, which is still deleted at source-cleanup.

### ADR-8 — the repo stays data-free; tests run against the external capture folder
**Context:** the `bobframes` repo in `c:\Users\vsiva\dev\` is the **pure tool**. The user does not
want it polluted with real captures, `.rdc`, or `_data`. The capture project
(`c:\Users\vsiva\Downloads\RDC mainline r110565 25-05-2026\`) holds real `_data/`, XML, and `.rdc`
and is the sanctioned **test data source**.
**Decision:**
- The repo commits **no real captures / `_data` / `.rdc`**. `.gitignore` already enforces this
  (`**/_data/`, `*.rdc`, `*.parquet`, `*.zip.xml`, `_manifest.json`, …).
- Local dev / smoke / golden generation point at the external capture folder via
  `bobframes --root "<capture>"` / `bobframes smoke --data "<capture>"`. `.venv/` lives in the repo
  but is gitignored.
**Open (resolve at c02):** CI has no access to the external folder, so golden-parity needs *some*
committed fixture. Two options — (a) a **tiny anonymized synthetic** `_data/` (~500KB) committed as a
test fixture (the gitignore `!…/synthetic/` exception already allows it; this is test code, not user
data, so arguably consistent with "pure tool"); or (b) **no fixture** — parity/golden run locally
only against the capture folder, and CI runs unit tests + lint only. Default leaning: (a), pending
user confirmation. This supersedes the "synthetic" framing in [QUALITY_GATES](reference/QUALITY_GATES.md)
§21.1 and ADR-6's "derive from real ingest" only insofar as *whether* to commit it.

### ADR-9 — the replay-drift guard's count + equality are corrected against the real code (c13)
**Context:** ADR-5 / [QUALITY_GATES §21.3](reference/QUALITY_GATES.md) specify the c13 drift test as
`cols == schemas.expected_columns(stem)` for every replay `*_COLS`, plus `assert len(tables) >= 21`.
Implementing c13 and checking against the actual `replay/replay_main.py` (read-only `ast` extraction)
found the literal spec **cannot be green**:
- **Count is 20, not 21.** `replay_main.py` defines 20 `*_COLS` table tuples (excl. `ID_COLS`).
  `assert >= 21` fails on the spot. (ADR-5 itself estimated "~21"; the c13 doc's "Done when" already
  hedges to "~21".)
- **Three tables legitimately differ from `schemas.py`.** `events`, `draws`, `passes` omit exactly
  four columns that `derive_post_merge.py` (see its module docstring) computes **host-side, after
  replay**: `events.parent_marker_path_norm`; `draws.parent_pass_path_norm`, `draws.draw_class`;
  `passes.marker_path_norm`. Replay emits raw extraction; the host adds the normalized-path +
  classification columns before the final Parquet. The other 17 tables match byte-for-byte.

**Decision (Option A — pinned-derived allowlist; user-confirmed):** c13 compares each replay
`*_COLS` against its schema tuple **minus a pinned set of host-derived columns** (`_DERIVED_COLS`
in `tests/test_replay_drift.py`) and asserts `len(tables) >= 20`. This keeps the full guard intent of
ADR-5 — it still fails on any raw-column add/remove/reorder **and** on any *new, unpinned*
schema-only column (forcing a deliberate update), while staying green today. The test also asserts
every pinned derived column genuinely exists in its schema tuple, so the allowlist can't mask a typo
or a real raw column. **Consequence:** this is a correction to ADR-5's exact-equality framing and its
`>=21` count, recorded by append (DECISIONS is frozen). The cheaper "rename replay vars to match
stems" alternative from ADR-5 is orthogonal — it would remove the alias map but not the derived-column
difference — and is not taken.

### ADR-10 — the bundled-fixture wheel `force-include` is dropped (it duplicated entries)
**Context:** [ARCHITECTURE §3](ARCHITECTURE.md)'s `pyproject.toml` template lists two wheel
force-includes — `bobframes/replay/replay_main.py` and `bobframes/tests/data`. Building the wheel
during c17's publish dry-validation emitted ~65 `Duplicate name:` warnings, all under
`bobframes/tests/data/**`. Inspection of the built wheel (130 logical files, 195 zip entries)
confirmed every fixture file appeared twice. Root cause: the `.gitignore` negation
(`!bobframes/tests/data/**`, added at c02 to track the synthetic `_data` + golden HTML, ADR-8) makes
those files **tracked**, so hatchling's default `packages = ["bobframes"]` selection already ships
them; the `tests/data` force-include then added a second copy. `replay_main.py` (a tracked `.py`
under the package) is likewise shipped by `packages`, but its single-file force-include produced **no**
duplicate.
**Decision:** remove the `"bobframes/tests/data" = "bobframes/tests/data"` force-include line; keep
the `replay_main.py` force-include (no duplicate, and §3 justifies it as a guarantee that
`importlib.resources` always resolves a real on-disk path). Verified post-fix: the wheel has 130
entries / 130 unique / **0 duplicates**, still containing `replay_main.py`, all 54 synthetic
Parquet, both manifests, and all 9 golden HTML; `twine check` passes. **Consequence:** the real
`pyproject.toml` diverges from the §3 snapshot by one removed line; §3 is annotated with a pointer to
this ADR rather than rewritten (frozen, append-only).

### ADR-11 — golden byte-parity is pinned to one canonical env; the matrix runs functional gates
**Context:** c17's CI matrix (windows × py{3.10,3.12,3.13} × pyarrow{17,21}) went red on the first
push. Root-caused by reproducing each cell locally under `uv` (read-only): the rendered golden HTML
is **not** byte-identical across the matrix because it embeds environment-variable bytes —
(A) the per-drop drill page prints each Parquet's **on-disk KB**, which differs by pyarrow writer
version (render-only rewrites the derived Parquet with the local pyarrow; pa17 `15.1 KB` vs pa21
`12.3 KB`); and (B) a computed `pass_gpu` bar-width `pct_share` flips `0.62% -> 0.63%` on py3.10 — a
one-ULP difference in a float aggregate (numpy build bundled per-python) landing on the `.2f`
rounding boundary. Each cell diverges in exactly one file; the functional gates (unit, schema,
replay-drift, **determinism** — which renders twice in the *same* env, so it is stable — perf,
hardening, smoke, lint) pass on every cell.
**Decision:** run **`test_parity` only on the canonical cell** (py3.12 + pyarrow 21, where the golden
is baked); every other gate runs on every matrix cell. Rationale: byte-snapshot equality across
differing numpy/pyarrow builds is not a deliverable promise, whereas the snapshot's real job —
catching render-**logic** regressions — is fully served by running it each push on one fixed env.
The matrix proves install/import/functional compatibility across the version range; it does not
promise byte-identical bytes across builds. **Consequence:** ci.yml splits the pytest step
(`--ignore=test_parity.py` everywhere + a canonical-only `test_parity.py` step). If the canonical
env's pyarrow floor is bumped, re-bake the golden. This refines [QUALITY_GATES §21.6](reference/QUALITY_GATES.md),
which had listed parity in the matrix.

### ADR-12 — package URLs repointed to github.com/altpsyche/bobframes
**Context:** [ARCHITECTURE §3](ARCHITECTURE.md) froze `[project.urls]` (Homepage/Issues/Changelog) at
`github.com/mayhem-studios/bobframes`, and the CHANGELOG link refs matched. At release prep the actual
git remote is `github.com/altpsyche/bobframes`; CI and the v0.1.0 publish happen there. Publishing as
frozen would give the PyPI page Homepage/Issues/Changelog links that 404. **Decision (user-confirmed):**
repoint the three `pyproject.toml` `[project.urls]` and the two CHANGELOG link-reference URLs to
`altpsyche/bobframes`. The author email (`@mayhem-studios.com`) is unchanged — it is the real contact,
not a repo URL. **Consequence:** `pyproject.toml` + `CHANGELOG.md` diverge from the §3 snapshot; §3 is
annotated with a pointer to this ADR rather than rewritten (frozen, append-only). If the project later
moves to a mayhem-studios org repo, repoint again.

### ADR-13 — PyPI publish uses Trusted Publishing (OIDC), not an API token
**Context:** c17/c19 + [QUALITY_GATES §21.6](reference/QUALITY_GATES.md) specified API-token auth
(`PYPI_API_TOKEN` GH secret + `twine upload`). At release setup this is awkward: a **project-scoped**
token cannot be created before `bobframes` exists on PyPI (chicken-and-egg), and an **account-wide**
token is over-privileged and a standing secret to rotate. **Decision (user-confirmed):** use PyPI
**Trusted Publishing** (OIDC) via a **pending publisher** — no token, no GH secret. A pending publisher
is registered on PyPI before first publish (Owner `altpsyche`, Repository `bobframes`, Workflow
`ci.yml`, no environment). The `publish` job changes: `runs-on: ubuntu-latest` (the
`pypa/gh-action-pypi-publish` OIDC action is Linux-only, and the wheel is `py3-none-any` so the build
host is irrelevant), `permissions: id-token: write` (+ `contents: write` for the GH Release), and the
`twine upload` step is replaced by `pypa/gh-action-pypi-publish@release/v1`. **Consequence:** no
`PYPI_API_TOKEN` secret is created or referenced; supersedes the token mention in c17/c19 and §21.6.
On first successful publish PyPI converts the pending publisher into a normal trusted publisher.

---

## v0.2+ roadmap ADRs (from the 2026-05-31 planning session — [ROADMAP.md](ROADMAP.md))

> Decided with the user before locking the v0.5 graphics-API epic and the v0.6 cross-platform epic.
> See [ROADMAP.md](ROADMAP.md) for phasing and the per-commit docs under `commits/v03..v06/`.

### ADR-14 — multi-API schema is a unified core + per-API extension tables
**Context:** v0.5 adds a second graphics API (Vulkan). The schema can either widen the existing tables
per-API, give each API its own full table set, or keep shared columns in the core tables and isolate
API-specific data in small optional extension tables. The frozen contract is `SCHEMA_VERSION=3` +
`ID_COLS=(area,drop_date,drop_label,capture)` (H-29), and the hard rule is that GL Parquet stays
byte-identical for identical `.rdc`. **Decision (user-confirmed):** **unified core + per-API extension
tables.** Shared columns stay in the core tables (GL output byte-identical); API-specific data lives in
small **optional, additive** extension tables (`frame_totals_gl`, `frame_totals_vk`, …) keyed by the
frozen `ID_COLS` (H-29 stays frozen as the join key). New API tables never edit GL output. The
mechanism (an `api` tag on `schemas.TABLES` entries) lands additively in c33 with **no** version
change; the single intentional `SCHEMA_VERSION` bump (3→4) is isolated to **c35**, which refreshes the
goldens and bumps bobframes MINOR (pre-1.0). **Consequence:** cross-API reports query the core tables
and left-join the extension tables; `parquetize`'s existing missing-column auto-fill means a GL capture
simply has no Vulkan extension rows. Rejected: per-API full table sets (duplicates common columns,
forces UNION/branch in every report).

### ADR-15 — the first added graphics API is Vulkan
**Context:** after the GL-adapter refactor (c32), the second API can be Vulkan or D3D12. **Decision
(user-confirmed):** **Vulkan first** — cross-vendor and aligned with the v0.6 cross-platform epic.
D3D12 is deferred and will later validate the adapter abstraction against a very different binding
model. **Consequence:** c34 ships `VulkanAdapter` + a Vulkan synthetic fixture + golden; the v0.6
cross-platform lane and Vulkan reinforce each other.

### ADR-16 — `--json` is a versioned contract from day one
**Context:** CI consumers need stable machine-readable output (G-9). **Decision (user-confirmed):**
`--json` emits a single JSON object to **stdout** (logs stay on **stderr**) carrying an independent
`json_schema_version` (≠ data `SCHEMA_VERSION`), introduced in c20 and required of every verb that
gains JSON. `json_schema_version` bumps only on a breaking JSON-shape change. **Consequence:** a
`tests/test_json_contract.py` pins the version + key set; `--json` is additive to stdout so it never
touches the HTML golden.

### ADR-17 — SQL `query` is an optional extra; the core stays pyarrow-only
**Context:** the "queryable Parquet" goal wants SQL, but the frozen dep invariant is **pyarrow only**;
a bundled engine would be a standing heavy dep. The user delegated the choice to "whatever is better
for tool lifespan." **Decision:** `schema` introspection ships in the **core** (pyarrow-only, always
available); SQL `query` is an **opt-in extra** — `pip install bobframes[query]` pulls DuckDB, and the
`query` verb lazy-imports it with a helpful install hint when absent. **Consequence:** the
pyarrow-only-core invariant is preserved; `pyproject.toml` gains
`[project.optional-dependencies] query = ["duckdb>=1.0"]` (ARCHITECTURE §3 annotated, not rewritten);
power users opt in. Best for lifespan: lean core, no forced heavy dep, full SQL available. Rejected:
bundling DuckDB in core (breaks pyarrow-only, grows every install); introspection-only (too weak).

### ADR-18 — cross-platform (Linux/macOS) lands v0.6, after the API epic
**Context:** ARCHITECTURE §12 freezes "Windows only in v1." Vulkan-first (ADR-15) mildly argues for
pulling Linux forward. **Decision (user-confirmed):** keep cross-platform at **v0.6** (c36) — land
Vulkan extraction on Windows first (v0.5), then port the tool locator (extends c06 `resolve_tool`) and
a platform-dispatched process-tree kill (`os.killpg`+`start_new_session` on POSIX; taskkill/job object
on Windows), and relax the `sys.platform!='win32'` gate in `_cmd_check`. **Consequence:** this
supersedes the ARCHITECTURE §12 "Windows only in v1" statement for v0.6+; §12 is annotated with a
pointer to this ADR (frozen, not rewritten). A per-OS nightly real-`.rdc` lane is added.

### ADR-19 — plugins are trusted-local-only (no sandbox)
**Context:** v0.6 wants user-supplied reports/derives/presets/API-adapters (M-1/M-2); the open question
is the security posture. **Decision (user-confirmed):** **trusted-local-only** — plugins are discovered
from a documented user dir / installed entry points and run in-process; the posture is documented as
"you run code you install." No sandbox, no signature verification. **Consequence:** c38 implements
auto-discovery (`pkgutil.iter_modules` + entry-point groups + a `build()` convention) and schema-table
registration (M-2); sandboxing/signing is deferred until demanded.

### ADR-20 — the public sample capture is a SHA256-pinned GitHub Release asset
**Context:** the <5-min onboarding goal needs a public sample capture / `_data`, but the repo stays
data-free (ADR-8). **Decision (user-confirmed):** host an anonymized sample as a **SHA256-pinned
GitHub Release asset**, versioned with the tool; docs (and an optional fetch helper) pull it.
**Consequence:** the repo gains no captures; the sample is referenced by release URL + SHA256. Rejected:
a separate companion repo (extra maintenance) and committing the sample (violates ADR-8).

### ADR-21 — engine presets are generic-first; each new engine needs its own fixture + golden
**Context:** c09 ships the classifier-TOML mechanism + a UE preset. Adding engines needs a validation
strategy and an order. **Decision (user-confirmed):** **generic-first** — ship an honest "generic"
preset (depth-write/blend heuristics, no engine keywords) that needs no external capture and unblocks
every non-UE user immediately (c27). Unity/Godot presets land when a real `.rdc` from that engine
exists to anonymize. Each new engine preset requires its **own synthetic fixture + golden**, gated
behind a real-`.rdc` smoke from that engine. **Consequence:** breadth ≥2 engines (UE + generic) is met
in v0.4 without waiting on third-party captures; per-engine goldens grow the parity surface one engine
at a time.

### ADR-22 — per-API / per-engine golden parity grows one fixture at a time
**Context:** ADR-11 pins byte-parity to one canonical cell for the single GL fixture. Multi-API
(ADR-14/15) and multi-engine (ADR-21) each add fixtures. **Decision:** **each new API and each new
engine gets its own synthetic fixture + golden**, anonymized/down-sampled from a real ingest
(ADR-6/ADR-8) and baked on the canonical cell py3.12+pa21 (ADR-11). The byte-parity gate runs each new
golden on the canonical cell; functional gates run the full matrix. **Consequence:** this refines
QUALITY_GATES §21 — the golden set is `{golden (GL/UE), golden-vk, golden-generic, …}`; every
output-changing commit refreshes the affected golden(s) in-PR.
