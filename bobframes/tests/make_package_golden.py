"""Refresh the `package` golden trees (tests/data/golden_package/{shared,redacted,shared_redacted}).
Run on an INTENTIONAL output-changing commit (chrome / CSS / JS / report change), AFTER `make_golden`,
then review the diff page-by-page (ADR-23) before committing:

    python -m bobframes.tests.make_package_golden

Builds each variant bundle from the bundled synthetic, extracts it, and writes every NON-`_data` file
into its golden dir (HTML normalized to `<TS>` + LF like `make_golden`; `_pagedata` / `_assets` /
`README.txt` as raw text, LF). `_data` parquet is gated by `parquet_digest` at test time (the
writer-version-independent contract, ADR-11/23), so it is never stored. The `inline/` + `light/` slices
REUSE the render `golden/` (the inline bundle HTML is a byte-identical copy), so they are not stored
here. Variants: `shared/` (c16s/c16t DEFAULT), `redacted/` (c16u `--inline --redact`), `shared_redacted/`
(c16u `--redact`). Mirrors make_golden / make_preview_golden."""
from __future__ import annotations

import os
import shutil
import tempfile
import zipfile

from . import _render_util as u
from .. import package as pkg
from .. import paths as _paths

_GOLDEN_ROOT = os.path.join(u.HERE, "data", "golden_package")
SHARED_GOLDEN = os.path.join(_GOLDEN_ROOT, "shared")
REDACTED_GOLDEN = os.path.join(_GOLDEN_ROOT, "redacted")
SHARED_REDACTED_GOLDEN = os.path.join(_GOLDEN_ROOT, "shared_redacted")
_DATA = _paths.DATA_DIR + "/"

# (golden dir, pkg.build kwargs) -- summary_file=False: the standalone one-pager is not part of the
# bundle tree (gated separately in test_package).
_VARIANTS = [
    (SHARED_GOLDEN, dict(summary_file=False)),
    (REDACTED_GOLDEN, dict(summary_file=False, inline=True, redact=True)),
    (SHARED_REDACTED_GOLDEN, dict(summary_file=False, redact=True)),
]


def _extract_top(zip_path: str, dest: str) -> str:
    os.makedirs(dest, exist_ok=True)
    with zipfile.ZipFile(zip_path) as zf:
        zf.extractall(dest)
    return os.path.join(dest, os.listdir(dest)[0])


def _materialize(top: str, golden_dir: str) -> int:
    n = 0
    for rel in u.tree_files(top):
        if rel == _paths.DATA_DIR or rel.startswith(_DATA):
            continue  # parquet/sidecars gated by parquet_digest at test time, never stored
        data = open(os.path.join(top, rel), encoding="utf-8").read()
        if rel.endswith(".html"):
            data = u.normalize(data)
        out = os.path.join(golden_dir, rel)
        os.makedirs(os.path.dirname(out), exist_ok=True)
        with open(out, "w", encoding="utf-8", newline="\n") as f:
            f.write(data)
        n += 1
    return n


def main() -> int:
    for golden_dir, _kw in _VARIANTS:
        if os.path.isdir(golden_dir):
            shutil.rmtree(golden_dir)
    with tempfile.TemporaryDirectory(prefix="bobframes_pkg_golden_") as tmp:
        dest = u.render_fresh(os.path.join(tmp, "root"))
        for i, (golden_dir, kw) in enumerate(_VARIANTS):
            zip_path, _ = pkg.build(dest, out=os.path.join(tmp, f"out{i}", "x.zip"), **kw)
            top = _extract_top(zip_path, os.path.join(tmp, f"x{i}"))
            n = _materialize(top, golden_dir)
            print(f"wrote {n} files under {golden_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
