"""Pipeline orchestrator. Host Python 3.14.

Per-drop stages:
  1. Pre-flight  — skip-marker / --force rotate / clean stale tmp
  2. Export      — renderdoccmd convert to .xml + .zip.xml (parallel)
  3. Static parse — parse_init_state.py per capture (parallel)
  4. Replay main  — qrenderdoc + replay_main.py per capture (SEQUENTIAL)
  5. Merge + parquetize — concat CSV fragments, compute stable_keys, write Parquet
  6. Render HTML  (placeholder; full template wired later)
  7. Lint
  8. Manifest
  9. Atomic commit (rename tmp -> _analysis_out)
 10. Marker
Run-level (after all drops):
 11. Catalog rebuild
 12. Root index render
 13. Root lint
"""

from __future__ import annotations

import argparse
import concurrent.futures as cf
import datetime as _dt
import os
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass

from . import (
    catalog, derive_post_merge, discovery, global_entities, lint, manifest,
    parquetize, paths, qrd_harness, query_examples, rdcmd, resource_labels, schemas,
)
from .derives import pass_class_breakdown, texture_usage
from .html import template
from .parsers import derive_program_transitions
from .reports import orchestrator as reports_orchestrator


def _ts() -> str:
    return _dt.datetime.now().strftime('%Y%m%dT%H%M%S')


def _log(msg: str) -> None:
    print(f'[{_dt.datetime.now().strftime("%H:%M:%S")}] {msg}', flush=True)


# --- Stage 1: pre-flight -----------------------------------------------------

def _drop_inputs_max_mtime(drop_dir: str, captures: tuple[str, ...]) -> float:
    mt = 0.0
    for capture in captures:
        for ext in ('rdc', 'xml', 'zip.xml'):
            p = os.path.join(drop_dir, f'{capture}.{ext}')
            if os.path.exists(p):
                mt = max(mt, os.path.getmtime(p))
    return mt


def _preflight(drop: discovery.Drop, force: bool, project_root: str) -> tuple[bool, str | None]:
    """Returns (should_skip, rotated_from). Cleans up stale tmp."""
    drop_label_dated = os.path.basename(drop.drop_dir)
    out = paths.drop_data_dir(project_root, drop.area, drop_label_dated)
    tmp = paths.drop_data_dir_tmp(project_root, drop.area, drop_label_dated)

    if os.path.isdir(tmp):
        rot = f'{tmp}.{_ts()}'
        try:
            os.replace(tmp, rot)
            _log(f'  cleaned stale tmp -> {os.path.basename(rot)}')
        except OSError as e:
            _log(f'  failed to rotate stale tmp: {e}')
            shutil.rmtree(tmp, ignore_errors=True)

    if os.path.isdir(out):
        marker = os.path.join(out, 'done.marker')
        if not force and os.path.exists(marker):
            marker_mt = os.path.getmtime(marker)
            input_mt = _drop_inputs_max_mtime(drop.drop_dir, drop.captures)
            if marker_mt >= input_mt:
                return True, None

        if force:
            rot = f'{out}.{_ts()}'
            try:
                os.replace(out, rot)
                _log(f'  rotated existing _data dir -> {os.path.basename(rot)}')
                return False, os.path.basename(rot)
            except OSError as e:
                _log(f'  rotate failed ({e}); falling back to delete')
                shutil.rmtree(out, ignore_errors=True)
                if os.path.isdir(out):
                    raise RuntimeError(f'cannot remove existing {out}; close any program holding it')
        else:
            shutil.rmtree(out, ignore_errors=True)

    return False, None


# --- Stage 2: export ---------------------------------------------------------

def _export_one(rdc_path: str) -> tuple[str, dict[str, float]]:
    """Returns (capture, {fmt: elapsed_s})."""
    drop_dir = os.path.dirname(rdc_path)
    capture = os.path.basename(rdc_path)[:-4]
    timings: dict[str, float] = {}
    for fmt in ('xml', 'zip.xml'):
        out = os.path.join(drop_dir, f'{capture}.{fmt}')
        if not rdcmd.needs_export(rdc_path, out):
            timings[fmt] = 0.0
            continue
        timings[fmt] = rdcmd.convert(rdc_path, out, fmt=fmt)
    return capture, timings


def _do_export(drop: discovery.Drop, workers: int) -> None:
    todo: list[str] = []
    for capture in drop.captures:
        rdc = os.path.join(drop.drop_dir, f'{capture}.rdc')
        x = os.path.join(drop.drop_dir, f'{capture}.xml')
        z = os.path.join(drop.drop_dir, f'{capture}.zip.xml')
        if rdcmd.needs_export(rdc, x) or rdcmd.needs_export(rdc, z):
            todo.append(rdc)

    if not todo:
        _log(f'  export: nothing to do ({len(drop.captures)} captures already exported)')
        return

    _log(f'  export: {len(todo)}/{len(drop.captures)} captures need export (workers={workers})')
    t0 = time.monotonic()
    with cf.ProcessPoolExecutor(max_workers=workers) as ex:
        results = list(ex.map(_export_one, todo))
    _log(f'  export done in {time.monotonic()-t0:.1f}s')


# --- Stage 3: static parse ---------------------------------------------------

def _parse_one(args: tuple[str, str, str, str, str, str]) -> tuple[str, float, str]:
    xml_path, capture_stage, area, drop_date, drop_label, capture = args
    cmd = [
        sys.executable, '-m', 'bobframes.parsers.parse_init_state',
        xml_path, capture_stage, area, drop_date, drop_label, capture,
    ]
    cwd = os.path.dirname(os.path.dirname(os.path.dirname(capture_stage)))
    if not cwd:
        cwd = os.getcwd()
    cwd = os.environ.get('RDC_ROOT', cwd) or cwd
    t0 = time.monotonic()
    p = subprocess.run(cmd, capture_output=True, text=True, cwd=cwd)
    elapsed = time.monotonic() - t0
    if p.returncode != 0:
        return capture, elapsed, f'FAIL: {p.stderr.strip() or p.stdout.strip()}'
    return capture, elapsed, p.stdout.strip()


def _do_parse(drop: discovery.Drop, stage_root: str, workers: int, project_root: str) -> dict[str, str]:
    _log(f'  parse: {len(drop.captures)} captures (workers={workers})')
    args = []
    for capture in drop.captures:
        xml = os.path.join(drop.drop_dir, f'{capture}.zip.xml')
        capture_stage = os.path.join(stage_root, capture)
        os.makedirs(capture_stage, exist_ok=True)
        args.append((xml, capture_stage, drop.area, drop.drop_date, drop.drop_label, capture))
    os.environ['RDC_ROOT'] = project_root
    t0 = time.monotonic()
    statuses: dict[str, str] = {}
    with cf.ProcessPoolExecutor(max_workers=workers) as ex:
        for capture, elapsed, status in ex.map(_parse_one, args):
            statuses[capture] = 'ok' if not status.startswith('FAIL') else 'fail'
            _log(f'    {capture}: {status} ({elapsed:.1f}s)')
    _log(f'  parse done in {time.monotonic()-t0:.1f}s')
    return statuses


# --- Stage 4: replay ---------------------------------------------------------

def _do_replay(drop: discovery.Drop, stage_root: str, project_root: str,
               pixel_grid: int = 4) -> dict[str, str]:
    os.environ['RDC_PIXEL_GRID'] = str(pixel_grid)
    _log(f'  replay: {len(drop.captures)} captures (sequential)')
    script = os.path.join(project_root, 'bobframes', 'replay', 'replay_main.py')
    statuses: dict[str, str] = {}
    for capture in drop.captures:
        capture_stage = os.path.join(stage_root, capture)
        os.makedirs(capture_stage, exist_ok=True)
        log_path = os.path.join(capture_stage, '_harness.log')
        t0 = time.monotonic()
        rc, elapsed = qrd_harness.run(
            script,
            payload_args=[drop.drop_dir, capture, drop.area, drop.drop_date, drop.drop_label, stage_root],
            log_path=log_path,
            timeout_s=600,
        )
        statuses[capture] = 'ok' if rc == 0 else f'fail(rc={rc})'
        _log(f'    {capture}: rc={rc} {elapsed:.1f}s')
        if rc != 0:
            raise RuntimeError(f'replay failed for capture {capture!r}; see {log_path}')
    return statuses


# --- Drop driver -------------------------------------------------------------

@dataclass
class DropResult:
    drop: discovery.Drop
    row_counts: dict[str, int]
    capture_status: dict[str, str]
    rotated_from: str | None
    skipped: bool


def process_drop(drop: discovery.Drop, *, force: bool, workers: int,
                 project_root: str) -> DropResult:
    _log(f'== drop: {drop.area} / {drop.drop_date}_{drop.drop_label} ({len(drop.captures)} captures) ==')
    skip, rotated_from = _preflight(drop, force, project_root)
    if skip:
        _log('  skip (done.marker fresh)')
        return DropResult(drop=drop, row_counts={}, capture_status={}, rotated_from=None, skipped=True)

    drop_label_dated = os.path.basename(drop.drop_dir)
    tmp = paths.drop_data_dir_tmp(project_root, drop.area, drop_label_dated)
    stage_root = os.path.join(tmp, '_stage')
    os.makedirs(stage_root, exist_ok=True)

    _do_export(drop, workers=workers)

    parse_status = _do_parse(drop, stage_root, workers=workers, project_root=project_root)

    replay_status = _do_replay(drop, stage_root, project_root=project_root,
                               pixel_grid=int(os.environ.get('RDC_PIXEL_GRID', '4')))

    capture_status: dict[str, str] = {}
    for s in drop.captures:
        p_ok = parse_status.get(s, 'ok') == 'ok'
        r_ok = replay_status.get(s, 'ok') == 'ok'
        capture_status[s] = 'ok' if (p_ok and r_ok) else 'fail'

    _log('  merge + parquetize')
    t0 = time.monotonic()
    row_counts = parquetize.merge_drop(stage_root, tmp)
    _log(f'  parquetize done in {time.monotonic()-t0:.1f}s ({sum(row_counts.values())} rows)')

    t0 = time.monotonic()
    n_pt = derive_program_transitions.derive(tmp)
    if n_pt:
        row_counts['program_transitions'] = n_pt
    _log(f'  derive program_transitions: {n_pt} rows ({time.monotonic()-t0:.1f}s)')

    t0 = time.monotonic()
    derive_post_merge.derive(tmp)
    _log(f'  post-merge derives applied ({time.monotonic()-t0:.1f}s)')

    t0 = time.monotonic()
    n_pcb = pass_class_breakdown.build(tmp)
    n_tu = texture_usage.build(tmp)
    if n_pcb:
        row_counts['pass_class_breakdown'] = n_pcb
    if n_tu:
        row_counts['texture_usage'] = n_tu
    _log(f'  derived tables: pass_class_breakdown={n_pcb}, texture_usage={n_tu} ({time.monotonic()-t0:.1f}s)')

    t0 = time.monotonic()
    resource_labels.write_resource_labels(tmp)
    _log(f'  resource labels written ({time.monotonic()-t0:.1f}s)')

    m = manifest.build_manifest(
        area=drop.area, drop_date=drop.drop_date, drop_label=drop.drop_label,
        captures=list(drop.captures), capture_status=capture_status,
        row_counts=row_counts, rotated_from=rotated_from,
    )
    manifest.write_manifest(tmp, m)

    # Drop _stage/ before commit so it doesn't pollute the committed output.
    if not os.environ.get('RDC_KEEP_STAGE'):
        shutil.rmtree(stage_root, ignore_errors=True)

    out = paths.drop_data_dir(project_root, drop.area, drop_label_dated)
    if os.path.isdir(out):
        raise RuntimeError(f'unexpected: {out} exists at commit time')
    os.makedirs(os.path.dirname(out), exist_ok=True)
    os.replace(tmp, out)

    with open(os.path.join(out, 'done.marker'), 'w', encoding='utf-8') as f:
        f.write(str(_drop_inputs_max_mtime(drop.drop_dir, drop.captures)))

    # Render per-drop browser HTML to _reports/drill/<area>/<drop>/index.html.
    # Separate from data commit: HTML is idempotent and can be regenerated.
    drill_dir = paths.drop_drill_dir(project_root, drop.area, drop_label_dated)
    os.makedirs(drill_dir, exist_ok=True)
    template.render_drop(
        drill_dir, data_dir=out,
        area=drop.area, drop_date=drop.drop_date, drop_label=drop.drop_label,
        captures=list(drop.captures), schema_version=schemas.SCHEMA_VERSION,
        build_timestamp=manifest.utc_now_iso(),
        row_counts=row_counts,
    )

    hits = lint.lint_file(os.path.join(drill_dir, 'index.html'))
    if hits:
        for lineno, label, snip in hits:
            _log(f'  LINT FAIL {drill_dir}/index.html:{lineno}: [{label}] {snip}')
        raise RuntimeError('lint blocked the build')

    _log(f'  done -> {os.path.relpath(out)}')
    return DropResult(drop=drop, row_counts=row_counts,
                      capture_status=capture_status, rotated_from=rotated_from, skipped=False)


# --- CLI ---------------------------------------------------------------------

def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(prog='bobframes.run',
        description='RDC capture analysis pipeline')
    ap.add_argument('positional', nargs='?',
        help='optional drop folder (e.g. "Chor bazar/2026-05-27_r110565/")')
    ap.add_argument('--root', default='.', help='project root (containing area subdirs)')
    ap.add_argument('--area', help='restrict to one area name')
    ap.add_argument('--label', help='restrict to drops matching this label')
    ap.add_argument('--capture', help='restrict to a single capture name (e.g. "1")')
    ap.add_argument('--force', action='store_true', help='rotate existing _analysis_out and rebuild')
    ap.add_argument('--render-only', action='store_true',
        help='skip export/parse/replay; rebuild HTML + catalog from existing Parquet')
    ap.add_argument('--workers', type=int, default=min(4, os.cpu_count() or 4))
    ap.add_argument('--pixel-grid', type=int, default=4)
    args = ap.parse_args(argv)

    os.environ['RDC_PIXEL_GRID'] = str(args.pixel_grid)
    root = os.path.abspath(args.root)
    project_root = root  # the run.py is invoked via `python -m bobframes.run` from project root

    if args.positional:
        drops = [discovery.parse_single_drop_arg(args.positional, root)]
        if args.capture:
            drops = [discovery.Drop(area=d.area, drop_date=d.drop_date,
                                    drop_label=d.drop_label, drop_dir=d.drop_dir,
                                    captures=(args.capture,)) for d in drops]
    else:
        drops = discovery.find_drops(
            root=root,
            area_filter=args.area,
            label_filter=args.label,
            capture_filter=args.capture,
        )

    if not drops:
        _log('no drops to process')
        return 0

    _log(f'pipeline: {len(drops)} drop(s); root={root}')

    if args.render_only:
        _log(f'render-only: re-rendering {len(drops)} drop(s) from existing parquet')
        for drop in drops:
            drop_label_dated = os.path.basename(drop.drop_dir)
            data_dir = paths.drop_data_dir(root, drop.area, drop_label_dated)
            if not os.path.isdir(data_dir):
                _log(f'  {drop.area}: no _data dir, skipping')
                continue
            drill_dir = paths.drop_drill_dir(root, drop.area, drop_label_dated)
            try:
                derive_post_merge.derive(data_dir)
                pass_class_breakdown.build(data_dir)
                texture_usage.build(data_dir)
                resource_labels.write_resource_labels(data_dir)
                m = manifest.read_manifest(data_dir)
                os.makedirs(drill_dir, exist_ok=True)
                template.render_drop(
                    drill_dir, data_dir=data_dir,
                    area=drop.area, drop_date=drop.drop_date, drop_label=drop.drop_label,
                    captures=m.get('captures') or m.get('stems') or list(drop.captures),
                    schema_version=m.get('schema_version', schemas.SCHEMA_VERSION),
                    build_timestamp=m.get('build_timestamp', ''),
                    row_counts=m.get('row_counts') or {},
                )
                hits = lint.lint_file(os.path.join(drill_dir, 'index.html'))
                if hits:
                    for lineno, label, snip in hits:
                        _log(f'  LINT FAIL {drill_dir}/index.html:{lineno}: [{label}] {snip}')
                    return 1
                _log(f'  {drop.area}: rendered')
            except Exception as e:
                _log(f'  {drop.area}: render FAILED: {e}')
                return 1
        _log('rebuilding catalog')
        summary = catalog.build_catalog(root)
        _log(f'  catalog: {summary["drop_count"]} drops, {summary["capture_count"]} captures')
        n_ge = global_entities.build_global_entities(root)
        _log(f'  global entities: {n_ge} rows')
        query_examples.write_query_examples(root)
        _log('  wrote _query_examples.md')

        rc = reports_orchestrator.render_all_reports(root, _log)
        if rc != 0:
            return rc
        _log('render-only done')
        return 0

    results: list[DropResult] = []
    for drop in drops:
        try:
            r = process_drop(drop, force=args.force, workers=args.workers,
                             project_root=project_root)
            results.append(r)
        except Exception as e:
            _log(f'  drop FAILED: {e}')
            return 1

    _log('rebuilding catalog')
    summary = catalog.build_catalog(root)
    _log(f'  catalog: {summary["drop_count"]} drops, {summary["capture_count"]} captures, areas={summary["areas"]}')

    t0 = time.monotonic()
    n_ge = global_entities.build_global_entities(root)
    _log(f'  global entities: {n_ge} rows ({time.monotonic()-t0:.1f}s)')

    query_examples.write_query_examples(root)
    _log('  wrote _query_examples.md')

    rc = reports_orchestrator.render_all_reports(root, _log)
    if rc != 0:
        return rc

    _log(f'pipeline done: {len(results)} drops processed')
    for r in results:
        if r.skipped:
            _log(f'  {r.drop.area}: skipped')
        else:
            _log(f'  {r.drop.area}: {sum(r.row_counts.values())} rows')

    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
