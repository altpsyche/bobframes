"""External-tool resolution (ARCHITECTURE §5) and the TOML config layer (§6).

``resolve_tool(name)`` finds ``renderdoccmd`` / ``qrenderdoc`` with the precedence:

    BOBFRAMES_* env  >  [tools] config  >  PATH  >  known Windows paths  >  ToolNotFound

Legacy ``RENDERDOCCMD`` / ``RENDERDOC_QRENDERDOC`` env vars are still honored, with a one-shot
deprecation warning.

The config layer (c07) loads a ``Config`` dataclass from bundled defaults
(``_default_config.toml`` + ``lint_banlist.toml``) deep-merged with the first user file found in the
§6 lookup ($BOBFRAMES_CONFIG > <root>/.bobframes.toml > %APPDATA%/bobframes/config.toml). The bundled
TOML is the single source of truth for every de-hardcoded literal; defaults reproduce today's output
byte-identically (ADR-6). Value precedence: CLI flag > env > config file > built-in default.

``tomllib`` is stdlib only on Python 3.11+. The package floor is 3.10 because qrenderdoc embeds
Python 3.10 (the replay stage runs there); ``tomli`` is the conditional backport for that cell
(ADR-26).

Windows-only in v1 (§5/§12): the ``.exe`` suffix and the known paths below are intentionally
hardcoded. c06 keeps them in the ``_ARM_GLOB`` / ``_KNOWN_PATH_TEMPLATES`` constants so the
cross-platform commit (c36) can branch them per-OS without rewriting ``_candidates``.
"""

from __future__ import annotations

import functools
import glob
import logging
import os
import re
import shutil
from dataclasses import dataclass
from importlib.resources import files

try:
    import tomllib  # Python 3.11+
except ModuleNotFoundError:  # pragma: no cover - exercised on the py3.10 CI cell via tomli
    import tomli as tomllib  # backport for qrenderdoc's embedded 3.10 (ADR-26)

from .errors import BobFramesError, EXIT_USER_ERROR, ToolNotFound

# tool name -> (canonical env var, legacy env var honored one more release)
_ENV_VARS = {
    'renderdoccmd': ('BOBFRAMES_RENDERDOCCMD', 'RENDERDOCCMD'),
    'qrenderdoc': ('BOBFRAMES_QRENDERDOC', 'RENDERDOC_QRENDERDOC'),
}

# Known install paths (Windows). c36 branches these per-OS; do not "fix" the .exe here early.
# Arm Performance Studio bumps quarterly, so the version dir is globbed and the latest picked
# by directory-name sort (H-7).
_ARM_GLOB = 'C:/Program Files/Arm/Arm Performance Studio */renderdoc_for_arm_gpus/{name}.exe'
_KNOWN_PATH_TEMPLATES = (
    'C:/Program Files/RenderDoc/{name}.exe',
    '{LOCALAPPDATA}/Programs/RenderDoc/{name}.exe',
)

# Bundled-config resource names (shipped in the package via packages=["bobframes"]).
_DEFAULT_CONFIG_TOML = '_default_config.toml'
_LINT_BANLIST_TOML = 'lint_banlist.toml'

_warned_legacy: set[str] = set()


# --- config dataclasses (§6) -------------------------------------------------

@dataclass(frozen=True)
class ToolsCfg:
    renderdoccmd: str | None = None
    qrenderdoc: str | None = None


@dataclass(frozen=True)
class PipelineCfg:
    replay_timeout_s: float = 600.0    # H-12
    convert_timeout_s: float = 120.0   # H-13


@dataclass(frozen=True)
class DiscoveryCfg:
    dated_re: str = r'^(\d{4}-\d{2}-\d{2})(?:_(.*))?$'   # H-30


@dataclass(frozen=True)
class FormattingCfg:
    id_short_n: int = 12                                 # H-23
    text_trunc_max: int = 60                             # H-23
    chrome_scrub_chars: str = r'[—–…“”‘’→←↑↓×·]'         # H-16


@dataclass(frozen=True)
class DeltaCfg:
    fmt: str = '{:+,.0f}'        # H-22
    bar_label_min_pct: float = 8.0   # H-21


@dataclass(frozen=True)
class ComplexityCfg:               # H-17 / Q-3
    w_texture_samples: float = 2.0
    w_branches: float = 0.5
    w_loops: float = 2.0
    w_discards: float = 0.3
    w_dfdx_dfdy: float = 0.5
    w_mat4: float = 0.3
    src_len_divisor: float = 100.0
    src_len_cap: float = 50.0


@dataclass(frozen=True)
class ScoringCfg:
    # Parent-with-subsection so c21 can add ``regression`` / ``gating`` by extension (ARCHITECTURE §6).
    complexity: ComplexityCfg = ComplexityCfg()


@dataclass(frozen=True)
class LintCfg:
    # User-appended [[banned]] entries; the default banlist lives in lint_banlist.toml.
    extra_banned: tuple[tuple[str, str, tuple[str, ...]], ...] = ()


@dataclass(frozen=True)
class ClassifierCfg:                  # c09 — selects the draw-classifier preset (H-1..H-5)
    preset: str = 'ue'                # 'ue' -> draw_classifier.toml; '<name>' -> presets/<name>.toml
    custom_path: str | None = None    # absolute path to a custom classifier TOML (wins over preset)


@dataclass(frozen=True)
class ReportCfg:                      # c16 — report-presentation thresholds (callout severity)
    shader_complexity_high: float = 60.0
    overdraw_reject_warn_pct: float = 40.0
    overdraw_reject_alarm_pct: float = 70.0
    instancing_repeat_min: int = 4
    gpu_regression_pct: float = 10.0
    max_prerendered_runs: int = 10    # c16f — cap on pre-rendered older-run pages (per-run UX)


@dataclass(frozen=True)
class Config:
    schema_version: int = 1
    tools: ToolsCfg = ToolsCfg()
    pipeline: PipelineCfg = PipelineCfg()
    discovery: DiscoveryCfg = DiscoveryCfg()
    formatting: FormattingCfg = FormattingCfg()
    delta: DeltaCfg = DeltaCfg()
    scoring: ScoringCfg = ScoringCfg()
    lint: LintCfg = LintCfg()
    classifier: ClassifierCfg = ClassifierCfg()
    report: ReportCfg = ReportCfg()


class ConfigError(BobFramesError):
    """A user config file is missing/unreadable/invalid TOML."""

    exit_code = EXIT_USER_ERROR


# --- loader (§6) -------------------------------------------------------------

def _load_toml_text(name: str) -> dict:
    """Parse a bundled package TOML resource into a dict (read-only text, no temp extraction)."""
    text = files('bobframes').joinpath(name).read_text(encoding='utf-8')
    return tomllib.loads(text)


def _deep_merge(base: dict, over: dict) -> dict:
    """Recursively merge ``over`` onto a copy of ``base`` (over wins; sub-tables merge per key)."""
    out = dict(base)
    for k, v in over.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = v
    return out


def _find_user_config_file(root: str | None) -> str | None:
    """First-found user config per §6 (no merging of the three locations)."""
    env_path = os.environ.get('BOBFRAMES_CONFIG', '').strip()
    if env_path:
        return env_path
    if root:
        proj = os.path.join(root, '.bobframes.toml')
        if os.path.isfile(proj):
            return proj
    appdata = os.environ.get('APPDATA')
    if appdata:
        user = os.path.join(appdata, 'bobframes', 'config.toml')
        if os.path.isfile(user):
            return user
    return None


def _banned_entries(raw: list) -> tuple[tuple[str, str, tuple[str, ...]], ...]:
    """Normalize ``[[banned]]`` array-of-tables to ``(pattern, label, flags)`` tuples (order kept)."""
    out = []
    for e in raw:
        out.append((e['pattern'], e.get('label', ''), tuple(e.get('flags', ()))))
    return tuple(out)


def _build_config(root: str | None) -> Config:
    """Build the active ``Config``: bundled defaults, deep-merged with the first user file (§6)."""
    base = _load_toml_text(_DEFAULT_CONFIG_TOML)
    user_path = _find_user_config_file(root)
    if user_path:
        try:
            with open(user_path, 'rb') as f:
                user = tomllib.load(f)
        except FileNotFoundError as e:
            raise ConfigError(f'config file not found: {user_path}') from e
        except tomllib.TOMLDecodeError as e:
            raise ConfigError(f'invalid TOML in {user_path}: {e}') from e
        merged = _deep_merge(base, user)
    else:
        merged = base

    tools = merged.get('tools', {})
    pipe = merged.get('pipeline', {})
    disc = merged.get('discovery', {})
    fmt = merged.get('formatting', {})
    dlt = merged.get('delta', {})
    cx = merged.get('scoring', {}).get('complexity', {})
    lint = merged.get('lint', {})
    cls = merged.get('classifier', {})
    rpt = merged.get('report', {})

    return Config(
        schema_version=merged.get('schema_version', 1),
        tools=ToolsCfg(renderdoccmd=tools.get('renderdoccmd'), qrenderdoc=tools.get('qrenderdoc')),
        pipeline=PipelineCfg(
            replay_timeout_s=pipe.get('replay_timeout_s', 600.0),
            convert_timeout_s=pipe.get('convert_timeout_s', 120.0),
        ),
        discovery=DiscoveryCfg(dated_re=disc.get('dated_re', DiscoveryCfg.dated_re)),
        formatting=FormattingCfg(
            id_short_n=fmt.get('id_short_n', 12),
            text_trunc_max=fmt.get('text_trunc_max', 60),
            chrome_scrub_chars=fmt.get('chrome_scrub_chars', FormattingCfg.chrome_scrub_chars),
        ),
        delta=DeltaCfg(
            fmt=dlt.get('fmt', '{:+,.0f}'),
            bar_label_min_pct=dlt.get('bar_label_min_pct', 8.0),
        ),
        scoring=ScoringCfg(complexity=ComplexityCfg(
            w_texture_samples=cx.get('w_texture_samples', 2.0),
            w_branches=cx.get('w_branches', 0.5),
            w_loops=cx.get('w_loops', 2.0),
            w_discards=cx.get('w_discards', 0.3),
            w_dfdx_dfdy=cx.get('w_dfdx_dfdy', 0.5),
            w_mat4=cx.get('w_mat4', 0.3),
            src_len_divisor=cx.get('src_len_divisor', 100.0),
            src_len_cap=cx.get('src_len_cap', 50.0),
        )),
        lint=LintCfg(extra_banned=_banned_entries(lint.get('extra_banned', []))),
        classifier=ClassifierCfg(
            preset=cls.get('preset', 'ue'),
            custom_path=cls.get('custom_path'),
        ),
        report=ReportCfg(
            shader_complexity_high=rpt.get('shader_complexity_high', 60.0),
            overdraw_reject_warn_pct=rpt.get('overdraw_reject_warn_pct', 40.0),
            overdraw_reject_alarm_pct=rpt.get('overdraw_reject_alarm_pct', 70.0),
            instancing_repeat_min=rpt.get('instancing_repeat_min', 4),
            gpu_regression_pct=rpt.get('gpu_regression_pct', 10.0),
            max_prerendered_runs=rpt.get('max_prerendered_runs', 10),
        ),
    )


_ACTIVE: Config | None = None


def load_config(root: str | None = None) -> Config:
    """Build the active config from the §6 lookup and cache it. Call once at CLI entry."""
    global _ACTIVE
    _ACTIVE = _build_config(root)
    return _ACTIVE


def get_config() -> Config:
    """Return the active config, lazily loading bundled defaults (root=cwd) on first use."""
    global _ACTIVE
    if _ACTIVE is None:
        _ACTIVE = _build_config(os.getcwd())
    return _ACTIVE


def _reset_for_tests() -> None:
    """Drop the cached config + compiled-pattern caches. Test seam only."""
    global _ACTIVE
    _ACTIVE = None
    banlist.cache_clear()


_RE_FLAGS = {'I': re.I, 'M': re.M, 'S': re.S, 'X': re.X, 'A': re.A}


def _compile_banned(entries) -> list[tuple[re.Pattern, str]]:
    out = []
    for pattern, label, flags in entries:
        f = 0
        for name in flags:
            f |= _RE_FLAGS[name]
        out.append((re.compile(pattern, f), label))
    return out


@functools.lru_cache(maxsize=1)
def banlist() -> list[tuple[re.Pattern, str]]:
    """Default banned tokens (lint_banlist.toml) + ``[lint].extra_banned``, in order (H-14)."""
    raw = _load_toml_text(_LINT_BANLIST_TOML).get('banned', [])
    default = _banned_entries(raw)
    return _compile_banned(default + get_config().lint.extra_banned)


def _version_key(path: str) -> list:
    """Natural sort key: split digit runs into ints so '2026.10' > '2026.2' (ADR-24).

    Plain lexicographic sort (the original §5 wording) mis-ranks once a minor reaches two
    digits ('2026.2' > '2026.10' as strings). This realizes the same "pick the latest install"
    intent correctly regardless of minor width.
    """
    return [int(tok) if tok.isdigit() else tok for tok in re.split(r'(\d+)', path)]


def _warn_legacy_once(legacy: str, canonical: str) -> None:
    """Emit the legacy-env-var deprecation warning at most once per process."""
    if legacy in _warned_legacy:
        return
    _warned_legacy.add(legacy)
    logging.getLogger('bobframes').warning(
        '%s is deprecated; use %s instead.', legacy, canonical)


def getenv_legacy(canonical: str, legacy: str, default: str | None = None) -> str | None:
    """Read ``$canonical``, falling back to the deprecated ``$legacy`` for one release.

    Returns the canonical value if set; else the legacy value (with a one-shot deprecation
    warning, shared with the tool-env path via ``_warned_legacy``); else ``default``. The
    single source for the c10 env-rename cadence (``BOBFRAMES_PIXEL_GRID``/``BOBFRAMES_KEEP_STAGE``),
    matching the ``_candidates`` precedence used for the tool vars (renderdoccmd/qrenderdoc)."""
    val = os.environ.get(canonical)
    if val is not None:
        return val
    legacy_val = os.environ.get(legacy)
    if legacy_val is not None:
        _warn_legacy_once(legacy, canonical)
        return legacy_val
    return default


def _config_tool(config, name: str) -> str | None:
    """Read ``[tools].<name>`` from an optional config, tolerating a dataclass or a dict."""
    if config is None:
        return None
    tools = getattr(config, 'tools', None)
    if tools is None and isinstance(config, dict):
        tools = config.get('tools')
    if not tools:
        return None
    if isinstance(tools, dict):
        return tools.get(name)
    return getattr(tools, name, None)


def _expand_templates(name: str) -> list[str]:
    """Expand ``_KNOWN_PATH_TEMPLATES``; skip any whose required env var is unset."""
    subs = {'name': name}
    lad = os.environ.get('LOCALAPPDATA')
    if lad:
        subs['LOCALAPPDATA'] = lad.replace('\\', '/')
    out = []
    for tpl in _KNOWN_PATH_TEMPLATES:
        try:
            out.append(tpl.format(**subs))
        except KeyError:
            continue  # e.g. {LOCALAPPDATA} unset -> drop that candidate
    return out


def _candidates(name: str, config=None) -> list[tuple[str, str | None, str]]:
    """Ordered ``(desc, path, kind)`` candidates in §5 precedence. First existing path wins.

    ``kind`` ∈ {'env', 'config', 'path', 'file'} drives the error-block status line.
    """
    canonical, legacy = _ENV_VARS[name]
    out: list[tuple[str, str | None, str]] = []

    env_val = os.environ.get(canonical, '').strip()
    out.append((f'${canonical}', env_val or None, 'env'))

    legacy_val = os.environ.get(legacy, '').strip()
    if legacy_val and not env_val:
        _warn_legacy_once(legacy, canonical)
    out.append((f'${legacy} (deprecated)', legacy_val or None, 'env'))

    out.append((f'config: tools.{name}', _config_tool(config, name), 'config'))

    out.append(('PATH', shutil.which(name + '.exe'), 'path'))

    arm = sorted(glob.glob(_ARM_GLOB.format(name=name)), key=_version_key, reverse=True)
    arm_desc = arm[0] if arm else _ARM_GLOB.format(name=name).replace('/', os.sep)
    out.append((arm_desc, arm[0] if arm else None, 'file'))

    for p in _expand_templates(name):
        out.append((p.replace('/', os.sep), p, 'file'))

    return out


def resolve_tool_verbose(name: str, config=None) -> tuple[str, str]:
    """Resolve ``name`` to a path and the description of the step that won.

    Raises ``ToolNotFound`` (exit 3) when no candidate exists.
    """
    if name not in _ENV_VARS:
        raise ValueError(f'unknown tool {name!r}; expected one of {tuple(_ENV_VARS)}')
    if config is None:
        config = get_config()
    attempts = _candidates(name, config)
    for desc, path, _kind in attempts:
        if path and os.path.exists(path):
            return path, desc
    raise ToolNotFound(name, attempts)


def resolve_tool(name: str, config=None) -> str:
    """Resolve ``name`` ∈ {'renderdoccmd', 'qrenderdoc'} to an absolute path (§5)."""
    path, _ = resolve_tool_verbose(name, config)
    return path


def write_config_stub(root: str) -> tuple[str, bool]:
    """Write a curated, commented ``.bobframes.toml`` starter to ``root``.

    Returns ``(path, written)``; ``written`` is False when the file already exists (skip, no
    overwrite). Deliberately a small starter, NOT a dump of ``_default_config.toml`` — pinning every
    internal default would defeat deep-merge forward-compat (the user would never inherit improved
    defaults for keys they did not intend to override).
    """
    path = os.path.join(root, '.bobframes.toml')
    if os.path.exists(path):
        return path, False
    with open(path, 'w', encoding='utf-8', newline='\n') as f:
        f.write(_CONFIG_STUB)
    return path, True


_CONFIG_STUB = """\
# bobframes project config. Any key omitted here inherits the bundled default,
# so list only what you want to override. Full schema: bobframes/_default_config.toml.
schema_version = 1

[tools]
# Pin the RenderDoc tools explicitly (else resolved via PATH / known install paths).
# renderdoccmd = "C:/Program Files/RenderDoc/renderdoccmd.exe"
# qrenderdoc   = "C:/Program Files/RenderDoc/qrenderdoc.exe"

[pipeline]
# replay_timeout_s  = 600.0   # per-capture qrenderdoc replay budget (seconds)
# convert_timeout_s = 120.0   # per-file renderdoccmd convert budget (seconds)
"""
