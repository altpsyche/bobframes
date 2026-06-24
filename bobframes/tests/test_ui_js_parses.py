"""v028_7/8: the panel JS must PARSE -- an automated gate that runs the parser (the v028_6 lesson).

pytest exercises the panel's HTTP surface in Python but never parses or executes the panel JS; the
v028_2 bug (a normal triple-quoted page literal turned the embedded JS ``"\\n"`` into a REAL newline
mid-string-literal -> the WHOLE script was a syntax error -> nothing populated) shipped undetected
through five commits for exactly that reason. v028_8 externalized the JS to
``bobframes/ui/assets/panel.js`` (a real file -- the embedding bug class is now impossible), and this
runs ``node --check`` on it (syntax-only, so browser globals like ``document`` / ``fetch`` /
``EventSource`` are fine -- it parses, it does not resolve).

Skips when node is absent locally; CI (`windows-latest` ships node) also runs an UNCONDITIONAL
``node --check bobframes/ui/assets/panel.js`` step + ``node --version``, so the gate can never silently
skip everywhere (ADR-23).
"""
from __future__ import annotations

import pathlib
import shutil
import subprocess

import pytest

from ..ui import server as _server

_PANEL_JS = pathlib.Path(_server.__file__).parent / 'assets' / 'panel.js'


def test_panel_js_parses_with_node():
    node = shutil.which('node')
    if node is None:
        pytest.skip('node not installed (CI runs an unconditional node --check step)')
    assert _PANEL_JS.exists(), f'missing {_PANEL_JS}'
    proc = subprocess.run([node, '--check', str(_PANEL_JS)], capture_output=True, text=True)
    assert proc.returncode == 0, f'node --check rejected panel.js:\n{proc.stdout}\n{proc.stderr}'
