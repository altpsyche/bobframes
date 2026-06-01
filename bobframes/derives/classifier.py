"""Engine-agnostic draw classifier (c09, H-1..H-5).

The single source of truth for draw classification, the pass-path strip rules, the frame-prefix
regex, and the GPU-duration counter aliases. Rules live in TOML presets (``draw_classifier.toml`` =
the UE default; ``presets/*.toml`` = alternates) so other engines work without code patches.

Design (ADR-29): classification is an ANALYSIS-layer, single-source concern. ``classify`` is a small
**state-capable predicate engine** over a draw's field record — a rule matches if any of its marker
predicates hits OR all of its ``when`` field conditions hold; first matching rule wins; else the
``fallback_class``. Markers are a *refinement* layer, not the foundation: the ``when`` predicates read
graphics STATE (blend / depth / …, and any future draw column), so a state-first "generic" preset
(c27) is expressible without rearchitecting. The bundled UE preset reproduces the former
``derive_post_merge._classify_draw`` byte-for-byte (parity, ADR-6).

Reuses the c07/c08 ``tomllib``/``tomli`` shim (ADR-26: the package floor is 3.10 because qrenderdoc
embeds Python 3.10) and the ``importlib.resources`` bundled-read pattern. Pure-Python: the walker
takes a field dict and needs no host package — classification no longer runs inside qrenderdoc (the
former replay-side copy fed only dead columns and was deleted, D-6).
"""

from __future__ import annotations

import functools
import re
from importlib.resources import files

try:
    import tomllib  # Python 3.11+
except ModuleNotFoundError:  # pragma: no cover - py3.10 (qrenderdoc embed) via tomli backport, ADR-26
    import tomli as tomllib

from .. import config

_DEFAULT_FILE = 'draw_classifier.toml'

# (kind, ref) -> normalized spec dict. Keyed by resolved source so switching presets is cached
# independently; cleared by _reset_for_tests().
_SPEC_CACHE: dict = {}


def _bundled_text(rel: str) -> str:
    """Verbatim text of a bundled resource under bobframes/derives (``rel`` may contain '/')."""
    return files('bobframes.derives').joinpath(*rel.split('/')).read_text(encoding='utf-8')


def _resolve_source(preset, custom_path) -> tuple[str, str]:
    """Map ``[classifier]`` selection to a (kind, ref) source. custom_path wins; else preset name."""
    if custom_path:
        return ('custom', custom_path)
    if preset in (None, '', 'ue'):
        return ('bundled', _DEFAULT_FILE)
    return ('bundled', f'presets/{preset}.toml')


def _normalize(raw: dict) -> dict:
    """Flatten a parsed preset TOML to the spec the walker consumes (rule order preserved)."""
    return {
        'class_order': list(raw.get('class_order', ())),
        'fallback': raw.get('fallback_class', 'other'),
        'frame_prefix_regex': raw.get('frame_prefix_regex', ''),
        'rules': raw.get('rule', []),
        'pass_strip': raw.get('pass_strip', {}),
        'gpu_duration_aliases': list(raw.get('counters', {}).get('gpu_duration_aliases', ())),
    }


def load_spec(preset=None, custom_path=None) -> dict:
    """Load + cache the classifier spec. With no args, reads ``[classifier]`` from the active config
    (preset 'ue' -> bundled draw_classifier.toml; '<name>' -> presets/<name>.toml; custom_path -> file)."""
    if preset is None and custom_path is None:
        cfg = getattr(config.get_config(), 'classifier', None)
        if cfg is not None:
            preset, custom_path = cfg.preset, cfg.custom_path
    kind, ref = _resolve_source(preset, custom_path)
    key = (kind, ref)
    if key not in _SPEC_CACHE:
        if kind == 'custom':
            with open(ref, 'rb') as f:
                raw = tomllib.load(f)
        else:
            raw = tomllib.loads(_bundled_text(ref))
        _SPEC_CACHE[key] = _normalize(raw)
    return _SPEC_CACHE[key]


def _cond(field, expect) -> bool:
    """Faithful field condition. bool -> truthy/falsy int coercion (``int(x or 0)``); str -> case-
    insensitive equality (mirrors the old ``(x or '').lower() == 'one'``); else exact equality."""
    if expect is True:
        return int(field or 0) != 0
    if expect is False:
        return int(field or 0) == 0
    if isinstance(expect, str):
        return str(field or '').lower() == expect.lower()
    return field == expect


def classify(fields: dict, spec: dict | None = None) -> str:
    """Return the draw class for a draw's field record ({marker, blend_enable, depth_write_enable,
    blend_src_color, blend_dst_color, ...}). First matching rule wins; else the fallback class."""
    spec = spec or load_spec()
    mp = str(fields.get('marker') or '').lower()
    for r in spec['rules']:
        if any(k in mp for k in r.get('marker_contains', ())):
            return r['class']
        if any(mp.endswith(s) for s in r.get('marker_suffix', ())):
            return r['class']
        when = r.get('when')
        if when and all(_cond(fields.get(k), v) for k, v in when.items()):
            return r['class']
    return spec['fallback']


def class_order() -> list[str]:
    """The canonical draw-class order (single source for chrome.DRAW_CLASSES, H-5)."""
    return load_spec()['class_order']


def pass_strip() -> dict:
    """The ``[pass_strip]`` table: {prefixes: [...], noise_segments: [...]} (H-2)."""
    return load_spec()['pass_strip']


def gpu_duration_aliases() -> list[str]:
    """Counter names that carry GPU duration, in fall-through order (H-4)."""
    return load_spec()['gpu_duration_aliases']


@functools.lru_cache(maxsize=None)
def _compiled_frame_re(pattern: str) -> re.Pattern:
    return re.compile(pattern)


def frame_prefix_re() -> re.Pattern:
    """Compiled frame-prefix regex (e.g. ``^Frame\\s+\\d+/?``) for pass-path normalization (H-3)."""
    return _compiled_frame_re(load_spec()['frame_prefix_regex'])


def _reset_for_tests() -> None:
    """Drop the cached specs + compiled frame regex. Test seam only."""
    _SPEC_CACHE.clear()
    _compiled_frame_re.cache_clear()
