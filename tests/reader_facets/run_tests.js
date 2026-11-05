// Regression test for the reader's scope semantics (lib/js/reader.js):
// the qbreader-style category picker (taxPass / setCat / toggleSub /
// toggleAlt / pruneOrphanedPicks), group picks narrowing only their own
// unit (secPass / groupModel), the migration of pre-picker saved scopes,
// and set mode (rowInScope's set + packet range, setOrder, playedCodes).
// Executes the REAL functions sliced out of reader.js against a synthetic
// catalog. Run: node tests/reader_facets/run_tests.js
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
  slice('function distPicks()', '\nlet SET_FRESH'),
  slice('function playedCodes(', '\nlet SET_ROWS'),
].join('\n');

const ctx = vm.createContext({
  console, Set, Map, Object, Array, JSON, Number, String, Math,
  ID2SLUG: new Map(), TOPICS: {}, eraOf: () => null,
  // audio + score modes off for these tests — scoping is what's under test
  audioMode: () => false, hasAudio: () => true, scoreModeOn: () => false,
});
vm.runInContext(code +
  '\n; globalThis.__api = { filters, setPick, rowInScope, refreshBranchScopes, pruneOrphanedPicks, groupModel,' +
  ' setCat, toggleSub, toggleAlt, catSubs, catAlts, pickerCats, migrateOldScope, distPicks, setOrder, playedCodes,' +
  ' rowUnit, setIdx: () => SET_IDX, setCAT: c => { CAT = c; } };',
  ctx, { filename: 'reader.js (sliced)' });
const api = ctx.__api;

/* ---- synthetic catalog ---- */
const CATS = ['Science', 'Mythology', 'Fine Arts', 'Literature'];
const SUBS = ['Biology', 'Other Science', 'Other Fine Arts', 'Visual Fine Arts', 'Mythology',
              'American Literature', 'British Literature'];
const ALTS = ['Computer Science', 'Math', 'Opera', 'Film', 'Poetry', 'Drama'];
const SECV = [['biology', 'Cells'], ['computer_science', 'Algorithms'], ['math', 'Analysis'],
              ['opera', 'Verdi'], ['mythology', 'Greek'], ['visual_fine_arts', 'Baroque'],
              ['opera', 'Puccini'], ['american_literature', 'Modernist Poetry'],
              ['american_literature', 'American Drama'], ['biology', 'Genetics'],
              ['american_literature', 'Tiny']];
const rows = [];
const add = (cat, sub, alt, sec, count, set = 0) => {
  for (let i = 0; i < count; i++) rows.push([CATS.indexOf(cat), SUBS.indexOf(sub),
    alt == null ? -1 : ALTS.indexOf(alt), sec, 4, set]);
};
add('Science', 'Biology', null, 0, 100);
add('Science', 'Biology', null, 9, 50);
add('Science', 'Other Science', 'Computer Science', 1, 100);
add('Science', 'Other Science', 'Math', 2, 100);
add('Fine Arts', 'Other Fine Arts', 'Opera', 3, 100);
add('Fine Arts', 'Other Fine Arts', 'Film', -1, 100);
add('Fine Arts', 'Visual Fine Arts', null, 5, 100);
add('Mythology', 'Mythology', null, 4, 100);
// Literature: the forms (Poetry/Drama) partition both subcategories; this
// is set 1, the set-mode fixture (10 packets of 20)
add('Literature', 'American Literature', 'Poetry', 7, 60, 1);
add('Literature', 'American Literature', 'Drama', 8, 38, 1);
add('Literature', 'American Literature', 'Drama', 10, 2, 1);   // a 2-row group: noise
add('Literature', 'British Literature', 'Poetry', -1, 50, 1);
add('Literature', 'British Literature', 'Drama', -1, 50, 1);
// corpus noise: single mis-tagged rows that must NOT affect the taxonomy
add('Mythology', 'Mythology', 'Math', 4, 1);       // Math "under" Mythology
add('Science', 'Biology', 'Computer Science', 0, 1); // CS "under" Biology

let litI = 0;
const packet = [], number = [];
for (const r of rows) {
  if (r[5] === 1) { packet.push(Math.floor(litI / 20) + 1); number.push(litI % 20 + 1); litI++; }
  else { packet.push(1); number.push(1); }
}
const CAT = {
  category_values: CATS, subcategory_values: SUBS, alternate_subcategory_values: ALTS,
  section_values: SECV,
  sets: [{ slug: 'a', name: 'Set A', difficulty: 4 }, { slug: 'b', name: 'Set B', difficulty: 7 }],
  tossups: {
    id: rows.map((_, i) => 'q' + i),
    category: rows.map(r => r[0]), subcategory: rows.map(r => r[1]),
    alternate_subcategory: rows.map(r => r[2]), section: rows.map(r => r[3]),
    difficulty: rows.map(r => r[4]), set: rows.map(r => r[5]), packet, number,
  },
};
api.setCAT(CAT);

/* ---- helpers ---- */
let pass = 0, fail = 0;
const check = (label, cond, detail) => {
  if (cond) { pass++; }
  else { fail++; console.error('FAIL ' + label + (detail ? ' — ' + detail : '')); }
};
const F = api.filters;
function reset() {
  F.cats.clear(); F.subsOff.clear(); F.altsOff.clear(); F.sections.clear(); F.diffs.clear();
  api.setPick.slug = api.setPick.from = api.setPick.to = null;
  api.refreshBranchScopes();
}
function scopeCount() {
  api.refreshBranchScopes();
  const by = {};
  for (let r = 0; r < rows.length; r++) {
    if (!api.rowInScope(r, 'all')) continue;
    const key = CATS[rows[r][0]] + '/' + (rows[r][2] >= 0 ? ALTS[rows[r][2]] : SUBS[rows[r][1]]);
    by[key] = (by[key] || 0) + 1;
  }
  return by;
}
const total = by => Object.values(by).reduce((a, b) => a + b, 0);

/* ---- picker semantics (qbreader) ---- */
reset();
let by = scopeCount();
check('nothing picked -> everything', total(by) === rows.length, total(by));

api.setCat('Science', true);
by = scopeCount();
check('picking a category picks all of it', by['Science/Biology'] === 150 && by['Science/Computer Science'] === 101
  && by['Science/Math'] === 100 && !by['Mythology/Mythology'], JSON.stringify(by));

api.toggleSub('Science', 'Biology');
by = scopeCount();
check('switching a subcategory off drops it', !by['Science/Biology'] && by['Science/Math'] === 100, JSON.stringify(by));

api.toggleAlt('Math');
api.setCat('Mythology', true);
by = scopeCount();
check('switching a subtype off drops it', !by['Science/Math'] && by['Science/Computer Science'] === 100, JSON.stringify(by));
check('...but not a stray mis-tagged row elsewhere', by['Mythology/Math'] === 1 && by['Mythology/Mythology'] === 100,
  JSON.stringify(by));

api.setCat('Science', true);
by = scopeCount();
check('re-picking a category turns all of it back on', by['Science/Biology'] === 150 && by['Science/Math'] === 100,
  JSON.stringify(by));

reset();
api.setCat('Literature', true);
api.toggleAlt('Poetry');
by = scopeCount();
check('a form switched off across both subcategories', by['Literature/Drama'] === 90 && !by['Literature/Poetry'],
  JSON.stringify(by));

reset();
api.setCat('Fine Arts', true);
for (const s of api.catSubs('Fine Arts')) api.toggleSub('Fine Arts', s);
check('switching off the last subcategory drops the category', !F.cats.has('Fine Arts') && F.subsOff.size === 0,
  [...F.cats].join() + ' / ' + [...F.subsOff].join());

check('one-subcategory categories show no subcategory buttons', api.catSubs('Mythology').length === 0);
check('subtypes listed under their category, in qbreader order',
  JSON.stringify(api.catAlts('Science')) === '["Math","Computer Science"]', JSON.stringify(api.catAlts('Science')));
check('categories in qbreader order', JSON.stringify(api.pickerCats()) === '["Literature","Science","Fine Arts","Mythology"]',
  JSON.stringify(api.pickerCats()));

// pruning: no switch survives out of view
reset();
api.setCat('Science', true); api.toggleSub('Science', 'Biology'); api.toggleAlt('Math');
F.cats.delete('Science'); F.cats.add('Mythology');
api.pruneOrphanedPicks();
check('switches of a dropped category pruned', F.subsOff.size === 0 && F.altsOff.size === 0);
F.cats.clear(); F.subsOff.add('Biology'); F.sections.add(0);
api.pruneOrphanedPicks();
check('no category picked clears everything', F.subsOff.size === 0 && F.sections.size === 0);

/* ---- groups narrow only their own unit ---- */
reset();
api.setCat('Literature', true); api.setCat('Science', true);
F.sections.add(7);   // Modernist Poetry (American Literature)
by = scopeCount();
// American Literature keeps only Modernist Poetry (60); British Literature
// is its own unit and stays whole (50 poetry + 50 drama)
check('group narrows its own unit', by['Literature/Poetry'] === 110 && by['Literature/Drama'] === 50, JSON.stringify(by));
check('...not another category', by['Science/Biology'] === 150, JSON.stringify(by));
F.sections.add(0);   // Cells (Biology)
by = scopeCount();
check('groups in two units compose', by['Science/Biology'] === 100 && by['Science/Math'] === 100
  && by['Literature/Poetry'] === 110, JSON.stringify(by));
F.cats.delete('Science');
api.pruneOrphanedPicks();
check('a group pick goes with its category', !F.sections.has(0) && F.sections.has(7), [...F.sections].join());

/* ---- the Group column's model ---- */
reset();
check('no category -> no groups', api.groupModel().length === 0);
api.setCat('Literature', true); api.setCat('Science', true); api.setCat('Mythology', true);
let gm = api.groupModel();
const units = gm.map(m => m.u);
check('units in taxonomy order', JSON.stringify(units) === '["american_literature","biology"]', JSON.stringify(units));
check('unit labelled by its subcategory', gm[0].label === 'American Literature', gm[0].label);
check('groups by count, 2-row noise dropped', JSON.stringify(gm[0].ids) === '[7,8]', JSON.stringify(gm[0].ids));
check('one-group units left out', !units.includes('computer_science') && !units.includes('mythology'));
F.sections.add(10);
gm = api.groupModel();
check('a picked noise group stays visible', gm[0].ids.includes(10), JSON.stringify(gm[0].ids));
check('subtype units use the subtype', api.rowUnit('Other Science', 'Math') === 'math'
  && api.rowUnit('Other Fine Arts', 'Film') === 'other_fine_arts' && api.rowUnit('American Literature', 'Drama') === 'american_literature');

/* ---- saved scopes from before the picker ---- */
reset();
const old = { cats: ['Science', 'Fine Arts', 'Mythology'], subs: [], subsubs: ['Computer Science', 'Math', 'Opera'] };
old.cats.forEach(c => F.cats.add(c));
api.migrateOldScope(old);
by = scopeCount();
check('old subtype picks become switches', by['Science/Computer Science'] === 100 && by['Science/Math'] === 100
  && by['Fine Arts/Opera'] === 100 && !by['Science/Biology'] && !by['Fine Arts/Film'] && !by['Fine Arts/Visual Fine Arts'],
  JSON.stringify(by));
check('...and a whole category stays whole', by['Mythology/Mythology'] === 100, JSON.stringify(by));

reset();
F.cats.add('Science');
api.migrateOldScope({ cats: ['Science'], subs: ['Biology'], subsubs: [] });
by = scopeCount();
check('old sub pick keeps only that sub', by['Science/Biology'] === 150 && !by['Science/Math'], JSON.stringify(by));
const dp = api.distPicks();
check('distribution keeps the narrowed branches', dp.subs.has('Biology') && !dp.subs.has('Other Science'),
  [...dp.subs].join());

/* ---- set mode ---- */
reset();
F.diffs.add(9);   // no row has difficulty 9 ...
api.setPick.slug = 'b';
by = scopeCount();
check('set picked -> only its rows', api.setIdx() === 1 && total(by) === 200, JSON.stringify(by));
check('...at the set\'s own difficulty', by['Literature/Poetry'] === 110, JSON.stringify(by));
api.setPick.from = 3; api.setPick.to = 4;
by = scopeCount();
check('packet range', total(by) === 40, total(by));
api.setCat('Literature', true); api.toggleAlt('Drama');
by = scopeCount();
check('categories still narrow a set', total(by) > 0 && !by['Literature/Drama'], JSON.stringify(by));

const T = CAT.tossups;
const setRows = [];
for (let r = 0; r < rows.length; r++) if (T.set[r] === 1 && T.packet[r] <= 2) setRows.push(r);
setRows.reverse();
const seen = new Set([T.id[setRows[setRows.length - 1]], T.id[setRows[setRows.length - 3]]]);   // P1 #1 and #3
const o = api.setOrder(setRows, T, seen);
const lbl = r => T.packet[r] + '.' + T.number[r];
check('set order: unplayed first, packet order', o.fresh === 38 && lbl(o.queue[0]) === '1.2' && lbl(o.queue[1]) === '1.4'
  && lbl(o.queue[37]) === '2.20', o.queue.slice(0, 3).map(lbl).join());
check('...then the played ones, in order', lbl(o.queue[38]) === '1.1' && lbl(o.queue[39]) === '1.3',
  o.queue.slice(38).map(lbl).join());

const pc = api.playedCodes(
  [{ id: 'x', res: 'W' }, { id: 'x', res: 'C', pow: true }, { id: 'y', res: 'C' }, { id: 'z', res: 'D' }],
  [{ id: 'h' }, { id: 'y' }]);
check('played codes: latest attempt wins, heard counts',
  pc.get('x') === 'P' && pc.get('y') === 'C' && pc.get('z') === 'D' && pc.get('h') === 'H' && pc.size === 4,
  JSON.stringify([...pc]));

console.log(`${pass}/${pass + fail} reader facet cases pass`);
process.exit(fail ? 1 : 0);
