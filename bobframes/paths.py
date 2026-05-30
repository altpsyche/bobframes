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


def data_root(root: str) -> str:
    return os.path.join(root, '_data')


def drop_data_dir(root: str, area: str, drop_label_dated: str) -> str:
    """<root>/_data/<area>/<drop>/"""
    return os.path.join(data_root(root), area, drop_label_dated)


def drop_data_dir_tmp(root: str, area: str, drop_label_dated: str) -> str:
    """Staging dir for atomic commit. Renamed to drop_data_dir on success."""
    return drop_data_dir(root, area, drop_label_dated) + '.tmp'


def drop_drill_dir(root: str, area: str, drop_label_dated: str) -> str:
    """<root>/_reports/drill/<area>/<drop>/  (per-drop browser HTML)"""
    return os.path.join(root, '_reports', 'drill', area, drop_label_dated)


def reports_dir(root: str) -> str:
    return os.path.join(root, '_reports')


def reports_cache_dir(root: str) -> str:
    return os.path.join(reports_dir(root), '_cache')


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
    return os.path.join(root, 'index.html')


def drop_dir_rel(area: str, drop_label_dated: str) -> str:
    """Relative path stored in catalog.analysis_out_path column.
    Combine with root via resolve_drop_dir() at read time."""
    return os.path.join('_data', area, drop_label_dated).replace('\\', '/')


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
        i = parts.index('_data')
    except ValueError:
        return drop_dir
    return os.sep.join(parts[:i] + ['_reports', 'drill'] + parts[i + 1:])
