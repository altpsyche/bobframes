"""Refresh the chrome-preview golden (c08). Run on an intentional change to the preview gallery or
to the design tokens:  python -m bobframes.tests.make_preview_golden
"""
from __future__ import annotations

import os
import shutil
import tempfile

from . import _render_util as u


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="bobframes_preview_golden_") as tmp:
        src = u.render_preview(os.path.join(tmp, "root"))
        os.makedirs(os.path.dirname(u.GOLDEN_PREVIEW), exist_ok=True)
        shutil.copyfile(src, u.GOLDEN_PREVIEW)
    print(f"wrote {u.GOLDEN_PREVIEW}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
