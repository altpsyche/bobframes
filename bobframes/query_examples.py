"""Emit <root>/_query_examples.md.

Canonical DuckDB / polars query patterns for Layer 2 reports.
"""

from __future__ import annotations

import os


_CONTENT = r"""# Canonical query patterns

All snippets target DuckDB. Replace `**/` with the root path or a specific
drop folder when needed. Reports may also use polars / pyarrow on the same
Parquet files.

## Read the catalog

```sql
SELECT * FROM read_parquet('_catalog.parquet') ORDER BY drop_date, area, capture;
```

Each row = one capture. Has `row_count_*` per table, schema_version, build
timestamp, replay_status, and `analysis_out_path` pointing at the drop folder.

## Total GPU duration per area per drop

```sql
SELECT area, drop_date, drop_label, sum(total_gpu_duration_s) AS gpu_s
FROM read_parquet('**/frame_totals.parquet')
GROUP BY area, drop_date, drop_label
ORDER BY drop_date, area;
```

## Top shaders by total draw count, across all drops

```sql
SELECT stable_key, count(*) AS draw_uses,
       any_value(shader_type) AS type,
       any_value(src_len) AS src_len
FROM read_parquet('**/shaders.parquet') s
JOIN read_parquet('**/draws.parquet') d
  ON s.area = d.area
 AND s.drop_date = d.drop_date
 AND s.drop_label = d.drop_label
 AND s.capture = d.capture
 AND (s.shader_id = d.fs_shader_id OR s.shader_id = d.vs_shader_id)
WHERE s.stable_key != ''
GROUP BY stable_key
ORDER BY draw_uses DESC
LIMIT 20;
```

## Use _global_entities for single-key joins

```sql
-- All draws whose fragment shader matches a given stable_key
WITH g AS (
  SELECT area, drop_date, drop_label, capture, local_id
  FROM read_parquet('_global_entities.parquet')
  WHERE kind = 'shader' AND stable_key = '390139100b660402...'
)
SELECT d.* FROM read_parquet('**/draws.parquet') d
JOIN g USING (area, drop_date, drop_label, capture)
WHERE d.fs_shader_id = g.local_id;
```

## Pass-level GPU time across drops

```sql
SELECT marker_path_norm, drop_date, sum(gpu_duration_s) AS gpu_s,
       sum(num_draws) AS draws
FROM read_parquet('**/passes.parquet')
WHERE marker_path_norm != ''
GROUP BY marker_path_norm, drop_date
ORDER BY marker_path_norm, drop_date;
```

`marker_path_norm` has the `Frame N/` prefix stripped so passes match across
captures and drops.

## Draws-by-class per area

```sql
SELECT area, draw_class, count(*) AS n,
       sum(num_indices * num_instances) AS pre_vs_verts
FROM read_parquet('**/draws.parquet')
GROUP BY area, draw_class
ORDER BY area, n DESC;
```

## Find non-instanced repeated draws (potential merge targets)

```sql
SELECT area, capture, parent_pass_path_norm, fs_shader_id,
       count(*) AS occurrences
FROM read_parquet('**/draws.parquet')
WHERE num_instances <= 1 AND draw_class IN ('opaque', 'prepass')
GROUP BY area, capture, parent_pass_path_norm, fs_shader_id
HAVING count(*) >= 4
ORDER BY occurrences DESC
LIMIT 50;
```

## Largest render targets per area

```sql
SELECT area, format, width, height, count(*) AS rt_count,
       any_value(label) AS sample_label
FROM read_parquet('**/render_targets.parquet')
WHERE width > 0
GROUP BY area, format, width, height
ORDER BY width * height DESC
LIMIT 50;
```

## Texture inventory across drops (deduped via stable_key)

```sql
SELECT stable_key, any_value(label) AS label,
       any_value(format) AS format,
       any_value(width) AS w, any_value(height) AS h,
       count(DISTINCT area || drop_date || drop_label || capture) AS in_captures
FROM read_parquet('**/textures.parquet')
WHERE stable_key != ''
GROUP BY stable_key
ORDER BY in_captures DESC, label
LIMIT 100;
```

## Pixel-history rejection summary per RT

```sql
SELECT rt_id, count(*) AS samples,
       sum(passed) AS passed,
       sum(depth_test_failed) AS depth_failed,
       sum(shader_discarded) AS discarded,
       sum(scissor_clipped) AS scissored
FROM read_parquet('**/pixel_history.parquet')
GROUP BY rt_id
ORDER BY samples DESC;
```

## Cross-drop entity stability check

```sql
-- How many unique shader stable_keys exist across all drops?
SELECT count(DISTINCT stable_key) FROM read_parquet('_global_entities.parquet')
WHERE kind = 'shader';

-- Which shaders appear in every drop?
WITH per_drop AS (
  SELECT stable_key, drop_date, count(*) AS n
  FROM read_parquet('_global_entities.parquet')
  WHERE kind = 'shader'
  GROUP BY stable_key, drop_date
)
SELECT stable_key, count(DISTINCT drop_date) AS in_drops
FROM per_drop
GROUP BY stable_key
HAVING count(DISTINCT drop_date) = (SELECT count(DISTINCT drop_date) FROM per_drop)
ORDER BY stable_key;
```

## Per-capture totals from catalog (no joins needed)

```sql
SELECT area, capture, row_count_draws, row_count_state_change_events,
       row_count_pixel_history
FROM read_parquet('_catalog.parquet')
ORDER BY area, capture;
```

## Reading shader source on demand

```python
import json, glob, os
shader_id = 16844
# Find captures that have this shader id
import pyarrow.parquet as pq
for p in glob.glob('*/2026-05-27_*/_analysis_out/shaders.parquet'):
    t = pq.read_table(p, columns=['area','capture','shader_id','src_file_path'])
    df = t.to_pandas()
    hit = df[df['shader_id'] == shader_id]
    for _, r in hit.iterrows():
        src = os.path.join(os.path.dirname(p), r['src_file_path'])
        with open(src) as f:
            print(f.read())
```

## Uniform values per pass

`uniforms_per_pass.jsonl` (per drop) carries one JSON object per pass-first-draw
with the bound constant-block layouts and raw UBO bytes. Read line-by-line:

```python
import json
for p in glob.glob('*/2026-05-27_*/_analysis_out/uniforms_per_pass.jsonl'):
    with open(p) as f:
        for line in f:
            o = json.loads(line)
            if 'MobileBasePass' in o['marker_path']:
                # o['constant_blocks'] -> list of {stage, block_name, members, ...}
                # o['raw_by_binding'][slot] -> {buffer_id, offset, size, raw_hex}
                ...
```
"""


def write_query_examples(root: str) -> str:
    from . import paths as _paths
    os.makedirs(_paths.data_root(root), exist_ok=True)
    path = _paths.query_examples_md(root)
    with open(path, 'w', encoding='utf-8') as f:
        f.write(_CONTENT)
    return path


if __name__ == '__main__':
    import sys
    p = write_query_examples(sys.argv[1] if len(sys.argv) > 1 else '.')
    print(f'wrote {p}')
