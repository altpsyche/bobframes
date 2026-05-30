"""WHATIF shader-override probe. NOT WIRED INTO run.py.

Stub holding the BuildTargetShader + ReplaceResource pattern from
Appendix A.10 for ad-hoc use. Run separately when a human has identified
shader IDs they want to stub-test for GPU-time savings.

Usage (from inside qrenderdoc.exe --python):
    set RDC_INSIDE_ARGS=<rdc_path>\x1f<shader_id>[\x1f<shader_id>...]\x1f<N_samples>
    qrenderdoc.exe --python probes/whatif.py

Writes results to <rdc_dir>/_whatif_<shader_id>.csv.

Pattern documentation (verbatim from Appendix A.10):

  - GetResources() returns a list with .resourceId fields; str(rid) is
    'ResourceId::N'. Parse N to map int handles to ResourceId objects.
  - BuildTargetShader returns a tuple of (ResourceId, str) OR (str, ResourceId)
    depending on RD version. Find the ResourceId via isinstance walk.
  - ReplaceResource requires both arguments to be real ResourceId objects;
    rd.ResourceId(int) is rejected.
  - FetchCounters([rd.GPUCounter.EventGPUDuration]) returns one CounterResult
    per event with value.d in seconds.
  - Median 3-5 baseline + 3-5 replaced samples per shader for reliable deltas;
    single-sample variance is +/- 10%.
  - Always FreeTargetResource() and RemoveReplacement() after each test.

The actual implementation is left as an exercise for the downstream report
layer that drives this probe with specific shader IDs and sample counts.
"""

from __future__ import annotations

import csv
import os
import statistics
import sys
import time


FS_GRAY_STUB = """\
#version 310 es
precision mediump float;
out vec4 out_FragColor;
void main() { out_FragColor = vec4(0.5, 0.5, 0.5, 1.0); }
"""


def run_whatif_for_shader(ctrl, shader_handle: int, samples: int = 3) -> dict:
    """Run baseline + replaced timing for one shader. Returns dict of medians."""
    import renderdoc as rd  # type: ignore

    resources = ctrl.GetResources()
    handle_to_rid: dict[int, object] = {}
    for r in resources:
        s = str(r.resourceId)
        if '::' in s:
            try:
                handle_to_rid[int(s.split('::', 1)[1])] = r.resourceId
            except Exception:
                continue

    if shader_handle not in handle_to_rid:
        raise KeyError(f'shader {shader_handle} not found in capture resources')
    orig_rid = handle_to_rid[shader_handle]

    def measure_total() -> float:
        rs = ctrl.FetchCounters([rd.GPUCounter.EventGPUDuration])
        return float(sum(float(r.value.d) for r in rs))

    baseline_samples = [measure_total() for _ in range(samples)]

    result = ctrl.BuildTargetShader(
        'main', rd.ShaderEncoding.GLSL,
        bytes(FS_GRAY_STUB, 'utf-8'),
        rd.ShaderCompileFlags(),
        rd.ShaderStage.Pixel,
    )
    new_id = None
    err_str = ''
    if isinstance(result, tuple) and len(result) >= 2:
        for x in result:
            if isinstance(x, rd.ResourceId):
                new_id = x
            else:
                err_str = str(x)
    if new_id is None or new_id == rd.ResourceId.Null():
        raise RuntimeError(f'compile failed: {err_str}')

    ctrl.ReplaceResource(orig_rid, new_id)
    try:
        replaced_samples = [measure_total() for _ in range(samples)]
    finally:
        ctrl.RemoveReplacement(orig_rid)
        ctrl.FreeTargetResource(new_id)

    bm = statistics.median(baseline_samples)
    rm = statistics.median(replaced_samples)
    return {
        'shader_id': shader_handle,
        'baseline_median_s': bm,
        'baseline_samples': baseline_samples,
        'replaced_median_s': rm,
        'replaced_samples': replaced_samples,
        'delta_s_median': bm - rm,
        'delta_pct_median': (bm - rm) / bm * 100.0 if bm else 0.0,
    }


def main() -> int:
    env = os.environ.get('RDC_INSIDE_ARGS', '')
    parts = env.split('\x1f') if env else []
    if len(parts) < 2:
        print('usage: set RDC_INSIDE_ARGS=<rdc>\\x1f<shader_id>[\\x1f<shader_id>...][\\x1f<samples>]')
        os._exit(2)

    rdc_path = parts[0]
    samples = 3
    shader_ids = []
    for p in parts[1:]:
        try:
            sh = int(p)
            if sh < 100:  # treat small ints as samples count
                samples = sh
            else:
                shader_ids.append(sh)
        except ValueError:
            continue

    if not shader_ids:
        print('no shader ids supplied')
        os._exit(2)

    import renderdoc as rd  # type: ignore
    cap = rd.OpenCaptureFile()
    cap.OpenFile(rdc_path, '', None)
    res = cap.OpenCapture(rd.ReplayOptions(), None)
    rc, ctrl = (res if isinstance(res, tuple) else (res.result, res.controller))
    if rc != rd.ResultCode.Succeeded:
        print(f'open failed: {rc}')
        os._exit(1)

    out_path = os.path.join(os.path.dirname(rdc_path),
                            f'_whatif_{os.path.basename(rdc_path).replace(".rdc","")}.csv')
    fields = ['shader_id', 'baseline_median_s', 'baseline_samples',
              'replaced_median_s', 'replaced_samples',
              'delta_s_median', 'delta_pct_median']
    with open(out_path, 'w', encoding='utf-8', newline='') as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for sh in shader_ids:
            r = run_whatif_for_shader(ctrl, sh, samples=samples)
            r['baseline_samples'] = ';'.join(f'{x:.6f}' for x in r['baseline_samples'])
            r['replaced_samples'] = ';'.join(f'{x:.6f}' for x in r['replaced_samples'])
            w.writerow(r)
            print(f'  shader {sh}: baseline={r["baseline_median_s"]*1000:.2f}ms '
                  f'replaced={r["replaced_median_s"]*1000:.2f}ms '
                  f'delta={r["delta_s_median"]*1000:.2f}ms ({r["delta_pct_median"]:.1f}%)')

    ctrl.Shutdown(); cap.Shutdown()
    print(f'wrote {out_path}')
    os._exit(0)


if __name__ == '__main__':
    main()
