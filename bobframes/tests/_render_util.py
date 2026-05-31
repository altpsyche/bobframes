"""Shared helper: render the synthetic fixture into a throwaway root.

`render-only` discovers drops via `discovery.find_drops`, which scans RAW input dirs
(`<root>/<area>/<drop>/*.rdc`) and skips any drop with no `.rdc`. The committed fixture is
`_data`-only (ADR-8), so we fabricate empty `.rdc` stubs in the temp root at render time.
The stubs are never read by render-only (it reads `_data/`) and never committed.
"""
from __future__ import annotations

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
    """Run `bobframes --render-only --root <dest>`; raise on nonzero with captured output."""
    r = subprocess.run(
        [sys.executable, "-m", "bobframes.run", "--render-only", "--root", dest],
        capture_output=True, text=True,
    )
    if r.returncode != 0:
        raise RuntimeError(f"render failed ({r.returncode}):\nSTDOUT:\n{r.stdout}\nSTDERR:\n{r.stderr}")
    return dest


def render_fresh(dest: str, data_src: str = SYNTHETIC_DATA) -> str:
    setup_root(dest, data_src)
    return render(dest)


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
