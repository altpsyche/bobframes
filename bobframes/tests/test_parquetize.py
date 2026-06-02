"""Unit coverage for the parquetize internals that the render-only golden path does NOT exercise
(the synthetic fixture is pre-built _data, so parquetize never runs in test_parquet_parity).

- Q-1: `_apply_stable_key` (the dict-of-builders refactor) dispatches each entity table to the right
  `stable_keys.*` function - asserted against the oracle so the refactor stays byte-identical to the
  old if/elif chain (the keys feed the frozen Parquet digests + cross-run identity).
- Q-2: `_cast_value` tallies genuine coercion failures into the `fails` accumulator (so the caller
  can log a summary) while still returning the defaulted value, and does NOT count legit empty cells.
"""
from __future__ import annotations

from .. import stable_keys
from ..parquetize import _apply_stable_key, _as_int, _cast_value


def _apply(stem: str, columns: dict) -> list:
    cols = dict(columns)
    cols['stable_key'] = [''] * len(next(iter(columns.values())))
    _apply_stable_key(stem, cols)
    return cols['stable_key']


def test_apply_stable_key_shaders_passthrough():
    assert _apply('shaders', {'src_hash': ['deadbeef', '']}) == ['deadbeef', '']


def test_apply_stable_key_textures_and_render_targets_use_texture_key():
    cols = {'label': ['albedo'], 'format': ['RGBA8'], 'width': ['1024'], 'height': ['512'],
            'depth': ['1'], 'mip_levels': ['10'], 'sample_count': ['1']}
    oracle = stable_keys.texture_key('albedo', 'RGBA8', 1024, 512, 1, 10, 1)
    assert _apply('textures', cols) == [oracle]
    assert _apply('render_targets', cols) == [oracle]   # render_targets shares the texture builder


def test_apply_stable_key_samplers():
    cols = {'min_filter': ['LINEAR'], 'mag_filter': ['LINEAR'], 'wrap_s': ['REPEAT'],
            'wrap_t': ['REPEAT'], 'wrap_r': ['CLAMP'], 'max_anisotropy': ['16'],
            'compare_mode': ['NONE'], 'compare_func': ['LEQUAL']}
    oracle = stable_keys.sampler_key('LINEAR', 'LINEAR', 'REPEAT', 'REPEAT', 'CLAMP',
                                     16, 'NONE', 'LEQUAL')
    assert _apply('samplers', cols) == [oracle]


def test_apply_stable_key_buffers_first_target_split():
    cols = {'usage_hint': ['STATIC'], 'allocated_size_bytes': ['2048'],
            'target_history': ['ARRAY_BUFFER;ELEMENT_ARRAY_BUFFER']}
    oracle = stable_keys.buffer_key('STATIC', 2048, 'ARRAY_BUFFER')
    assert _apply('buffers', cols) == [oracle]
    # empty target_history -> first_target ''
    cols2 = {'usage_hint': ['DYN'], 'allocated_size_bytes': ['0'], 'target_history': ['']}
    assert _apply('buffers', cols2) == [stable_keys.buffer_key('DYN', 0, '')]


def test_apply_stable_key_programs_filters_empty_ids():
    assert _apply('programs', {'attached_shader_ids': ['7;8;9']}) \
        == [stable_keys.program_key(['7', '8', '9'])]
    # no ids / all-empty after filter -> '' (matches the old `if id_list:` guard)
    assert _apply('programs', {'attached_shader_ids': ['']}) == ['']
    assert _apply('programs', {'attached_shader_ids': [';;']}) == ['']


def test_apply_stable_key_fbos_skips_zero_and_empty():
    assert _apply('fbos', {'resource_id': ['5']}) == [stable_keys.fbo_key(['5'])]
    assert _apply('fbos', {'resource_id': ['0']}) == ['']
    assert _apply('fbos', {'resource_id': ['']}) == ['']


def test_apply_stable_key_missing_column_defaults_empty():
    # a builder column absent from `columns` resolves to '' (the CSV merge never yields None).
    cols = {'format': ['RGBA8'], 'width': ['8'], 'height': ['8'], 'depth': ['1'],
            'mip_levels': ['1'], 'sample_count': ['1']}   # 'label' missing
    assert _apply('textures', cols) == [stable_keys.texture_key('', 'RGBA8', 8, 8, 1, 1, 1)]


def test_apply_stable_key_noop_without_stable_key_column():
    cols = {'src_hash': ['x']}    # no 'stable_key' key -> function returns without adding one
    _apply_stable_key('shaders', cols)
    assert 'stable_key' not in cols


def test_cast_value_tallies_failures_but_still_defaults():
    fails: dict = {}
    assert _cast_value('not-an-int', 'int', fails) == 0
    assert _cast_value('NaNeither', 'float', fails) == 0.0
    assert fails == {'int': 1, 'float': 1}


def test_cast_value_empty_is_not_a_failure():
    fails: dict = {}
    assert _cast_value('', 'int', fails) == 0
    assert _cast_value('', 'float', fails) == 0.0
    assert _cast_value('', 'bool', fails) is False
    assert fails == {}                       # empty cells are legit defaults, not coercion failures


def test_cast_value_valid_inputs_unchanged_and_uncounted():
    fails: dict = {}
    assert _cast_value('42', 'int', fails) == 42
    assert _cast_value('3.5', 'float', fails) == 3.5
    assert _cast_value('1', 'bool', fails) is True
    assert _cast_value('0', 'bool', fails) is False
    assert _cast_value('12.0', 'int', fails) == 12      # int(float(v)) fallback path
    assert fails == {}


def test_as_int_tolerant():
    assert _as_int('7') == 7 and _as_int('') == 0 and _as_int(None) == 0 and _as_int('x') == 0
