"""bobframes ui -- a zero-dependency local-web control panel (ADR-47).

A stdlib ``http.server`` surface that DRIVES the existing verbs for QA / product teammates who
are not comfortable in a terminal. It emits no report HTML (the golden gate / ADR-37 contract is
untouched) and pulls no dependency into core (ADR-17). Heavy work is run by spawning the existing
CLI verbs as subprocesses; only read-only state is computed in-process.

This package is imported lazily from ``cli._cmd_ui`` so the core install never loads it.
"""
from __future__ import annotations

__all__ = ["serve"]


def serve(*args, **kwargs) -> int:  # thin re-export so callers do `from .ui import serve`
    from .server import serve as _serve
    return _serve(*args, **kwargs)
