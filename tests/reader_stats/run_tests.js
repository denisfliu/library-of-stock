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
].join('\n') + `
; globalThis.__api = {
  statsScope, statsDims, scopedLog, facetVals, pruneScope, compositeKey,
  aggBy, KEY_SEP, DIM_ORDER,
  setLog: rows => { LOG = rows; },
};`;

const ctx = vm.createContext({ console, Set, Map, Object, Array, JSON, Number, String, Math });
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

console.log(`\n${pass} passed, ${fail} failed`);
process.exit(fail ? 1 : 0);
