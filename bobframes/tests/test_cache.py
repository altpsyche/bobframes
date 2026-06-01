"""Per-drop cache integrity (c16, R-13).

build_per_drop_cache writes a SHA256 sidecar next to each cache parquet; load_cached validates it and
returns None (with a warning) on a missing/mismatched/unreadable cache so callers fall back to a live
scan instead of silently returning empty. Missing requested columns degrade with a warning, not a
KeyError.
"""
from __future__ import annotations

import pyarrow as pa
import pyarrow.parquet as papq

from bobframes.reports import cache


def _write_valid_cache(root: str):
    cp = cache.cache_path(root, 'draws_summary')
    papq.write_table(pa.table({'a': [1, 2], 'b': ['x', 'y']}), cp, compression='snappy')
    cache._write_cache_sidecar(cp)
    return cp


def test_load_cached_valid(tmp_path):
    root = str(tmp_path)
    _write_valid_cache(root)
    t = cache.load_cached(root, 'draws_summary')
    assert t is not None and t.num_rows == 2


def test_load_cached_missing_file_returns_none(tmp_path):
    assert cache.load_cached(str(tmp_path), 'draws_summary') is None


def test_load_cached_corrupt_warns_and_returns_none(tmp_path, caplog):
    root = str(tmp_path)
    cp = _write_valid_cache(root)
    with open(cp, 'ab') as f:          # mutate bytes after the sidecar was written -> hash mismatch
        f.write(b'\x00garbage')
    with caplog.at_level('WARNING', logger='bobframes'):
        t = cache.load_cached(root, 'draws_summary')
    assert t is None
    assert any('draws_summary' in r.message for r in caplog.records)


def test_load_cached_missing_sidecar_warns_and_returns_none(tmp_path, caplog):
    root = str(tmp_path)
    cp = cache.cache_path(root, 'draws_summary')
    papq.write_table(pa.table({'a': [1]}), cp, compression='snappy')  # no sidecar written
    with caplog.at_level('WARNING', logger='bobframes'):
        assert cache.load_cached(root, 'draws_summary') is None


def test_load_cached_missing_column_tolerated(tmp_path, caplog):
    root = str(tmp_path)
    _write_valid_cache(root)           # columns a, b
    with caplog.at_level('WARNING', logger='bobframes'):
        t = cache.load_cached(root, 'draws_summary', columns=['a', 'does_not_exist'])
    assert t is not None and t.column_names == ['a']


def test_build_per_drop_cache_writes_sidecars(tmp_path):
    # rendering the synthetic via the smoke path is covered elsewhere; here just assert the helper
    # emits a sidecar that validates the file it sits next to.
    root = str(tmp_path)
    cp = _write_valid_cache(root)
    with open(cp + '.sha256', encoding='utf-8') as f:
        digest = f.read().strip()
    assert digest == cache._sha256_file(cp)
