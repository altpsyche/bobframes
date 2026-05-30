"""Determinism: rendering the same data twice produces byte-identical HTML (after masking the
build timestamp). Catches dict-ordering, set-iteration, and other nondeterminism regressions."""
from __future__ import annotations

import os

from . import _render_util as u


def test_render_is_deterministic(tmp_path):
    a = u.render_fresh(str(tmp_path / "a"))
    b = u.render_fresh(str(tmp_path / "b"))

    fa, fb = u.rendered_html_files(a), u.rendered_html_files(b)
    assert fa == fb, f"page set differs between runs: {set(fa) ^ set(fb)}"
    for rel in fa:
        ca = u.normalize(open(os.path.join(a, rel), encoding="utf-8").read())
        cb = u.normalize(open(os.path.join(b, rel), encoding="utf-8").read())
        assert ca == cb, f"nondeterministic output: {rel}"
