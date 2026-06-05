#!/usr/bin/env python3
"""Deterministic headless-Chrome screenshot harness for the v0.2.6 visual-redesign matrix (ADR-43 gate d).

The HTML golden is theme-agnostic, so light/dark/print regressions are invisible to it. This drives a
local Chrome over the DevTools Protocol (CDP) to capture a rendered page in each mode -- the eye the
golden no longer is. It is DEV-ONLY tooling: not shipped in the wheel, not imported by the package, and
the PNGs it writes are review artifacts (default under c:/tmp), never goldens. Because it is dev-only it
may use sockets + os.urandom (the ADR-37 no-random/offline rules govern the rendered REPORT, not this).

Stdlib only (no pyppeteer/selenium): a ~minimal RFC-6455 WebSocket client + a tiny CDP request/response
loop. Usage:

    python tools/shoot.py <rendered.html | rendered-tree-dir> [--out DIR] [--modes light,dark,print] [--width 1280]

Examples:
    python tools/shoot.py c:/tmp/perf --out c:/tmp/shots-perf          # real Perf, curated page set
    python tools/shoot.py <synthetic-root>/_reports/_chrome_preview.html --out c:/tmp/shots-gallery
"""
from __future__ import annotations

import argparse
import base64
import json
import os
import pathlib
import shutil
import socket
import struct
import subprocess
import sys
import tempfile
import time
import urllib.request

_CHROME_CANDIDATES = (
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"),
)


def find_chrome() -> str | None:
    """Absolute path to a local Chrome, or None (callers skip when None)."""
    for p in _CHROME_CANDIDATES:
        if p and os.path.exists(p):
            return p
    return shutil.which("chrome") or shutil.which("chrome.exe") or shutil.which("chromium")


# --------------------------------------------------------------------------------------------------
# Minimal RFC-6455 WebSocket client (text frames; handles fragmentation + ping/close control frames).
# --------------------------------------------------------------------------------------------------
class _WS:
    def __init__(self, host: str, port: int, path: str, timeout: float = 30.0):
        self.sock = socket.create_connection((host, port), timeout=timeout)
        self.sock.settimeout(timeout)
        key = base64.b64encode(os.urandom(16)).decode("ascii")
        req = (
            f"GET {path} HTTP/1.1\r\nHost: {host}:{port}\r\n"
            "Upgrade: websocket\r\nConnection: Upgrade\r\n"
            f"Sec-WebSocket-Key: {key}\r\nSec-WebSocket-Version: 13\r\n\r\n"
        )
        self.sock.sendall(req.encode("ascii"))
        buf = b""
        while b"\r\n\r\n" not in buf:
            chunk = self.sock.recv(4096)
            if not chunk:
                raise ConnectionError("WebSocket handshake: connection closed")
            buf += chunk
        head, _, rest = buf.partition(b"\r\n\r\n")
        if b" 101 " not in head.split(b"\r\n", 1)[0] + b" ":
            raise RuntimeError("WebSocket handshake failed: " + head.decode("latin-1"))
        self._buf = bytearray(rest)

    def _recv_exact(self, n: int) -> bytes:
        while len(self._buf) < n:
            chunk = self.sock.recv(65536)
            if not chunk:
                raise ConnectionError("WebSocket closed mid-frame")
            self._buf += chunk
        out = bytes(self._buf[:n])
        del self._buf[:n]
        return out

    def _send_frame(self, opcode: int, payload: bytes) -> None:
        header = bytearray([0x80 | opcode])  # FIN set
        n = len(payload)
        if n < 126:
            header.append(0x80 | n)
        elif n < 65536:
            header.append(0x80 | 126)
            header += struct.pack(">H", n)
        else:
            header.append(0x80 | 127)
            header += struct.pack(">Q", n)
        mask = os.urandom(4)
        header += mask
        self.sock.sendall(bytes(header) + bytes(b ^ mask[i % 4] for i, b in enumerate(payload)))

    def send(self, text: str) -> None:
        self._send_frame(0x1, text.encode("utf-8"))

    def recv(self) -> str:
        data = bytearray()
        while True:
            b0, b1 = self._recv_exact(2)
            fin, opcode = b0 & 0x80, b0 & 0x0F
            masked, length = b1 & 0x80, b1 & 0x7F
            if length == 126:
                length = struct.unpack(">H", self._recv_exact(2))[0]
            elif length == 127:
                length = struct.unpack(">Q", self._recv_exact(8))[0]
            mask = self._recv_exact(4) if masked else b""
            payload = self._recv_exact(length)
            if masked:
                payload = bytes(b ^ mask[i % 4] for i, b in enumerate(payload))
            if opcode == 0x9:          # ping -> pong
                self._send_frame(0xA, payload)
                continue
            if opcode == 0xA:          # pong
                continue
            if opcode == 0x8:          # close
                raise ConnectionError("WebSocket closed by peer")
            data += payload
            if fin:
                return data.decode("utf-8")

    def close(self) -> None:
        try:
            self._send_frame(0x8, b"")
        except OSError:
            pass
        self.sock.close()


class _CDP:
    """One CDP message channel: id-matched request/response + a small event buffer."""

    def __init__(self, ws: _WS):
        self.ws = ws
        self._id = 0
        self._events: list[dict] = []

    def call(self, method: str, params: dict | None = None, session: str | None = None) -> dict:
        self._id += 1
        mid = self._id
        msg: dict = {"id": mid, "method": method, "params": params or {}}
        if session:
            msg["sessionId"] = session
        self.ws.send(json.dumps(msg))
        while True:
            m = json.loads(self.ws.recv())
            if m.get("id") == mid:
                if "error" in m:
                    raise RuntimeError(f"{method}: {m['error']}")
                return m.get("result", {})
            if "method" in m:
                self._events.append(m)

    def wait_event(self, method: str, session: str | None = None) -> dict:
        for i, m in enumerate(self._events):
            if m.get("method") == method and (session is None or m.get("sessionId") == session):
                return self._events.pop(i)
        while True:
            m = json.loads(self.ws.recv())
            if m.get("method") == method and (session is None or m.get("sessionId") == session):
                return m
            if "method" in m:
                self._events.append(m)


# --------------------------------------------------------------------------------------------------
# Chrome launcher + capture.
# --------------------------------------------------------------------------------------------------
def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _browser_ws_url(port: int, timeout: float = 30.0) -> str:
    deadline = time.monotonic() + timeout
    last = None
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{port}/json/version", timeout=2) as r:
                return json.loads(r.read())["webSocketDebuggerUrl"]
        except Exception as e:  # noqa: BLE001 - chrome not up yet
            last = e
            time.sleep(0.15)
    raise RuntimeError(f"Chrome DevTools endpoint never came up on :{port} ({last})")


class Chrome:
    """Context-managed headless Chrome with one attached page target for capture."""

    def __init__(self, width: int = 1280, height: int = 900):
        self.width, self.height = width, height
        self.proc: subprocess.Popen | None = None

    def __enter__(self) -> "Chrome":
        chrome = find_chrome()
        if not chrome:
            raise RuntimeError("Chrome not found")
        self.port = _free_port()
        self.tmp = tempfile.mkdtemp(prefix="bf-shoot-")
        args = [
            chrome, "--headless=new", f"--remote-debugging-port={self.port}",
            f"--user-data-dir={self.tmp}", "--no-first-run", "--no-default-browser-check",
            "--hide-scrollbars", "--force-color-profile=srgb", "--disable-gpu",
            "--disable-extensions", "--disable-background-networking", "--disable-dev-shm-usage",
            "--mute-audio", "--no-sandbox", "about:blank",
        ]
        self.proc = subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        url = _browser_ws_url(self.port)
        _, _, rest = url.partition("://")
        hostport, _, path = rest.partition("/")
        host, _, port = hostport.partition(":")
        self.ws = _WS(host, int(port), "/" + path)
        self.cdp = _CDP(self.ws)
        tgt = self.cdp.call("Target.createTarget", {"url": "about:blank"})["targetId"]
        self.session = self.cdp.call(
            "Target.attachToTarget", {"targetId": tgt, "flatten": True}
        )["sessionId"]
        self.cdp.call("Page.enable", session=self.session)
        self.cdp.call("Runtime.enable", session=self.session)
        return self

    def shoot(self, url: str, out_path: str, *, mode: str = "light", width: int | None = None) -> str:
        """Capture `url` (a file:// or http URL) to `out_path` in mode light|dark|print."""
        s = self.session
        media = "print" if mode == "print" else "screen"
        features = [
            {"name": "prefers-color-scheme", "value": "dark" if mode == "dark" else "light"},
            {"name": "prefers-reduced-motion", "value": "reduce"},
        ]
        w = width or self.width
        self.cdp.call("Emulation.setEmulatedMedia", {"media": media, "features": features}, session=s)
        self.cdp.call(
            "Emulation.setDeviceMetricsOverride",
            {"width": w, "height": self.height, "deviceScaleFactor": 1, "mobile": False},
            session=s,
        )
        self.cdp.call("Page.navigate", {"url": url}, session=s)
        self.cdp.wait_event("Page.loadEventFired", session=s)
        # Let the vendored woff2 finish laying out before the shot (fonts shift metrics).
        try:
            self.cdp.call(
                "Runtime.evaluate",
                {"expression": "document.fonts ? document.fonts.ready.then(()=>1) : 1", "awaitPromise": True},
                session=s,
            )
        except RuntimeError:
            pass
        metrics = self.cdp.call("Page.getLayoutMetrics", session=s)
        size = metrics.get("cssContentSize") or metrics.get("contentSize") or {}
        height = int(size.get("height") or self.height)
        shot = self.cdp.call(
            "Page.captureScreenshot",
            {"format": "png", "captureBeyondViewport": True,
             "clip": {"x": 0, "y": 0, "width": w, "height": height, "scale": 1}},
            session=s,
        )
        data = base64.b64decode(shot["data"])
        with open(out_path, "wb") as f:
            f.write(data)
        return out_path

    def __exit__(self, *exc) -> None:
        try:
            self.ws.close()
        except OSError:
            pass
        if self.proc:
            self.proc.terminate()
            try:
                self.proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self.proc.kill()
        shutil.rmtree(self.tmp, ignore_errors=True)


# --------------------------------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------------------------------
def _discover_pages(root: pathlib.Path) -> list[pathlib.Path]:
    """A curated, stable page set from a rendered tree (index + one-pager + each report + gallery +
    catalog + the newest drill). Missing files are skipped."""
    pages: list[pathlib.Path] = []
    for rel in ("index.html", "_reports/_chrome_preview.html"):
        p = root / rel
        if p.exists():
            pages.append(p)
    reports = sorted((root / "_reports").glob("*.html")) if (root / "_reports").is_dir() else []
    pages += [p for p in reports if p not in pages]
    return pages


def _label(path: pathlib.Path, root: pathlib.Path | None) -> str:
    rel = path.relative_to(root) if root and root in path.parents else pathlib.Path(path.name)
    return str(rel).replace("\\", "_").replace("/", "_").removesuffix(".html")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Headless-Chrome screenshot matrix (v0.2.6 gate d).")
    ap.add_argument("root", help="a rendered .html file OR a rendered-tree directory")
    ap.add_argument("--out", default=r"c:\tmp\bobframes-shots", help="output dir for PNGs")
    ap.add_argument("--modes", default="light,dark,print", help="comma list of light|dark|print")
    ap.add_argument("--width", type=int, default=1280)
    args = ap.parse_args(argv)

    if not find_chrome():
        print("ERROR: Chrome not found.", file=sys.stderr)
        return 2
    root = pathlib.Path(args.root).resolve()
    if root.is_dir():
        pages, base = _discover_pages(root), root
    else:
        pages, base = [root], root.parent
    if not pages:
        print(f"ERROR: no .html pages under {root}", file=sys.stderr)
        return 2
    modes = [m.strip() for m in args.modes.split(",") if m.strip()]
    out = pathlib.Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    with Chrome(width=args.width) as c:
        for page in pages:
            url = page.as_uri()
            for mode in modes:
                name = f"{_label(page, base)}.{mode}.png"
                c.shoot(url, str(out / name), mode=mode)
                print("shot", name)
    print(f"{len(pages) * len(modes)} captures -> {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
