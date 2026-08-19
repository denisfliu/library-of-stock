// Regression test for the reader's stats filtering engine (lib/js/reader.js:
// statsScope/scopedLog/facetVals/pruneScope/compositeKey/aggBy). Scope facets
// are multi-select sets (empty = all; union within a facet, intersection
// across facets); facetVals offers each facet's options under the OTHER
// facets; pruneScope drops finer picks orphaned by a coarser deselection;
// the breakdown groups by every active dimension via compositeKey.
// Run: node tests/reader_stats/run_tests.js
'use strict';
const fs = require('fs');
const path = require('path');
const vm = require('vm');
const src = fs.readFileSync(path.join(__dirname, '../../lib/js/reader.js'), 'utf8');

function slice(startMarker, endMarker) {
  const i = src.indexOf(startMarker);
  const j = src.indexOf(endMarker, i);
  if (i < 0 || j < 0) throw new Error('marker not found: ' + startMarker);
  return src.slice(i, j);
}

const preamble = `
let LOG = [];
`;
const code = [
  preamble,
  slice('// --- stats state ---', '\nconst pctCol'),
  slice('/* ---------- progress over time ----------', '\n// hover x in canvas px'),
].join('\n') + `
; globalThis.__api = {
  statsScope, statsDims, scopedLog, facetVals, pruneScope, compositeKey,
  aggBy, KEY_SEP, DIM_ORDER,
  wilson, rollup, progState, progWindow, clampWindow, WIN_MIN,
  progressBlock, PROG_MIN_ROWS,
  setLog: rows => { LOG = rows; },
};`;

const ctx = vm.createContext({
  console, Set, Map, Object, Array, JSON, Number, String, Math, Float64Array,
});
ctx.globalThis = ctx;
vm.runInContext(code, ctx, { filename: 'reader.js (sliced)' });
const api = ctx.__api;

const row = (cat, sub, section, diff, res, bf) =>
  ({ cat, sub, section, diff, res: res || 'C', bf: bf == null ? 0.5 : bf });
const FIXTURE = [
  row('Literature', 'American Literature', 'Modernism', 2),
  row('Literature', 'American Literature', 'Modernism', 3, 'W'),
  row('Literature', 'American Literature', 'Poetry', 3, 'D', null),
  row('Literature', 'British Literature', 'Romanticism', 2),
  row('Literature', 'British Literature', 'Romanticism', 4, 'C', 0.2),
  row('History', 'European History', 'WWII', 3),
  row('History', 'European History', 'WWII', 3, 'W'),
  row('History', 'American History', null, 2, 'D', null),
  row('Science', 'Biology', 'Genetics', 5),
];
api.setLog(FIXTURE);

function resetScope() { for (const f of api.DIM_ORDER) api.statsScope[f].clear(); }

let pass = 0, fail = 0;
function check(name, cond) {
  if (cond) { pass++; console.log('  ok  ' + name); }
  else { fail++; console.log('FAIL  ' + name); }
}

/* 1. empty scope = all */
resetScope();
check('empty scope -> whole log', api.scopedLog().length === FIXTURE.length);

/* 2. union within a facet, intersection across facets */
api.statsScope.cat.add('Literature').add('History');
check('two cats -> union', api.scopedLog().length === 8);
api.statsScope.diff.add('3');
check('cats + diff -> intersection', api.scopedLog().length === 4);
api.statsScope.diff.add('2');
check('two diffs -> union within facet', api.scopedLog().length === 7);
api.statsScope.sub.add('American Literature');
check('sub narrows further', api.scopedLog().length === 3);

/* 3. section scope; null sections never match a section pick */
resetScope();
api.statsScope.section.add('WWII').add('Modernism');
check('section scope -> only picked groups', api.scopedLog().length === 4);
check('null section rows excluded', api.scopedLog().every(r => r.section));

/* 4. facetVals: options under the OTHER facets, own facet excluded */
resetScope();
check('all cats offered', api.facetVals('cat').length === 3);
api.statsScope.cat.add('Literature');
check('subs follow picked cat', String(api.facetVals('sub')) === 'American Literature,British Literature');
check('own facet not self-limited', api.facetVals('cat').length === 3);
api.statsScope.sub.add('American Literature');
check('groups follow cat+sub', String(api.facetVals('section')) === 'Modernism,Poetry');
check('diff sorted numerically', String(api.facetVals('diff')) === '2,3');

/* 5. facetVals skips null/empty values */
resetScope();
api.statsScope.cat.add('History');
check('null group yields no chip', String(api.facetVals('section')) === 'WWII');

/* 6. pruneScope: orphaned finer picks drop, valid ones survive */
resetScope();
api.statsScope.cat.add('Literature').add('History');
api.statsScope.sub.add('American Literature').add('European History');
api.statsScope.section.add('Modernism').add('WWII');
api.statsScope.cat.delete('Literature');
api.pruneScope();
check('orphaned sub dropped', !api.statsScope.sub.has('American Literature'));
check('valid sub kept', api.statsScope.sub.has('European History'));
check('orphaned group dropped', !api.statsScope.section.has('Modernism'));
check('valid group kept', api.statsScope.section.has('WWII'));

/* 7. pruneScope with no cats picked keeps everything (empty = all) */
resetScope();
api.statsScope.sub.add('Biology');
api.pruneScope();
check('no cat picked -> sub survives', api.statsScope.sub.has('Biology'));

/* 8. compositeKey: DIM_ORDER order, KEY_SEP join, null value drops the row */
api.statsDims.clear(); api.statsDims.add('sub').add('diff');
const k = api.compositeKey(FIXTURE[0]);
check('composite key joins in order', k === 'American Literature' + api.KEY_SEP + 'Diff 2');
api.statsDims.add('section');
check('null dim value -> row dropped', api.compositeKey(FIXTURE[7]) === null);

/* 9. aggBy over composite keys: one row per combination, correct tallies */
api.statsDims.clear(); api.statsDims.add('cat').add('diff');
resetScope();
const rows = api.aggBy(api.compositeKey, api.scopedLog());
check('one row per combination', rows.length === 6);
const lit3 = rows.find(r => r.k === 'Literature' + api.KEY_SEP + 'Diff 3');
check('tallies: n', lit3.n === 2);
check('tallies: acc', lit3.acc === 0);
check('tallies: neg', lit3.neg === 0.5);
check('tallies: dead', lit3.dead === 0.5);

/* ---------- progress over time ----------
   rollup is a prefix-sum rewrite of a trailing rolling window, so the
   reference below (recompute every window from scratch) is what it must
   equal at every window size, including the Max case where the window is
   the whole history and the line becomes a running average. */

// deterministic pseudo-history: enough rows to exercise every window size
function mulberry32(a) {
  return function () {
    a |= 0; a = a + 0x6D2B79F5 | 0;
    let t = Math.imul(a ^ a >>> 15, 1 | a);
    t = t + Math.imul(t ^ t >>> 7, 61 | t) ^ t;
    return ((t ^ t >>> 14) >>> 0) / 4294967296;
  };
}
const prnd = mulberry32(1234567);
const HIST = [];
for (let i = 0; i < 400; i++) {
  const skill = 0.3 + 0.4 * (i / 400);
  const roll = prnd();
  let res = 'D', bf = null;
  if (roll < skill) { res = 'C'; bf = Math.max(0.05, Math.min(0.95, 0.6 - 0.25 * (i / 400) + (prnd() - 0.5) * 0.3)); }
  else if (roll < skill + 0.15) { res = 'W'; bf = 0.4 + (prnd() - 0.5) * 0.4; }
  HIST.push({ res, bf, ts: 1700000000000 + i * 60000 });
}

function refRollup(rows, W, metric) {
  const n = rows.length;
  W = Math.max(2, Math.min(W, n));
  const out = [];
  for (let i = 0; i < n; i++) {
    if (i + 1 < Math.min(W, 12)) continue;
    const w = rows.slice(Math.max(0, i - W + 1), i + 1);
    if (metric === 'acc' || metric === 'neg') {
      const want = metric === 'acc' ? 'C' : 'W';
      const k = w.filter(r => r.res === want).length;
      const [lo, hi] = api.wilson(k, w.length);
      out.push({ i, v: k / w.length, lo, hi, n: w.length });
    } else {
      const b = w.filter(r => r.res === 'C' && r.bf != null);
      if (b.length < 5) continue;
      const vals = b.map(r => 1 - r.bf);
      const mean = vals.reduce((s, x) => s + x, 0) / vals.length;
      const sd = Math.sqrt(vals.reduce((s, x) => s + (x - mean) ** 2, 0) / Math.max(1, vals.length - 1));
      const se = sd / Math.sqrt(vals.length);
      out.push({ i, v: mean, lo: Math.max(0, mean - 1.96 * se), hi: Math.min(1, mean + 1.96 * se), n: b.length });
    }
  }
  return out;
}

/* 10. rollup matches the naive reference at every window size */
let worst = 0, mismatch = 0, series = 0;
for (const W of [10, 17, 50, 123, 399, 400, 800]) {
  for (const m of ['acc', 'cel', 'neg']) {
    const a = api.rollup(HIST, W, m), b = refRollup(HIST, W, m);
    series++;
    if (a.length !== b.length) { mismatch++; continue; }
    for (let i = 0; i < a.length; i++)
      for (const f of ['v', 'lo', 'hi', 'n']) {
        const d = Math.abs(a[i][f] - b[i][f]);
        if (d > worst) worst = d;
        if (d > 1e-9) mismatch++;
      }
  }
}
check(`rollup matches reference (${series} series, worst delta ${worst.toExponential(1)})`,
  mismatch === 0 && worst < 1e-9);

/* 11. window >= row count clamps: the running average ends at the true mean */
const overall = HIST.filter(r => r.res === 'C').length / HIST.length;
const maxed = api.rollup(HIST, HIST.length, 'acc');
check('max window -> last point is the overall rate',
  Math.abs(maxed[maxed.length - 1].v - overall) < 1e-12);
check('window above row count clamps, not overruns',
  api.rollup(HIST, 99999, 'acc').length === maxed.length);
check('max window -> first window starts at attempt 0', maxed[0].n === maxed[0].i + 1);

/* 12. the band is honest: a thin window is wider than a fat one */
const thin = api.rollup(HIST, 10, 'acc'), fat = api.rollup(HIST, 200, 'acc');
const width = p => p.hi - p.lo;
check('thin window -> wider band', width(thin[thin.length - 1]) > width(fat[fat.length - 1]));
check('band contains the point', api.rollup(HIST, 50, 'acc').every(p => p.lo <= p.v && p.v <= p.hi));

/* 13. celerity ignores dead/neg rows: its count is the correct-buzz count */
const cel = api.rollup(HIST, 50, 'cel');
check('celerity counts only correct buzzes', cel.every(p => p.n <= 50));
check('celerity emits nothing below 5 buzzes', cel.every(p => p.n >= 5));

/* 14. wilson: known values and degenerate inputs */
const [w0lo, w0hi] = api.wilson(0, 10);
check('wilson(0,n) starts at 0', w0lo === 0 && w0hi > 0 && w0hi < 1);
const [w1lo, w1hi] = api.wilson(10, 10);
check('wilson(n,n) ends at 1', w1hi === 1 && w1lo > 0 && w1lo < 1);
check('wilson(k,0) is the full interval', String(api.wilson(3, 0)) === '0,1');

/* 15. window clamping follows the scope; Max re-fits when the scope shrinks */
api.progState.wmax = false; api.progState.W = 300;
check('clampWindow caps at scope size', api.clampWindow(120) === 120);
check('clampWindow floors at WIN_MIN', (api.progState.W = 2, api.clampWindow(500)) === api.WIN_MIN);
api.progState.wmax = true; api.clampWindow(400);
check('Max follows the scope up', api.progState.W === 400);
api.clampWindow(40);
check('Max follows the scope down', api.progState.W === 40);
check('progWindow at Max = scope size', api.progWindow(40) === 40);
api.progState.wmax = false; api.progState.W = 50;
check('progWindow below scope size passes through', api.progWindow(400) === 50);
check('progWindow never exceeds the scope', api.progWindow(20) === 20);

/* 16. the markup contract between progressBlock and wireProgress: every id
   and hook wireProgress reaches for must exist in the emitted block, and
   the block must degrade to a note (no controls to wire) on a thin scope */
api.progState.wmax = false; api.progState.W = 50;
const block = api.progressBlock(HIST);
const wireSrc = slice('function drawProgress(', '\nfunction showProgTip');
const ids = [...wireSrc.matchAll(/\$\('([a-z]+)'\)/g)].map(m => m[1])
  .filter(id => id !== 'view-stats');
check('wireProgress reaches for ids', ids.length >= 5);
for (const id of [...new Set(ids)])
  check(`block emits #${id}`, block.includes('id="' + id + '"'));
check('block emits the canvas', block.includes('class="progcv"'));
check('block emits a Max button', block.includes('id="progmax"'));
check('slider range ends at the scope size', block.includes('max="' + HIST.length + '"'));
check('slider starts at the current window', block.includes('value="50"'));
api.progState.wmax = true; api.clampWindow(HIST.length);
const maxBlock = api.progressBlock(HIST);
check('Max disables the slider', /id="progwin"[^>]*disabled/.test(maxBlock));
check('Max chip renders active', /class="dimbtn on" id="progmax"/.test(maxBlock));
api.progState.wmax = false; api.progState.W = 50;
const thinBlock = api.progressBlock(HIST.slice(0, api.PROG_MIN_ROWS - 1));
check('thin scope -> note, no controls', !thinBlock.includes('id="progctl"')
  && thinBlock.includes('statnote'));

console.log(`\n${pass} passed, ${fail} failed`);
process.exit(fail ? 1 : 0);
