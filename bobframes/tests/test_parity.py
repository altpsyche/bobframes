"""Golden-snapshot parity: rendering the synthetic fixture reproduces the frozen golden HTML
(byte-identical after masking the build timestamp). The backbone gate for every refactor."""
from __future__ import annotations

import os

import pytest

from . import _render_util as u


@pytest.mark.golden_env  # ADR-11: byte parity only on the canonical env (py3.12 / pyarrow 21)
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

    # c16j: the catalog/drill heavy data lives in _pagedata/*.js (ADR-37). Gate it as a SEPARATE
    # family so a failure says "js" vs "html". No normalize (no timestamp); the .js is ASCII + LF.
    actual_js = u.rendered_page_data_files(dest)
    golden_js = u.rendered_page_data_files(u.GOLDEN_DIR)
    assert actual_js == golden_js, (
        f"rendered _pagedata/*.js set changed vs golden: {set(actual_js) ^ set(golden_js)}"
    )
    for rel in golden_js:
        golden = open(os.path.join(u.GOLDEN_DIR, rel), encoding="utf-8").read()
        actual = open(os.path.join(dest, rel), encoding="utf-8").read()
        assert actual == golden, f"page-data diverged from golden: {rel}"
