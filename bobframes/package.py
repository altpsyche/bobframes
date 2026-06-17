"""``bobframes package`` -- bundle a rendered tree into a shareable artifact set (c16s, ADR-40/41).

A deterministic, NON-MUTATING stream transform: read an already-rendered ``<root>`` and write, OUTSIDE
that tree, two friendly artifacts:

  * ``<project>-<rundate>-report.zip`` -- the full viewable tree under a single ``<project>-<rundate>/``
    folder, plus a recipient ``README.txt``;
  * ``<project>-<rundate>-summary.html`` -- a standalone, self-contained copy of the exec one-pager
    (c16q) you can email / double-click / print to PDF with no unzip.

Delivery is **shared-assets by default** (c16t, ADR-41): the ~95 KB of chrome (font + CSS + JS) lives once
per page-family under ``_assets/`` and every page links it depth-relative, collapsing the cross-page
duplication a zip's per-entry DEFLATE cannot. The REF form is produced BY THE RENDER SEAM (``head_assets``)
-- `package` re-renders the tree with ``sink=REF`` into a temp staging dir, READING source data (parquet,
the existing per-drop cache, manifests) from ``<root>`` and WRITING only the staging HTML/``_pagedata`` (so
``<root>`` is never touched; ``_data`` is streamed raw into the zip). ``--inline`` opts out and reproduces
the c16s self-contained-per-page bundle (a fast identity copy). The standalone summary stays INLINE in both
modes. ``--redact`` lands at c16u. No new dependency -- stdlib ``zipfile``/``tempfile``/``shutil`` only; the
zip is reproducible (fixed entry timestamps + pinned DEFLATE), so the gate reads the tree back out rather
than byte-comparing zip bytes (zlib/Python variance, ADR-40).
"""
from __future__ import annotations

import logging
import os
import re
import shutil
import tempfile
import zipfile

from . import paths as _paths
from .errors import EXIT_USER_ERROR, BobFramesError

log = logging.getLogger('bobframes')

# Fixed ZipInfo timestamp -> reproducible archives (the DOS/zip epoch; 1980-01-01 is the minimum a
# ZipInfo accepts). The only wall-clock the verb touches is the `[HH:MM:SS]` log-line prefix.
_ZIP_DATE = (1980, 1, 1, 0, 0, 0)

# --- redaction (c16u, ADR-40) ---------------------------------------------------------------------
# An absolute-path token: a drive-letter path `C:\...`. The token stops at whitespace / quotes / angle
# brackets / pipe, so it never spans a line and a JSON-escaped `C:\\...` stops at its closing quote
# (replacing the whole token keeps the JSON valid). The pattern REQUIRES a drive letter + colon +
# backslash, which is UNAMBIGUOUSLY absolute -- base64 / `data:` URIs / `http:` URLs never have `:\` and
# RELATIVE backslash paths (e.g. a `shader_src\2192.glsl` resource ref) have no drive letter, so neither
# is touched (the c16u "no false positives" goal). Out of scope (recorded ADR-23 limitations, FINDINGS):
# UNC `\\host\share` (a JSON-escaped single separator `\\` is indistinguishable from a literal UNC `\\`
# in assembled text, so a blanket UNC strip would mangle relative paths) and forward-slash drive paths
# `C:/...` (would false-match `http://`; RenderDoc emits backslash on Windows).
_ABS_PATH = re.compile(r"[A-Za-z]:\\[^\s\"'<>|]+")
_PATH_REDACTED = '<path redacted>'
# Provenance-only `_data` sidecars carry device/host values (host_info, gl_renderer) but are linked by
# NO viewable page -> dropped wholesale from a redacted bundle (robust to manifest schema growth).
_REDACT_DROP_SIDECARS = (_paths.MANIFEST_NAME, 'frame_metadata.jsonl')
# Bundled text the strip pass rewrites; binary `.parquet` is out of scope (recorded limitation).
_REDACT_TEXT_EXT = ('.html', '.js', '.csv', '.json', '.jsonl')

README_NAME = 'README.txt'
README_TEXT = (
    'bobframes report bundle\n'
    '\n'
    'Extract this whole folder first - do NOT open files from inside the zip.\n'
    "(The in-zip preview opens a single file without its siblings, which breaks\n"
    'the relative links between pages and their data.)\n'
    '\n'
    'Then open index.html and start at the Build Health Summary.\n'
)


class PackageError(BobFramesError):
    """A ``package`` user error: not a rendered tree, no run data, unknown ``--run``, output inside root."""

    exit_code = EXIT_USER_ERROR


def build(root: str, *, out: str | None = None, light: bool = False,
          inline: bool = False, summary_file: bool = True, stage: bool = False,
          run: str | None = None, redact: bool = False,
          redact_paths: str = 'strip') -> tuple[str, str]:
    """Package an already-rendered ``<root>`` into ``(zip_path, summary_path)``, both OUTSIDE ``<root>``.

    Non-mutating: ``<root>`` is only read. ``run`` selects the run whose ``drop_date`` names the
    artifacts (a ``DropSet.key`` like ``2026-05-28_r110600``); default is the newest run. ``light``
    bundles only ``index.html`` + the top-level ``_reports/*.html`` (no drill / ``_pagedata`` / ``_data``).
    ``summary_file=False`` skips the standalone one-pager (``summary_path`` is then ``''``). ``stage=True``
    also materializes the bundle tree to a sibling ``.stage`` dir for inspection.

    Delivery (c16t, ADR-41): the DEFAULT is the deduped shared-asset bundle -- the tree is re-rendered
    with the REF sink into a temp staging dir, ``_assets/`` written once per family, ``_data`` streamed
    raw from ``<root>``. ``inline=True`` (and ``light``, which is inherently self-contained) take the
    c16s identity-copy path instead. The standalone summary is INLINE (a verbatim source copy) regardless.

    ``redact`` (c16u, ADR-40) produces a bundle safe to share externally: device/host provenance is
    re-emitted as ``redacted`` at the render seam (so redaction FORCES a re-render -- ``--inline
    --redact`` re-renders at the INLINE sink rather than copying), the provenance-only ``_data`` sidecars
    (``_manifest.json`` / ``frame_metadata.jsonl``) are dropped, and absolute-path tokens are handled per
    ``redact_paths``: ``'strip'`` (default) replaces them with ``<path redacted>`` across all bundled
    text; ``'fail'`` is a CI completeness assertion that exits nonzero if a path remains in any rendered
    page. ``redact=False`` -> the c16s/c16t paths byte-for-byte.
    """
    if redact_paths not in ('strip', 'fail'):
        raise PackageError(f"redact_paths must be 'strip' or 'fail', got {redact_paths!r}")
    root = os.path.abspath(root)
    from .reports import discovery

    if not os.path.isdir(_paths.reports_dir(root)):
        raise PackageError(
            f'{root!r} is not a rendered tree (no {_paths.REPORTS_DIR}/ dir); '
            f'run `bobframes render` first')

    drops = discovery.discover_drops(root)
    if not drops:
        raise PackageError(
            f'{root!r} has no rendered run data (empty _catalog.parquet); run `bobframes render` first')

    if run:
        target = next((d for d in drops if d.key == run), None)
        if target is None:
            raise PackageError(
                f'run {run!r} not found; available runs: {", ".join(d.key for d in drops)}')
    else:
        target = discovery.current_run(drops)

    project = os.path.basename(os.path.normpath(root))
    rundate = target.date
    topdir = f'{project}-{rundate}'
    newest = target.key == drops[-1].key
    summary_rel = ('summary.html' if newest
                   else f'{_paths.RUN_DIR}/{target.key}/summary.html')

    # Artifact paths -- default OUTSIDE the read tree (the parent of <root>, so `package .` from inside
    # a tree never drops the zip into the tree it is reading -- the cwd-relative `./` default would).
    if out:
        zip_path = os.path.abspath(out)
        out_dir = os.path.dirname(zip_path)
    else:
        out_dir = os.path.dirname(root)
        zip_path = os.path.join(out_dir, f'{project}-{rundate}-report.zip')
    summary_path = os.path.join(out_dir, f'{project}-{rundate}-summary.html')

    _ensure_outside(out_dir, root)
    os.makedirs(out_dir, exist_ok=True)

    # Validate the standalone-summary source up front so a missing one-pager fails BEFORE any artifact
    # is written (no partial output). For an older `--run`, the per-run summary under _reports/run/<key>/.
    if summary_file:
        src_summary = os.path.join(_paths.reports_dir(root), summary_rel)
        if not os.path.isfile(src_summary):
            raise PackageError(
                f'no rendered summary at {src_summary}; run `bobframes render` first '
                f'(or pass --no-summary-file)')

    # Bundle entries as (rel, abspath). Shared (default) + any redact re-render the tree into a temp
    # staging dir (reading <root>, writing staging); plain `--inline`/`--light` keep the c16s identity
    # copy of the live <root>. Staging lives only long enough to read its files into the zip (and, for
    # a redacted shared bundle, render the standalone summary), then is removed.
    shared = not inline and not light
    restage = shared or redact
    sink_for_render = _ref_sink() if shared else _inline_sink()
    staging: str | None = None
    n_stripped = 0
    summary_bytes: bytes | None = None
    try:
        if restage:
            # c1c (ADR-45): a shared/redact bundle RE-renders, so it must carry the packaged root's
            # `[theme]` (the source INLINE pages baked it, but the REF re-render + `_assets/` are
            # composed fresh). package REJECTS the --accent flags (a presentation verb); it inherits
            # only the config [theme]. theme=None -> byte-identical to the c16t/c16u shared golden.
            from . import config as _config
            theme = _config.theme_for_render(_config.get_config())
            staging = tempfile.mkdtemp(prefix=f'{topdir}.', dir=out_dir)
            _render_tree(root, staging, sink=sink_for_render, build_ts=rundate, redact=redact, theme=theme)
            if shared:
                entries = _collect_shared(root, staging)
            else:
                entries = _collect(staging, light=light)
                _append_preview(entries, root)  # preview isn't re-rendered -> add raw (matches --inline)
        else:
            entries = _collect(root, light=light)

        if redact:
            # Drop the provenance-only sidecars, then handle absolute paths over the bundled text.
            entries = [(rel, ap) for rel, ap in entries
                       if os.path.basename(rel) not in _REDACT_DROP_SIDECARS]
            n_stripped = _redact_text_files(entries, mode=redact_paths)  # raises (fail) BEFORE the zip

        # Reproducible zip: fixed arcname order, fixed entry timestamps, pinned DEFLATE, per-entry
        # writestr; one file read into memory at a time (memory stays O(largest file), not O(tree)).
        items: list[tuple[str, str | None, bytes | None]] = [
            (f'{topdir}/{README_NAME}', None, README_TEXT.encode('ascii'))]
        items += [(f'{topdir}/{rel}', src, None) for rel, src in entries]
        file_count = 0
        with zipfile.ZipFile(zip_path, 'w', compression=zipfile.ZIP_DEFLATED) as zf:
            for arc, src, data in sorted(items, key=lambda t: t[0]):
                if data is None:
                    with open(src, 'rb') as f:
                        data = f.read()
                zi = zipfile.ZipInfo(arc, date_time=_ZIP_DATE)
                zi.compress_type = zipfile.ZIP_DEFLATED
                zf.writestr(zi, data)
                file_count += 1

        # Standalone summary bytes (while staging is alive, AFTER the zip is written). Non-redact:
        # verbatim <root> copy. Redact: from the re-rendered staging (INLINE modes); for the shared
        # bundle, a dedicated self-contained INLINE+redact render -- done here so it overwrites the
        # staging summary only after the REF copy has already been zipped. Always self-contained.
        if summary_file:
            if not redact:
                with open(src_summary, 'rb') as f:
                    summary_bytes = f.read()
            else:
                summary_bytes = _redacted_summary_bytes(
                    staging, summary_rel, newest=newest, target=target,
                    build_ts=rundate, shared=shared, redact_paths=redact_paths)
    finally:
        if staging is not None:
            shutil.rmtree(staging, ignore_errors=True)

    if summary_file:
        # The standalone one-pager is a DETACHED single file -- strip the tree-relative navigation that
        # cannot resolve beside a lone HTML (R-21), so it no longer carries a dead run dropdown.
        summary_bytes = _detach_summary(summary_bytes)
        with open(summary_path, 'wb') as f:
            f.write(summary_bytes)
    else:
        summary_path = ''

    if stage:
        stage_dir = os.path.join(out_dir, topdir + _paths.STAGE_SUFFIX)
        with zipfile.ZipFile(zip_path) as zf:
            zf.extractall(stage_dir)

    dup = _duplicated_chrome_bytes(entries)
    bundle_bytes = os.path.getsize(zip_path)
    chrome_note = (f'{dup} duplicated-chrome bytes reclaimed by shared-assets (default)' if shared
                   else f'{dup} duplicated-chrome bytes inlined (the default shared bundle dedupes these)')
    redact_note = ''
    if redact:
        paths_note = (f'{n_stripped} abs-path tokens stripped' if redact_paths == 'strip'
                      else 'rendered pages clean (0 residual paths)')
        redact_note = f'; redacted: provenance scrubbed, manifest+frame_metadata excluded, {paths_note}'
    log.info(
        f'packaged {file_count} files, {bundle_bytes} bytes; {chrome_note}{redact_note}; '
        f'summary {summary_path or "(skipped)"}; zip {zip_path}')

    return zip_path, summary_path


def _ref_sink():
    from .reports import base as _rbase
    return _rbase.AssetSink.REF


def _inline_sink():
    from .reports import base as _rbase
    return _rbase.AssetSink.INLINE


def _collect(root: str, *, light: bool) -> list[tuple[str, str]]:
    """The bundle's source files as ``(rel, abspath)`` (``rel`` is ``/``-joined, relative to ``<root>``).

    Full: ``index.html`` + every ``_reports/**`` HTML + every ``_pagedata/*.js`` + everything under
    ``_data/`` (parquet + sidecars), copied raw -- the raw ``<area>/`` capture inputs and the ``_cache``/
    ``.stage``/``.tmp`` working dirs are NOT viewable output and are excluded. Light: only ``index.html``
    + the top-level ``_reports/*.html`` (summary + 6 reports + dashboard).
    """
    out: list[tuple[str, str]] = []
    idx = _paths.root_index_html(root)
    if os.path.isfile(idx):
        out.append(('index.html', idx))

    if light:
        reports = _paths.reports_dir(root)
        if os.path.isdir(reports):
            for fn in sorted(os.listdir(reports)):
                p = os.path.join(reports, fn)
                if fn.endswith('.html') and os.path.isfile(p):
                    out.append((f'{_paths.REPORTS_DIR}/{fn}', p))
        return out

    seen = {rel for rel, _ in out}
    for dirpath, _dirs, files in os.walk(root):
        if os.sep + _paths.CACHE_DIR in dirpath:
            continue
        if any(seg.endswith((_paths.STAGE_SUFFIX, _paths.TMP_SUFFIX))
               for seg in dirpath.split(os.sep)):
            continue
        base = os.path.basename(dirpath)
        for fn in files:
            ap = os.path.join(dirpath, fn)
            rel = os.path.relpath(ap, root).replace('\\', '/')
            if rel in seen:
                continue
            in_data = rel == _paths.DATA_DIR or rel.startswith(_paths.DATA_DIR + '/')
            if (fn.endswith('.html') and not in_data) \
                    or (fn.endswith('.js') and base == _paths.PAGEDATA_DIR) \
                    or in_data:
                out.append((rel, ap))
                seen.add(rel)
    return out


def _duplicated_chrome_bytes(entries: list[tuple[str, str]]) -> int:
    """Inline chrome (CSS+JS) repeated across pages = ``Sum_family (n-1) * family_inline_bytes``.

    The ADR-37/41 measurement of what the c16t shared-asset bundle reclaims. Two page families carry
    distinct chrome: the catalog/drill family (root ``index.html`` + ``drill/**/index.html``) and the
    page_open report family (everything else). Each family's inline head+body bytes come from its own
    ``head_assets(INLINE)`` seam -- one source of truth, no scraping.
    """
    from .html import template
    from .reports import chrome

    def _inline_bytes(ha) -> int:
        return len((ha.head + ha.body_js).encode('utf-8'))

    rep = _inline_bytes(chrome.head_assets(chrome.AssetSink.INLINE))
    cat = _inline_bytes(template.head_assets(chrome.AssetSink.INLINE))

    n_rep = n_cat = 0
    drill_prefix = f'{_paths.REPORTS_DIR}/{_paths.DRILL_DIR}/'
    for rel, _ in entries:
        if not rel.endswith('.html'):
            continue
        if rel == 'index.html' or (rel.startswith(drill_prefix) and rel.endswith('/index.html')):
            n_cat += 1
        else:
            n_rep += 1
    return max(0, n_rep - 1) * rep + max(0, n_cat - 1) * cat


def _render_tree(root: str, staging: str, *, sink, build_ts: str, redact: bool = False,
                 theme: dict | None = None) -> None:
    """Re-render the tree into ``staging`` (c16t shared-assets; c16u redaction).

    ``_data`` is copied RAW into ``staging`` (no derive -> parquet bytes verbatim -> digests match the
    source) so the re-render reads AND links within ONE tree: the relative drill / CSV / parquet links
    resolve INSIDE the bundle (a decoupled out-dir would make them escape into the source tree). The
    whole tree is then rendered with the given ``sink``; ``build_ts`` pins a deterministic "built" stamp
    on the report family so two packages are byte-identical (the ``--inline`` non-redact copy keeps the
    source wall-clock stamp -- ADR-23 records the divergence). ``redact=True`` (c16u, ADR-40) re-emits
    every page's device strip as ``redacted``. The per-family ``_assets/`` are written only for the REF
    sink (the INLINE re-render is self-contained per page). ``<root>`` is only ever READ.

    Default ``(sink=REF, redact=False)`` is byte-identical to the c16t shared re-render (guarded by the
    shared golden); the call shape is unchanged on that path.
    """
    from .reports import ab as _ab, base as _rbase, discovery as _disc, orchestrator as _orch
    from .html import template as _template
    from . import manifest as _manifest
    is_ref = sink is _rbase.AssetSink.REF

    src_data = _paths.data_root(root)
    if os.path.isdir(src_data):
        shutil.copytree(src_data, _paths.data_root(staging))

    def _silent(_msg: str) -> None:
        pass

    rc = _orch.render_all_reports(staging, _silent, sink=sink, build_ts=build_ts, redact=redact, theme=theme)
    if rc != 0:
        raise PackageError(
            f're-render of {root!r} failed; cannot build the bundle (try --inline without --redact)')

    # Drill pages: mirror the existing per-(area, drop) set so the bundle reproduces EXACTLY the source
    # set (orchestrator renders reports/dashboard/per-run/root, never drill). render_drop reads + links
    # within staging; every kwarg comes from the drop's manifest, so the bytes match the source render.
    for area, drop, rel in _drill_index_rels(root):
        data_dir = _paths.drop_data_dir(staging, area, drop)
        if not os.path.isfile(os.path.join(data_dir, _paths.MANIFEST_NAME)):
            continue
        m = _manifest.read_manifest(data_dir)
        drill_dir = _paths.drop_drill_dir(staging, area, drop)
        os.makedirs(drill_dir, exist_ok=True)
        _template.render_drop(
            drill_dir, data_dir=data_dir,
            area=m.get('area', area), drop_date=m.get('drop_date', ''),
            drop_label=m.get('drop_label', ''),
            captures=m.get('captures') or [], schema_version=m.get('schema_version', 0),
            build_timestamp=m.get('build_timestamp', ''), row_counts=m.get('row_counts') or {},
            sink=sink, depth=rel.count('/'), redact=redact, theme=theme)

    # A/B pairs: render-only never emits ab/, so this is usually a no-op. When present, resolve each
    # <baselineKey>_vs_<compareKey> dir back to its DropSets and re-render; an unresolvable pair is
    # logged + omitted (never silently mislabeled -- ADR-23), so use --inline to bundle it verbatim.
    ab_root = os.path.join(_paths.reports_dir(root), _paths.AB_DIR)
    if os.path.isdir(ab_root):
        by_key = {d.key: d for d in _disc.discover_drops(staging)}
        for pair in sorted(os.listdir(ab_root)):
            if not os.path.isdir(os.path.join(ab_root, pair)):
                continue
            bkey, _sep, ckey = pair.partition('_vs_')
            baseline, compare = by_key.get(bkey), by_key.get(ckey)
            if not baseline or not compare:
                log.warning(
                    f'package: A/B pair {pair!r} could not be resolved; its pages are omitted from the '
                    f'bundle (use --inline to bundle them verbatim)')
                continue
            _ab.render_pair(staging, baseline, compare, sink=sink, build_ts=build_ts, redact=redact,
                            theme=theme)

    if is_ref:
        _write_assets(staging, theme=theme)


def _write_assets(staging: str, theme: dict | None = None) -> None:
    """Write the per-family shared chrome assets under ``staging/_assets/`` from the manifests (c16t).

    Each file's bytes ARE the composer output the REF heads link to (``AssetFile.content()``), so the
    asset boundary is one source of truth -- zero drift, no scrape (ADR-41). Two families, distinct
    files: ``report.{css,js}`` (page_open family) + ``catalog.{css,js}`` (template family).

    ``theme`` (c1c, ADR-45): the css assets are recomposed with the color override so a shared bundle
    matches the INLINE pages' accent (the JS is theme-independent). theme=None -> ``a.content()``
    byte-for-byte (the shared/redacted goldens are unthemed, so they stay identical).
    """
    from .reports import chrome as _chrome
    from .html import template as _template
    overrides = {}
    if theme:
        overrides['report.css'] = lambda: _chrome.compose_css(theme)
        overrides['catalog.css'] = lambda: _template._css_for(theme)
    assets_dir = os.path.join(staging, _paths.ASSETS_DIR)
    os.makedirs(assets_dir, exist_ok=True)
    for a in (*_chrome.REPORT_ASSETS, *_template.CATALOG_ASSETS):
        produce = overrides.get(a.name, a.content)
        with open(os.path.join(assets_dir, a.name), 'w', encoding='utf-8') as f:
            f.write(produce())


# --- redaction helpers (c16u) ---------------------------------------------------------------------

def _append_preview(entries: list[tuple[str, str]], root: str) -> None:
    """Add ``_reports/_chrome_preview.html`` raw from ``<root>`` to a staged (INLINE) bundle's entries.

    The preview gallery is produced by `bobframes preview`, not the orchestrator, so a re-render into
    staging never emits it. ``_collect_shared`` already adds it for the shared bundle; this mirrors that
    for the INLINE re-render path (used by ``--inline --redact``) so the file-set matches non-redact
    ``--inline``. The subsequent abs-path pass scrubs it like any other bundled HTML.
    """
    rel = f'{_paths.REPORTS_DIR}/_chrome_preview.html'
    if any(r == rel for r, _ in entries):
        return
    preview = os.path.join(_paths.reports_dir(root), '_chrome_preview.html')
    if os.path.isfile(preview):
        entries.append((rel, preview))


def _is_asset_rel(rel: str) -> bool:
    return rel == _paths.ASSETS_DIR or rel.startswith(_paths.ASSETS_DIR + '/')


def _is_rendered_surface(rel: str) -> bool:
    """A viewer-facing rendered page: an HTML page or its decoupled ``_pagedata/*.js`` payload."""
    if rel.endswith('.html'):
        return True
    return rel.endswith('.js') and os.path.basename(os.path.dirname(rel)) == _paths.PAGEDATA_DIR


def _strip_bytes(raw: bytes) -> tuple[bytes, int]:
    """Replace every absolute-path token in ``raw`` with ``<path redacted>``; return (bytes, count).

    Decodes with ``surrogateescape`` so non-UTF-8 bytes round-trip exactly -- only the matched tokens
    change, never surrounding bytes / line endings / the base64 font.
    """
    txt = raw.decode('utf-8', 'surrogateescape')
    new, k = _ABS_PATH.subn(_PATH_REDACTED, txt)
    return new.encode('utf-8', 'surrogateescape'), k


def _redact_text_files(entries: list[tuple[str, str]], *, mode: str) -> int:
    """Handle absolute paths in the bundle's text files (c16u, ADR-40).

    ``strip`` (default, share-safe) rewrites every abs-path token to ``<path redacted>`` across ALL
    bundled text (HTML, ``_pagedata``, CSV, JSON sidecars), skipping ``_assets/*`` and binary parquet;
    returns the replacement count. ``fail`` (CI completeness assertion) modifies nothing -- it scans only
    the rendered surface (HTML + ``_pagedata``), "did the device-strip scrub miss a path that surfaced
    in a page?", and raises ``PackageError`` on any residual (so the caller exits nonzero BEFORE the zip
    is written -- no partial artifact).
    """
    if mode == 'fail':
        hits: list[tuple[str, str]] = []
        for rel, ap in entries:
            if _is_asset_rel(rel) or not _is_rendered_surface(rel):
                continue
            txt = open(ap, 'rb').read().decode('utf-8', 'surrogateescape')
            for m in _ABS_PATH.finditer(txt):
                hits.append((rel, m.group(0)))
            if len(hits) >= 50:
                break
        if hits:
            sample = '; '.join(f'{r}: {p}' for r, p in hits[:5])
            raise PackageError(
                f'--redact-paths=fail: {len(hits)} absolute path(s) remain in rendered pages '
                f'(e.g. {sample}); scrub the source or use the default --redact-paths=strip')
        return 0
    n = 0
    for rel, ap in entries:
        if _is_asset_rel(rel) or not rel.endswith(_REDACT_TEXT_EXT):
            continue
        new, k = _strip_bytes(open(ap, 'rb').read())
        if k:
            with open(ap, 'wb') as f:
                f.write(new)
            n += k
    return n


# Tree-relative navigation that only resolves inside the rendered tree -- dead in a detached one-pager.
# Each is a cleanly-delimited, non-nesting element generated by the chrome builders.
_DETACH_RES = (
    # the run selector: its options point to run/<key>/summary.html siblings not bundled with a lone file
    re.compile(rb'<rdc-ab-picker><label for="rdc-run-select">.*?</rdc-ab-picker>', re.S),
    re.compile(rb'<nav class="crumb">.*?</nav>', re.S),          # breadcrumb (root catalog / dashboard)
    re.compile(rb'<a class="sb-link"[^>]*>.*?</a>', re.S),       # summary-bar "dashboard" link
)


def _detach_summary(html: bytes) -> bytes:
    """Make the standalone one-pager genuinely self-contained (R-21): strip the tree-relative navigation
    that cannot work in a LONE file -- the run selector (a silently-dead dropdown), the breadcrumb, and
    the summary-bar dashboard link. The page's own content (verdict, KPIs, movement, by-area) is
    self-contained and untouched; the in-tree `_reports/summary.html` keeps its working nav."""
    for rx in _DETACH_RES:
        html = rx.sub(b'', html)
    return html


def _redacted_summary_bytes(staging: str, summary_rel: str, *, newest: bool, target,
                            build_ts: str, shared: bool, redact_paths: str) -> bytes:
    """The standalone one-pager for a redacted bundle: self-contained (INLINE) + redacted.

    INLINE bundle modes already re-rendered the summary self-contained into ``staging`` (and the strip
    pass already touched it). The shared bundle's staging summary is REF-linked, so render a dedicated
    self-contained INLINE+redact copy here -- safe because the REF copy was already zipped. In ``strip``
    mode the bytes are stripped (idempotent for the INLINE-mode file; necessary for the freshly rendered
    shared one). The summary is a verdict page with no path cells, so it is not scanned in ``fail`` mode.
    """
    summ_path = os.path.join(_paths.reports_dir(staging), summary_rel)
    if shared:
        from .reports import base as _rbase, summary as _summary
        kw = {} if newest else {'run_label': target.label, 'run_date': target.date}
        _summary.build(staging, sink=_rbase.AssetSink.INLINE, build_ts=build_ts, redact=True, **kw)
    raw = open(summ_path, 'rb').read()
    if redact_paths == 'strip':
        raw, _ = _strip_bytes(raw)
    return raw


def _drill_index_rels(root: str) -> list[tuple[str, str, str]]:
    """Existing per-drop browser pages as ``(area, drop, rel)`` (``rel`` relative to ``<root>``).

    Mirrors ``<root>/_reports/drill/<area>/<drop>/index.html`` so the shared re-render reproduces the
    EXACT drill set in the source tree (robust to a ``_data``-only tree / cleaned raw ``.rdc`` inputs).
    """
    out: list[tuple[str, str, str]] = []
    drill_root = os.path.join(_paths.reports_dir(root), _paths.DRILL_DIR)
    if not os.path.isdir(drill_root):
        return out
    for dirpath, _dirs, files in os.walk(drill_root):
        if _paths.INDEX_HTML not in files:
            continue
        rel = os.path.relpath(os.path.join(dirpath, _paths.INDEX_HTML), root).replace('\\', '/')
        parts = rel.split('/')  # _reports / drill / <area> / <drop> / index.html
        if len(parts) == 5:
            out.append((parts[2], parts[3], rel))
    return out


def _collect_shared(root: str, staging: str) -> list[tuple[str, str]]:
    """The shared bundle's source files as ``(rel, abspath)``.

    The whole tree (REF HTML + ``_pagedata`` + the raw ``_data`` copy) was rendered into ``staging``,
    so reuse ``_collect`` over it; then add the shared ``_assets/*`` (which ``_collect``'s
    html/_pagedata/_data filter does not match) and the optional ``_reports/_chrome_preview.html`` (the
    preview gallery is produced by `bobframes preview`, not the orchestrator -> copy it raw from ``<root>``
    so the shared file-set matches ``--inline``).
    """
    out = _collect(staging, light=False)
    assets_dir = os.path.join(staging, _paths.ASSETS_DIR)
    if os.path.isdir(assets_dir):
        for fn in sorted(os.listdir(assets_dir)):
            ap = os.path.join(assets_dir, fn)
            if os.path.isfile(ap):
                out.append((f'{_paths.ASSETS_DIR}/{fn}', ap))
    preview = os.path.join(_paths.reports_dir(root), '_chrome_preview.html')
    if os.path.isfile(preview):
        out.append((f'{_paths.REPORTS_DIR}/_chrome_preview.html', preview))
    return out


def _ensure_outside(out_dir: str, root: str) -> None:
    """Raise if ``out_dir`` is ``<root>`` itself or nested inside it (the non-mutation guard)."""
    d = os.path.normcase(os.path.abspath(out_dir))
    r = os.path.normcase(os.path.abspath(root))
    try:
        common = os.path.commonpath([d, r])
    except ValueError:
        return  # different drives -> definitely outside
    if common == r:
        raise PackageError(
            f'output dir {out_dir!r} is inside the read tree {root!r}; '
            f'pass --out to a location outside <root>')
