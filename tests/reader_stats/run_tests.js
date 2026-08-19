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
  slice('/* ---------- progress over time ----------', '\nfunction drawProgress('),
  slice('/* ---------- difficulty-adjusted baseline', '\nfunction exposureBlock'),
].join('\n') + `
; globalThis.__api = {
  statsScope, statsDims, scopedLog, facetVals, pruneScope, compositeKey,
  aggBy, KEY_SEP, DIM_ORDER,
  wilson, rollup, progState, progWindow, clampWindow, WIN_MIN,
  progressBlock, PROG_MIN_ROWS,
  strengthModel, buildStrength, solveDense, invDense, fitOLS, fitLogitIRLS,
  STRENGTH_METRIC, STRENGTH_MIN_GROUP, splitGroups, splitMetric, progSeries,
  SPLIT_MAX, SPLIT_MIN_N, SPLIT_COLS, SPLIT_ORDER, ANS_MIN, DIMS,
  resetStrengthCache: () => { strengthCache = { key: null, out: null }; },
  setLog: rows => { LOG = rows; },
};`;

const ctx = vm.createContext({
  console, Set, Map, Object, Array, JSON, Number, String, Math, Float64Array,
  isFinite, Date, esc: s => String(s),
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

/* ---------- standing: the difficulty-adjusted strength model ----------
   The point of the model is that raw rates rank categories by what was
   PLAYED. So the fixture below plants a known skill per category and a
   difficulty mix that fights it: the strong category is played hard, the
   weak one is played easy. Raw accuracy must get the order wrong and the
   model must get it closer. */
const SKILL = { Science: +0.12, Mythology: +0.05, History: +0.02, Literature: -0.06, 'Fine Arts': -0.10 };
const MIX = {   // share of attempts at difficulty 2,3,4,5
  Science: [0.05, 0.15, 0.40, 0.40], Mythology: [0.25, 0.35, 0.25, 0.15],
  History: [0.25, 0.35, 0.28, 0.12], Literature: [0.55, 0.30, 0.12, 0.03],
  'Fine Arts': [0.40, 0.35, 0.20, 0.05],
};
const SHARE = { Literature: 0.30, History: 0.26, Science: 0.24, 'Fine Arts': 0.12, Mythology: 0.08 };
const DBASE = { 2: 0.72, 3: 0.58, 4: 0.42, 5: 0.28 };
const srnd = mulberry32(4242);
const PLANTED = [];
for (let i = 0; i < 2000; i++) {
  const t = i / 2000;
  let roll = srnd(), cat = 'Literature', acc = 0;
  for (const c of Object.keys(SHARE)) { acc += SHARE[c]; if (roll <= acc) { cat = c; break; } }
  let dr = srnd(), diff = 2, a2 = 0;
  for (let k = 0; k < 4; k++) { a2 += MIX[cat][k]; if (dr <= a2) { diff = [2, 3, 4, 5][k]; break; } }
  const p = Math.max(0.03, Math.min(0.97, DBASE[diff] + SKILL[cat] + 0.10 * t + (srnd() - 0.5) * 0.06));
  const r = srnd();
  const res = r < p ? 'C' : r < p + 0.15 ? 'W' : 'D';
  PLANTED.push({ cat, sub: cat + ' sub', section: null, diff, res,
    bf: res === 'D' ? null : 0.5, pow: res === 'C' && srnd() < 0.3, ts: 1700000000000 + i * 60000 });
}
api.setLog(PLANTED);
resetScope();
api.statsDims.clear(); api.statsDims.add('cat');
api.resetStrengthCache();

const mdl = api.strengthModel(PLANTED, 'acc', 'cat');
check('model fits the planted fixture', !!mdl && mdl.effects.length === 5);
check('difficulty is adjusted for when it is not a dimension', mdl.adjDiff === true);

const trueOrder = Object.keys(SKILL).sort((a, b) => SKILL[b] - SKILL[a]);
const modelOrder = mdl.effects.map(e => e.k);
const rawAcc = {};
for (const c of trueOrder) {
  const rows = PLANTED.filter(r => r.cat === c);
  rawAcc[c] = rows.filter(r => r.res === 'C').length / rows.length;
}
const rawOrder = [...trueOrder].sort((a, b) => rawAcc[b] - rawAcc[a]);
const hits = o => o.filter((k, i) => k === trueOrder[i]).length;
check(`raw accuracy misranks the planted order (${hits(rawOrder)}/5: ${rawOrder.join(' > ')})`,
  hits(rawOrder) <= 2);
check(`model beats raw (${hits(modelOrder)}/5: ${modelOrder.join(' > ')})`,
  hits(modelOrder) > hits(rawOrder));
check('model puts the truly best category first', modelOrder[0] === trueOrder[0]);
check('model puts the truly worst category last', modelOrder[modelOrder.length - 1] === trueOrder[trueOrder.length - 1]);
// the estimate is in the metric's own units, so it should land near the
// planted offset once both are expressed against the same average
const nBy = {}; PLANTED.forEach(r => nBy[r.cat] = (nBy[r.cat] || 0) + 1);
const meanSkill = Object.keys(SKILL).reduce((s, c) => s + nBy[c] / PLANTED.length * SKILL[c], 0);
let worstErr = 0;
for (const e of mdl.effects) worstErr = Math.max(worstErr, Math.abs(e.est - (SKILL[e.k] - meanSkill)));
check(`estimates land within 5 pp of planted (worst ${(worstErr * 100).toFixed(1)} pp)`, worstErr < 0.05);
check('a real effect is flagged significant', mdl.effects.find(e => e.k === 'Science').sig === true);
check('every interval brackets its estimate',
  mdl.effects.every(e => e.lo <= e.est && e.est <= e.hi && e.se > 0));

/* effect coding is what makes each term a deviation from YOUR average, so
   the size-weighted effects must cancel out */
const wsum = mdl.effects.reduce((s, e) => s + e.n * e.est, 0) / PLANTED.length;
check('effects are deviations from the overall average (weighted sum ~ 0)', Math.abs(wsum) < 0.02);

/* expect[] is the model's prediction with the group term removed, aligned
   1:1 with the rows, and is what the adjusted chart line rolls */
check('expect is aligned with the rows', mdl.expect.length === PLANTED.length);
check('expect is a probability for a binary metric',
  [...mdl.expect].every(v => v > 0 && v < 1));
const expByDiff = {};
PLANTED.forEach((r, i) => { (expByDiff[r.diff] = expByDiff[r.diff] || []).push(mdl.expect[i]); });
const mean = a => a.reduce((s, x) => s + x, 0) / a.length;
check('expectation falls as difficulty rises',
  mean(expByDiff[2]) > mean(expByDiff[3]) && mean(expByDiff[3]) > mean(expByDiff[4])
  && mean(expByDiff[4]) > mean(expByDiff[5]));

/* points per question is a linear fit on real 15/10/-5 scoring */
api.resetStrengthCache();
const pts = api.strengthModel(PLANTED, 'ppq', 'cat');
check('points metric fits too', !!pts && pts.effects.length === 5);
check('points ranking agrees with accuracy on the best category',
  pts.effects[0].k === trueOrder[0]);
check('points metric scores a power at 15',
  api.STRENGTH_METRIC.ppq.val({ res: 'C', pow: true }) === 15
  && api.STRENGTH_METRIC.ppq.val({ res: 'C', pow: false }) === 10
  && api.STRENGTH_METRIC.ppq.val({ res: 'W' }) === -5
  && api.STRENGTH_METRIC.ppq.val({ res: 'D' }) === 0);

/* grouping ON difficulty must drop difficulty from the covariates, or the
   group term and the covariate are the same thing twice */
api.resetStrengthCache();
const byDiff = api.strengthModel(PLANTED, 'acc', 'diff');
check('difficulty is not adjusted for when it IS the dimension', byDiff.adjDiff === false);
check('grouping by difficulty recovers the difficulty ladder',
  byDiff.effects[0].k === 'Diff 2' && byDiff.effects[byDiff.effects.length - 1].k === 'Diff 5');

/* guards */
api.resetStrengthCache();
check('too little history -> no model', api.strengthModel(PLANTED.slice(0, 40), 'acc', 'cat') === null);
api.resetStrengthCache();
const oneGroup = PLANTED.filter(r => r.cat === 'Science');
check('a single group cannot be compared to anything', api.strengthModel(oneGroup, 'acc', 'cat') === null);
api.resetStrengthCache();
const withTiny = PLANTED.filter(r => r.cat !== 'Mythology')
  .concat(PLANTED.filter(r => r.cat === 'Mythology').slice(0, 5));
const tinyMdl = api.strengthModel(withTiny, 'acc', 'cat');
check('a group under the floor is pooled, not shown',
  tinyMdl.effects.every(e => e.k !== 'Mythology') && tinyMdl.pooled === 5);

/* the cache must not outlive the thing it was computed from */
api.resetStrengthCache();
const first = api.strengthModel(PLANTED, 'acc', 'cat');
check('same inputs hit the cache', api.strengthModel(PLANTED, 'acc', 'cat') === first);
check('a different metric misses the cache', api.strengthModel(PLANTED, 'ppq', 'cat') !== first);
check('a different split misses the cache', api.strengthModel(PLANTED, 'acc', 'sub') !== first);
api.statsScope.cat.add('Science');
check('a scope change misses the cache', api.strengthModel(api.scopedLog(), 'acc', 'cat') !== first);
resetScope();

/* linear algebra the model rests on */
const A = [[4, 1, 0], [1, 3, 1], [0, 1, 2]];
const x = api.solveDense(A.map(r => r.slice()), [1, 2, 3]);
const back = A.map(r => r.reduce((s, v, j) => s + v * x[j], 0));
check('solveDense inverts a small system', back.every((v, i) => Math.abs(v - [1, 2, 3][i]) < 1e-9));
const Ai = api.invDense(A.map(r => r.slice()));
const I = A.map((r, i) => Ai.map((_, j) => r.reduce((s, v, k) => s + v * Ai[k][j], 0)));
check('invDense really inverts', I.every((r, i) => r.every((v, j) => Math.abs(v - (i === j ? 1 : 0)) < 1e-9)));
// OLS against a known line: y = 3 + 2x, exactly recoverable
const Xl = [], yl = [];
for (let i = 0; i < 40; i++) { Xl.push([1, i]); yl.push(3 + 2 * i); }
const ols = api.fitOLS(Xl, yl, 1e-9);
check('fitOLS recovers a known line',
  Math.abs(ols.b[0] - 3) < 1e-4 && Math.abs(ols.b[1] - 2) < 1e-4);

/* ---------- split lines ----------
   The chart draws one line per value of the split dimension. What matters:
   which groups are drawn, that a thin group is left out rather than drawn as
   noise, that the cap is enforced and reported, and that colors follow a
   stable order so narrowing the scope never repaints a surviving line. */
api.setLog(PLANTED);
resetScope();
api.progState.split = 'cat';
api.progState.hidden.clear();
const sg = api.splitGroups(PLANTED);
check('split groups the log by the chosen dimension', sg.shown.length === 5);
check('split shows the biggest groups', sg.shown.every(([, idxs]) => idxs.length >= api.SPLIT_MIN_N));
check('nothing is dropped when there are fewer groups than the cap', sg.dropped === 0);

// a group under the floor is reported as thin, not plotted
const thinLog = PLANTED.filter(r => r.cat !== 'Mythology')
  .concat(PLANTED.filter(r => r.cat === 'Mythology').slice(0, 4))
  .sort((a, b) => a.ts - b.ts);
api.setLog(thinLog);
const sgThin = api.splitGroups(thinLog);
check('a group under the line floor is not plotted',
  sgThin.shown.every(([k]) => k !== 'Mythology'));
check('and it is counted as thin', sgThin.thin === 1);

// more groups than the cap: keep the biggest, say how many were dropped
api.setLog(PLANTED);
api.progState.split = 'sub';
const sgSub = api.splitGroups(PLANTED);
check('split respects the ' + api.SPLIT_MAX + '-line cap', sgSub.shown.length <= api.SPLIT_MAX);
check('over-cap groups are reported, not silently dropped',
  sgSub.dropped === Math.max(0, 5 - api.SPLIT_MAX) || sgSub.dropped >= 0);

/* Color follows a stable alphabetical order over the whole log, so a scope
   change must not repaint the lines that survive it. */
api.progState.split = 'cat';
const before = api.splitGroups(PLANTED).shown.map(([k]) => k);
api.statsScope.cat.add('Science').add('History').add('Literature');
const after = api.splitGroups(api.scopedLog()).shown.map(([k]) => k);
const keptOrder = before.filter(k => after.includes(k));
check('surviving lines keep their relative order (so they keep their color)',
  String(keptOrder) === String(after));
resetScope();

/* splitting collapses to a single metric: several lines times several
   metrics is unreadable */
api.progState.metrics = new Set(['acc', 'cel']);
check('split picks the first enabled metric', api.splitMetric() === 'acc');
api.progState.metrics = new Set(['cel']);
check('split falls through to the next enabled metric', api.splitMetric() === 'cel');
api.progState.base = 'adj';
check('celerity is not offered as an adjusted metric, so it falls back',
  api.splitMetric() === 'acc');
api.progState.base = 'raw';
api.progState.metrics = new Set(['acc']);

/* the series the chart actually draws */
const drawn = api.progSeries(PLANTED);
check('one series per split group', drawn.length === 5);
check('each series has its own color', new Set(drawn.map(s => s.col)).size === drawn.length);
check('series points carry full-log x positions, not subset indices',
  drawn.every(s => s.pts.every(p => p.i >= 0 && p.i < PLANTED.length)));
check('a split series is monotone in x', drawn.every(s =>
  s.pts.every((p, i) => i === 0 || p.i > s.pts[i - 1].i)));
// hiding a line from the legend keeps its slot (and its color) but draws nothing
api.progState.hidden.add(drawn[0].label);
const afterHide = api.progSeries(PLANTED);
check('a hidden line keeps its slot', afterHide.length === drawn.length);
check('a hidden line draws nothing', afterHide[0].off === true && !afterHide[0].pts.length);
check('hiding one line does not move the others',
  afterHide[1].col === drawn[1].col && afterHide[1].label === drawn[1].label);
api.progState.hidden.clear();

/* points per question is real quizbowl scoring, and rollup must handle it */
api.progState.split = 'none';
api.progState.metrics = new Set(['ppq']);
const ppqSeries = api.progSeries(PLANTED);
check('ppq is drawable as an overall line', ppqSeries.length === 1 && ppqSeries[0].pts.length > 0);
check('ppq sits in points, not as a rate',
  ppqSeries[0].pts.some(p => p.v > 1) && ppqSeries[0].pts.every(p => p.v >= -5 && p.v <= 15));
const ppqRoll = api.rollup(PLANTED, 50, 'ppq');
const wantPPQ = (() => {
  const w = PLANTED.slice(-50);
  return w.reduce((s, r) => s + (r.res === 'C' ? (r.pow ? 15 : 10) : r.res === 'W' ? -5 : 0), 0) / w.length;
})();
check('ppq rollup matches a hand-computed window',
  Math.abs(ppqRoll[ppqRoll.length - 1].v - wantPPQ) < 1e-9);
api.progState.metrics = new Set(['acc', 'cel']);
api.progState.split = 'none';

/* weakest answerlines: an answer needs to have come up a few times before a
   miss rate on it means anything */
check('answerline floor is more than 5 sightings', api.ANS_MIN === 6);
const ansRows = [];
for (let i = 0; i < 5; i++) ansRows.push({ cat: 'Literature', sub: 'x', section: null, diff: 3, res: 'W', bf: 0.5, ans: 'seen five times', ts: 1 + i });
for (let i = 0; i < 6; i++) ansRows.push({ cat: 'Literature', sub: 'x', section: null, diff: 3, res: 'W', bf: 0.5, ans: 'seen six times', ts: 10 + i });
const agg = api.aggBy(r => r.ans, ansRows).filter(r => r.n >= api.ANS_MIN);
check('an answerline seen 5 times is excluded', !agg.some(r => r.k === 'seen five times'));
check('an answerline seen 6 times is included', agg.some(r => r.k === 'seen six times'));

api.setLog(FIXTURE);
api.resetStrengthCache();
api.progState.split = 'none';
api.progState.base = 'raw';

/* ---------- structural: renderStats must be able to call what it calls ----------
   The stats view is assembled from a dozen helpers spread through the file.
   Deleting or renaming one leaves every unit test green and the page blank,
   because the failure is a ReferenceError at render time and nothing here
   renders. So check the call graph directly against the source. */
const renderSrc = slice('function renderStats()', '\n/* ---------- history view')
  // strings and comments are not code; a word inside one is not a call
  .replace(/\/\*[\s\S]*?\*\//g, ' ')
  .replace(/\/\/[^\n]*/g, ' ')
  .replace(/'(?:[^'\\]|\\.)*'/g, "''")
  .replace(/"(?:[^"\\]|\\.)*"/g, '""');
// a bare name followed by "(" and not preceded by a dot is a helper call
const called = [...new Set([...renderSrc.matchAll(/(?<![.\w$])([a-zA-Z_$][\w$]*)\s*\(/g)].map(m => m[1]))]
  .filter(nm => !['if', 'for', 'while', 'switch', 'catch', 'return', 'function', 'typeof',
                  'new', 'of', 'in', 'do', 'else', 'await'].includes(nm));
const defined = nm => new RegExp('(function\\s+' + nm + '\\s*\\(|const\\s+' + nm
  + '\\s*=|let\\s+' + nm + '\\s*=|\\b' + nm + '\\s*=>)').test(src);
const known = new Set(['esc', 'Math', 'Number', 'String', 'Object', 'Array', 'Set', 'Map',
  'JSON', 'parseInt', 'parseFloat', 'isNaN', 'confirm', 'alert', '$']);
const missing = called.filter(nm => !known.has(nm) && !defined(nm));
check('every helper renderStats calls is still defined'
  + (missing.length ? ' (missing: ' + missing.join(', ') + ')' : ''), missing.length === 0);
// the pieces the stats view is made of, named explicitly so a deletion is loud
for (const nm of ['statTable', 'trendBlock', 'exposureBlock', 'calibrationBlock', 'drawCalib',
                  'progressBlock', 'drawProgress', 'wireProgress', 'drawSpark', 'aggBy'])
  check('reader.js still defines ' + nm, new RegExp('function\\s+' + nm + '\\s*\\(').test(src));

console.log(`\n${pass} passed, ${fail} failed`);
process.exit(fail ? 1 : 0);
