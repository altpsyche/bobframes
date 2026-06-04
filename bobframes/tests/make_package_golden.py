"""Refresh the `package` shared-asset golden (tests/data/golden_package/shared). Run on an INTENTIONAL
output-changing commit (chrome / CSS / JS / report change), AFTER `make_golden`, then review the diff
page-by-page (ADR-23) before committing:

    python -m bobframes.tests.make_package_golden

Builds the DEFAULT (shared-asset) bundle from the bundled synthetic, extracts it, and writes every
NON-`_data` file into `golden_package/shared/` (HTML normalized to `<TS>` + LF like `make_golden`;
`_pagedata` / `_assets` / `README.txt` as raw text, LF). `_data` parquet is gated by `parquet_digest`
at test time (the writer-version-independent contract, ADR-11/23), so it is never stored. The `inline/`
+ `light/` slices REUSE the render `golden/` (the inline bundle HTML is a byte-identical copy), so only
`shared/` is materialized here (c16s as-built). Mirrors make_golden / make_preview_golden."""
from __future__ import annotations

import os
import shutil
import tempfile
import zipfile

from . import _render_util as u
from .. import package as pkg
from .. import paths as _paths

SHARED_GOLDEN = os.path.join(u.HERE, "data", "golden_package", "shared")
_DATA = _paths.DATA_DIR + "/"


def _extract_top(zip_path: str, dest: str) -> str:
    os.makedirs(dest, exist_ok=True)
    with zipfile.ZipFile(zip_path) as zf:
        zf.extractall(dest)
    return os.path.join(dest, os.listdir(dest)[0])


def main() -> int:
    if os.path.isdir(SHARED_GOLDEN):
        shutil.rmtree(SHARED_GOLDEN)
    with tempfile.TemporaryDirectory(prefix="bobframes_pkg_golden_") as tmp:
        dest = u.render_fresh(os.path.join(tmp, "root"))
        zip_path, _ = pkg.build(dest, out=os.path.join(tmp, "out", "x.zip"), summary_file=False)
        top = _extract_top(zip_path, os.path.join(tmp, "x"))
        n = 0
        for rel in u.tree_files(top):
            if rel == _paths.DATA_DIR or rel.startswith(_DATA):
                continue  # parquet/sidecars gated by parquet_digest at test time, never stored
            src = os.path.join(top, rel)
            data = open(src, encoding="utf-8").read()
            if rel.endswith(".html"):
                data = u.normalize(data)
            out = os.path.join(SHARED_GOLDEN, rel)
            os.makedirs(os.path.dirname(out), exist_ok=True)
            with open(out, "w", encoding="utf-8", newline="\n") as f:
                f.write(data)
            n += 1
    print(f"wrote {n} files under {SHARED_GOLDEN}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
