"""Banned-token lint for HTML/markdown chrome.

Catches LLM-filler vocabulary and label scaffolding that the previous
iteration of the pipeline kept generating. Applies only to chrome around
data tables, not to CSV cell contents.

Run via `python -m bobframes.lint <file...>` or imported by run.py.
"""

from __future__ import annotations

import sys
from html.parser import HTMLParser

from . import config

# The banlist now lives in bobframes/lint_banlist.toml (default) + [lint].extra_banned (H-14);
# read it via config.banlist() (compiled + cached, order preserved).


class _HtmlTextExtractor(HTMLParser):
    """Collects text outside <table>, <script>, <style> ranges.

    Each entry is (lineno, text).
    """

    _SKIP_TAGS = {'table', 'script', 'style'}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._skip_depth: dict[str, int] = {t: 0 for t in self._SKIP_TAGS}
        self.chunks: list[tuple[int, str]] = []

    def handle_starttag(self, tag, attrs):
        t = tag.lower()
        if t in self._SKIP_TAGS:
            self._skip_depth[t] += 1

    def handle_endtag(self, tag):
        t = tag.lower()
        if t in self._SKIP_TAGS and self._skip_depth[t] > 0:
            self._skip_depth[t] -= 1

    def handle_data(self, data):
        if any(v > 0 for v in self._skip_depth.values()):
            return
        if not data.strip():
            return
        line, _col = self.getpos()
        self.chunks.append((line, data))


def lint_html(path: str) -> list[tuple[int, str, str]]:
    """Return list of (lineno, pattern_label, snippet) for any banned matches."""
    with open(path, 'r', encoding='utf-8') as f:
        body = f.read()
    extractor = _HtmlTextExtractor()
    extractor.feed(body)
    hits: list[tuple[int, str, str]] = []
    banned = config.banlist()
    for lineno, text in extractor.chunks:
        for rx, label in banned:
            m = rx.search(text)
            if m:
                snippet = text.strip()[:80]
                hits.append((lineno, label, snippet))
    return hits


def lint_markdown(path: str) -> list[tuple[int, str, str]]:
    hits: list[tuple[int, str, str]] = []
    banned = config.banlist()
    with open(path, 'r', encoding='utf-8') as f:
        for lineno, line in enumerate(f, start=1):
            for rx, label in banned:
                if rx.search(line):
                    hits.append((lineno, label, line.rstrip()[:80]))
    return hits


def lint_file(path: str) -> list[tuple[int, str, str]]:
    lower = path.lower()
    if lower.endswith('.md'):
        return lint_markdown(path)
    return lint_html(path)


def main(argv: list[str]) -> int:
    if not argv:
        print('usage: lint.py <file...>', file=sys.stderr)
        return 2
    total = 0
    for path in argv:
        hits = lint_file(path)
        for lineno, label, snippet in hits:
            print(f'{path}:{lineno}: [{label}] {snippet}', file=sys.stderr)
            total += 1
    return 2 if total else 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
