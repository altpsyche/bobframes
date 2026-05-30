# c09 — engine-agnostic classifier     release: v0.2 · phase: De-hardcoding

## Goal
The biggest de-hardcoding step: move the UE-specific draw classification, pass-strip rules, frame
prefix, and counter names into a TOML preset so other engines work without code patches. Ship a UE
preset that is **byte-identical to today**. (Most invasive — budget extra time; parity is critical.)

## Depends on
[c08](c08_design_tokens.md).

## Files
- `derives/classifier.py` — NEW: 10-line walker reading `derives/draw_classifier.toml`.
- `derives/draw_classifier.toml` — NEW: `class_order`, `frame_prefix_regex`, ordered `[[draw_class]]`
  `{pattern, class}` rules (all 9 current rules transcribed verbatim), `[pass_strip]`, `[counters]
  gpu_duration_aliases`.
- `derives/presets/{ue,unity,godot,custom-template}.toml` — NEW.
- `derive_post_merge._classify_draw` → replaced by the walker. `formatters.pass_short` reads
  `[pass_strip]`. `chrome.DRAW_CLASSES` derived from `classifier.class_order` (single source, H-5).
  `derives/pass_class_breakdown` walks `gpu_duration_aliases` (H-4).

## Changes
Transcribe the current rules exactly. Regex in TOML needs doubled escapes
(`frame_prefix_regex = "^Frame\\s+\\d+/?"`). User selects preset via `[classifier] preset = "unity"`
or `custom_path`.

## Done when
- **Parity gate:** synthetic golden reproduces the current `draw_class` column **byte-identically**,
  and the emitted `--c-<name>` color tokens are unchanged. Add a parity assertion that each TOML regex
  `.pattern` equals the original compiled pattern ([ADR-6](../../DECISIONS.md)).
- Classifier unit test (the one deferred from c15) green: `classifier.classify()` over sample markers.
- A Unity preset run reclassifies as expected (manual check).

## Closes
H-1, H-2, H-3, H-4, H-5. Opens the "fewer `other` draws" quality win
([QUALITY_GATES §21.5](../../reference/QUALITY_GATES.md)).
