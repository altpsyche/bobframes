"""Perf guard: a full render-only of the synthetic fixture stays well under budget. Catches gross
regressions, not micro-changes. The budget is generous (subprocess incl. interpreter + pyarrow
import + render of ~60-row tables); tighten if it ever proves too loose."""
from __future__ import annotations

import time

from . import _render_util as u

PERF_BUDGET_S = 15.0


def test_render_perf(tmp_path):
    root = u.setup_root(str(tmp_path / "root"))
    t0 = time.monotonic()
    u.render(root)
    dt = time.monotonic() - t0
    assert dt < PERF_BUDGET_S, f"render took {dt:.2f}s (budget {PERF_BUDGET_S}s)"
