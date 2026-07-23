// Regression test for the missed-clues report's buzz-sentence derivation:
// missedQueryFor in lib/js/reader.js re-derives the buzz sentence from a
// LOG row alone (bf + sent), with nothing extra stored. Executes the REAL
// sliced functions against ground truth computed independently from word
// counts. Run: node tests/missed_clues/run_tests.js
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

/* ---- build the context: real reveal units + real reader slices ---- */
const ctx = vm.createContext({ Math, Number, Array, Object, JSON, RegExp, String, globalThis: null });
ctx.globalThis = ctx;
vm.runInContext(
  fs.readFileSync(path.join(__dirname, '../../lib/js/reveal_units.js'), 'utf8'),
  ctx, { filename: 'reveal_units.js' });

const readerSrc = fs.readFileSync(path.join(__dirname, '../../lib/js/reader.js'), 'utf8');
vm.runInContext(
  'const { buildUnits } = globalThis.qbRevealUnits;\n'
  + slice(readerSrc, 'const ABBREV', 'const { buildUnits', 'reader.js (splitSentences)')
  + slice(readerSrc, 'function missedQueryFor(', '\nfunction missedOrder(', 'reader.js (missedQueryFor)')
  + '\n; globalThis.__t = { splitSentences, missedQueryFor, buildUnits };',
  ctx, { filename: 'reader.js (sliced)' });
const { splitSentences, missedQueryFor, buildUnits } = ctx.__t;

let pass = 0, fail = 0;
const check = (label, cond, detail) => {
  if (cond) { pass++; }
  else { fail++; console.error('FAIL ' + label + (detail ? ' — ' + detail : '')); }
};

/* ---- ground truth from word counts (independent of char offsets) ----
   For plain prose (no dash note runs) units are 1:1 with words, so the
   last-heard sentence is simply the sentence containing word fb-1 of the
   read text. */
function truth(text, nSent, fb) {
  const sents = splitSentences(text);
  const startSent = (nSent > 0 && sents.length > nSent) ? sents.length - nSent : 0;
  if (fb === 0) return { lastHeard: startSent };
  const counts = sents.slice(startSent).map(s => s.split(/\s+/).length);
  let w = 0;
  for (let i = 0; i < counts.length; i++) {
    w += counts[i];
    if (fb - 1 < w) return { lastHeard: startSent + i };
  }
  return { lastHeard: sents.length - 1 };
}

// Simulate record(): bf as the reader stores it (3-decimal rounding).
function recFor(text, nSent, fb) {
  const sents = splitSentences(text);
  const startSent = (nSent > 0 && sents.length > nSent) ? sents.length - nSent : 0;
  const skipped = sents.slice(0, startSent).join(' ');
  const skipWords = skipped ? skipped.split(/\s+/).length : 0;
  const units = buildUnits(sents.slice(startSent).join(' ').split(/\s+/));
  const total = skipWords + units.length;
  return {
    bf: Math.round((skipWords + fb) / total * 1000) / 1000,
    sent: nSent,
    nUnits: units.length,
  };
}

const TEXT = 'In one novel by this author, a governess at Bly sees the ghosts of '
  + 'Peter Quint and Miss Jessel. Another of his novels follows Isabel Archer, '
  + 'who marries Gilbert Osmond after inheriting a fortune. This author wrote '
  + 'about Lambert Strether in a novel set largely in Paris. For 10 points, '
  + 'name this American-born author of The Turn of the Screw.';
const doc = { question_sanitized: TEXT };
const SENTS = splitSentences(TEXT);
check('fixture splits into 4 sentences', SENTS.length === 4, String(SENTS.length));

/* ---- full read: every buzz position round-trips exactly ---- */
{
  const nUnits = recFor(TEXT, 0, 0).nUnits;
  let ok = true, detail = '';
  for (let fb = 0; fb <= nUnits; fb++) {
    const rec = recFor(TEXT, 0, fb);
    const got = missedQueryFor(rec, doc);
    const want = truth(TEXT, 0, fb);
    if (got.lastHeard !== want.lastHeard) {
      ok = false;
      detail = 'fb=' + fb + ' got=' + got.lastHeard + ' want=' + want.lastHeard;
      break;
    }
    if (got.qi !== Math.max(0, want.lastHeard - 1)) {
      ok = false; detail = 'fb=' + fb + ' qi=' + got.qi; break;
    }
    if (got.query !== SENTS[got.qi]) { ok = false; detail = 'fb=' + fb + ' query mismatch'; break; }
  }
  check('full read: all ' + (nUnits + 1) + ' buzz positions round-trip', ok, detail);
}

/* ---- trimmed read (last 2 sentences): positions round-trip ---- */
{
  const nUnits = recFor(TEXT, 2, 0).nUnits;
  let ok = true, detail = '';
  for (let fb = 0; fb <= nUnits; fb++) {
    const rec = recFor(TEXT, 2, fb);
    const got = missedQueryFor(rec, doc);
    const want = truth(TEXT, 2, fb);
    if (got.lastHeard !== want.lastHeard) {
      ok = false;
      detail = 'fb=' + fb + ' got=' + got.lastHeard + ' want=' + want.lastHeard;
      break;
    }
  }
  check('last-2 trim: all ' + (nUnits + 1) + ' buzz positions round-trip', ok, detail);
  // buzz inside the first READ sentence still queries the unheard one before it
  const got = missedQueryFor(recFor(TEXT, 2, 3), doc);
  check('trim: query reaches back into the unread text',
    got.lastHeard === 2 && got.qi === 1 && got.query === SENTS[1],
    JSON.stringify({ lastHeard: got.lastHeard, qi: got.qi }));
}

/* ---- edge cases ---- */
{
  // dead question: last heard is the giveaway, query the sentence before it
  const got = missedQueryFor({ bf: null, sent: 0 }, doc);
  check('dead: query = second-to-last sentence',
    got.lastHeard === 3 && got.qi === 2 && got.query === SENTS[2],
    JSON.stringify(got));

  // buzz before the first word: clamp to sentence 0
  const got0 = missedQueryFor(recFor(TEXT, 0, 0), doc);
  check('buzz at word 0: clamps to sentence 0', got0.qi === 0 && got0.query === SENTS[0]);

  // buzz in sentence 0: no earlier sentence to query
  const got1 = missedQueryFor(recFor(TEXT, 0, 5), doc);
  check('buzz in sentence 0: queries sentence 0', got1.lastHeard === 0 && got1.qi === 0);

  // one-sentence question, dead
  const one = { question_sanitized: 'Name this element with atomic number 79.' };
  const gotOne = missedQueryFor({ bf: null, sent: 0 }, one);
  check('one-sentence dead: queries the only sentence', gotOne.qi === 0);

  // empty text
  check('empty text -> null', missedQueryFor({ bf: 0.5, sent: 0 }, { question_sanitized: '' }) === null);
}

console.log(`${pass}/${pass + fail} missed-clues derivation cases pass`);
process.exit(fail ? 1 : 0);
