// clue_search.js — one clue-search call, two backends. Shared by
// reader.html (clue panel + missed-clues report) and search.html.
//
//   cloud — POST /search on the sync Worker (sign-in gated; the Worker
//           embeds the query with Workers AI and scans the R2 index).
//   local — the same pipeline entirely in this browser: transformers.js
//           embeds the query with the same model (onnx-community ONNX
//           build of Qwen3-Embedding-0.6B, q8, ~600 MB, cached by the
//           browser after the first download), then the IVF-binary scan
//           runs client-side with HTTP range reads against the public
//           data bucket. No sign-in, no Worker involvement.
//
// The local scan is a port of sync/worker.js /search and MUST stay in
// lockstep with it (tests/semsearch/run_tests.js exercises the shared
// pieces against synthetic rows). The mode is per-device (localStorage,
// shared across pages) and deliberately NOT synced in prefs: the model
// download is a per-device commitment.
//
// Load order: after lib/js/qdata.js (QDATA_BASE), before page scripts.
window.losClueSearch = (function () {
'use strict';

const MODE_KEY = 'losClueSearchV1';
const TJS_URL = 'https://cdn.jsdelivr.net/npm/@huggingface/transformers@3.7.5/+esm';
const EMBED_MODEL = 'onnx-community/Qwen3-Embedding-0.6B-ONNX';
// Same query instruction the corpus index was evaluated with (worker.js).
const QUERY_PREFIX = 'Instruct: Given a web search query, retrieve relevant '
  + 'passages that answer the query\nQuery: ';
const NPROBE = 24, NPROBE_FILTERED = 40, TOPK = 40, MAX_QUERY_CHARS = 500;
const CODE_BYTES = 128;
const ORD_NULL = 255;
const PART_CACHE_MAX = 64;  // ~0.7 MB per partition — bounded scan cache

/* ---------- ports from sync/worker.js (keep in lockstep) ---------- */
function f16One(bytes, off) {
  const h = bytes[off] | (bytes[off + 1] << 8);
  const s = (h & 0x8000) >> 15, e = (h & 0x7C00) >> 10, f = h & 0x3FF;
  let v;
  if (e === 0) v = f * Math.pow(2, -24);
  else if (e === 31) v = f ? NaN : Infinity;
  else v = (1 + f / 1024) * Math.pow(2, e - 15);
  return s ? -v : v;
}

function f16ToF32(bytes) {
  const n = bytes.length / 2;
  const u16 = new Uint16Array(bytes.buffer, bytes.byteOffset, n);
  const out = new Float32Array(n);
  for (let i = 0; i < n; i++) {
    const h = u16[i], s = (h & 0x8000) >> 15, e = (h & 0x7C00) >> 10, f = h & 0x3FF;
    let v;
    if (e === 0) v = f * Math.pow(2, -24);
    else if (e === 31) v = f ? NaN : Infinity;
    else v = (1 + f / 1024) * Math.pow(2, e - 15);
    out[i] = s ? -v : v;
  }
  return out;
}

const HEX = '0123456789abcdef';
function rowIdHex(bytes, off) {
  let s = '';
  for (let i = 0; i < 12; i++) { const b = bytes[off + i]; s += HEX[b >> 4] + HEX[b & 15]; }
  return s;
}

function ordMask(list) {
  const m = new Uint8Array(256);
  for (const v of list) if (Number.isInteger(v) && v >= 0 && v < 256) m[v] = 1;
  return m;
}

function buildRowFilter(body, manifest) {
  const cats = Array.isArray(body.cats) ? body.cats : [];
  const subs = Array.isArray(body.subs) ? body.subs : [];
  const alts = Array.isArray(body.alts) ? body.alts : [];
  const diffs = Array.isArray(body.diffs) ? body.diffs : [];
  const qtype = body.qtype === 'tossup' ? 0 : body.qtype === 'bonus' ? 1 : -1;
  const minYear = Number.isInteger(body.minYear) ? body.minYear : null;
  const maxYear = Number.isInteger(body.maxYear) ? body.maxYear : null;
  const setQuery = typeof body.set === 'string' ? body.set.trim().toLowerCase() : '';

  const hasBundle = cats.length > 0;
  const needSetPass = minYear !== null || maxYear !== null || setQuery !== '';
  if (!hasBundle && !diffs.length && qtype < 0 && !needSetPass) return null;

  const f = { qtype, hasBundle };
  if (hasBundle) {
    f.catOK = ordMask(cats);
    f.subOK = ordMask(subs);
    f.altOK = ordMask(alts);
  }
  f.diffOK = diffs.length ? ordMask(diffs) : null;
  if (needSetPass) {
    const years = manifest.set_years || [];
    const names = manifest.set_names || [];
    const n = Math.max(years.length, names.length);
    const setOK = new Uint8Array(n);
    for (let i = 0; i < n; i++) {
      const y = years[i] || 0;
      if (minYear !== null && (!y || y < minYear)) continue;
      if (maxYear !== null && (!y || y > maxYear)) continue;
      if (setQuery && !(names[i] || '').toLowerCase().includes(setQuery)) continue;
      setOK[i] = 1;
    }
    f.setOK = setOK;
  }
  return f;
}

function rowPasses(f, bytes, off) {
  if (f.qtype >= 0 && bytes[off + 12] !== f.qtype) return false;
  if (f.setOK) {
    const so = bytes[off + 14] | (bytes[off + 15] << 8);
    if (so >= f.setOK.length || !f.setOK[so]) return false;
  }
  if (f.hasBundle) {
    if (!f.catOK[bytes[off + 16]]) return false;
    if (!f.subOK[bytes[off + 17]]) return false;
    const alt = bytes[off + 18];
    if (alt !== ORD_NULL && !f.altOK[alt]) return false;
  }
  if (f.diffOK && !f.diffOK[bytes[off + 19]]) return false;
  return true;
}

// Stages 1+2 of the worker's scan over already-fetched partition buffers:
// Hamming over the binary codes, then the int8 rerank tier carried in each
// row. Returns the top results in the Worker's JSON shape.
function scanBuffers(vec, filter, manifest, bufs, popcnt) {
  const dims = manifest.dims;
  const metaBytes = manifest.meta_bytes || 16;
  const rowBytes = manifest.row_bytes;
  const rerankTop = manifest.rerank_top || 200;

  const qbits = new Uint8Array(CODE_BYTES);
  for (let d = 0; d < dims; d++) if (vec[d] > 0) qbits[d >> 3] |= 128 >> (d & 7);

  const cands = [];
  for (const buf of bufs) {
    const bytes = new Uint8Array(buf);
    for (let off = 0; off + rowBytes <= bytes.length; off += rowBytes) {
      if (filter && !rowPasses(filter, bytes, off)) continue;
      let dist = 0;
      for (let i = 0; i < CODE_BYTES; i++)
        dist += popcnt[bytes[off + metaBytes + i] ^ qbits[i]];
      cands.push({ dist, bytes, off });
    }
  }
  cands.sort((a, b) => a.dist - b.dist);
  cands.length = Math.min(cands.length, rerankTop);

  const RD = manifest.rerank_dims || 512;
  const qr = new Float32Array(RD);
  let qn = 0;
  for (let d = 0; d < RD; d++) qn += vec[d] * vec[d];
  qn = Math.sqrt(qn) || 1;
  for (let d = 0; d < RD; d++) qr[d] = vec[d] / qn;
  for (const c of cands) {
    const scaleOff = c.off + metaBytes + CODE_BYTES;
    const scale = f16One(c.bytes, scaleOff);
    let dot = 0;
    const base = scaleOff + 2;
    for (let d = 0; d < RD; d++) {
      let v = c.bytes[base + d];
      if (v > 127) v -= 256;
      dot += v * qr[d];
    }
    c.score = dot * scale;
  }
  cands.sort((a, b) => b.score - a.score);

  const named = (list, ord) =>
    (ord === undefined || ord >= 254) ? null : (list && list[ord]) || null;
  return cands.slice(0, TOPK).map(c => {
    const off = c.off, b = c.bytes;
    const setOrd = b[off + 14] | (b[off + 15] << 8);
    const out = {
      id: rowIdHex(b, off),
      kind: b[off + 12],
      s: b[off + 13],
      set: manifest.set_slugs[setOrd] || null,
      score: Math.round(c.score * 1000) / 1000,
    };
    if (metaBytes >= 20) {
      out.cat = named(manifest.categories, b[off + 16]);
      out.sub = named(manifest.subcategories, b[off + 17]);
      out.alt = named(manifest.alternate_subcategories, b[off + 18]);
      out.diff = b[off + 19] === ORD_NULL ? null : b[off + 19];
      out.year = (manifest.set_years || [])[setOrd] || null;
    }
    return out;
  });
}
/* ---------- end of worker.js ports ---------- */

/* ---------- progress relay ----------
   One page-level listener (settings UI). Model download events aggregate
   the per-file transformers.js callbacks into a single MB counter. */
let _progressCb = null;
function onProgress(cb) { _progressCb = cb; }
function report(info) { if (_progressCb) try { _progressCb(info); } catch (e) {} }

const _files = new Map();  // file -> {loaded, total} for weight downloads
function modelProgress(p) {
  if (!p || !p.file || !/\.onnx/.test(p.file)) return;
  if (p.status === 'progress') _files.set(p.file, { loaded: p.loaded || 0, total: p.total || 0 });
  else if (p.status === 'done') {
    const f = _files.get(p.file);
    if (f) f.loaded = f.total;
  } else return;
  let loaded = 0, total = 0;
  for (const f of _files.values()) { loaded += f.loaded; total += f.total; }
  if (total) report({
    phase: 'model',
    loadedMB: Math.round(loaded / 1e6),
    totalMB: Math.round(total / 1e6),
  });
}

/* ---------- local backend ---------- */
let _index = null;
function loadIndex() {
  if (_index) return _index;
  _index = Promise.all([
    fetch(QDATA_BASE + '/search/search_manifest.json').then(r => {
      if (!r.ok) throw new Error('HTTP ' + r.status);
      return r.json();
    }),
    fetch(QDATA_BASE + '/search/centroids.f16').then(r => {
      if (!r.ok) throw new Error('HTTP ' + r.status);
      return r.arrayBuffer();
    }),
  ]).then(([manifest, cbuf]) => {
    const centroids = f16ToF32(new Uint8Array(cbuf));
    const popcnt = new Uint8Array(256);
    for (let i = 1; i < 256; i++) popcnt[i] = (i & 1) + popcnt[i >> 1];
    return { manifest, centroids, popcnt };
  });
  _index.catch(() => { _index = null; });
  return _index;
}

let _pipe = null;
function loadEmbedder() {
  if (_pipe) return _pipe;
  _pipe = import(TJS_URL).then(tjs =>
    // WASM backend ONLY. q8 weights on WebGPU run with fp16 accumulation
    // and the embeddings come out wrong — searches were "completely off"
    // (Denis, July 2026). WASM+q8 is the parity-validated path (top-10
    // overlap 9/10 vs the corpus pipeline). Revisit WebGPU (fp16/q4f16
    // dtypes) only behind an in-page parity check against known vectors.
    tjs.pipeline('feature-extraction', EMBED_MODEL, {
      dtype: 'q8', device: 'wasm', progress_callback: modelProgress,
    })
  ).then(pipe => { report({ phase: 'ready' }); return pipe; });
  _pipe.catch(() => { _pipe = null; });
  return _pipe;
}

async function embedQuery(q) {
  const pipe = await loadEmbedder();
  const out = await pipe([QUERY_PREFIX + q], { pooling: 'last_token', normalize: true });
  const dims = out.dims[out.dims.length - 1];
  return out.data.subarray(0, dims);
}

// Partition slices cached across searches (a missed-clues report fires
// many related queries whose probe sets overlap heavily). FIFO-bounded.
const _parts = new Map();  // 'bundle/offset' -> ArrayBuffer
function rangeRead(bundle, offset, length) {
  const key = bundle + '/' + offset;
  if (_parts.has(key)) return Promise.resolve(_parts.get(key));
  const url = QDATA_BASE + '/search/bundle_' + String(bundle).padStart(2, '0') + '.bin';
  return fetch(url, { headers: { Range: 'bytes=' + offset + '-' + (offset + length - 1) } })
    .then(r => {
      if (r.status === 206) return r.arrayBuffer();
      // A server that ignores Range answers 200 with the whole object.
      if (r.ok) return r.arrayBuffer().then(b => b.slice(offset, offset + length));
      throw new Error('HTTP ' + r.status);
    })
    .then(buf => {
      if (_parts.size >= PART_CACHE_MAX) _parts.delete(_parts.keys().next().value);
      _parts.set(key, buf);
      return buf;
    });
}

async function localSearch(q, body) {
  const [idx, vec] = await Promise.all([loadIndex(), embedQuery(q)]);
  const { manifest, centroids, popcnt } = idx;
  if (vec.length !== manifest.dims) throw new Error('embedding failed');
  const metaBytes = manifest.meta_bytes || 16;
  const filter = buildRowFilter(body || {}, manifest);
  if (filter && metaBytes < 20) throw new Error('published index predates filters');

  const dims = manifest.dims, k = manifest.k;
  const nprobe = filter ? NPROBE_FILTERED : NPROBE;
  const scores = new Float32Array(k);
  for (let c = 0; c < k; c++) {
    let dot = 0; const base = c * dims;
    for (let d = 0; d < dims; d++) dot += centroids[base + d] * vec[d];
    scores[c] = dot;
  }
  const probes = Array.from(scores.keys())
    .sort((a, b) => scores[b] - scores[a]).slice(0, nprobe);

  const reads = probes
    .map(p => manifest.parts[p])
    .filter(part => part[2] > 0)
    .map(part => rangeRead(part[0], part[1], part[2]).catch(() => null));
  const bufs = (await Promise.all(reads)).filter(Boolean);

  return { q, filtered: !!filter, results: scanBuffers(vec, filter, manifest, bufs, popcnt) };
}

/* ---------- cloud backend ---------- */
let cfg = { syncBase: null, getAuth: null };
function configure(c) { Object.assign(cfg, c); }

function cloudSearch(q, body) {
  const base = typeof cfg.syncBase === 'function' ? cfg.syncBase() : cfg.syncBase;
  const auth = cfg.getAuth ? cfg.getAuth() : null;
  if (!base || !auth) {
    const e = new Error('sign in required');
    e.signin = true;
    return Promise.reject(e);
  }
  return fetch(base + '/search', {
    method: 'POST',
    headers: Object.assign({ 'Content-Type': 'application/json' }, auth),
    body: JSON.stringify(Object.assign({ q }, body || {})),
  }).then(r => {
    if (r.status === 401) { const e = new Error('session expired'); e.signin = true; throw e; }
    if (!r.ok) return r.json().catch(() => ({})).then(b => {
      throw new Error(b.error || ('HTTP ' + r.status));
    });
    return r.json();
  });
}

/* ---------- public surface ---------- */
function mode() {
  try { return localStorage.getItem(MODE_KEY) === 'local' ? 'local' : 'cloud'; }
  catch (e) { return 'cloud'; }
}
function setMode(m) {
  try { localStorage.setItem(MODE_KEY, m === 'local' ? 'local' : 'cloud'); } catch (e) {}
}

function search(q, body) {
  q = String(q || '').trim().slice(0, MAX_QUERY_CHARS);
  if (!q) return Promise.reject(new Error('empty query'));
  return mode() === 'local' ? localSearch(q, body) : cloudSearch(q, body);
}

// Kick off the model + index downloads without a query (mode toggle).
function prepare() {
  if (mode() !== 'local') return Promise.resolve();
  return Promise.all([loadIndex(), loadEmbedder()]).then(() => {});
}

return {
  mode, setMode, configure, search, prepare, onProgress,
  // sliced by tests/semsearch/run_tests.js
  _test: { f16One, f16ToF32, buildRowFilter, rowPasses, scanBuffers, rowIdHex, ordMask },
};
})();
