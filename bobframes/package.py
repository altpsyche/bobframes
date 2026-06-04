"""``bobframes package`` -- bundle a rendered tree into a shareable artifact set (c16s, ADR-40/41).

A deterministic, NON-MUTATING stream transform: read an already-rendered ``<root>`` and write, OUTSIDE
that tree, two friendly artifacts:

  * ``<project>-<rundate>-report.zip`` -- the full viewable tree under a single ``<project>-<rundate>/``
    folder, plus a recipient ``README.txt``;
  * ``<project>-<rundate>-summary.html`` -- a standalone, self-contained copy of the exec one-pager
    (c16q) you can email / double-click / print to PDF with no unzip.

c16s delivery is INLINE (each page self-contained -- exactly today's render bytes, so the HTML transform
is an identity copy). ``--shared-assets`` (the deduped ``_assets/`` bundle) lands at c16t and ``--redact``
at c16u; their flags arrive WITH their implementations. No new dependency -- stdlib ``zipfile`` only; the
zip is reproducible (fixed entry timestamps + pinned DEFLATE), so the gate reads the tree back out rather
than byte-comparing zip bytes (zlib/Python variance, ADR-40).
"""
from __future__ import annotations

import logging
import os
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
          summary_file: bool = True, stage: bool = False,
          run: str | None = None) -> tuple[str, str]:
    """Package an already-rendered ``<root>`` into ``(zip_path, summary_path)``, both OUTSIDE ``<root>``.

    Non-mutating: ``<root>`` is only read. ``run`` selects the run whose ``drop_date`` names the
    artifacts (a ``DropSet.key`` like ``2026-05-28_r110600``); default is the newest run. ``light``
    bundles only ``index.html`` + the top-level ``_reports/*.html`` (no drill / ``_pagedata`` / ``_data``).
    ``summary_file=False`` skips the standalone one-pager (``summary_path`` is then ``''``). ``stage=True``
    also materializes the bundle tree to a sibling ``.stage`` dir for inspection.
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

    entries = _collect(root, light=light)

    # Reproducible zip: fixed arcname order, fixed entry timestamps, pinned DEFLATE, per-entry writestr;
    # one file read into memory at a time (memory stays O(largest file), not O(tree)).
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
    log.info(
        f'packaged {file_count} files, {bundle_bytes} bytes; '
        f'{dup} duplicated-chrome bytes (deduped by shared-assets, c16t); '
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
