"""v028_7: the panel JS must PARSE -- an automated gate that runs the parser (the v028_6 lesson).

pytest exercises the panel's HTTP surface in Python but never parses or executes the served `<script>`;
the v028_2 bug (a normal triple-quoted page literal turned the embedded JS ``"\\n"`` into a REAL newline
mid-string-literal -> the WHOLE script was a syntax error -> nothing populated) shipped undetected
through five commits for exactly that reason. This extracts the served `<script>` body and runs
``node --check`` (syntax-only, so browser globals like ``document`` / ``fetch`` / ``EventSource`` are
fine -- it parses, it does not resolve).

Skips when node is absent locally; CI (`windows-latest` ships node) also runs an UNCONDITIONAL
``node --check`` step + ``node --version``, so the gate can never silently skip everywhere (ADR-23).
v028_8 externalizes the JS to ``bobframes/ui/assets/panel.js`` and retargets this at the real file.
"""
from __future__ import annotations

import re
import shutil
import subprocess

import pytest

from ..ui import server as _server


def test_panel_script_parses_with_node(tmp_path):
    node = shutil.which('node')
    if node is None:
        pytest.skip('node not installed (CI runs an unconditional node --check step)')
    m = re.search(r'<script>(.*)</script>', _server.control_page(), re.S)
    assert m, 'no <script> in the control page'
    js = tmp_path / 'panel_check.js'
    js.write_text(m.group(1), encoding='utf-8')
    proc = subprocess.run([node, '--check', str(js)], capture_output=True, text=True)
    assert proc.returncode == 0, f'node --check rejected the panel <script>:\n{proc.stdout}\n{proc.stderr}'
