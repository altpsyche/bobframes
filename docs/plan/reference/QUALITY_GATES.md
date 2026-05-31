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
