"""c16v (G-29): instancing repeat-count + shader cost/uses are normalized PER FRAME. Constructed
multi-capture trees (no golden dependency) prove a mesh drawn once/frame reads repeat==1 (not 3), a
shader used once/frame has cost normalized, the 1-capture path is a no-op, and the divisor is the
DATA-derived frame count (distinct captures present), NOT the manifest `ok_captures`.
"""
from __future__ import annotations

import os

from bobframes import catalog, paths
from bobframes.reports import cache, dashboard, instancing_opportunities, shader_hotlist
from bobframes.reports.discovery import discover_drops

from .test_aggregates import _draws, _shaders, _write_tree


def _build(tmp_root: str, *, captures: list, mesh_caps: list, shader_rows: list):
    """Write one AreaA drop, build catalog + cache, return (root, drops, cur)."""
    os.makedirs(tmp_root, exist_ok=True)
    date, label, area = '2026-05-30', 'r1', 'AreaA'
    _write_tree(tmp_root, area=area, date=date, label=label, captures=captures,
                draws=_draws(area, date, label, mesh_caps),
                shaders=_shaders(area, date, label, shader_rows))
    catalog.build_catalog(tmp_root)
    cache.build_per_drop_cache(tmp_root)
    drops = discover_drops(tmp_root)
    return tmp_root, drops, drops[-1]


def _mesh_repeat(root, cur, mesh_tag: str) -> float:
    """Max per-frame repeat across the helper rows whose label carries mesh_tag's hash suffix."""
    rows = dashboard._top_meshes_by_area(root, cur, 999)
    return max((rep for (_a, lbl, rep, _med) in rows if mesh_tag[-4:] in lbl), default=0)


def test_repeat_per_frame_three_captures(tmp_path):
    """Mesh drawn once per frame across 3 captures -> repeat-per-frame == 1 (not 3)."""
    root, _drops, cur = _build(
        str(tmp_path / 'a'), captures=['1', '2', '3'],
        mesh_caps=[('mAAAA', '1'), ('mAAAA', '2'), ('mAAAA', '3')],
        shader_rows=[('sk1', 'fragment', '1', 30.0, 2), ('sk1', 'fragment', '2', 30.0, 2),
                     ('sk1', 'fragment', '3', 30.0, 2)])
    assert _mesh_repeat(root, cur, 'mAAAA') == 1.0                       # 3 draws / 3 frames
    # collapsed dashboard card agrees
    top = dashboard._top_meshes(root, cur, 999)
    assert max(rep for (_lbl, rep, _med) in top) == 1.0


def test_shader_cost_normalized_complexity_unchanged(tmp_path):
    """Shader used twice/frame across 3 frames -> uses 6 -> per-frame 2 -> cost 60 (not 180);
    complexity (per-shader max) UNCHANGED."""
    root, _drops, cur = _build(
        str(tmp_path / 'b'), captures=['1', '2', '3'],
        mesh_caps=[('mAAAA', '1'), ('mAAAA', '2'), ('mAAAA', '3')],
        shader_rows=[('sk1', 'fragment', '1', 30.0, 2), ('sk1', 'fragment', '2', 30.0, 2),
                     ('sk1', 'fragment', '3', 30.0, 2)])
    top_s = dashboard._top_shaders(root, cur, 999)
    s1 = [r for r in top_s if r[0].startswith('frag')][0]
    assert s1[1] == 30.0          # complexity (max) unchanged
    assert s1[2] == 60.0          # cost = 30 * (6 uses / 3 frames) = 60, not 30*6=180


def test_one_capture_is_a_noop(tmp_path):
    """1 capture, a mesh drawn 3x in that capture -> repeat == 3 (divisor is the FRAME count = 1, not
    the draw count). Pins golden-neutrality on 1-capture data."""
    root, _drops, cur = _build(
        str(tmp_path / 'c'), captures=['1'],
        mesh_caps=[('mAAAA', '1'), ('mAAAA', '1'), ('mAAAA', '1')],
        shader_rows=[('sk1', 'fragment', '1', 30.0, 2)])
    assert _mesh_repeat(root, cur, 'mAAAA') == 3


def test_divisor_is_data_frames_not_ok_captures(tmp_path):
    """Manifest declares 5 ok captures but draws/shaders only populate capture '1' (the exact synthetic
    fixture skew). The per-frame divisor must be the DATA-derived frame count (1), NOT ok_captures (5):
    a mesh drawn 3x in capture 1 reads repeat == 3 (not 3/5)."""
    root, drops, cur = _build(
        str(tmp_path / 'd'), captures=['1', '2', '3', '4', '5'],
        mesh_caps=[('mAAAA', '1'), ('mAAAA', '1'), ('mAAAA', '1')],
        shader_rows=[('sk1', 'fragment', '1', 30.0, 2)])
    assert drops[0].n_captures == 5                 # manifest/catalog says 5 ok
    assert _mesh_repeat(root, cur, 'mAAAA') == 3    # but divided by the 1 frame that has data


def test_instancing_and_shader_reports_render_per_frame(tmp_path):
    """The detailed reports (not just the dashboard helpers) emit per-frame numbers."""
    root, drops, _cur = _build(
        str(tmp_path / 'e'), captures=['1', '2', '3'],
        mesh_caps=[('mAAAA', '1'), ('mAAAA', '2'), ('mAAAA', '3')],
        shader_rows=[('sk1', 'fragment', '1', 30.0, 2), ('sk1', 'fragment', '2', 30.0, 2),
                     ('sk1', 'fragment', '3', 30.0, 2)])
    inst_html = open(instancing_opportunities.build(root, drops=drops), encoding='utf-8').read()
    assert '(repeat 1)' in inst_html and '(repeat 3)' not in inst_html   # top mesh per frame
    sh_html = open(shader_hotlist.build(root, drops=drops), encoding='utf-8').read()
    assert '2 uses in the current run' in sh_html and '6 uses' not in sh_html  # uses per frame
