"""Parquet-output parity (G-14): rendering the synthetic fixture reproduces the frozen golden
Parquet outputs under `_data/`. The data-path twin of `test_parity` (which gates HTML only and
explicitly skips `_data`/`_cache`, so c05's `_global_entities` row-order shift slipped ungated).

The gate is on the LOGICAL contents — schema + row order + cell values — via a writer-independent
digest (`_render_util.parquet_digest`), NOT on-disk bytes (those vary by pyarrow writer version, the
D-8 trap). That lets this run on the FULL CI matrix, unlike HTML parity which ADR-11 pins to one
cell. Refresh the golden with `python -m bobframes.tests.make_parquet_golden` on an intentional
data-path change (same discipline as the HTML golden)."""
from __future__ import annotations

import json

from . import _render_util as u


def test_rendered_parquet_matches_golden(tmp_path):
    dest = u.render_fresh(str(tmp_path / "root"))
    actual = u.compute_digest_map(dest)
    with open(u.GOLDEN_PARQUET_DIGEST, encoding="utf-8") as f:
        golden = json.load(f)

    # (1) file-set parity — catches added/removed/renamed tables (mirror of test_parity's check).
    assert set(actual) == set(golden), (
        f"gated parquet set changed vs golden: {set(actual) ^ set(golden)}"
    )

    # (2) per-table digest — schema, row order, cell values.
    for rel in sorted(golden):
        a, g = actual[rel], golden[rel]
        drift = [k for k in ("schema", "num_rows", "rows_sha256") if a[k] != g[k]]
        assert not drift, (
            f"{rel} diverged from golden in {drift} "
            f"(num_rows {a['num_rows']} vs {g['num_rows']}; "
            f"refresh intentionally via `python -m bobframes.tests.make_parquet_golden`)"
        )
