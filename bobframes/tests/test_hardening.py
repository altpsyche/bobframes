"""c03 reliability hardening — mocked-subprocess unit tests (DECISIONS ADR-6).

CI has no GPU/RenderDoc, so the ingest-path hardening branches (process-tree kill on timeout,
replay-failure skip, atomic writes, stderr surfacing, key versioning) get no coverage from the
golden-parity gate. These drive each branch with fakes instead of real subprocesses.

Named `test_hardening.py` (not the c03 doc's `unit_hardening.py`) so the default-config
`pytest bobframes/tests` collects it — the repo defines no pytest `python_files` override.
"""
from __future__ import annotations

import hashlib
import os
import subprocess

import pyarrow as pa
import pytest

from .. import manifest, parquetize, paths, qrd_harness, rdcmd, run, stable_keys
from ..discovery import Drop


# --- R-4: replay timeout reaps the process tree ------------------------------

def test_qrd_timeout_kills_process_tree(monkeypatch):
    class _FakeTimeoutPopen:
        def __init__(self, *a, **k):
            self.pid = 4242
            self.returncode = None

        def communicate(self, timeout=None):
            raise subprocess.TimeoutExpired(cmd='qrenderdoc', timeout=timeout)

        def wait(self, timeout=None):
            self.returncode = -1
            return -1

    killed: list[list[str]] = []

    def _rec_run(cmd, *a, **k):
        killed.append(cmd)
        return type('R', (), {'returncode': 0})()

    monkeypatch.setattr(qrd_harness, 'find_qrenderdoc', lambda: 'qrenderdoc.exe')
    monkeypatch.setattr(qrd_harness.subprocess, 'Popen', _FakeTimeoutPopen)
    monkeypatch.setattr(qrd_harness.subprocess, 'run', _rec_run)

    rc, elapsed = qrd_harness.run('replay_main.py', payload_args=['a', 'b'],
                                  log_path=None, timeout_s=1)

    assert rc == -1
    assert ['taskkill', '/T', '/F', '/PID', '4242'] in killed


# --- R-6: one capture's replay failure is skipped, not fatal ------------------

def test_replay_failure_skips_and_records_status(monkeypatch, tmp_path):
    def _fake_run(script, payload_args, log_path=None, timeout_s=600.0):
        capture = payload_args[1]
        return (1, 0.1) if capture == '2' else (0, 0.1)

    monkeypatch.setattr(run.qrd_harness, 'run', _fake_run)

    drop = Drop(area='A', drop_date='2026-01-01', drop_label='x',
                drop_dir=str(tmp_path / 'drop'), captures=('1', '2'))
    stage_root = str(tmp_path / 'stage')

    statuses = run._do_replay(drop, stage_root, pixel_grid=4)

    assert statuses == {'1': 'ok', '2': 'replay_failed'}


# --- R-1: manifest write is atomic (no partial file on mid-write crash) -------

def test_write_manifest_atomic_no_partial(monkeypatch, tmp_path):
    def _boom(*a, **k):
        raise RuntimeError('disk full mid-write')

    monkeypatch.setattr(manifest.json, 'dump', _boom)

    with pytest.raises(RuntimeError):
        manifest.write_manifest(str(tmp_path), {'schema_version': 3})

    assert not os.path.exists(tmp_path / paths.MANIFEST_NAME)
    assert not os.path.exists(tmp_path / (paths.MANIFEST_NAME + paths.TMP_SUFFIX))


# --- R-2: Parquet+CSV pair rolls back both tmps if either write fails ---------

def test_write_pair_rolls_back_on_csv_failure(monkeypatch, tmp_path):
    def _boom(*a, **k):
        raise RuntimeError('csv writer exploded')

    monkeypatch.setattr(parquetize.pacsv, 'write_csv', _boom)

    tbl = pa.table({'x': [1, 2, 3]})
    with pytest.raises(RuntimeError):
        parquetize._write_pair(tbl, str(tmp_path), 'foo')

    for leftover in ('foo.parquet', 'foo.csv', 'foo.parquet.tmp', 'foo.csv.tmp'):
        assert not os.path.exists(tmp_path / leftover), f'left behind: {leftover}'


# --- R-8: convert timeout surfaces stderr before re-raising -------------------

def test_convert_timeout_logs_stderr(monkeypatch, capsys):
    def _raise_timeout(*a, **k):
        raise subprocess.TimeoutExpired(cmd=['renderdoccmd'], timeout=1,
                                        output='', stderr='boom-stderr-tail')

    monkeypatch.setattr(rdcmd, 'find_renderdoccmd', lambda: 'renderdoccmd.exe')
    monkeypatch.setattr(rdcmd.subprocess, 'run', _raise_timeout)

    with pytest.raises(subprocess.TimeoutExpired):
        rdcmd.convert('a.rdc', 'b.xml', fmt='xml', timeout_s=1)

    assert 'boom-stderr-tail' in capsys.readouterr().err


# --- R-7: parse surfaces stderr even when the return code is 0 ----------------

def test_parse_one_returns_stderr_on_success(monkeypatch):
    def _fake_run(cmd, *a, **k):
        return type('P', (), {'returncode': 0, 'stdout': 'okout\n', 'stderr': 'warnmsg\n'})()

    monkeypatch.setattr(run.subprocess, 'run', _fake_run)

    capture, elapsed, status, stderr = run._parse_one(
        ('x.zip.xml', 'root/_data/_stage/cap', 'A', '2026-01-01', 'x', 'cap'))

    assert status == 'okout'
    assert stderr == 'warnmsg'


# --- H-27 / G-11: stable keys carry a version byte ---------------------------

def test_stable_key_version_prefix():
    assert stable_keys.KEY_VERSION == 1
    bare = hashlib.sha256(b'x').hexdigest()
    versioned = hashlib.sha256(bytes([1]) + b'x').hexdigest()
    assert stable_keys.shader_key('x') != bare
    assert stable_keys.shader_key('x') == versioned
