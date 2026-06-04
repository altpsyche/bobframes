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
from .make_synthetic import SYNTH_HOST_INFO, SYNTH_TOOL_VERSIONS

# The inline base64 @font-face data URI lives once in `_assets/report.css`/`catalog.css` for the shared
# bundle; its presence in a *page* would mean that page still inlines chrome (a dedup miss).
FONT_MARKER = "data:font/woff2;base64"
_GOLDEN_PKG = os.path.join(os.path.dirname(__file__), "data", "golden_package")
SHARED_GOLDEN = os.path.join(_GOLDEN_PKG, "shared")
REDACTED_GOLDEN = os.path.join(_GOLDEN_PKG, "redacted")
SHARED_REDACTED_GOLDEN = os.path.join(_GOLDEN_PKG, "shared_redacted")
REDACTED_STRIP = '<div class="device-strip">redacted</div>'
# The synthetic's known device/host values (G-6/G-7) -- must appear NOWHERE in a redacted bundle.
SYNTH_DEVICE_VALUES = [v for v in SYNTH_HOST_INFO.values() if v != SYNTH_HOST_INFO["bobframes"]]
SYNTH_DEVICE_VALUES += list(SYNTH_TOOL_VERSIONS.values())


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
    # `--redact` (c16u): inline-sink + redact (`redacted/`) and shared + redact (`shared_redacted/`).
    red_zip, red_summary = pkg.build(dest, out=str(base / "red" / "x.zip"), inline=True, redact=True)
    sred_zip, sred_summary = pkg.build(dest, out=str(base / "sred" / "x.zip"), redact=True)
    return SimpleNamespace(
        dest=dest,
        shared_zip=shared_zip, shared_summary=shared_summary,
        shared_tree=u.extract_zip(shared_zip, str(base / "shared_x")),
        inline_zip=inline_zip, inline_summary=inline_summary,
        inline_tree=u.extract_zip(inline_zip, str(base / "inline_x")),
        light_tree=u.extract_zip(light_zip, str(base / "light_x")),
        red_summary=red_summary, red_tree=u.extract_zip(red_zip, str(base / "red_x")),
        sred_summary=sred_summary, sred_tree=u.extract_zip(sred_zip, str(base / "sred_x")),
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


# --- redaction (--redact, c16u, ADR-40) -----------------------------------------------------------

def _red_trees(env):
    """(extracted top, golden dir) for both redacted variants."""
    return [(_top(env.red_tree), REDACTED_GOLDEN), (_top(env.sred_tree), SHARED_REDACTED_GOLDEN)]


def test_redacted_tree_matches_golden(env):
    for root, golden in _red_trees(env):
        golden_files = set(u.tree_files(golden))
        for rel in golden_files:
            g = open(os.path.join(golden, rel), encoding="utf-8").read()
            a = open(os.path.join(root, rel), encoding="utf-8").read()
            if rel.endswith(".html"):
                a = u.normalize(a)
            assert a == g, f"redacted bundle diverged from golden {golden}: {rel}"
        got = {r for r in u.tree_files(root) if not (r == "_data" or r.startswith("_data/"))}
        assert got == golden_files, f"redacted file-set != golden for {golden}"


def test_redacted_no_device_value(env):
    """The lifespan footgun net: NO device value on ANY rendered page/_pagedata of EITHER redacted tree
    (a future report that forgets `redact=redact` surfaces its un-redacted strip here, generically)."""
    saw_redacted_strip = False
    for root, _golden in _red_trees(env):
        surfaces = list(u.rendered_html_files(root)) + list(u.rendered_page_data_files(root))
        assert surfaces
        for rel in surfaces:
            txt = open(os.path.join(root, rel), encoding="utf-8").read()
            for val in SYNTH_DEVICE_VALUES:
                assert val not in txt, f"device value {val!r} leaked into {rel} of {root}"
            assert "gpu <strong>" not in txt and "driver <strong>" not in txt, \
                f"un-redacted device-strip markup in {rel}"
            if REDACTED_STRIP in txt:
                saw_redacted_strip = True
    assert saw_redacted_strip, "no page carried the redacted device strip (scrub never exercised)"


def test_redacted_excludes_provenance_sidecars(env):
    """The provenance-only `_data` sidecars are dropped wholesale from a redacted bundle (the manifest's
    host_info + frame_metadata's gl_renderer would otherwise leak raw)."""
    for root, _golden in _red_trees(env):
        got = set(u.tree_files(root))
        assert not any(os.path.basename(r) in ("_manifest.json", "frame_metadata.jsonl") for r in got), \
            f"a provenance sidecar survived in {root}"


def test_redacted_no_dangling_sidecar_links(env):
    """Dropping the sidecars is safe only if no page links them -- prove it (no dead links)."""
    for root, _golden in _red_trees(env):
        for rel in list(u.rendered_html_files(root)) + list(u.rendered_page_data_files(root)):
            txt = open(os.path.join(root, rel), encoding="utf-8").read()
            assert "_manifest.json" not in txt and "frame_metadata.jsonl" not in txt, \
                f"{rel} references a dropped sidecar"


def test_redacted_data_text_files_are_known(env):
    """Denylist -> tripwire: the redacted bundle's `_data` TEXT files are only the CSV twins +
    `_resource_labels.json`. A NEW provenance-bearing sidecar trips this and forces a redact decision."""
    root = _top(env.sred_tree)  # shared_redacted carries the full _data
    data_text = [r for r in u.tree_files(root)
                 if r.startswith("_data/") and r.endswith((".csv", ".json", ".jsonl"))]
    assert data_text, "expected _data text files to gate"
    # Known-safe _data text: CSV table twins (path columns scrubbed by the strip pass) + the per-drop
    # resource labels + the catalog summary (counts/areas only -- verified no device/host fields).
    known_json = ("_resource_labels.json", "_catalog.json")
    for r in data_text:
        base = os.path.basename(r)
        assert base.endswith(".csv") or base in known_json, \
            f"unexpected _data text file {r} -- a new sidecar may carry provenance; review redaction"


def test_redacted_abs_path_scan_clean(env):
    """strip mode (default): no absolute-path token remains in the bundle's text (incl. CSV)."""
    for root, _golden in _red_trees(env):
        for rel in u.tree_files(root):
            if not rel.endswith((".html", ".js", ".csv", ".json", ".jsonl")):
                continue
            if rel == "_assets" or rel.startswith("_assets/"):
                continue
            txt = open(os.path.join(root, rel), "rb").read().decode("utf-8", "surrogateescape")
            m = pkg._ABS_PATH.search(txt)
            assert m is None, f"abs-path {m.group(0)!r} survived strip in {rel}"


def test_redacted_standalone_summary(env):
    """Both redacted standalone summaries stay self-contained (INLINE) AND carry no device value."""
    for p in (env.red_summary, env.sred_summary):
        assert os.path.isfile(p)
        html = open(p, encoding="utf-8").read()
        assert "_assets/" not in html, "redacted standalone summary must not link shared assets"
        assert FONT_MARKER in html, "redacted standalone summary must inline its own font"
        assert "fetch(" not in html and 'type="module"' not in html
        assert REDACTED_STRIP in html, "redacted standalone summary missing the redacted strip"
        for val in SYNTH_DEVICE_VALUES:
            assert val not in html, f"device value {val!r} leaked into the standalone summary"


def test_redacted_non_mutation(tmp_path):
    dest = u.render_fresh(str(tmp_path / "root"))
    before = _source_digest(dest)
    pkg.build(dest, out=str(tmp_path / "out" / "b.zip"), redact=True)
    assert _source_digest(dest) == before


def test_redacted_is_deterministic(env, tmp_path):
    z1, _ = pkg.build(env.dest, out=str(tmp_path / "a" / "x.zip"), summary_file=False, redact=True)
    z2, _ = pkg.build(env.dest, out=str(tmp_path / "b" / "x.zip"), summary_file=False, redact=True)
    t1, t2 = u.extract_zip(z1, str(tmp_path / "ax")), u.extract_zip(z2, str(tmp_path / "bx"))
    assert u.tree_files(t1) == u.tree_files(t2)
    for rel in u.tree_files(t1):
        assert open(os.path.join(t1, rel), "rb").read() == open(os.path.join(t2, rel), "rb").read(), rel


# --- redaction: crafted-input unit tests (ADR-23: the synthetic has no abs-path value / gl_renderer) --

def test_provenance_strip_redact_mode():
    s = chrome.provenance_strip(SYNTH_HOST_INFO, SYNTH_TOOL_VERSIONS, redact=True)
    assert s == REDACTED_STRIP
    for val in SYNTH_DEVICE_VALUES:
        assert val not in s
    assert chrome.provenance_strip({}, {}, redact=True) == ""  # nothing to redact -> empty


def test_strip_bytes_replaces_drive_paths_only():
    """Drive-letter abs paths are stripped; the base64 font, relative backslash paths (a shader resource
    ref like `shader_src\\2192.glsl` -- the real-Perf false-positive that bit us), and UNC paths are NOT
    touched (the c16u 'no false positives' goal; UNC + forward-slash drive are recorded limitations)."""
    font = "url(data:font/woff2;base64,d09GMgABAAAAAA/+aZ==)"  # base64 has no `:\` -> untouched
    body = (
        'shader at C:\\Users\\dev\\proj\\cache\\shaders\\frag.spv done. '          # drive -> stripped
        '{"src_file_path": "shader_src\\\\2192.glsl", "abs": "D:\\\\Caps\\\\f.rdc"} ' + font
    )
    out, n = pkg._strip_bytes(body.encode("utf-8"))
    txt = out.decode("utf-8")
    assert n == 2, "exactly the two drive-letter paths (C:\\... and D:\\...) are stripped"
    assert pkg._ABS_PATH.search(txt) is None, "a drive-letter path survived the strip"
    assert pkg._PATH_REDACTED in txt
    assert font in txt, "the base64 font must be untouched (no `:\\` to match)"
    assert "shader_src\\\\2192.glsl" in txt, "a RELATIVE backslash path must NOT be redacted (no drive)"
    import json
    assert json.loads('{"src_file_path": "shader_src\\\\2192.glsl", "abs": "<path redacted>"}')


def test_redact_paths_fail_raises_on_planted_leak(tmp_path):
    leak = tmp_path / "page.html"
    leak.write_text("<p>built at C:\\Users\\ci\\secret\\cap.rdc</p>", encoding="utf-8")
    entries = [("_reports/x.html", str(leak))]
    with pytest.raises(pkg.PackageError):
        pkg._redact_text_files(entries, mode="fail")
    # strip mode sanitizes the same file in place (no raise)
    n = pkg._redact_text_files(entries, mode="strip")
    assert n == 1
    assert "C:\\Users" not in leak.read_text(encoding="utf-8")


def test_redact_paths_fail_clean_passes(tmp_path):
    clean = tmp_path / "page.html"
    clean.write_text("<p>no paths here, just text</p>", encoding="utf-8")
    assert pkg._redact_text_files([("_reports/x.html", str(clean))], mode="fail") == 0


def test_redact_paths_fail_requires_redact(env, tmp_path):
    from .. import cli
    rc = cli.main(["package", env.dest, "--out", str(tmp_path / "o" / "x.zip"),
                   "--redact-paths", "fail"])  # missing --redact -> user error
    assert rc != 0


def test_redact_paths_invalid_rejected(env, tmp_path):
    with pytest.raises(pkg.PackageError):
        pkg.build(env.dest, out=str(tmp_path / "o" / "x.zip"), redact=True, redact_paths="nope")


def test_unknown_run_rejected(env, tmp_path):
    with pytest.raises(pkg.PackageError):
        pkg.build(env.dest, out=str(tmp_path / "o" / "x.zip"), run="9999-99-99_nope")
