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
import shutil
import tempfile
import zipfile

from . import paths as _paths
from .errors import EXIT_USER_ERROR, BobFramesError

log = logging.getLogger('bobframes')

# Fixed ZipInfo timestamp -> reproducible archives (the DOS/zip epoch; 1980-01-01 is the minimum a
# ZipInfo accepts). The only wall-clock the verb touches is the `[HH:MM:SS]` log-line prefix.
_ZIP_DATE = (1980, 1, 1, 0, 0, 0)

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
          run: str | None = None) -> tuple[str, str]:
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
    """
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
    src_summary = ''
    if summary_file:
        if target.key == drops[-1].key:
            src_summary = os.path.join(_paths.reports_dir(root), 'summary.html')
        else:
            src_summary = os.path.join(_paths.reports_dir(root), _paths.RUN_DIR, target.key, 'summary.html')
        if not os.path.isfile(src_summary):
            raise PackageError(
                f'no rendered summary at {src_summary}; run `bobframes render` first '
                f'(or pass --no-summary-file)')

    # Bundle entries as (rel, abspath). Default = shared-assets: re-render the REF form into a temp
    # staging dir (reading <root>, writing staging) and stream _data raw from <root>; `--inline`/`--light`
    # keep the c16s identity copy of the live <root>. Staging lives only long enough to read its files
    # into the zip, then is removed (the zip is the artifact; `--stage` extracts the zip, not staging).
    shared = not inline and not light
    staging: str | None = None
    try:
        if shared:
            staging = tempfile.mkdtemp(prefix=f'{topdir}.', dir=out_dir)
            _render_shared(root, staging, build_ts=rundate)
            entries = _collect_shared(root, staging)
        else:
            entries = _collect(root, light=light)

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
    finally:
        if staging is not None:
            shutil.rmtree(staging, ignore_errors=True)

    if summary_file:
        with open(src_summary, 'rb') as f:
            summary_bytes = f.read()
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
    log.info(
        f'packaged {file_count} files, {bundle_bytes} bytes; {chrome_note}; '
        f'summary {summary_path or "(skipped)"}; zip {zip_path}')

    return zip_path, summary_path


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


def _render_shared(root: str, staging: str, *, build_ts: str) -> None:
    """Re-render the tree in REF (shared-asset) form into ``staging`` (c16t, ADR-41).

    ``_data`` is copied RAW into ``staging`` (no derive -> parquet bytes verbatim -> digests match the
    source) so the re-render reads AND links within ONE tree: the relative drill / CSV / parquet links
    resolve INSIDE the bundle (a decoupled out-dir would make them escape into the source tree). The
    whole tree is then rendered with ``sink=REF``; ``build_ts`` pins a deterministic "built" stamp on
    the report family so two packages are byte-identical (the standalone summary + the ``--inline`` copy
    keep the source wall-clock stamp -- ADR-23 records the divergence). ``<root>`` is only ever READ.
    """
    from .reports import ab as _ab, base as _rbase, discovery as _disc, orchestrator as _orch
    from .html import template as _template
    from . import manifest as _manifest
    REF = _rbase.AssetSink.REF

    src_data = _paths.data_root(root)
    if os.path.isdir(src_data):
        shutil.copytree(src_data, _paths.data_root(staging))

    def _silent(_msg: str) -> None:
        pass

    rc = _orch.render_all_reports(staging, _silent, sink=REF, build_ts=build_ts)
    if rc != 0:
        raise PackageError(
            f'shared re-render of {root!r} failed; cannot build a deduped bundle (try --inline)')

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
            sink=REF, depth=rel.count('/'))

    # A/B pairs: render-only never emits ab/, so this is usually a no-op. When present, resolve each
    # <baselineKey>_vs_<compareKey> dir back to its DropSets and re-render REF; an unresolvable pair is
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
                    f'shared bundle (use --inline to bundle them verbatim)')
                continue
            _ab.render_pair(staging, baseline, compare, sink=REF, build_ts=build_ts)

    _write_assets(staging)


def _write_assets(staging: str) -> None:
    """Write the per-family shared chrome assets under ``staging/_assets/`` from the manifests (c16t).

    Each file's bytes ARE the composer output the REF heads link to (``AssetFile.content()``), so the
    asset boundary is one source of truth -- zero drift, no scrape (ADR-41). Two families, distinct
    files: ``report.{css,js}`` (page_open family) + ``catalog.{css,js}`` (template family).
    """
    from .reports import chrome as _chrome
    from .html import template as _template
    assets_dir = os.path.join(staging, _paths.ASSETS_DIR)
    os.makedirs(assets_dir, exist_ok=True)
    for a in (*_chrome.REPORT_ASSETS, *_template.CATALOG_ASSETS):
        with open(os.path.join(assets_dir, a.name), 'w', encoding='utf-8') as f:
            f.write(a.content())


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
