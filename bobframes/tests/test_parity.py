"""Golden-snapshot parity: rendering the synthetic fixture reproduces the frozen golden HTML
(byte-identical after masking the build timestamp). The backbone gate for every refactor."""
from __future__ import annotations

import os

from . import _render_util as u


def test_render_matches_golden(tmp_path):
    dest = u.render_fresh(str(tmp_path / "root"))

    actual_files = u.rendered_html_files(dest)
    golden_files = u.rendered_html_files(u.GOLDEN_DIR)
    assert actual_files == golden_files, (
        f"rendered page set changed vs golden: {set(actual_files) ^ set(golden_files)}"
    )

    for rel in golden_files:
        golden = u.normalize(open(os.path.join(u.GOLDEN_DIR, rel), encoding="utf-8").read())
        actual = u.normalize(open(os.path.join(dest, rel), encoding="utf-8").read())
        assert actual == golden, f"output diverged from golden: {rel}"
