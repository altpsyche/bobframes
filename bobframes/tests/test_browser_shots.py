"""v0.2.6-0: opt-in smoke for the tools/shoot.py screenshot harness (ADR-43 gate d machinery).

Marked `browser`: it is DESELECTED by the default suite (`-m "not browser"`) and only runs on demand
(`pytest -m browser`) where a local Chrome exists. It proves the harness end-to-end -- that it captures
a `file://` page in light/dark/print and that prefers-color-scheme emulation actually flips the pixels
(the reason gate d needs CDP rather than a plain `--screenshot` CLI). The per-surface redesign captures
are driven from `tools/shoot.py` directly at each visual commit, not from CI.
"""
from __future__ import annotations

import pathlib
import sys

import pytest

_TOOLS = pathlib.Path(__file__).resolve().parents[2] / "tools"
sys.path.insert(0, str(_TOOLS))
import shoot  # noqa: E402  (path injected above)

pytestmark = pytest.mark.browser

_PAGE = (
    "<!doctype html><html><head><meta charset=utf-8>"
    "<style>:root{color-scheme:light dark}"
    "body{margin:0;height:300px;background:light-dark(white,black);"
    "color:light-dark(black,white)}</style></head><body>bobframes shoot smoke</body></html>"
)
_PNG_MAGIC = b"\x89PNG\r\n\x1a\n"


def test_harness_captures_light_dark_print(tmp_path):
    if not shoot.find_chrome():
        pytest.skip("Chrome not found")
    page = tmp_path / "smoke.html"
    page.write_text(_PAGE, encoding="ascii")
    url = page.resolve().as_uri()

    shots: dict[str, bytes] = {}
    with shoot.Chrome() as chrome:
        for mode in ("light", "dark", "print"):
            out = tmp_path / f"smoke.{mode}.png"
            chrome.shoot(url, str(out), mode=mode)
            shots[mode] = out.read_bytes()

    for mode, data in shots.items():
        assert data[:8] == _PNG_MAGIC, f"{mode} not a PNG"
        assert len(data) > 100, f"{mode} too small"
    # light-dark() must actually respond to the emulated prefers-color-scheme (the CDP win over a CLI shot).
    assert shots["light"] != shots["dark"], "light and dark captures are identical (media emulation failed)"
