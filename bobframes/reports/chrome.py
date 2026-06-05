"""Page chrome: CSS tokens, page open/close, header, KPI strip, section card, legend, footer."""

from __future__ import annotations

import base64 as _base64
import enum as _enum
import html as _html
import re as _re
import string as _string
from dataclasses import dataclass as _dataclass
from importlib.resources import files as _files
from typing import Callable as _Callable

from . import formatters as _f
from . import _tokens
from .. import paths as _paths
from ..derives import classifier as _classifier


# Vendored Inter subset (c16d, ADR-34): a Latin + tabular-figures subset of the Inter variable font
# (wght 400-600), baked into the wheel and inlined as a base64 @font-face data URI. Reports stay a
# single self-contained HTML file that renders identically on every OS with NO network (a CDN fetch
# would break offline + byte-determinism). The woff2 bytes are committed; base64 over fixed bytes is
# byte-stable on any machine. ASCII-only output (base64 alphabet) keeps the page lint clean. See
# reports/assets/README.md for provenance + the subset command, and Inter-OFL.txt for the licence.
_FONT_WOFF2_B64 = _base64.b64encode(
    _files('bobframes.reports').joinpath('assets', 'inter-subset.woff2').read_bytes()
).decode('ascii')
_FONT_FACE_CSS = (
    "\n@font-face{font-family:'Inter';"
    "src:url(data:font/woff2;base64," + _FONT_WOFF2_B64 + ") format('woff2');"
    "font-weight:400 600;font-style:normal;font-display:swap}\n"
)


def _read_asset(name: str) -> str:
    """Read a bundled text asset (CSS/JS/SVG) from reports/assets/ (c16x-1).

    The chrome CSS/JS now live as real `.css`/`.js` files instead of Python string literals, loaded
    the same way `design_tokens.toml` is (importlib.resources). Text mode is universal-newline, so the
    returned string is LF regardless of the on-disk EOL -- byte-identical to the former literal, which
    keeps the golden/parity gates green. `string.Template` `${token}` placeholders (and the rdc-table
    `__ROW_H__` marker) are preserved verbatim in the files and substituted by the existing callers.
    """
    return _files('bobframes.reports').joinpath('assets', name).read_text(encoding='utf-8')


# Design-token VALUES live in reports/design_tokens.toml (c08, H-15); this skeleton owns only the
# CSS var NAMES + layout/alignment. string.Template substitutes $key -> value (CSS uses no '$', so
# only our placeholders match). The @media reduced-motion reset (0s) is a fixed a11y behavior, not a
# designer token, so it stays literal. design_tokens_css() returns this UN-minified (template.py
# embeds it raw on the drill/root pages), so the inter-arg spacing here is parity-significant.
_DESIGN_TOKENS_TMPL = _read_asset('design_tokens.css')

_DESIGN_TOKENS = _string.Template(_DESIGN_TOKENS_TMPL).substitute(_tokens.token_subst())


_CHROME_CSS_TMPL = _read_asset('chrome.css')

_CHROME_CSS = _string.Template(_CHROME_CSS_TMPL).substitute(_tokens.layout_subst())


_STICKY_CSS_TMPL = _read_asset('sticky.css')

_STICKY_CSS = _string.Template(_STICKY_CSS_TMPL).substitute(_tokens.layout_subst())


_LINK_KIND_CSS = _read_asset('link_kind.css')


_ICON_SPRITE = _read_asset('icon_sprite.html')


_CONTAINER_CSS = _read_asset('container.css')


_PRINT_CSS = _read_asset('print.css')


_COMPONENTS_CSS_BASE = _read_asset('components.css')


_COMPONENTS_JS_ALL = _read_asset('components.js')


_TOKENS_CSS = _DESIGN_TOKENS
# The @font-face leads the primitives so it ships on BOTH CSS paths: chrome page_open's _compose_css
# AND template.py's chrome_css() (drill/root). design_tokens_css() stays pure :root (test contract).
_PRIMITIVES_CSS = _FONT_FACE_CSS + _CHROME_CSS + _LINK_KIND_CSS + _STICKY_CSS + _CONTAINER_CSS + _PRINT_CSS
_COMPONENTS_CSS = _COMPONENTS_CSS_BASE
_COMPONENTS_JS = _COMPONENTS_JS_ALL


# Inline 16x16 SVG favicon (3-bar stack pattern) as data URL.
# Uses single quotes inside SVG so the data URL can be enclosed in
# href="..." without breaking the HTML attribute.
_FAVICON_HREF = (
    "data:image/svg+xml;utf8,"
    "<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 16 16'>"
    "<rect x='2' y='3' width='12' height='2' fill='%23888'/>"
    "<rect x='2' y='7' width='12' height='2' fill='%234a8'/>"
    "<rect x='2' y='11' width='12' height='2' fill='%23d54'/>"
    "</svg>"
)


def _minify_css(s: str) -> str:
    """Strip CSS comments + collapse whitespace + drop blank lines.
    Conservative: preserves selectors and rule structure."""
    import re as _re
    s = _re.sub(r'/\*.*?\*/', '', s, flags=_re.DOTALL)
    s = _re.sub(r'\n\s*\n', '\n', s)
    s = _re.sub(r'^\s+', '', s, flags=_re.MULTILINE)
    s = _re.sub(r'\s*([{};:,])\s*', r'\1', s)
    s = _re.sub(r';}', '}', s)
    return s.strip()


def _minify_js(s: str) -> str:
    """Strip JS line comments + block comments + collapse leading whitespace.
    Conservative: preserves string literals (does not strip inside them naively)."""
    import re as _re
    # Strip block comments (greedy minimal)
    s = _re.sub(r'/\*.*?\*/', '', s, flags=_re.DOTALL)
    # Strip line comments (// to end of line) - careful with URLs (// in strings)
    # Use a heuristic: only strip lines whose // is preceded by whitespace at start of statement
    lines = []
    for line in s.split('\n'):
        # Drop line comments that begin a line (after whitespace)
        stripped = line.lstrip()
        if stripped.startswith('//'):
            continue
        lines.append(line.rstrip())
    s = '\n'.join(ln for ln in lines if ln)
    return s


def _compose_css() -> str:
    # c16l (ADR-38): the rdc-table engine is now ALWAYS-ON in the report bundle (was opt-in via
    # report_page(rdc_table=True) in c16k). Every report/dashboard/A-B/per-run page hosts a STATIC
    # rdc-table, so the engine CSS ships unconditionally. template.py composes its own bundle for
    # catalog/drill (it adds rdc_table_css() explicitly), so this fold does NOT double-include there.
    return _minify_css(_TOKENS_CSS + _PRIMITIVES_CSS + _COMPONENTS_CSS + _RDC_TABLE_CSS)


def _compose_js() -> str:
    return _minify_js(_COMPONENTS_JS + _RDC_TABLE_JS)


def design_tokens_css() -> str:
    """Return :root tokens CSS for reuse in template.py."""
    return _TOKENS_CSS


def chrome_css() -> str:
    """Return primitives + components CSS (without tokens). Used by template.py."""
    return _PRIMITIVES_CSS + _COMPONENTS_CSS


def components_js() -> str:
    """Return Web Components JS blob. Used by template.py."""
    return _COMPONENTS_JS


# --- token-validity guard (c16x-3, ADR-42; closes the G-30 footgun class) --------------------------
# A typo'd `var(--sp-5)` makes the property invalid -> it computes to nothing, silently zeroing (e.g.)
# the padding until a human notices. This catches it: any referenced var(--NAME) whose NAME is neither
# a declared design token NOR a custom property defined in the composed CSS is undefined. The declared
# set is (TOML :root scale) UNION (every `--x:` definition scanned from the composed CSS), so in-body
# props (--crumb-h, --hdr-offset, --clip-cap*, --th-bg*) are NOT false-flagged; programmatic chart
# tokens (_tokens.chart()) are passed as values, never var()-referenced, so they never appear.
_TOKEN_DEF_RE = _re.compile(r'--([a-zA-Z][a-zA-Z0-9-]*)\s*:')        # a custom-property DEFINITION
_TOKEN_REF_RE = _re.compile(r'var\(\s*--([a-zA-Z][a-zA-Z0-9-]*)')    # a var(--NAME) REFERENCE


def _undefined_token_refs(composed_css: str, *emitted: str) -> set:
    """NAMEs referenced via var(--NAME) that are neither a TOML token nor a `--x:` def in composed_css.

    `emitted` carries extra fragments to scan for references (the bundle JS, emitted `style=`/`<style>`),
    so a `var(--typo)` set from JS or an inline style is caught too. Declarations are taken ONLY from
    composed_css (the authoritative stylesheet); emitted fragments contribute references, not declarations.
    """
    declared = {k.replace('_', '-') for k in _tokens.token_subst()}
    declared |= set(_TOKEN_DEF_RE.findall(composed_css))
    referenced = set(_TOKEN_REF_RE.findall(composed_css))
    for frag in emitted:
        referenced |= set(_TOKEN_REF_RE.findall(frag))
    return referenced - declared


def undefined_tokens() -> set:
    """Undefined var(--NAME) across the report bundle (CSS + JS). EMPTY on a healthy build; a non-empty
    result is the G-30 footgun. CI hard-gates this (tests/test_token_guard.py); `bobframes preview`
    warns on it (non-fatal) so a designer editing design_tokens.toml sees the typo in their own loop."""
    return _undefined_token_refs(_compose_css(), _compose_js())


# ---------------------------------------------------------------------------
# The head-asset seam (c16r, ADR-41). ONE source of truth for the page's chrome CSS/JS boundary so
# `bobframes package --shared-assets` (c16t) can emit `_assets/`-linked assets BY CONSTRUCTION rather
# than scraping rendered HTML. Two sinks: INLINE (the render default - byte-identical to today; ADR-37
# single-file default stands) and REF (depth-relative `<link>`/`<script defer src>` into `_assets/`).
#
# The (filename -> content) pairing lives ONCE, in the per-family manifest (REPORT_ASSETS here; the
# catalog/drill family's CATALOG_ASSETS in html/template.py). head_assets(REF) builds links FROM the
# manifest and c16t writes each `_assets/*` file FROM the same manifest - zero-drift by construction,
# no duplicated `report.css` literal a later rename could split (the property ADR-41 demands).
# ---------------------------------------------------------------------------


class AssetSink(_enum.Enum):
    """Where a page's chrome CSS/JS goes (c16r, ADR-41)."""
    INLINE = 'inline'   # rendered inline; the render default - byte-identical to pre-c16r output
    REF = 'ref'         # depth-relative links into `_assets/` (consumed at c16t)


@_dataclass(frozen=True)
class AssetFile:
    """One extractable chrome asset: its `_assets/` filename, kind, and a lazy content producer.

    `content()` is called once by c16t to write the file; head_assets(REF) only needs `name`+`kind`.
    Keeping the producer here makes the manifest the single source of the filename->content pairing.
    """
    name: str                     # e.g. 'report.css'
    kind: str                     # 'css' | 'js'
    content: _Callable[[], str]   # e.g. _compose_css

    def ref_link(self, prefix: str) -> str:
        """The REF-sink `<link>`/`<script defer src>` for this asset (ASCII, file://-safe). Shared
        by both page families so the link contract (css->stylesheet link, js->DEFERRED external
        script) lives once. `defer` is required: an external script in `<head>` must run AFTER body
        parse (the components are DOM-ready-safe; mirrors the `_pagedata` defer pattern)."""
        href = f'{prefix}{self.name}'
        if self.kind == 'css':
            return f'<link rel="stylesheet" href="{href}">'
        return f'<script defer src="{href}"></script>'


@_dataclass(frozen=True)
class HeadAssets:
    """The chrome-asset markup for one page, split by where it is placed in the document.

    `head` is spliced into `<head>`; `body_js` at the end of `<body>`. The report family (page_open)
    puts CSS+JS adjacent in the head, so its `body_js` is '' and both pieces ride in `head`. The
    catalog/drill family (template.py) keeps the engine `<script>` at body-end, so it fills `body_js`.
    """
    head: str
    body_js: str


# The report family's asset manifest (page_open: reports, dashboard, A/B, per-run, summary, preview).
REPORT_ASSETS = (
    AssetFile('report.css', 'css', _compose_css),
    AssetFile('report.js', 'js', _compose_js),
)


def assets_prefix(depth: int) -> str:
    """Depth-relative `_assets/` href prefix, e.g. `../../_assets/` at depth 2 (c16r, ADR-41).
    Shared by both page families' REF sinks so the depth->prefix math lives once."""
    return ('../' * depth) + _paths.ASSETS_DIR + '/'


def head_assets(sink: 'AssetSink', depth: int = 0) -> 'HeadAssets':
    """The report family's head-asset markup for `sink` (c16r, ADR-41).

    INLINE reproduces today's exact `page_open` bytes: `<style>{_compose_css()}</style>` immediately
    followed by `<script>{_compose_js()}</script>` (the JS tag omitted iff the composed JS is empty -
    today's guard, preserved so the refactor is provably byte-faithful). REF emits depth-relative
    `_assets/report.{css,js}` links built from REPORT_ASSETS. `body_js` is always '' for this family
    (the JS rides in the head, adjacent to the CSS).
    """
    if sink is AssetSink.INLINE:
        js = _compose_js()
        script = f'<script>{js}</script>' if js else ''
        return HeadAssets(head=f'<style>{_compose_css()}</style>{script}', body_js='')
    prefix = assets_prefix(depth)
    head = ''.join(a.ref_link(prefix) for a in REPORT_ASSETS)
    return HeadAssets(head=head, body_js='')


# ---------------------------------------------------------------------------
# rdc-table: the ONE bespoke table engine (c16k build + c16l rollout, ADR-38). It SUBSUMED both the
# old catalog/drill VTable and the reports' rdc-sortable-table (now deleted - G-23 fully resolved).
# Progressive-enhancement, two data-delivery modes picked by data-mode:
#   - virtual: rows stream from window.__data_<key> (_pagedata/*.js); the DOM is windowed (VTable).
#   - static : rows are SERVER-BAKED into <table class="data">; JS only enhances IN PLACE (sort
#              reorders existing <tr> nodes, heatmap tints existing <td>s, column-groups toggle
#              display) so JS-off / print / Ctrl-F all see every row (ADR-37 preserved).
# Bootstrapped from a single DOMContentLoaded pass (NOT customElements) so it dodges the parse-time
# connectedCallback footgun and matches today's VTable timing. Offline, byte-deterministic (NO
# random/Date/fetch in the rendered output), ASCII (the runtime ' ▲'/' ▼' textContent is tolerated,
# as in the old VTable). c16l folded the engine into the ALWAYS-ON shared bundle (_compose_css/
# _compose_js): every report/dashboard/A-B/per-run page hosts a STATIC rdc-table, so the opt-in is
# gone. template.py composes its own bundle for catalog/drill (it adds rdc_table_css()/rdc_table_js()
# explicitly), so the fold does not double-include there.
# ---------------------------------------------------------------------------

# Single-source virtual-scroll row height (c16i): the JS `const ROW_H` (via the __ROW_H__ sentinel)
# and the CSS cell padding are tuned together so a row never overflows ROW_H (14px x 1.3 + 12 + 1).
_RDC_ROW_H = 32

# Engine CSS. The `table.data` rules + `.col-groups` toggles + the type-split, lifted from the old
# template._PER_DROP_CSS so BOTH the catalog/drill (virtual) and a static report render through one
# class. Carries the custom-prop defs `table.data` depends on (--th-bg/--th-bg-active/--label) so the
# report context (which never loaded _PER_DROP_CSS) styles headers + labels correctly.
_RDC_TABLE_CSS = _read_asset('rdc_table.css')

# Engine JS. One IIFE; shared cmpVals (natural-numeric, ADR-24) + tintImage (uniform-tint heatmap);
# VTable = the windowed virtual engine; StaticTable = the in-place static enhancer.
_RDC_TABLE_JS_TMPL = _read_asset('rdc_table.js')

_RDC_TABLE_JS = _RDC_TABLE_JS_TMPL.replace('__ROW_H__', str(_RDC_ROW_H))


def rdc_table_css() -> str:
    """Engine CSS for the unified rdc-table (c16k). Used by template.py (catalog/drill), emitted
    verbatim (un-minified) so the c16i substring guards over the catalog/drill output stay green. The
    report bundle folds it in via _compose_css() (c16l, ADR-38 — always-on, no longer opt-in)."""
    return _RDC_TABLE_CSS


def rdc_table_js() -> str:
    """Engine JS for the unified rdc-table (c16k). Used verbatim by template.py (catalog/drill); the
    report bundle folds it into _compose_js() (c16l)."""
    return _RDC_TABLE_JS


def h(s) -> str:
    return _html.escape(str(s if s is not None else ''))


# --- escape-by-construction element builder (c16x-2, ADR-42; subsumes roadmap C6) ------------------
# A component built through el() cannot emit an unescaped attribute value or text child -- escaping is
# structural, not a per-call h() the author can forget. A _Raw child (any component's own output) is
# spliced verbatim (no double-escape); a plain str/number child is HTML-escaped. Plain server-rendered
# strings, no dependency / build step, deterministic, ASCII-clean for ASCII input (ADR-37).

class _Raw(str):
    """Already-safe HTML markup. el() emits a _Raw child verbatim; a plain str child is escaped."""
    __slots__ = ()


def raw(s) -> _Raw:
    """Mark a pre-built HTML fragment as safe (no escaping) -- nested component output, or markup
    assembled elsewhere (e.g. a `_f.safe_chrome_text(...)` result the caller wants spliced raw)."""
    return _Raw('' if s is None else str(s))


# Attribute NAMES are never data; restrict them so a name can never break out of the tag.
_ATTR_NAME_CHARS = frozenset(
    'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_:')


def _el_attrs(attrs: dict | None) -> str:
    if not attrs:
        return ''
    out = []
    for name, value in attrs.items():
        if not name or any(ch not in _ATTR_NAME_CHARS for ch in name):
            raise ValueError(f'unsafe attribute name: {name!r}')
        if value is None or value is False:
            continue                                          # omit absent / false attributes
        if value is True:
            out.append(f' {name}')                            # boolean attribute
        else:
            out.append(f' {name}="{_html.escape(str(value), quote=True)}"')
    return ''.join(out)


def _el_children(children) -> str:
    out = []
    for c in children:
        if c is None or c is False:
            continue                                          # skip so `cond and frag` composes
        out.append(str(c) if isinstance(c, _Raw) else h(c))   # _Raw verbatim; else escape
    return ''.join(out)


def el(tag: str, attrs: dict | None = None, *children) -> _Raw:
    """Build `<tag ...>children</tag>` with attribute values + text children escaped BY CONSTRUCTION.

    attrs value: None/False omits the attribute, True emits a bare boolean attribute, else
    name="escaped". children: a _Raw passes verbatim (no double-escape), None/False is skipped, anything
    else is HTML-escaped via h(). Returns _Raw so nesting composes. Quotes match the chrome house style
    (double-quoted attrs + html.escape(quote=True)), so an el() rebuild of an existing double-quoted
    leaf is byte-identical (the parity contract for c16x leaf migrations)."""
    return _Raw(f'<{tag}{_el_attrs(attrs)}>{_el_children(children)}</{tag}>')


def el_void(tag: str, attrs: dict | None = None, *, self_close: bool = False) -> _Raw:
    """A childless element: `<tag ...>` (HTML void: link/img/input/meta) or `<tag .../>` when
    self_close (XML/SVG: use/rect/...). Same attribute escaping as el()."""
    return _Raw(f'<{tag}{_el_attrs(attrs)}{"/" if self_close else ""}>')


def classes(*names) -> str:
    """Join truthy class names with single spaces (skips '' / None) for an el() `class=` value."""
    return ' '.join(str(n) for n in names if n)


# c16m: per-tier char thresholds for emitting a title= on a truncating cell. A deterministic proxy for
# "will visually clip" (matches the pass_gpu title-gating precedent); short values skip title= to avoid
# screen-reader double-read. Tier '' = default (--clip-cap 320px), 'narrow' (200px), 'wide' (560px).
_CLIP_TITLE_THRESH = {'': 40, 'narrow': 24, 'wide': 64}


def clip_attrs(full_value, *, tier: str = '') -> str:
    """The ` class="clip…"` + length-gated ` title="…"` for a truncating cell element (c16m).

    Splice onto an existing in-cell `<a>`/element whose visible text is the (possibly long) value; the
    clip is CSS-only so the real DOM text + the title= keep the FULL value (Ctrl-F / hover / copy). Use
    on cells that already build their own inner element (e.g. a linked src path). `tier` in
    {'', 'narrow', 'wide'}; the full value lives in title= when longer than the tier threshold.
    """
    s = '' if full_value is None else str(full_value)
    cls = 'clip' if not tier else f'clip clip-{tier}'
    title = f' title="{_f.safe_chrome_text(s)}"' if len(s) > _CLIP_TITLE_THRESH.get(tier, 40) else ''
    return f' class="{cls}"{title}'


def clip_span(value, *, tier: str = '') -> str:
    """Wrap a plain-text cell value in a truncating `<span class="clip…">` (c16m).

    For long text cells that have no inner element of their own (RT label, areas, area name, …). The
    value is HTML-escaped for display and (when long) carried verbatim in title= via `clip_attrs`.
    Copy-button / link payloads are built separately by the caller and stay the FULL value.
    """
    s = '' if value is None else str(value)
    return f'<span{clip_attrs(s, tier=tier)}>{_html.escape(s)}</span>'


# Canonical class order + colors. Reports use this order in stacks. Single source = the active
# classifier preset's class_order (H-5); the UE default reproduces the former literal byte-for-byte
# (pinned by tests/test_classifier). The hand-aligned --c-<name> CSS tokens live in the design-token
# skeleton above and are asserted to cover every class here.
DRAW_CLASSES = list(_classifier.class_order())


def class_color_var(cls: str) -> str:
    return f'var(--c-{cls})' if cls in DRAW_CLASSES else 'var(--c-other)'


def page_open(title: str, *, hdr_offset_px: int | None = None,
              body_attrs: dict | None = None,
              sink: 'AssetSink' = AssetSink.INLINE, depth: int = 0) -> str:
    """Open a self-contained HTML page. hdr_offset_px sets --hdr-offset on <body>.

    Use 48 for dashboard / single-section reports, 84 for multi-section reports
    that carry ab_strip / device_strip / toc above the first sticky h2.
    body_attrs: extra attributes on <body> (e.g. {'data-multi-section': 'true'}).

    The rdc-table engine CSS+JS ship in the shared bundle (_compose_css/_compose_js) for EVERY page
    (c16l, ADR-38 — every report now hosts a STATIC <rdc-table>); the c16k opt-in is gone.

    ``sink``/``depth`` (c16t, ADR-41): INLINE (the render default) is BYTE-IDENTICAL to today and
    ignores ``depth``; REF emits depth-relative ``_assets/report.{css,js}`` links so `package`'s
    shared-asset bundle re-renders the page from this same seam (no scrape, no str.replace).
    """
    # Chrome CSS/JS routed through the c16r head_assets seam (ADR-41); INLINE is byte-identical to the
    # pre-c16r `<style>{_compose_css()}</style>{script}` pair (body_js is '' for the report family).
    ha = head_assets(sink, depth)
    attrs: list[str] = []
    if hdr_offset_px is not None:
        attrs.append(f'style="--hdr-offset: {int(hdr_offset_px)}px"')
    for k, v in (body_attrs or {}).items():
        attrs.append(f'{_html.escape(k)}="{_html.escape(str(v))}"')
    body_attr_str = (' ' + ' '.join(attrs)) if attrs else ''
    return (f'<!doctype html><html lang="en"><head><meta charset="utf-8">'
            f'<title>{_html.escape(title)}</title>'
            f'<link rel="icon" href="{_FAVICON_HREF}">'
            f'{ha.head}{ha.body_js}</head><body{body_attr_str}>'
            f'{_ICON_SPRITE}')


def icon(name: str) -> str:
    """Return inline SVG referencing the icon sprite (c16x-2: composed via el, byte-identical)."""
    return el('svg', {'class': 'icon', 'aria-hidden': 'true'},
              el_void('use', {'href': f'#icon-{name}'}, self_close=True))


def summary_bar(label: str, headline: str, *,
                sub: str | None = None,
                link_href: str | None = None,
                link_text: str = 'view',
                tone: str = 'neutral') -> str:
    """Render the per-page summary-bar primitive.

    label: short caption (e.g. "worst gpu area")
    headline: 5-second number / phrase (rendered at --fs-display)
    sub: optional sub-line (e.g. "rank 1 of 7 areas")
    link_href: optional primary-action link rendered as button chip
    tone: neutral | alarm | warn | ok | info (controls top border color)
    """
    wrap_open = ''
    wrap_close = ''
    if tone == 'alarm':
        wrap_open = '<rdc-alarm-banner data-severity="high">'
        wrap_close = '</rdc-alarm-banner>'
    parts = [wrap_open]
    parts.append(f'<aside class="summary-bar tone-{_html.escape(tone)}" aria-label="page summary">')
    parts.append(f'<div class="sb-label">{_html.escape(label)}</div>')
    parts.append(f'<div class="sb-headline">{_html.escape(headline)}</div>')
    if sub:
        parts.append(f'<div class="sb-sub">{_html.escape(sub)}</div>')
    if link_href:
        parts.append(f'<a class="sb-link" href="{_html.escape(link_href)}" '
                     f'data-link-kind="primary">{_html.escape(link_text)}</a>')
    parts.append('</aside>')
    parts.append(wrap_close)
    return ''.join(parts)


def empty_state(message: str, *, icon_name: str = 'warn') -> str:
    """Friendly empty-state card (icon + message) for a report/section with no rows (c16). Replaces a
    bare `<p class="note">` / blank `<tbody>` so a sparse drop reads as 'no data', not 'broken'."""
    return f'<div class="empty-state">{icon(icon_name)}<span>{h(message)}</span></div>'


def callout(severity: str, title: str, detail: str = '', *,
            href: str | None = None, link_text: str = 'view',
            icon_name: str | None = None) -> str:
    """Render a ranked-finding callout — the report's 'so what' (c16).

    severity in {ok, warn, alarm, info, neutral}; controls the left-border + icon color. warn/alarm
    wrap in <rdc-alarm-banner> so the finding is announced to assistive tech (role/aria-live set by
    the component). ``detail`` is a sub-line; ``href``/``link_text`` an optional primary action.
    """
    sev = severity if severity in ('ok', 'warn', 'alarm', 'info') else 'neutral'
    ic = icon_name or ('warn' if sev in ('alarm', 'warn') else 'arrow-right')
    wrap_open = wrap_close = ''
    if sev in ('alarm', 'warn'):
        wrap_open = f'<rdc-alarm-banner data-severity="{"high" if sev == "alarm" else "low"}">'
        wrap_close = '</rdc-alarm-banner>'
    body = [f'<div class="co-body"><div class="co-title">{h(title)}</div>']
    if detail:
        body.append(f'<div class="co-detail">{h(detail)}</div>')
    if href:
        body.append(f'<a href="{h(href)}" data-link-kind="inline">{h(link_text)}</a>')
    body.append('</div>')
    return f'{wrap_open}<div class="callout sev-{sev}">{icon(ic)}{"".join(body)}</div>{wrap_close}'


def heatmap_cell(value, lo, hi, *, direction: str = 'hot', text: str | None = None) -> str:
    """Inline data-shaded cell via the rdc-heatmap-cell web-component (c16). The server emits
    value+min+max; the component shades client-side, so the emitted HTML stays deterministic. Returns
    the element only — wrap it in a `<td class="num">`. ``direction`` 'hot' = high values are intense."""
    disp = text if text is not None else value
    return (f'<rdc-heatmap-cell data-value="{h(value)}" data-min="{h(lo)}" data-max="{h(hi)}" '
            f'data-direction="{h(direction)}">{h(disp)}</rdc-heatmap-cell>')


def provenance_strip(host_info: dict | None, tool_versions: dict | None,
                     *, redact: bool = False) -> str:
    """Capture-context strip: GPU/driver/CPU/OS + external tool versions (G-6/G-7) recorded at ingest.

    Renders the .device-strip primitive under the page header so every report shows the machine + tool
    versions the data came from. Omits the bobframes version on purpose (a release bump must not churn
    the golden). Returns '' when no provenance was recorded (older manifests).

    ``redact=True`` (c16u, ADR-40) emits a fixed ``redacted`` strip in place of the values -- the
    `package --redact` re-render scrubs device/host provenance at the structured DATA seam, never by an
    HTML regex. It still returns '' when there was nothing to redact (so an empty manifest stays empty).
    Default ``False`` -> byte-identical to the pre-c16u output.
    """
    host_info = host_info or {}
    tool_versions = tool_versions or {}
    fields = []
    for key, label in (('gpu', 'gpu'), ('gpu_driver', 'driver'), ('cpu', 'cpu'), ('os', 'os')):
        v = host_info.get(key)
        if v:
            fields.append(f'{label} <strong>{h(v)}</strong>')
    for tool in ('renderdoccmd', 'qrenderdoc'):
        v = tool_versions.get(tool)
        if v:
            fields.append(f'{tool} <strong>{h(v)}</strong>')
    if not fields:
        return ''
    if redact:
        return '<div class="device-strip">redacted</div>'
    return f'<div class="device-strip">{" | ".join(fields)}</div>'


def ab_picker(options: list, current_href: str | None = None) -> str:
    """Render A/B picker dropdown.

    options: list of (label, href) tuples.
    current_href: optional href to mark selected.
    """
    if not options:
        return ''
    parts = ['<rdc-ab-picker><label for="rdc-ab-select">compare</label>',
             '<select id="rdc-ab-select">',
             '<option value="">none</option>']
    for label, href in options:
        sel = ' selected' if current_href == href else ''
        parts.append(f'<option value="{_html.escape(href)}"{sel}>'
                     f'{_html.escape(label)}</option>')
    parts.append('</select></rdc-ab-picker>')
    return ''.join(parts)


def ab_picker_for(root: str, report_name: str, *, ab=None) -> str:
    """Discover A/B pairs under <root>/_reports/ab and emit picker for given report.

    Suppresses output when ab is non-None (caller is already on an A/B page).
    Emits relative URLs from <root>/_reports/<report>.html.
    """
    import os as _os
    from .. import paths as _paths
    if ab is not None:
        return ''
    ab_dir = _os.path.join(_paths.reports_dir(root), _paths.AB_DIR)
    if not _os.path.isdir(ab_dir):
        return ''
    pairs = sorted(d for d in _os.listdir(ab_dir)
                   if _os.path.isdir(_os.path.join(ab_dir, d)))
    if not pairs:
        return ''
    options = [(p, f'ab/{p}/{report_name}.html') for p in pairs]
    return ab_picker(options)


def run_picker(options: list, current_href: str | None = None) -> str:
    """Run selector (c16f): a static <select> of per-run page links, reusing the rdc-ab-picker web
    component (it navigates to select.value on change - no new JS). Distinct select id from the A/B
    picker so both can coexist on one page; no 'none' option (a report is always for some run)."""
    if not options:
        return ''
    parts = ['<rdc-ab-picker><label for="rdc-run-select">run</label>',
             '<select id="rdc-run-select">']
    for label, href in options:
        sel = ' selected' if current_href == href else ''
        parts.append(f'<option value="{_html.escape(href)}"{sel}>'
                     f'{_html.escape(label)}</option>')
    parts.append('</select></rdc-ab-picker>')
    return ''.join(parts)


def run_picker_for(run, report_name: str, *, reports_up: str = '',
                   max_older: int = 10) -> str:
    """Emit the run selector for `report_name` from a RunContext (c16f). '' when <=1 run.

    Lists the pre-rendered runs (newest + the `max_older` most-recent older) as links: the newest is
    the top-level `<report>.html`, older runs are `run/<key>/<report>.html`, each prefixed by
    `reports_up` ('' from a top-level page, '../../' from a per-run page) so links resolve from both
    locations. The current run's own option is marked selected. Labels via safe_chrome_text.
    """
    from .discovery import prerendered_runs as _prerendered
    from .. import paths as _paths
    if run is None or getattr(run, 'n_runs', 0) <= 1:
        return ''
    shown = {d.key for d in _prerendered(run.drops, max_older)}
    newest_key = run.drops[-1].key
    cur_key = run.current.key if getattr(run, 'current', None) else newest_key
    n = run.n_runs
    options = []
    current_href = None
    for i, d in enumerate(run.drops):
        if d.key not in shown:
            continue
        is_new = d.key == newest_key
        label = _f.safe_chrome_text(
            f'run {i + 1}/{n}: {d.key}' + (' (newest)' if is_new else ''))
        href = (f'{reports_up}{report_name}.html' if is_new
                else f'{reports_up}{_paths.RUN_DIR}/{d.key}/{report_name}.html')
        options.append((label, href))
        if d.key == cur_key:
            current_href = href
    return run_picker(options, current_href)


def run_compare_banner(current, baseline) -> str:
    """The 'current <x> vs baseline <y>' banner (c16f). '' when there is no baseline.

    Reuses the .ab-strip chrome; the baseline key is dimmed (--text-3 via .dim). Keys are
    data-derived -> routed through safe_chrome_text.
    """
    if current is None or baseline is None:
        return ''
    return (f'<div class="ab-strip">current: {_f.safe_chrome_text(current.key)} '
            f'| baseline: <span class="dim">{_f.safe_chrome_text(baseline.key)}</span></div>')


def link(href: str, text: str, *, kind: str = 'inline',
         icon_name: str | None = None, target_blank: bool = False) -> str:
    """Render <a data-link-kind=...> with optional trailing icon.

    kind: primary | inline | drill | copy | crumb
    icon_name: matches a symbol id in _ICON_SPRITE (link-out, file, arrow-right, copy, search, warn)
    """
    target_attr = ' target="_blank" rel="noopener"' if target_blank else ''
    icon_html = icon(icon_name) if icon_name else ''
    return (f'<a href="{_html.escape(href)}" data-link-kind="{_html.escape(kind)}"'
            f'{target_attr}>{_html.escape(text)}{icon_html}</a>')


def page_close() -> str:
    return '</body></html>'


def report_page(title: str, body, *, drops: int = 0, captures: int = 0,
                build_ts: str = '', crumb_depth: int = 1, kpis: list | None = None,
                current_page: str | None = None, hdr_offset_px: int | None = 120,
                body_attrs: dict | None = None, ab=None, root: str | None = None,
                report_key: str | None = None, device: str = '', run=None,
                run_nav_key: str | None = None,
                sink: 'AssetSink' = AssetSink.INLINE) -> str:
    """Assemble a standard Layer-2 report page, deduping the open/header/strip/close shared by every
    report (Q-6). ``body`` is an HTML string or a list of fragments (the report's summary_bar +
    sections, in order). The fragments are '\\n'-joined exactly as write_report joins a parts list, so
    routing a report through this helper is byte-identical to the old inline boilerplate.

    The A/B strip + picker are emitted right after the header only when ``report_key`` and ``root``
    are both given (the cumulative-vs-A/B reports); both self-suppress to '' when ``ab`` is None.
    Reports with a bespoke strip (trend_table's capture-count suffixes) pass report_key=None and place
    their strip at the head of ``body`` instead.

    ``run`` is the report's RunContext (c16e, ADR-35); when it has a current run the header names it
    ("run 2 of 2: <key>"). c16f layers the navigation UX on the same object: an "older run" cue when
    not viewing the newest, a run selector, and a "current vs baseline" banner. ``run_nav_key`` is the
    page's own file stem for the run-selector hrefs (defaults to ``report_key``; the dashboard passes
    'index' since it carries no report_key).
    """
    parts = [page_open(title, hdr_offset_px=hdr_offset_px, body_attrs=body_attrs,
                       sink=sink, depth=crumb_depth),
             header(title, drops=drops, captures=captures, build_ts=build_ts,
                    kpis=kpis, crumb_depth=crumb_depth, current_page=current_page,
                    run=run)]
    if device:
        parts.append(device)
    nav_key = run_nav_key or report_key
    reports_up = '../' * (crumb_depth - 1)   # '' from a top-level page, '../../' from a per-run page
    # "older run" cue: viewing a non-newest run is easy to misread as current (c16f).
    if run is not None and nav_key and getattr(run, 'current', None) is not None \
            and not run.is_newest:
        parts.append(callout(
            'warn', 'viewing an older run',
            f'this is run {run.ordinal} ({run.run_label}); the newest run is {run.drops[-1].key}',
            href=f'{reports_up}{nav_key}.html', link_text='go to newest'))
    # A/B strip + picker: only on top-level (newest) pages - per-run pages omit it (a per-run snapshot
    # is single-run; A/B comparison lives on the top-level pages, and its links are _reports-relative).
    if report_key is not None and root is not None and (run is None or run.is_newest):
        parts.append(ab_strip(ab))
        parts.append(ab_picker_for(root, report_key, ab=ab))
    # Run selector + "current vs baseline" banner (every page with >1 run, except A/B pages).
    if ab is None and run is not None and nav_key:
        parts.append(run_picker_for(run, nav_key, reports_up=reports_up,
                                    max_older=_report_max_prerendered_runs()))
        parts.append(run_compare_banner(run.current, getattr(run, 'baseline', None)))
    parts.extend(body if isinstance(body, (list, tuple)) else [body])
    parts.append(page_close())
    return '\n'.join(parts)


def _report_max_prerendered_runs() -> int:
    """The [report] max_prerendered_runs cap (c16f); defensive default for no-config contexts."""
    try:
        from ..config import get_config
        return int(get_config().report.max_prerendered_runs)
    except Exception:
        return 10


def header(title: str, *, drops: int = 0, captures: int = 0,
           build_ts: str = '', kpis: list | None = None,
           crumb_depth: int = 1, current_page: str | None = None, run=None) -> str:
    """Render top page header: h1 + data strip + crumb + optional kpi strip.

    crumb_depth = number of '../' segments to root index.html.
    Chronological reports under _reports/ use 1. A/B under _reports/ab/<pair>/ use 3.

    current_page: if 'dashboard', drops the dashboard self-link from crumb.
                  if 'root', drops the root-catalog self-link.
                  'summary' (c16q) is a leaf page - it matches neither, so it KEEPS both crumbs
                  (root catalog + dashboard), which is correct; no behavioral branch is added (one
                  would churn every other report/dashboard/catalog golden).

    run: a RunContext (c16e, ADR-35). When it carries a current run, a "run <ordinal>: <key>" fact
         span is added so the reported run is visible (data-derived key via safe_chrome_text).
    """
    up = '../' * crumb_depth
    crumb_links = []
    if current_page != 'root':
        crumb_links.append(f'<a href="{up}index.html" data-link-kind="crumb">root catalog</a>')
    if current_page != 'dashboard':
        crumb_links.append(f'<a href="{up}_reports/index.html" data-link-kind="crumb">dashboard</a>')
    fact_spans = [f'<span>built <strong>{_html.escape(build_ts)}</strong></span>']
    if drops > 1:
        fact_spans.append(f'<span>drops <strong>{drops}</strong></span>')
    if run is not None and getattr(run, 'current', None):
        fact_spans.append(
            f'<span>run <strong>{_f.safe_chrome_text(run.ordinal)}</strong>: '
            f'<strong>{_f.safe_chrome_text(run.run_label)}</strong></span>')
    parts = [
        f'<h1>{_html.escape(title)}</h1>',
        '<header class="strip">',
        *fact_spans,
        '</header>',
        f'<nav class="crumb">{"".join(crumb_links)}</nav>',
    ]
    if kpis:
        parts.append(kpi_strip(kpis))
    return '\n'.join(parts)


def legend(classes: list[str] | None = None) -> str:
    out = ['<div class="legend">']
    for c in (classes or DRAW_CLASSES):
        out.append(f'<span class="chip"><span class="swatch" '
                   f'style="background: {class_color_var(c)}"></span>{_html.escape(c)}</span>')
    out.append('</div>')
    return '\n'.join(out)


def kpi_chip(label: str, value, *, delta: str | None = None,
             tone: str = 'neutral') -> str:
    """Render one KPI chip. tone in {pos, neg, neutral} (c16x-2: composed via el, byte-identical)."""
    return el('div', {'class': 'kpi-chip tone-' + tone},
              el('div', {'class': 'kpi-label'}, label),
              el('div', {'class': 'kpi-value'}, value),
              el('div', {'class': 'kpi-delta'}, delta) if delta else None)


def kpi_strip(kpis: list) -> str:
    """Render hero KPI strip below page header."""
    if not kpis:
        return ''
    parts = ['<div class="kpi-strip">']
    for k in kpis:
        parts.append(kpi_chip(
            k.get('label', ''), k.get('value', ''),
            delta=k.get('delta'), tone=k.get('tone', 'neutral'),
        ))
    parts.append('</div>')
    return ''.join(parts)


def section_card(section_id: str, title: str, body: str, *,
                 count: str | int | None = None,
                 subtitle: str | None = None,
                 level: str = 'h2') -> str:
    head_parts = [f'<{level}>{h(title)}</{level}>']
    if count is not None:
        if isinstance(count, int):
            count_str = _f.fmt_int(count)
        else:
            count_str = str(count)
        head_parts.append(f'<span class="card-count">{h(count_str)}</span>')
    sub = (f'<p class="card-subtitle">{h(subtitle)}</p>'
           if subtitle else '')
    return (f'<section class="card" id="{h(section_id)}">'
            f'<header>{"".join(head_parts)}</header>'
            f'{sub}'
            f'{body}'
            f'</section>')


def ab_strip(ab, *, baseline_suffix: str = '', compare_suffix: str = '') -> str:
    """Render the A/B header strip. Empty string when ab is None."""
    if ab is None:
        return ''
    baseline, compare = ab
    return (f'<div class="ab-strip">baseline: {h(baseline.key)}{baseline_suffix} '
            f'| compare: {h(compare.key)}{compare_suffix}</div>')
