"""End-to-end smoke test (c15 rewrite — G-12).

Two modes, no hardcoded area/label/date (the old `Chor bazar` / `r110565` / `2026-05-27`
constants + the `__file__`-walked project root are gone):

  bobframes smoke                 render-only against the bundled synthetic `_data/` fixture
                                  (no `.rdc`, no qrenderdoc/GPU). Runs everywhere, incl. CI.
  bobframes smoke --data <DIR>    full ingest + render against a real capture root; auto-selects
                                  area + latest drop via discovery.find_drops. Needs Windows +
                                  RenderDoc; self-hosted / nightly only.

Both modes assert: outputs exist, every Parquet matches schemas.expected_columns, entity tables
carry a populated stable_key, catalog is rebuilt, and every emitted HTML is lint-clean.

Run standalone:  python -m bobframes.tests.smoke [--data DIR]
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile

import pyarrow.parquet as papq

from .. import discovery, lint, paths, schemas


def _fail(msg: str) -> int:
    print(f'FAIL: {msg}')
    return 1


def _lint_html(root: str) -> int:
    """Lint every emitted HTML under `root` (skipping the parquet cache). Returns hit count."""
    from . import _render_util as u
    hits = 0
    for rel in u.rendered_html_files(root):
        for lineno, label, snip in lint.lint_file(os.path.join(root, rel)):
            print(f'  LINT {rel}:{lineno}: [{label}] {snip}')
            hits += 1
    return hits


def _assert_drop_parquet(out_dir: str, check_csv: bool) -> int:
    """Schema match + stable_key population for one drop's `_data` dir. Returns error count.

    `check_csv` asserts each Parquet has its `.csv` sidecar — true only for the full-ingest path;
    the committed synthetic fixture is Parquet-only (ADR-8), so render-only skips it.
    """
    errors = 0
    for stem in schemas.TABLES:
        pq = os.path.join(out_dir, f'{stem}.parquet')
        if not os.path.exists(pq):
            continue
        if check_csv and not os.path.exists(os.path.join(out_dir, f'{stem}.csv')):
            print(f'  {stem}: .csv missing alongside .parquet')
            errors += 1
        cols = list(papq.read_schema(pq).names)
        expected = list(schemas.expected_columns(stem))
        if cols != expected:
            print(f'  {stem}: cols={cols} != expected={expected}')
            errors += 1
        if schemas.is_entity_table(stem):
            t = papq.read_table(pq, columns=['stable_key'])
            if t.num_rows and not any(t.column('stable_key').to_pylist()):
                print(f'  {stem}: stable_key all empty across {t.num_rows} rows')
                errors += 1
    return errors


# --- render-only (default) ---------------------------------------------------

def _render_only_smoke() -> int:
    from . import _render_util as u

    with tempfile.TemporaryDirectory(prefix='bobframes-smoke-') as td:
        dest = os.path.join(td, 'root')
        print(f'1. render-only against bundled synthetic -> {dest}')
        try:
            u.render_fresh(dest)
        except RuntimeError as e:
            return _fail(str(e))

        print('2. html emitted')
        html = u.rendered_html_files(dest)
        if not os.path.exists(paths.root_index_html(dest)):
            return _fail('root index.html missing')
        drills = [r for r in html if r.endswith('/' + paths.INDEX_HTML) and paths.DRILL_DIR in r]
        reports = [r for r in html if r.startswith(paths.REPORTS_DIR + '/') and paths.DRILL_DIR not in r]
        if not drills:
            return _fail('no per-drop drill index.html emitted')
        if not reports:
            return _fail('no _reports/*.html emitted')

        print('3. schema + stable_key (synthetic _data)')
        errors = 0
        for drop in discovery.find_drops(dest):
            out_dir = paths.drop_data_dir(dest, drop.area, os.path.basename(drop.drop_dir))
            errors += _assert_drop_parquet(out_dir, check_csv=False)
        if errors:
            return _fail(f'{errors} parquet schema/stable_key error(s)')

        print('4. catalog')
        if not os.path.exists(paths.catalog_parquet(dest)):
            return _fail('catalog parquet missing')

        print('5. lint')
        if _lint_html(dest):
            return _fail('lint hits in rendered HTML')

        print(f'OK: render-only smoke - {len(drills)} drop(s), {len(html)} HTML pages, lint clean')
        return 0


# --- full ingest (--data) ----------------------------------------------------

def _full_smoke(data_dir: str, pixel_grid: int) -> int:
    data_dir = os.path.abspath(data_dir)
    drops = discovery.find_drops(data_dir)
    if not drops:
        return _fail(f'no drops with .rdc found under {data_dir}')
    print(f'1. discovered {len(drops)} drop(s): ' +
          ', '.join(f'{d.area}/{os.path.basename(d.drop_dir)}' for d in drops))

    print('2. ingest (full pipeline, --force)')
    rc = subprocess.run(
        [sys.executable, '-m', 'bobframes.run', '--root', data_dir, '--force',
         '--pixel-grid', str(pixel_grid)],
    ).returncode
    if rc != 0:
        return _fail(f'pipeline exited rc={rc}')

    print('3. per-drop outputs')
    errors = 0
    for drop in drops:
        dated = os.path.basename(drop.drop_dir)
        out_dir = paths.drop_data_dir(data_dir, drop.area, dated)
        tmp_dir = paths.drop_data_dir_tmp(data_dir, drop.area, dated)
        if not os.path.isdir(out_dir):
            errors += 1
            print(f'  {out_dir} missing')
            continue
        if os.path.isdir(tmp_dir):
            errors += 1
            print(f'  {tmp_dir} should be gone after atomic commit')
        errors += _assert_drop_parquet(out_dir, check_csv=True)

        mf = os.path.join(out_dir, paths.MANIFEST_NAME)
        with open(mf, encoding='utf-8') as f:
            m = json.load(f)
        if m.get('schema_version') != schemas.SCHEMA_VERSION:
            errors += 1
            print(f'  manifest schema_version={m.get("schema_version")} != {schemas.SCHEMA_VERSION}')
        if not all(s == 'ok' for s in m.get('capture_status', {}).values()):
            errors += 1
            print(f'  capture_status not all ok: {m.get("capture_status")}')

        drill = paths.drop_drill_dir(data_dir, drop.area, dated)
        if not os.path.exists(os.path.join(drill, paths.INDEX_HTML)):
            errors += 1
            print(f'  drill index.html missing at {drill}')
    if errors:
        return _fail(f'{errors} ingest output error(s)')

    print('4. catalog + root index')
    if not os.path.exists(paths.catalog_parquet(data_dir)):
        return _fail('catalog parquet missing')
    if not os.path.exists(paths.root_index_html(data_dir)):
        return _fail('root index.html missing')

    print('5. lint')
    if _lint_html(data_dir):
        return _fail('lint hits in rendered HTML')

    print(f'OK: full smoke - {len(drops)} drop(s) ingested + rendered, lint clean')
    return 0


def main(data: str | None = None, pixel_grid: int = 4) -> int:
    if data:
        return _full_smoke(data, pixel_grid)
    return _render_only_smoke()


def _parse(argv: list[str]) -> argparse.Namespace:
    ap = argparse.ArgumentParser(prog='bobframes.tests.smoke',
                                 description='render-only (default) or full ingest (--data) smoke')
    ap.add_argument('--data', help='capture root for full ingest (default: bundled synthetic)')
    ap.add_argument('--pixel-grid', type=int, default=4)
    return ap.parse_args(argv)


if __name__ == '__main__':
    a = _parse(sys.argv[1:])
    sys.exit(main(data=a.data, pixel_grid=a.pixel_grid))
