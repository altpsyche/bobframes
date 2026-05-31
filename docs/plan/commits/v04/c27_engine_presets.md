# c27 — generic + non-UE classifier presets     release: v0.4 · phase: Engine breadth + ergonomics

## Goal
Make BobFrames work on non-Unreal engines. c09 externalized the UE classifier to a TOML preset; this
commit ships an **honest "generic" preset** (depth-write/blend heuristics, no engine keywords) as the
safe default for any engine, and adds the per-engine fixture+golden harness. Unity/Godot presets are
filled when real `.rdc` captures from those engines exist ([ADR-21](../../DECISIONS.md)) — generic-first.

## Depends on
[c09](../v02/c09_classifier.md) (classifier TOML + walker + presets dir + UE preset).

## Seam extended
The c09 `derives/classifier.py` walker + `derives/presets/*.toml` + `[classifier] preset=` selection.
Resolves D-6 in practice (c09 unifies the two drifted `_classify_draw` copies; c27 proves the
preset-selectable path on a non-UE fixture). No parallel classifier.

## Files
- `derives/presets/generic.toml` — NEW: `class_order` (the 9 classes), depth-write→`opaque` /
  blend→`translucent`/`additive` heuristics, **no engine keyword rules**, neutral `[pass_strip]`,
  no `frame_prefix_regex`.
- `derives/presets/{unity,godot}.toml` — stubs (filled when a real capture from that engine arrives;
  each gated behind its own fixture+golden, ADR-21/ADR-22).
- `tests/data/synthetic-generic/` + `tests/data/golden-generic/` — NEW per-engine fixture + golden
  (anonymized from a real non-UE ingest where available; else a synthetic exercising every
  heuristic).
- `tests/test_classifier_presets.py` — NEW: preset selection + `classifier.classify()` over sample
  markers for UE **and** generic.

## Changes
The generic preset must be self-consistent (every `class_order` bucket reachable by a heuristic). The
UE preset stays **byte-identical** to its golden. Preset selection via `[classifier] preset="generic"`
or `custom_path`.

## Done when
- `preset="generic"` reclassifies the generic fixture and matches the **new** generic golden.
- UE preset run is byte-identical to the existing UE golden (**parity green**).
- `test_classifier_presets.py` green (UE + generic).

## Closes
Serves the ≥2-engines breadth criterion (UE + generic). Validates D-6's c09 unification on a non-UE
path. Establishes [ADR-21](../../DECISIONS.md) (per-engine fixture+golden).
