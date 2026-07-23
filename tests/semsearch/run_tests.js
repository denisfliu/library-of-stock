// Regression test for the semantic-search filter chain: the category-
// bundle expansion in lib/js/semsearch.js (a port of lib/mirror/query.py
// _expand_category_bundle) and the Worker's row filtering in
// sync/worker.js (buildRowFilter / rowPasses, a port of _build_where).
// Executes the REAL functions sliced out of both files against synthetic
// index rows. Run: node tests/semsearch/run_tests.js
'use strict';
const fs = require('fs');
const path = require('path');
const vm = require('vm');

function slice(src, startMarker, endMarker, label) {
  const i = src.indexOf(startMarker);
  const j = src.indexOf(endMarker, i);
  if (i < 0 || j < 0) throw new Error('marker not found in ' + label + ': ' + startMarker);
  return src.slice(i, j);
}

/* ---- taxonomy fixture (subset of lib/mirror/query.py's tables) ---- */
const CFG = {
  cats: ['Literature', 'Science', 'Fine Arts', 'Mythology'],
  subs: ['American Literature', 'Other Literature', 'Biology', 'Other Science',
         'Visual Fine Arts', 'Other Fine Arts', 'Mythology'],
  alts: ['Drama', 'Poetry', 'Math', 'Computer Science', 'Opera', 'Film'],
  catToSubs: {
    'Literature': ['American Literature', 'Other Literature'],
    'Science': ['Biology', 'Other Science'],
    'Fine Arts': ['Visual Fine Arts', 'Other Fine Arts'],
    'Mythology': ['Mythology'],
  },
  catToAlts: {
    'Literature': ['Drama', 'Poetry'],
    'Science': ['Math', 'Computer Science'],
    'Fine Arts': ['Opera', 'Film'],
  },
  subToCat: {
    'American Literature': 'Literature', 'Other Literature': 'Literature',
    'Biology': 'Science', 'Other Science': 'Science',
    'Visual Fine Arts': 'Fine Arts', 'Other Fine Arts': 'Fine Arts',
    'Mythology': 'Mythology',
  },
  altToCat: {
    'Drama': 'Literature', 'Poetry': 'Literature',
    'Math': 'Science', 'Computer Science': 'Science',
    'Opera': 'Fine Arts', 'Film': 'Fine Arts',
  },
};

/* ---- slice the page's expansion ---- */
const pageSrc = fs.readFileSync(path.join(__dirname, '../../lib/js/semsearch.js'), 'utf8');
const pageCtx = vm.createContext({ CFG, Number, Array, Object });
vm.runInContext(
  slice(pageSrc, 'function expandBundle(', '\n/* ---------- session', 'semsearch.js') +
  '\n; globalThis.__page = { expandBundle, bundleOrdinals };',
  pageCtx, { filename: 'semsearch.js (sliced)' });
const page = pageCtx.__page;

/* ---- slice the Worker's filter ---- */
const workerSrc = fs.readFileSync(path.join(__dirname, '../../sync/worker.js'), 'utf8');
const workerCtx = vm.createContext({ Number, Array, Object, Uint8Array, Math });
vm.runInContext(
  'const ORD_NULL = 255;\n' +
  slice(workerSrc, 'function ordMask(', '\nasync function search(', 'worker.js') +
  '\n; globalThis.__worker = { buildRowFilter, rowPasses };',
  workerCtx, { filename: 'worker.js (sliced)' });
const worker = workerCtx.__worker;

/* ---- helpers ---- */
let pass = 0, fail = 0;
const check = (label, cond, detail) => {
  if (cond) { pass++; }
  else { fail++; console.error('FAIL ' + label + (detail ? ' — ' + detail : '')); }
};

// One synthetic index row: 20B meta prefix, layout per build_search_index.py.
function row({ kind = 0, sidx = 0, setOrd = 0, cat = 255, sub = 255,
               alt = 255, diff = 255 }) {
  const b = new Uint8Array(20);
  b[12] = kind; b[13] = sidx;
  b[14] = setOrd & 0xFF; b[15] = setOrd >> 8;
  b[16] = cat; b[17] = sub; b[18] = alt; b[19] = diff;
  return b;
}
const manifest = {
  set_years: [2015, 2022, 0],
  set_names: ['2015 ACF Regionals', '2022 ACF Winter', 'Mystery Set'],
};
const filterFor = body => worker.buildRowFilter(body, manifest);
const passes = (f, r) => worker.rowPasses(f, r, 0);

/* ---- expansion semantics (query.py parity) ---- */
let b = page.expandBundle([], [], []);
check('nothing selected -> null', b === null);

b = page.expandBundle(['Science'], [], []);
check('cat only -> all its subs', JSON.stringify(b.subs.sort()) ===
  JSON.stringify(['Biology', 'Other Science']), JSON.stringify(b));
check('cat only -> all its alts', JSON.stringify(b.alts.sort()) ===
  JSON.stringify(['Computer Science', 'Math']), JSON.stringify(b));

b = page.expandBundle([], ['Other Science'], []);
check('sub implies cat', b.cats.includes('Science'), JSON.stringify(b));
check('sub pick narrows subs', JSON.stringify(b.subs) === '["Other Science"]',
  JSON.stringify(b));
check('sub pick still fills alts', b.alts.includes('Math') && b.alts.includes('Computer Science'),
  JSON.stringify(b));

b = page.expandBundle([], [], ['Opera']);
check('alt implies cat + all subs', b.cats.includes('Fine Arts') &&
  b.subs.includes('Visual Fine Arts') && b.subs.includes('Other Fine Arts'),
  JSON.stringify(b));
check('alt pick narrows alts', JSON.stringify(b.alts) === '["Opera"]', JSON.stringify(b));

b = page.expandBundle(['Mythology'], [], ['Math']);
check('cross-category picks compose', b.cats.includes('Science') &&
  b.subs.includes('Mythology') && JSON.stringify(b.alts) === '["Math"]',
  JSON.stringify(b));

/* ---- worker row filtering ---- */
check('no filters -> null (unfiltered scan)', filterFor({}) === null);

// bundle via the real expansion: Science with only Math picked
const ords = page.bundleOrdinals(page.expandBundle([], [], ['Math']));
let f = filterFor(ords);
const CAT = n => CFG.cats.indexOf(n), SUB = n => CFG.subs.indexOf(n),
      ALT = n => CFG.alts.indexOf(n);
check('math row passes', passes(f, row({ cat: CAT('Science'), sub: SUB('Other Science'), alt: ALT('Math') })));
check('CS row fails (alt not picked)', !passes(f, row({ cat: CAT('Science'), sub: SUB('Other Science'), alt: ALT('Computer Science') })));
check('null-alt quirk: bio row passes', passes(f, row({ cat: CAT('Science'), sub: SUB('Biology'), alt: 255 })));
check('off-taxonomy alt (254) fails', !passes(f, row({ cat: CAT('Science'), sub: SUB('Biology'), alt: 254 })));
check('other category fails', !passes(f, row({ cat: CAT('Literature'), sub: SUB('American Literature'), alt: 255 })));
check('missing meta (cat=255) fails under bundle', !passes(f, row({})));

f = filterFor({ diffs: [7, 8] });
check('difficulty in', passes(f, row({ diff: 7 })));
check('difficulty out', !passes(f, row({ diff: 4 })));
check('difficulty unknown (255) out', !passes(f, row({})));

f = filterFor({ qtype: 'tossup' });
check('qtype tossup keeps sentences', passes(f, row({ kind: 0 })));
check('qtype tossup drops bonus parts', !passes(f, row({ kind: 1 })));

f = filterFor({ minYear: 2020 });
check('year filter keeps 2022 set', passes(f, row({ setOrd: 1 })));
check('year filter drops 2015 set', !passes(f, row({ setOrd: 0 })));
check('year filter drops unknown-year set', !passes(f, row({ setOrd: 2 })));
check('year filter drops unknown set ordinal', !passes(f, row({ setOrd: 0xFFFF })));

f = filterFor({ set: 'acf winter' });
check('set substring keeps its set', passes(f, row({ setOrd: 1 })));
check('set substring drops others', !passes(f, row({ setOrd: 0 })));

f = filterFor({ qtype: 'bonus', diffs: [9], minYear: 2020, ...page.bundleOrdinals(page.expandBundle(['Fine Arts'], [], [])) });
check('all filters compose (pass)', passes(f, row({ kind: 1, diff: 9, setOrd: 1, cat: CAT('Fine Arts'), sub: SUB('Visual Fine Arts'), alt: ALT('Film') })));
check('all filters compose (one miss fails)', !passes(f, row({ kind: 0, diff: 9, setOrd: 1, cat: CAT('Fine Arts'), sub: SUB('Visual Fine Arts'), alt: ALT('Film') })));

/* ---- clue_search.js: the in-browser engine (port of the Worker) ---- */
const clueSrc = fs.readFileSync(path.join(__dirname, '../../lib/js/clue_search.js'), 'utf8');
const clueCtx = vm.createContext({
  window: {},
  localStorage: { getItem: () => null, setItem: () => {} },
  navigator: {},
  QDATA_BASE: '',
  fetch: () => Promise.reject(new Error('no network in tests')),
  Number, Array, Object, Math, JSON, String, Promise,
  Uint8Array, Uint16Array, Float32Array,
});
vm.runInContext(clueSrc, clueCtx, { filename: 'clue_search.js' });
const clue = clueCtx.window.losClueSearch._test;

// filter parity: identical verdicts to the Worker on every body x row
{
  const bodies = [
    {}, ords, { diffs: [7, 8] }, { qtype: 'tossup' }, { qtype: 'bonus' },
    { minYear: 2020 }, { maxYear: 2016 }, { set: 'acf winter' },
    { qtype: 'bonus', diffs: [9], minYear: 2020,
      ...page.bundleOrdinals(page.expandBundle(['Fine Arts'], [], [])) },
  ];
  const rows = [
    row({}), row({ kind: 1 }), row({ diff: 7 }), row({ diff: 9, kind: 1, setOrd: 1 }),
    row({ setOrd: 0 }), row({ setOrd: 1 }), row({ setOrd: 2 }), row({ setOrd: 0xFFFF }),
    row({ cat: CAT('Science'), sub: SUB('Other Science'), alt: ALT('Math') }),
    row({ cat: CAT('Science'), sub: SUB('Biology'), alt: 255 }),
    row({ cat: CAT('Science'), sub: SUB('Biology'), alt: 254 }),
    row({ cat: CAT('Fine Arts'), sub: SUB('Visual Fine Arts'), alt: ALT('Film'), kind: 1, diff: 9, setOrd: 1 }),
  ];
  let agree = true, detail = '';
  for (const body of bodies) {
    const fw = worker.buildRowFilter(body, manifest);
    const fc = clue.buildRowFilter(body, manifest);
    if ((fw === null) !== (fc === null)) { agree = false; detail = 'null mismatch ' + JSON.stringify(body); break; }
    if (fw === null) continue;
    for (let i = 0; i < rows.length; i++) {
      if (worker.rowPasses(fw, rows[i], 0) !== clue.rowPasses(fc, rows[i], 0)) {
        agree = false;
        detail = 'body ' + JSON.stringify(body) + ' row ' + i;
        break;
      }
    }
    if (!agree) break;
  }
  check('port parity: buildRowFilter/rowPasses agree with the Worker', agree, detail);
}

// scan correctness: scanBuffers vs an independent naive reference
{
  // deterministic PRNG so the fixture is stable
  let seed = 0x9e3779b9;
  const rand = () => {
    seed |= 0; seed = seed + 0x6D2B79F5 | 0;
    let t = Math.imul(seed ^ seed >>> 15, 1 | seed);
    t = t + Math.imul(t ^ t >>> 7, 61 | t) ^ t;
    return ((t ^ t >>> 14) >>> 0) / 4294967296;
  };
  const f16Encode = v => {  // f32 -> f16 bits (round-to-nearest, normals only)
    const f32 = new Float32Array(1); f32[0] = v;
    const bits = new Uint32Array(f32.buffer)[0];
    const sign = (bits >>> 16) & 0x8000;
    let exp = ((bits >>> 23) & 0xFF) - 127 + 15;
    let frac = (bits >>> 13) & 0x3FF;
    if ((bits & 0x1FFF) > 0x1000) { frac++; if (frac === 0x400) { frac = 0; exp++; } }
    if (exp <= 0) return sign;                    // fixture stays in normal range
    return sign | (exp << 10) | frac;
  };
  const f16Decode = h => {
    const s = (h & 0x8000) >> 15, e = (h & 0x7C00) >> 10, f = h & 0x3FF;
    const v = e === 0 ? f * Math.pow(2, -24) : (1 + f / 1024) * Math.pow(2, e - 15);
    return s ? -v : v;
  };

  const DIMS = 1024, RD = 16, ROWB = 20 + 128 + 2 + RD, N = 40;
  const man = {
    dims: DIMS, meta_bytes: 20, row_bytes: ROWB, rerank_top: 8, rerank_dims: RD,
    set_slugs: ['set_a'], set_names: ['Set A'], set_years: [2021],
    categories: ['Literature'], subcategories: ['American Literature'],
    alternate_subcategories: [],
  };
  const popcnt = new Uint8Array(256);
  for (let i = 1; i < 256; i++) popcnt[i] = (i & 1) + popcnt[i >> 1];

  const buf = new ArrayBuffer(N * ROWB);
  const bytes = new Uint8Array(buf);
  const rowsRef = [];
  for (let i = 0; i < N; i++) {
    const off = i * ROWB;
    bytes[off] = i;                       // id: first byte carries the index
    bytes[off + 12] = 0; bytes[off + 13] = i & 0xFF;
    bytes[off + 14] = 0; bytes[off + 15] = 0;
    bytes[off + 16] = 0; bytes[off + 17] = 0; bytes[off + 18] = 255;
    bytes[off + 19] = i % 2 ? 7 : 4;
    const v = new Float32Array(DIMS);
    for (let d = 0; d < DIMS; d++) v[d] = rand() * 2 - 1;
    const code = new Uint8Array(128);
    for (let d = 0; d < DIMS; d++) if (v[d] > 0) code[d >> 3] |= 128 >> (d & 7);
    bytes.set(code, off + 20);
    // int8 rerank tier: first RD dims renormalized, symmetric quantization
    let n2 = 0;
    for (let d = 0; d < RD; d++) n2 += v[d] * v[d];
    n2 = Math.sqrt(n2) || 1;
    let mx = 0;
    for (let d = 0; d < RD; d++) mx = Math.max(mx, Math.abs(v[d] / n2));
    const scale = Math.max(mx, 1e-9) / 127;
    const h = f16Encode(scale);
    bytes[off + 148] = h & 0xFF; bytes[off + 149] = h >> 8;
    const q8 = new Int8Array(RD);
    for (let d = 0; d < RD; d++) {
      q8[d] = Math.round(v[d] / n2 / scale);
      bytes[off + 150 + d] = q8[d] & 0xFF;
    }
    rowsRef.push({ i, code, q8, scale16: f16Decode(h), diff: bytes[off + 19] });
  }

  const vec = new Float32Array(DIMS);
  for (let d = 0; d < DIMS; d++) vec[d] = rand() * 2 - 1;

  const reference = filterFn => {
    const qbits = new Uint8Array(128);
    for (let d = 0; d < DIMS; d++) if (vec[d] > 0) qbits[d >> 3] |= 128 >> (d & 7);
    const cands = rowsRef.filter(filterFn).map(r => {
      let dist = 0;
      for (let b2 = 0; b2 < 128; b2++) dist += popcnt[r.code[b2] ^ qbits[b2]];
      return { r, dist };
    });
    cands.sort((a, b2) => a.dist - b2.dist);
    cands.length = Math.min(cands.length, man.rerank_top);
    let qn = 0;
    for (let d = 0; d < RD; d++) qn += vec[d] * vec[d];
    qn = Math.sqrt(qn) || 1;
    for (const c of cands) {
      let dot = 0;
      for (let d = 0; d < RD; d++) dot += c.r.q8[d] * (vec[d] / qn);
      c.score = Math.round(dot * c.r.scale16 * 1000) / 1000;
    }
    cands.sort((a, b2) => b2.score - a.score);
    return cands;
  };

  const got = clue.scanBuffers(vec, null, man, [buf], popcnt);
  const want = reference(() => true);
  check('scan: result count = rerank_top', got.length === want.length,
    got.length + ' vs ' + want.length);
  let same = got.length === want.length;
  for (let i = 0; same && i < got.length; i++) {
    if (parseInt(got[i].id.slice(0, 2), 16) !== want[i].r.i) { same = false; break; }
    if (got[i].score !== want[i].score) { same = false; break; }
  }
  check('scan: ranking + scores match the naive reference', same,
    JSON.stringify(got.map(g => [g.id.slice(0, 2), g.score])) + ' vs '
    + JSON.stringify(want.map(w => [w.r.i.toString(16).padStart(2, '0'), w.score])));
  check('scan: meta decodes (set/cat/diff/year)',
    got[0].set === 'set_a' && got[0].cat === 'Literature'
    && got[0].year === 2021 && (got[0].diff === 7 || got[0].diff === 4),
    JSON.stringify(got[0]));

  // filtered scan drops rows BEFORE ranking (top-K within the filter)
  const fc = clue.buildRowFilter({ diffs: [7] }, man);
  const gotF = clue.scanBuffers(vec, fc, man, [buf], popcnt);
  const wantF = reference(r => r.diff === 7);
  let sameF = gotF.length === wantF.length && gotF.every(g => g.diff === 7);
  for (let i = 0; sameF && i < gotF.length; i++) {
    if (parseInt(gotF[i].id.slice(0, 2), 16) !== wantF[i].r.i
        || gotF[i].score !== wantF[i].score) sameF = false;
  }
  check('filtered scan matches reference within the filter', sameF,
    JSON.stringify(gotF.map(g => [g.id.slice(0, 2), g.diff])));
}

console.log(`${pass}/${pass + fail} semsearch filter + local-engine cases pass`);
process.exit(fail ? 1 : 0);
