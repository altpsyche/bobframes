"""Unit tests for stable_keys (c15, doc's `unit_keys.py`).

Pins the load-bearing key contracts: version prefix, GLSL normalization, determinism, the
empty-string contract for unknown inputs, and order-invariance of the composite keys. The exact
SHA256 version-prefix byte is already asserted in test_hardening.py — here we cover the surrounding
behavior so a key-derivation rule change can't silently shift results.

Named `test_*` (not the c15 doc's `unit_keys.py`) so default pytest collects it — no `python_files`
override in pyproject.
"""
from __future__ import annotations

from .. import stable_keys as sk


def test_key_version_is_one():
    assert sk.KEY_VERSION == 1


def test_normalize_glsl_strips_and_collapses():
    src = "void main(){\n  // line comment\n  /* block */ x=1;   \n\n\n\n  y=2;\n}\n"
    out = sk.normalize_glsl(src)
    assert "//" not in out and "/*" not in out
    assert "\n\n\n" not in out          # blank-line runs collapsed to at most one blank line
    assert not out.endswith(" ")        # trailing ws stripped
    assert sk.normalize_glsl(out) == out  # idempotent
    assert sk.normalize_glsl("") == ""


def test_shader_key_determinism_and_comment_insensitivity():
    a = sk.normalize_glsl("float f(){ return 1.0; } // v1")
    b = sk.normalize_glsl("float f(){ return 1.0; } /* different comment */")
    assert sk.shader_key(a) == sk.shader_key(b)          # comments don't change the key
    assert sk.shader_key(a) == sk.shader_key(a)          # deterministic
    assert sk.shader_key("float g(){ return 2.0; }") != sk.shader_key(a)
    assert len(sk.shader_key(a)) == 64                   # sha256 hexdigest


def test_empty_input_contract():
    assert sk.shader_key("") == ""
    assert sk.program_key([]) == ""
    assert sk.program_key(["", ""]) == ""                # only empties -> empty
    assert sk.fbo_key([]) == ""
    assert sk.texture_key("lbl", None, 10, 10, 1, 1, 1) == ""   # fmt None
    assert sk.texture_key("lbl", "RGBA8", None, 10, 1, 1, 1) == ""  # width None
    assert sk.sampler_key(None, "LIN", "R", "R", "R", 1, "NONE", "ALW") == ""
    assert sk.buffer_key("h", 0, "t") == ""              # size <= 0
    assert sk.buffer_key("h", -5, "t") == ""


def test_composite_keys_order_invariant_and_filter_empties():
    assert sk.program_key(["a", "b"]) == sk.program_key(["b", "a"])
    assert sk.program_key(["a", "", "b"]) == sk.program_key(["b", "a"])  # empties dropped
    assert sk.fbo_key(["x", "y"]) == sk.fbo_key(["y", "x"])
    assert sk.program_key(["a", "b"]) != sk.program_key(["a", "c"])


def test_distinct_payloads_distinct_keys():
    t1 = sk.texture_key("color", "RGBA8", 256, 256, 1, 1, 1)
    t2 = sk.texture_key("color", "RGBA8", 512, 256, 1, 1, 1)
    assert t1 and t2 and t1 != t2
