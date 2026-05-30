"""Build _resource_labels.json sidecar from per-capture stage labels + Parquet.

The HTML browser reads this file and enriches ID columns at render time so
e.g. `tex_id=2184` shows as `2184 SceneDepthZ`.

Structure on disk:
{
  "by_capture": {
    "1": {
      "texture":   {"2184": "SceneDepthZ", ...},
      "shader":    {"2192": "compute 224B hash:39013910"},
      "program":   {"2193": "vs:2192 fs:0"},
      "sampler":   {"116": "..."},
      "fbo":       {"...": "..."},
      "buffer":    {"...": "..."}
    }
  }
}

`build_from_stage` runs at merge time when _stage/<cap>/labels.json + the
already-merged Parquet files are both present.

`build_from_outdir` rebuilds from an existing _analysis_out/ (when no
stage is available, e.g. --render-only mode).
"""

from __future__ import annotations

import json
import os
from typing import Iterable

import pyarrow.parquet as papq


def _short_name_for_shader(shader_row: dict) -> str:
    stype = shader_row.get('shader_type', '') or ''
    src_len = int(shader_row.get('src_len', 0) or 0)
    h = shader_row.get('src_hash', '') or ''
    samples = int(shader_row.get('total_texture_samples', 0) or 0)
    branches = int(shader_row.get('total_branches', 0) or 0)
    loops = int(shader_row.get('total_loops', 0) or 0)
    bits = []
    if stype: bits.append(stype)
    if src_len: bits.append(f'{src_len}B')
    if h: bits.append(f'h:{h[:8]}')
    if samples: bits.append(f'tex={samples}')
    if branches: bits.append(f'br={branches}')
    if loops: bits.append(f'lo={loops}')
    return ' '.join(bits)


def _short_name_for_program(prog_row: dict, shader_names: dict[int, str]) -> str:
    vs = int(prog_row.get('vs_shader_id', 0) or 0)
    fs = int(prog_row.get('fs_shader_id', 0) or 0)
    cs = int(prog_row.get('cs_shader_id', 0) or 0)
    bits = []
    if vs: bits.append(f'vs:{vs}')
    if fs: bits.append(f'fs:{fs}')
    if cs: bits.append(f'cs:{cs}')
    n_uniforms = int(prog_row.get('num_active_uniforms', 0) or 0)
    if n_uniforms: bits.append(f'u={n_uniforms}')
    return ' '.join(bits)


def _per_capture_from_parquet(out_dir: str) -> dict[str, dict[str, dict[str, str]]]:
    """Read the drop's Parquet files and build per-capture label maps.

    Pulls glObjectLabel-supplied names from textures/programs/samplers/fbos
    columns, and synthesizes names for shaders + programs without labels.
    """
    by_cap: dict[str, dict[str, dict[str, str]]] = {}

    def _bag(cap: str) -> dict[str, dict[str, str]]:
        return by_cap.setdefault(cap, {
            'texture': {}, 'shader': {}, 'program': {},
            'sampler': {}, 'fbo': {}, 'buffer': {},
        })

    def _read(table: str, id_col: str, label_col: str, kind: str) -> None:
        p = os.path.join(out_dir, f'{table}.parquet')
        if not os.path.exists(p):
            return
        cols = list(papq.read_schema(p).names)
        want = ['capture', id_col]
        if label_col in cols:
            want.append(label_col)
        try:
            t = papq.read_table(p, columns=want)
        except Exception:
            return
        cap_arr = t.column('capture').to_pylist()
        id_arr = t.column(id_col).to_pylist()
        lab_arr = t.column(label_col).to_pylist() if label_col in cols else [''] * t.num_rows
        for c, i, l in zip(cap_arr, id_arr, lab_arr):
            if not i:
                continue
            sid = str(i)
            if l:
                _bag(c)[kind][sid] = l

    _read('textures', 'tex_id', 'label', 'texture')
    _read('render_targets', 'rt_id', 'label', 'texture')  # RTs go into texture bucket
    _read('programs', 'program_id', 'label', 'program')
    _read('samplers', 'sampler_id', 'label', 'sampler')
    _read('fbos', 'fbo_id', 'label', 'fbo')

    # Synthesize shader names from shaders.parquet
    sh_path = os.path.join(out_dir, 'shaders.parquet')
    if os.path.exists(sh_path):
        t = papq.read_table(sh_path)
        cols = t.column_names
        idx = {c: t.column(c).to_pylist() for c in cols}
        n = t.num_rows
        for i in range(n):
            cap = idx['capture'][i]
            sid = idx['shader_id'][i]
            if not sid:
                continue
            row = {c: idx[c][i] for c in cols}
            name = _short_name_for_shader(row)
            if name:
                _bag(cap)['shader'][str(sid)] = name

    # Synthesize program "name" (vs:N fs:M) if no glObjectLabel name set
    pr_path = os.path.join(out_dir, 'programs.parquet')
    if os.path.exists(pr_path):
        t = papq.read_table(pr_path)
        cols = t.column_names
        idx = {c: t.column(c).to_pylist() for c in cols}
        n = t.num_rows
        for i in range(n):
            cap = idx['capture'][i]
            pid = idx['program_id'][i]
            if not pid:
                continue
            existing = _bag(cap)['program'].get(str(pid), '')
            if existing:
                continue
            row = {c: idx[c][i] for c in cols}
            sname = _short_name_for_program(row, {})
            if sname:
                _bag(cap)['program'][str(pid)] = sname

    return by_cap


def write_resource_labels(out_dir: str) -> str:
    """Read _analysis_out/*.parquet, produce _resource_labels.json sidecar."""
    by_cap = _per_capture_from_parquet(out_dir)
    path = os.path.join(out_dir, '_resource_labels.json')
    with open(path, 'w', encoding='utf-8') as f:
        json.dump({'by_capture': by_cap}, f, separators=(',', ':'))
    return path


if __name__ == '__main__':
    import sys
    p = sys.argv[1] if len(sys.argv) > 1 else '.'
    out = write_resource_labels(p)
    sz = os.path.getsize(out)
    print(f'wrote {out} ({sz} bytes)')
