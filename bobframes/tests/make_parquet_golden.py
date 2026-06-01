"""(Re)generate the committed Parquet-parity golden (`data/golden_parquet/digests.json`).

The golden-parity suite gates rendered HTML (`test_parity`) AND, since c06b (G-14), the rendered
Parquet outputs under `_data/` (`test_parquet_parity`). This script writes the latter's reference:
a writer-INDEPENDENT logical digest per parquet (schema + row order + cell values), NOT the on-disk
bytes (those vary by pyarrow writer version — the D-8 trap). See `_render_util.parquet_digest`.

NOT run in CI. Run by hand ONLY on an intentional data-path output change, then commit the refreshed
digests.json + review the diff in the PR (same discipline as the HTML golden refresh).

Usage (from the venv):
  python -m bobframes.tests.make_parquet_golden
"""
from __future__ import annotations

import json
import os
import tempfile

from . import _render_util as u


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="bobframes_pqgolden_") as tmp:
        root = u.render_fresh(os.path.join(tmp, "root"))
        digests = u.compute_digest_map(root)

    os.makedirs(os.path.dirname(u.GOLDEN_PARQUET_DIGEST), exist_ok=True)
    with open(u.GOLDEN_PARQUET_DIGEST, "w", encoding="utf-8", newline="\n") as f:
        json.dump(digests, f, indent=2, sort_keys=True)
        f.write("\n")
    print(f"wrote {u.GOLDEN_PARQUET_DIGEST}: {len(digests)} parquet tables")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
