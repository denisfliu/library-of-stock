// Regression test for the reader's hierarchical facet semantics
// (lib/js/reader.js: taxPass / rowInScope / refreshBranchScopes /
// pruneOrphanedPicks). Executes the REAL functions sliced out of reader.js
// against a synthetic catalog, covering the July 2026 Group-overview bugs:
// a subtype pick must narrow only its own category (CS+Math must compose
// with a whole Mythology or with Opera), and single mis-tagged rows must
// not pollute the taxonomy maps. Run: node tests/reader_facets/run_tests.js
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

const code = [
  'let CAT = null;',
  slice('const filters = {', '\n// Subcategories whose'),
  slice('let SUBTYPED_SUBS = null;', '\n// Standard quizbowl'),
  slice('const catName =', '\nfunction chip('),
].join('\n');

const ctx = vm.createContext({
  console, Set, Map, Object, Array, JSON, Number, String, Math,
  ID2SLUG: new Map(), TOPICS: {}, eraOf: () => null,
  // audio mode off for these tests — facet scoping is what's under test
  audioMode: () => false, hasAudio: () => true,
});
vm.runInContext(code +
  '\n; globalThis.__api = { filters, rowInScope, refreshBranchScopes, pruneOrphanedPicks, groupFacetModel, setCAT: c => { CAT = c; } };',
  ctx, { filename: 'reader.js (sliced)' });
const api = ctx.__api;

/* ---- synthetic catalog ---- */
const CATS = ['Science', 'Mythology', 'Fine Arts'];
const SUBS = ['Biology', 'Other Science', 'Other Fine Arts', 'Visual Fine Arts', 'Mythology'];
const ALTS = ['Computer Science', 'Math', 'Opera', 'Film'];
const SECV = [['biology', 'Cells'], ['computer_science', 'Algorithms'], ['math', 'Analysis'],
              ['opera', 'Verdi'], ['mythology', 'Greek'], ['visual_fine_arts', 'Baroque'],
              ['opera', 'Puccini']];
const rows = [];
const add = (cat, sub, alt, sec, count) => {
  for (let i = 0; i < count; i++) rows.push([CATS.indexOf(cat), SUBS.indexOf(sub),
    alt == null ? -1 : ALTS.indexOf(alt), sec, 4]);
};
add('Science', 'Biology', null, 0, 100);
add('Science', 'Other Science', 'Computer Science', 1, 100);
add('Science', 'Other Science', 'Math', 2, 100);
add('Fine Arts', 'Other Fine Arts', 'Opera', 3, 100);
add('Fine Arts', 'Other Fine Arts', 'Film', -1, 100);
add('Fine Arts', 'Visual Fine Arts', null, 5, 100);
add('Mythology', 'Mythology', null, 4, 100);
// corpus noise: single mis-tagged rows that must NOT affect the taxonomy
add('Mythology', 'Mythology', 'Math', 4, 1);       // Math "under" Mythology
add('Science', 'Biology', 'Computer Science', 0, 1); // CS "under" Biology

const CAT = {
  category_values: CATS, subcategory_values: SUBS, alternate_subcategory_values: ALTS,
  section_values: SECV,
  tossups: {
    id: rows.map((_, i) => i),
    category: rows.map(r => r[0]), subcategory: rows.map(r => r[1]),
    alternate_subcategory: rows.map(r => r[2]), section: rows.map(r => r[3]),
    difficulty: rows.map(r => r[4]), set: rows.map(() => 0),
  },
};
api.setCAT(CAT);

/* ---- helpers ---- */
let pass = 0, fail = 0;
const check = (label, cond, detail) => {
  if (cond) { pass++; }
  else { fail++; console.error('FAIL ' + label + (detail ? ' — ' + detail : '')); }
};
function setFilters(cats, subs, subsubs) {
  api.filters.cats.clear(); cats.forEach(x => api.filters.cats.add(x));
  api.filters.subs.clear(); subs.forEach(x => api.filters.subs.add(x));
  api.filters.subsubs.clear(); subsubs.forEach(x => api.filters.subsubs.add(x));
  api.filters.diffs.clear(); api.filters.sections.clear();
  api.refreshBranchScopes();
}
function scopeCount() {
  const by = {};
  for (let r = 0; r < rows.length; r++) {
    if (!api.rowInScope(r, 'all')) continue;
    const key = CATS[rows[r][0]] + '/' + (rows[r][2] >= 0 ? ALTS[rows[r][2]] : SUBS[rows[r][1]]);
    by[key] = (by[key] || 0) + 1;
  }
  return by;
}

/* ---- the July 2026 bug scenarios ---- */
// subtype picks narrow their own category, whole categories stay whole
setFilters(['Science', 'Mythology'], [], ['Computer Science', 'Math']);
let by = scopeCount();
check('Mythology whole next to CS+Math', by['Mythology/Mythology'] === 100, JSON.stringify(by));
check('Science narrowed to CS+Math', by['Science/Computer Science'] === 101 && !by['Science/Biology'], JSON.stringify(by));

// the reported case: CS/Math + Opera compose across categories
setFilters(['Science', 'Fine Arts'], [], ['Computer Science', 'Math', 'Opera']);
by = scopeCount();
check('CS+Math+Opera compose', by['Science/Math'] === 100 && by['Fine Arts/Opera'] === 100, JSON.stringify(by));
check('unpicked FA subtypes excluded', !by['Fine Arts/Film'] && !by['Fine Arts/Visual Fine Arts'], JSON.stringify(by));

// a sub pick and a subtype pick compose within one category
setFilters(['Science'], ['Biology'], ['Computer Science', 'Math']);
by = scopeCount();
check('Biology + CS/Math compose', by['Science/Biology'] === 100 && by['Science/Math'] === 100, JSON.stringify(by));

// noise immunity: the 1-row mis-tags must not have taught the hierarchy
setFilters(['Mythology'], [], ['Math']);
api.pruneOrphanedPicks();
check('orphaned subtype pruned despite noise row', api.filters.subsubs.size === 0,
  'left: ' + [...api.filters.subsubs].join());
setFilters(['Science'], ['Biology'], []);
by = scopeCount();
check('Biology not "constrained" by its noise CS row', by['Science/Biology'] === 100, JSON.stringify(by));

// deselecting all categories clears descendants (no invisible filters)
setFilters([], ['Other Science'], ['Opera']);
api.pruneOrphanedPicks();
check('no-category state clears descendants', api.filters.subs.size === 0 && api.filters.subsubs.size === 0);

/* ---- Group facet model (accordion; the July 2026 vanish bug) ---- */
const gfm = (secCount, sections) => {
  api.filters.sections.clear();
  (sections || []).forEach(s => api.filters.sections.add(s));
  return api.groupFacetModel(secCount, SECV);
};
const unitsOf = m => m.units.map(u => u[0]);

// THE bug: >4 units used to hide the facet outright — now all offered
setFilters(['Science'], [], []);
let m = gfm({ 0: 100, 1: 90, 2: 80, 3: 70, 4: 60, 5: 50 });
check('many-unit scope shows (no more unit cap)', m.show && m.units.length === 6,
  JSON.stringify(unitsOf(m)));
check('units ordered by scope rows', unitsOf(m)[0] === 'biology' && unitsOf(m)[5] === 'visual_fine_arts',
  JSON.stringify(unitsOf(m)));

// unfiltered corpus: no taxonomy narrowing -> facet stays hidden
setFilters([], [], []);
m = gfm({ 0: 100, 1: 90 });
check('no narrowing -> hidden', !m.show);

// stray under-floor unit never surfaces...
setFilters(['Science'], [], []);
m = gfm({ 1: 100, 2: 90, 4: 4 });
check('under-floor stray unit excluded', m.show && !unitsOf(m).includes('mythology'),
  JSON.stringify(unitsOf(m)));
// ...unless one of its sections is actively picked (picks never vanish)
m = gfm({ 1: 100, 2: 90, 4: 4 }, [4]);
check('picked section keeps its under-floor unit', unitsOf(m).includes('mythology'),
  JSON.stringify(unitsOf(m)));

// <3-row sections are noise unless picked
m = gfm({ 1: 100, 2: 2 });
check('2-row section dropped', m.units.every(([, ids]) => !ids.includes(2)),
  JSON.stringify(m.units));
m = gfm({ 1: 100, 2: 2 }, [2]);
check('2-row section kept when picked', m.units.some(([, ids]) => ids.includes(2)));

// single unit still shows (renderer draws it flat, no accordion header)
m = gfm({ 3: 50, 6: 20, 1: 2 });
check('single-unit scope', m.show && m.units.length === 1 && unitsOf(m)[0] === 'opera'
  && JSON.stringify(m.units[0][1]) === '[3,6]',
  JSON.stringify(m.units));

// a lone section is no facet at all
m = gfm({ 3: 50 });
check('one section -> hidden', !m.show);

console.log(`${pass}/${pass + fail} reader facet cases pass`);
process.exit(fail ? 1 : 0);
