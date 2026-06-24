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

### ADR-23 — no patch-fixes: root-cause or record, never narrow the gate to go green
**Context:** a lifecycle audit (2026-06-01) asked whether fixes across v0.1/v0.2 were thought-through
or "green-chasing." The trail was mostly principled, but it surfaced cases where a gate was *scoped
down* to pass rather than the underlying wart removed (ADR-11 pins parity to one env because the
rendered HTML embeds env-sensitive bytes; the golden gate covers HTML only, so a Parquet row-order
change slipped through at c05; a test picked version numbers that dodged a lexicographic-sort flaw).
The user set a standing rule. **Decision (user-confirmed):** **never patch-fix.** Concretely, the
following are banned as a way to reach green: masking or narrowing a test/gate's scope to hide a real
divergence; choosing fixture/test data that sidesteps a known flaw; catching-and-swallowing to silence
a symptom; shipping known-weak code with a vague "fix later." The required response to a failure is to
**root-cause it and fix the cause**, OR — when the true fix is genuinely out of the current commit's
scope — **record it explicitly** as a `FINDINGS`/`HARDCODE` row (symbol-anchored) **and** an ADR
stating the deliberate scoping and its rationale, so the limitation is visible and owned, not silent.
A documented, rationalized scoping decision (e.g. ADR-11's "byte-snapshot equality across numpy/pyarrow
builds is not a deliverable") is legitimate **because** it is explicit; an undocumented one is the
thing this ADR forbids. **Consequence:** every commit's "Done when" gate must pass on its real intent,
not a narrowed proxy. New gate-coverage and root-cause findings opened by the audit: D-8, D-9, G-14.
This rule is mirrored as a one-line principle in the repo `CLAUDE.md` ("How to work").

### ADR-24 — Arm version pick uses a natural-numeric sort, not literal lexicographic (refines §5)
**Context:** [ARCHITECTURE §5](ARCHITECTURE.md) / [c06](commits/v02/c06_tool_resolver.md) say the
glob over `Arm Performance Studio *` picks the latest "by directory-name sort." A literal
lexicographic sort mis-ranks once a minor version reaches two digits (`'2026.2' > '2026.10'` as
strings), which would silently select an older install. Arm's real naming has kept minors single-digit
so the literal form happens to work today, but relying on that is exactly the kind of undocumented
fragility ADR-23 forbids. **Decision:** implement the "latest install" *intent* with a natural-numeric
key (`config._version_key`: split digit runs to ints) so `2026.10` correctly outranks `2026.2`,
regardless of minor width. **Consequence:** §5's "directory-name sort" wording is realized as a
numeric-aware sort (same intent, robust); `test_config.test_arm_glob_picks_latest_version` asserts the
two-digit-minor case. Frozen §5 is refined by this ADR, not rewritten.


### ADR-25 — config = bundled-default base, deep-merged with the first-found user file
**Context:** [ARCHITECTURE §6](ARCHITECTURE.md) says the config lookup ($BOBFRAMES_CONFIG >
`<root>/.bobframes.toml` > `%APPDATA%/bobframes/config.toml`) is "first found wins, no merging,"
and shows a sparse user file. Taken literally, "no merging" would mean a user file fully *replaces*
the defaults, so overriding one timeout would silently drop every other default (the de-hardcoded
weights, regex, banlist). That is hostile UX and brittle as defaults evolve. **Decision (c07):** the
bundled `bobframes/_default_config.toml` (+ `lint_banlist.toml`) is the single source of truth and is
always the base; the **first-found user file is deep-merged ON TOP** (per-section, per-key; user
wins). §6's "no merging" governs **user-file selection** — pick exactly one of the three locations,
do not merge the three — *not* the default base. So a user sets only what they want to change and
inherits improved defaults for everything else. **Consequence:** `check --write-config` writes a
small *commented* starter (not a full dump) so users don't pin every internal default;
`test_user_file_deep_merge` locks the behavior. §6 is annotated with this ADR (frozen, append-only).

### ADR-26 — config layer adds a conditional `tomli` backport; the Python floor stays 3.10
**Context:** c07 loads config with stdlib `tomllib`, which exists only on Python 3.11+. The obvious
shortcut — bump `requires-python` to `>=3.11` — was considered and **rejected on evidence**: the
replay stage runs inside qrenderdoc's *embedded* Python 3.10 (`replay_main.py` documents it;
confirmed on the dev box: `Arm Performance Studio 2026.2/renderdoc_for_arm_gpus/python310.dll` +
`python310.zip`), and [c09](commits/v02/c09_classifier.md) plans to share a TOML-loading classifier
into that replay side (D-6 collapse), where a missing `tomllib` would crash. The `>=3.10` floor in
[ARCHITECTURE §1](ARCHITECTURE.md) exists precisely for that embedded interpreter. **Decision:** keep
`requires-python = ">=3.10,<3.15"`; add `tomli>=2.0; python_version<'3.11'` to dependencies + a 3-line
import shim (`try: import tomllib except ModuleNotFoundError: import tomli as tomllib`). `tomli` is the
upstream of `tomllib` (pure-Python, conditional, zero weight on 3.11+); the data path stays
pyarrow-only. **Consequence:** the CI matrix keeps its 3.10 cell, so the loader is exercised under
`tomli` (3.10) *and* `tomllib` (3.12/3.13) and the digest gates prove them equivalent (verified
locally: identical loaded values under py3.10/tomli). ARCHITECTURE §3 is annotated with this ADR
(frozen, append-only); §1's floor is unchanged.

### ADR-27 — design tokens move to TOML by a value-only Template skeleton (no golden refresh)
**Context:** c08 (H-15) extracts the `chrome` design-token VALUES to a designer-editable
`reports/design_tokens.toml`. The blocking constraint: `html/template.py` embeds the token block
**un-minified** (`<style>{design_tokens_css()}…`) on the drill + root pages, while `chrome.page_open`
embeds the **minified** form on the report pages — so the hand-aligned `:root` bytes (per-group
eyeballed column alignment; 1/2/3-space gaps inside `light-dark(a,  b)` to align the dark-mode oklch)
are baked into the golden. That alignment is not algorithmically reconstructible from key/value pairs.
Two paths were weighed: (A) emit a canonical token block and accept a whitespace-only golden refresh
of the un-minified pages; (B) keep the alignment skeleton in `chrome.py` with `string.Template` `$key`
placeholders and source only the VALUES from TOML. **Decision:** take (B). The skeleton
(`_DESIGN_TOKENS_TMPL` / `_CHROME_CSS_TMPL` / `_STICKY_CSS_TMPL`) owns the CSS var NAMES + layout, the
TOML owns the values; `Template.substitute` reinserts each value verbatim, so the emitted CSS is
byte-identical and **no golden is refreshed** (the c08 "Done when" gate). CSS uses no `$`, so only our
placeholders match (verified). The token loader (`reports/_tokens.py`) is a SEPARATE concern from the
c07 config: bundled-only, **no user-file / deep-merge layer** in v0.2 — DESIGNER Track A's documented
workflow edits the packaged file directly; per-project token overrides are explicitly Track B. H-20
(layout literals) rides the same mechanism; the bundled defaults reproducing today's bytes is pinned
by `tests/test_design_tokens.py` (independent of the full-page golden) and ADR-6. ARCHITECTURE §3 is
annotated with this ADR (frozen, append-only). **Scoping (ADR-23, recorded not hidden):** H-20 covers
the base report layout tokens; the responsive `@container` / `@media print` grid overrides and
incidental component widths (copy-button 28/22px, search 280px, catalog-grid 200px, print A4/12mm)
stay inline as breakpoint/print constants — they are not designer-tunable base tokens. Noted on the
HARDCODE H-20 row.

### ADR-28 — token CSS var names are preserved; the `--color-*` section-prefixed rename is deferred
**Context:** [DESIGNER.md](reference/DESIGNER.md) illustrates a "1:1 section-prefixed" naming
(`color.accent_primary` → `--color-accent-primary`). The current emitted vars are NOT prefixed
(`--accent-primary`, `--sp-1`, `--c-opaque`, `--bg`, …) and follow no single per-section convention
(spacing is `--sp-*`, type is `--fs-*`, color has no shared prefix). Adopting the prefixed scheme
would rename every var + every `var(--…)` reference across all CSS, changing the emitted bytes on all
9 golden pages — directly contradicting c08's "byte-identical, golden green, no refresh" gate.
**Decision (user-confirmed):** preserve the exact current var names in c08; the TOML `[color]` /
`[spacing]` / … sections are organizational only (the var name is fixed by the skeleton). The
cosmetic rename, if ever wanted, is a separate future commit that intentionally refreshes the golden.
Recorded here so the DESIGNER.md illustration is understood as superseded for v0.2, not silently
ignored (ADR-23).

### ADR-29 — the classifier is an analysis-layer, single-source, state-capable rule engine; the dead replay copy is deleted
**Context:** [c09](commits/v02/c09_classifier.md) externalizes UE-specific draw classification
(H-1..H-5). [D-6](reference/FINDINGS.md) flagged `_classify_draw` as two drifted copies
(host `derive_post_merge` vs `replay_main`) and asked whether the replay copy is dead. A first design
would have pushed a shared classifier *into* qrenderdoc's embedded Python 3.10 (which can't import the
package or parse TOML) via a JSON-spec hand-off. **Investigation (recorded so the rejected path is
owned):** the replay copy feeds **only** `passes.draws_by_class_*` — 9 columns with **zero readers**,
superseded by the host-derived `pass_class_breakdown` table; and durable GPU tools (RenderDoc, AMD
RGP, Unity Frame Debugger) classify from **structured state / render passes / shader pass-tags**,
treating debug markers as *display grouping* only. **Decision (user-confirmed):**
1. Classification is an **analysis-layer, single-source** concern. One `derives/classifier.py` API
   (`classify(fields, spec)`) is the only `draw_class` computation site; `pass_class_breakdown`,
   `draws_by_class`, etc. *read* the derived column. Rules live in TOML presets
   (`draw_classifier.toml` = UE default; `presets/*.toml`).
2. The engine is a **state-capable predicate engine**: a rule matches if any marker predicate
   (`marker_contains`/`marker_suffix`) hits OR all `when` field conditions (over any draw column —
   blend/depth/…/color-write/RT) hold; first match wins; else `fallback_class`. Markers are a
   *refinement* layer, not the foundation — so a state-first "generic" preset (c27) needs no
   rearchitecting. The bundled UE preset reproduces the former host `_classify_draw` **byte-for-byte**
   (parity, ADR-6; `tests/test_classifier` runs a 300+ case oracle battery + the `draw_class` golden
   gates hold with no refresh).
3. **D-6 is collapsed by DELETING the dead replay copy**, not by feeding it: the replay stage now
   emits **facts only** (so QUALITY_GATES §21.9 "de-hardcoding does not change extraction" holds *by
   construction*). The 9 dead `passes.draws_by_class_*` columns stay **zeroed** (PASSES_COLS is frozen
   at SCHEMA_VERSION 3; the c13 drift gate stays green); full column removal + `passes`-table slim is
   deferred to the c35 bump (D-11). The synthetic fixture's committed `passes.draws_by_class_*` predate
   the deletion (replay is never run in render-only) — harmless because unread, recorded not hidden.
**Consequence:** `classifier.py` reuses the ADR-26 `tomllib`/`tomli` shim + `importlib.resources` so
it imports under embedded 3.10 (the walker is pure-Python, rules-as-data) even though replay no longer
calls it. Accuracy improvements (state-first generic preset, robust shadow-by-state, "fewer other")
are opt-in and deferred (D-10 → c27 / §21.5 / ADR-21). The frozen ARCHITECTURE §3/§4 is annotated by
pointer, not rewritten. Real-`.rdc` re-validation (replay still runs after the deletion) is the
self-hosted/nightly smoke (ADR-6; CI never runs replay, §21.6).

### ADR-30 — classifier preset layout: `draw_classifier.toml` is the canonical UE default; no duplicate `ue.toml`
**Context:** the c09 doc lists `presets/{ue,unity,godot,custom-template}.toml`. Shipping a separate
`presets/ue.toml` *and* the default `draw_classifier.toml` (both UE) would reintroduce a dual-edit
duplication — the exact hazard H-5 closes. **Decision (user-confirmed):** `draw_classifier.toml` IS
the canonical UE default; `[classifier] preset = "ue"` (the default) resolves to it. Ship
`presets/{unity,godot,custom-template}.toml` as alternates/examples; per ADR-21 the Unity/Godot
presets are **illustrative** (manual-check only — no per-engine fixture/golden until a real `.rdc`
from that engine exists to anonymize), and `custom-template.toml` is the documented starting point
(shows both marker and state-only predicates). **Consequence:** a literal `presets/ue.toml` is
deliberately NOT shipped; recorded here so the doc's file list is understood as satisfied by the
default file, not silently dropped (ADR-23).

### ADR-31 — `RDC_ROOT` is eliminated by threading `project_root` as the parse `cwd`, not by a `parse_init_state` CLI arg
**Context:** the c10 doc says "pass `--project-root` as an explicit CLI arg to `parse_init_state`"
to retire `RDC_ROOT` (R-5/Q-5). Investigation shows `parse_init_state.main(argv)` consumes **no**
project root: it takes 6 positional args and writes every output under the absolute `capture_stage`
(`xml_path`/`capture_stage` are both absolute via `discovery`/`paths.drop_stage_dir`). It is therefore
**cwd-independent** — the parse child's working directory cannot affect any output byte. `RDC_ROOT`
was only ever read in `_parse_one` as that child's `cwd`, and `_do_parse` always set it to
`project_root` before the pool ran (so the triple-`dirname` fallback was dead). **Decision
(user-confirmed, "cleaner for the long run"):** add `project_root` to `_parse_one`'s args tuple
(now a 7-tuple) and pass it directly as `subprocess.run(cwd=project_root)`; delete the global
`os.environ['RDC_ROOT']` set/restore. Do **not** add a `--project-root` flag to `parse_init_state` —
that would be dead surface (the ADR-23 anti-pattern). **Consequence:** completes R-5 (no global env
mutation that leaks across drops) and resolves Q-5 (positional args are canonical; the misleading
comment is fixed) with **zero** new child surface; byte-identical output (ADR-6), golden untouched.
The spec's "Files: pipeline, qrd_harness, replay_main" line is stale — the real touch is
`run.py` + `config.py` + `replay_main.py`; `qrd_harness` is unchanged (only the kept `RDC_INSIDE_ARGS`
wire). The `BOBFRAMES_PIXEL_GRID` / `BOBFRAMES_KEEP_STAGE` renames keep the one-release legacy `RDC_*`
fallback via the shared `config.getenv_legacy` helper (reusing the c06 one-shot deprecation machinery);
`RDC_INSIDE_ARGS` (three consumers: `qrd_harness`, `replay_main`, `probes/whatif`) is the
qrenderdoc↔harness wire protocol and is renamed nowhere.

### ADR-32 — report contract: every report leads with KPI strip + insight callout + provenance, over a de-hardcoded threshold set (c16)
**Context.** A review of the rendered golden found the reports were verbose monospace tables that
under-used a strong chrome library: `kpi_strip` called by 0/6 reports, `rdc-heatmap-cell` by 1,
`.device-strip` CSS unused, and no "so what" layer (G-15). **Decision.** A report's shared shape is now:
hero **KPI strip** (`report_page(kpis=...)`), one or more **insight callouts** (`chrome.callout(severity,
title, detail)` — `rdc-alarm-banner`-wrapped for warn/alarm so findings are announced), a header
**provenance/device strip** (`chrome.provenance_strip` over the newest drop's `host_info`/`tool_versions`,
the previously-unused `.device-strip`), and **heatmap shading** on ranked numeric columns
(`chrome.heatmap_cell` over the existing `rdc-heatmap-cell`). Severity thresholds are **de-hardcoded** to
`config [report]` (`ReportCfg`: `shader_complexity_high`, `overdraw_reject_{warn,alarm}_pct`,
`instancing_repeat_min`, `gpu_regression_pct`), tunable per project like the c07 layer. The provenance
strip deliberately **omits** `host_info['bobframes']` so a release bump never churns the golden, and is
shown in the header on **every** report (superseding the c16-doc's dashboard-only "footer" — same data,
better UX; it still appears on the dashboard, satisfying the Done-when). Friendly **empty-state** cards
(`chrome.empty_state`, icon + message) replace blank tables/`.note` on sparse data. **Consequence.**
Output-changing → the golden is refreshed in c16 (reviewed; the only drill/root deltas are the D-11b dead-CSS
removal + the shared `.callout`/`.empty-state` rules). Parquet parity holds (data untouched). Reaches ~8/10;
the chart-first restructure to 10/10 is c16b (ADR-33). This is additive to ADR-27 (the chrome CSS stays a
value-only Template skeleton; new rules use `var()` tokens, no `$`).

### ADR-33 — charts are deterministic server-side inline SVG, not a JS chart lib (c16b)
**Context.** Reaching a 10/10 presentation needs real visualizations (treemap/flame for GPU passes, donut
+ stacked bars for draw classes, scatter for shaders, trend lines), not just dressed-up tables — but the
golden-parity gate (ADR-6/11) requires byte-stable output, and the reports are offline static HTML with no
network. **Decision (user-chosen).** A new `reports/charts.py` generates **deterministic, dependency-free,
server-side inline SVG** (fixed-precision coords, no `random`/timestamps), themed entirely from design
tokens — extending the existing `delta.sparkline_svg` precedent. **No** vendored JS chart library and **no**
`<canvas>` (canvas pixels are not byte-stable → would force the parity gate to skip chart regions, the
ADR-11 trap we are paying down, not extending). Each chart is `role="img"` with `<title>`/`<desc>` and keeps
its detail **table directly below as the exact, accessible data fallback** (chart = at-a-glance, table =
source of truth). **Consequence.** Charts ride the normal golden byte-parity gate like the rest of the HTML;
they print (vector) and are reduced-motion-safe (static). This is the spine of [c16b](commits/v02/c16b_report_viz.md).

### ADR-34 — report visual language: depth over borders, tinted severity, and a VENDORED Inter subset (c16d)
**Context.** c16/c16b/c16c made the report info-design complete (G-15) but the design *language* read as
debug output: `1px solid var(--border-1)` wireframe outlines around every element, flat chart fills,
stark callout boxes, and a font stack that *named* `'Inter'` but never loaded it (so KPI numbers fell back
to whatever sans the viewer's OS had). c16d is the design-language pass (G-17). Two pieces are
frozen-decision-worthy. **Decision 1 (depth over borders).** Cards and chrome are differentiated by
**surface + a soft elevation shadow** (`--elev-1/2/3`, a new `[shadow]` token block emitted through the
ADR-27 value-only skeleton), not outlines; report tables become horizontal-rule only; severity is a faint
translucent **box tint** (`color-mix(in oklch, var(--status-*) ..%, var(--surface-1))`) instead of a stark
border + left rule; the sticky-h2 in-view cue moves from recolouring an h2 left-border to a `::before`
accent marker (the h2 left-accent is gone). Micro-interactions (hover `scale(var(--hover-scale))` + spring)
**no-op under `prefers-reduced-motion`** by construction (the reduced-motion `:root` sets `--hover-scale: 1`
and `--motion-spring: 0s`); print re-adds a thin paper border + kills shadows (a borderless+shadowless card
is invisible on white). **Decision 2 (vendored font — overrides the c16d-doc's original "do NOT load a web
font", user signoff 2026-06-02).** The dependency posture is re-opened: a **subset of the Inter variable
font** (Latin + tabular figures, `wght` 400-600, ~29 KB) is **vendored into the wheel**
(`reports/assets/inter-subset.woff2` + OFL licence) and **base64-inlined as an `@font-face` data URI** at
import. KPI/summary display numbers + headings render in Inter on every OS; data tables stay monospace
(dual stack). A *CDN / network* web-font remains forbidden — it would break the offline + byte-deterministic
report contract. The committed woff2 makes the inlined base64 byte-stable on any machine; `fonttools` is a
**dev-time only** subsetting tool (its output is committed, never run at build/runtime). **Consequence
(accepted contract change).** The wheel grows ~29 KB and each self-contained report HTML grows ~40 KB
(the inlined font); reports stay a single file that renders identically **offline** and remain
**byte-deterministic** (the golden HTML carries the static blob). Everything still rides the ADR-6 golden
parity gate; `test_parquet_parity` is untouched (presentation only, §21.9). This is the spine of
[c16d](commits/v02/c16d_report_aesthetics.md); additive to ADR-27 (tokens) / ADR-32 (report contract) /
ADR-33 (charts).

### ADR-35 — the run model: a report renders for ONE current run, prior runs are baselines (c16e)
**Context.** The real Perf ingest (2 runs x 7 areas) exposed a data-model flaw (G-19): the dashboard + the
five single-state reports (`instancing_opportunities`, `draws_by_class`, `shader_hotlist`, `pass_gpu`,
`overdraw`) defaulted to `discover_drops(root)` = **every drop** and aggregated **cumulatively**, so work
fixed/removed in the newer run still showed — "total draws" = run1+run2 summed; a mesh removed in run2 still
listed as a live instancing candidate; the draws-by-class donut summed both runs. The cumulative design
back-fires the moment there is more than one run. **Decision.** A report is rendered **for one CURRENT run**
(a `DropSet` = `(drop_date, drop_label)`), default = newest. The current run's contents are the **reported
truth**: the candidate/item set AND every headline KPI are computed from the **current run only**. Prior runs
are **baselines for delta/trend context** — comparison columns, deltas, the `trend_table` matrix — and are
**never summed into a "current" figure**. An item present in a baseline but **absent in the current run is
NOT a live candidate**: it is dropped, or (on `instancing_opportunities` + `shader_hotlist`, where it is cheap
and high-signal) surfaced in a separated, positively-framed **"resolved since `<baseline>`"** section.
`trend_table` + A/B remain the **across-run** views (A/B already restricts `drops` to a pair, so the same
default resolves current = the compare drop). **The model has ONE implementation:** `reports/discovery.py`
`current_run` / `baseline_run` / `RunContext` (resolved per build via `run_context`, re-exported through
`base`), threaded into `report_page`/`header` as a single `run=` argument. A new report obtains per-run truth
+ the run-naming header by passing its `RunContext` — it cannot silently re-introduce the cumulative bug by
forgetting to scope. **Known assumption:** "newest" = `drops[-1]` after the existing `discover_drops` sort
`(date asc, label asc)`, i.e. label is assumed monotonic-with-time *within a single date* (ISO dates are the
dominant key and are unique per run in practice); revisit if intra-day runs appear. **Default baseline** =
the immediately-prior run (`drops[-2]`); None for a single/oldest run. **Consequence.** The change is
presentation/aggregation only — extraction is untouched, so `test_parquet_parity` stays green with **no
`digests.json` refresh** (§21.9); the HTML golden **is** refreshed and reviewed (the 2-drop synthetic now
shows one run's numbers — e.g. the donut centre drops from the cross-run sum to the current run's total).
Per-drop comparison columns are retained as-is in c16e; collapsing the wide N-run columns to
current+baseline+delta+sparkline is recorded as **G-20** (resolved by c16f, no-op at 2 runs). This is the
spine of [c16e](commits/v02/c16e_run_model.md); the run-switching + comparison **UX** layered on top is
[c16f](commits/v02/c16f_multirun_ux.md) (G-18). Additive to ADR-32 (report contract).

### ADR-36 — reports become an offline static SPA (app folder), with a single-file export (v0.2 SPA epic)
> **SUPERSEDED by ADR-37 (2026-06-02, before any code).** On a lifespan review we judged a bespoke
> client-side SPA a *local maximum* — slicker now, a perpetual web-framework maintenance tax that weakens
> the golden-as-correctness gate, loses JS-optional content, and constrains the v0.6 plugin / cross-platform
> future. ADR-37 keeps presentation server-rendered + static and invests the durable effort in the data
> contract instead. ADR-36 is retained for the decision trail; do NOT implement it.
**Context.** Three design reviews (`docs/plan/{overall_overhaul_proposal,readability_and_presentation_review,report_roadmap}.md`)
surfaced three real problems: the per-drop drill bakes ~21 MB of inline data (slow TTI), every page
duplicates the design system + the base64 font, and the catalog/drill layer (`html/template.py`) is dense +
all-monospace (G-21). The reviews' naive fix (SPA + `fetch('_data/*.json')` + external `/assets/` + a CDN
font) breaks the offline contract: `fetch` of a local file fails on a `file://` page (CORS), so a
double-clicked report would never load (ADR-6), and a CDN font breaks ADR-34. **The unlock:** browsers load
`<script src>`/`<link href>` from `file://` (these are NOT subject to the `fetch`/XHR same-origin block), so
data + assets can be decoupled **with no server** and the output still opens by double-click — at the cost of
the output being a folder rather than one file. **Decision (user signoff 2026-06-02; full proposal +
rationale in `docs/plan/adr36_spa_architecture_proposal.md`).** `bobframes render` emits an **offline static
SPA app folder**: a tiny shell `index.html` + `_assets/app.css` (the WHOLE design system + the base64-inlined
Inter subset, ONCE) + `_assets/app.js` (a **hash router** + the existing web components/VTable) + `_views/*.html`
(one **pre-rendered** HTML fragment per route, rendered server-side by the SAME Python renderers —
`reports/chrome.py` / `charts.py` / the report modules / `html/template.py` — **not** reimplemented in JS) +
`_data/*.js` (the heavy catalog/drill payloads, each `window.__bf_data['<key>']={...}`, **lazy-loaded via an
injected `<script src>` on navigation**, never `fetch`). The **whole output** moves into the app — catalog,
drill, dashboard, and all 6 reports become routes (`#/run/<key>/<report>` replaces the c16f per-run files); the
c16b–f presentation (charts ADR-33, run model ADR-35, A/B, c16d aesthetics) is **re-homed as views, reusing
the renderers**. A **single-file static export** is retained (`export --single-file`): today's self-contained
HTML, the same renderer with data + assets **inlined** instead of `<script src>`'d, via a `DataSink`
abstraction (external vs inline) — so one report can still be emailed/archived as a byte-deterministic file.
**This AMENDS ADR-6** (offline byte-deterministic *single HTML file* → offline byte-deterministic *app folder,
double-click-openable via `<script src>`, no server*, **plus** the single-file export) and **AMENDS ADR-34**
(the vendored Inter subset stays inlined but **relocates** to `_assets/app.css`, loaded once — a CDN/network
font remains forbidden; net size improves). It **supersedes c16i** (the static `html/template.py` readability
pass): the catalog/drill readability goals (type split, roomier rows, heatmap cells, collapsible column
groups, G-21) are delivered **inside the SPA's catalog/drill views**. G-22 (the served/decoupled architecture)
is hereby **ACCEPTED** in this `<script src>`-based, server-less, offline-preserving form. **Consequence.**
This is the **largest change in the project** — it re-homes just-finished work, adds a router/loader,
restructures the golden gate (now over the app-folder file-set + each file's bytes + the single-file export),
and is bigger than the rest of v0.2 combined; the user chose to land it **in v0.2 before the tag** (the tag
slips accordingly) and to **replace** the flat static files now (the single-file export covers the
standalone-file need). The hard guarantees HOLD: **no network** (all loads are `<script src>`/`<link>` of
local relative files; opens by double-click), **byte-deterministic** (every emitted file is static — no
`random`/`Date`/timestamps — gated by the restructured golden), `test_parquet_parity` untouched (presentation
only, §21.9), ASCII lint + c16c a11y + c16d/print/reduced-motion preserved (route changes manage focus +
announce; `<noscript>` links the single-file export). Routing is **hash-based** (zero-config on `file://`).
Implemented as the phased epic **c16j–c16o** (spine + asset bundle + golden restructure → data decoupling →
re-home reports/dashboard/run-model → single-file export + `DataSink` → catalog/drill readability in the SPA →
close-out). Additive to / amends ADR-6/27/32/33/34/35.

**Hard implementation invariants (post-review hardening, 2026-06-02 — these are part of the decision, not
optional):**
1. **The byte-golden no longer proves correctness — add a runtime gate.** In the SPA what the user sees is
   the *result of running the router/loader JS*, so byte-identical files no longer imply a working app
   (CI could be green on dead navigation). c16j adds a **headless-Chrome navigation smoke** to the gate
   (Chrome is already used for screenshots → no new dependency): load `index.html` over `file://`, visit a
   couple of routes, `--dump-dom`/screenshot, assert the view mounted + a known cell rendered.
2. **`#/route` vs `#anchor` must not collide.** The existing reports use bare fragment anchors pervasively
   (`#counts`, `#top_meshes`, `#<area>`, sticky-h2 targets, `trend_table.html#gpu`). The router claims ONLY
   `#/…` (leading slash); a bare `#anchor` means scroll-within-the-current-view. Every in-view jump link is
   rewritten to this scheme in c16l. Stated rule, established in c16j.
3. **Classic scripts only — NO ES modules.** Chrome (and others) block `file://` ES-module loading
   outright. `app.js` is one classic `<script>` (the existing `components_js` IIFE style); no
   `<script type=module>`, no `import`/`import()`. This is what keeps double-click-open working.
4. **Lazy `<script src>` data load is async — sequence it.** The router must NOT mount a VTable before its
   `_data/<key>.js` has loaded; await the script's `onload` (or have the data file call a registration hook
   that triggers the mount). "inject then mount" is a race. (c16k.)
Plus: sidecar links (shader-src `.glsl`, histograms) stay **relative file links**, not routes (c16l);
route changes manage focus + `aria-live` on EVERY view (a sustained a11y cost, not one-time); the root
`index.html` is repurposed (catalog → shell) so c16j defines the default route.

### ADR-37 — keep reports server-rendered + static; fix only the heavy data; invest in the data contract (supersedes ADR-36)
**Context.** ADR-36 (accepted hours earlier, no code) proposed turning the whole output into a bespoke
offline SPA. On a deliberate **lifespan** review (what is best over v0.2->v1.0+: more report types, more
CI/automation consumers, plugins, cross-platform) we concluded the full SPA is a **local maximum**. The
durability hierarchy: (1) the **data** (parquet + a versioned JSON contract) outlasts any UI; (2)
**server-rendered static HTML** is near-indestructible — zero runtime deps, renders with JS off, archivable,
and *the file IS the output so the byte-golden actually proves correctness*; (3) a **bespoke SPA**
(hand-rolled router/loader/fragments) is a mini web-framework maintained forever, shifts correctness into JS
the golden cannot see, loses JS-optional content, and makes the v0.6 plugin story (a plugin emitting a
page/section) + cross-platform harder. The tool's trajectory is toward **machine consumers** (v0.3 `--json` /
gating / verify / diff, v0.4 query, v0.5 schema) — so the lasting investment is the **data contract**, not a
presentation engine. **Decision.** Reject the bespoke SPA (ADR-36). Keep presentation **server-rendered,
static, multi-page, with browser-native links** (the most durable, accessible, zero-maintenance navigation
there is). Specifically:
- **Reports + dashboard stay self-contained single HTML files** — unchanged. Their good properties are
  *preserved*: email-one-file, JS-optional content (JS is progressive enhancement only), and golden-as-output.
  The per-page font/CSS duplication (~40 KB/page) is **accepted** — negligible next to the data, not worth
  trading the single-file property for. (No shared `_assets/` extraction; revisit only on a *measured* size
  problem.)
- **Fix the one real perf problem — the ~21 MB inline-data drill/catalog** — by **decoupling only the heavy
  VTable payload** into a `_data/<key>.js` loaded via an injected `<script src>` (file://-safe, no `fetch`, no
  server) with `onload` sequencing. Those pages were **never** portable-as-one-file (21 MB) and **never**
  JS-optional (the VTable is JS), so decoupling their data costs nothing real and fixes TTI. No router, no
  fragments, no whole-output rewrite — the pages stay static HTML with normal links; the golden stays a
  meaningful byte-gate over the page + its data file.
- **Catalog/drill readability** (type split, roomier rows, heatmap cells, collapsible column groups — G-21)
  proceeds on the static `html/template.py` layer (the revived **c16i**).
- **The durable layer is the data contract:** lean on the already-roadmapped **c20 (`--json`)** + **c30
  (schema + query)** as the versioned machine-readable output that outlives any UI; do not build a parallel
  presentation-coupled data layer. The `_data/*.js` decoupling is a presentation convenience, not the contract.
**This supersedes ADR-36** and **re-affirms ADR-6** (offline byte-deterministic single HTML files remain the
default — only the genuinely-heavy catalog/drill become a small page+data-file pair) and **ADR-34** (font
stays inlined per page). **Epic re-scoped:** the SPA commits **c16k-c16n are voided**; **c16i** (catalog/drill
readability) is **revived**; **c16j** is **repurposed** to the static heavy-data decoupling. **Consequence.**
Far smaller, lower-risk, durable: no bespoke framework, no re-homing of the just-finished c16b-f reports, the
golden keeps proving correctness, JS-optional + single-file survive for the reports, and the lasting effort
routes to the data contract (c20/c30). G-22 resolved as **"SPA rejected; heavy-data decoupling done statically
(c16j); durable data contract = c20/c30."** Additive to ADR-6/27/32/33/34/35; supersedes ADR-36.

### ADR-38 — unify the two table systems into ONE bespoke, progressive-enhancement table component (G-23)
**Context.** The product renders tabular data through **two** unrelated systems (G-23): (1) the **reports**
use a server-baked `<table class="report">` (rows in the HTML) enhanced by the `rdc-sortable-table` web
component (client sort only; degrades gracefully — JS-optional, printable, Ctrl-F-able, golden-visible);
(2) the **catalog + per-drop drill** use the `html/template.py` **VTable** (client-built virtual scroll from
`_pagedata/*.js`, with its OWN sort/filter, numeric detection, type-split, uniform-tint heatmap, and
collapsible column groups). The two duplicate sort/numeric-detection/type-split logic and diverge in look +
capability (filter/heatmap/column-groups exist only in the VTable; golden/print/Ctrl-F/JS-optional exist only
in the report tables). A reviewer asked to unify them, feature-rich, before closing v0.2.
**Forces.** (a) ADR-37 (just frozen) keeps **reports static, self-contained, JS-optional, golden-as-output,
printable**; moving reports onto a client-built virtual grid would forfeit all of those (the byte-golden can't
see client rows; virtual scroll prints/Ctrl-Fs only the windowed DOM). (b) The drill is ~600K rows — it MUST
virtualize (server-baking it was the 21 MB problem c16j just removed); it cannot become a static `<table>`.
(c) A third-party grid (AG-Grid/Tabulator/DataTables/Grid.js) adds a vendored JS dependency, several need
`fetch`/ES-modules (break `file://`) or emit nondeterministic ids (break the golden), and reintroduces the
perpetual web-framework maintenance tax that ADR-37 rejected when it killed the SPA. The repo already has a
~27 KB zero-dep deterministic VTable + the `rdc-sortable-table` component.
**Decision.** Unify on **ONE bespoke component** — `rdc-table` — built by merging the VTable engine with
`rdc-sortable-table` (NO third-party library; offline, byte-deterministic, file://-safe, ASCII, no new dep).
It is **progressive-enhancement with two data-delivery modes**, selected by `data-mode`:
- **`static`** (reports, A/B, per-run, trend, dashboard minis): the rows are **server-baked into the HTML**;
  JS *enhances* (sort/filter/heatmap/column-groups/truncation). JS-off, print, Ctrl-F, single-file, and
  **golden-as-output all hold** — ADR-37's report guarantees are *preserved, not reversed*. This also brings
  c16i's heatmap + column-groups + type-split to the reports (today VTable-only).
- **`virtual`** (catalog + drill): rows stream from `_pagedata/*.js` and the DOM is windowed (today's VTable
  behaviour). These pages were never JS-optional/portable (ADR-37), so nothing is lost.
The shared engine owns sort (natural-numeric, ADR-24), numeric/type detection, the type-split classes, the
uniform-tint heatmap, column groups, search/filter, and truncation+`title=` hover (c16m). Determinism holds:
no `random`/`Date` in rendered output. **Rollout is staged:** **c16k** builds `rdc-table` + both modes and
migrates the catalog/drill (virtual) + one report (static proof); **c16l** migrates the remaining reports +
A/B + per-run + trend + dashboard minis and removes the old `rdc-sortable-table` + VTable scaffolding;
**c16m** adds controllable truncation + hover-reveal to the one component. Golden is refreshed + reviewed at
each stage (split into sub-commits if it balloons, precedent c16d/c16i); reports' server-baked `<td>` row
**content** stays byte-stable (only the wrapper/markup/classes change), `test_parquet_parity` untouched
(§21.9). **Consequence.** One table system, feature-parity across reports + drill, ADR-37 intact (reports
stay static/golden/JS-optional/printable), no new dependency. **Reaffirms ADR-37 + ADR-6 + ADR-24; resolves
G-23.** Additive to ADR-6/24/27/32/33/34/35/37.

### ADR-39 — the exec one-pager + a presentation-independent health verdict + the converged surface model (v0.2.5)
**Context.** Every output surface is engineer-facing (report_roadmap calls the dashboard "flat,
developer-oriented"); a perf lead / producer has no one-screen health read. The verdict ("is my frame
healthy") is the tool's single most durable output, and the roadmap already wires its consumers below
presentation: c20 `--json`, c21 `report --gate` exit code, c37 alerts. **Decision.** (1) Add a NEW
standalone report `reports/summary.py` (`_reports/summary.html`), print/PDF-first, a composition of the
existing primitives (KPI strip, callout, charts, run model, provenance) that **supplements, not replaces**
the dashboard. (2) The verdict logic lives in a presentation-INDEPENDENT module `bobframes/health.py`
(peer of the future `jsonout.py`/`export.py`, NOT under `reports/`). It is computed **PER AREA then rolled
up**: `area_verdict(area_metrics, cfg)` scores one area first-match from `ReportCfg` thresholds (no new
threshold; each comparison mirrors a source report so the verdict cannot disagree); `verdict()` returns a
stable `Verdict` (`State` enum `OK/AT_RISK/ALARM/UNKNOWN` + a `Trigger` list + `worst_area` +
`area_verdicts: dict[str,State]`) where `state = max(area_verdicts)`. The headline is therefore scope-able
("N of M areas needs attention - <worst_area>") instead of a single global tier one bad area paints red -
this pulls forward the per-area work G-25 had deferred. It is **data-aware**: a missing input (no baseline,
missing parquet) yields `UNKNOWN`, never a false-green `OK` (ADR-23). `summary.py` builds per-area
`AreaMetrics` via direct reuse of `dashboard.py`'s current-run helpers (`_top_*` keyed on area, `n=999` for
true maxima) + per-area frame counts, calls `health.verdict()`, and RENDERS it. The headline KPIs are
**AVERAGES** (mean `draws/frame` and `gpu/frame` across the run, each with a baseline delta; the run total
shown small for scale) over a worst-first per-area breakdown table; "worst overdraw"/"worst shader" stay
MAX and name their area, so averaging the headline cannot bury a fire the worst-based verdict still catches.
The stable enum is the wire key while the banlist-clean human labels (`Healthy`/`Needs attention`/`Action
needed`/an UNKNOWN label) are a presentation lookup, never in `health.py`. A sibling `health.trend(current, baseline)` answers the dual-use need ("are draws reducing / is there a
regression"): a `Direction` (IMPROVING/MIXED/REGRESSING/UNKNOWN, net of the headline deltas, lower-is-better,
NEVER a cross-run sum - the G-19 flaw) + an `improvements`/`regressions` ledger of ranked `Change` items
(incl. resolved/new counts). The one-pager is thus dual-use - execs read the verdict + scope; tech leads
glance the Direction tag, the Movement card (Improvements | Regressions + counts), the per-KPI vs-prior
deltas + sparklines, and the per-area vs-prior deltas. **c20 `--json` and c21 `report --gate` will CONSUME
`health.verdict()` + `health.trend()` (the regression signal), not re-implement them**
(a FINDINGS row ties c21 to health.py); the `reports/aggregates.py` extraction is deferred to the 3rd
consumer (YAGNI), guarded by a parity test that the average KPIs reconcile with the dashboard's current-run
totals / frame count. (3) **Converged surface
model (recorded end-state):** root `index.html` = the directory; `summary` = the human/exec landing +
verdict; `dashboard` = the engineer drill-board. summary is made discoverable now (a `summary` chip in
`dashboard._NAV`, a promoted slot in the root-index dashboard section excluded from the auto-listed report
grid, and `chrome.header` taught the `summary` surface) rather than shipping as an orphan; the convergence
target (deferred, churns `dashboard.html`) is the dashboard hero `summary_bar` consuming `health.verdict()`
so the verdict shows on both surfaces from one source. **Consequence.** Additive: a new golden page (+
per-run) plus an intentional, reviewed `index.html`/`dashboard.html` nav refresh; the verdict is seated in
the durable layer ADR-37 asked for. Extends ADR-32's report contract; reaffirms ADR-33/35/37. The per-area
rollup + worst-area naming + the "N of M areas" headline + the averaged KPIs all ship in c16q (pulled
forward at the user's request, to convey scope rather than alarm). The verdict tier asymmetry (only
overdraw/gpu reach ALARM, since config has a warn+alarm band only there) is recorded; what REMAINS deferred
is a per-dimension warn+alarm `[gating]` config table that lifts the inline `shader_hotlist` `*1.25` band
(G-25, H-40).

### ADR-40 — `bobframes package`: a non-mutating stream transform + the output-verb taxonomy (v0.2.5)
**Context.** Users need a first-class way to hand the HTML tree to a colleague; the output-verb set
(serve/package/export/--json/schema) is accreting one-at-a-time, and a `package` zip would collide head-on
with the already-specified c26 `export --format csv|json|zip` (two verbs emitting a `.zip`, with
`export.py` not yet built). **Decision.** Add a `package` verb that is a deterministic, NON-MUTATING
transform: it reads an already-rendered `<root>` and **streams** entries into a reproducible `.zip`
(HTML transformed in memory; parquet/sidecars/`_pagedata` written raw from source; NO physical 2x staging
copy by default - the gate reads entries back out of the zip; `--stage` is the opt-in for a materialized
tree). The zip is written OUTSIDE the read tree (default `./<root-basename>-report.zip`), so non-mutation
holds at the filesystem level. Because render is untouched, the default single-file inlined output and
`test_parity` are unchanged and **ADR-37 holds literally**. Define FOUR orthogonal output-verb contracts -
**PRESENTATION** (`render`/`package`/`serve`: emit HTML, never `--format`, never machine data, never an
asset-build engine beyond the render-time sink), **DATA** (`export` `--format csv|json` / `--json` /
`schema`/`query`: versioned contract per ADR-16, never HTML; `export` owns the `_data` data-zip),
**ANALYSIS/GATING** (`diff`/`verify`/`report --gate`: exit-code-bearing, consume `health.Verdict`),
**PIPELINE** (`ingest`/`parse`/`replay`/`catalog`) - with the invariant that a presentation verb may
relocate/bundle already-rendered bytes but may NOT become a data emitter or asset-build engine; durable
capability lives in the data contract (c20/c30). Concretely **`package` never gains `--format`**, which is
what keeps it from drifting into the SPA ambitions ADR-37 rejected, and c26 `export` inherits the boundary.
The byte gate is the tree extracted from the produced zip (zip bytes are not stable across zlib/Python, so
they are round-tripped, not byte-compared; reproducible-zip knobs: sorted `/` arcnames, fixed `ZipInfo`
date, pinned `ZIP_DEFLATED`, per-entry `writestr`). `--redact` scrubs at the provenance DATA seam (give
`provenance_strip` a redact mode + re-emit from the manifest), not an HTML regex, and strips abs-path
tokens by default (usable on real captures that carry a path in a value); fail-closed only in an explicit
`--redact-paths=fail` CI mode, where the abs-path scan is a post-scrub completeness assertion.
**Friendly-UX defaults (so a non-expert gets the right artifact without flag knowledge).** `package`
emits TWO tiers in one run: a standalone single-file `<project>-<rundate>-summary.html` (the one-pager with
assets inlined via `head_assets(INLINE)`) for the email/double-click/`Ctrl-P -> PDF` case with NO unzip,
AND the explorable `<project>-<rundate>-report.zip`. The zip DEFAULTS to shared-assets (small, the common
multi-run case; `--inline` is the opt-out, c16t); carries a root `README.txt` (extract first, open
index.html, start at the summary); is named from the project + the current run's `drop_date` (deterministic,
filenames are not golden-gated); and a `--light` preset bundles summary + the 6 reports only (no
drill/`_data`) for a small "read, do not drill" share. **Accurate-usage facts recorded** (the contract a
recipient relies on): the zip must be EXTRACTED before opening (Windows' in-zip preview extracts a single
file without its siblings, breaking relative `_assets/`/`_pagedata/` links); in `--inline` the summary/6
reports/dashboard are each individually portable but DRILL pages need their `_pagedata/` siblings; in the
default shared-assets bundle NO page is individually portable (all need `_assets/`), which is exactly why
the standalone summary exists; PDF is the recipient-friendliest format but is a manual `Ctrl-P` (no runtime
PDF dep), so the one-pager is print-tuned for it. **Consequence.** A first-class human-share path with a
measured multi-run size win (via ADR-41), a coherent verb taxonomy the rest of the roadmap inherits, ADR-37
unforked. Reaffirms ADR-37/6/11/16.

### ADR-41 — shared-asset extraction via a render-emission seam; revisits ADR-37's accepted duplication (v0.2.5)
**Context.** ADR-37 accepted the per-page font/CSS duplication ("negligible next to the data") and
reserved `_assets/` extraction "only on a measured size problem." That problem is now **measured**: 30
inlined report pages zip to 1.30 MB versus 48 KB when the ~95 KB of chrome is a single shared asset (a
zip's per-file DEFLATE compresses each entry independently and does NOT collapse cross-page duplication),
and multi-run trees multiply it. **Decision.** Introduce a single `head_assets(sink, depth)` seam in
`chrome.page_open()` (and the catalog/drill equivalent in `html/template.py`): the `INLINE` sink is the
render default and is BYTE-IDENTICAL to today (ADR-37's single-file default stands, golden untouched); the
`REF` sink emits `_assets/` + depth-relative `<link>`/`<script defer src>`. `bobframes package
--shared-assets` produces the REF form by calling the SAME seam and writing each `_assets/*` file once from
the composer output, so the asset boundary is one source of truth - **zero-drift by construction**, with no
needle, no `str.replace`, and no "exactly one replacement" tripwire (the rejected post-render-scrape
mechanism). Extraction is per page-family (`report.css`/`report.js` for the `page_open` family,
`catalog.css`/`catalog.js` for the template family) because the two families emit different CSS bundles +
JS tags; the unique `__labels` inline and the per-page `_pagedata/*.js` data scripts stay. All ADR-37
report guarantees (file://-safe links, JS-optional server-baked bodies, printable, Ctrl-F-able,
golden-as-output) hold in the bundle. The `package` summary line emits the size measurement so
the "measured problem" stays on record. **Consequence.** The measured size win is captured cleanly via the
render-time mechanism ADR-37 implied for the eventual revisit, without a second render-default golden;
ADR-37 is confronted and extended, not forked. Reaffirms ADR-37/6/34.

### ADR-42 — a server-side component system; stop brute-forcing per-page CSS (v0.2.5, c16x)
**Context.** c16q shipped the exec one-pager's styling as a page-scoped inline `<style>` (keyed on
`body[data-page-kind="summary"]`) plus bespoke markup helpers (`summary._kpi`, `_trendline`, a status
badge, the Movement layout) that re-implement card/kpi patterns chrome already half-owns. The untyped
inline-CSS approach bit back immediately: a typo'd `var(--sp-5)` (there is no `--sp-5` - the token scale
is 1/2/3/4/6/8/12) made the padding shorthand invalid, which computes to `0`, silently zeroing the chip
padding until a visual review caught it (recorded G-30). This is the structural smell: every new surface
hand-rolls markup + a scoped `<style>` against one big inlined CSS string, with no reusable + testable
component layer and no guard that a referenced token actually exists. It does not scale past one page.
**Decision.** Introduce a small **server-side component system** - plain render helpers + one owned
stylesheet, NOT a CSS framework, build step, or runtime dependency (ADR-37 holds: static, offline,
JS-optional, golden-as-output). Concretely: (1) promote the ad-hoc one-pager primitives into composable
`chrome` components (e.g. `kpi_card`, `trendline`, `status_badge`) alongside the existing
`section_card`/`callout`/`summary_bar`, so pages COMPOSE components instead of emitting bespoke markup;
(2) their classes live ONCE in the shared chrome CSS bundle (the same bytes ADR-41's seam extracts to
`_assets/report.css`), never in a per-page `<style>`; (3) a **token-validity guard** - a `_tokens`
accessor / lint that rejects any `var(--…)` not in the declared design-token scale - so the c16q
`--sp-5` failure mode is structurally impossible; (4) every component gets a structural test (mirroring
`tests/test_report_structure.py`) and one instance in the existing `_chrome_preview.html` gallery (c08),
which becomes the living component catalog. `summary.py`'s inline `<style>` + `_kpi`/`_trendline`/badge
are the first migration (a reviewed golden refresh; the chrome-family pages re-render because the
component CSS joins the always-on bundle - visual parity, no body-markup change beyond summary's). This
is why it is its OWN commit (c16x), separate from c16q's tight 5-file delta. Best sequenced after c16t
so the now-larger shared CSS is a single packaged asset (render still inlines it per page, ADR-41), and
before the c16w close-out. **Consequence.** New surfaces compose tested, gallery-reviewed components;
the inline-CSS / undefined-token failure class is gone; the preview gallery is the component catalog.
Closes G-30. Reaffirms ADR-37/34/27 (design tokens), rides ADR-41 (where the component CSS lives).

### ADR-43 — v0.2.6 bold visual redesign; deliberate parity->improvement; collapse the unreleased 0.2.5 into 0.2.6
**Context.** c16x (ADR-42) landed the component system as a SAFE FOUNDATION at visual parity (CSS/JS
extracted to files; the escape-by-construction `el` builder subsuming roadmap C6; the token-validity
guard; the table component family built-but-not-adopted; summary migrated off its inline `<style>`).
None of that is user-visible -- it is internal plumbing plus a pixel-identical summary migration. The
user-facing value is the look-and-feel improvement, which c16x deliberately deferred. Two follow-on
decisions: (a) the visual redesign should be BOLD (new type scale, spacing rhythm, palette/contrast,
accent rails, component states, responsive/print/a11y), an intentional deviation from ADR-42's
visual-parity clause; (b) there is no reason to cut a standalone 0.2.5 release for invisible plumbing.
**Decision.** (1) The visual-parity clause of ADR-42 is SUPERSEDED for the v0.2.6 work (its MECHANISM --
the owned bundle, `el`, the token guard, the gallery -- is reaffirmed and is what makes the redesign
safe). (2) **Do not release 0.2.5.** `0.2.5` becomes an unreleased version gap (consistent with v0.1's
c04-c10 gaps); the next PyPI release is **0.2.6**, carrying BOTH the component-system foundation
(c16q-c16x) AND the redesign. `_version` jumps `0.2.0 -> 0.2.6`; ONE CHANGELOG `[0.2.6]` covers
everything since 0.2.0; the c16w close-out is repurposed as the v0.2.6 close-out. (3) Because byte-parity
is intentionally broken for the redesign, the binding gates become: data digest unchanged
(`test_parquet_parity`, never refreshed); golden-INDEPENDENT structural + ARIA component tests; the
token guard; a MANDATORY headless-Chrome browser matrix (light/dark/print, synthetic + real Perf at
`c:/tmp/perf`) per changed surface; lint/ASCII/determinism. Golden refreshes run ONLY on the canonical
env (py3.12 / pyarrow 21; ADR-11 / D-8 / the `golden_env` marker), never an out-of-range local pyarrow.
(4) v0.2.6 also ADOPTS the table component family across the reports + rolls the remaining hand-concat
leaves onto `el` (the work c16x deferred because byte-identical migration was infeasible). **Correction
to ADR-42.** ADR-42 said the guard rejects a `var(--...)` "not in the declared design-token SCALE"; the
as-built (and correct) declared set is (the TOML `:root` scale) UNION (every `--x:` custom-property
DEFINITION scanned from the composed CSS), and programmatic chart/layout tokens (`_tokens.chart()`) are
passed as values, never `var()`-referenced, so they need no allowlist. **Consequence.** One meaningful
0.2.6 release (foundation + redesign); the ADR-37 invariants (static / JS-optional / printable /
Ctrl-F-able / offline / ASCII / deterministic) hold throughout -- only the byte-parity gate is
intentionally, and gate-replaced, relaxed. Reaffirms ADR-37/34/27/41/42; rides ADR-11/23.

### ADR-44 — v0.2.6 visual language: flat/border-led (reverse ADR-34 depth), neutral chrome, radius scale, hero-on-summary type, Grafana density
**Context.** ADR-43 authorized the v0.2.6 redesign anchored on shadcn/ui surfaces + Grafana data-density;
the brief left six concrete look-and-feel decisions open for the implementing session. They were
reconciled with the user (AskUserQuestion, 2026-06-05) and are recorded here so the visual language is a
frozen decision, not a per-commit drift. **Decision.** (1) **Flat, border-led elevation** -- cards / minis
/ reports sit on the page background, separated by a 1px `--border` + a radius, with near-zero shadow.
This **reverses ADR-34's "depth over borders"** for v0.2.6 (recorded here per ADR-23; flat also prints
cleaner and matches shadcn's identity). `--elev-1/2/3` are re-tuned toward flat in v0.2.6-1b. (2)
**Neutral chrome** -- the default palette is chroma-0 grayscale (shadcn): white / `oklch(0.145)`
backgrounds, hairline borders, a near-black/near-white `--accent-primary`. The **semantic data colors are
kept** (`--status-*`, the `--c-*` draw classes, the `--accent-data` data accent + heatmap tint) so data
stays legible on the quiet chrome. (3) **A `--radius` token scale** (`--radius-sm` 6px / `--radius` 8px /
`--radius-lg` 10px) replaces the hardcoded 2/3/4px literals -- tight on dense minis, generous on hero
cards. (4) **Restrained type** -- vendored Inter weight <= 600 holds (700 = faux-bold = regression); modest
`h1/h2/h3` tune + `tabular-nums` + uppercase `--fs-micro` eyebrows (DOM text stays lowercase for Ctrl-F);
`fs_body`/`fs_mono` unchanged; the ~2.75rem hero numeral is scoped to the summary one-pager KPIs only.
(5) **Grafana density** -- dashboard / reports / drill pack tight (smaller spacing steps, more KPI cards
per row, the `rdc-table` row height stays tight); the summary one-pager is the one airy/exec surface.
**WCAG-AA** is fixed in the process (`--text-3` 3.0->4.85:1), proven by `test_contrast.py`. **Consequence.**
A single frozen visual language for v0.2.6; ADR-34's depth is superseded for this release (its anti-clutter
intent survives as the hairline-border restraint). Implemented across v0.2.6-1a (token values) + 1b (flat
surfaces / radius application / states / responsive / print). Reaffirms ADR-37/43; rides ADR-23.

### ADR-45 — user theme override: pip users tune accent/status/chart hues without editing source
**Context.** ADR-44 makes the chrome neutral by default; the user requires that a `pip install`-ed user be
able to brand the reports with their own accent WITHOUT editing the packaged `design_tokens.toml` (which
lives in site-packages and is lost on upgrade), and tokens are substituted into a chrome module constant
at import time. **Decision.** Reuse the EXISTING config cascade (ADR-25): a new `[theme]` section in
`.bobframes.toml` (discovered via `$BOBFRAMES_CONFIG` > `<root>/.bobframes.toml` > `%APPDATA%/...`,
deep-merged over the bundled token defaults) plus a one-shot `bobframes render --accent <oklch>` flag (the
top precedence tier: CLI > env > config > default). The overridable surface is the COLOR HUES only
(`accent_primary`, `accent_data`, the four `status_*`, the `c_*` draw-class palette) -- layout / spacing /
type / radius stay bundled (a key outside the allowlist warns + is ignored, so a user can never desync
`ROW_H` / density / parity machinery). A parameterized `chrome.compose_css(theme=None)` re-substitutes for
an overriding render while `theme is None` returns the existing cached constant **byte-for-byte** (the
default render stays byte-identical -> goldens green); the `theme` dict threads through the same seam that
already carries `sink`/`build_ts`/`redact`. The overridden bundle is run through the c16x token guard at
render (non-fatal warn / hard CI assert on a planted bad override). `package` (a PRESENTATION verb, ADR-40)
rejects the flags. **Consequence.** Pip users brand reports via config/CLI, not source edits; the full
per-token override stays deferred to Track B. Implemented in v0.2.6-1c. Extends ADR-25; rides ADR-40/43/44
+ the c16x guard.

### ADR-46 — one aggregation policy: per-frame canonical, estimator+population named on every label (v0.2.7)
**Context.** A 2026-06-16 audit of the real RDC mainline Perf corpus (`reference/AGGREGATION_FINDINGS.md`)
found the reports use FOUR aggregation bases (pooled/frame-weighted mean, per-area mean, median, raw total),
several labeled as a bare "avg", so the same metric reads at different magnitudes across reports. The
rendered-corpus review confirmed the felt confusion: the same area's GPU read `0.0356` on summary
(per-frame), `0.178` on the dashboard card (raw total), and `0.178` on trend, with no bridge
(`0.178 = 0.0356 x 5 captures`, denominator never shown). Two reports also computed "GPU regression" on
contradictory bases -- raw cross-capture total in `trend_table` (capture-count-SENSITIVE) vs per-frame mean
in `summary`/`health` (capture-count-INDEPENDENT) -- producing disagreeing action items when capture counts
differ; the corpus had to be hand-trimmed to a uniform 5 captures/run to dodge it. User feedback (v0.2.7):
"the averages are very confusing when we read the reports," plus a directive to name the estimator
precisely ("Mean", not "avg"). c16v (G-29) already established `formatters.per_frame` as the ONE
normalization seam and `aggregates.py` as the single per-(drop, area) data layer with a data-derived frame
count. **Decision (user-confirmed 2026-06-17).** (1) Canonical headline basis for additive quantities (GPU
s, draws, bytes) = **per-frame, pooled micro** (`Sigma total / Sigma frames`); canonical per-area basis =
**per-frame, per-area** (`area_total / area_frames`). (2) Non-additive roll-ups (prepass/opaque ratio,
"typical" verts) use the **median** across the population. (3) Raw cross-capture totals are NEVER a lone
headline -- where shown they are labeled "total over N captures" and paired with the per-frame rate
(user decision: normalize the raw-total reports to per-frame). (4) **Naming convention:** the exact
estimator word -- "Pooled mean" / "Mean ... (per area)" / "Median ..." / "Total ..." -- never "avg"/
"average"/"(med)". (5) ONE regression basis = per-frame, sourced from `ReportCfg`, consumed identically by
`trend_table`, `summary`, `health` (D-13, H-41). (6) ONE owner of every per-(drop, area) frame count
(`aggregates.frame_counts`); per-frame GPU/draws divide by the frame_totals frame count, per-frame entity
rates by the entity-capture count -- these legitimately DIFFER (a capture can replay ok yet export no
entity rows), so the build WARNS on divergence rather than forcing a single (wrong) denominator (D-15;
equality does not hold by design -- the synthetic itself is 5 vs 1). (7) Overdraw's pooled-over-samples
reject% and the MAX "worst overdraw" are correct as designed and recorded so they are not "fixed" into a
mean (Q-13). **Consequence.** Each labeling/normalization commit changes emitted numbers/labels -> a bounded
golden refresh per ADR-23 (intentional change, diff reviewed in the PR), never a silent gate narrowing. On
the 1-capture-per-frame path `per_frame` is a no-op, so numeric churn is confined to multi-capture data +
constructed tests. Enforced by new tests (trend<->health per-frame parity; headline<->per-area-column
relationship; an "avg/(med) absent from rendered labels" naming gate). Extends c16v/G-29; implemented across
v0.2.7-0..-4.

### ADR-47 — human frontends are a layer above the verb taxonomy; the first is a zero-dep local-web control panel `ui` (v0.2.8)
**Context.** v1's CLI (argparse, `[HH:MM:SS]` log lines) is a barrier for QA/product teammates who need to
ingest -> generate -> package reports but are not comfortable in a terminal: they must get the
`<Area>/<YYYY-MM-DD[_label]>/*.rdc` convention exactly right, resolve the RenderDoc tools, recall the
verb/flag sequence, and read raw logs through a 600s/capture replay with no progress affordance. ROADMAP
names "install + first report < 5 min" as an explicit adoptability goal. ADR-37 rejected a bespoke offline
SPA *for the report artifacts* on durability/maintenance-tax grounds; ADR-40 froze the PRESENTATION verbs
(`render`/`package`/`serve`) and the four-contract verb taxonomy; ADR-17 keeps the core pyarrow-only. None
of these address a tool that DRIVES the pipeline for a human. A TUI (still a terminal; adds a dep) and a
packaged desktop GUI (heavy build/signing/maintenance) were weighed and set aside.
**Decision (user-confirmed 2026-06-24).** A human-facing frontend is a SURFACE layered ABOVE the ADR-40
verb taxonomy, not a fifth verb category. The first frontend is `bobframes ui`: a ZERO-dependency local-web
control panel on the stdlib `http.server` (the pattern `serve` already proves), bound to `127.0.0.1`, that
opens the browser and DRIVES the existing verbs. Rules: (1) it MUST NOT re-implement pipeline/render/package
logic -- read-only state via in-process calls (config/discovery), heavy work by SPAWNING the existing CLI
verbs as subprocesses and streaming their stdout (the `_render_watch` precedent), so a qrenderdoc native
fault or the `os.environ` / `config._ACTIVE` singleton mutation in `run.main` cannot corrupt the panel;
(2) it MUST NOT become a report artifact -- it emits no report HTML, so the golden gate and ADR-37's
static-output contract are untouched (reaffirmed); (3) it MUST NOT pull a dependency into core -- pyarrow-only
stands (reaffirms ADR-17); distribution is `pipx install bobframes` -> `bobframes ui`, all features, no extra,
no `.exe`; (4) because POST endpoints spawn processes, a minimal guard is mandatory: localhost bind + a random
per-session token required on every `/api/*` call. **Hard governance limit:** the panel never accretes a JS
framework, a client-side router, or a build step. If it ever needs one, that is the trigger to promote a real
GUI as an optional extra -- not to grow a bespoke web app inside core (the exact tax ADR-37 refused).
**Consequence.** A new top-level `ui` verb + a `bobframes/ui/` package; no change to the verb taxonomy or any
existing verb. Progress in v1 is derived by PARSING the verbs' stdout `[HH:MM:SS]` lines (raw lines always
shown verbatim, nothing hidden -- ADR-23); the durable replacement is the structured `api.py` + `events.py`
orchestration seam, which is the v0.3 `--json` prerequisite and will absorb the panel's progress channel then
(one seam -> CLI, `--json`, verify/diff, the panel) -- recorded as deliberate scoping, not rework. Golden gate
unaffected (no report HTML emitted). Approved plan
`~/.claude/plans/lets-plan-on-improving-bubbly-bumblebee.md`; implemented across v0.2.8 (v028_0..-5).
