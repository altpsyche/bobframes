"""`bobframes package` -- the shareable bundle + standalone summary (c16s/c16t, ADR-40/41).

The bundle DEFAULTS to shared-assets (c16t): the ~95 KB of chrome lives once per family under `_assets/`
and every page links it depth-relative, re-rendered from the `head_assets(REF)` seam (no scrape). The
`shared/` tree is the stored golden (HTML via `normalize`, `_pagedata`/`_assets`/README raw; parquet by
`parquet_digest` vs source, not stored). `--inline` reproduces the c16s self-contained-per-page bundle,
whose HTML is a byte-identical copy of the render output -> it REUSES the render `golden/` (no duplicate
stored tree). Refresh the shared golden with `python -m bobframes.tests.make_package_golden`.

Gate (QUALITY_GATES §21.1s): non-mutation, determinism, round-trip, inline/light vs the render golden,
the shared tree vs `golden_package/shared/`, `_assets/` == composer output, the inline font ABSENT from
every shared page, depth-correct `_assets/` links produced by `head_assets(REF)`, no `fetch(`/modules,
the size win, the standalone summary self-contained, README + naming, `--format` rejected.
"""
from __future__ import annotations

import hashlib
import os
from types import SimpleNamespace

import pytest

from . import _render_util as u
from .. import package as pkg
from ..reports import all_reports, chrome
from ..reports import discovery as disc
from ..html import template

# The inline base64 @font-face data URI lives once in `_assets/report.css`/`catalog.css` for the shared
# bundle; its presence in a *page* would mean that page still inlines chrome (a dedup miss).
FONT_MARKER = "data:font/woff2;base64"
SHARED_GOLDEN = os.path.join(os.path.dirname(__file__), "data", "golden_package", "shared")


def _only_dir(extract_root: str) -> str:
    """The single top-level `<project>-<rundate>/` folder a bundle extracts to."""
    entries = os.listdir(extract_root)
    assert len(entries) == 1, f"expected one top folder, got {entries}"
    return entries[0]


def _top(tree: str) -> str:
    return os.path.join(tree, _only_dir(tree))


def _family(rel: str) -> str:
    """Which page family a bundled HTML rel belongs to (decides report.* vs catalog.* assets)."""
    if rel == "index.html" or (rel.startswith("_reports/drill/") and rel.endswith("/index.html")):
        return "catalog"
    return "report"


def _target(dest: str):
    return disc.current_run(disc.discover_drops(dest))


def _source_digest(root: str):
    """A logical fingerprint of the source tree (parquet digests + HTML/js content hashes)."""
    def _h(rel):
        return hashlib.sha256(open(os.path.join(root, rel), "rb").read()).hexdigest()
    return (u.compute_digest_map(root),
            {rel: _h(rel) for rel in u.rendered_html_files(root)},
            {rel: _h(rel) for rel in u.rendered_page_data_files(root)})


@pytest.fixture(scope="module")
def env(tmp_path_factory):
    base = tmp_path_factory.mktemp("pkg")
    dest = u.render_fresh(str(base / "root"))
    # DEFAULT = the shared-asset bundle (c16t), with the DEFAULT name + location (parent of <root>).
    shared_zip, shared_summary = pkg.build(dest)
    # `--inline` opt-out (the c16s self-contained-per-page bundle); its own out dir.
    inline_zip, inline_summary = pkg.build(dest, out=str(base / "inl" / "x.zip"), inline=True)
    # `--light` (inherently self-contained); its own out dir, no summary file.
    light_zip, _ = pkg.build(dest, out=str(base / "lite" / "x.zip"), summary_file=False, light=True)
    return SimpleNamespace(
        dest=dest,
        shared_zip=shared_zip, shared_summary=shared_summary,
        shared_tree=u.extract_zip(shared_zip, str(base / "shared_x")),
        inline_zip=inline_zip, inline_summary=inline_summary,
        inline_tree=u.extract_zip(inline_zip, str(base / "inline_x")),
        light_tree=u.extract_zip(light_zip, str(base / "light_x")),
    )


# --- inline (--inline) bundle == render golden (byte-identical copy) ------------------------------

def test_inline_html_matches_render_golden(env):
    root = _top(env.inline_tree)
    for rel in u.rendered_html_files(u.GOLDEN_DIR):
        g = u.normalize(open(os.path.join(u.GOLDEN_DIR, rel), encoding="utf-8").read())
        a = u.normalize(open(os.path.join(root, rel), encoding="utf-8").read())
        assert a == g, f"bundled HTML diverged from render golden: {rel}"


def test_inline_pagedata_matches_render_golden(env):
    root = _top(env.inline_tree)
    for rel in u.rendered_page_data_files(u.GOLDEN_DIR):
        g = open(os.path.join(u.GOLDEN_DIR, rel), encoding="utf-8").read()
        a = open(os.path.join(root, rel), encoding="utf-8").read()
        assert a == g, f"bundled _pagedata diverged from render golden: {rel}"


def test_inline_file_set(env):
    root = _top(env.inline_tree)
    got = set(u.tree_files(root))
    assert pkg.README_NAME in got
    assert set(u.rendered_html_files(u.GOLDEN_DIR)) <= got
    assert set(u.rendered_page_data_files(u.GOLDEN_DIR)) <= got
    assert set(u.rendered_parquet_files(env.dest)) <= got
    # raw capture inputs + working dirs are not viewable output -> never bundled.
    assert not any(r.endswith(".rdc") or "/_cache/" in r or r.startswith("_cache/") for r in got)
    # --inline is self-contained per page -> NO shared assets.
    assert not any(r == "_assets" or r.startswith("_assets/") for r in got)


def test_inline_parquet_digests_match_source(env):
    """Parquet is copied raw -> the bundle's digest equals the source's (no corruption, no rewrite)."""
    root = _top(env.inline_tree)
    for rel in u.rendered_parquet_files(env.dest):
        a = u.parquet_digest(os.path.join(root, rel))
        g = u.parquet_digest(os.path.join(env.dest, rel))
        assert a == g, f"bundled parquet diverged from source: {rel}"


# --- shared-asset bundle (DEFAULT, c16t) ----------------------------------------------------------

def test_shared_tree_matches_golden(env):
    root = _top(env.shared_tree)
    golden_files = set(u.tree_files(SHARED_GOLDEN))
    for rel in golden_files:
        g = open(os.path.join(SHARED_GOLDEN, rel), encoding="utf-8").read()
        a = open(os.path.join(root, rel), encoding="utf-8").read()
        if rel.endswith(".html"):
            a = u.normalize(a)
        assert a == g, f"shared bundle diverged from golden: {rel}"
    # file-set: the bundle minus _data == the stored golden (parquet gated separately, below).
    got = {r for r in u.tree_files(root) if not (r == "_data" or r.startswith("_data/"))}
    assert got == golden_files


def test_shared_parquet_digests_match_source(env):
    root = _top(env.shared_tree)
    for rel in u.rendered_parquet_files(env.dest):
        a = u.parquet_digest(os.path.join(root, rel))
        g = u.parquet_digest(os.path.join(env.dest, rel))
        assert a == g, f"shared bundle parquet diverged from source: {rel}"


def test_shared_assets_equal_composer(env):
    """ADR-41 zero-drift: each `_assets/*` file IS the composer output the REF heads link to."""
    root = _top(env.shared_tree)

    def rd(name):
        return open(os.path.join(root, "_assets", name), encoding="utf-8").read()
    assert rd("report.css") == chrome._compose_css()
    assert rd("report.js") == chrome._compose_js()
    assert rd("catalog.css") == template._CSS
    assert rd("catalog.js") == template.reports_base.rdc_table_js()


def test_shared_font_absent_from_every_page(env):
    root = _top(env.shared_tree)
    for rel in u.rendered_html_files(root):
        page = open(os.path.join(root, rel), encoding="utf-8").read()
        assert FONT_MARKER not in page, f"inline font still in shared page {rel}"


def test_shared_pages_produced_by_ref_seam(env):
    """Every bundled page carries EXACTLY `head_assets(REF, depth)` for its family (no scrape; the
    depth-relative `_assets/` prefix is correct). Generic over the whole tree, so a future page that
    skips the sink threading is caught here, not only if it happens to be fixtured."""
    root = _top(env.shared_tree)
    for rel in u.rendered_html_files(root):
        depth = rel.count("/")
        page = open(os.path.join(root, rel), encoding="utf-8").read()
        if _family(rel) == "catalog":
            ha = template.head_assets(chrome.AssetSink.REF, depth)
        else:
            ha = chrome.head_assets(chrome.AssetSink.REF, depth)
        assert ha.head and ha.head in page, f"REF head missing/incorrect in {rel}"
        if ha.body_js:
            assert ha.body_js in page, f"REF body_js missing in {rel}"


def test_shared_covers_every_report(env):
    """Footgun guard: every `all_reports()` member has a top-level shared page that is font-free and
    REF-linked. Adding a report that forgets `sink=sink` fails here generically."""
    root = _top(env.shared_tree)
    files = set(u.rendered_html_files(root))
    rep_head = chrome.head_assets(chrome.AssetSink.REF, 1).head
    for mod in all_reports():
        stem = mod.__name__.rsplit(".", 1)[-1]
        rel = f"_reports/{stem}.html"
        assert rel in files, f"{rel} missing from the shared bundle"
        page = open(os.path.join(root, rel), encoding="utf-8").read()
        assert FONT_MARKER not in page, f"{rel} still inlines the font"
        assert rep_head in page, f"{rel} not linked to shared _assets via head_assets(REF, 1)"


def test_shared_no_fetch_or_module(env):
    root = _top(env.shared_tree)
    for rel in u.tree_files(root):
        if rel.endswith((".html", ".js", ".css")):
            txt = open(os.path.join(root, rel), encoding="utf-8", errors="ignore").read()
            assert "fetch(" not in txt, f"fetch( in {rel}"
            assert 'type="module"' not in txt, f'type="module" in {rel}'


def test_shared_size_win(env):
    """The deduped bundle's HTML is smaller than `--inline` by at least one inlined chrome head per
    extra report page (the duplication a zip's per-entry DEFLATE cannot collapse, ADR-41)."""
    sroot, iroot = _top(env.shared_tree), _top(env.inline_tree)

    def html_bytes(root):
        return sum(os.path.getsize(os.path.join(root, r)) for r in u.rendered_html_files(root))
    rep_inline = len(chrome.head_assets(chrome.AssetSink.INLINE).head.encode("utf-8"))
    report_pages = [r for r in u.rendered_html_files(iroot) if _family(r) == "report"]
    threshold = (len(report_pages) - 1) * rep_inline
    assert html_bytes(iroot) - html_bytes(sroot) >= threshold


def test_shared_non_mutation(tmp_path):
    """The shared (default) re-render reads <root> + its cache and writes ONLY staging/zip/summary."""
    dest = u.render_fresh(str(tmp_path / "root"))
    before = _source_digest(dest)
    pkg.build(dest, out=str(tmp_path / "out" / "b.zip"))
    assert _source_digest(dest) == before


# --- light bundle --------------------------------------------------------------------------------

def test_light_tree(env):
    root = _top(env.light_tree)
    got = set(u.tree_files(root))
    assert "index.html" in got and pkg.README_NAME in got
    assert all(not r.startswith("_data/") for r in got), "light must not carry _data"
    assert all("/_pagedata/" not in r and not r.startswith("_pagedata/") for r in got), \
        "light must not carry _pagedata"
    assert all("/drill/" not in r for r in got), "light must not carry drill pages"
    assert not any(r == "_assets" or r.startswith("_assets/") for r in got), \
        "light is self-contained -> no shared assets"
    reports = [r for r in got if r.startswith("_reports/")]
    assert reports and all(r.count("/") == 1 and r.endswith(".html") for r in reports), \
        "light _reports is the top-level pages only"
    for rel in reports + ["index.html"]:
        g = u.normalize(open(os.path.join(u.GOLDEN_DIR, rel), encoding="utf-8").read())
        a = u.normalize(open(os.path.join(root, rel), encoding="utf-8").read())
        assert a == g, f"light HTML diverged from render golden: {rel}"


# --- contract: non-mutation, determinism, reproducible zip ---------------------------------------

def test_build_does_not_mutate_source(tmp_path):
    dest = u.render_fresh(str(tmp_path / "root"))
    before = _source_digest(dest)
    pkg.build(dest, out=str(tmp_path / "out" / "b.zip"), inline=True)
    assert _source_digest(dest) == before


def test_package_is_deterministic(env, tmp_path):
    """Two shared (default) builds are byte-identical -- the re-render's build_ts is pinned (c16t)."""
    z1, _ = pkg.build(env.dest, out=str(tmp_path / "a" / "x.zip"), summary_file=False)
    z2, _ = pkg.build(env.dest, out=str(tmp_path / "b" / "x.zip"), summary_file=False)
    t1, t2 = u.extract_zip(z1, str(tmp_path / "ax")), u.extract_zip(z2, str(tmp_path / "bx"))
    f1, f2 = u.tree_files(t1), u.tree_files(t2)
    assert f1 == f2
    for rel in f1:
        assert open(os.path.join(t1, rel), "rb").read() == open(os.path.join(t2, rel), "rb").read(), rel


def test_zip_entries_are_reproducible(env):
    import zipfile
    with zipfile.ZipFile(env.shared_zip) as zf:
        infos = zf.infolist()
    assert infos
    for zi in infos:
        assert zi.date_time == (1980, 1, 1, 0, 0, 0), zi.filename
        assert zi.compress_type == zipfile.ZIP_DEFLATED, zi.filename


# --- friendly artifacts ---------------------------------------------------------------------------

def test_standalone_summary_self_contained(env):
    """The standalone summary is INLINE (self-contained) in BOTH modes -- a verbatim copy of the
    source one-pager, so it works emailed alone even though the shared bundle's pages link `_assets/`."""
    for p in (env.shared_summary, env.inline_summary):
        assert os.path.isfile(p)
        project = os.path.basename(os.path.normpath(env.dest))
        assert os.path.basename(p) == f"{project}-{_target(env.dest).date}-summary.html"
        html = open(p, encoding="utf-8").read()
        assert "_assets/" not in html, "standalone summary must not link shared assets"
        assert FONT_MARKER in html, "standalone summary must inline its own font"
        assert "fetch(" not in html and 'type="module"' not in html, "JS-self-contained / file://-safe"
        # it is exactly the rendered one-pager (already inline via head_assets(INLINE), c16q).
        with open(p, "rb") as a, open(os.path.join(env.dest, "_reports", "summary.html"), "rb") as b:
            assert a.read() == b.read()


def test_readme_present_and_ascii(env):
    root = _top(env.shared_tree)
    data = open(os.path.join(root, pkg.README_NAME), "rb").read()
    data.decode("ascii")  # raises on any non-ASCII byte
    assert data == pkg.README_TEXT.encode("ascii")


def test_default_zip_name(env):
    project = os.path.basename(os.path.normpath(env.dest))
    assert os.path.basename(env.shared_zip) == f"{project}-{_target(env.dest).date}-report.zip"


# --- taxonomy + edge cases ------------------------------------------------------------------------

def test_stage_materializes_tree(env, tmp_path):
    project = os.path.basename(os.path.normpath(env.dest))
    topdir = f"{project}-{_target(env.dest).date}"
    out = tmp_path / "s"
    pkg.build(env.dest, out=str(out / "x.zip"), summary_file=False, stage=True)
    stage_dir = out / (topdir + ".stage")
    assert (stage_dir / topdir / "index.html").is_file()
    assert (stage_dir / topdir / pkg.README_NAME).is_file()


def test_package_rejects_format_flag():
    from .. import cli
    with pytest.raises(SystemExit):       # ADR-40: `package` is a PRESENTATION verb, never --format
        cli.main(["package", "anywhere", "--format", "zip"])


def test_not_a_rendered_tree(tmp_path):
    with pytest.raises(pkg.PackageError):
        pkg.build(str(tmp_path))          # no _reports/ dir


def test_out_inside_root_rejected(env, tmp_path):
    with pytest.raises(pkg.PackageError):
        pkg.build(env.dest, out=os.path.join(env.dest, "inside.zip"))


def test_unknown_run_rejected(env, tmp_path):
    with pytest.raises(pkg.PackageError):
        pkg.build(env.dest, out=str(tmp_path / "o" / "x.zip"), run="9999-99-99_nope")
