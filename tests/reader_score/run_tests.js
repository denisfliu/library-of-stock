// Tests for score-clue mode's reading plan (lib/js/reader.js):
//   - scoreMask: note-run sentences detected via the shared slowSpans/
//     buildUnits pacing logic (comma runs AND dash runs)
//   - readingPlan: geometry + bf measure, exact parity with the legacy
//     skipWords/units math for full and last-n reads
//   - missedQueryFor round-trips score-mode LOG rows (bf + sent + sg)
//   - lib/mirror/notation_scan.js (the publish-time catalog bit) agrees
//     with scoreMask on every fixture
// Run: node tests/reader_score/run_tests.js
'use strict';
const fs = require('fs');
const os = require('os');
const path = require('path');
const vm = require('vm');
const { execFileSync } = require('child_process');

function slice(src, startMarker, endMarker, label) {
  const i = src.indexOf(startMarker);
  const j = src.indexOf(endMarker, i);
  if (i < 0 || j < 0) throw new Error('marker not found in ' + label + ': ' + startMarker);
  return src.slice(i, j);
}

const ctx = vm.createContext({ Math, Number, Array, Object, JSON, RegExp, String, globalThis: null });
ctx.globalThis = ctx;
vm.runInContext(
  fs.readFileSync(path.join(__dirname, '../../lib/js/reveal_units.js'), 'utf8'),
  ctx, { filename: 'reveal_units.js' });

const readerSrc = fs.readFileSync(path.join(__dirname, '../../lib/js/reader.js'), 'utf8');
vm.runInContext(
  'const { buildUnits, slowSpans } = globalThis.qbRevealUnits;\n'
  + slice(readerSrc, 'const ABBREV', 'const { buildUnits', 'reader.js (splitSentences)')
  + slice(readerSrc, 'function scoreMask(', '\n/* ---------- answer', 'reader.js (readingPlan)')
  + slice(readerSrc, 'function missedQueryFor(', '\nfunction missedOrder(', 'reader.js (missedQueryFor)')
  + '\n; globalThis.__t = { splitSentences, scoreMask, readingPlan, missedQueryFor, buildUnits };',
  ctx, { filename: 'reader.js (sliced)' });
const { splitSentences, scoreMask, readingPlan, missedQueryFor, buildUnits } = ctx.__t;

let pass = 0, fail = 0;
const check = (label, cond, detail) => {
  if (cond) { pass++; }
  else { fail++; console.error('FAIL ' + label + (detail ? ' — ' + detail : '')); }
};
const eq = (a, b) => JSON.stringify(a) === JSON.stringify(b);

/* ---- fixture: two notation sentences (dash run + comma run) ---- */
const S = [
  'One scene in this opera replaced its planned glass harmonica accompaniment with a harp solo.',
  'One character in this opera recalls seeing a ghost by a fountain in an early aria.',
  'Its Act 2 sextet begins with a tenor melody on D–D–D–C♯–D, marked Larghetto.',
  'In its final scene, Edgardo stabs himself after learning his beloved has died.',
  'A (*) flute echoes a mad scene whose cabaletta begins with the melody C, high A, F, long C, B, long D, C, but is often sung a step lower.',
  'For 10 points, name this Donizetti opera about a fragile Scottish bride.',
];
const TEXT = S.join(' ');
const doc = { question_sanitized: TEXT };
const words = s => s.split(/\s+/).filter(Boolean);
const unitsOf = s => buildUnits(words(s));

check('fixture splits into 6 sentences', eq(splitSentences(TEXT), S),
  String(splitSentences(TEXT).length));

/* ---- scoreMask detection ---- */
{
  const m = scoreMask(S);
  check('scoreMask flags the dash-run and comma-run sentences only',
    eq(m, [false, false, true, false, true, false]), JSON.stringify(m));
  check('scoreMask: prose-only text has no notation',
    !scoreMask([S[0], S[1], S[3]]).some(Boolean));
}

/* ---- readingPlan: legacy parity for full and last-n ---- */
{
  const full = readingPlan(TEXT, 0, true);
  check('full read: every sentence read, mode full',
    full.mode === 'full' && full.mask.every(Boolean)
    && full.startSent === 0 && full.skipWords === 0);
  check('full read: pos[i] == i and total == units.length',
    full.pos.every((p, i) => p === i) && full.total === full.units.length);
  check('full read: units match a whole-text buildUnits',
    eq(full.units, buildUnits(words(TEXT))));

  const n = 2;
  const lastn = readingPlan(TEXT, n, true);
  const startSent = S.length - n;
  const skipWords = words(S.slice(0, startSent).join(' ')).length;
  const legacyUnits = buildUnits(S.slice(startSent).join(' ').split(/\s+/));
  check('last-2: startSent/skipWords match the legacy formulas',
    lastn.startSent === startSent && lastn.skipWords === skipWords,
    JSON.stringify([lastn.startSent, lastn.skipWords]));
  check('last-2: units match the legacy suffix build', eq(lastn.units, legacyUnits));
  check('last-2: pos[i] == skipWords + i (incl. the sentinel) and total matches',
    lastn.pos.every((p, i) => p === skipWords + i)
    && lastn.total === skipWords + legacyUnits.length);
}

/* ---- readingPlan: score mode geometry ---- */
{
  const plan = readingPlan(TEXT, 'score', true);
  check('score+giveaway: mask = notation sentences + giveaway',
    plan.mode === 'score' && eq(plan.mask, [false, false, true, false, true, true]),
    JSON.stringify(plan.mask));
  check('score: units are the read sentences’ units concatenated',
    eq(plan.units, [].concat(unitsOf(S[2]), unitsOf(S[4]), unitsOf(S[5]))));
  const w = i => words(S[i]).length;
  const k2 = unitsOf(S[2]).length, k4 = unitsOf(S[4]).length, k5 = unitsOf(S[5]).length;
  check('score: dash run split into per-note units', k2 > w(2), k2 + ' vs ' + w(2));
  check('score: measure interleaves hidden words and read units',
    plan.pos[0] === w(0) + w(1)
    && plan.pos[k2] === w(0) + w(1) + k2 + w(3)
    && plan.total === w(0) + w(1) + k2 + w(3) + k4 + k5,
    JSON.stringify([plan.pos[0], plan.pos[k2], plan.total]));
  check('score: charStart offsets index the read text',
    plan.sentInfo[2].charStart === 0
    && plan.sentInfo[4].charStart === S[2].length + 1
    && plan.sentInfo[5].charStart === S[2].length + 1 + S[4].length + 1);

  const noGive = readingPlan(TEXT, 'score', false);
  check('score, giveaway off: last sentence hidden; trailing words stay in the total',
    !noGive.mask[5]
    && noGive.total - noGive.pos[noGive.units.length] === w(5),
    JSON.stringify([noGive.mask[5], noGive.total, noGive.pos[noGive.units.length]]));

  const fallback = readingPlan(S[0] + ' ' + S[3], 'score', true);
  check('score on a no-notation question: falls back to a full read',
    fallback.mode === 'full' && fallback.mask.every(Boolean));
}

/* ---- missedQueryFor: score-mode round-trip ---- */
{
  const plan = readingPlan(TEXT, 'score', true);
  const k2 = unitsOf(S[2]).length, k4 = unitsOf(S[4]).length;
  const expectSent = fb => fb === 0 ? plan.startSent
    : fb <= k2 ? 2 : fb <= k2 + k4 ? 4 : 5;
  let ok = true, detail = '';
  for (let fb = 0; fb <= plan.units.length; fb++) {
    const rec = { bf: Math.round(plan.pos[fb] / plan.total * 1000) / 1000, sent: 'score', sg: true };
    const got = missedQueryFor(rec, doc);
    if (got.lastHeard !== expectSent(fb)) {
      ok = false; detail = 'fb=' + fb + ' got=' + got.lastHeard + ' want=' + expectSent(fb);
      break;
    }
  }
  check('score round-trip: all ' + (plan.units.length + 1) + ' buzz positions recover their sentence', ok, detail);

  // buzz early in the comma-run sentence: queries reach back through the
  // hidden sentence before it
  const fb = k2 + 2;
  const rec = { bf: Math.round(plan.pos[fb] / plan.total * 1000) / 1000, sent: 'score', sg: true };
  const got = missedQueryFor(rec, doc);
  check('score: queries reach back into hidden clues',
    got.lastHeard === 4 && eq(got.queries.map(q => q.qi), [3, 2, 1])
    && got.queries[0].text === S[3],
    JSON.stringify({ lastHeard: got.lastHeard, qis: got.queries.map(q => q.qi) }));

  // dead in score mode: last heard is the giveaway
  const dead = missedQueryFor({ bf: null, sent: 'score', sg: true }, doc);
  check('score dead: queries the 3 sentences before the giveaway',
    dead.lastHeard === 5 && eq(dead.queries.map(q => q.qi), [4, 3, 2]));

  // giveaway off: rec.sg false re-derives the shorter read
  const ng = readingPlan(TEXT, 'score', false);
  const lastUnit = ng.units.length;
  const recNg = { bf: Math.round(ng.pos[lastUnit] / ng.total * 1000) / 1000, sent: 'score', sg: false };
  check('score, giveaway off: end-of-read buzz lands in the comma-run sentence',
    missedQueryFor(recNg, doc).lastHeard === 4,
    String(missedQueryFor(recNg, doc).lastHeard));
}

/* ---- notation_scan.js (publish-time catalog bit) parity ---- */
{
  const cases = S.concat([TEXT, '', S[0] + ' ' + S[3]]);
  const tmp = path.join(os.tmpdir(), 'notation_scan_test_' + process.pid + '.jsonl');
  fs.writeFileSync(tmp, cases.map(t => JSON.stringify(t)).join('\n') + '\n');
  let bits = '';
  try {
    bits = execFileSync(process.execPath,
      [path.join(__dirname, '../../lib/mirror/notation_scan.js'), tmp],
      { encoding: 'utf8' });
  } finally { fs.unlinkSync(tmp); }
  const want = cases.map(t => scoreMask(splitSentences(t)).some(Boolean) ? '1' : '0').join('');
  check('notation_scan agrees with scoreMask on every fixture', bits === want,
    bits + ' vs ' + want);
}

console.log(`${pass}/${pass + fail} reader score-mode cases pass`);
process.exit(fail ? 1 : 0);
