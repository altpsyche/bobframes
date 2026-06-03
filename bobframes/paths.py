"""Single source of truth for output paths.

Layout (Option A — outputs separated from RDC inputs):

  <root>/
    index.html                          # root catalog VIEW
    <area>/<drop>/                      # raw RDC inputs (untouched)
    _data/                              # pipeline outputs
      _catalog.parquet (+.csv, .json)
      _global_entities.parquet (+.csv)
      _query_examples.md
      <area>/<drop>/                    # per-drop data
        *.parquet (29 tables)
        _manifest.json, _resource_labels.json
        shader_src/*.glsl, histogram/, jsonl sidecars
        done.marker
    _reports/                           # rendered HTML
      *.html (dashboard + 6 reports)
      ab/<pair>/*.html
      drill/<area>/<drop>/index.html    # per-drop browser
      _cache/

Catalog `analysis_out_path` column stores RELATIVE path (e.g. `_data/Police station/2026-05-27_r110565`)
for portability. Reports resolve via resolve_drop_dir(root, analysis_out_path).
"""

from __future__ import annotations

import os

# Layout literals — single source of truth (H-18, H-19). Changing the on-disk
# layout means changing these, nowhere else. Values are frozen for v1; only the
# literals are centralized (parity must stay byte-identical).
DATA_DIR = '_data'           # pipeline outputs root
REPORTS_DIR = '_reports'     # rendered HTML root
CACHE_DIR = '_cache'         # per-project report cache (under _reports/)
STAGE_SUFFIX = '.stage'      # per-drop staging tree; SIBLING of the .tmp commit dir (R-16)
DRILL_DIR = 'drill'          # per-drop browser HTML (under _reports/)
AB_DIR = 'ab'                # A/B report pairs (under _reports/)
RUN_DIR = 'run'              # per-run report pages (under _reports/run/<run_key>/, c16f)
PAGEDATA_DIR = '_pagedata'   # externalized heavy VTable data (.js); sibling of each catalog/drill index.html (c16j)
TMP_SUFFIX = '.tmp'          # atomic-commit staging suffix (dir + file)
MANIFEST_NAME = '_manifest.json'
DONE_MARKER = 'done.marker'
# Written by replay_main.py as its FINAL action, after every output table - before RenderDoc's native
# teardown (ctrl/cap.Shutdown), which can fault (access violation) on some captures. Its presence lets
# the host SALVAGE a nonzero process exit as a complete replay (see run._classify_replay). The literal
# is duplicated in replay_main.py (embedded py3.10 cannot import this module, H-6).
REPLAY_COMPLETE_MARKER = '_replay_complete.marker'
INDEX_HTML = 'index.html'


def data_root(root: str) -> str:
    return os.path.join(root, DATA_DIR)


def drop_dirname(drop_date: str, drop_label: str) -> str:
    """Canonical per-drop dir basename: ``<drop_date>_<drop_label>`` (or just ``<drop_date>``
    when there is no label), the inverse of ``discovery.DATED_RE``.

    Used to tell a live drop dir from a rotation backup / staging dir (R-18): a ``--force`` run
    rotates ``<drop>`` to a SIBLING ``<drop>.<ts>`` (R-16) and the ``.stage``/``.tmp`` trees share
    the prefix, but all of them keep the ORIGINAL manifest/Parquet whose ``drop_label`` is the clean
    value -- so their dir basename no longer equals this reconstruction, while a live drop's does.
    """
    return f'{drop_date}_{drop_label}' if drop_label else drop_date


def drop_data_dir(root: str, area: str, drop_label_dated: str) -> str:
    """<root>/_data/<area>/<drop>/"""
    return os.path.join(data_root(root), area, drop_label_dated)


def drop_data_dir_tmp(root: str, area: str, drop_label_dated: str) -> str:
    """Staging dir for atomic commit. Renamed to drop_data_dir on success."""
    return drop_data_dir(root, area, drop_label_dated) + TMP_SUFFIX


def drop_stage_dir(root: str, area: str, drop_label_dated: str) -> str:
    """Per-drop parse/replay staging tree (CSVs + ``_harness.log`` + sidecars).

    A SIBLING of the ``.tmp`` commit dir, deliberately NOT nested inside it (R-16):
    qrd_harness hands ``_harness.log`` to qrenderdoc as an inheritable stdout handle,
    which a foreign process (e.g. the adb server daemon) can inherit and hold open.
    If the log lived inside ``.tmp`` that held handle would make the atomic
    ``os.replace(tmp, final)`` commit fail with ``[WinError 5]`` after a fully
    successful ingest; as a sibling it can never block the commit.
    """
    return drop_data_dir(root, area, drop_label_dated) + STAGE_SUFFIX


def drop_drill_dir(root: str, area: str, drop_label_dated: str) -> str:
    """<root>/_reports/drill/<area>/<drop>/  (per-drop browser HTML)"""
    return os.path.join(root, REPORTS_DIR, DRILL_DIR, area, drop_label_dated)


def reports_dir(root: str) -> str:
    return os.path.join(root, REPORTS_DIR)


def reports_cache_dir(root: str) -> str:
    return os.path.join(reports_dir(root), CACHE_DIR)


def catalog_parquet(root: str) -> str:
    return os.path.join(data_root(root), '_catalog.parquet')


def catalog_csv(root: str) -> str:
    return os.path.join(data_root(root), '_catalog.csv')


def catalog_json(root: str) -> str:
    return os.path.join(data_root(root), '_catalog.json')


def global_entities_parquet(root: str) -> str:
    return os.path.join(data_root(root), '_global_entities.parquet')


def global_entities_csv(root: str) -> str:
    return os.path.join(data_root(root), '_global_entities.csv')


def query_examples_md(root: str) -> str:
    return os.path.join(data_root(root), '_query_examples.md')


def root_index_html(root: str) -> str:
    return os.path.join(root, INDEX_HTML)


def drop_dir_rel(area: str, drop_label_dated: str) -> str:
    """Relative path stored in catalog.analysis_out_path column.
    Combine with root via resolve_drop_dir() at read time."""
    return os.path.join(DATA_DIR, area, drop_label_dated).replace('\\', '/')


def resolve_drop_dir(root: str, analysis_out_path: str) -> str:
    """Convert catalog's stored path to an absolute drop data dir.
    Tolerates legacy absolute paths for back-compat during migration."""
    if not analysis_out_path:
        return ''
    if os.path.isabs(analysis_out_path):
        return analysis_out_path
    return os.path.join(root, analysis_out_path)


def drop_dir_to_drill_dir(drop_dir: str) -> str:
    """Given absolute <root>/_data/<area>/<drop>, return <root>/_reports/drill/<area>/<drop>.
    Used by report drill-link helpers."""
    parts = os.path.normpath(drop_dir).split(os.sep)
    try:
        i = parts.index(DATA_DIR)
    except ValueError:
        return drop_dir
    return os.sep.join(parts[:i] + [REPORTS_DIR, DRILL_DIR] + parts[i + 1:])
