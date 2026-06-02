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


def test_classify_replay_salvages_crash_on_teardown():
    # rc==0 is always ok; a nonzero exit is salvaged ONLY if the completion marker is present
    # (replay_main wrote all output, then qrenderdoc faulted on native shutdown).
    assert run._classify_replay(0, complete=True) == 'ok'
    assert run._classify_replay(0, complete=False) == 'ok'
    assert run._classify_replay(3221225477, complete=True) == 'replay_dirty_exit'   # 0xC0000005
    assert run._classify_replay(1, complete=False) == 'replay_failed'


def test_replay_dirty_exit_salvaged_when_marker_present(monkeypatch, tmp_path):
    """Regression (real Perf ingest, 2026-06-02): qrenderdoc replays a capture fully, writes every
    table + the completion marker, then crashes on native teardown (rc=0xC0000005). The host must
    salvage that (status replay_dirty_exit), not discard complete data as replay_failed."""
    def _fake_run(script, payload_args, log_path=None, timeout_s=600.0):
        capture, stage_root = payload_args[1], payload_args[5]
        if capture == '1':   # wrote the marker (complete) THEN faulted on exit
            with open(os.path.join(stage_root, capture, paths.REPLAY_COMPLETE_MARKER),
                      'w', encoding='utf-8') as f:
                f.write('draws=10\n')
            return (3221225477, 1.0)
        return (3221225477, 1.0)   # capture '2': crash with NO marker -> genuine failure

    monkeypatch.setattr(run.qrd_harness, 'run', _fake_run)
    drop = Drop(area='A', drop_date='2026-01-01', drop_label='x',
                drop_dir=str(tmp_path / 'drop'), captures=('1', '2'))
    statuses = run._do_replay(drop, str(tmp_path / 'stage'), pixel_grid=4)
    assert statuses == {'1': 'replay_dirty_exit', '2': 'replay_failed'}


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
    seen = {}

    def _fake_run(cmd, *a, **k):
        seen['cwd'] = k.get('cwd')
        return type('P', (), {'returncode': 0, 'stdout': 'okout\n', 'stderr': 'warnmsg\n'})()

    monkeypatch.setattr(run.subprocess, 'run', _fake_run)

    # 7-tuple: project_root rides as the explicit child cwd (c10; RDC_ROOT eliminated, R-5/Q-5).
    capture, elapsed, status, stderr = run._parse_one(
        ('x.zip.xml', 'root/_data/_stage/cap', 'A', '2026-01-01', 'x', 'cap', '/proj/root'))

    assert status == 'okout'
    assert stderr == 'warnmsg'
    assert seen['cwd'] == '/proj/root'


def test_do_parse_leaves_environ_untouched(monkeypatch, tmp_path):
    """R-5: parse must not mutate the process env (no global RDC_ROOT leak across drops)."""
    class _FakeExecutor:
        def __init__(self, *a, **k):
            pass
        def __enter__(self):
            return self
        def __exit__(self, *a):
            return False
        def map(self, fn, args):
            # Return one ok status per submitted arg without running a real subprocess.
            return [(a[5], 0.0, 'ok', '') for a in args]

    monkeypatch.setattr(run.cf, 'ProcessPoolExecutor', _FakeExecutor)
    drop = Drop(area='A', drop_date='2026-01-01', drop_label='x',
                drop_dir=str(tmp_path / 'A' / '2026-01-01_x'), captures=('1', '2'))

    before = dict(os.environ)
    run._do_parse(drop, str(tmp_path / 'stage'), workers=2, project_root=str(tmp_path))
    assert dict(os.environ) == before
    assert 'RDC_ROOT' not in os.environ


# --- H-27 / G-11: stable keys carry a version byte ---------------------------

def test_stable_key_version_prefix():
    assert stable_keys.KEY_VERSION == 1
    bare = hashlib.sha256(b'x').hexdigest()
    versioned = hashlib.sha256(bytes([1]) + b'x').hexdigest()
    assert stable_keys.shader_key('x') != bare
    assert stable_keys.shader_key('x') == versioned


# --- R-16: stage tree (with _harness.log) lives OUTSIDE the atomic-commit dir ----

def test_stage_dir_is_sibling_not_inside_commit_dir():
    """A held _harness.log handle (e.g. inherited by adb) must never block the commit.
    The stage tree must not be nested inside the .tmp dir that os.replace renames."""
    root, area, drop = 'R', 'A', '2026-01-01_x'
    tmp = os.path.normpath(paths.drop_data_dir_tmp(root, area, drop))
    final = os.path.normpath(paths.drop_data_dir(root, area, drop))
    stage = os.path.normpath(paths.drop_stage_dir(root, area, drop))
    assert not stage.startswith(tmp + os.sep), 'stage must not be inside the .tmp commit dir'
    assert not stage.startswith(final + os.sep), 'stage must not be inside the committed dir'
    assert stage not in (tmp, final)
