"""Refresh the rendered-HTML golden snapshot (tests/data/golden). Run on an INTENTIONAL
output-changing commit, then review the diff page-by-page (ADR-23) before committing:

    python -m bobframes.tests.make_golden

Renders the bundled synthetic via render_fresh (which scrubs BOBFRAMES_CONFIG -> bundled defaults),
then writes each page into golden/ with the build timestamp normalized to <TS> (u.normalize, which
test_parity also applies on read) and LF newlines. Mirrors make_preview_golden / make_parquet_golden.
"""
from __future__ import annotations

import os
import tempfile

from . import _render_util as u


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="bobframes_golden_") as tmp:
        dest = u.render_fresh(os.path.join(tmp, "root"))
        n = 0
        for rel in u.rendered_html_files(dest):
            html = u.normalize(open(os.path.join(dest, rel), encoding="utf-8").read())
            out = os.path.join(u.GOLDEN_DIR, rel)
            os.makedirs(os.path.dirname(out), exist_ok=True)
            with open(out, "w", encoding="utf-8", newline="\n") as f:
                f.write(html)
            n += 1
        # c16j: the catalog/drill VTable payloads now live in _pagedata/*.js companions. Copy them
        # raw (LF, NO normalize - no timestamp); test_parity byte-compares them as a separate family.
        j = 0
        for rel in u.rendered_page_data_files(dest):
            data = open(os.path.join(dest, rel), encoding="utf-8").read()
            out = os.path.join(u.GOLDEN_DIR, rel)
            os.makedirs(os.path.dirname(out), exist_ok=True)
            with open(out, "w", encoding="utf-8", newline="\n") as f:
                f.write(data)
            j += 1
    print(f"wrote {n} golden pages + {j} _pagedata/*.js under {u.GOLDEN_DIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
