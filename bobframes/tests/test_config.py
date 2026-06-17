"""c06: config.resolve_tool precedence, legacy-env deprecation, Arm glob version-pick (H-7).
c07: TOML config loader — defaults reproduce today's literals (ADR-6), §6 lookup + deep-merge,
spawn-safe timeout threading, config-driven readers.

Hermetic — no real RenderDoc/Arm install needed: env vars are cleared, PATH lookup is stubbed,
and the Arm glob constant is repointed at a tmp tree.
"""

from __future__ import annotations

import logging
import re
import struct

import pytest

from bobframes import config, discovery, run
from bobframes.errors import EXIT_TOOL_MISSING, ToolNotFound
from bobframes.reports import formatters


def _mk_exe(path) -> str:
    """Create an empty file at `path` (parents made) and return it as a string."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b'')
    return str(path)


@pytest.fixture(autouse=True)
def _isolate(monkeypatch):
    """Clear tool + config env vars, the one-shot memo, and the cached config singleton; stub PATH."""
    for var in ('BOBFRAMES_RENDERDOCCMD', 'RENDERDOCCMD',
                'BOBFRAMES_QRENDERDOC', 'RENDERDOC_QRENDERDOC', 'BOBFRAMES_CONFIG'):
        monkeypatch.delenv(var, raising=False)
    config._warned_legacy.clear()
    config._reset_for_tests()
    monkeypatch.setattr(config.shutil, 'which', lambda name: None)
    yield
    config._reset_for_tests()


# The original (pre-c07) lint.BANNED, frozen here as the parity anchor for the banlist TOML.
_ORIG_BANNED = [
    (r'[—–]', 0, 'em/en dash anywhere'),
    (r'[…]', 0, 'ellipsis unicode'),
    (r'[“”‘’]', 0, 'curly quote'),
    (r'[✓✅↑↓·×⏳→←⚠✨]', 0, 'decorative unicode'),
    (r'\bcaps\b', 0, 'shorthand caps'),
    (r'\bcap\b(?![A-Za-z])', 0, 'shorthand cap'),
    (r'\b(comprehensive|leverage|robust|polished|sleek|seamless)\b', re.I, 'LLM filler vocabulary'),
    (r'\b(overview|insights?|breakdown of|deep dive|key findings)\b', re.I, 'report-prose noun'),
    (r'\b(this (report|chart|table|section) shows|as (you can )?see|as shown|the following|let us|we (can )?see|note that|please note|observe that)\b', re.I, 'reader-address phrase'),
    (r'\b(highlights?|takeaways?|notable|noteworthy|significant|interesting)\b', re.I, 'editorial verb'),
    (r'\b(in conclusion|to summarize|in summary|overall)\b', re.I, 'summary opener'),
    (r'\bN/A\b', 0, 'NA filler'),
    (r'ranks remaining work', re.I, 'LLM filler phrase'),
    (r'\*\*(What to do|Why this matters|Verify|Effort|Impact|Detail|Fix|Severity|Title):\*\*', 0, 'label scaffolding'),
    (r'\betc\.', 0, 'filler etc.'),
]


def _bits(x: float) -> bytes:
    return struct.pack('>d', x)


def test_defaults_equal_literals():
    """ADR-6 parity assertion: bundled defaults reproduce the original in-code literals exactly."""
    cfg = config.get_config()
    # regex / format strings: byte-exact .pattern
    assert re.compile(cfg.discovery.dated_re).pattern == r'^(\d{4}-\d{2}-\d{2})(?:_(.*))?$'
    assert cfg.formatting.chrome_scrub_chars == r'[—–…“”‘’→←↑↓×·]'
    assert cfg.delta.fmt == '{:+,.0f}'
    # ints
    assert cfg.formatting.id_short_n == 12
    assert cfg.formatting.text_trunc_max == 60
    # floats bit-for-bit (tomllib must parse them identically to the Python literals)
    assert _bits(cfg.delta.bar_label_min_pct) == _bits(8.0)
    assert _bits(cfg.pipeline.replay_timeout_s) == _bits(600.0)
    assert _bits(cfg.pipeline.convert_timeout_s) == _bits(120.0)
    cx = cfg.scoring.complexity
    for got, want in [(cx.w_texture_samples, 2.0), (cx.w_branches, 0.5), (cx.w_loops, 2.0),
                      (cx.w_discards, 0.3), (cx.w_dfdx_dfdy, 0.5), (cx.w_mat4, 0.3),
                      (cx.src_len_divisor, 100.0), (cx.src_len_cap, 50.0)]:
        assert _bits(got) == _bits(want)


def test_report_thresholds_defaults():
    """c16: the bundled [report] thresholds load bit-for-bit equal to the ReportCfg defaults."""
    r = config.get_config().report
    for got, want in [(r.shader_complexity_high, 60.0),
                      (r.overdraw_reject_warn_pct, 40.0),
                      (r.overdraw_reject_alarm_pct, 70.0),
                      (r.gpu_regression_pct, 10.0),
                      # H-41 — per-KPI trend thresholds; defaults reproduce the old KPIS literals.
                      (r.draws_regression_pct, 10.0),
                      (r.vbo_regression_pct, 15.0),
                      (r.ibo_regression_pct, 15.0),
                      (r.program_switches_regression_pct, 20.0)]:
        assert _bits(got) == _bits(want)
    assert r.instancing_repeat_min == 4
    assert r.max_prerendered_runs == 10        # c16f — per-run page cap


def test_banlist_roundtrip_matches_code():
    """The lint_banlist.toml compiles to the exact original BANNED list, in order (H-14)."""
    bl = config.banlist()
    assert len(bl) == len(_ORIG_BANNED) == 15
    for (rx, label), (pat, flags, lbl) in zip(bl, _ORIG_BANNED):
        assert rx.pattern == pat
        assert rx.flags == re.compile(pat, flags).flags
        assert label == lbl


def test_chrome_scrub_alias_equals_default():
    """The back-compat _BANNED_CHROME_CHARS alias equals the config default (single source, H-16)."""
    assert formatters._BANNED_CHROME_CHARS.pattern == config.get_config().formatting.chrome_scrub_chars


def test_user_file_deep_merge(tmp_path):
    """A user file overriding one key keeps every other default (ADR-25 deep-merge)."""
    (tmp_path / '.bobframes.toml').write_text(
        '[scoring.complexity]\nw_loops = 9.0\n', encoding='utf-8')
    cfg = config.load_config(str(tmp_path))
    assert cfg.scoring.complexity.w_loops == 9.0           # overridden
    assert cfg.scoring.complexity.w_branches == 0.5        # sibling default kept
    assert cfg.pipeline.replay_timeout_s == 600.0          # untouched section kept


def test_env_config_path_beats_project_file(tmp_path, monkeypatch):
    """$BOBFRAMES_CONFIG wins over <root>/.bobframes.toml (§6 first-found order)."""
    (tmp_path / '.bobframes.toml').write_text(
        '[pipeline]\nreplay_timeout_s = 111.0\n', encoding='utf-8')
    env_cfg = tmp_path / 'elsewhere.toml'
    env_cfg.write_text('[pipeline]\nreplay_timeout_s = 222.0\n', encoding='utf-8')
    monkeypatch.setenv('BOBFRAMES_CONFIG', str(env_cfg))
    cfg = config.load_config(str(tmp_path))
    assert cfg.pipeline.replay_timeout_s == 222.0


def test_timeout_file_overrides_default(tmp_path):
    """config file > built-in default for the timeouts (H-12/H-13)."""
    (tmp_path / '.bobframes.toml').write_text(
        '[pipeline]\nreplay_timeout_s = 7.5\nconvert_timeout_s = 3.0\n', encoding='utf-8')
    cfg = config.load_config(str(tmp_path))
    assert cfg.pipeline.replay_timeout_s == 7.5
    assert cfg.pipeline.convert_timeout_s == 3.0


def test_dated_re_config_driven(tmp_path):
    """discovery._dated_re() recompiles from config; module-level DATED_RE fallback still exists (H-30)."""
    assert hasattr(discovery, 'DATED_RE')   # back-compat name preserved
    (tmp_path / '.bobframes.toml').write_text(
        "[discovery]\ndated_re = '^DROP-(.+)$'\n", encoding='utf-8')
    config.load_config(str(tmp_path))
    pat = discovery._dated_re()
    assert pat.pattern == '^DROP-(.+)$'
    assert pat.match('DROP-x')
    assert not pat.match('2026-05-27')


def test_convert_timeout_threaded_as_argument(monkeypatch):
    """The resolved convert timeout reaches rdcmd.convert as an explicit arg (spawn-safe, H-13).

    Read from config inside the spawned pool worker would silently miss the override (Windows
    spawn re-imports), so the value must flow as a function argument; None falls back to rdcmd's
    own default (the safety net).
    """
    calls: list[float] = []

    def fake_convert(rdc, out, fmt='xml', timeout_s=120.0):
        calls.append(timeout_s)
        return 0.0

    monkeypatch.setattr(run.rdcmd, 'needs_export', lambda a, b: True)
    monkeypatch.setattr(run.rdcmd, 'convert', fake_convert)

    run._export_one('/x/1.rdc', convert_timeout=42.0)
    assert calls == [42.0, 42.0]          # both formats got the resolved override
    calls.clear()
    run._export_one('/x/1.rdc')           # None -> rdcmd default safety net
    assert calls == [120.0, 120.0]


def test_write_config_stub(tmp_path):
    """check --write-config writes a starter once, then skips if present (no overwrite)."""
    path, written = config.write_config_stub(str(tmp_path))
    assert written and (tmp_path / '.bobframes.toml').is_file()
    body = (tmp_path / '.bobframes.toml').read_text(encoding='utf-8')
    assert '[tools]' in body
    path2, written2 = config.write_config_stub(str(tmp_path))
    assert path2 == path and written2 is False
    assert (tmp_path / '.bobframes.toml').read_text(encoding='utf-8') == body  # untouched


# --- c1c: [theme] user color override parse (ADR-45) -------------------------

def test_theme_parse_allowlisted(tmp_path):
    """A [theme] with an allowlisted color key lands in Config.theme (deep-merged via the §6 cascade)."""
    (tmp_path / '.bobframes.toml').write_text(
        "[theme]\naccent_primary = 'light-dark(oklch(55% 0.15 264), oklch(72% 0.13 264))'\n",
        encoding='utf-8')
    cfg = config.load_config(str(tmp_path))
    assert cfg.theme is not None
    assert cfg.theme.as_dict()['accent_primary'] == \
        'light-dark(oklch(55% 0.15 264), oklch(72% 0.13 264))'


def test_theme_rejects_non_color_key(tmp_path, caplog):
    """A non-color key (layout/spacing/radius/type) is OUTSIDE the allowlist -> warned + dropped, so a
    user can never desync density / parity machinery via [theme]."""
    (tmp_path / '.bobframes.toml').write_text(
        "[theme]\nradius = '999px'\naccent_primary = 'oklch(50% 0 0)'\n", encoding='utf-8')
    with caplog.at_level(logging.WARNING, logger='bobframes'):
        cfg = config.load_config(str(tmp_path))
    d = cfg.theme.as_dict()
    assert 'radius' not in d and d.get('accent_primary') == 'oklch(50% 0 0)'
    assert any('radius' in r.getMessage() for r in caplog.records)


def test_theme_rejects_bad_value(tmp_path, caplog):
    """Values must be ASCII + free of ;{} (CSS-injection guard); a bad value is warned + dropped (here
    the only key, so Config.theme collapses to None -> the byte-identical default path)."""
    (tmp_path / '.bobframes.toml').write_text(
        "[theme]\naccent_primary = 'red; } body{display:none}'\n", encoding='utf-8')
    with caplog.at_level(logging.WARNING, logger='bobframes'):
        cfg = config.load_config(str(tmp_path))
    assert cfg.theme is None


def test_theme_none_when_absent(tmp_path):
    """No [theme] -> Config.theme is None (the default render path stays byte-identical)."""
    (tmp_path / '.bobframes.toml').write_text(
        '[pipeline]\nreplay_timeout_s = 1.0\n', encoding='utf-8')
    assert config.load_config(str(tmp_path)).theme is None


def test_theme_for_render_cli_beats_config(tmp_path):
    """--accent (CLI) overrides [theme].accent_primary (config) -- the §6 precedence holds for theme."""
    (tmp_path / '.bobframes.toml').write_text(
        "[theme]\naccent_primary = 'oklch(50% 0 0)'\naccent_data = 'oklch(60% 0.1 200)'\n",
        encoding='utf-8')
    cfg = config.load_config(str(tmp_path))
    merged = config.theme_for_render(cfg, accent='oklch(30% 0 0)')
    assert merged['accent_primary'] == 'oklch(30% 0 0)'    # CLI wins
    assert merged['accent_data'] == 'oklch(60% 0.1 200)'   # config sibling kept
    assert config.theme_for_render(config.Config()) is None  # nothing to override -> default path


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


# --- c10: getenv_legacy (BOBFRAMES_* with one-release RDC_* fallback) ----------

def test_getenv_legacy_prefers_canonical(monkeypatch):
    monkeypatch.setenv('BOBFRAMES_PIXEL_GRID', '8')
    monkeypatch.setenv('RDC_PIXEL_GRID', '4')
    assert config.getenv_legacy('BOBFRAMES_PIXEL_GRID', 'RDC_PIXEL_GRID') == '8'


def test_getenv_legacy_falls_back_and_warns_once(monkeypatch):
    monkeypatch.delenv('BOBFRAMES_KEEP_STAGE', raising=False)
    monkeypatch.setenv('RDC_KEEP_STAGE', '1')

    records: list[logging.LogRecord] = []

    class _Capture(logging.Handler):
        def emit(self, record):
            records.append(record)

    logger = logging.getLogger('bobframes')
    handler = _Capture()
    logger.addHandler(handler)
    try:
        assert config.getenv_legacy('BOBFRAMES_KEEP_STAGE', 'RDC_KEEP_STAGE') == '1'
        assert config.getenv_legacy('BOBFRAMES_KEEP_STAGE', 'RDC_KEEP_STAGE') == '1'  # no re-warn
    finally:
        logger.removeHandler(handler)

    warns = [r for r in records if 'RDC_KEEP_STAGE' in r.getMessage()]
    assert len(warns) == 1


def test_getenv_legacy_default_when_unset(monkeypatch):
    monkeypatch.delenv('BOBFRAMES_PIXEL_GRID', raising=False)
    monkeypatch.delenv('RDC_PIXEL_GRID', raising=False)
    assert config.getenv_legacy('BOBFRAMES_PIXEL_GRID', 'RDC_PIXEL_GRID', '4') == '4'
    assert config.getenv_legacy('BOBFRAMES_PIXEL_GRID', 'RDC_PIXEL_GRID') is None


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
