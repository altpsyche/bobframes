"""`bobframes package` -- the shareable bundle + standalone summary (c16s, ADR-40/41).

The inline bundle's HTML is a byte-identical copy of the render output, so we reuse the existing render
golden (`golden/`) rather than storing a duplicate `golden_package/inline` tree (which would force a
permanent double-refresh). Parquet is checked by the writer-independent digest, not stored. The stored
`shared/` golden + `make_package_golden.py` arrive at c16t, where the shared bundle genuinely diverges.

Gate (matching QUALITY_GATES §21.1s, c16s slice): non-mutation, determinism, round-trip (extract ==
gated tree, fixed entry timestamps), the inline/light trees vs the render golden, the standalone summary
is self-contained, README + naming, and `package` argparse rejects `--format`.
"""
from __future__ import annotations

import hashlib
import os
from types import SimpleNamespace

import pytest

from . import _render_util as u
from .. import package as pkg
from ..reports import discovery as disc


def _only_dir(extract_root: str) -> str:
    """The single top-level `<project>-<rundate>/` folder a bundle extracts to."""
    entries = os.listdir(extract_root)
    assert len(entries) == 1, f"expected one top folder, got {entries}"
    return entries[0]


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
    # Inline (full) bundle with the DEFAULT name + location (parent of <root> == base).
    inline_zip, inline_summary = pkg.build(dest)
    # Light bundle to its own out dir (the default name would collide with the inline zip).
    light_zip, _ = pkg.build(dest, out=str(base / "lite" / "x.zip"), summary_file=False, light=True)
    return SimpleNamespace(
        dest=dest,
        inline_zip=inline_zip, inline_summary=inline_summary,
        inline_tree=u.extract_zip(inline_zip, str(base / "inline_x")),
        light_tree=u.extract_zip(light_zip, str(base / "light_x")),
    )


# --- inline (full) bundle == render golden -------------------------------------------------------

def test_inline_html_matches_render_golden(env):
    root = os.path.join(env.inline_tree, _only_dir(env.inline_tree))
    for rel in u.rendered_html_files(u.GOLDEN_DIR):
        g = u.normalize(open(os.path.join(u.GOLDEN_DIR, rel), encoding="utf-8").read())
        a = u.normalize(open(os.path.join(root, rel), encoding="utf-8").read())
        assert a == g, f"bundled HTML diverged from render golden: {rel}"


def test_inline_pagedata_matches_render_golden(env):
    root = os.path.join(env.inline_tree, _only_dir(env.inline_tree))
    for rel in u.rendered_page_data_files(u.GOLDEN_DIR):
        g = open(os.path.join(u.GOLDEN_DIR, rel), encoding="utf-8").read()
        a = open(os.path.join(root, rel), encoding="utf-8").read()
        assert a == g, f"bundled _pagedata diverged from render golden: {rel}"


def test_inline_file_set(env):
    root = os.path.join(env.inline_tree, _only_dir(env.inline_tree))
    got = set(u.tree_files(root))
    assert pkg.README_NAME in got
    assert set(u.rendered_html_files(u.GOLDEN_DIR)) <= got
    assert set(u.rendered_page_data_files(u.GOLDEN_DIR)) <= got
    assert set(u.rendered_parquet_files(env.dest)) <= got
    # raw capture inputs + working dirs are not viewable output -> never bundled.
    assert not any(r.endswith(".rdc") or "/_cache/" in r or r.startswith("_cache/") for r in got)


def test_inline_parquet_digests_match_source(env):
    """Parquet is copied raw -> the bundle's digest equals the source's (no corruption, no rewrite)."""
    root = os.path.join(env.inline_tree, _only_dir(env.inline_tree))
    for rel in u.rendered_parquet_files(env.dest):
        a = u.parquet_digest(os.path.join(root, rel))
        g = u.parquet_digest(os.path.join(env.dest, rel))
        assert a == g, f"bundled parquet diverged from source: {rel}"


# --- light bundle --------------------------------------------------------------------------------

def test_light_tree(env):
    root = os.path.join(env.light_tree, _only_dir(env.light_tree))
    got = set(u.tree_files(root))
    assert "index.html" in got and pkg.README_NAME in got
    assert all(not r.startswith("_data/") for r in got), "light must not carry _data"
    assert all("/_pagedata/" not in r and not r.startswith("_pagedata/") for r in got), \
        "light must not carry _pagedata"
    assert all("/drill/" not in r for r in got), "light must not carry drill pages"
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
    pkg.build(dest, out=str(tmp_path / "out" / "b.zip"))
    assert _source_digest(dest) == before


def test_package_is_deterministic(env, tmp_path):
    z1, _ = pkg.build(env.dest, out=str(tmp_path / "a" / "x.zip"), summary_file=False)
    z2, _ = pkg.build(env.dest, out=str(tmp_path / "b" / "x.zip"), summary_file=False)
    t1, t2 = u.extract_zip(z1, str(tmp_path / "ax")), u.extract_zip(z2, str(tmp_path / "bx"))
    f1, f2 = u.tree_files(t1), u.tree_files(t2)
    assert f1 == f2
    for rel in f1:
        assert open(os.path.join(t1, rel), "rb").read() == open(os.path.join(t2, rel), "rb").read(), rel


def test_zip_entries_are_reproducible(env):
    import zipfile
    with zipfile.ZipFile(env.inline_zip) as zf:
        infos = zf.infolist()
    assert infos
    for zi in infos:
        assert zi.date_time == (1980, 1, 1, 0, 0, 0), zi.filename
        assert zi.compress_type == zipfile.ZIP_DEFLATED, zi.filename


# --- friendly artifacts ---------------------------------------------------------------------------

def test_standalone_summary_self_contained(env):
    p = env.inline_summary
    assert os.path.isfile(p)
    project = os.path.basename(os.path.normpath(env.dest))
    assert os.path.basename(p) == f"{project}-{_target(env.dest).date}-summary.html"
    html = open(p, encoding="utf-8").read()
    assert "_assets/" not in html, "standalone summary must not link shared assets"
    assert "fetch(" not in html and 'type="module"' not in html, "must be JS-self-contained / file://-safe"
    # it is exactly the rendered one-pager (already inline via head_assets(INLINE), c16q).
    with open(p, "rb") as a, open(os.path.join(env.dest, "_reports", "summary.html"), "rb") as b:
        assert a.read() == b.read()


def test_readme_present_and_ascii(env):
    root = os.path.join(env.inline_tree, _only_dir(env.inline_tree))
    data = open(os.path.join(root, pkg.README_NAME), "rb").read()
    data.decode("ascii")  # raises on any non-ASCII byte
    assert data == pkg.README_TEXT.encode("ascii")


def test_default_zip_name(env):
    project = os.path.basename(os.path.normpath(env.dest))
    assert os.path.basename(env.inline_zip) == f"{project}-{_target(env.dest).date}-report.zip"


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
