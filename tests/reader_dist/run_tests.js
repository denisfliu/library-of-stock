#!/usr/bin/env node
// Regression test for the reader's distribution sampling model (lib/js/
// reader.js: distWeights). Executes the REAL function sliced out of
// reader.js against synthetic scope cells and checks the target shares the
// nested weight chain produces: category weights from settings.dist, sub /
// subtype splits from settings.distSub (missing = even), normalization over
// what's in scope, and the explicit-pick escape hatch at every level.
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

const ctx = vm.createContext({ console, Set, Map, Object, Array, JSON, Number, String, Math });
vm.runInContext(
  slice('function distWeights(', '\nfunction rebuildQueue(')
  + '\n; globalThis.__api = { distWeights };',
  ctx, { filename: 'reader.js (sliced)' });
ctx.globalThis = ctx;
const { distWeights } = vm.runInContext('__api', ctx);

/* ---- helpers ---- */
let pass = 0, fail = 0;
const check = (label, cond, detail) => {
  if (cond) { pass++; }
  else { fail++; console.error('FAIL ' + label + (detail ? ' — ' + detail : '')); }
};
const near = (a, b, eps) => Math.abs(a - b) <= (eps || 1e-9);
const SUBTYPED = new Set(['Other Science', 'Social Science']);
const noPicks = { cats: new Set(), subs: new Set(), subsubs: new Set() };
// expand [cell, count] pairs into per-row cells, run the model, and return
// total share per label (weights sum to the group's share of the whole)
function shares(spec, opts) {
  const cells = [];
  for (const [c, s, a, count] of spec)
    for (let i = 0; i < count; i++) cells.push({ c, s: s || '', a: a || '' });
  const ws = distWeights(cells, {
    dist: opts.dist, distSub: opts.distSub || {},
    subtyped: opts.subtyped || SUBTYPED, picked: opts.picked || noPicks,
  });
  const by = {};
  let total = 0;
  for (let i = 0; i < cells.length; i++) {
    if (ws[i] == null) continue;
    const k = cells[i].c + '/' + cells[i].s + (cells[i].a ? '/' + cells[i].a : '');
    by[k] = (by[k] || 0) + ws[i];
    total += ws[i];
  }
  for (const k in by) by[k] /= total;   // normalized shares
  return { by, raw: ws };
}

/* ---- category level (the pre-existing behavior) ---- */
{
  const { by } = shares([
    ['Literature', 'American Literature', null, 10],
    ['History', 'American History', null, 40],
    ['Mythology', 'Mythology', null, 5],
  ], { dist: { Literature: 4, History: 4, Mythology: 1 } });
  check('cat shares follow dist, not corpus counts',
    near(by['Literature/American Literature'], 4 / 9) &&
    near(by['History/American History'], 4 / 9) &&
    near(by['Mythology/Mythology'], 1 / 9), JSON.stringify(by));
}
{
  const { raw } = shares([
    ['Literature', 'American Literature', null, 5],
    ['History', 'American History', null, 5],
  ], { dist: { Literature: 4, History: 0 } });
  check('zero-weight category excluded', raw.slice(5).every(w => w === null));
}
{
  const { by } = shares([
    ['Literature', 'American Literature', null, 5],
    ['History', 'American History', null, 5],
  ], { dist: { Literature: 4, History: 0 },
       picked: { cats: new Set(['History']), subs: new Set(), subsubs: new Set() } });
  check('picked category rescued from zero weight',
    near(by['History/American History'], 1 / 5), JSON.stringify(by));
}
{
  const { by } = shares([
    ['Literature', 'American Literature', null, 30],
    ['History', 'American History', null, 10],
  ], { dist: { Literature: 0, History: 0 } });
  check('all categories zeroed -> uniform category shares',
    near(by['Literature/American Literature'], 0.5) &&
    near(by['History/American History'], 0.5), JSON.stringify(by));
}

/* ---- subcategory level ---- */
{
  const { by } = shares([
    ['Literature', 'American Literature', null, 100],
    ['Literature', 'British Literature', null, 10],
    ['Literature', 'European Literature', null, 1],
  ], { dist: { Literature: 4 } });
  check('untouched sub split is even regardless of corpus counts',
    near(by['Literature/American Literature'], 1 / 3) &&
    near(by['Literature/British Literature'], 1 / 3) &&
    near(by['Literature/European Literature'], 1 / 3), JSON.stringify(by));
}
{
  const { by } = shares([
    ['Science', 'Biology', null, 10],
    ['Science', 'Chemistry', null, 10],
    ['Science', 'Physics', null, 10],
  ], { dist: { Science: 4 }, distSub: { Science: { Biology: 2, Chemistry: 1, Physics: 1 } } });
  check('distSub weights split the category share',
    near(by['Science/Biology'], 0.5) &&
    near(by['Science/Chemistry'], 0.25) &&
    near(by['Science/Physics'], 0.25), JSON.stringify(by));
}
{
  const { by } = shares([
    ['Science', 'Biology', null, 10],
    ['Science', 'Chemistry', null, 10],
  ], { dist: { Science: 4 }, distSub: { Science: { Biology: 2, Chemistry: 1, Physics: 5 } } });
  check('absent sub redistributes to in-scope siblings',
    near(by['Science/Biology'], 2 / 3) && near(by['Science/Chemistry'], 1 / 3),
    JSON.stringify(by));
}
{
  const { by, raw } = shares([
    ['Science', 'Biology', null, 10],
    ['Science', 'Chemistry', null, 10],
  ], { dist: { Science: 4 }, distSub: { Science: { Biology: 1, Chemistry: 0 } } });
  check('zero-weight sub excluded',
    near(by['Science/Biology'], 1) && raw.slice(10).every(w => w === null));
}
{
  const { by } = shares([
    ['Science', 'Biology', null, 10],
    ['Science', 'Chemistry', null, 10],
  ], { dist: { Science: 4 }, distSub: { Science: { Biology: 1, Chemistry: 0 } },
       picked: { cats: new Set(), subs: new Set(['Chemistry']), subsubs: new Set() } });
  check('picked sub rescued from zero weight',
    near(by['Science/Chemistry'], 0.5), JSON.stringify(by));
}
{
  // rows of one cell share its slice equally: per-row weight halves when the
  // cell has twice the rows, but the cell's total share is unchanged
  const a = shares([['Science', 'Biology', null, 10], ['Science', 'Chemistry', null, 10]],
    { dist: { Science: 4 } });
  const b = shares([['Science', 'Biology', null, 20], ['Science', 'Chemistry', null, 10]],
    { dist: { Science: 4 } });
  check('cell share independent of its row count',
    near(a.by['Science/Biology'], b.by['Science/Biology']) &&
    near(b.raw[0], a.raw[0] / 2), JSON.stringify(b.by));
}

/* ---- subtype level ---- */
{
  const { by } = shares([
    ['Science', 'Biology', null, 10],
    ['Science', 'Other Science', 'Math', 10],
    ['Science', 'Other Science', 'Computer Science', 10],
  ], { dist: { Science: 4 } });
  check('untouched subtype split is even within its sub',
    near(by['Science/Biology'], 0.5) &&
    near(by['Science/Other Science/Math'], 0.25) &&
    near(by['Science/Other Science/Computer Science'], 0.25), JSON.stringify(by));
}
{
  const { by } = shares([
    ['Science', 'Other Science', 'Math', 10],
    ['Science', 'Other Science', 'Computer Science', 10],
    ['Science', 'Other Science', 'Astronomy', 10],
  ], { dist: { Science: 4 },
       distSub: { 'Other Science': { Math: 2, 'Computer Science': 1, Astronomy: 1 } } });
  check('subtype weights split the sub share',
    near(by['Science/Other Science/Math'], 0.5) &&
    near(by['Science/Other Science/Computer Science'], 0.25) &&
    near(by['Science/Other Science/Astronomy'], 0.25), JSON.stringify(by));
}
{
  const { by } = shares([
    ['Science', 'Other Science', 'Math', 10],
    ['Science', 'Other Science', 'Computer Science', 10],
  ], { dist: { Science: 4 },
       distSub: { 'Other Science': { Math: 1, 'Computer Science': 0 } },
       picked: { cats: new Set(), subs: new Set(), subsubs: new Set(['Computer Science']) } });
  check('picked subtype rescued from zero weight',
    near(by['Science/Other Science/Computer Science'], 0.5), JSON.stringify(by));
}
{
  // subtype-bearing sub with a straggler row missing its alt: the '' bucket
  // participates at weight 1 instead of vanishing
  const { by } = shares([
    ['Science', 'Other Science', 'Math', 10],
    ['Science', 'Other Science', null, 10],
  ], { dist: { Science: 4 } });
  check('alt-less rows in a subtyped sub keep an even bucket',
    near(by['Science/Other Science/Math'], 0.5) &&
    near(by['Science/Other Science'], 0.5), JSON.stringify(by));
}
{
  // alt names repeat across parents (the Literature forms): splits are keyed
  // by the parent sub, so each sub's group is independent
  const subtyped = new Set(['American Literature', 'British Literature']);
  const { by } = shares([
    ['Literature', 'American Literature', 'Drama', 10],
    ['Literature', 'American Literature', 'Poetry', 10],
    ['Literature', 'British Literature', 'Drama', 10],
    ['Literature', 'British Literature', 'Poetry', 10],
  ], { dist: { Literature: 4 }, subtyped,
       distSub: { 'American Literature': { Drama: 3, Poetry: 1 } } });
  check('same-named subtypes split per parent sub',
    near(by['Literature/American Literature/Drama'], 0.375) &&
    near(by['Literature/American Literature/Poetry'], 0.125) &&
    near(by['Literature/British Literature/Drama'], 0.25) &&
    near(by['Literature/British Literature/Poetry'], 0.25), JSON.stringify(by));
}

/* ---- chain composition ---- */
{
  const { by } = shares([
    ['Science', 'Biology', null, 7],
    ['Science', 'Other Science', 'Math', 3],
    ['Science', 'Other Science', 'Computer Science', 9],
    ['History', 'American History', null, 20],
  ], { dist: { Science: 4, History: 4 },
       distSub: { Science: { Biology: 3, 'Other Science': 1 },
                  'Other Science': { Math: 1, 'Computer Science': 3 } } });
  check('full chain: cat x sub x subtype',
    near(by['History/American History'], 0.5) &&
    near(by['Science/Biology'], 0.375) &&
    near(by['Science/Other Science/Math'], 0.5 * 0.25 * 0.25) &&
    near(by['Science/Other Science/Computer Science'], 0.5 * 0.25 * 0.75),
    JSON.stringify(by));
}

/* ==== editor smoke: distTree + renderDistEditor against a stub DOM ==== */
// The tree editor is DOM code, so it gets a wiring smoke here: taxonomy
// built from a synthetic catalog, expand, a group-persisting edit, the Even
// link, and the % column.
function mkEl(tag) {
  const e = {
    tag, children: [], style: {}, attrs: {}, _cls: new Set(),
    set className(v) { this._cls = new Set(v.split(/\s+/).filter(Boolean)); },
    get className() { return [...this._cls].join(' '); },
    set textContent(v) { this._text = v; }, get textContent() { return this._text || ''; },
    set innerHTML(v) { this.children = []; }, get innerHTML() { return ''; },
    appendChild(c) { this.children.push(c); return c; },
    append(...cs) { for (const c of cs) this.children.push(c); },
    setAttribute(k, v) { this.attrs[k] = v; },
    value: '', disabled: false,
  };
  e.classList = {
    toggle(c, on) { on ? e._cls.add(c) : e._cls.delete(c); },
    add(c) { e._cls.add(c); }, remove(c) { e._cls.delete(c); }, contains(c) { return e._cls.has(c); },
  };
  return e;
}
const byId = {};
const edPreamble = `
let CAT = null;
const filters = { cats: new Set(), subs: new Set(), subsubs: new Set() };
let savedCount = 0, rebuilt = 0;
function savePrefs() { savedCount++; }
function rebuildQueue() { rebuilt++; }
`;
const edCode = [
  edPreamble,
  slice('let SUBTYPED_SUBS = null;', '// A unit needs a real presence'),
  slice('function computeSubtypedSubs()', '// Hierarchical filter semantics'),
  slice('// Standard quizbowl', '\nlet queue = []'),
  slice('const catName =', '\nfunction rowInScope('),
  slice('/* ---------- distribution editor', '/* ---------- controls ----------'),
].join('\n') + `
; globalThis.__api = { renderDistEditor, distTree, settings, distOpen,
  setCAT: c => { CAT = c; }, counters: () => ({ savedCount, rebuilt }) };`;
const edCtx = vm.createContext({
  console, Set, Map, Object, Array, JSON, Number, String, Math,
  $: id => byId[id] || (byId[id] = mkEl('div')),
  document: { createElement: mkEl },
});
edCtx.globalThis = edCtx;
vm.runInContext(edCode, edCtx, { filename: 'reader.js (editor slice)' });
const ed = edCtx.__api;

const CATS = ['Science', 'Religion'];
const SUBS = ['Biology', 'Chemistry', 'Other Science', 'Religion'];
const ALTS = ['Math', 'Computer Science'];
const rows = [];
const add = (c, s, a, n) => { for (let i = 0; i < n; i++) rows.push([CATS.indexOf(c), SUBS.indexOf(s), a == null ? -1 : ALTS.indexOf(a)]); };
add('Science', 'Biology', null, 50);
add('Science', 'Chemistry', null, 50);
add('Science', 'Other Science', 'Math', 40);
add('Science', 'Other Science', 'Computer Science', 40);
add('Religion', 'Religion', null, 50);
ed.setCAT({
  category_values: CATS, subcategory_values: SUBS, alternate_subcategory_values: ALTS,
  tossups: {
    id: rows.map((_, i) => i),
    category: rows.map(r => r[0]), subcategory: rows.map(r => r[1]),
    alternate_subcategory: rows.map(r => r[2]),
  },
});

const tree = ed.distTree();
check('editor: 12 category roots', tree.length === 12);
const sci = tree.find(n => n.name === 'Science');
check('editor: Science has 3 sub kids', sci.kids.length === 3, JSON.stringify(sci.kids.map(k => k.name)));
check('editor: Other Science sorted last', sci.kids[2].name === 'Other Science');
check('editor: subtypes keyed by their sub',
  sci.kids[2].kids.length === 2 && sci.kids[2].kids[0].parent === 'Other Science');
check('editor: single-sub category has no kids', tree.find(n => n.name === 'Religion').kids.length === 0);

ed.renderDistEditor();
check('editor: one row per category', byId.disttree.children.filter(c => c._cls.has('drow')).length === 12);
check('editor: total footer', /weights sum/.test(byId.disttotal.textContent), byId.disttotal.textContent);

ed.distOpen.add('Science');
ed.renderDistEditor();
const kidsBox = byId.disttree.children.find(c => c._cls.has('kids'));
check('editor: expanded kids rendered', !!kidsBox && kidsBox.children.filter(c => c._cls.has('drow')).length === 3);
const bioRow = kidsBox.children.find(c => c.children.some(x => x._text === 'Biology'));
const bioInput = bioRow.children.find(c => c.tag === 'input');
check('editor: untouched input dimmed', bioInput._cls.has('untouched'));
bioInput.value = '2';
bioInput.onchange();
check('editor: edit persists the whole group',
  JSON.stringify(ed.settings.distSub['Science']) === JSON.stringify({ Biology: 2, Chemistry: 1, 'Other Science': 1 }),
  JSON.stringify(ed.settings.distSub));
check('editor: edit saves prefs + rebuilds queue', ed.counters().savedCount >= 1 && ed.counters().rebuilt >= 1);

ed.renderDistEditor();
const kidsBox2 = byId.disttree.children.find(c => c._cls.has('kids'));
const evenBtn = (kidsBox2.children.find(c => c._cls.has('evenrow')) || { children: [] }).children[0];
check('editor: Even link rendered for touched group', !!evenBtn);
evenBtn.onclick();
check('editor: Even clears the group', ed.settings.distSub['Science'] === undefined);

ed.renderDistEditor();
const sciRow = byId.disttree.children.find(c => c.children.some(x => x._text === 'Science'));
check('editor: Science share 19% of the default mix',
  sciRow.children.find(c => c._cls.has('dpct'))._text === '19%');

console.log(pass + ' passed, ' + fail + ' failed');
process.exit(fail ? 1 : 0);
