"""Loader for reports/design_tokens.toml — designer-editable CSS token VALUES (c08, H-15/H-20).

A separate concern from the c07 config (config.py): this is the visual palette a non-Python
designer tunes. Bundled-only in v0.2 (DESIGNER Track A edits the packaged file directly); per-project
token overrides / deep-merge are Track B. Reuses c07's tomllib/tomli shim (ADR-26) and the
importlib.resources read pattern.
"""

from __future__ import annotations

from importlib.resources import files

try:
    import tomllib  # Python 3.11+
except ModuleNotFoundError:  # pragma: no cover - py3.10 (qrenderdoc embed) via tomli backport, ADR-26
    import tomli as tomllib

_TOKENS_FILE = 'design_tokens.toml'

# Substitution sections merged into one flat {key: value} map for string.Template (color/spacing/
# type/motion/shadow). Order is irrelevant for substitution; keys are globally unique.
_SUBST_SECTIONS = ('spacing', 'type', 'motion', 'color', 'shadow')

_CACHE: dict | None = None


def _toml_text() -> str:
    """Verbatim bundled design_tokens.toml text (also used by `export-tokens --format toml`)."""
    return files('bobframes.reports').joinpath(_TOKENS_FILE).read_text(encoding='utf-8')


def load_tokens() -> dict:
    """Parse design_tokens.toml (cached). Keys: color/spacing/type/motion/shadow/layout/chart."""
    global _CACHE
    if _CACHE is None:
        _CACHE = tomllib.loads(_toml_text())
    return _CACHE


def token_subst() -> dict:
    """Flat {key: value} for the :root color/spacing/type/motion placeholders (string.Template)."""
    t = load_tokens()
    out: dict = {}
    for section in _SUBST_SECTIONS:
        out.update(t.get(section, {}))
    return out


def layout_subst() -> dict:
    """Flat {key: str(value)} for the [layout] CSS placeholders (string.Template). Ints stringified."""
    return {k: str(v) for k, v in load_tokens().get('layout', {}).items()}


def layout() -> dict:
    """The raw [layout] table (e.g. sparkline_w/h as ints for delta.py defaults)."""
    return load_tokens().get('layout', {})


def chart() -> dict:
    """The raw [chart] table (sizes + var() palette) for reports/charts.py (c16b, ADR-33).

    Not a string.Template section, so it never reaches the :root CSS / golden.
    """
    return load_tokens().get('chart', {})


def tokens_toml_text() -> str:
    """Public alias for the verbatim bundled TOML (export-tokens identity round-trip)."""
    return _toml_text()
