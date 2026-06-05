"""Per-(drop, area, entity) aggregation - the single source of the mesh repeat-count and the shader
uses/cost/complexity numbers, plus the per-(drop, area) frame count, that the instancing report, the
shader report, the dashboard cards, and the health verdict all read (G-26).

Pure data layer (no HTML, no human labels): a peer of ``health.py``, BELOW presentation, so the
verdict can never disagree with the reports it mirrors. Reads the per-drop caches
(``reports.cache.load_cached``) with a live per-drop parquet fallback, mirroring the readers it
replaces (``instancing_opportunities._iter_draws`` / ``shader_hotlist._iter_shaders`` /
``dashboard._top_*``) so the aggregated numbers are byte-for-byte what those call sites computed
inline. The three formerly-divergent "count mesh repeats / sum shader cost" implementations now derive
from these atoms.

c16v normalizes these numbers PER FRAME in ONE place: the per-(drop, area) ``frame_count`` (= the
number of distinct ``capture`` values actually present in that drop+area's entity data) is the
denominator; ``base.per_frame(total, frames)`` does the division (a no-op when frames<=1, so 1-capture
data stays byte-identical). Frame count is taken from the DATA (distinct captures present), not the
manifest ``ok_captures`` - the two agree on consistent data, but the data-derived count is the
correct denominator when a capture replayed "ok" yet exported no entity rows (ADR-23 as-built).
"""

from __future__ import annotations

import os
from collections import Counter, defaultdict
from dataclasses import dataclass, field

import pyarrow.parquet as papq

from .reports.cache import _to_dict_of_lists, load_cached

_DRAWS_COLS = [
    'area', 'drop_date', 'drop_label', 'capture',
    'mesh_hash', 'program_id', 'vs_shader_id', 'fs_shader_id',
    'parent_pass_path_norm', 'draw_class', 'num_indices', 'num_instances',
]

_SHADER_COLS = [
    'area', 'drop_date', 'drop_label', 'capture', 'shader_id', 'stable_key',
    'shader_type', 'src_len', 'complexity_score', 'total_branches',
    'total_loops', 'total_discards', 'total_dfdx_dfdy',
    'total_texture_samples', 'used_by_draw_count', 'src_file_path',
    'fb_fetch', 'uses_cubemap',
]


def drop_key(drop_date, drop_label) -> str:
    return f'{drop_date}_{drop_label}'


def _iter_rows(root: str, drops: list, cache: str, cols: list, parquet: str):
    """Yield row dicts from the per-drop cache (sha256-validated; R-13), else a live per-drop scan.

    Identical row stream to the inline readers in instancing/shader_hotlist: cache-first filtered to
    the drops' (date, label); on a cache miss, live-scan each drop's parquet and stamp drop_date /
    drop_label from the DropRow. Order is preserved, so Counter.most_common ties + first-seen
    setdefault resolve exactly as before.
    """
    t = load_cached(root, cache)
    if t is not None:
        c = _to_dict_of_lists(t)
        wanted = {(d.date, d.label) for d in drops}
        for i in range(t.num_rows):
            if (c['drop_date'][i], c['drop_label'][i]) not in wanted:
                continue
            yield {k: c[k][i] for k in c}
        return
    for d in drops:
        for r in d.rows:
            p = os.path.join(r.drop_dir, parquet)
            if not os.path.exists(p):
                continue
            try:
                schema_cols = set(papq.read_schema(p).names)
                want = [x for x in cols if x in schema_cols]
                tt = papq.read_table(p, columns=want)
            except Exception:
                continue
            c = _to_dict_of_lists(tt)
            for i in range(tt.num_rows):
                row = {k: c[k][i] for k in c}
                row['drop_date'] = r.drop_date
                row['drop_label'] = r.drop_label
                yield row


# --- draws / meshes -----------------------------------------------------------------------------

@dataclass
class DrawAgg:
    """Mesh-draw aggregates keyed by ``(drop_key, area, mesh_hash)`` over VALID draw rows
    (mesh_hash truthy, num_indices>0, program_id!=0), plus the per-(drop_key, area) captured-frame
    set over ALL draw rows (a frame exists if it produced any draw)."""

    count: Counter = field(default_factory=Counter)            # draw occurrences (the repeat atom)
    num_indices: dict = field(default_factory=lambda: defaultdict(list))
    draw_class: dict = field(default_factory=dict)             # first-seen
    pass_norm: dict = field(default_factory=dict)              # first-seen
    captures: dict = field(default_factory=lambda: defaultdict(set))  # (drop_key, area) -> {capture}

    def frames(self, dk: str, area: str) -> int:
        """Per-(drop, area) frame count for c16v normalization: distinct captures present in the
        draws, guarded >=1 (so per_frame is a no-op on 1-capture data)."""
        return max(len(self.captures.get((dk, area), ())), 1)


def draw_aggregates(root: str, drops: list) -> DrawAgg:
    da = DrawAgg()
    for row in _iter_rows(root, drops, 'draws_summary', _DRAWS_COLS, 'draws.parquet'):
        dk = drop_key(row['drop_date'], row['drop_label'])
        area = row['area']
        da.captures[(dk, area)].add(row.get('capture'))
        mh = row.get('mesh_hash')
        n_idx = row.get('num_indices') or 0
        prog = row.get('program_id') or 0
        if not mh or n_idx <= 0 or prog == 0:
            continue
        k = (dk, area, mh)
        da.count[k] += 1
        da.num_indices[k].append(n_idx)
        da.draw_class.setdefault(k, row.get('draw_class') or 'other')
        da.pass_norm.setdefault(k, row.get('parent_pass_path_norm') or '')
    return da


# --- shaders ------------------------------------------------------------------------------------

@dataclass
class ShaderAgg:
    """Shader aggregates keyed by ``(drop_key, area, stable_key)``. ``uses`` sums used_by_draw_count;
    ``cplx`` is the per-key max complexity; ``cost_sum`` is sum-over-rows(complexity*uses) - the two
    consumers use DIFFERENT cost formulas (dashboard._top_shaders = cost_sum; shader_hotlist =
    cplx*uses), so both atoms are exposed to stay byte-identical."""

    uses: Counter = field(default_factory=Counter)             # sum used_by_draw_count
    cost_sum: dict = field(default_factory=lambda: defaultdict(float))  # sum(complexity*uses) per row
    cplx: dict = field(default_factory=dict)                   # max complexity
    stype: dict = field(default_factory=dict)
    captures: dict = field(default_factory=lambda: defaultdict(set))   # (drop_key, area) -> {capture}

    def frames(self, dk: str, area: str) -> int:
        return max(len(self.captures.get((dk, area), ())), 1)


def shader_aggregates(root: str, drops: list, *, stage: str | None = None) -> ShaderAgg:
    """Aggregate shaders. ``stage`` filters shader_type (e.g. 'fragment'); None keeps all. The
    captured-frame set spans the kept (stage-filtered) rows, matching the entity being normalized."""
    sa = ShaderAgg()
    for row in _iter_rows(root, drops, 'shader_summary', _SHADER_COLS, 'shaders.parquet'):
        stype = row.get('shader_type') or ''
        if stage and stype != stage:
            continue
        sk = row.get('stable_key') or ''
        if not sk:
            continue
        dk = drop_key(row['drop_date'], row['drop_label'])
        area = row['area']
        sa.captures[(dk, area)].add(row.get('capture'))
        k = (dk, area, sk)
        c_val = float(row.get('complexity_score') or 0)
        uses = int(row.get('used_by_draw_count') or 0)
        sa.uses[k] += uses
        sa.cost_sum[k] += c_val * uses
        sa.cplx[k] = max(sa.cplx.get(k, 0.0), c_val)
        sa.stype[k] = stype
    return sa
