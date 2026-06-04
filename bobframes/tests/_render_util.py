"""Shared helper: render the synthetic fixture into a throwaway root.

`render-only` discovers drops via `discovery.find_drops`, which scans RAW input dirs
(`<root>/<area>/<drop>/*.rdc`) and skips any drop with no `.rdc`. The committed fixture is
`_data`-only (ADR-8), so we fabricate empty `.rdc` stubs in the temp root at render time.
The stubs are never read by render-only (it reads `_data/`) and never committed.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import sys

from .. import paths as _paths

HERE = os.path.dirname(__file__)

# The only render-time nondeterminism is the catalog build timestamp on the footer line
# `built <strong>...</strong>` (mixed UTC/local per H-28; c03 will unify). Mask it on both sides.
# (The `Math.random()` table id in chrome.py is client-side JS text — emitted identically.)
_TS_RE = re.compile(r"(built <strong>)[^<]*(</strong>)")


def normalize(html: str) -> str:
    return _TS_RE.sub(r"\1<TS>\2", html)
SYNTHETIC_DATA = os.path.join(HERE, "data", "synthetic", _paths.DATA_DIR)
GOLDEN_DIR = os.path.join(HERE, "data", "golden")
# Preview gallery golden lives OUTSIDE golden/ so test_parity's file-set walk is unaffected (the
# preview page is not produced by render-only). Refresh via tests/make_preview_golden.py (c08).
GOLDEN_PREVIEW = os.path.join(HERE, "data", "golden_preview", "_chrome_preview.html")


def setup_root(dest: str, data_src: str = SYNTHETIC_DATA) -> str:
    """Lay down <dest>/_data (copy of the fixture) + raw .rdc stubs so discovery sees the drops."""
    if os.path.exists(dest):
        shutil.rmtree(dest)
    os.makedirs(dest)
    shutil.copytree(data_src, os.path.join(dest, _paths.DATA_DIR))
    data = os.path.join(dest, _paths.DATA_DIR)
    for area in os.listdir(data):
        area_dir = os.path.join(data, area)
        if area.startswith("_") or not os.path.isdir(area_dir):
            continue
        for drop in os.listdir(area_dir):
            mf = os.path.join(area_dir, drop, _paths.MANIFEST_NAME)
            if not os.path.isfile(mf):
                continue
            with open(mf, encoding="utf-8") as f:
                caps = json.load(f).get("captures") or ["1"]
            raw = os.path.join(dest, area, drop)
            os.makedirs(raw, exist_ok=True)
            for c in caps:
                open(os.path.join(raw, f"{c}.rdc"), "w", encoding="utf-8").close()
    return dest


def render(dest: str) -> str:
    """Run `bobframes --render-only --root <dest>`; raise on nonzero with captured output.

    Scrubs BOBFRAMES_CONFIG from the child env so a developer's user config can't leak into the
    parity render and silently diverge the golden (c07; hermeticity, not gate-narrowing). The temp
    <dest> has no .bobframes.toml, so the config falls back to bundled defaults = today's values.
    """
    env = {k: v for k, v in os.environ.items() if k != "BOBFRAMES_CONFIG"}
    r = subprocess.run(
        [sys.executable, "-m", "bobframes.run", "--render-only", "--root", dest],
        capture_output=True, text=True, env=env,
    )
    if r.returncode != 0:
        raise RuntimeError(f"render failed ({r.returncode}):\nSTDOUT:\n{r.stdout}\nSTDERR:\n{r.stderr}")
    return dest


def render_fresh(dest: str, data_src: str = SYNTHETIC_DATA) -> str:
    setup_root(dest, data_src)
    return render(dest)


def render_preview(dest: str) -> str:
    """Run `bobframes preview <dest>` (c08; no data dependency); return the preview html path.

    Scrubs BOBFRAMES_CONFIG like render() so the gallery is hermetic against a dev's user config.
    """
    os.makedirs(dest, exist_ok=True)
    env = {k: v for k, v in os.environ.items() if k != "BOBFRAMES_CONFIG"}
    r = subprocess.run(
        [sys.executable, "-m", "bobframes.cli", "preview", dest],
        capture_output=True, text=True, env=env,
    )
    if r.returncode != 0:
        raise RuntimeError(f"preview failed ({r.returncode}):\nSTDOUT:\n{r.stdout}\nSTDERR:\n{r.stderr}")
    return os.path.join(_paths.reports_dir(dest), "_chrome_preview.html")


def rendered_html_files(root: str) -> list[str]:
    """Relative paths of every emitted .html under <root> (root index + _reports), sorted.
    Excludes the parquet cache dir."""
    out = []
    for dirpath, _dirs, files in os.walk(root):
        if os.sep + "_cache" in dirpath:
            continue
        for fn in files:
            if fn.endswith(".html"):
                rel = os.path.relpath(os.path.join(dirpath, fn), root).replace("\\", "/")
                if rel.startswith(_paths.DATA_DIR + "/"):
                    continue
                out.append(rel)
    return sorted(out)


def rendered_page_data_files(root: str) -> list[str]:
    """Relative paths of every externalized page-data ``.js`` under <root>, sorted (c16j).

    These are the catalog/drill VTable payloads moved OUT of the HTML into ``_pagedata/<key>.js``
    (ADR-37). Identified by their parent dir basename == ``_paths.PAGEDATA_DIR``, so reports (which
    keep inline data + stay self-contained) contribute nothing. Excludes the report cache dir."""
    out = []
    for dirpath, _dirs, files in os.walk(root):
        if os.sep + _paths.CACHE_DIR in dirpath:
            continue
        if os.path.basename(dirpath) != _paths.PAGEDATA_DIR:
            continue
        for fn in files:
            if fn.endswith(".js"):
                rel = os.path.relpath(os.path.join(dirpath, fn), root).replace("\\", "/")
                out.append(rel)
    return sorted(out)


def rendered_parquet_files(root: str) -> list[str]:
    """Relative paths of every emitted .parquet under <root>/_data, sorted (`\\`->`/`).
    Excludes the report cache dir. Mirror of `rendered_html_files` for the data path (G-14)."""
    out = []
    data_root = _paths.data_root(root)
    for dirpath, _dirs, files in os.walk(data_root):
        if os.sep + _paths.CACHE_DIR in dirpath:
            continue
        for fn in files:
            if fn.endswith(".parquet"):
                rel = os.path.relpath(os.path.join(dirpath, fn), root).replace("\\", "/")
                out.append(rel)
    return sorted(out)


# Stable sentinels for the IEEE non-finite floats that legitimately occur in the data — e.g.
# vbo_samples.as_f32_* reinterprets raw vertex bytes as float32, so a non-float attribute reads
# back as NaN. These are real committed values we WANT to gate (a NaN->number flip is a data-path
# change worth catching); we canonicalize them to a fixed token rather than mask them (allow_nan
# would be the patch-fix). All NaN payloads collapse to one token — logically equal, and NaN bits
# are not a cross-build promise anyway. A dict sentinel can't collide with any str/number/null/list.
_INF = float("inf")


def _nonfinite_to_sentinel(v):
    if isinstance(v, float):
        if v != v:
            return {"__nf__": "nan"}
        if v == _INF:
            return {"__nf__": "inf"}
        if v == -_INF:
            return {"__nf__": "-inf"}
    return v


def parquet_digest(path: str) -> dict:
    """Writer-INDEPENDENT logical digest of one parquet file (G-14, ADR-23).

    Gates schema + row order + cell values WITHOUT touching on-disk bytes (the D-8 trap:
    pyarrow writer version changes compression/encoding but not logical contents). Returns
    {schema: [[name, type_str], ...], num_rows, rows_sha256}. The hash canonicalizes the
    logical table via `to_pydict()` serialized in SCHEMA column order, row order preserved.
    Non-finite floats are mapped to fixed sentinels (see `_nonfinite_to_sentinel`); finite
    floats go through json's shortest round-trip repr, which is stable across CPython 3.10-3.13.
    `allow_nan=False` then guarantees no un-canonicalized non-finite slipped through.
    """
    import pyarrow.parquet as papq

    t = papq.read_table(path)
    schema = [[f.name, str(f.type)] for f in t.schema]
    pydict = t.to_pydict()
    canon = json.dumps(
        [[name, [_nonfinite_to_sentinel(v) for v in pydict[name]]] for name, _ in schema],
        sort_keys=False, ensure_ascii=True, allow_nan=False, separators=(",", ":"),
    )
    return {
        "schema": schema,
        "num_rows": t.num_rows,
        "rows_sha256": hashlib.sha256(canon.encode("utf-8")).hexdigest(),
    }


GOLDEN_PARQUET_DIGEST = os.path.join(HERE, "data", "golden_parquet", "digests.json")


def compute_digest_map(root: str) -> dict:
    """{relpath: parquet_digest} for every rendered parquet under <root>/_data."""
    return {rel: parquet_digest(os.path.join(root, rel))
            for rel in rendered_parquet_files(root)}


def extract_zip(zip_path: str, dest: str) -> str:
    """Extract `zip_path` into `dest`; return `dest`. The c16s package gate reads the tree back out
    of the produced zip (zip bytes are not byte-stable across zlib/Python -- ADR-40)."""
    import zipfile
    with zipfile.ZipFile(zip_path) as zf:
        zf.extractall(dest)
    return dest


def tree_files(root: str) -> list[str]:
    """Relative paths of every file under `root`, sorted (`\\`->`/`). For comparing extracted trees."""
    out = []
    for dirpath, _dirs, files in os.walk(root):
        for fn in files:
            out.append(os.path.relpath(os.path.join(dirpath, fn), root).replace("\\", "/"))
    return sorted(out)
