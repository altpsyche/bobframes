"""Manifest schema-version guard (c16, D-7 + D-4).

render/catalog/ab must refuse to operate on Parquet written under a different SCHEMA_VERSION, pointing
the user at `bobframes ingest --force`. The guard is parity-neutral until exercised: a current-version
manifest passes (every existing render test stays green).
"""
from __future__ import annotations

import json
import os

import pytest

from bobframes import catalog, manifest, paths, schemas
from bobframes.errors import PipelineError


def _write_manifest(drop_dir: str, schema_version: int) -> None:
    os.makedirs(drop_dir, exist_ok=True)
    m = {
        'schema_version': schema_version,
        'build_timestamp': '2026-01-01T00:00:00+00:00',
        'area': 'Area', 'drop_date': '2026-01-01', 'drop_label': 'r1',
        'captures': ['1'], 'capture_status': {'1': 'ok'},
        'row_counts': {}, 'rotated_from': None,
    }
    with open(os.path.join(drop_dir, paths.MANIFEST_NAME), 'w', encoding='utf-8') as f:
        json.dump(m, f)


def test_check_schema_version_match_no_raise():
    manifest.check_schema_version({'schema_version': schemas.SCHEMA_VERSION})


def test_check_schema_version_mismatch_raises_with_hint():
    with pytest.raises(PipelineError) as ei:
        manifest.check_schema_version({'schema_version': schemas.SCHEMA_VERSION + 1}, source='x')
    assert ei.value.exit_code == 1
    assert 'ingest --force' in str(ei.value)


def test_assert_compatible_match(tmp_path):
    d = str(tmp_path / 'drop')
    _write_manifest(d, schemas.SCHEMA_VERSION)
    manifest.assert_compatible(d)  # no raise


def test_assert_compatible_mismatch(tmp_path):
    d = str(tmp_path / 'drop')
    _write_manifest(d, schemas.SCHEMA_VERSION + 1)
    with pytest.raises(PipelineError):
        manifest.assert_compatible(d)


def test_build_catalog_refuses_stale_schema(tmp_path):
    # render/catalog both route through build_catalog -> the guard fires before any Parquet read.
    root = str(tmp_path)
    drop = os.path.join(paths.data_root(root), 'Area', '2026-01-01_r1')
    _write_manifest(drop, schemas.SCHEMA_VERSION + 1)
    with pytest.raises(PipelineError):
        catalog.build_catalog(root)


def test_build_catalog_accepts_current_schema(tmp_path):
    root = str(tmp_path)
    drop = os.path.join(paths.data_root(root), 'Area', '2026-01-01_r1')
    _write_manifest(drop, schemas.SCHEMA_VERSION)
    catalog.build_catalog(root)  # no raise (empty but compatible)
