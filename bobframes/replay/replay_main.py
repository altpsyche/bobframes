"""Main replay-time extraction. Runs INSIDE qrenderdoc's embedded Python 3.10.

Invoked via:
    qrenderdoc.exe --python replay_main.py

Args via env var RDC_INSIDE_ARGS, separated by \\x1f:
    drop_dir, capture, area, drop_date, drop_label, stage_root

Writes CSVs to <stage_root>/<capture>/<table>.csv (one row per record).

This script cannot import the host bobframes package reliably from inside
qrenderdoc, so column tuples are duplicated here. Host-side parquetize
verifies headers against schemas.py.

CRITICAL:
- End with os._exit(0); sys.exit() lets qrenderdoc start its GUI.
- stdout is swallowed; everything important must go to <capture>/_replay.log.
"""

from __future__ import annotations

import csv
import json
import os
import sys
import time
import traceback

_SEP = '\x1f'


# --- Schema constants (mirror schemas.py exactly) ---------------------------
#
# Duplicated by design (H-6): this script runs inside qrenderdoc's embedded Python and cannot import
# the host bobframes package, so these tuples mirror bobframes/schemas.py. Drift is guarded by
# bobframes/tests/test_replay_drift.py (CI) and re-checked at parquetize header-verify time.
# EVENTS/DRAWS/PASSES intentionally omit their *_norm + draw_class columns — those are derived
# host-side after replay (see derive_post_merge.py). Keep these in sync with schemas.py.

ID_COLS = ('area', 'drop_date', 'drop_label', 'capture')

EVENTS_COLS = ID_COLS + (
    'event_id', 'parent_marker_path', 'chunk_name', 'depth',
    'is_drawcall', 'is_dispatch', 'is_clear', 'is_copy', 'is_resolve',
    'is_marker_push', 'is_marker_pop', 'is_set_state',
    'num_indices', 'num_instances',
    'dispatch_x', 'dispatch_y', 'dispatch_z',
    'output_color_rt_id', 'output_depth_rt_id',
    'copy_source_id', 'copy_destination_id',
)

DRAWS_COLS = ID_COLS + (
    'event_id', 'parent_pass_path', 'draw_name',
    'num_indices', 'num_instances', 'base_vertex', 'vertex_offset', 'index_offset',
    'topology',
    'program_id', 'vs_shader_id', 'fs_shader_id',
    'color_rt_ids', 'depth_rt_id',
    'viewport_x', 'viewport_y', 'viewport_w', 'viewport_h',
    'scissor_x', 'scissor_y', 'scissor_w', 'scissor_h',
    'cull_mode', 'front_face',
    'depth_test_enable', 'depth_write_enable', 'depth_func',
    'stencil_enable',
    'stencil_front_pass_op', 'stencil_front_fail_op', 'stencil_front_depth_fail_op',
    'stencil_back_pass_op',  'stencil_back_fail_op',  'stencil_back_depth_fail_op',
    'stencil_ref', 'stencil_read_mask', 'stencil_write_mask',
    'blend_enable',
    'blend_src_color', 'blend_dst_color', 'blend_op_color',
    'blend_src_alpha', 'blend_dst_alpha', 'blend_op_alpha',
    'color_write_mask',
    'ibo_id', 'ibo_index_type',
    'gpu_duration_s',
    'post_vs_primitives', 'post_vs_vertices',
    'mesh_hash',
    'screen_min_x', 'screen_min_y', 'screen_max_x', 'screen_max_y',
    'screen_coverage_px',
)

PASSES_COLS = ID_COLS + (
    'marker_path', 'depth', 'first_event_id', 'last_event_id',
    'num_draws', 'num_dispatches', 'num_clears', 'num_other_actions',
    'num_primitives_pre_vs', 'num_primitives_post_vs',
    'num_vertices_pre_vs', 'num_vertices_post_vs',
    'gpu_duration_s',
    'unique_programs', 'unique_shaders', 'unique_meshes', 'unique_materials',
    'color_rt_id_first', 'depth_rt_id_first',
    'draws_by_class_opaque', 'draws_by_class_prepass', 'draws_by_class_translucent',
    'draws_by_class_decal', 'draws_by_class_shadow', 'draws_by_class_ui',
    'draws_by_class_postprocess', 'draws_by_class_additive', 'draws_by_class_other',
)

RT_COLS = ID_COLS + (
    'stable_key',
    'rt_id', 'format', 'width', 'height', 'depth', 'mip_levels', 'sample_count',
    'is_color', 'is_depth', 'is_stencil', 'is_swap_chain_target',
    'first_write_event', 'last_write_event', 'first_read_event', 'last_read_event',
    'num_write_events', 'num_read_events',
    'attached_to_fbo_ids', 'sampled_by_shader_ids',
    'min_value_r', 'min_value_g', 'min_value_b', 'min_value_a',
    'max_value_r', 'max_value_g', 'max_value_b', 'max_value_a',
)

RT_TIMELINE_COLS = ID_COLS + (
    'rt_id', 'event_id', 'usage_code', 'usage_name', 'view_id',
    'attachment_point_or_slot',
)

COUNTERS_COLS = ID_COLS + (
    'event_id', 'counter_name', 'counter_unit', 'value_double', 'value_uint64',
)

STATE_CHANGE_COLS = ID_COLS + (
    'event_id', 'parent_marker_path', 'call_name',
    'target_or_cap', 'arg_id', 'arg_int', 'arg_float', 'arg_extra_json',
)

CLEARS_COLS = ID_COLS + (
    'event_id', 'parent_marker_path', 'target',
    'color_r', 'color_g', 'color_b', 'color_a',
    'depth_value', 'stencil_value',
    'buffer_mask', 'fbo_id',
)

DISPATCHES_COLS = ID_COLS + (
    'event_id', 'parent_marker_path',
    'program_id', 'cs_shader_id',
    'group_count_x', 'group_count_y', 'group_count_z',
    'work_group_size_x', 'work_group_size_y', 'work_group_size_z',
    'total_threads',
    'ssbo_bindings', 'image_bindings', 'atomic_counter_bindings',
    'gpu_duration_s',
)

DRAW_BINDINGS_COLS = ID_COLS + (
    'event_id', 'slot_kind', 'slot_index', 'resource_id', 'sampler_id',
    'offset', 'size', 'stride',
)

VERTEX_INPUTS_COLS = ID_COLS + (
    'event_id', 'attribute_index', 'attribute_name', 'enabled',
    'component_count', 'component_type', 'normalized', 'integer',
    'stride_bytes', 'offset_bytes', 'buffer_id', 'vbo_slot',
    'divisor',
)

DESCRIPTOR_ACCESS_COLS = ID_COLS + (
    'event_id', 'descriptor_kind', 'slot_index', 'resource_id', 'view_id',
    'byte_offset', 'byte_size', 'access_type',
)

INDIRECT_ARGS_COLS = ID_COLS + (
    'event_id', 'call_name', 'indirect_buffer_id', 'offset',
    'count', 'instance_count', 'first', 'base_vertex', 'base_instance',
    'group_x', 'group_y', 'group_z', 'stride', 'draw_count',
)

VBO_SAMPLES_COLS = ID_COLS + (
    'buffer_id', 'vertex_index', 'byte_offset',
    'raw_hex', 'as_f32_0', 'as_f32_1', 'as_f32_2', 'as_f32_3',
)

IBO_SAMPLES_COLS = ID_COLS + (
    'buffer_id', 'index_position', 'index_value', 'index_type',
)

POST_VS_SAMPLES_COLS = ID_COLS + (
    'event_id', 'vertex_index',
    'position_x', 'position_y', 'position_z', 'position_w',
    'clipped',
)

TEXTURE_SAMPLES_COLS = ID_COLS + (
    'tex_id', 'row_index', 'col_index',
    'raw_hex', 'as_unorm8_r', 'as_unorm8_g', 'as_unorm8_b', 'as_unorm8_a',
)

PIXEL_HISTORY_COLS = ID_COLS + (
    'rt_id', 'sample_x', 'sample_y', 'mod_index',
    'event_id', 'primitive_id',
    'passed', 'backface_culled', 'depth_test_failed', 'stencil_test_failed',
    'scissor_clipped', 'shader_discarded', 'sample_masked',
    'depth_clipped', 'view_clipped',
    'shader_out_r', 'shader_out_g', 'shader_out_b', 'shader_out_a',
    'pre_mod_r', 'pre_mod_g', 'pre_mod_b', 'pre_mod_a',
    'post_mod_r', 'post_mod_g', 'post_mod_b', 'post_mod_a',
)

FBOS_COLS = ID_COLS + (
    'stable_key',
    'fbo_id', 'attachment_point', 'kind', 'resource_id', 'format',
    'width', 'height', 'sample_count',
    'mip_level', 'layer', 'created_at_event', 'bound_at_events',
    'num_clears', 'num_writes', 'num_reads', 'label',
)

FRAME_TOTALS_COLS = ID_COLS + (
    'n_events', 'n_draws', 'n_dispatches', 'n_clears',
    'total_primitives_pre_vs', 'total_vertices_pre_vs',
    'total_primitives_post_vs', 'total_vertices_post_vs',
    'total_gpu_duration_s',
    'glUseProgram_count', 'glBindBuffer_count', 'glBindTexture_count', 'glActiveTexture_count',
    'glBindFramebuffer_count', 'glBindBufferBase_count', 'glBindSampler_count',
    'glDrawElements_count', 'glDrawArrays_count', 'glDrawElementsInstanced_count',
    'glDispatchCompute_count', 'glClear_count', 'glClearBuffer_count',
    'total_vbo_bytes_uploaded', 'total_ibo_bytes_uploaded', 'total_ubo_bytes_uploaded',
    'total_texture_bytes_allocated', 'total_renderbuffer_bytes_allocated',
    'unique_programs_used', 'unique_shaders_used', 'unique_meshes_drawn',
    'unique_materials_drawn', 'unique_textures_bound',
    'fbo_switches', 'program_switches', 'texture_unit_switches',
)


# --- Helpers -----------------------------------------------------------------

def _parse_args() -> dict:
    env = os.environ.get('RDC_INSIDE_ARGS', '')
    parts = env.split(_SEP) if env else []
    if len(parts) < 6:
        raise RuntimeError(f'expected 6 args in RDC_INSIDE_ARGS, got {len(parts)}: {parts!r}')
    return {
        'drop_dir':   parts[0],
        'capture':    parts[1],
        'area':       parts[2],
        'drop_date':  parts[3],
        'drop_label': parts[4],
        'stage_root': parts[5],
    }


def _tee_setup(capture_stage: str):
    log_path = os.path.join(capture_stage, '_replay.log')
    os.makedirs(capture_stage, exist_ok=True)
    log = open(log_path, 'w', encoding='utf-8', buffering=1)

    class _Tee:
        def __init__(self, *s): self.s = s
        def write(self, d):
            for o in self.s:
                try: o.write(d); o.flush()
                except Exception: pass
        def flush(self):
            for o in self.s:
                try: o.flush()
                except Exception: pass

    sys.stdout = _Tee(sys.stdout, log)
    sys.stderr = _Tee(sys.stderr, log)
    return log


def _rid_int(rid) -> int:
    """Extract trailing integer from a ResourceId."""
    if rid is None:
        return 0
    try:
        s = str(rid)
        if '::' in s:
            return int(s.split('::', 1)[1])
    except Exception:
        pass
    return 0


def _enum_short(value) -> str:
    """Decode rd enum value to its short name (after final '.')."""
    s = str(value)
    return s.rsplit('.', 1)[-1] if '.' in s else s


def _open_capture(rdc_path: str):
    import renderdoc as rd  # type: ignore
    cap = rd.OpenCaptureFile()
    status = cap.OpenFile(rdc_path, '', None)
    if status != rd.ResultCode.Succeeded:
        raise RuntimeError(f'OpenFile failed: {status}')
    result = cap.OpenCapture(rd.ReplayOptions(), None)
    if isinstance(result, tuple):
        rc, ctrl = result[0], result[1]
    else:
        rc, ctrl = result.result, result.controller
    if rc != rd.ResultCode.Succeeded:
        cap.Shutdown()
        raise RuntimeError(f'OpenCapture failed: {rc}')
    return cap, ctrl


# --- Action tree walk (events + classification) ------------------------------

def _build_event_records(ctrl, sd, ctx):
    """Walk action tree once, build:
       - events[]: list of dicts (one per action node)
       - draw_events[]: subset where is_drawcall=1
       - marker_pushes[]: list of (event_id, depth, marker_path) for PUSH
       - marker_pops[]: list of (event_id, depth) for POP
       - action_by_event: {event_id: action node}  (used later for SetFrameEvent)
       - parent_path_by_event: {event_id: marker_path string}
       Returns dict.
    """
    import renderdoc as rd  # type: ignore

    F = rd.ActionFlags
    DRAW = int(F.Drawcall)
    DISPATCH = int(F.Dispatch)
    CLEAR = int(F.Clear)
    COPY = int(F.Copy)
    RESOLVE = int(F.Resolve)
    PUSH = int(F.PushMarker)
    POP = int(F.PopMarker)
    SET_MARK = int(F.SetMarker) if hasattr(F, 'SetMarker') else 0
    SET_STATE = 0  # rd has no SetState; treated as residual

    events: list[dict] = []
    draw_events: list[dict] = []
    marker_pushes: list[tuple] = []   # (event_id, depth, marker_path)
    marker_pops: list[tuple] = []     # (event_id, depth)
    action_by_event: dict[int, object] = {}
    parent_path_by_event: dict[int, str] = {}
    chunk_name_by_event: dict[int, str] = {}
    chunk_to_event_id: dict[int, int] = {}

    null_rid = rd.ResourceId.Null()

    def name_of(n):
        if hasattr(n, 'GetName'):
            try:
                return n.GetName(sd) or ''
            except Exception:
                pass
        return getattr(n, 'customName', '') or ''

    def walk(nodes, stack, depth):
        for n in nodes:
            flags = int(getattr(n, 'flags', 0))
            nm = name_of(n)
            this_stack = stack
            ev = int(getattr(n, 'eventId', 0))

            if flags & PUSH:
                this_stack = stack + [nm or 'marker']
                marker_pushes.append((ev, depth, '/'.join(this_stack)))
            elif flags & POP:
                marker_pops.append((ev, depth))

            outputs = getattr(n, 'outputs', None) or ()
            depth_out_rid = _rid_int(getattr(n, 'depthOut', None))
            color_out_ids: list[int] = []
            for o in outputs:
                v = _rid_int(o)
                if v:
                    color_out_ids.append(v)
            color_first = color_out_ids[0] if color_out_ids else 0
            color_join = ';'.join(str(x) for x in color_out_ids)

            dim = getattr(n, 'dispatchDimension', None) or (0, 0, 0)
            try:
                dx, dy, dz = int(dim[0]), int(dim[1]), int(dim[2])
            except Exception:
                dx = dy = dz = 0

            row = {
                **ctx,
                'event_id': ev,
                'parent_marker_path': '/'.join(stack),
                'chunk_name': nm,
                'depth': depth,
                'is_drawcall':    int(bool(flags & DRAW)),
                'is_dispatch':    int(bool(flags & DISPATCH)),
                'is_clear':       int(bool(flags & CLEAR)),
                'is_copy':        int(bool(flags & COPY)),
                'is_resolve':     int(bool(flags & RESOLVE)),
                'is_marker_push': int(bool(flags & PUSH)),
                'is_marker_pop':  int(bool(flags & POP)),
                'is_set_state':   int(bool(flags & SET_MARK)),
                'num_indices':   int(getattr(n, 'numIndices', 0) or 0),
                'num_instances': int(getattr(n, 'numInstances', 0) or 0),
                'dispatch_x': dx, 'dispatch_y': dy, 'dispatch_z': dz,
                'output_color_rt_id': color_first,
                'output_depth_rt_id': depth_out_rid,
                'copy_source_id':      _rid_int(getattr(n, 'copySource', None)),
                'copy_destination_id': _rid_int(getattr(n, 'copyDestination', None)),
            }
            row['_color_ids_join'] = color_join

            events.append(row)
            action_by_event[ev] = n
            parent_path_by_event[ev] = '/'.join(stack)
            chunk_name_by_event[ev] = nm

            # Build chunk_index -> event_id map from action's API events.
            for api_ev in (getattr(n, 'events', None) or ()):
                ci = getattr(api_ev, 'chunkIndex', -1)
                if ci >= 0:
                    chunk_to_event_id[ci] = ev

            if row['is_drawcall']:
                draw_events.append(row)

            children = getattr(n, 'children', None) or ()
            if children:
                walk(children, this_stack, depth + 1)

    walk(ctrl.GetRootActions(), [], 0)

    return {
        'events': events,
        'draw_events': draw_events,
        'marker_pushes': marker_pushes,
        'marker_pops': marker_pops,
        'action_by_event': action_by_event,
        'parent_path_by_event': parent_path_by_event,
        'chunk_name_by_event': chunk_name_by_event,
        'chunk_to_event_id': chunk_to_event_id,
    }


# --- Topology + primitive math ----------------------------------------------

def _topology_short(topology) -> str:
    return _enum_short(topology)


def _primitives_for(topology_short: str, ni: int, ic: int) -> int:
    if ni == 0:
        return 0
    if topology_short == 'TriangleList':
        return (ni // 3) * max(ic, 1)
    if topology_short == 'TriangleStrip':
        return max(0, ni - 2) * max(ic, 1)
    if topology_short == 'LineList':
        return (ni // 2) * max(ic, 1)
    if topology_short == 'LineStrip':
        return max(0, ni - 1) * max(ic, 1)
    if topology_short == 'PointList':
        return ni * max(ic, 1)
    return (ni // 3) * max(ic, 1)  # fallback triangle


# Draw classification was removed here (c09, D-6): it was a drifted duplicate of the host
# derive_post_merge classifier and fed only the dead passes.draws_by_class_* columns (no reader;
# superseded by the host-derived pass_class_breakdown table). draw_class is host-derived from facts
# (ADR-9 / ADR-29); the replay stage now emits facts only. Those 9 columns stay zeroed (PASSES_COLS
# is frozen at SCHEMA_VERSION 3); full removal is deferred to the c35 bump (FINDINGS D-6/D-11).


# --- Pipeline state read per draw ------------------------------------------

def _read_draw_state(ctrl, ev_id: int, base_row: dict, parent_path: str,
                     event_durations: dict[int, float]) -> dict:
    import renderdoc as rd  # type: ignore

    ctrl.SetFrameEvent(ev_id, False)
    pipe = ctrl.GetPipelineState()
    glp = ctrl.GetGLPipelineState()

    topology = _topology_short(pipe.GetPrimitiveTopology())

    # depth state
    ds = glp.depthState
    depth_test = int(bool(ds.depthEnable))
    depth_write = int(bool(ds.depthWrites))
    depth_func = _enum_short(rd.CompareFunction(int(ds.depthFunction)))

    # stencil state
    ss = glp.stencilState
    stencil_enable = int(bool(ss.stencilEnable))
    sf = ss.frontFace
    sb = ss.backFace
    s_fp = _enum_short(rd.StencilOperation(int(sf.passOperation)))
    s_ff = _enum_short(rd.StencilOperation(int(sf.failOperation)))
    s_fd = _enum_short(rd.StencilOperation(int(sf.depthFailOperation)))
    s_bp = _enum_short(rd.StencilOperation(int(sb.passOperation)))
    s_bf = _enum_short(rd.StencilOperation(int(sb.failOperation)))
    s_bd = _enum_short(rd.StencilOperation(int(sb.depthFailOperation)))
    sref = int(getattr(sf, 'reference', 0) or 0)
    srd = int(getattr(sf, 'compareMask', 0) or 0)
    swr = int(getattr(sf, 'writeMask', 0) or 0)

    # rasterizer
    rast = glp.rasterizer
    rstate = rast.state
    cull = _enum_short(rd.CullMode(int(rstate.cullMode)))
    front_face = 'CW' if not bool(getattr(rstate, 'frontCCW', True)) else 'CCW'
    # viewport (first)
    vp = rast.viewports[0] if rast.viewports else None
    vp_x = int(vp.x) if vp else 0
    vp_y = int(vp.y) if vp else 0
    vp_w = int(vp.width) if vp else 0
    vp_h = int(vp.height) if vp else 0
    sc = rast.scissors[0] if getattr(rast, 'scissors', None) else None
    sc_x = int(sc.x) if sc else 0
    sc_y = int(sc.y) if sc else 0
    sc_w = int(sc.width) if sc else 0
    sc_h = int(sc.height) if sc else 0

    # blend
    fb = glp.framebuffer
    bs = fb.blendState
    b0 = bs.blends[0] if len(bs.blends) else None
    blend_enable = int(bool(b0.enabled)) if b0 else 0
    if b0:
        cb = b0.colorBlend
        ab = b0.alphaBlend
        blend_src_color = _enum_short(rd.BlendMultiplier(int(cb.source)))
        blend_dst_color = _enum_short(rd.BlendMultiplier(int(cb.destination)))
        blend_op_color  = _enum_short(rd.BlendOperation(int(cb.operation)))
        blend_src_alpha = _enum_short(rd.BlendMultiplier(int(ab.source)))
        blend_dst_alpha = _enum_short(rd.BlendMultiplier(int(ab.destination)))
        blend_op_alpha  = _enum_short(rd.BlendOperation(int(ab.operation)))
        color_write_mask = int(b0.writeMask)
    else:
        blend_src_color = blend_dst_color = blend_op_color = ''
        blend_src_alpha = blend_dst_alpha = blend_op_alpha = ''
        color_write_mask = 15

    # render targets
    dfb = fb.drawFBO
    color_rt_ids: list[int] = []
    for a in getattr(dfb, 'colorAttachments', []) or []:
        rid = _rid_int(getattr(a, 'resource', None))
        if rid:
            color_rt_ids.append(rid)
    depth_rt_id = _rid_int(getattr(dfb.depthAttachment, 'resource', None)) if getattr(dfb, 'depthAttachment', None) else 0
    color_rt_join = ';'.join(str(x) for x in color_rt_ids)

    # shaders
    program_id = _rid_int(getattr(glp.vertexShader, 'programResourceId', None)) or \
                 _rid_int(getattr(glp.fragmentShader, 'programResourceId', None))
    vs_id = _rid_int(getattr(glp.vertexShader, 'shaderResourceId', None))
    fs_id = _rid_int(getattr(glp.fragmentShader, 'shaderResourceId', None))

    # ibo
    vi = glp.vertexInput
    ibo_id = _rid_int(getattr(vi, 'indexBuffer', None))
    ibo_type = ''
    if hasattr(vi, 'indexByteStride'):
        s = int(vi.indexByteStride)
        ibo_type = {1: 'UNSIGNED_BYTE', 2: 'UNSIGNED_SHORT', 4: 'UNSIGNED_INT'}.get(s, str(s))

    # GPU duration: from pre-fetched counters
    gpu_s = event_durations.get(ev_id, 0.0)

    # Post-VS data (count only; samples done later)
    post_vs_prim = 0
    post_vs_vert = 0
    try:
        mf = ctrl.GetPostVSData(0, 0, rd.MeshDataStage.VSOut)
        if mf and getattr(mf, 'vertexResourceId', None) and mf.vertexResourceId != rd.ResourceId.Null():
            post_vs_vert = int(mf.numIndices)
            post_vs_prim = _primitives_for(_topology_short(mf.topology), post_vs_vert, 1)
    except Exception:
        pass

    draw_name = base_row.get('chunk_name', '')

    return {
        **{k: base_row[k] for k in ID_COLS},
        'event_id': ev_id,
        'parent_pass_path': parent_path,
        'draw_name': draw_name,
        'num_indices': base_row['num_indices'],
        'num_instances': base_row['num_instances'],
        'base_vertex': int(getattr(action_attr_get(ctrl, ev_id), 'baseVertex', 0) or 0),
        'vertex_offset': int(getattr(action_attr_get(ctrl, ev_id), 'vertexOffset', 0) or 0),
        'index_offset': int(getattr(action_attr_get(ctrl, ev_id), 'indexOffset', 0) or 0),
        'topology': topology,
        'program_id': program_id,
        'vs_shader_id': vs_id,
        'fs_shader_id': fs_id,
        'color_rt_ids': color_rt_join,
        'depth_rt_id': depth_rt_id,
        'viewport_x': vp_x, 'viewport_y': vp_y, 'viewport_w': vp_w, 'viewport_h': vp_h,
        'scissor_x': sc_x, 'scissor_y': sc_y, 'scissor_w': sc_w, 'scissor_h': sc_h,
        'cull_mode': cull, 'front_face': front_face,
        'depth_test_enable': depth_test, 'depth_write_enable': depth_write,
        'depth_func': depth_func,
        'stencil_enable': stencil_enable,
        'stencil_front_pass_op': s_fp,
        'stencil_front_fail_op': s_ff,
        'stencil_front_depth_fail_op': s_fd,
        'stencil_back_pass_op': s_bp,
        'stencil_back_fail_op': s_bf,
        'stencil_back_depth_fail_op': s_bd,
        'stencil_ref': sref, 'stencil_read_mask': srd, 'stencil_write_mask': swr,
        'blend_enable': blend_enable,
        'blend_src_color': blend_src_color,
        'blend_dst_color': blend_dst_color,
        'blend_op_color': blend_op_color,
        'blend_src_alpha': blend_src_alpha,
        'blend_dst_alpha': blend_dst_alpha,
        'blend_op_alpha': blend_op_alpha,
        'color_write_mask': color_write_mask,
        'ibo_id': ibo_id, 'ibo_index_type': ibo_type,
        'gpu_duration_s': gpu_s,
        'post_vs_primitives': post_vs_prim,
        'post_vs_vertices': post_vs_vert,
    }


def action_attr_get(ctrl, ev_id: int):
    """Reach the current action for ev_id via ctrl. Used to read base_vertex etc."""
    # Note: ctrl.SetFrameEvent already positioned us; pipe.GetMeshFormat is one path
    # but reading via the cached action node is simpler. We pass _action_by_event in.
    return _ACTION_CACHE.get(ev_id, _Empty())


class _Empty: pass

_ACTION_CACHE: dict[int, object] = {}


# --- Per-draw aux extractors (bindings, vertex_inputs, descriptor_access, post_vs samples, fbo state) ---

def _extract_draw_aux(ctrl, ev_id: int, ctx: dict, draw_row: dict,
                      vi_rows: list, db_rows: list, da_rows: list, pvs_rows: list,
                      fbo_state_per_event: dict,
                      mesh_hash_cache: dict,
                      buffer_map: dict,
                      pvs_max_verts: int) -> None:
    """Extend writer lists with bindings/vertex_inputs/descriptor_access/post_vs
    samples for the current draw event. Mutates draw_row to add mesh_hash and
    screen_min_x/min_y/max_x/max_y/screen_coverage_px. SetFrameEvent already done.
    """
    import renderdoc as rd  # type: ignore
    import struct
    import hashlib

    glp = ctrl.GetGLPipelineState()

    # FBO state at this draw: drawFBO with its color/depth/stencil attachments
    try:
        dfb = glp.framebuffer.drawFBO
        fbo_rid = _rid_int(getattr(dfb, 'resourceId', None))
        if fbo_rid and fbo_rid not in fbo_state_per_event:
            attachments: list[dict] = []
            for i, a in enumerate(getattr(dfb, 'colorAttachments', None) or ()):
                rid = _rid_int(getattr(a, 'resource', None))
                if not rid:
                    continue
                attachments.append({
                    'attachment_point': f'GL_COLOR_ATTACHMENT{i}',
                    'kind': 'tex',
                    'resource_id': rid,
                    'mip_level': int(getattr(a, 'firstMip', 0) or 0),
                    'layer': int(getattr(a, 'firstSlice', 0) or 0),
                    'first_event': ev_id,
                })
            for tag, attr_name in (('GL_DEPTH_ATTACHMENT', 'depthAttachment'),
                                    ('GL_STENCIL_ATTACHMENT', 'stencilAttachment')):
                a = getattr(dfb, attr_name, None)
                if a is None:
                    continue
                rid = _rid_int(getattr(a, 'resource', None))
                if not rid:
                    continue
                attachments.append({
                    'attachment_point': tag,
                    'kind': 'tex',
                    'resource_id': rid,
                    'mip_level': int(getattr(a, 'firstMip', 0) or 0),
                    'layer': int(getattr(a, 'firstSlice', 0) or 0),
                    'first_event': ev_id,
                })
            fbo_state_per_event[fbo_rid] = attachments
    except Exception:
        pass

    # Vertex inputs (per attribute slot)
    vi = glp.vertexInput
    attrs = getattr(vi, 'attributes', None) or []
    vbuffers = getattr(vi, 'vertexBuffers', None) or []
    for i, attr in enumerate(attrs):
        slot = int(getattr(attr, 'vertexBufferSlot', 0) or 0)
        buf = vbuffers[slot] if 0 <= slot < len(vbuffers) else None
        bytes_offset = int(getattr(attr, 'byteOffset', 0) or 0)
        comp_type = _enum_short(getattr(attr.format, 'compType', '')) if hasattr(attr, 'format') else ''
        comp_count = int(getattr(attr.format, 'compCount', 0) or 0) if hasattr(attr, 'format') else 0
        normalized = int(bool(getattr(attr.format, 'compType', None) and 'NORM' in _enum_short(attr.format.compType).upper())) if hasattr(attr, 'format') else 0
        integer = int(bool(comp_type.startswith('UInt') or comp_type.startswith('SInt'))) if comp_type else 0
        stride = int(getattr(buf, 'byteStride', 0) or 0) if buf else 0
        buffer_id = _rid_int(getattr(buf, 'resourceId', None)) if buf else 0
        divisor = int(getattr(buf, 'instanceDivisor', 0) or 0) if buf else 0
        vi_rows.append({
            **ctx,
            'event_id': ev_id, 'attribute_index': i,
            'attribute_name': getattr(attr, 'name', '') or '',
            'enabled': int(bool(getattr(attr, 'enabled', True))),
            'component_count': comp_count, 'component_type': comp_type,
            'normalized': normalized, 'integer': integer,
            'stride_bytes': stride, 'offset_bytes': bytes_offset,
            'buffer_id': buffer_id, 'vbo_slot': slot,
            'divisor': divisor,
        })

    # Draw bindings: textures + samplers + uniform buffers + ssbos + image units
    textures = getattr(glp, 'textures', None) or []
    for i, t in enumerate(textures):
        rid = _rid_int(getattr(t, 'resourceId', None))
        if not rid:
            continue
        db_rows.append({
            **ctx, 'event_id': ev_id,
            'slot_kind': 'texture', 'slot_index': i, 'resource_id': rid,
            'sampler_id': 0, 'offset': 0, 'size': 0, 'stride': 0,
        })
    samplers = getattr(glp, 'samplers', None) or []
    for i, s in enumerate(samplers):
        rid = _rid_int(getattr(s, 'resourceId', None))
        if not rid:
            continue
        db_rows.append({
            **ctx, 'event_id': ev_id,
            'slot_kind': 'sampler', 'slot_index': i, 'resource_id': 0,
            'sampler_id': rid, 'offset': 0, 'size': 0, 'stride': 0,
        })
    ubos = getattr(glp, 'uniformBuffers', None) or []
    for i, b in enumerate(ubos):
        rid = _rid_int(getattr(b, 'resourceId', None))
        if not rid:
            continue
        db_rows.append({
            **ctx, 'event_id': ev_id,
            'slot_kind': 'ubo', 'slot_index': i, 'resource_id': rid,
            'sampler_id': 0,
            'offset': int(getattr(b, 'byteOffset', 0) or 0),
            'size': int(getattr(b, 'byteSize', 0) or 0),
            'stride': 0,
        })
    ssbos = getattr(glp, 'shaderStorageBuffers', None) or []
    for i, b in enumerate(ssbos):
        rid = _rid_int(getattr(b, 'resourceId', None))
        if not rid:
            continue
        db_rows.append({
            **ctx, 'event_id': ev_id,
            'slot_kind': 'ssbo', 'slot_index': i, 'resource_id': rid,
            'sampler_id': 0,
            'offset': int(getattr(b, 'byteOffset', 0) or 0),
            'size': int(getattr(b, 'byteSize', 0) or 0),
            'stride': 0,
        })

    # Descriptor access (resources actually used by bound shaders)
    try:
        accesses = ctrl.GetDescriptorAccess()
    except Exception:
        accesses = ()
    for a in accesses or ():
        try:
            kind = _enum_short(getattr(a, 'type', ''))
            slot = int(getattr(a, 'index', 0) or 0)
            rid = _rid_int(getattr(a, 'descriptorStore', None))
            view = _rid_int(getattr(a, 'view', None))
            byte_offset = int(getattr(a, 'byteOffset', 0) or 0)
            byte_size = int(getattr(a, 'byteSize', 0) or 0)
            access = _enum_short(getattr(a, 'stage', ''))
            da_rows.append({
                **ctx, 'event_id': ev_id,
                'descriptor_kind': kind, 'slot_index': slot,
                'resource_id': rid, 'view_id': view,
                'byte_offset': byte_offset, 'byte_size': byte_size,
                'access_type': access,
            })
        except Exception:
            continue

    # Post-VS samples + screen-space bbox derivation
    vp_x = float(draw_row.get('viewport_x', 0) or 0)
    vp_y = float(draw_row.get('viewport_y', 0) or 0)
    vp_w = float(draw_row.get('viewport_w', 0) or 0)
    vp_h = float(draw_row.get('viewport_h', 0) or 0)
    min_x = min_y = float('inf')
    max_x = max_y = float('-inf')
    have_bbox = False
    try:
        mf = ctrl.GetPostVSData(0, 0, rd.MeshDataStage.VSOut)
        if mf and mf.vertexResourceId and mf.vertexResourceId != rd.ResourceId.Null():
            stride = int(getattr(mf, 'vertexByteStride', 0) or 0)
            n_v = min(int(mf.numIndices), pvs_max_verts)
            if stride >= 16 and n_v > 0:
                raw = ctrl.GetBufferData(mf.vertexResourceId, 0, stride * n_v)
                for vi_idx in range(n_v):
                    off = vi_idx * stride
                    try:
                        x, y, z, w = struct.unpack_from('<ffff', raw, off)
                    except struct.error:
                        break
                    clipped = 0
                    if w == 0.0 or abs(x) > abs(w) or abs(y) > abs(w) or abs(z) > abs(w):
                        clipped = 1
                    pvs_rows.append({
                        **ctx,
                        'event_id': ev_id, 'vertex_index': vi_idx,
                        'position_x': x, 'position_y': y, 'position_z': z, 'position_w': w,
                        'clipped': clipped,
                    })
                    # NDC -> viewport pixel space
                    if w != 0.0 and not clipped:
                        ndc_x = x / w
                        ndc_y = y / w
                        sx = vp_x + (ndc_x * 0.5 + 0.5) * vp_w
                        sy = vp_y + (ndc_y * 0.5 + 0.5) * vp_h
                        if sx < min_x: min_x = sx
                        if sy < min_y: min_y = sy
                        if sx > max_x: max_x = sx
                        if sy > max_y: max_y = sy
                        have_bbox = True
    except Exception:
        pass

    if have_bbox:
        # clamp to viewport
        cx0 = max(min_x, vp_x); cy0 = max(min_y, vp_y)
        cx1 = min(max_x, vp_x + vp_w); cy1 = min(max_y, vp_y + vp_h)
        draw_row['screen_min_x'] = float(min_x)
        draw_row['screen_min_y'] = float(min_y)
        draw_row['screen_max_x'] = float(max_x)
        draw_row['screen_max_y'] = float(max_y)
        if cx1 > cx0 and cy1 > cy0:
            draw_row['screen_coverage_px'] = int(round((cx1 - cx0) * (cy1 - cy0)))
        else:
            draw_row['screen_coverage_px'] = 0
    else:
        draw_row['screen_min_x'] = 0.0
        draw_row['screen_min_y'] = 0.0
        draw_row['screen_max_x'] = 0.0
        draw_row['screen_max_y'] = 0.0
        draw_row['screen_coverage_px'] = 0

    # Mesh hash for instancing-candidate detection
    ibo_id = int(draw_row.get('ibo_id', 0) or 0)
    n_indices = int(draw_row.get('num_indices', 0) or 0)
    base_vertex = int(draw_row.get('base_vertex', 0) or 0)
    index_offset = int(draw_row.get('index_offset', 0) or 0)
    vbo_slot_0_id = 0
    vbuffers = getattr(vi, 'vertexBuffers', None) or []
    if vbuffers:
        vbo_slot_0_id = _rid_int(getattr(vbuffers[0], 'resourceId', None))

    if ibo_id > 0:
        identity = (ibo_id, base_vertex, index_offset, n_indices)
        cached = mesh_hash_cache.get(identity)
        if cached is not None:
            draw_row['mesh_hash'] = cached
        else:
            ibo_obj = buffer_map.get(ibo_id)
            data_bytes = b''
            if ibo_obj is not None:
                try:
                    # index_offset in draws is the offset within IBO (in bytes typically
                    # for glDrawElementsBaseVertex* path; we read 1KB from there)
                    data_bytes = bytes(ctrl.GetBufferData(ibo_obj.resourceId,
                                                         max(index_offset, 0), 1024))
                except Exception:
                    data_bytes = b''
            h = hashlib.sha256()
            h.update(f'{ibo_id}|{base_vertex}|{index_offset}|{n_indices}|'.encode())
            h.update(data_bytes)
            digest = h.hexdigest()[:24]
            mesh_hash_cache[identity] = digest
            draw_row['mesh_hash'] = digest
    else:
        identity = ('noidx', vbo_slot_0_id, int(draw_row.get('vertex_offset', 0) or 0), n_indices)
        cached = mesh_hash_cache.get(identity)
        if cached is None:
            h = hashlib.sha256(f'noidx|{vbo_slot_0_id}|{draw_row.get("vertex_offset",0)}|{n_indices}'.encode())
            cached = h.hexdigest()[:24]
            mesh_hash_cache[identity] = cached
        draw_row['mesh_hash'] = cached


# --- Uniforms per pass -------------------------------------------------------

def _snapshot_uniforms(ctrl, ev_id: int, marker_path: str, ctx: dict) -> dict | None:
    """For the first draw under a unique pass marker, capture each bound
    constant block: the binding metadata + the reflection layout (name,
    type, byteOffset, byteSize per member) + a hex-encoded UBO data sample.

    SetFrameEvent must have been called on ev_id. Returns dict or None.
    """
    import renderdoc as rd  # type: ignore

    glp = ctrl.GetGLPipelineState()
    blocks_out: list[dict] = []

    stages = [
        ('vertex', getattr(glp, 'vertexShader', None)),
        ('fragment', getattr(glp, 'fragmentShader', None)),
        ('compute', getattr(glp, 'computeShader', None)),
    ]
    seen_buffer_keys: set[tuple[int, int, int]] = set()

    # First fetch raw UBO bytes (needed to decode member values inline).
    raw_by_binding: dict[int, dict] = {}
    raw_bytes_by_slot: dict[int, bytes] = {}
    try:
        accesses = ctrl.GetDescriptorAccess()
    except Exception:
        accesses = ()
    for a in accesses or ():
        try:
            kind = _enum_short(getattr(a, 'type', ''))
            if kind != 'ConstantBuffer':
                continue
            slot = int(getattr(a, 'index', 0) or 0)
            buf_rid = getattr(a, 'descriptorStore', None)
            if buf_rid is None:
                continue
            offset = int(getattr(a, 'byteOffset', 0) or 0)
            size = int(getattr(a, 'byteSize', 0) or 0)
            if not size:
                continue
            sample = min(size, 1024)
            data = bytes(ctrl.GetBufferData(buf_rid, offset, sample))
            raw_by_binding[slot] = {
                'buffer_id': _rid_int(buf_rid),
                'offset': offset, 'size': size,
                'raw_hex': data.hex(),
            }
            raw_bytes_by_slot[slot] = data
        except Exception:
            continue

    for stage_name, stage in stages:
        if stage is None:
            continue
        refl = getattr(stage, 'reflection', None)
        if refl is None:
            continue
        prog_rid = _rid_int(getattr(stage, 'programResourceId', None))
        shader_rid = _rid_int(getattr(stage, 'shaderResourceId', None))
        constant_blocks = getattr(refl, 'constantBlocks', None) or ()
        for cb in constant_blocks:
            binding_index = int(getattr(cb, 'bindPoint', 0) or 0)
            members_out: list[dict] = []
            ubo_data = raw_bytes_by_slot.get(binding_index, b'')
            for var in getattr(cb, 'variables', None) or ():
                vt = getattr(var, 'type', None)
                byte_offset = int(getattr(var, 'byteOffset', 0) or 0)
                base_type = _enum_short(getattr(vt, 'baseType', '')) if vt else ''
                rows = int(getattr(vt, 'rows', 0) or 0) if vt else 0
                cols = int(getattr(vt, 'columns', 0) or 0) if vt else 0
                elements = int(getattr(vt, 'elements', 0) or 0) if vt else 0
                m = {
                    'name': getattr(var, 'name', ''),
                    'byte_offset': byte_offset,
                    'type': base_type,
                    'rows': rows, 'columns': cols, 'elements': elements,
                }
                value, truncated = _decode_ubo_member(ubo_data, byte_offset,
                                                     base_type, rows, cols, elements,
                                                     array_cap=16)
                if value is not None:
                    m['value'] = value
                if truncated:
                    m['truncated'] = True
                members_out.append(m)
            byte_size = int(getattr(cb, 'byteSize', 0) or 0)
            blocks_out.append({
                'stage': stage_name,
                'shader_id': shader_rid,
                'program_id': prog_rid,
                'block_name': getattr(cb, 'name', ''),
                'binding_index': binding_index,
                'byte_size': byte_size,
                'members': members_out,
            })

    if not blocks_out:
        return None

    return {
        **ctx,
        'event_id': ev_id,
        'marker_path': marker_path,
        'constant_blocks': blocks_out,
        'raw_by_binding': raw_by_binding,
    }


def _decode_ubo_member(raw: bytes, byte_offset: int, base_type: str,
                       rows: int, cols: int, elements: int,
                       array_cap: int = 16):
    """Decode std140-laid-out scalars/vectors/matrices from raw UBO bytes.

    Returns (value, truncated). value is None when decode not possible
    (out-of-range offset, unknown type, no bytes). Arrays beyond array_cap
    are truncated; truncated=True flagged.
    """
    import struct
    if not raw or byte_offset < 0:
        return None, False
    n = len(raw)
    # Determine scalar size + struct fmt by base type.
    fmt = None
    elem_size = 0
    if base_type in ('Float',):
        fmt = '<f'; elem_size = 4
    elif base_type in ('SInt32', 'SInt', 'Int'):
        fmt = '<i'; elem_size = 4
    elif base_type in ('UInt32', 'UInt'):
        fmt = '<I'; elem_size = 4
    else:
        return None, False

    def read_one(off, rows_, cols_):
        if rows_ <= 1 and cols_ <= 1:
            if off + elem_size > n:
                return None
            return struct.unpack_from(fmt, raw, off)[0]
        if rows_ == 1 and cols_ > 1:
            need = elem_size * cols_
            if off + need > n:
                return None
            return list(struct.unpack_from(fmt * cols_, raw, off))
        # Matrix: GL std140 layout = each column on 16-byte boundary, column-major
        out = []
        for c in range(cols_):
            row_off = off + c * 16
            if row_off + elem_size * rows_ > n:
                return None
            out.append(list(struct.unpack_from(fmt * rows_, raw, row_off)))
        return out

    n_elements = max(1, elements)
    truncated = False
    if n_elements > array_cap:
        n_elements = array_cap
        truncated = True

    if elements <= 1:
        return read_one(byte_offset, rows, cols), False

    # std140 array stride: 16 bytes per scalar/vec; mat stride = cols * 16
    if rows <= 1:
        stride = 16
    else:
        stride = cols * 16
    out_list = []
    for ei in range(n_elements):
        v = read_one(byte_offset + ei * stride, rows, cols)
        if v is None:
            break
        out_list.append(v)
    return out_list, truncated


# --- Clears + dispatches extraction -----------------------------------------

_CLEAR_CHUNK_NAMES = {'glClear', 'glClearBufferfv', 'glClearBufferfi',
                      'glClearBufferiv', 'glClearBufferuiv'}


def _decode_clear_chunk(chunk) -> dict:
    """Decode a clear chunk's args. Probed on Arm RD v1.43.

    Children for glClearBufferfv: framebuffer (ResourceId), buffer (enum string),
    drawbuffer (int), value (array of 4 with sub.name='$el' .AsFloat()).
    Children for glClearBufferfi: framebuffer, buffer (GL_DEPTH_STENCIL),
    drawbuffer, depth (AsFloat), stencil (AsInt).
    Children for glClear: mask (bitfield via AsInt).
    """
    out = {
        'color_r': 0.0, 'color_g': 0.0, 'color_b': 0.0, 'color_a': 0.0,
        'depth_value': 0.0, 'stencil_value': 0,
        'buffer_mask': 0, 'target': '', 'fbo_id': 0,
    }
    name = chunk.name
    fb = chunk.FindChild('framebuffer')
    if fb is not None:
        try:
            out['fbo_id'] = _rid_int(fb.AsResourceId())
        except Exception:
            pass
    if name == 'glClear':
        m = chunk.FindChild('mask')
        if m is not None:
            try: out['buffer_mask'] = int(m.AsInt() or 0)
            except Exception: pass
    elif name in ('glClearBufferfv', 'glClearBufferiv', 'glClearBufferuiv'):
        b = chunk.FindChild('buffer')
        if b is not None:
            try: out['target'] = b.AsString() or ''
            except Exception: pass
        v = chunk.FindChild('value')
        if v is not None:
            try:
                n = v.NumChildren()
                keys = ('color_r', 'color_g', 'color_b', 'color_a')
                for i in range(min(n, 4)):
                    child = v.GetChild(i)
                    if child is None: continue
                    if name == 'glClearBufferfv':
                        out[keys[i]] = float(child.AsFloat() or 0.0)
                    else:
                        out[keys[i]] = float(child.AsInt() or 0)
            except Exception:
                pass
    elif name == 'glClearBufferfi':
        b = chunk.FindChild('buffer')
        if b is not None:
            try: out['target'] = b.AsString() or ''
            except Exception: pass
        d = chunk.FindChild('depth')
        if d is not None:
            try: out['depth_value'] = float(d.AsFloat() or 0.0)
            except Exception: pass
        s = chunk.FindChild('stencil')
        if s is not None:
            try: out['stencil_value'] = int(s.AsInt() or 0)
            except Exception: pass
    return out


def _extract_clears(sd, events: list[dict], action_by_event: dict,
                    ctx: dict) -> list[dict]:
    """One row per clear action with decoded color/depth/stencil/fbo_id."""
    rows: list[dict] = []
    chunks = sd.chunks
    n_chunks = len(chunks)
    for e in events:
        if not e['is_clear']:
            continue
        ev_id = e['event_id']
        action = action_by_event.get(ev_id)
        decoded = None
        if action is not None:
            api_evs = getattr(action, 'events', None) or ()
            for api_ev in api_evs:
                ci = getattr(api_ev, 'chunkIndex', -1)
                if 0 <= ci < n_chunks:
                    c = chunks[ci]
                    if c.name in _CLEAR_CHUNK_NAMES:
                        try:
                            decoded = _decode_clear_chunk(c)
                        except Exception:
                            decoded = None
                        break
        if decoded is None:
            decoded = {
                'color_r': 0.0, 'color_g': 0.0, 'color_b': 0.0, 'color_a': 0.0,
                'depth_value': 0.0, 'stencil_value': 0,
                'buffer_mask': 0, 'target': '', 'fbo_id': 0,
            }
        rows.append({
            **ctx,
            'event_id': ev_id,
            'parent_marker_path': e['parent_marker_path'],
            'target': decoded['target'],
            'color_r': decoded['color_r'], 'color_g': decoded['color_g'],
            'color_b': decoded['color_b'], 'color_a': decoded['color_a'],
            'depth_value': decoded['depth_value'],
            'stencil_value': decoded['stencil_value'],
            'buffer_mask': decoded['buffer_mask'],
            'fbo_id': decoded['fbo_id'],
        })
    return rows


def _sample_vbos(ctrl, used_vbo_ids: set, ctx: dict, max_verts: int = 16) -> list[dict]:
    """Sample first `max_verts` raw bytes of each used VBO. 64 bytes per row."""
    import renderdoc as rd  # type: ignore

    rows: list[dict] = []
    buffers = {_rid_int(b.resourceId): b for b in ctrl.GetBuffers()}
    for bid in sorted(used_vbo_ids):
        if not bid or bid not in buffers:
            continue
        b = buffers[bid]
        size = int(b.length) if hasattr(b, 'length') else 0
        if size <= 0:
            continue
        sample_bytes = min(64 * max_verts, size)
        try:
            data = ctrl.GetBufferData(b.resourceId, 0, sample_bytes)
        except Exception:
            continue
        stride = 64  # presumed vertex stride; tools can re-interpret per layout
        n_v = min(max_verts, len(data) // stride if stride else 0)
        for vi in range(n_v):
            off = vi * stride
            seg = data[off:off + stride]
            import struct
            try:
                f0, f1, f2, f3 = struct.unpack_from('<ffff', seg, 0)
            except struct.error:
                f0 = f1 = f2 = f3 = 0.0
            rows.append({
                **ctx,
                'buffer_id': bid,
                'vertex_index': vi,
                'byte_offset': off,
                'raw_hex': bytes(seg[:64]).hex(),
                'as_f32_0': float(f0), 'as_f32_1': float(f1),
                'as_f32_2': float(f2), 'as_f32_3': float(f3),
            })
    return rows


def _sample_ibos(ctrl, used_ibo_ids: set, ctx: dict, max_indices: int = 32) -> list[dict]:
    import renderdoc as rd  # type: ignore
    import struct

    rows: list[dict] = []
    buffers = {_rid_int(b.resourceId): b for b in ctrl.GetBuffers()}
    for bid in sorted(used_ibo_ids):
        if not bid or bid not in buffers:
            continue
        b = buffers[bid]
        size = int(b.length) if hasattr(b, 'length') else 0
        if size <= 0:
            continue
        # try uint16 first (mobile typical)
        nb = min(max_indices * 2, size)
        try:
            data = ctrl.GetBufferData(b.resourceId, 0, nb)
        except Exception:
            continue
        n = min(max_indices, len(data) // 2)
        for i in range(n):
            try:
                v = struct.unpack_from('<H', data, i * 2)[0]
            except struct.error:
                v = 0
            rows.append({
                **ctx,
                'buffer_id': bid, 'index_position': i,
                'index_value': int(v), 'index_type': 'uint16',
            })
    return rows


def _sample_textures(ctrl, ctx: dict, max_dim: int = 256, max_cols: int = 16) -> list[dict]:
    import renderdoc as rd  # type: ignore
    import struct

    rows: list[dict] = []
    sub = rd.Subresource(0, 0, 0)
    for tex in ctrl.GetTextures():
        if tex.width <= 0 or tex.height <= 0:
            continue
        if tex.width > max_dim or tex.height > max_dim:
            continue
        try:
            data = ctrl.GetTextureData(tex.resourceId, sub)
        except Exception:
            continue
        if not data:
            continue
        # Heuristic: 4 bytes per pixel for unorm8 RGBA
        bpp = 4
        row_stride = tex.width * bpp
        if len(data) < row_stride:
            continue
        n_cols = min(max_cols, tex.width)
        for col in range(n_cols):
            off = col * bpp
            try:
                r, g, b, a = struct.unpack_from('BBBB', data, off)
            except struct.error:
                continue
            rows.append({
                **ctx,
                'tex_id': _rid_int(tex.resourceId),
                'row_index': 0, 'col_index': col,
                'raw_hex': bytes(data[off:off + 16]).hex(),
                'as_unorm8_r': r, 'as_unorm8_g': g,
                'as_unorm8_b': b, 'as_unorm8_a': a,
            })
    return rows


def _extract_dispatches(ctrl, events: list[dict], event_durations: dict,
                        ctx: dict) -> list[dict]:
    """One row per compute dispatch with program + work group dimensions."""
    rows: list[dict] = []
    for e in events:
        if not e['is_dispatch']:
            continue
        ev = e['event_id']
        gpu = event_durations.get(ev, 0.0)
        program = 0; cs_shader = 0
        wg_x = wg_y = wg_z = 0
        try:
            ctrl.SetFrameEvent(ev, False)
            glp = ctrl.GetGLPipelineState()
            program = _rid_int(getattr(glp.computeShader, 'programResourceId', None))
            cs_shader = _rid_int(getattr(glp.computeShader, 'shaderResourceId', None))
            refl = getattr(glp.computeShader, 'reflection', None)
            if refl is not None:
                ds = getattr(refl, 'dispatchThreadsDimension', None) or (0, 0, 0)
                wg_x, wg_y, wg_z = int(ds[0]), int(ds[1]), int(ds[2])
        except Exception:
            pass
        gx, gy, gz = e['dispatch_x'], e['dispatch_y'], e['dispatch_z']
        rows.append({
            **ctx,
            'event_id': ev, 'parent_marker_path': e['parent_marker_path'],
            'program_id': program, 'cs_shader_id': cs_shader,
            'group_count_x': gx, 'group_count_y': gy, 'group_count_z': gz,
            'work_group_size_x': wg_x, 'work_group_size_y': wg_y, 'work_group_size_z': wg_z,
            'total_threads': gx * gy * gz * max(1, wg_x) * max(1, wg_y) * max(1, wg_z),
            'ssbo_bindings': '', 'image_bindings': '', 'atomic_counter_bindings': '',
            'gpu_duration_s': gpu,
        })
    return rows


# --- FBO finalizer ----------------------------------------------------------

def _build_fbo_rows(ctrl, fbo_state_per_event: dict[int, list[dict]],
                    labels: dict[int, str], ctx: dict) -> list[dict]:
    """Turn the (fbo_id -> attachments list) map into one row per
    (fbo_id, attachment_point). Cross-reference texture metadata for
    format/width/height.
    """
    import renderdoc as rd  # type: ignore

    # Build texture metadata lookup
    tex_info: dict[int, dict] = {}
    for t in ctrl.GetTextures():
        rid = _rid_int(t.resourceId)
        if not rid:
            continue
        try:
            fmt = t.format.Name() if hasattr(t.format, 'Name') else str(t.format)
        except Exception:
            fmt = ''
        tex_info[rid] = {
            'format': fmt,
            'width': int(t.width), 'height': int(t.height),
            'sample_count': int(t.msSamp),
        }

    rows: list[dict] = []
    for fbo_id, attachments in fbo_state_per_event.items():
        for att in attachments:
            tinfo = tex_info.get(att['resource_id'], {'format': '', 'width': 0,
                                                      'height': 0, 'sample_count': 0})
            rows.append({
                **ctx,
                'stable_key': '',  # filled host-side from sorted attachments
                'fbo_id': fbo_id,
                'attachment_point': att['attachment_point'],
                'kind': att['kind'],
                'resource_id': att['resource_id'],
                'format': tinfo['format'],
                'width': tinfo['width'],
                'height': tinfo['height'],
                'sample_count': tinfo['sample_count'],
                'mip_level': att['mip_level'],
                'layer': att['layer'],
                'created_at_event': -1,
                'bound_at_events': str(att['first_event']),
                'num_clears': 0, 'num_writes': 0, 'num_reads': 0,
                'label': labels.get(fbo_id, ''),
            })
    return rows


# --- Indirect args -----------------------------------------------------------

_INDIRECT_CHUNK_NAMES = {
    'glDrawArraysIndirect',
    'glDrawElementsIndirect',
    'glMultiDrawArraysIndirect',
    'glMultiDrawElementsIndirect',
    'glDispatchComputeIndirect',
}


def _extract_indirect_args(ctrl, events: list[dict], ctx: dict) -> list[dict]:
    """For each indirect draw/dispatch event, read the indirect buffer at the
    bound offset and unpack the args. On Arm RD GL backend the bound indirect
    buffer is accessible via the structured chunk args; we use a best-effort
    approach via SetFrameEvent + GLPipelineState.vertexInput.indirectBuffer
    (when present). If we cannot recover the buffer reliably, skip silently.
    """
    import renderdoc as rd  # type: ignore
    import struct

    rows: list[dict] = []
    for e in events:
        cn = e['chunk_name']
        if cn not in _INDIRECT_CHUNK_NAMES:
            continue
        ev = e['event_id']
        try:
            ctrl.SetFrameEvent(ev, False)
            glp = ctrl.GetGLPipelineState()
            ind_rid = None
            offset = 0
            # Try various attribute names where the bound indirect buffer may live.
            for attr_path in (('vertexInput', 'indirectBuffer'),
                              ('vertexInput', 'indirect'),
                              ('framebuffer', 'indirectBuffer')):
                node = glp
                ok = True
                for a in attr_path:
                    node = getattr(node, a, None)
                    if node is None:
                        ok = False
                        break
                if ok and node is not None:
                    rid = _rid_int(getattr(node, 'resourceId', None) or node)
                    if rid:
                        ind_rid = (getattr(node, 'resourceId', None) or node)
                        offset = int(getattr(node, 'byteOffset', 0) or 0)
                        break
            if ind_rid is None:
                continue
            data = ctrl.GetBufferData(ind_rid, offset, 64)
            row = {**ctx, 'event_id': ev, 'call_name': cn,
                   'indirect_buffer_id': _rid_int(ind_rid), 'offset': offset,
                   'count': 0, 'instance_count': 0, 'first': 0,
                   'base_vertex': 0, 'base_instance': 0,
                   'group_x': 0, 'group_y': 0, 'group_z': 0,
                   'stride': 0, 'draw_count': 0}
            if cn == 'glDrawArraysIndirect' and len(data) >= 16:
                count, instance_count, first, base_instance = struct.unpack_from('<IIII', data, 0)
                row.update(count=count, instance_count=instance_count,
                           first=first, base_instance=base_instance)
            elif cn == 'glDrawElementsIndirect' and len(data) >= 20:
                count, instance_count, first, base_vertex, base_instance = struct.unpack_from('<IIIiI', data, 0)
                row.update(count=count, instance_count=instance_count,
                           first=first, base_vertex=base_vertex, base_instance=base_instance)
            elif cn == 'glDispatchComputeIndirect' and len(data) >= 12:
                gx, gy, gz = struct.unpack_from('<III', data, 0)
                row.update(group_x=gx, group_y=gy, group_z=gz)
            rows.append(row)
        except Exception:
            continue
    return rows


# --- Pixel history ----------------------------------------------------------

def _extract_pixel_history(ctrl, ctx: dict, last_event_id: int,
                           grid: int = 4, min_size: int = 256) -> list[dict]:
    """Sample an N×N grid of pixels on each large color render target at
    last_event_id. Per-pixel PixelHistory() yields one row per modification.

    Skips RTs smaller than min_size² (typical dummy/atlas textures).
    """
    import renderdoc as rd  # type: ignore

    rows: list[dict] = []
    if grid <= 0:
        return rows
    sub = rd.Subresource(0, 0, 0)

    for tex in ctrl.GetTextures():
        flags = int(tex.creationFlags)
        if not (flags & int(rd.TextureCategory.ColorTarget)):
            continue
        if tex.width < min_size or tex.height < min_size:
            continue
        rid_int = _rid_int(tex.resourceId)
        margin_x = max(2, int(0.05 * tex.width))
        margin_y = max(2, int(0.05 * tex.height))
        for gy in range(grid):
            for gx in range(grid):
                denom = max(grid - 1, 1)
                x = margin_x + (gx * (tex.width - 2 * margin_x)) // denom
                y = margin_y + (gy * (tex.height - 2 * margin_y)) // denom
                try:
                    hist = ctrl.PixelHistory(tex.resourceId, x, y, sub, rd.CompType.Typeless)
                except Exception:
                    continue
                for idx, mod in enumerate(hist or ()):
                    passed = not (mod.backfaceCulled or mod.depthTestFailed or
                                  mod.stencilTestFailed or mod.scissorClipped or
                                  mod.shaderDiscarded or mod.sampleMasked or
                                  mod.depthClipped or mod.viewClipped)
                    so = mod.shaderOut.col.floatValue
                    pre = mod.preMod.col.floatValue
                    post = mod.postMod.col.floatValue
                    rows.append({
                        **ctx,
                        'rt_id': rid_int,
                        'sample_x': x, 'sample_y': y, 'mod_index': idx,
                        'event_id': int(mod.eventId),
                        'primitive_id': int(getattr(mod, 'primitiveID', -1) or -1),
                        'passed': int(bool(passed)),
                        'backface_culled': int(bool(mod.backfaceCulled)),
                        'depth_test_failed': int(bool(mod.depthTestFailed)),
                        'stencil_test_failed': int(bool(mod.stencilTestFailed)),
                        'scissor_clipped': int(bool(mod.scissorClipped)),
                        'shader_discarded': int(bool(mod.shaderDiscarded)),
                        'sample_masked': int(bool(mod.sampleMasked)),
                        'depth_clipped': int(bool(mod.depthClipped)),
                        'view_clipped': int(bool(mod.viewClipped)),
                        'shader_out_r': float(so[0]), 'shader_out_g': float(so[1]),
                        'shader_out_b': float(so[2]), 'shader_out_a': float(so[3]),
                        'pre_mod_r': float(pre[0]), 'pre_mod_g': float(pre[1]),
                        'pre_mod_b': float(pre[2]), 'pre_mod_a': float(pre[3]),
                        'post_mod_r': float(post[0]), 'post_mod_g': float(post[1]),
                        'post_mod_b': float(post[2]), 'post_mod_a': float(post[3]),
                    })
    return rows


# --- Counters fetch ----------------------------------------------------------

def _fetch_counters_per_event(ctrl, ctx) -> tuple[list[dict], dict[int, float]]:
    """Fetch ALL enumerable counters per event. Returns (rows, duration_by_event)."""
    import renderdoc as rd  # type: ignore

    rows: list[dict] = []
    duration_by_event: dict[int, float] = {}

    counters = ctrl.EnumerateCounters()
    # Use CounterResult.resultType-aware extraction. result_type attr may be int.
    try:
        FLOAT_T = int(rd.CompType.Float)
        DOUBLE_T = -1  # CompType has no Double; renderdoc uses Float for both internally
    except Exception:
        FLOAT_T = -1
        DOUBLE_T = -1

    for counter in counters:
        d = ctrl.DescribeCounter(counter)
        try:
            results = ctrl.FetchCounters([counter])
        except Exception:
            continue
        unit = _enum_short(d.unit)
        name = d.name
        result_type = int(getattr(d, 'resultType', 0))
        # Heuristic: byte width 4 == 32-bit; width 8 + name says 'Duration' or
        # unit Seconds means double. Use d.resultByteWidth + result_type.
        rbw = int(getattr(d, 'resultByteWidth', 8))
        is_float_kind = ('Float' in _enum_short(getattr(d, 'resultType', 0))
                         or unit in ('Seconds', 'Percentage', 'Hertz'))
        for r in results:
            ev = int(r.eventId)
            vd = 0.0
            vu = 0
            if is_float_kind:
                try: vd = float(r.value.d)
                except Exception: pass
            else:
                try: vu = int(r.value.u64)
                except Exception: pass
            rows.append({
                **ctx,
                'event_id': ev,
                'counter_name': name,
                'counter_unit': unit,
                'value_double': vd,
                'value_uint64': vu,
            })
            if counter == rd.GPUCounter.EventGPUDuration:
                duration_by_event[ev] = vd if is_float_kind else float(vu)

    return rows, duration_by_event


# --- RT walk ----------------------------------------------------------------

def _walk_render_targets(ctrl, ctx) -> tuple[list[dict], list[dict]]:
    """Build render_targets.csv rows + rt_event_timeline rows.

    A render target is any texture that has the ColorTarget or DepthTarget
    creation flag. For each one, GetUsage() yields per-event read/write rows.
    """
    import renderdoc as rd  # type: ignore

    rt_rows: list[dict] = []
    timeline_rows: list[dict] = []

    null_rid = rd.ResourceId.Null()
    sub = rd.Subresource(0, 0, 0)

    histogram_by_rt: dict[int, list[int]] = {}
    for tex in ctrl.GetTextures():
        flags = int(tex.creationFlags)
        is_color = bool(flags & int(rd.TextureCategory.ColorTarget))
        is_depth = bool(flags & int(rd.TextureCategory.DepthTarget))
        if not (is_color or is_depth):
            continue
        is_stencil = is_depth and tex.format.compType == rd.CompType.Depth
        is_swap = bool(flags & int(rd.TextureCategory.SwapBuffer))
        rid = _rid_int(tex.resourceId)
        if not rid:
            continue
        fmt = tex.format.Name() if hasattr(tex.format, 'Name') else str(tex.format)

        # min/max for color RTs (depth often returns garbage on GLES replay)
        mn_r = mn_g = mn_b = mn_a = 0.0
        mx_r = mx_g = mx_b = mx_a = 0.0
        if is_color and tex.width > 1 and tex.height > 1:
            try:
                mn, mx = ctrl.GetMinMax(tex.resourceId, sub, rd.CompType.Typeless)
                mn_r, mn_g, mn_b, mn_a = float(mn.floatValue[0]), float(mn.floatValue[1]), float(mn.floatValue[2]), float(mn.floatValue[3])
                mx_r, mx_g, mx_b, mx_a = float(mx.floatValue[0]), float(mx.floatValue[1]), float(mx.floatValue[2]), float(mx.floatValue[3])
            except Exception:
                pass
            try:
                hist = ctrl.GetHistogram(tex.resourceId, sub, rd.CompType.Typeless,
                                         0.0, 1.0, (True, True, True, True))
                histogram_by_rt[rid] = list(int(x) for x in hist)
            except Exception:
                pass

        # Walk usage for timeline
        first_write = -1; last_write = -1; first_read = -1; last_read = -1
        n_writes = 0; n_reads = 0
        try:
            for u in ctrl.GetUsage(tex.resourceId):
                code = int(u.usage)
                kind = _enum_short(rd.ResourceUsage(code))
                evid = int(u.eventId)
                view_rid = _rid_int(getattr(u, 'view', None))
                tl = {
                    **ctx,
                    'rt_id': rid, 'event_id': evid, 'usage_code': code,
                    'usage_name': kind, 'view_id': view_rid,
                    'attachment_point_or_slot': '',
                }
                timeline_rows.append(tl)
                lc = kind.lower()
                is_write_kind = ('target' in lc or 'write' in lc or 'clear' in lc or
                                 'copydst' in lc or 'resolvedst' in lc)
                if is_write_kind:
                    n_writes += 1
                    if first_write < 0: first_write = evid
                    last_write = evid
                else:
                    n_reads += 1
                    if first_read < 0: first_read = evid
                    last_read = evid
        except Exception:
            pass

        rt_rows.append({
            **ctx,
            'stable_key': '',  # filled host-side
            'rt_id': rid,
            'format': fmt,
            'width': int(tex.width), 'height': int(tex.height),
            'depth': int(tex.depth), 'mip_levels': int(tex.mips),
            'sample_count': int(tex.msSamp),
            'is_color': int(is_color),
            'is_depth': int(is_depth),
            'is_stencil': int(is_stencil),
            'is_swap_chain_target': int(is_swap),
            'first_write_event': first_write,
            'last_write_event': last_write,
            'first_read_event': first_read,
            'last_read_event': last_read,
            'num_write_events': n_writes,
            'num_read_events': n_reads,
            'attached_to_fbo_ids': '',
            'sampled_by_shader_ids': '',
            'min_value_r': mn_r, 'min_value_g': mn_g, 'min_value_b': mn_b, 'min_value_a': mn_a,
            'max_value_r': mx_r, 'max_value_g': mx_g, 'max_value_b': mx_b, 'max_value_a': mx_a,
        })

    return rt_rows, timeline_rows, histogram_by_rt


# --- State-change chunks -----------------------------------------------------

STATE_CHANGE_CHUNK_NAMES = {
    'glBindTexture', 'glActiveTexture', 'glUseProgram',
    'glEnable', 'glDisable',
    'glBindBuffer', 'glBindBufferBase', 'glBindBufferRange',
    'glBindFramebuffer', 'glBindSampler',
    'glStencilFunc', 'glStencilFuncSeparate',
    'glStencilOp', 'glStencilOpSeparate',
    'glStencilMask', 'glStencilMaskSeparate',
    'glDepthFunc', 'glDepthMask', 'glDepthRangef',
    'glCullFace', 'glFrontFace',
    'glBlendFunc', 'glBlendFuncSeparate', 'glBlendFunci', 'glBlendFuncSeparatei',
    'glBlendEquation', 'glBlendEquationSeparate',
    'glBlendEquationi', 'glBlendEquationSeparatei',
    'glColorMask', 'glColorMaski',
    'glViewport', 'glScissor', 'glPolygonOffset',
    'glPushGroupMarkerEXT', 'glPopGroupMarkerEXT',
}


def _build_state_change_rows(sd, parent_by_event, chunk_name_by_event,
                              chunk_to_event_id, ctx) -> list[dict]:
    """Walk sd.chunks once, emit one row per state-change chunk.

    chunk_to_event_id maps each chunk index to the event_id of the action
    whose api-events list includes it. Built during action tree walk.
    """
    rows: list[dict] = []

    chunks = getattr(sd, 'chunks', None)
    if chunks is None:
        return rows

    for ci, c in enumerate(chunks):
        name = c.name if hasattr(c, 'name') else ''
        if name not in STATE_CHANGE_CHUNK_NAMES:
            continue
        ev_id = chunk_to_event_id.get(ci, -1)
        parent = parent_by_event.get(ev_id, '') if ev_id >= 0 else ''
        # Args are too varied to fully decode; emit best-effort blob.
        arg_id = 0
        arg_int = 0
        arg_float = 0.0
        target_or_cap = ''
        args_repr: list = []
        try:
            for a in getattr(c, 'args', []) or []:
                args_repr.append(str(a))
        except Exception:
            pass
        rows.append({
            **ctx,
            'event_id': ev_id,
            'parent_marker_path': parent,
            'call_name': name,
            'target_or_cap': target_or_cap,
            'arg_id': arg_id,
            'arg_int': arg_int,
            'arg_float': arg_float,
            'arg_extra_json': json.dumps(args_repr) if args_repr else '',
        })
    return rows


# --- Passes (markers aggregation) -------------------------------------------

def _build_passes(events: list[dict], event_durations: dict[int, float], ctx,
                  draws_by_event: dict[int, dict] | None = None,
                  bindings_by_event: dict[int, list] | None = None) -> list[dict]:
    """Aggregate per-marker_path stats. Populates unique_programs/shaders/
    meshes/materials sets when draws_by_event + bindings_by_event are passed.
    """
    draws_by_event = draws_by_event or {}
    bindings_by_event = bindings_by_event or {}
    passes: dict[tuple[int, str], dict] = {}

    for e in events:
        if e['is_marker_push'] or e['is_marker_pop']:
            continue
        path = e['parent_marker_path']
        if not path:
            continue
        ev = e['event_id']
        gpu = event_durations.get(ev, 0.0)
        is_draw = e['is_drawcall']; is_disp = e['is_dispatch']; is_clr = e['is_clear']
        d_row = draws_by_event.get(ev) if is_draw else None

        # contribute to every prefix path
        parts = path.split('/')
        for d in range(1, len(parts) + 1):
            sub = '/'.join(parts[:d])
            key = (d - 1, sub)
            p = passes.get(key)
            if p is None:
                p = {
                    'marker_path': sub, 'depth': d - 1,
                    'first_event_id': ev, 'last_event_id': ev,
                    'num_draws': 0, 'num_dispatches': 0,
                    'num_clears': 0, 'num_other_actions': 0,
                    'num_primitives_pre_vs': 0, 'num_primitives_post_vs': 0,
                    'num_vertices_pre_vs': 0, 'num_vertices_post_vs': 0,
                    'gpu_duration_s': 0.0,
                    'unique_programs': set(), 'unique_shaders': set(),
                    'unique_meshes': set(), 'unique_materials': set(),
                    'color_rt_id_first': 0, 'depth_rt_id_first': 0,
                    'draws_by_class_opaque': 0, 'draws_by_class_prepass': 0,
                    'draws_by_class_translucent': 0, 'draws_by_class_decal': 0,
                    'draws_by_class_shadow': 0, 'draws_by_class_ui': 0,
                    'draws_by_class_postprocess': 0, 'draws_by_class_additive': 0,
                    'draws_by_class_other': 0,
                }
                if e.get('output_color_rt_id'):
                    p['color_rt_id_first'] = e['output_color_rt_id']
                if e.get('output_depth_rt_id'):
                    p['depth_rt_id_first'] = e['output_depth_rt_id']
                passes[key] = p
            p['last_event_id'] = ev
            p['gpu_duration_s'] += gpu

            if is_draw:
                p['num_draws'] += 1
                ni = e['num_indices']; ic = e['num_instances'] or 1
                p['num_vertices_pre_vs'] += ni * ic
                p['num_primitives_pre_vs'] += (ni // 3) * ic
                # draws_by_class_* stay at their zero-init (dead/unread; host derives the live
                # per-class counts in pass_class_breakdown — c09, D-6).
                if d_row is not None:
                    pid = d_row.get('program_id') or 0
                    vs = d_row.get('vs_shader_id') or 0
                    fs = d_row.get('fs_shader_id') or 0
                    mh = d_row.get('mesh_hash') or ''
                    if pid: p['unique_programs'].add(pid)
                    if vs: p['unique_shaders'].add(vs)
                    if fs: p['unique_shaders'].add(fs)
                    if mh: p['unique_meshes'].add(mh)
                    # material identity = (program_id, sorted texture binding resource_ids)
                    tex_ids = []
                    for b in bindings_by_event.get(ev, ()):
                        if b.get('slot_kind') == 'texture' and b.get('resource_id'):
                            tex_ids.append(b['resource_id'])
                    p['unique_materials'].add((pid, tuple(sorted(tex_ids))))
            elif is_disp:
                p['num_dispatches'] += 1
            elif is_clr:
                p['num_clears'] += 1
            else:
                p['num_other_actions'] += 1

    # finalize: convert sets to ints
    rows: list[dict] = []
    for (_, _path), p in sorted(passes.items(), key=lambda kv: (kv[0][0], kv[0][1])):
        rows.append({
            **ctx,
            **{k: (len(v) if isinstance(v, set) else v) for k, v in p.items()},
        })
    return rows


# --- Frame totals -----------------------------------------------------------

def _build_frame_totals(events: list[dict], draws: list[dict],
                        event_durations: dict[int, float],
                        unique_programs_used: set, unique_shaders_used: set,
                        unique_textures_bound: set, ctx,
                        sc_rows: list[dict] | None = None,
                        bindings_by_event: dict[int, list] | None = None,
                        buffers_rows: list[dict] | None = None,
                        textures_rows: list[dict] | None = None) -> dict:
    sc_rows = sc_rows or []
    bindings_by_event = bindings_by_event or {}
    buffers_rows = buffers_rows or []
    textures_rows = textures_rows or []

    n_draws = sum(1 for e in events if e['is_drawcall'])
    n_disp = sum(1 for e in events if e['is_dispatch'])
    n_clr = sum(1 for e in events if e['is_clear'])

    total_pre_vs_vertices = 0
    total_pre_vs_primitives = 0
    total_post_vs_vertices = 0
    total_post_vs_primitives = 0
    for d in draws:
        ic = d['num_instances'] or 1
        total_pre_vs_vertices += d['num_indices'] * ic
        total_pre_vs_primitives += _primitives_for(d['topology'], d['num_indices'], ic)
        total_post_vs_vertices += d['post_vs_vertices']
        total_post_vs_primitives += d['post_vs_primitives']

    total_gpu = sum(event_durations.values())

    # State change call counts
    call_counts: dict[str, int] = {}
    for r in sc_rows:
        nm = r.get('call_name', '')
        call_counts[nm] = call_counts.get(nm, 0) + 1
    # Add draw-call chunk names (action tree gives is_drawcall, but for counts
    # we tally by chunk_name).
    for e in events:
        cn = e.get('chunk_name', '')
        if cn in ('glDrawElements', 'glDrawArrays', 'glDrawElementsInstanced',
                  'glDispatchCompute', 'glClear', 'glClearBufferfv',
                  'glClearBufferfi', 'glClearBufferiv', 'glClearBufferuiv'):
            call_counts[cn] = call_counts.get(cn, 0) + 1
    gl_clear_buffer_count = (call_counts.get('glClearBufferfv', 0)
                              + call_counts.get('glClearBufferfi', 0)
                              + call_counts.get('glClearBufferiv', 0)
                              + call_counts.get('glClearBufferuiv', 0))

    # Switches by walking draws/events in event_id order
    sorted_draws = sorted(draws, key=lambda d: d['event_id'])
    program_switches = 0
    prev_prog = None
    for d in sorted_draws:
        pid = d.get('program_id') or 0
        if prev_prog is not None and pid and pid != prev_prog:
            program_switches += 1
        if pid: prev_prog = pid
    fbo_switches = 0
    prev_rt = None
    for e in sorted(events, key=lambda x: x['event_id']):
        rt = e.get('output_color_rt_id') or 0
        if prev_rt is not None and rt and rt != prev_rt:
            fbo_switches += 1
        if rt: prev_rt = rt
    texture_unit_switches = call_counts.get('glActiveTexture', 0)

    # Unique mesh + material from draws / bindings
    unique_meshes_drawn = len({d.get('mesh_hash') for d in draws if d.get('mesh_hash')})
    materials: set = set()
    for d in draws:
        pid = d.get('program_id') or 0
        ev = d['event_id']
        tex_ids = tuple(sorted(
            b['resource_id'] for b in bindings_by_event.get(ev, ())
            if b.get('slot_kind') == 'texture' and b.get('resource_id')
        ))
        materials.add((pid, tex_ids))
    unique_materials_drawn = len(materials)

    # Bytes totals from buffers + textures
    total_vbo = sum(r.get('allocated_size_bytes', 0) for r in buffers_rows if r.get('used_as_vbo'))
    total_ibo = sum(r.get('allocated_size_bytes', 0) for r in buffers_rows if r.get('used_as_ibo'))
    total_ubo = sum(r.get('allocated_size_bytes', 0) for r in buffers_rows if r.get('used_as_ubo'))
    total_tex_bytes = sum(r.get('est_bytes', 0) or 0 for r in textures_rows)

    return {
        **ctx,
        'n_events': len(events),
        'n_draws': n_draws, 'n_dispatches': n_disp, 'n_clears': n_clr,
        'total_primitives_pre_vs': total_pre_vs_primitives,
        'total_vertices_pre_vs': total_pre_vs_vertices,
        'total_primitives_post_vs': total_post_vs_primitives,
        'total_vertices_post_vs': total_post_vs_vertices,
        'total_gpu_duration_s': total_gpu,
        'glUseProgram_count': call_counts.get('glUseProgram', 0),
        'glBindBuffer_count': call_counts.get('glBindBuffer', 0),
        'glBindTexture_count': call_counts.get('glBindTexture', 0),
        'glActiveTexture_count': call_counts.get('glActiveTexture', 0),
        'glBindFramebuffer_count': call_counts.get('glBindFramebuffer', 0),
        'glBindBufferBase_count': call_counts.get('glBindBufferBase', 0),
        'glBindSampler_count': call_counts.get('glBindSampler', 0),
        'glDrawElements_count': call_counts.get('glDrawElements', 0),
        'glDrawArrays_count': call_counts.get('glDrawArrays', 0),
        'glDrawElementsInstanced_count': call_counts.get('glDrawElementsInstanced', 0),
        'glDispatchCompute_count': call_counts.get('glDispatchCompute', 0),
        'glClear_count': call_counts.get('glClear', 0),
        'glClearBuffer_count': gl_clear_buffer_count,
        'total_vbo_bytes_uploaded': total_vbo,
        'total_ibo_bytes_uploaded': total_ibo,
        'total_ubo_bytes_uploaded': total_ubo,
        'total_texture_bytes_allocated': total_tex_bytes,
        'total_renderbuffer_bytes_allocated': 0,
        'unique_programs_used': len(unique_programs_used),
        'unique_shaders_used': len(unique_shaders_used),
        'unique_meshes_drawn': unique_meshes_drawn,
        'unique_materials_drawn': unique_materials_drawn,
        'unique_textures_bound': len(unique_textures_bound),
        'fbo_switches': fbo_switches,
        'program_switches': program_switches,
        'texture_unit_switches': texture_unit_switches,
    }


# --- Frame metadata ---------------------------------------------------------

def _frame_metadata(ctrl, ctx, rdc_path: str, sd=None) -> dict:
    md = dict(ctx)
    try:
        api = ctrl.GetAPIProperties()
        md['driver_name'] = _enum_short(api.driver) if hasattr(api, 'driver') else ''
        md['gpu_vendor'] = _enum_short(getattr(api, 'vendor', ''))
        md['gpu_description'] = getattr(api, 'description', '') or ''
    except Exception:
        pass
    try:
        fi = ctrl.GetFrameInfo()
        md['frame_number'] = int(getattr(fi, 'frameNumber', 0))
        md['capture_time_us'] = int(getattr(fi, 'captureTime', 0))
        md['file_size_bytes'] = int(getattr(fi, 'fileSize', 0))
    except Exception:
        pass
    md['rdc_file_bytes'] = os.path.getsize(rdc_path)
    # Probe Internal::Driver Initialisation Parameters chunk for GL_VERSION/RENDERER + format details
    md['gl_version_string'] = ''
    md['gl_renderer_string'] = ''
    md['init_color_bits'] = 0
    md['init_depth_bits'] = 0
    md['init_stencil_bits'] = 0
    md['init_multi_samples'] = 0
    md['init_width'] = 0
    md['init_height'] = 0
    md['init_is_srgb'] = 0
    if sd is not None:
        try:
            for c in sd.chunks:
                if c.name != 'Internal::Driver Initialisation Parameters':
                    continue
                params = c.FindChild('InitParams')
                src = params if params is not None else c
                def _get_str(name):
                    ch = src.FindChild(name)
                    try: return ch.AsString() if ch is not None else ''
                    except Exception: return ''
                def _get_int(name):
                    ch = src.FindChild(name)
                    try: return int(ch.AsInt()) if ch is not None else 0
                    except Exception: return 0
                md['gl_renderer_string'] = _get_str('renderer')
                md['gl_version_string']  = _get_str('version')
                md['init_color_bits']    = _get_int('colorBits')
                md['init_depth_bits']    = _get_int('depthBits')
                md['init_stencil_bits']  = _get_int('stencilBits')
                md['init_multi_samples'] = _get_int('multiSamples')
                md['init_width']         = _get_int('width')
                md['init_height']        = _get_int('height')
                md['init_is_srgb']       = _get_int('isSRGB')
                break
        except Exception:
            pass
    return md


# --- Writers ----------------------------------------------------------------

def _write_rows(path: str, fields: tuple, rows: list[dict]) -> int:
    with open(path, 'w', encoding='utf-8', newline='') as f:
        w = csv.DictWriter(f, fieldnames=list(fields), extrasaction='ignore')
        w.writeheader()
        for r in rows:
            w.writerow(r)
    return len(rows)


# --- Main --------------------------------------------------------------------

def main() -> None:
    args = _parse_args()
    capture_stage = os.path.join(args['stage_root'], args['capture'])
    log = _tee_setup(capture_stage)

    try:
        rdc_path = os.path.join(args['drop_dir'], f"{args['capture']}.rdc")
        if not os.path.exists(rdc_path):
            raise FileNotFoundError(rdc_path)
        print(f'opening {rdc_path}')
        ctx = {k: args[k] for k in ID_COLS}

        cap, ctrl = _open_capture(rdc_path)
        try:
            sd = ctrl.GetStructuredFile()

            t0 = time.monotonic()
            tree = _build_event_records(ctrl, sd, ctx)
            print(f'  walked action tree: {len(tree["events"])} events, {len(tree["draw_events"])} draws ({time.monotonic()-t0:.1f}s)')

            global _ACTION_CACHE
            _ACTION_CACHE = tree['action_by_event']

            t0 = time.monotonic()
            counter_rows, event_durations = _fetch_counters_per_event(ctrl, ctx)
            print(f'  fetched counters: {len(counter_rows)} rows ({time.monotonic()-t0:.1f}s)')

            t0 = time.monotonic()
            draws: list[dict] = []
            db_rows: list[dict] = []
            vi_rows: list[dict] = []
            da_rows: list[dict] = []
            pvs_rows: list[dict] = []
            fbo_state_per_event: dict[int, list[dict]] = {}
            uniforms_per_pass_rows: list[dict] = []
            seen_marker_paths: set = set()
            mesh_hash_cache: dict = {}
            buffer_map: dict = {_rid_int(b.resourceId): b for b in ctrl.GetBuffers()}
            unique_programs = set(); unique_shaders = set(); unique_textures = set()
            n_draws_total = len(tree['draw_events'])
            for i, e in enumerate(tree['draw_events']):
                ev_id = e['event_id']
                parent = tree['parent_path_by_event'].get(ev_id, '')
                try:
                    row = _read_draw_state(ctrl, ev_id, e, parent, event_durations)
                except Exception as ex:
                    print(f'    draw {ev_id} failed: {ex}')
                    continue
                draws.append(row)
                # aux per-draw extraction (re-uses the SetFrameEvent already done)
                try:
                    _extract_draw_aux(ctrl, ev_id, ctx, row,
                                      vi_rows, db_rows, da_rows, pvs_rows,
                                      fbo_state_per_event, mesh_hash_cache, buffer_map,
                                      pvs_max_verts=32)
                except Exception as ex:
                    print(f'    draw {ev_id} aux failed: {ex}')
                # First-draw-per-marker uniforms snapshot
                if parent and parent not in seen_marker_paths:
                    seen_marker_paths.add(parent)
                    try:
                        u_obj = _snapshot_uniforms(ctrl, ev_id, parent, ctx)
                        if u_obj is not None:
                            uniforms_per_pass_rows.append(u_obj)
                    except Exception as ex:
                        print(f'    uniforms {ev_id} failed: {ex}')
                if row['program_id']: unique_programs.add(row['program_id'])
                if row['vs_shader_id']: unique_shaders.add(row['vs_shader_id'])
                if row['fs_shader_id']: unique_shaders.add(row['fs_shader_id'])
                # Tally textures seen across draws
                for db in db_rows[-12:]:  # cheap window; not exact but fast
                    if db['slot_kind'] == 'texture' and db['resource_id']:
                        unique_textures.add(db['resource_id'])
                if (i + 1) % 500 == 0:
                    print(f'    draws: {i+1}/{n_draws_total}')
            print(f'  read draw states: {len(draws)} rows ({time.monotonic()-t0:.1f}s)')
            print(f'  per-draw aux: bindings={len(db_rows)} vertex_inputs={len(vi_rows)} descriptor_access={len(da_rows)} post_vs_samples={len(pvs_rows)}')

            # On Arm RD's GLES backend the per-stage GetReadOnlyResources()
            # returns empty arrays — resources are reached via the descriptor
            # store, and only GetDescriptorAccess() yields the actually-used
            # bindings. To keep draw_bindings populated, project from
            # descriptor_access. The columns differ slightly but both describe
            # "what this draw touched."
            _KIND_TO_SLOT = {
                'ReadOnlyResource': 'texture',
                'ImageSampler': 'texture',   # Arm RD GLES: combined tex+sampler
                'TypedBuffer': 'texture',    # texture buffer object
                'ReadWriteResource': 'ssbo',
                'ReadWriteBuffer': 'ssbo',
                'Sampler': 'sampler',
                'ConstantBuffer': 'ubo',
            }
            for da in da_rows:
                slot_kind = _KIND_TO_SLOT.get(da['descriptor_kind'], da['descriptor_kind'].lower())
                db_rows.append({
                    **{k: da[k] for k in ID_COLS},
                    'event_id': da['event_id'],
                    'slot_kind': slot_kind,
                    'slot_index': da['slot_index'],
                    'resource_id': da['resource_id'] if slot_kind != 'sampler' else 0,
                    'sampler_id': da['resource_id'] if slot_kind == 'sampler' else 0,
                    'offset': da['byte_offset'],
                    'size': da['byte_size'],
                    'stride': 0,
                })

            t0 = time.monotonic()
            clears = _extract_clears(sd, tree['events'], tree['action_by_event'], ctx)
            dispatches = _extract_dispatches(ctrl, tree['events'], event_durations, ctx)
            print(f'  clears={len(clears)} dispatches={len(dispatches)} ({time.monotonic()-t0:.1f}s)')

            # Sample VBOs + IBOs that draws actually used
            used_vbo_ids: set = set()
            used_ibo_ids: set = set()
            for vi in vi_rows:
                if vi['buffer_id']:
                    used_vbo_ids.add(vi['buffer_id'])
            for d in draws:
                if d['ibo_id']:
                    used_ibo_ids.add(d['ibo_id'])
            t0 = time.monotonic()
            vbo_samples = _sample_vbos(ctrl, used_vbo_ids, ctx)
            ibo_samples = _sample_ibos(ctrl, used_ibo_ids, ctx)
            print(f'  sampled VBOs={len(used_vbo_ids)}->{len(vbo_samples)} rows '
                  f'IBOs={len(used_ibo_ids)}->{len(ibo_samples)} rows ({time.monotonic()-t0:.1f}s)')

            t0 = time.monotonic()
            texture_samples = _sample_textures(ctrl, ctx)
            print(f'  sampled small textures: {len(texture_samples)} rows ({time.monotonic()-t0:.1f}s)')

            t0 = time.monotonic()
            rt_rows, timeline_rows, histogram_by_rt = _walk_render_targets(ctrl, ctx)
            print(f'  walked RTs: {len(rt_rows)} rts, {len(timeline_rows)} timeline rows, {len(histogram_by_rt)} histograms ({time.monotonic()-t0:.1f}s)')

            # Write histograms as sidecar JSON files
            hist_dir = os.path.join(capture_stage, 'histogram')
            os.makedirs(hist_dir, exist_ok=True)
            for rt_id, buckets in histogram_by_rt.items():
                with open(os.path.join(hist_dir, f'{rt_id}.json'), 'w', encoding='utf-8') as f:
                    json.dump({'rt_id': rt_id, 'buckets': buckets}, f)

            t0 = time.monotonic()
            sc_rows = _build_state_change_rows(sd, tree['parent_path_by_event'],
                                               tree['chunk_name_by_event'],
                                               tree['chunk_to_event_id'], ctx)
            print(f'  state change chunks: {len(sc_rows)} rows ({time.monotonic()-t0:.1f}s)')

            # Indices for passes/frame_totals: per-event lookups
            draws_by_event = {d['event_id']: d for d in draws}
            bindings_by_event: dict[int, list] = {}
            for b in db_rows:
                bindings_by_event.setdefault(b['event_id'], []).append(b)

            t0 = time.monotonic()
            passes = _build_passes(tree['events'], event_durations, ctx,
                                   draws_by_event=draws_by_event,
                                   bindings_by_event=bindings_by_event)
            print(f'  passes: {len(passes)} ({time.monotonic()-t0:.1f}s)')

            # FBO inventory from per-draw state
            labels: dict[int, str] = {}
            labels_path = os.path.join(capture_stage, 'labels.json')
            if os.path.exists(labels_path):
                try:
                    with open(labels_path, 'r', encoding='utf-8') as f:
                        labels = {int(k): v for k, v in json.load(f).items()}
                except Exception:
                    pass
            t0 = time.monotonic()
            fbo_rows = _build_fbo_rows(ctrl, fbo_state_per_event, labels, ctx)
            print(f'  fbos: {len(fbo_rows)} rows ({time.monotonic()-t0:.1f}s)')

            # Indirect args
            t0 = time.monotonic()
            indirect_rows = _extract_indirect_args(ctrl, tree['events'], ctx)
            print(f'  indirect_args: {len(indirect_rows)} rows ({time.monotonic()-t0:.1f}s)')

            # Pixel history at last event
            last_ev = max((e['event_id'] for e in tree['events']), default=0)
            try:
                ctrl.SetFrameEvent(last_ev, False)
            except Exception:
                pass
            t0 = time.monotonic()
            # BOBFRAMES_PIXEL_GRID is set by the host; RDC_PIXEL_GRID kept one release for a
            # standalone old caller (c10 rename; cannot import the host config helper here, H-6).
            pixel_history = _extract_pixel_history(ctrl, ctx, last_ev,
                                                   grid=int(os.environ.get('BOBFRAMES_PIXEL_GRID')
                                                            or os.environ.get('RDC_PIXEL_GRID', '4')))
            print(f'  pixel_history: {len(pixel_history)} rows ({time.monotonic()-t0:.1f}s)')

            totals = _build_frame_totals(
                tree['events'], draws, event_durations,
                unique_programs, unique_shaders, unique_textures, ctx,
                sc_rows=sc_rows,
                bindings_by_event=bindings_by_event,
                buffers_rows=[],  # parser owns buffers.csv; aggregates via derive_post_merge
                textures_rows=rt_rows,  # RTs are textures with est_bytes after derive
            )

            md = _frame_metadata(ctrl, ctx, rdc_path, sd=sd)

            # --- write outputs ---
            print('writing CSVs')
            n_events = _write_rows(os.path.join(capture_stage, 'events.csv'), EVENTS_COLS, tree['events'])
            n_draws_w = _write_rows(os.path.join(capture_stage, 'draws.csv'), DRAWS_COLS, draws)
            n_db = _write_rows(os.path.join(capture_stage, 'draw_bindings.csv'), DRAW_BINDINGS_COLS, db_rows)
            n_vi = _write_rows(os.path.join(capture_stage, 'vertex_inputs.csv'), VERTEX_INPUTS_COLS, vi_rows)
            n_da = _write_rows(os.path.join(capture_stage, 'descriptor_access.csv'), DESCRIPTOR_ACCESS_COLS, da_rows)
            n_pvs = _write_rows(os.path.join(capture_stage, 'post_vs_samples.csv'), POST_VS_SAMPLES_COLS, pvs_rows)
            n_cl = _write_rows(os.path.join(capture_stage, 'clears.csv'), CLEARS_COLS, clears)
            n_disp = _write_rows(os.path.join(capture_stage, 'dispatches.csv'), DISPATCHES_COLS, dispatches)
            n_vbo = _write_rows(os.path.join(capture_stage, 'vbo_samples.csv'), VBO_SAMPLES_COLS, vbo_samples)
            n_ibo = _write_rows(os.path.join(capture_stage, 'ibo_samples.csv'), IBO_SAMPLES_COLS, ibo_samples)
            n_ts = _write_rows(os.path.join(capture_stage, 'texture_samples.csv'), TEXTURE_SAMPLES_COLS, texture_samples)
            n_rt = _write_rows(os.path.join(capture_stage, 'render_targets.csv'), RT_COLS, rt_rows)
            n_tl = _write_rows(os.path.join(capture_stage, 'rt_event_timeline.csv'), RT_TIMELINE_COLS, timeline_rows)
            n_ctr = _write_rows(os.path.join(capture_stage, 'counters_per_event.csv'), COUNTERS_COLS, counter_rows)
            n_sc = _write_rows(os.path.join(capture_stage, 'state_change_events.csv'), STATE_CHANGE_COLS, sc_rows)
            n_p = _write_rows(os.path.join(capture_stage, 'passes.csv'), PASSES_COLS, passes)
            n_fbo = _write_rows(os.path.join(capture_stage, 'fbos.csv'), FBOS_COLS, fbo_rows)
            n_ind = _write_rows(os.path.join(capture_stage, 'indirect_args.csv'), INDIRECT_ARGS_COLS, indirect_rows)
            n_ph = _write_rows(os.path.join(capture_stage, 'pixel_history.csv'), PIXEL_HISTORY_COLS, pixel_history)
            totals['unique_textures_bound'] = len(unique_textures)
            n_ft = _write_rows(os.path.join(capture_stage, 'frame_totals.csv'), FRAME_TOTALS_COLS, [totals])

            with open(os.path.join(capture_stage, 'frame_metadata.json'), 'w', encoding='utf-8') as f:
                json.dump(md, f, indent=2)

            with open(os.path.join(capture_stage, 'uniforms_per_pass.jsonl'), 'w', encoding='utf-8') as f:
                for u in uniforms_per_pass_rows:
                    f.write(json.dumps(u))
                    f.write('\n')

            print(f'wrote events={n_events} draws={n_draws_w} bindings={n_db} vinputs={n_vi}'
                  f' desc_access={n_da} post_vs={n_pvs} clears={n_cl} disp={n_disp}'
                  f' rt={n_rt} timeline={n_tl} counters={n_ctr} state_change={n_sc}'
                  f' passes={n_p} fbos={n_fbo} indirect={n_ind} pixel_history={n_ph}'
                  f' uniforms_passes={len(uniforms_per_pass_rows)} totals={n_ft}')

        finally:
            try: ctrl.Shutdown()
            except Exception: pass
            try: cap.Shutdown()
            except Exception: pass

        print('done')
    except Exception:
        traceback.print_exc()
        try: log.flush(); log.close()
        except Exception: pass
        os._exit(1)

    try: log.flush(); log.close()
    except Exception: pass
    os._exit(0)


if __name__ == '__main__':
    main()
