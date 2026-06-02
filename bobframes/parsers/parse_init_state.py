"""Stream a .zip.xml file and emit partial CSVs of init-state data.

Heavyweight text extraction that doesn't need replay state:
  - glShaderSource source dumps (one .glsl file per shader id)
  - shaders.csv partial rows (id, type, src_len, src_hash, complexity counts)
  - programs.csv partial rows (id, linked flag, attached_shader_ids)
  - textures.csv partial rows (id, format, w, h, mip_levels, sample_count)
  - samplers.csv partial rows (id, filter/wrap/aniso parameters)
  - buffers.csv partial rows (id, allocated_size_bytes, usage_hint)
  - fbos.csv partial rows (id, attachments)
  - resource_creation.csv rows for every glGen*/glCreate* chunk
  - labels.json: {resource_id (int): label_string}
  - chunk_index_init_max: max chunkIndex covered (so replay knows where the init region ends)

Replay-side (replay_main.py) fills the entity tables further at merge time
(used_by_draw_count, attached_to_fbo_ids from frame usage, etc.).

`created_at_event` is set to -1 ("init state") for everything emitted here
since these chunks are pre-action-tree. A merge-time pass overlays the real
event_id when one is associated.
"""

from __future__ import annotations

import csv
import hashlib
import json
import logging
import os
import re
import sys
import time
from collections.abc import Iterator

_LOG = logging.getLogger('bobframes')

# --- Streaming chunk reader --------------------------------------------------

_RE_CHUNK_START = re.compile(
    r'<chunk\s+id="(\d+)"\s+chunkIndex="(\d+)"\s+name="([^"]+)"'
)


def iter_chunks(xml_path: str) -> Iterator[tuple[int, int, str, str]]:
    """Yield (chunk_id, chunk_index, chunk_name, body) for every <chunk>.

    Streams line by line; constant memory regardless of file size.
    body excludes the opening <chunk ...> tag and the closing </chunk> tag.
    """
    in_chunk = False
    cid = cidx = 0
    cname = ''
    buf: list[str] = []
    n_replaced = 0   # R-14: tally U+FFFD substitutions so bad/truncated UTF-8 is not silent
    with open(xml_path, 'r', encoding='utf-8', errors='replace') as f:
        for line in f:
            n_replaced += line.count(chr(0xfffd))   # U+FFFD = the decode-error substitution
            if not in_chunk:
                m = _RE_CHUNK_START.search(line)
                if m:
                    cid = int(m.group(1))
                    cidx = int(m.group(2))
                    cname = m.group(3)
                    in_chunk = True
                    buf = []
                    if '</chunk>' in line:
                        body = ''.join(buf)
                        yield cid, cidx, cname, body
                        in_chunk = False
                        buf = []
            else:
                buf.append(line)
                if '</chunk>' in line:
                    body = ''.join(buf)
                    yield cid, cidx, cname, body
                    in_chunk = False
                    buf = []
    if n_replaced:
        # R-14: bad/truncated UTF-8 was substituted with U+FFFD rather than raising. Surface it so a
        # corrupt/partial capture is not silently parsed into incomplete rows (the fuller fix - a
        # manifest parse_status='partial' - is a follow-up; this at least breaks the silence).
        _LOG.warning('parse %s: %d byte(s) were not valid UTF-8 and were replaced (U+FFFD); '
                     'parsed text for the affected chunk(s) may be incomplete', xml_path, n_replaced)


# --- Body extractors ---------------------------------------------------------

_RE_RESID = re.compile(
    r'<ResourceId\s+name="([^"]+)"[^>]*>(\d+)</ResourceId>'
)
_RE_INT = re.compile(
    r'<int\s+name="([^"]+)"[^>]*>(-?\d+)</int>'
)
_RE_UINT = re.compile(
    r'<u?int(?:64_t)?\s+name="([^"]+)"[^>]*>(\d+)</u?int(?:64_t)?>'
)
_RE_ENUM_WITH_STRING = re.compile(
    r'<enum\s+name="([^"]+)"[^>]*string="([^"]+)"[^>]*>(\d+)</enum>'
)
_RE_STRING_PLAIN = re.compile(
    r'<string\s+name="([^"]+)"[^>]*>([\s\S]*?)</string>'
)
_RE_SHADER_SRC = re.compile(
    r'<array\s+name="sources"[^>]*>\s*<string[^>]*>([\s\S]*?)</string>'
)


class _CI(dict):
    """Case-insensitive dict for chunk arg lookups."""
    def get(self, key, default=None):
        v = super().get(key, _MISS)
        if v is not _MISS:
            return v
        kl = key.lower()
        for k, v in self.items():
            if k.lower() == kl:
                return v
        return default

    def __contains__(self, key):
        return self.get(key, _MISS) is not _MISS

_MISS = object()


def _resids(body: str) -> _CI:
    d = _CI()
    for m in _RE_RESID.finditer(body):
        d[m.group(1)] = int(m.group(2))
    return d


def _ints(body: str) -> _CI:
    out = _CI()
    for m in _RE_INT.finditer(body):
        out[m.group(1)] = int(m.group(2))
    for m in _RE_UINT.finditer(body):
        if m.group(1) not in out:
            out[m.group(1)] = int(m.group(2))
    return out


def _enums(body: str) -> _CI:
    out = _CI()
    for m in _RE_ENUM_WITH_STRING.finditer(body):
        out[m.group(1)] = (int(m.group(3)), m.group(2))
    return out


def _strings(body: str) -> _CI:
    out = _CI()
    for m in _RE_STRING_PLAIN.finditer(body):
        out[m.group(1)] = m.group(2)
    return out


def _first_resid(body: str) -> int:
    """Return the FIRST non-zero ResourceId in body, or 0 if none."""
    for m in _RE_RESID.finditer(body):
        v = int(m.group(2))
        if v:
            return v
    return 0


# --- Shader source complexity heuristics (counts, not interpretation) --------

_RE_TEX_SAMPLE = re.compile(r'\btexture(?:\w*)\(')
_RE_BRANCH = re.compile(r'\b(if|else)\b')
_RE_LOOP = re.compile(r'\b(for|while)\b')
_RE_DISCARD = re.compile(r'\bdiscard\b')
_RE_DFDX = re.compile(r'\b(dFdx|dFdy|fwidth)\b')
_RE_MAT4_CTOR = re.compile(r'\bmat4\s*\(')
_RE_VARYING = re.compile(r'\b(in|out|varying)\s+(?:highp|mediump|lowp)?\s*\w+\s+\w+\s*;')
_RE_MEDIUMP = re.compile(r'\bmediump\b')
_RE_HIGHP = re.compile(r'\bhighp\b')
_RE_LOWP = re.compile(r'\blowp\b')
_RE_FB_FETCH = re.compile(r'\b(GL_EXT_shader_framebuffer_fetch|inout\s+\w+\s+gl_LastFragData)\b')
_RE_CUBEMAP = re.compile(r'\bsamplerCube\b')
_RE_TEX_GATHER = re.compile(r'\btextureGather\w*\(')
_RE_TEX_GRAD = re.compile(r'\btextureGrad\w*\(')


def shader_complexity(source: str) -> dict[str, int]:
    return {
        'total_texture_samples':   len(_RE_TEX_SAMPLE.findall(source)),
        'total_branches':          len(_RE_BRANCH.findall(source)),
        'total_loops':             len(_RE_LOOP.findall(source)),
        'total_discards':          len(_RE_DISCARD.findall(source)),
        'total_dfdx_dfdy':         len(_RE_DFDX.findall(source)),
        'total_mat4_constructors': len(_RE_MAT4_CTOR.findall(source)),
        'total_varyings':          len(_RE_VARYING.findall(source)),
        'mediump_decls':           len(_RE_MEDIUMP.findall(source)),
        'highp_decls':              len(_RE_HIGHP.findall(source)),
        'lowp_decls':               len(_RE_LOWP.findall(source)),
        'fb_fetch':                 1 if _RE_FB_FETCH.search(source) else 0,
        'uses_cubemap':             1 if _RE_CUBEMAP.search(source) else 0,
        'uses_texture_gather':      1 if _RE_TEX_GATHER.search(source) else 0,
        'uses_texture_grad':        1 if _RE_TEX_GRAD.search(source) else 0,
    }


# --- Shader type decode ------------------------------------------------------

_GL_SHADER_TYPE = {
    35633: 'vertex',
    35632: 'fragment',
    36313: 'geometry',
    36488: 'tess_control',
    36487: 'tess_evaluation',
    37305: 'compute',
}


# --- Resource kind mapping ---------------------------------------------------

_RESOURCE_GEN_CHUNKS = {
    'glGenBuffers':       'buffer',
    'glCreateBuffers':    'buffer',
    'glGenTextures':      'texture',
    'glCreateTextures':   'texture',
    'glGenFramebuffers':  'framebuffer',
    'glCreateFramebuffers': 'framebuffer',
    'glGenSamplers':      'sampler',
    'glCreateSamplers':   'sampler',
    'glGenRenderbuffers': 'renderbuffer',
    'glGenVertexArrays':  'vao',
    'glCreateVertexArrays': 'vao',
    'glGenQueries':       'query',
    'glFenceSync':        'sync',
}


# --- Parser ------------------------------------------------------------------

class _Acc:
    """Accumulator across chunks during one parse pass."""

    def __init__(self) -> None:
        self.resource_creation: list[dict] = []
        self.shaders: dict[int, dict] = {}             # shader_id → row dict
        self.programs: dict[int, dict] = {}            # program_id → row
        self.textures: dict[int, dict] = {}            # texture_id → row
        self.buffers: dict[int, dict] = {}             # buffer_id → row
        self.samplers: dict[int, dict] = {}            # sampler_id → row
        self.fbos: dict[int, dict] = {}                # fbo_id → row
        self.labels: dict[int, str] = {}               # resource_id → label
        self.max_chunk_index: int = -1
        self.shader_sources: dict[int, str] = {}       # shader_id → full source

    def _ensure_shader(self, sid: int) -> dict:
        return self.shaders.setdefault(sid, {
            'shader_id': sid,
            'shader_type': '',
            'src_len': 0,
            'src_hash': '',
            'linked_program_ids': '',
            'used_by_draw_count': 0,
            'total_texture_samples': 0, 'total_branches': 0, 'total_loops': 0,
            'total_discards': 0, 'total_dfdx_dfdy': 0,
            'total_mat4_constructors': 0, 'total_varyings': 0,
            'mediump_decls': 0, 'highp_decls': 0, 'lowp_decls': 0,
            'fb_fetch': 0, 'uses_cubemap': 0, 'uses_texture_gather': 0,
            'uses_texture_grad': 0,
            'src_file_path': '',
        })

    def _ensure_program(self, pid: int) -> dict:
        return self.programs.setdefault(pid, {
            'program_id': pid, 'linked': 0,
            'num_attached_shaders': 0, 'attached_shader_ids': '',
            'vs_shader_id': 0, 'fs_shader_id': 0, 'cs_shader_id': 0,
            'gs_shader_id': 0, 'tcs_shader_id': 0, 'tes_shader_id': 0,
            'num_active_uniforms': 0, 'num_active_uniform_blocks': 0,
            'num_active_attributes': 0, 'used_by_draw_count': 0, 'label': '',
        })

    def _ensure_texture(self, tid: int) -> dict:
        return self.textures.setdefault(tid, {
            'tex_id': tid, 'format': '', 'width': 0, 'height': 0, 'depth': 0,
            'mip_levels': 0, 'sample_count': 0, 'kind': '',
            'est_bytes': 0, 'is_rt': 0, 'is_swap_chain': 0, 'label': '',
            'created_at_event': -1, 'num_bind_events': 0, 'num_sample_events': 0,
            'sampled_by_shader_ids': '', 'attached_to_fbo_ids': '',
        })

    def _ensure_buffer(self, bid: int) -> dict:
        return self.buffers.setdefault(bid, {
            'buffer_id': bid, 'allocated_size_bytes': 0, 'usage_hint': '',
            'target_history': '',
            'first_alloc_event': -1, 'last_alloc_event': -1,
            'first_bind_event': -1, 'last_bind_event': -1,
            'num_glBufferData': 0, 'num_glBufferSubData': 0,
            'num_glBindBuffer': 0, 'num_glBindBufferBase': 0, 'num_glBindBufferRange': 0,
            'used_by_draws': 0,
            'used_as_vbo': 0, 'used_as_ibo': 0, 'used_as_ubo': 0,
            'used_as_ssbo': 0, 'used_as_indirect': 0,
        })

    def _ensure_sampler(self, sid: int) -> dict:
        return self.samplers.setdefault(sid, {
            'sampler_id': sid, 'min_filter': '', 'mag_filter': '',
            'wrap_s': '', 'wrap_t': '', 'wrap_r': '',
            'mip_min_lod': -1000.0, 'mip_max_lod': 1000.0, 'mip_lod_bias': 0.0,
            'max_anisotropy': 1, 'compare_mode': '', 'compare_func': '',
            'border_color_r': 0.0, 'border_color_g': 0.0,
            'border_color_b': 0.0, 'border_color_a': 0.0,
            'created_at_event': -1, 'bound_to_draw_count': 0, 'label': '',
        })

    def _ensure_fbo(self, fid: int) -> dict:
        return self.fbos.setdefault(fid, {
            'fbo_id': fid, 'attachment_point': '', 'kind': '',
            'resource_id': 0, 'format': '',
            'width': 0, 'height': 0, 'sample_count': 0,
            'mip_level': 0, 'layer': 0, 'created_at_event': -1,
            'bound_at_events': '',
            'num_clears': 0, 'num_writes': 0, 'num_reads': 0, 'label': '',
        })


def _handle_create_shader(acc: _Acc, body: str, cidx: int) -> None:
    rids = _resids(body)
    enums = _enums(body)
    sid = rids.get('real') or rids.get('shader') or 0
    if not sid:
        return
    type_enum = enums.get('type')
    kind_full = type_enum[1] if type_enum else ''
    type_int = type_enum[0] if type_enum else 0
    short = _GL_SHADER_TYPE.get(type_int, '')
    row = acc._ensure_shader(sid)
    row['shader_type'] = short or kind_full
    acc.resource_creation.append({
        'resource_id': sid, 'resource_kind': 'shader',
        'created_at_event': -1, 'creation_chunk': 'glCreateShader',
        'declared_label': '',
    })


def _handle_shader_source(acc: _Acc, body: str, cidx: int) -> None:
    rids = _resids(body)
    sid = rids.get('shader') or rids.get('shaderId') or 0
    if not sid:
        return
    m = _RE_SHADER_SRC.search(body)
    source = m.group(1) if m else ''
    if not source:
        return
    acc.shader_sources[sid] = source
    row = acc._ensure_shader(sid)
    row['src_len'] = len(source)
    row['src_hash'] = hashlib.sha256(source.encode('utf-8')).hexdigest()[:16]
    row.update(shader_complexity(source))


def _handle_create_program(acc: _Acc, body: str, cidx: int) -> None:
    rids = _resids(body)
    pid = rids.get('real') or rids.get('program') or 0
    if not pid:
        return
    acc._ensure_program(pid)
    acc.resource_creation.append({
        'resource_id': pid, 'resource_kind': 'program',
        'created_at_event': -1, 'creation_chunk': 'glCreateProgram',
        'declared_label': '',
    })


def _handle_attach_shader(acc: _Acc, body: str, cidx: int) -> None:
    rids = _resids(body)
    pid = rids.get('program') or 0
    sid = rids.get('shader') or 0
    if not pid or not sid:
        return
    prog = acc._ensure_program(pid)
    existing = [int(x) for x in prog['attached_shader_ids'].split(';') if x]
    if sid not in existing:
        existing.append(sid)
        prog['attached_shader_ids'] = ';'.join(str(x) for x in existing)
        prog['num_attached_shaders'] = len(existing)
    sh = acc._ensure_shader(sid)
    sh_type = sh.get('shader_type', '')
    slot_map = {
        'vertex': 'vs_shader_id', 'fragment': 'fs_shader_id',
        'compute': 'cs_shader_id', 'geometry': 'gs_shader_id',
        'tess_control': 'tcs_shader_id', 'tess_evaluation': 'tes_shader_id',
    }
    if sh_type in slot_map:
        prog[slot_map[sh_type]] = sid
    linked = [int(x) for x in sh['linked_program_ids'].split(';') if x]
    if pid not in linked:
        linked.append(pid)
        sh['linked_program_ids'] = ';'.join(str(x) for x in linked)


def _handle_link_program(acc: _Acc, body: str, cidx: int) -> None:
    rids = _resids(body)
    pid = rids.get('program') or 0
    if pid:
        acc._ensure_program(pid)['linked'] = 1


def _handle_gen_resources(acc: _Acc, body: str, cidx: int, chunk_name: str) -> None:
    kind = _RESOURCE_GEN_CHUNKS[chunk_name]
    for m in _RE_RESID.finditer(body):
        rid = int(m.group(2))
        if rid == 0:
            continue
        acc.resource_creation.append({
            'resource_id': rid, 'resource_kind': kind,
            'created_at_event': -1, 'creation_chunk': chunk_name,
            'declared_label': '',
        })


def _handle_tex_storage(acc: _Acc, body: str, cidx: int, chunk_name: str) -> None:
    rids = _resids(body)
    tid = rids.get('textureId') or rids.get('texture') or rids.get('target') or 0
    if not tid:
        return
    ints = _ints(body)
    enums = _enums(body)
    row = acc._ensure_texture(tid)
    fmt = enums.get('internalformat')
    if fmt:
        row['format'] = fmt[1]
    row['width']  = ints.get('width', row['width'])
    row['height'] = ints.get('height', row['height'])
    row['depth']  = ints.get('depth', row['depth'])
    row['mip_levels'] = ints.get('levels', row['mip_levels']) or 1
    row['sample_count'] = ints.get('samples', row['sample_count']) or 1
    target = enums.get('target')
    if target:
        row['kind'] = target[1].replace('GL_TEXTURE_', 'tex_').lower()
    if chunk_name.startswith('glTexStorage'):
        row['kind'] = row['kind'] or 'tex_2d'


def _handle_buffer_data(acc: _Acc, body: str, cidx: int) -> None:
    rids = _resids(body)
    bid = rids.get('bufferId') or rids.get('buffer') or 0
    if not bid:
        return
    row = acc._ensure_buffer(bid)
    ints = _ints(body)
    enums = _enums(body)
    sz = ints.get('bytesize') or ints.get('size') or 0
    if sz > row['allocated_size_bytes']:
        row['allocated_size_bytes'] = sz
    usage = enums.get('usage')
    if usage:
        row['usage_hint'] = usage[1]
    target = enums.get('target')
    if target:
        th = [t for t in row['target_history'].split(';') if t]
        if target[1] not in th:
            th.append(target[1])
            row['target_history'] = ';'.join(th)
    row['num_glBufferData'] += 1


def _handle_sampler_parameter(acc: _Acc, body: str, cidx: int, chunk_name: str) -> None:
    rids = _resids(body)
    sid = rids.get('sampler') or 0
    if not sid:
        return
    row = acc._ensure_sampler(sid)
    enums = _enums(body)
    pname = enums.get('pname')
    if not pname:
        return
    pn = pname[1]
    param_enum = enums.get('param')
    ints = _ints(body)
    pval_int = ints.get('param')
    pval_float = None
    if 'param' in body and 'float' in body:
        m = re.search(r'<float\s+name="param"[^>]*>(-?\d*\.?\d+(?:[eE][+-]?\d+)?)</float>', body)
        if m:
            pval_float = float(m.group(1))
    pstr = param_enum[1] if param_enum else (str(pval_int) if pval_int is not None else '')
    if pn == 'GL_TEXTURE_MIN_FILTER':       row['min_filter'] = pstr
    elif pn == 'GL_TEXTURE_MAG_FILTER':      row['mag_filter'] = pstr
    elif pn == 'GL_TEXTURE_WRAP_S':          row['wrap_s'] = pstr
    elif pn == 'GL_TEXTURE_WRAP_T':          row['wrap_t'] = pstr
    elif pn == 'GL_TEXTURE_WRAP_R':          row['wrap_r'] = pstr
    elif pn == 'GL_TEXTURE_MIN_LOD':         row['mip_min_lod'] = pval_float if pval_float is not None else (pval_int or 0)
    elif pn == 'GL_TEXTURE_MAX_LOD':         row['mip_max_lod'] = pval_float if pval_float is not None else (pval_int or 0)
    elif pn == 'GL_TEXTURE_LOD_BIAS':        row['mip_lod_bias'] = pval_float if pval_float is not None else (pval_int or 0)
    elif pn == 'GL_TEXTURE_MAX_ANISOTROPY' or pn == 'GL_TEXTURE_MAX_ANISOTROPY_EXT':
        row['max_anisotropy'] = int(pval_float if pval_float is not None else (pval_int or 1))
    elif pn == 'GL_TEXTURE_COMPARE_MODE':    row['compare_mode'] = pstr
    elif pn == 'GL_TEXTURE_COMPARE_FUNC':    row['compare_func'] = pstr


def _handle_label(acc: _Acc, body: str) -> None:
    rids = _resids(body)
    rid = rids.get('Resource') or rids.get('resource') or 0
    if not rid:
        return
    strs = _strings(body)
    label = strs.get('Label') or strs.get('label') or ''
    if label:
        acc.labels[rid] = label


# --- Driver ------------------------------------------------------------------

_CHUNK_HANDLERS = {
    'glCreateShader': _handle_create_shader,
    'glShaderSource': _handle_shader_source,
    'glCreateProgram': _handle_create_program,
    'glAttachShader': _handle_attach_shader,
    'glLinkProgram': _handle_link_program,
    'glBufferData': _handle_buffer_data,
    'glBufferStorageEXT': _handle_buffer_data,
    'glLabelObjectEXT': lambda acc, body, cidx: _handle_label(acc, body),
    'glObjectLabel': lambda acc, body, cidx: _handle_label(acc, body),
}


def parse(xml_path: str) -> _Acc:
    acc = _Acc()
    for cid, cidx, cname, body in iter_chunks(xml_path):
        if cidx > acc.max_chunk_index:
            acc.max_chunk_index = cidx
        if cname in _RESOURCE_GEN_CHUNKS:
            _handle_gen_resources(acc, body, cidx, cname)
        elif cname.startswith('glTexStorage') or cname.startswith('glTexImage'):
            _handle_tex_storage(acc, body, cidx, cname)
        elif cname.startswith('glSamplerParameter'):
            _handle_sampler_parameter(acc, body, cidx, cname)
        elif cname in _CHUNK_HANDLERS:
            _CHUNK_HANDLERS[cname](acc, body, cidx)
    # apply labels to entity rows (Q-8: buffers carry no `label` column - see schemas.BUFFERS_COLS -
    # so there is nothing to apply for them; the former no-op self-assign branch was dead and removed).
    for rid, label in acc.labels.items():
        if rid in acc.textures:
            acc.textures[rid]['label'] = label
        if rid in acc.programs:
            acc.programs[rid]['label'] = label
        if rid in acc.samplers:
            acc.samplers[rid]['label'] = label
        if rid in acc.fbos:
            acc.fbos[rid]['label'] = label
    return acc


# --- CSV writers (stage layout) ---------------------------------------------

def _open_csv(path: str, fieldnames: list[str]):
    f = open(path, 'w', encoding='utf-8', newline='')
    w = csv.DictWriter(f, fieldnames=fieldnames)
    w.writeheader()
    return f, w


def _id_cols(ctx: dict) -> dict:
    return {
        'area': ctx['area'], 'drop_date': ctx['drop_date'],
        'drop_label': ctx['drop_label'], 'capture': ctx['capture'],
    }


def write_outputs(acc: _Acc, ctx: dict, capture_stage: str) -> dict[str, int]:
    """Write CSVs + shader source files under capture_stage. Returns row counts."""
    os.makedirs(capture_stage, exist_ok=True)
    shader_src_dir = os.path.join(capture_stage, 'shader_src')
    os.makedirs(shader_src_dir, exist_ok=True)

    rc_path = os.path.join(capture_stage, 'resource_creation.csv')
    sh_path = os.path.join(capture_stage, 'shaders.csv')
    pr_path = os.path.join(capture_stage, 'programs.csv')
    tx_path = os.path.join(capture_stage, 'textures.csv')
    bf_path = os.path.join(capture_stage, 'buffers.csv')
    sm_path = os.path.join(capture_stage, 'samplers.csv')
    fb_path = os.path.join(capture_stage, 'fbos.csv')

    counts: dict[str, int] = {}

    # write shader source files first so we can put paths in shaders.csv
    src_path_by_id: dict[int, str] = {}
    for sid, source in acc.shader_sources.items():
        rel = os.path.join('shader_src', f'{sid}.glsl')
        full = os.path.join(capture_stage, rel)
        with open(full, 'w', encoding='utf-8') as f:
            f.write(source)
        src_path_by_id[sid] = rel

    id_cols = _id_cols(ctx)

    from .. import schemas
    RESOURCE_CREATION_FIELDS = list(schemas.RESOURCE_CREATION_COLS)
    SHADERS_FIELDS = list(schemas.SHADERS_COLS)
    PROGRAMS_FIELDS = list(schemas.PROGRAMS_COLS)
    TEXTURES_FIELDS = list(schemas.TEXTURES_COLS)
    BUFFERS_FIELDS = list(schemas.BUFFERS_COLS)
    SAMPLERS_FIELDS = list(schemas.SAMPLERS_COLS)
    FBOS_FIELDS = list(schemas.FBOS_COLS)

    # resource_creation
    f, w = _open_csv(rc_path, RESOURCE_CREATION_FIELDS)
    n = 0
    for r in acc.resource_creation:
        row = {**id_cols, **r}
        row['declared_label'] = acc.labels.get(r['resource_id'], '')
        w.writerow(row); n += 1
    f.close(); counts['resource_creation'] = n

    # shaders
    f, w = _open_csv(sh_path, SHADERS_FIELDS)
    n = 0
    for sid, r in sorted(acc.shaders.items()):
        r = dict(r)
        r['src_file_path'] = src_path_by_id.get(sid, '')
        w.writerow({**id_cols, 'stable_key': '', **r}); n += 1
    f.close(); counts['shaders'] = n

    # programs
    f, w = _open_csv(pr_path, PROGRAMS_FIELDS)
    n = 0
    for pid, r in sorted(acc.programs.items()):
        r = dict(r)
        r['label'] = acc.labels.get(pid, '')
        w.writerow({**id_cols, 'stable_key': '', **r}); n += 1
    f.close(); counts['programs'] = n

    # textures
    f, w = _open_csv(tx_path, TEXTURES_FIELDS)
    n = 0
    for tid, r in sorted(acc.textures.items()):
        r = dict(r)
        r['label'] = acc.labels.get(tid, '')
        w.writerow({**id_cols, 'stable_key': '', **r}); n += 1
    f.close(); counts['textures'] = n

    # buffers
    f, w = _open_csv(bf_path, BUFFERS_FIELDS)
    n = 0
    for bid, r in sorted(acc.buffers.items()):
        w.writerow({**id_cols, 'stable_key': '', **r}); n += 1
    f.close(); counts['buffers'] = n

    # samplers
    f, w = _open_csv(sm_path, SAMPLERS_FIELDS)
    n = 0
    for sid, r in sorted(acc.samplers.items()):
        r = dict(r)
        r['label'] = acc.labels.get(sid, '')
        w.writerow({**id_cols, 'stable_key': '', **r}); n += 1
    f.close(); counts['samplers'] = n

    # fbos (only ones we accumulated; mostly populated by replay_main)
    f, w = _open_csv(fb_path, FBOS_FIELDS)
    n = 0
    for fid, r in sorted(acc.fbos.items()):
        w.writerow({**id_cols, 'stable_key': '', **r}); n += 1
    f.close(); counts['fbos'] = n

    # labels.json as a sidecar so replay_main can pick up labels for entities
    # it discovers (e.g. RTs not seen as raw textures at parse time).
    with open(os.path.join(capture_stage, 'labels.json'), 'w', encoding='utf-8') as f:
        json.dump({str(k): v for k, v in acc.labels.items()}, f)

    return counts


def main(argv: list[str]) -> int:
    if len(argv) < 6:
        print('usage: parse_init_state.py <zip_xml_path> <capture_stage> <area> <drop_date> <drop_label> <capture>',
              file=sys.stderr)
        return 2
    xml_path, capture_stage, area, drop_date, drop_label, capture = argv[:6]
    ctx = {'area': area, 'drop_date': drop_date, 'drop_label': drop_label, 'capture': capture}
    t0 = time.monotonic()
    acc = parse(xml_path)
    counts = write_outputs(acc, ctx, capture_stage)
    elapsed = time.monotonic() - t0
    print(f'parse_init_state: {os.path.basename(xml_path)} -> {sum(counts.values())} rows in {elapsed:.1f}s; per-table {counts}')
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
