"""c06: config.resolve_tool precedence, legacy-env deprecation, Arm glob version-pick (H-7).

Hermetic — no real RenderDoc/Arm install needed: env vars are cleared, PATH lookup is stubbed,
and the Arm glob constant is repointed at a tmp tree.
"""

from __future__ import annotations

import logging

import pytest

from bobframes import config
from bobframes.errors import EXIT_TOOL_MISSING, ToolNotFound


def _mk_exe(path) -> str:
    """Create an empty file at `path` (parents made) and return it as a string."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b'')
    return str(path)


@pytest.fixture(autouse=True)
def _isolate(monkeypatch):
    """Clear tool env vars + the one-shot deprecation memo; stub PATH lookup to miss."""
    for var in ('BOBFRAMES_RENDERDOCCMD', 'RENDERDOCCMD',
                'BOBFRAMES_QRENDERDOC', 'RENDERDOC_QRENDERDOC'):
        monkeypatch.delenv(var, raising=False)
    config._warned_legacy.clear()
    monkeypatch.setattr(config.shutil, 'which', lambda name: None)


def test_env_beats_known_paths(monkeypatch, tmp_path):
    # An Arm install is present, but the BOBFRAMES_* env var must still win (step 1 > step 4).
    env_exe = _mk_exe(tmp_path / 'env' / 'renderdoccmd.exe')
    _mk_exe(tmp_path / 'arm' / 'Arm Performance Studio 2026.0'
            / 'renderdoc_for_arm_gpus' / 'renderdoccmd.exe')
    monkeypatch.setattr(config, '_ARM_GLOB',
                        str(tmp_path / 'arm' / 'Arm Performance Studio *'
                            / 'renderdoc_for_arm_gpus' / '{name}.exe'))
    monkeypatch.setenv('BOBFRAMES_RENDERDOCCMD', env_exe)

    assert config.resolve_tool('renderdoccmd') == env_exe


def test_legacy_env_honored_and_warns_once(monkeypatch, tmp_path):
    legacy_exe = _mk_exe(tmp_path / 'renderdoccmd.exe')
    monkeypatch.setenv('RENDERDOCCMD', legacy_exe)

    records: list[logging.LogRecord] = []

    class _Capture(logging.Handler):
        def emit(self, record):
            records.append(record)

    logger = logging.getLogger('bobframes')
    handler = _Capture()
    logger.addHandler(handler)
    try:
        assert config.resolve_tool('renderdoccmd') == legacy_exe
        assert config.resolve_tool('renderdoccmd') == legacy_exe  # second call: no re-warn
    finally:
        logger.removeHandler(handler)

    warns = [r for r in records if 'RENDERDOCCMD' in r.getMessage()]
    assert len(warns) == 1


def test_arm_glob_picks_latest_version(monkeypatch, tmp_path):
    # Includes the two-digit-minor case (2026.10) that a plain lexicographic sort mis-ranks
    # below 2026.2 — the natural-version key (ADR-24) must pick 2026.10.
    arm = tmp_path / 'Arm'
    for ver in ('2025.4', '2026.2', '2026.10'):
        _mk_exe(arm / f'Arm Performance Studio {ver}'
                / 'renderdoc_for_arm_gpus' / 'qrenderdoc.exe')
    monkeypatch.setattr(config, '_ARM_GLOB',
                        str(arm / 'Arm Performance Studio *'
                            / 'renderdoc_for_arm_gpus' / '{name}.exe'))

    resolved = config.resolve_tool('qrenderdoc')
    assert 'Arm Performance Studio 2026.10' in resolved   # latest by natural-version sort
    assert '2026.2' not in resolved
    assert '2025.4' not in resolved


def test_nothing_found_raises_toolnotfound(monkeypatch, tmp_path):
    monkeypatch.setattr(config, '_ARM_GLOB',
                        str(tmp_path / 'none' / 'Arm Performance Studio *' / '{name}.exe'))
    monkeypatch.setattr(config, '_KNOWN_PATH_TEMPLATES', ())

    with pytest.raises(ToolNotFound) as ei:
        config.resolve_tool('renderdoccmd')

    err = ei.value
    assert err.exit_code == EXIT_TOOL_MISSING
    msg = str(err)
    assert 'renderdoccmd' in msg
    assert 'Tried (in order):' in msg
