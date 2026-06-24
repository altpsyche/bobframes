"""v028_1: end-to-end smoke -- the panel serves its control page and read-only state over HTTP."""
from __future__ import annotations

import json
import re

from ..ui import server as _server
from ._ui_util import get, running


def test_root_page_and_state_smoke(tmp_path):
    with running(str(tmp_path)) as (httpd, port):
        page = get(port, '/')
        assert page.getcode() == 200
        body = page.read().decode('utf-8')
        assert 'bobframes ui' in body and '/api/state' in body   # the page knows to fetch state
        s = json.load(get(port, '/api/state?t=' + httpd.bobframes_token))
        assert {'root', 'tools', 'drops', 'runs', 'convention', 'platform', 'windows'} <= set(s)


def test_control_page_js_string_literals_are_not_broken_by_python_escapes():
    """Regression (v028_2 -> fixed v028_5): the page is an r-string so the embedded JS ``"\\n"`` stays a
    two-char escape. A normal string would let Python emit a REAL newline mid-JS-literal, which makes the
    WHOLE <script> fail to parse (the page renders but no JS runs -> everything stuck at placeholders).
    pytest never executes the panel JS, so guard the failure mode structurally: the <script> body must
    contain no raw newline inside a double-quoted JS string literal."""
    page = _server.control_page()
    script = re.search(r'<script>(.*)</script>', page, re.S).group(1)
    # The specific line that broke: the stream() newline concat must carry a literal backslash-n.
    assert r'd.line + "\n"' in script
    # General: no double-quoted string literal on any single line is left open (a raw newline inside one
    # leaves an odd number of unescaped double quotes on that line).
    for i, line in enumerate(script.splitlines()):
        unescaped_quotes = len(re.findall(r'(?<!\\)"', line))
        assert unescaped_quotes % 2 == 0, f'odd unescaped quotes on script line {i}: {line!r}'
