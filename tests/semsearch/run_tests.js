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

console.log(`${pass}/${pass + fail} semsearch filter cases pass`);
process.exit(fail ? 1 : 0);
