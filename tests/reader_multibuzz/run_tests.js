// Regression test for the reader's multibuzz mode (lib/js/reader.js:
// buzz/negContinue/resumeAfterNeg/judged/goDead/record). With the toggle ON,
// a wrong answer doesn't end the question — reading resumes from the buzz
// point and the player can buzz again — but stats stay honest: exactly one
// LOG row per question, res 'W' if ANY buzz was wrong, bf/pow from the FIRST
// buzz. Executes the REAL sliced functions with the real answer checker.
// Run: node tests/reader_multibuzz/run_tests.js
'use strict';
const fs = require('fs');
const path = require('path');
const vm = require('vm');
const { checkAnswer } = require('../../lib/js/answer_checker.js');
const src = fs.readFileSync(path.join(__dirname, '../../lib/js/reader.js'), 'utf8');

function slice(startMarker, endMarker) {
  const i = src.indexOf(startMarker);
  const j = src.indexOf(endMarker, i);
  if (i < 0 || j < 0) throw new Error('marker not found: ' + startMarker);
  return src.slice(i, j);
}

// Preamble: the module-level state the slices close over, fake DOM/timers,
// and stubs for the DOM-heavy collaborators that aren't under test.
const preamble = `
let cur = null, phase = 'idle', wordIdx = 0, buzzAt = null;
let tick = null, graceTimer = null, graceAnim = null;
let LOG = [];
const sessionRows = [];
const settings = { sent: 0, multibuzz: false };
const audioEl = null;
const window = { losReaderHook: {} };
const performance = { now: () => 0 };

// fake timers with a manual pump (fires a snapshot of pending timeouts)
const __timers = [];
function setTimeout(fn, ms) { const id = { fn, ms }; __timers.push(id); return id; }
function clearTimeout(id) { const i = __timers.indexOf(id); if (i >= 0) __timers.splice(i, 1); }
function setInterval(fn, ms) { const id = { fn, ms, interval: true }; __timers.push(id); return id; }
function clearInterval(id) { clearTimeout(id); }
function firePending() {
  for (const t of __timers.filter(t => !t.interval)) { clearTimeout(t); t.fn(); }
}

// fake elements, memoized by id
const __els = new Map();
function $(id) {
  if (!__els.has(id)) __els.set(id, {
    classList: {
      _s: new Set(),
      add(c) { this._s.add(c); }, remove(c) { this._s.delete(c); },
      toggle(c, on) { on ? this._s.add(c) : this._s.delete(c); },
      contains(c) { return this._s.has(c); },
    },
    style: {}, value: '', focus() {}, textContent: '', innerHTML: '', className: '',
  });
  return __els.get(id);
}

let __status = null;
function setStatus(cls, text) { __status = { cls, text }; }
const __calls = [];
function renderQText() {}
function updateButtons() {}
function stopAudio() { __calls.push('stopAudio'); }
function scheduleStep() { __calls.push('scheduleStep'); }
function loadNext() { __calls.push('loadNext'); }
function audioWordIdx() { return wordIdx; }
function showJudge(res) { __calls.push('showJudge:' + res); }
function answerKey(a, as) { return as || a || null; }
function saveLog() {}
`;

const code = [
  preamble,
  slice('function clearTicks', '\n/* ---------- voice reading'),
  slice('function startGrace', '\nfunction renderQText'),
  slice('function buzz()', '\n/* ---------- previous-question review'),
  slice('function record(', '\n// --- stats state ---'),
  slice('function renderVerdict', '\nfunction showJudge'),
  // the real skip handler (wireUp) — assigns onto the fake element
  slice("$('skipbtn').onclick", "$('qtext').addEventListener"),
].join('\n') + `
; globalThis.__api = {
  settings, buzz, submitAnswer, goDead, regrade, firePending, $,
  LOG: () => LOG, resetLog: () => { LOG = []; },
  setCur: c => { cur = c; }, getCur: () => cur,
  setPhase: p => { phase = p; }, getPhase: () => phase,
  setWordIdx: i => { wordIdx = i; }, getWordIdx: () => wordIdx,
  getBuzzAt: () => buzzAt, setBuzzAt: b => { buzzAt = b; },
  status: () => __status, calls: __calls,
};`;

const ctx = vm.createContext({ console, Set, Map, Object, Array, JSON, Number, String, Math, Date, globalThis: {} });
ctx.globalThis = ctx;
ctx.qbCheckAnswer = checkAnswer;
vm.runInContext(code, ctx, { filename: 'reader.js (sliced)' });
const api = ctx.__api;

/* ---- helpers ---- */
// 10 reveal units with the power mark at index 5
function mkCur(answerline) {
  const words = ['alpha', 'beta', 'gamma', 'delta', 'epsilon', '(*)', 'zeta', 'eta', 'theta', 'iota'];
  return {
    q: { id: 'q1', slug: null, a: answerline, as: answerline, cat: 'Science', sub: 'Chemistry', section: null, d: 7 },
    units: words.map(t => ({ t, sep: ' ' })),
    skipWords: 0, startSent: 0, sents: [], slow: new Set(), showSkipped: false,
    prompted: false, userRaw: null, firstBuzzAt: null, negged: false, lateCorrect: false,
    voice: false,
  };
}
function begin(answerline) {
  api.resetLog();
  api.calls.length = 0;
  api.setCur(mkCur(answerline || 'water [or H2O; prompt on liquid]'));
  api.setPhase('reading');
  api.setWordIdx(0);
  api.setBuzzAt(null);   // startQuestion() resets these (reader.js "wordIdx = 0; buzzAt = null")
}
function buzzAt(i) { api.setWordIdx(i); api.buzz(); }
function answer(text) { api.$('answerinput').value = text; api.submitAnswer(); }

let pass = 0, fail = 0;
function check(name, cond) {
  if (cond) { pass++; console.log('  ok  ' + name); }
  else { fail++; console.log('FAIL  ' + name); }
}

/* 1. multibuzz OFF: a wrong answer ends the question (regression) */
api.settings.multibuzz = false;
begin();
buzzAt(3);
answer('completely wrong nonsense');
check('off: wrong -> one row', api.LOG().length === 1);
check('off: wrong -> res W', api.LOG()[0].res === 'W');
check('off: wrong -> phase done', api.getPhase() === 'done');
check('off: teardown on finalize', api.calls.includes('stopAudio'));

/* 2. ON: neg -> resume -> correct: one row, W, first-buzz bf, lateCorrect */
api.settings.multibuzz = true;
begin();
buzzAt(3);
answer('completely wrong nonsense');
check('on: neg -> no row yet', api.LOG().length === 0);
check('on: neg -> judge hidden', !api.$('judge').classList.contains('show'));
check('on: neg -> beat keeps phase buzzed', api.getPhase() === 'buzzed');
check('on: neg -> keep-listening status', api.status().text === 'No, keep listening');
api.firePending();   // the 700ms beat
check('on: resume -> phase reading', api.getPhase() === 'reading');
check('on: resume -> text reveal restarts', api.calls.includes('scheduleStep'));
buzzAt(8);
answer('water');
check('on: recovered -> one row', api.LOG().length === 1);
check('on: recovered -> res is still W (neg counts)', api.LOG()[0].res === 'W');
check('on: recovered -> bf from FIRST buzz', api.LOG()[0].bf === 0.3);
check('on: recovered -> no power on W row', api.LOG()[0].pow === false);
check('on: recovered -> lateCorrect for UI', api.getCur().lateCorrect === true);
check('on: recovered -> status says correct-but-negged', api.status().text.startsWith('Correct, but negged'));

/* 3. regrade after a recovered neg: row flips to C, power from FIRST buzz */
api.regrade('C');
check('regrade -> row res C', api.LOG()[0].res === 'C');
check('regrade -> pow from first buzz (3 <= powermark 5)', api.LOG()[0].pow === true);

/* 4. ON: neg then never recovered -> grace expires -> one W row */
begin();
buzzAt(9);
answer('still wrong');
api.firePending();   // beat -> resumeAfterNeg; wordIdx 9 < 10 so scheduleStep
api.setWordIdx(10);  // simulate reading out; grace via direct startGrace path:
api.firePending();   // nothing pending except none — call goDead via grace below
// buzz during grace instead: re-neg at the end
buzzAt(10);
answer('wrong again');
api.firePending();   // beat -> resume; wordIdx >= units -> startGrace
api.firePending();   // grace timer -> goDead
check('on: dead after neg -> one row', api.LOG().length === 1);
check('on: dead after neg -> res W not D', api.LOG()[0].res === 'W');
check('on: dead after neg -> bf from first buzz', api.LOG()[0].bf === 0.9);
check('on: dead after neg -> status', api.status().text === 'Dead, neg recorded');
check('on: dead after neg -> override row via W judge', api.calls.includes('showJudge:W'));

/* 5. no buzz at all -> dead stays D with null bf (regression) */
begin();
api.goDead();
check('no buzz -> res D', api.LOG()[0].res === 'D');
check('no buzz -> bf null', api.LOG()[0].bf === null);
check('no buzz -> plain dead status', api.status().text === 'Dead, no buzz');

/* 6. prompt loop: prompt doesn't consume the buzz; empty concede -> neg+resume */
begin();
buzzAt(2);
answer('liquid');    // directed prompt in the answerline
check('prompt -> still buzzed', api.getPhase() === 'buzzed');
check('prompt -> no row', api.LOG().length === 0);
answer('');          // concede -> reject -> multibuzz neg
check('prompt concede -> no row (neg pending)', api.LOG().length === 0);
check('prompt concede -> judge hidden again', !api.$('judge').classList.contains('show'));
api.firePending();
check('prompt concede -> reading resumes', api.getPhase() === 'reading');
buzzAt(6);
answer('water');
check('prompt concede then correct -> one W row', api.LOG().length === 1 && api.LOG()[0].res === 'W');

/* 7. skip after a neg records the W (no stats escape); clean skip records nothing */
begin();
buzzAt(4);
answer('nope');
api.$('skipbtn').onclick();   // during the beat, phase 'buzzed'
check('skip after neg -> neg recorded', api.LOG().length === 1 && api.LOG()[0].res === 'W');
check('skip after neg -> moved on', api.calls.includes('loadNext'));
begin();
api.$('skipbtn').onclick();   // phase 'reading', no buzz
check('clean skip -> nothing recorded', api.LOG().length === 0);

console.log(`\n${pass} passed, ${fail} failed`);
process.exit(fail ? 1 : 0);
