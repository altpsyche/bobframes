"""External-tool resolution (ARCHITECTURE §5) and the seam for the future TOML config (§6).

``resolve_tool(name)`` finds ``renderdoccmd`` / ``qrenderdoc`` with the precedence:

    BOBFRAMES_* env  >  [tools] config  >  PATH  >  known Windows paths  >  ToolNotFound

Legacy ``RENDERDOCCMD`` / ``RENDERDOC_QRENDERDOC`` env vars are still honored, with a one-shot
deprecation warning. The full TOML loader is c07; this module accepts an optional ``config`` object
(``[tools]`` mapping) but works entirely on defaults when none is passed.

Windows-only in v1 (§5/§12): the ``.exe`` suffix and the known paths below are intentionally
hardcoded. c06 keeps them in the ``_ARM_GLOB`` / ``_KNOWN_PATH_TEMPLATES`` constants so the
cross-platform commit (c36) can branch them per-OS without rewriting ``_candidates``.
"""

from __future__ import annotations

import glob
import logging
import os
import re
import shutil

from .errors import ToolNotFound

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

_warned_legacy: set[str] = set()


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


def _config_tool(config, name: str) -> str | None:
    """Read ``[tools].<name>`` from an optional config, tolerating a dataclass or a dict.

    Dormant until c07 (no loader yet); kept so the c07 dataclass needs no signature change.
    """
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
    attempts = _candidates(name, config)
    for desc, path, _kind in attempts:
        if path and os.path.exists(path):
            return path, desc
    raise ToolNotFound(name, attempts)


def resolve_tool(name: str, config=None) -> str:
    """Resolve ``name`` ∈ {'renderdoccmd', 'qrenderdoc'} to an absolute path (§5)."""
    path, _ = resolve_tool_verbose(name, config)
    return path
