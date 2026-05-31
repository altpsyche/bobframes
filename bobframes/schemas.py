"""Single source of truth for table schemas.

Every fat table's column tuple lives here. Writers and readers import these
constants. SCHEMA_VERSION bumps on any column add/remove/rename.
"""

from typing import NamedTuple

SCHEMA_VERSION = 3

ID_COLS = ('area', 'drop_date', 'drop_label', 'capture')


class TableSpec(NamedTuple):
    """One row of the master table registry (single source of truth).

    `category` drives the per-drop browser grouping (was html/template._CATEGORY_MAP).
    `api` is reserved for the v0.5 graphics-API epic (c33): "core" applies to every API;
    "gl"/"vk" tag per-API extension tables. NamedTuple stays index-compatible, so legacy
    positional reads (`TABLES[stem][0]`) keep working during migration.
    """
    cols: tuple
    size_class: str
    is_entity: bool
    category: str
    api: str = "core"


# --- Entity tables (carry stable_key after ID_COLS) ---

SHADERS_COLS = ID_COLS + (
    'stable_key',
    'shader_id', 'shader_type', 'src_len', 'src_hash',
    'linked_program_ids', 'used_by_draw_count',
    'total_texture_samples', 'total_branches', 'total_loops', 'total_discards',
    'total_dfdx_dfdy', 'total_mat4_constructors', 'total_varyings',
    'mediump_decls', 'highp_decls', 'lowp_decls',
    'fb_fetch', 'uses_cubemap', 'uses_texture_gather', 'uses_texture_grad',
    'src_file_path',
    'complexity_score',
)

TEXTURES_COLS = ID_COLS + (
    'stable_key',
    'tex_id', 'format', 'width', 'height', 'depth', 'mip_levels', 'sample_count', 'kind',
    'est_bytes', 'is_rt', 'is_swap_chain', 'label',
    'created_at_event', 'num_bind_events', 'num_sample_events',
    'sampled_by_shader_ids', 'attached_to_fbo_ids',
)

RENDER_TARGETS_COLS = ID_COLS + (
    'stable_key',
    'rt_id', 'format', 'width', 'height', 'depth', 'mip_levels', 'sample_count',
    'is_color', 'is_depth', 'is_stencil', 'is_swap_chain_target',
    'first_write_event', 'last_write_event', 'first_read_event', 'last_read_event',
    'num_write_events', 'num_read_events',
    'attached_to_fbo_ids', 'sampled_by_shader_ids',
    'min_value_r', 'min_value_g', 'min_value_b', 'min_value_a',
    'max_value_r', 'max_value_g', 'max_value_b', 'max_value_a',
)

BUFFERS_COLS = ID_COLS + (
    'stable_key',
    'buffer_id', 'allocated_size_bytes', 'usage_hint', 'target_history',
    'first_alloc_event', 'last_alloc_event', 'first_bind_event', 'last_bind_event',
    'num_glBufferData', 'num_glBufferSubData', 'num_glBindBuffer',
    'num_glBindBufferBase', 'num_glBindBufferRange',
    'used_by_draws', 'used_as_vbo', 'used_as_ibo', 'used_as_ubo',
    'used_as_ssbo', 'used_as_indirect',
)

PROGRAMS_COLS = ID_COLS + (
    'stable_key',
    'program_id', 'linked', 'num_attached_shaders', 'attached_shader_ids',
    'vs_shader_id', 'fs_shader_id', 'cs_shader_id',
    'gs_shader_id', 'tcs_shader_id', 'tes_shader_id',
    'num_active_uniforms', 'num_active_uniform_blocks', 'num_active_attributes',
    'used_by_draw_count', 'label',
)

SAMPLERS_COLS = ID_COLS + (
    'stable_key',
    'sampler_id', 'min_filter', 'mag_filter',
    'wrap_s', 'wrap_t', 'wrap_r',
    'mip_min_lod', 'mip_max_lod', 'mip_lod_bias',
    'max_anisotropy', 'compare_mode', 'compare_func',
    'border_color_r', 'border_color_g', 'border_color_b', 'border_color_a',
    'created_at_event', 'bound_to_draw_count', 'label',
)

FBOS_COLS = ID_COLS + (
    'stable_key',
    'fbo_id', 'attachment_point', 'kind', 'resource_id', 'format',
    'width', 'height', 'sample_count',
    'mip_level', 'layer', 'created_at_event', 'bound_at_events',
    'num_clears', 'num_writes', 'num_reads', 'label',
)


# --- Non-entity tables (no stable_key) ---

DRAWS_COLS = ID_COLS + (
    'event_id', 'parent_pass_path', 'parent_pass_path_norm', 'draw_name', 'draw_class',
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

DRAW_BINDINGS_COLS = ID_COLS + (
    'event_id', 'slot_kind', 'slot_index', 'resource_id', 'sampler_id',
    'offset', 'size', 'stride',
)

PASSES_COLS = ID_COLS + (
    'marker_path', 'marker_path_norm', 'depth', 'first_event_id', 'last_event_id',
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

EVENTS_COLS = ID_COLS + (
    'event_id', 'parent_marker_path', 'parent_marker_path_norm', 'chunk_name', 'depth',
    'is_drawcall', 'is_dispatch', 'is_clear', 'is_copy', 'is_resolve',
    'is_marker_push', 'is_marker_pop', 'is_set_state',
    'num_indices', 'num_instances',
    'dispatch_x', 'dispatch_y', 'dispatch_z',
    'output_color_rt_id', 'output_depth_rt_id',
    'copy_source_id', 'copy_destination_id',
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

STATE_CHANGE_COLS = ID_COLS + (
    'event_id', 'parent_marker_path', 'call_name',
    'target_or_cap', 'arg_id', 'arg_int', 'arg_float', 'arg_extra_json',
)

INDIRECT_ARGS_COLS = ID_COLS + (
    'event_id', 'call_name', 'indirect_buffer_id', 'offset',
    'count', 'instance_count', 'first', 'base_vertex', 'base_instance',
    'group_x', 'group_y', 'group_z', 'stride', 'draw_count',
)

VERTEX_INPUTS_COLS = ID_COLS + (
    'event_id', 'attribute_index', 'attribute_name', 'enabled',
    'component_count', 'component_type', 'normalized', 'integer',
    'stride_bytes', 'offset_bytes', 'buffer_id', 'vbo_slot',
    'divisor',
)

RESOURCE_CREATION_COLS = ID_COLS + (
    'resource_id', 'resource_kind', 'created_at_event', 'creation_chunk', 'declared_label',
)

COUNTERS_COLS = ID_COLS + (
    'event_id', 'counter_name', 'counter_unit', 'value_double', 'value_uint64',
)

DESCRIPTOR_ACCESS_COLS = ID_COLS + (
    'event_id', 'descriptor_kind', 'slot_index', 'resource_id', 'view_id',
    'byte_offset', 'byte_size', 'access_type',
)

RT_TIMELINE_COLS = ID_COLS + (
    'rt_id', 'event_id', 'usage_code', 'usage_name', 'view_id',
    'attachment_point_or_slot',
)

PROG_TRANS_COLS = ID_COLS + (
    'from_program_id', 'to_program_id', 'count',
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

PASS_CLASS_BREAKDOWN_COLS = ID_COLS + (
    'marker_path_norm', 'draw_class',
    'n_draws', 'n_dispatches',
    'sum_pre_vs_vertices', 'sum_gpu_duration_s',
)

TEXTURE_USAGE_COLS = ID_COLS + (
    'tex_id', 'stable_key', 'label', 'format',
    'n_unique_events_sampled', 'n_descriptor_accesses',
    'first_event_id', 'last_event_id',
)


# Master table registry: file stem -> TableSpec(cols, size_class, is_entity, category, api).
# Key order is THE canonical table order — it drives catalog._CATALOG_TABLE_KEYS (and the catalog
# parquet/json column order baked into the golden root index.html), so it must stay byte-stable.
# `category` here replaces html/template._CATEGORY_MAP (H-11); the within-category *display* order is
# a separate presentation concern kept in template._TABLE_DISPLAY_ORDER.
TABLES = {
    'draws':                  TableSpec(DRAWS_COLS,              'large', False, 'actions'),
    'events':                 TableSpec(EVENTS_COLS,             'large', False, 'actions'),
    'shaders':                TableSpec(SHADERS_COLS,            'small', True,  'entities'),
    'textures':               TableSpec(TEXTURES_COLS,           'small', True,  'entities'),
    'render_targets':         TableSpec(RENDER_TARGETS_COLS,     'small', True,  'entities'),
    'buffers':                TableSpec(BUFFERS_COLS,            'small', True,  'entities'),
    'programs':               TableSpec(PROGRAMS_COLS,           'small', True,  'entities'),
    'samplers':               TableSpec(SAMPLERS_COLS,           'small', True,  'entities'),
    'fbos':                   TableSpec(FBOS_COLS,               'small', True,  'entities'),
    'state_change_events':    TableSpec(STATE_CHANGE_COLS,       'large', False, 'actions'),
    'counters_per_event':     TableSpec(COUNTERS_COLS,           'large', False, 'actions'),
    'descriptor_access':      TableSpec(DESCRIPTOR_ACCESS_COLS,  'large', False, 'actions'),
    'passes':                 TableSpec(PASSES_COLS,             'small', False, 'aggregates'),
    'frame_totals':           TableSpec(FRAME_TOTALS_COLS,       'small', False, 'aggregates'),
    'clears':                 TableSpec(CLEARS_COLS,             'small', False, 'actions'),
    'dispatches':             TableSpec(DISPATCHES_COLS,         'small', False, 'actions'),
    'rt_event_timeline':      TableSpec(RT_TIMELINE_COLS,        'large', False, 'actions'),
    'vertex_inputs':          TableSpec(VERTEX_INPUTS_COLS,      'large', False, 'actions'),
    'resource_creation':      TableSpec(RESOURCE_CREATION_COLS,  'small', False, 'actions'),
    'draw_bindings':          TableSpec(DRAW_BINDINGS_COLS,      'large', False, 'actions'),
    'program_transitions':    TableSpec(PROG_TRANS_COLS,         'small', False, 'actions'),
    'pixel_history':          TableSpec(PIXEL_HISTORY_COLS,      'small', False, 'samples'),
    'vbo_samples':            TableSpec(VBO_SAMPLES_COLS,        'small', False, 'samples'),
    'ibo_samples':            TableSpec(IBO_SAMPLES_COLS,        'small', False, 'samples'),
    'post_vs_samples':        TableSpec(POST_VS_SAMPLES_COLS,    'large', False, 'samples'),
    'texture_samples':        TableSpec(TEXTURE_SAMPLES_COLS,    'small', False, 'samples'),
    'indirect_args':          TableSpec(INDIRECT_ARGS_COLS,      'small', False, 'actions'),
    'pass_class_breakdown':   TableSpec(PASS_CLASS_BREAKDOWN_COLS, 'small', False, 'aggregates'),
    'texture_usage':          TableSpec(TEXTURE_USAGE_COLS,      'small', False, 'aggregates'),
}


# --- dtype inference for parquetize ---

_INT_NAMES = {
    'depth', 'width', 'height', 'mip_levels', 'sample_count',
    'mip_level', 'layer', 'src_len',
    'first_write_event', 'last_write_event', 'first_read_event', 'last_read_event',
    'num_write_events', 'num_read_events',
    'first_alloc_event', 'last_alloc_event', 'first_bind_event', 'last_bind_event',
    'created_at_event', 'used_by_draw_count', 'used_by_draws', 'bound_to_draw_count',
    'allocated_size_bytes', 'est_bytes',
    'num_attached_shaders', 'num_active_uniforms', 'num_active_uniform_blocks',
    'num_active_attributes',
    'event_id', 'first_event_id', 'last_event_id', 'parent_event_id',
    'num_draws', 'num_dispatches', 'num_clears', 'num_other_actions',
    'num_primitives_pre_vs', 'num_primitives_post_vs',
    'num_vertices_pre_vs', 'num_vertices_post_vs',
    'unique_programs', 'unique_shaders', 'unique_meshes', 'unique_materials',
    'unique_textures_bound', 'unique_programs_used', 'unique_shaders_used',
    'unique_meshes_drawn', 'unique_materials_drawn',
    'fbo_switches', 'program_switches', 'texture_unit_switches',
    'num_indices', 'num_instances', 'base_vertex', 'vertex_offset', 'index_offset',
    'viewport_x', 'viewport_y', 'viewport_w', 'viewport_h',
    'scissor_x', 'scissor_y', 'scissor_w', 'scissor_h',
    'stencil_ref', 'stencil_read_mask', 'stencil_write_mask',
    'color_write_mask',
    'post_vs_primitives', 'post_vs_vertices',
    'slot_index', 'attribute_index', 'component_count',
    'stride_bytes', 'offset_bytes', 'divisor',
    'count', 'instance_count', 'first', 'base_instance',
    'group_x', 'group_y', 'group_z', 'stride', 'draw_count',
    'group_count_x', 'group_count_y', 'group_count_z',
    'work_group_size_x', 'work_group_size_y', 'work_group_size_z',
    'total_threads',
    'stencil_value', 'buffer_mask',
    'mod_index', 'primitive_id', 'sample_x', 'sample_y',
    'usage_code', 'byte_offset', 'byte_size',
    'from_program_id', 'to_program_id',
    'n_events', 'n_draws', 'n_dispatches', 'n_clears',
    'total_primitives_pre_vs', 'total_vertices_pre_vs',
    'total_primitives_post_vs', 'total_vertices_post_vs',
    'value_uint64',
    'vertex_index', 'index_position', 'index_value',
    'row_index', 'col_index',
    'as_unorm8_r', 'as_unorm8_g', 'as_unorm8_b', 'as_unorm8_a',
    'total_texture_samples', 'total_branches', 'total_loops', 'total_discards',
    'total_dfdx_dfdy', 'total_mat4_constructors', 'total_varyings',
    'mediump_decls', 'highp_decls', 'lowp_decls',
    'num_bind_events', 'num_sample_events',
    'num_glBufferData', 'num_glBufferSubData', 'num_glBindBuffer',
    'num_glBindBufferBase', 'num_glBindBufferRange',
    'glUseProgram_count', 'glBindBuffer_count', 'glBindTexture_count',
    'glActiveTexture_count', 'glBindFramebuffer_count', 'glBindBufferBase_count',
    'glBindSampler_count', 'glDrawElements_count', 'glDrawArrays_count',
    'glDrawElementsInstanced_count', 'glDispatchCompute_count',
    'glClear_count', 'glClearBuffer_count',
    'total_vbo_bytes_uploaded', 'total_ibo_bytes_uploaded', 'total_ubo_bytes_uploaded',
    'total_texture_bytes_allocated', 'total_renderbuffer_bytes_allocated',
    'num_writes', 'num_reads',
    'arg_int', 'arg_id',
    'max_anisotropy',
    'mip_min_lod', 'mip_max_lod',  # actually float; overridden below
    # resource IDs (per-capture ints; large values OK in int64)
    'shader_id', 'program_id', 'vs_shader_id', 'fs_shader_id', 'cs_shader_id',
    'gs_shader_id', 'tcs_shader_id', 'tes_shader_id',
    'tex_id', 'rt_id', 'buffer_id', 'sampler_id', 'fbo_id',
    'depth_rt_id', 'ibo_id',
    'resource_id', 'view_id',
    'indirect_buffer_id', 'copy_source_id', 'copy_destination_id',
    'output_color_rt_id', 'output_depth_rt_id',
    'created_at_event',
    'est_bytes',
    'screen_coverage_px',
    'n_unique_events_sampled', 'n_descriptor_accesses',
    'first_event_id', 'last_event_id',
    'sum_pre_vs_vertices',
    'unique_meshes_drawn', 'unique_materials_drawn',
    'fbo_switches', 'program_switches', 'texture_unit_switches',
}

_FLOAT_NAMES = {
    'gpu_duration_s', 'total_gpu_duration_s',
    'depth_value',
    'mip_lod_bias', 'mip_min_lod', 'mip_max_lod',
    'min_value_r', 'min_value_g', 'min_value_b', 'min_value_a',
    'max_value_r', 'max_value_g', 'max_value_b', 'max_value_a',
    'border_color_r', 'border_color_g', 'border_color_b', 'border_color_a',
    'color_r', 'color_g', 'color_b', 'color_a',
    'shader_out_r', 'shader_out_g', 'shader_out_b', 'shader_out_a',
    'pre_mod_r', 'pre_mod_g', 'pre_mod_b', 'pre_mod_a',
    'post_mod_r', 'post_mod_g', 'post_mod_b', 'post_mod_a',
    'position_x', 'position_y', 'position_z', 'position_w',
    'as_f32_0', 'as_f32_1', 'as_f32_2', 'as_f32_3',
    'value_double',
    'arg_float',
    'complexity_score',
    'screen_min_x', 'screen_min_y', 'screen_max_x', 'screen_max_y',
    'sum_gpu_duration_s',
}

_BOOL_NAMES = {
    'is_rt', 'is_color', 'is_depth', 'is_stencil',
    'is_swap_chain', 'is_swap_chain_target',
    'is_drawcall', 'is_dispatch', 'is_clear', 'is_copy', 'is_resolve',
    'is_marker_push', 'is_marker_pop', 'is_set_state',
    'depth_test_enable', 'depth_write_enable', 'stencil_enable', 'blend_enable',
    'enabled', 'normalized', 'integer', 'linked',
    'used_as_vbo', 'used_as_ibo', 'used_as_ubo', 'used_as_ssbo', 'used_as_indirect',
    'fb_fetch', 'uses_cubemap', 'uses_texture_gather', 'uses_texture_grad',
    'passed', 'backface_culled', 'depth_test_failed', 'stencil_test_failed',
    'scissor_clipped', 'shader_discarded', 'sample_masked',
    'depth_clipped', 'view_clipped',
    'clipped',
}


def infer_dtype(col_name: str) -> str:
    """Return one of: 'int', 'float', 'bool', 'str'."""
    if col_name in _BOOL_NAMES:
        return 'bool'
    if col_name in _FLOAT_NAMES:
        return 'float'
    if col_name in _INT_NAMES:
        return 'int'
    return 'str'


def expected_columns(table_stem: str) -> tuple:
    """Lookup column tuple by table stem. Raises KeyError if unknown."""
    return TABLES[table_stem].cols


def is_entity_table(table_stem: str) -> bool:
    return TABLES[table_stem].is_entity


def size_class(table_stem: str) -> str:
    return TABLES[table_stem].size_class


def table_category(table_stem: str) -> str:
    """Grouping key for the per-drop browser. Raises KeyError if unknown."""
    return TABLES[table_stem].category


def entity_tables() -> tuple:
    """Stems of every table that carries a stable_key, in registry order (H-9)."""
    return tuple(stem for stem in TABLES if TABLES[stem].is_entity)
