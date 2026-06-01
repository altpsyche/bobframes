# Quality gates

> Carved from CLI_PLAN §11 (testing strategy) + §21 (safeguards). These run in CI on every push and
> are the contract behind "output as good or better than today." The golden-parity gate is the
> backbone that makes every refactor safe.

## Testing tiers (§11)

| Tier | What | Where | When |
|---|---|---|---|
| Unit | lint banlist; schema dtype inference; path helpers; discovery regex; stable_keys; classifier | `tests/unit_*.py` | pytest local + CI per push |
| Render smoke | render-only against bundled synthetic `_data/` | `bobframes smoke` (no `--data`) | CI per push |
| Full smoke | ingest + render against real `.rdc` corpus | `bobframes smoke --data <path>` | manual / nightly; needs Windows + RenderDoc |
| Schema regression | every parquet's columns match `schemas.expected_columns(stem)` exactly | inside smoke | both tiers |
| Lint regression | every emitted HTML passes `lint.lint_file` | report build (already enforced) | both tiers |

**Test corpus:** real `.rdc` corpus not bundled (size); README documents internal-share download +
SHA256. Synthetic bundled corpus ~500KB at `tests/data/synthetic/`, mimics `SCHEMA_VERSION=3`.
**Per [ADR-6](../DECISIONS.md): generate the synthetic by anonymizing/down-sampling a real ingest,
not by hand** — verify it exercises every `class_order` bucket and every `[pass_strip]` rule before
freezing the golden, or the parity gate gives false confidence on unexercised paths.

## 21.1 Golden-snapshot parity (byte-identical HTML before/after every refactor)

```
tests/data/
  synthetic/          # tiny _data/ tree (~500KB), SCHEMA_VERSION=3
    _data/<area>/<drop>/*.parquet   _data/_catalog.parquet
  golden/             # frozen expected HTML output
    index.html  _reports/*.html  _reports/drill/<area>/<drop>/index.html
```
`tests/parity.py`: copy synthetic → tmp, `bobframes render`, assert each `golden/**.html` byte-equal.
**Refresh** (only on intentional output change): re-render synthetic → copy to `golden/` → review
diff in PR.

## 21.1b Parquet-output parity (G-14) — see [c06b](../commits/v02/c06b_parquet_parity_gate.md)
`test_parity` gates **HTML only** (it skips `_data`/`_cache`), so a data-path regression — e.g.
c05's `_global_entities` row-order shift — is invisible to it. `tests/test_parquet_parity.py` closes
that: render synthetic → walk every `_data/**/*.parquet` → compare a **writer-independent logical
digest** (schema + row order + cell values) against `tests/data/golden_parquet/digests.json`.
The digest hashes `Table.to_pydict()` in schema column order (non-finite floats → fixed sentinels),
**NOT on-disk bytes** — those vary by pyarrow writer version (the D-8 trap). Because the digest is
logical, this gate runs on the **FULL matrix** (proven identical py3.10/pa17 ↔ py3.13/pa21), unlike
HTML parity which [ADR-11](../DECISIONS.md) pins to the canonical cell. **Refresh** (only on
intentional data-path change): `python -m bobframes.tests.make_parquet_golden` → review diff in PR.

## 21.1c Config defaults reproduce literals (c07, ADR-6) — see [c07](../commits/v02/c07_toml_config.md)
The c07 TOML config lifts timeouts, the drop-folder regex, the lint banlist, the chrome-scrub regex,
complexity weights, and delta/formatter knobs out of code. Bundled defaults (`_default_config.toml` +
`lint_banlist.toml`) must reproduce today's output **byte-identically**, so `tests/test_config.py`
asserts: regex `.pattern` equality (`dated_re`, `chrome_scrub_chars`), `delta.fmt` string identity,
and **bit-for-bit** floats (`struct.pack('>d', …)`) for every complexity weight + threshold + timeout
(tomllib must parse `0.3`/`2.0`/`8.0` to the same double as the Python literal). The banlist TOML
round-trips to the exact original 15-entry `lint.BANNED` (patterns + flags + order). Because the
defaults are bit-identical, **`test_parity` + `test_parquet_parity` stay green with no golden refresh**.
The **CI matrix is unchanged** (3.10 retained, ADR-26): the loader runs under `tomli` on the 3.10 cell
and stdlib `tomllib` on 3.12/3.13, and the digest gates assert identical loaded values across cells —
proving `tomli`↔`tomllib` equivalence, not assuming it. Spawn-safety: the convert timeout is threaded
into the pool worker as an argument (not read from a child-side singleton), gated by
`test_convert_timeout_threaded_as_argument`.

## 21.1d Design-token + preview parity (c08, ADR-6/27) — see [c08](../commits/v02/c08_design_tokens.md)
c08 lifts the `chrome` CSS token VALUES + the base layout literals into `reports/design_tokens.toml`,
routing them through a value-only `string.Template` skeleton (ADR-27), so the emitted `:root` block and
layout rules are byte-identical — **`test_parity` stays green with no golden refresh**.
`tests/test_design_tokens.py` adds focused, golden-independent guards: substitution leaves no `$`
placeholder; the hand-aligned color lines (incl. the 3-space `--c-other` alignment) and every layout
literal land verbatim; `sparkline_svg` defaults are `(60, 14)` from `[layout]`; the bundled TOML is
ASCII; and `export-tokens --format {toml,json,css}` round-trips. The new `preview` gallery has a
dedicated byte-golden at `tests/data/golden_preview/_chrome_preview.html` (OUTSIDE `golden/` so the
`test_parity` file-set walk is unaffected; refresh via `python -m bobframes.tests.make_preview_golden`)
and is asserted deterministic (no build timestamp). Q-6's `chrome.report_page(...)` extraction is
covered transitively by `test_parity` (the 6 reports + dashboard route through it byte-identically).

## 21.1e Classifier parity + the D-6 deletion (c09, ADR-6/29) — see [c09](../commits/v02/c09_classifier.md)
c09 lifts UE draw classification + pass-strip + frame-prefix + GPU-counter aliases into TOML presets
(`derives/draw_classifier.toml` = UE default) behind one analysis-layer API (`derives/classifier.py`),
a **state-capable** rule engine (`when{}` over any draw column; markers are a refinement). Bundled
defaults reproduce today's output **byte-identically** — `test_parity` + `test_parquet_parity` stay
green with **no golden refresh**. `tests/test_classifier.py` adds golden-independent guards: the UE
preset matches a frozen copy of the former `derive_post_merge._classify_draw` over a 300+ case oracle
battery (every rule + sub-pattern + blend/depth precedence); `frame_prefix_re().pattern` /
`pass_strip()` / `gpu_duration_aliases()` / `class_order()` equal the former literals; every
`--c-<name>` for name in `class_order` is present in the emitted `:root` block (H-5 names↔order); a
`when{}`-only mini-spec classifies without markers (the c27 generic-preset path); a Unity preset
reclassifies a Unity-style marker; and `replay_main` no longer defines `_classify_draw`. **D-6
collapse:** the drifted replay-side classifier (fed only the dead `passes.draws_by_class_*`, superseded
by `pass_class_breakdown`) is **deleted**, so the replay stage emits facts only (§21.9 by
construction); those 9 columns stay zeroed under the frozen schema (the §21.3 replay-drift gate stays
green), full removal deferred to c35. Real-`.rdc` re-validation that replay still runs is the
self-hosted/nightly smoke (CI never runs replay, §21.6).

## 21.1f Report-quality polish (c16, ADR-6/32) — see [c16](../commits/v02/c16_report_quality.md)
c16 adds hero KPI strips, insight callouts (`chrome.callout`, config `[report]` thresholds), heatmap
shading (`chrome.heatmap_cell`), a header provenance/device strip (`chrome.provenance_strip`, deterministic
via the synthetic manifest's stub `host_info`/`tool_versions`; the `bobframes` version is deliberately
**not** rendered, so a release bump never churns the golden), and icon empty-states — across all reports.
This **changes rendered HTML**, so the golden is **refreshed** here (reviewed: the only drill/root deltas
are the D-11b dead-CSS removal + the shared `.callout`/`.empty-state` rules). `test_parquet_parity` stays
green with **no** `digests.json` refresh (extraction untouched, §21.9). The manifest schema-version guard
(D-7) is **parity-neutral**: a current-version synthetic manifest passes, so every render gate stays green;
`test_manifest_guard` forces the mismatch. Cache integrity (R-13) is covered by `test_cache` (SHA256 sidecar
+ corrupt→warn→None + missing-column tolerance), empty-state by `test_report_polish` (a 0-row synthetic
render shows the friendly message), and sparkline null-gaps by `test_delta` (golden-independent; the live
series never emits `None` today, G-16).

## 21.1g Inline-SVG chart determinism (c16b, ADR-6/33) — see [c16b](../commits/v02/c16b_report_viz.md)
c16b leads each of the 6 reports with a visualization from `reports/charts.py` — deterministic,
dependency-free server-side inline SVG (fixed-precision coords mirroring `delta.sparkline_svg`, no
`random`/`Date`/timestamps), themed from `design_tokens.toml` `[chart]` (sizes) + existing CSS `var(--...)`
colors, with the detail table kept directly below as the exact/accessible fallback. Because the SVG is
logically deterministic it **rides the golden byte-parity gate** like the rest of the HTML (no `<canvas>`,
no vendored JS lib that would force a parity carve-out — the ADR-11 trap). The output-changing render means
the HTML golden is **refreshed here** (`python -m bobframes.tests.make_golden`, reviewed page-by-page:
the 6 reports gain a `<figure class="chart">` + the shader column-diet reshape; index/dashboard/drill change
only by the shared chart CSS). `test_parquet_parity` stays green with **no** `digests.json` refresh
(presentation only, §21.9). `test_charts` adds golden-independent guards (determinism = same input → same
bytes; SVG structure = `role="img"`/`<title>`/`<desc>`; token theming; empty-series → safe `''`; an
ASCII-only guard since chart `<text>`/`<title>`/`<desc>` ride **outside** `<table>` and are therefore linted
— labels are scrubbed via `safe_chrome_text`). Chart-first + table-as-fallback is the report pattern. The
restructure (section framing, copy buttons, dashboard small-multiples, fuller a11y) is
[c16c](../commits/v02/c16c_report_restructure.md).

## 21.2 Schema regression
Every parquet column list equals `schemas.expected_columns(stem)` (catches alphabetization drift,
dropped column, dtype slip). Skip `_`-prefixed (`_catalog`, `_global_entities`). Runs on synthetic +
any drop touched in CI.

## 21.3 Replay-side schema drift detector — see [c13](../commits/v01/c13_replay_drift_ci.md)
Guards H-6. **Corrected** test (the original was a no-op — [ADR-5](../DECISIONS.md)):

```python
_REPLAY_STEM = {   # var (sans _COLS) -> schemas stem; identity unless listed
    "RT": "render_targets", "RT_TIMELINE": "rt_event_timeline",
    "STATE_CHANGE": "state_change_events", "COUNTERS": "counters_per_event",
}
_EXPECTED_REPLAY_TABLES = 21

def test_replay_main_schema_in_sync():
    tree = ast.parse((PKG / "replay" / "replay_main.py").read_text())
    replay_tables = _extract_col_tuples(tree, suffix="_COLS", skip={"ID_COLS"})
    assert len(replay_tables) >= _EXPECTED_REPLAY_TABLES, "guard must not match zero"
    for var, cols in replay_tables.items():
        base = var[:-len("_COLS")]
        stem = _REPLAY_STEM.get(base, base.lower())
        assert cols == schemas.expected_columns(stem), f"{var} drifted"
```

## 21.4 Determinism + lint + performance
- **Determinism:** render synthetic twice; outputs byte-identical (catches dict ordering, timestamps).
- **Lint:** every rendered HTML passes `lint.lint_file` (zero hits).
- **Perf:** synthetic render < 2s on CI; flag regressions.

## 21.5 Quality-improving items (opt-in, off by default to preserve parity)
Misclassified UE draws → classifier TOML adds rules (c09); empty-state messages (c16); sparkline
null-gaps (already in `delta.py`, golden-verified); manifest `tool_versions`+`host_info` (c03);
cache SHA256 validation (R-13, c16).

## 21.6 CI matrix (v0.1)
```yaml
strategy:
  matrix:
    os: [windows-latest]
    python: ["3.10", "3.12", "3.13"]     # 3.14 dropped — no pyarrow 17 cp314 wheel (ADR-6)
    pyarrow: ["17", "21"]                # lower + upper of pin range
jobs:
  test:
    steps:
      - pytest tests/unit_*.py
      - pytest tests/parity.py           # golden snapshots
      - pytest tests/schemas.py          # schema regression
      - pytest tests/replay_drift.py     # H-6 drift detector (corrected)
      - pytest tests/determinism.py
      - pytest tests/perf.py
      - bobframes smoke                  # render-only against synthetic
      - bobframes lint tests/data/golden/**/*.html
```

> **Refined by [ADR-11](../DECISIONS.md):** golden byte-parity (`test_parity`) is **pinned to the
> canonical cell** (py3.12 + pyarrow 21) — the rendered HTML embeds env-variable bytes (parquet
> on-disk size by pyarrow version; a percentage's last `.2f` digit by numpy build), so it is only
> byte-identical on the env the golden was baked in. Every other gate (incl. `determinism`, which is
> within-env stable) runs on the full matrix. Real test files are `test_*.py`, not `unit_*.py`.
**Gap (ADR-6):** no GPU/RenderDoc on `windows-latest` → CI never exercises the **ingest** path. The
c03 hardening gets a **mocked-subprocess** unit test so kill/skip/atomic-rename ship tested; full
ingest smoke is self-hosted/nightly (v0.2).

## 21.7 Pre-merge checklist (per PR touching the package)
- [ ] Golden snapshots updated? (only if intentional output change)
- [ ] Schema regression green
- [ ] Replay-drift green
- [ ] Determinism green
- [ ] Lint green
- [ ] Perf within budget
- [ ] CHANGELOG entry if user-visible

## 21.9 Data-extraction guarantee
De-hardcoding does **not** change extraction (renderdoccmd export, qrenderdoc replay, parsers,
parquetize) — identical Parquet for identical `.rdc`. Improvements are in classification correctness,
report polish, operational reliability, and configurability. Parquet contents stay byte-identical
(verified by schema regression + golden tests).
