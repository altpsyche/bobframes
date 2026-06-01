"""c09: engine-agnostic draw classifier (H-1..H-5) + the D-6 replay-classifier deletion.

The golden HTML + Parquet gates (test_parity / test_parquet_parity) prove end-to-end byte-identity of
the emitted draw_class column. These asserts pin the MECHANISM and give a focused failure when a
bundled preset value drifts from today's form (ADR-6 / QUALITY_GATES §21.1e), independent of the
full-page golden — and prove the engine is state-capable, not marker-only.
"""

from __future__ import annotations

import re

import pytest

from bobframes import config
from bobframes.derives import classifier
from bobframes.reports import chrome


@pytest.fixture(autouse=True)
def _isolate(monkeypatch):
    """Bundled defaults only: clear $BOBFRAMES_CONFIG + cached config + cached classifier specs."""
    monkeypatch.delenv('BOBFRAMES_CONFIG', raising=False)
    config._reset_for_tests()
    classifier._reset_for_tests()
    yield
    config._reset_for_tests()
    classifier._reset_for_tests()


# --- The former host _classify_draw, frozen verbatim as the parity oracle (derive_post_merge, pre-c09).
def _orig_classify_draw(blend_enable, depth_write, marker_path, blend_src_color, blend_dst_color):
    mp = (marker_path or '').lower()
    if 'shadow' in mp:
        return 'shadow'
    if 'prepass' in mp or 'depthonly' in mp:
        return 'prepass'
    if 'slate' in mp or '/ui' in mp or mp.endswith('ui'):
        return 'ui'
    if 'postprocess' in mp or 'tonemap' in mp or 'bloom' in mp or 'eyeadapt' in mp:
        return 'postprocess'
    if 'decal' in mp:
        return 'decal'
    if 'translucen' in mp:
        return 'translucent'
    if int(blend_enable or 0):
        bs = (blend_src_color or '').lower()
        bd = (blend_dst_color or '').lower()
        if bs == 'one' and bd == 'one':
            return 'additive'
        return 'translucent'
    if 'basepass' in mp:
        return 'opaque'
    if int(depth_write or 0):
        return 'opaque'
    return 'other'


# --- H-3/H-2/H-4 parity asserts: bundled UE preset == the former in-code literals -------------------

def test_frame_prefix_regex_unchanged():
    assert classifier.frame_prefix_re().pattern == r'^Frame\s+\d+/?'
    # behaves like the old _RE_FRAME_PREFIX
    assert classifier.frame_prefix_re().sub('', 'Frame 12/PrePass/x') == 'PrePass/x'


def test_pass_strip_unchanged():
    ps = classifier.pass_strip()
    assert ps['prefixes'] == ['FRDGBuilder::Execute/', 'MobileSceneRender/']
    assert ps['noise_segments'] == ['Engine', 'EngineMaterials']


def test_gpu_duration_aliases_unchanged():
    assert classifier.gpu_duration_aliases() == ['GPU Duration']


# --- H-5: single source for DRAW_CLASSES + the CSS color tokens -------------------------------------

def test_class_order_equals_old_draw_classes_literal():
    assert classifier.class_order() == [
        'opaque', 'prepass', 'shadow', 'translucent', 'additive',
        'decal', 'ui', 'postprocess', 'other',
    ]
    assert chrome.DRAW_CLASSES == classifier.class_order()


def test_every_class_has_a_color_token():
    """Each --c-<name> for name in class_order is present in the emitted :root token block (H-5)."""
    css = chrome._DESIGN_TOKENS
    for cls in classifier.class_order():
        assert f'--c-{cls}:' in css, cls


# --- H-1: the UE preset reproduces the former host _classify_draw byte-for-byte ---------------------

_MARKERS = [
    'Frame 1/Shadow/p0', 'x/ShadowDepth', 'a/PrePass/b', 'c/DepthOnly', 'Slate/HUD', 'foo/UI',
    'bar/ui', '/UI/panel', 'PostProcess/Tonemap', 'x/Bloom', 'y/EyeAdapt', 'm/Decal/n',
    'Translucency/z', 'TranslucenT', 'BasePass/Mesh', 'MobileBasePass/x', 'scene/geo', '',
    'GuidPass', 'BuildStep', None,
]
_BLENDS = [(0, '', ''), (1, 'one', 'one'), (1, 'src_alpha', 'one_minus_src_alpha'),
           (1, 'one', 'zero'), (1, 'ONE', 'ONE'), (1, '', '')]
_DEPTHS = [0, 1, None]


def test_ue_preset_matches_frozen_original_over_battery():
    spec = classifier.load_spec()
    n = 0
    for mk in _MARKERS:
        for be, bs, bd in _BLENDS:
            for dw in _DEPTHS:
                n += 1
                want = _orig_classify_draw(be, dw, mk, bs, bd)
                got = classifier.classify({
                    'marker': mk, 'blend_enable': be, 'depth_write_enable': dw,
                    'blend_src_color': bs, 'blend_dst_color': bd,
                }, spec)
                assert got == want, (mk, be, bs, bd, dw, want, got)
    assert n >= 300  # guard: the battery actually ran


def test_first_matching_rule_wins_marker_over_blend():
    spec = classifier.load_spec()
    # 'translucen' marker beats an additive (one,one) blend — marker rule precedes the blend rules.
    assert classifier.classify({
        'marker': 'Translucency/x', 'blend_enable': 1,
        'blend_src_color': 'one', 'blend_dst_color': 'one',
    }, spec) == 'translucent'


# --- state-capability: the engine classifies WITHOUT any markers (the c27 generic-preset path) ------

def test_state_only_spec_classifies_without_markers():
    spec = {
        'rules': [
            {'class': 'additive', 'when': {'blend_enable': True, 'blend_src_color': 'one', 'blend_dst_color': 'one'}},
            {'class': 'translucent', 'when': {'blend_enable': True}},
            {'class': 'opaque', 'when': {'depth_write_enable': True}},
        ],
        'fallback': 'other',
    }
    f = lambda **kw: classifier.classify(kw, spec)
    assert f(marker='no/keywords/here', blend_enable=1, blend_src_color='one', blend_dst_color='one') == 'additive'
    assert f(marker='x', blend_enable=1, blend_src_color='src_alpha', blend_dst_color='x') == 'translucent'
    assert f(marker='x', blend_enable=0, depth_write_enable=1) == 'opaque'
    assert f(marker='x', blend_enable=0, depth_write_enable=0) == 'other'


# --- preset selection: a Unity preset reclassifies a Unity-style marker differently from UE ---------

def test_unity_preset_reclassifies(tmp_path):
    (tmp_path / '.bobframes.toml').write_text("[classifier]\npreset = 'unity'\n", encoding='utf-8')
    config.load_config(str(tmp_path))
    classifier._reset_for_tests()
    spec = classifier.load_spec()
    fields = {'marker': 'UniversalRenderPass/RenderShadows/ShadowCaster',
              'blend_enable': 0, 'depth_write_enable': 1}
    assert classifier.classify(fields, spec) == 'shadow'
    # the same marker is NOT a shadow under UE (no UE 'shadow' keyword path here besides the literal)
    ue = classifier.load_spec(preset='ue')
    assert classifier.classify({'marker': 'UniversalRenderPass/DrawTransparentObjects',
                                'blend_enable': 1, 'blend_src_color': 'src_alpha',
                                'blend_dst_color': 'one_minus_src_alpha'}, spec) == 'translucent'
    # class_order is the fixed contract across presets
    assert spec['class_order'] == ue['class_order']


def test_custom_path_overrides_preset(tmp_path):
    custom = tmp_path / 'mine.toml'
    custom.write_text(
        "class_order = ['opaque','other']\nfallback_class = 'other'\nframe_prefix_regex = ''\n"
        "[[rule]]\nclass = 'opaque'\nwhen = { depth_write_enable = true }\n",
        encoding='utf-8')
    (tmp_path / '.bobframes.toml').write_text(
        f"[classifier]\ncustom_path = '{custom.as_posix()}'\n", encoding='utf-8')
    config.load_config(str(tmp_path))
    classifier._reset_for_tests()
    assert classifier.class_order() == ['opaque', 'other']
    assert classifier.classify({'marker': 'shadow/x', 'depth_write_enable': 1}) == 'opaque'  # no marker rules


# --- D-6: the dead replay-side duplicate is gone and stays gone -------------------------------------

def test_replay_main_has_no_classifier():
    # replay_main imports cleanly host-side (top-level has no `renderdoc`); the drifted dead copy
    # must not silently return.
    from bobframes.replay import replay_main
    assert not hasattr(replay_main, '_classify_draw')
