// Regression test for lib/js/answer_checker.js (the vendored qbreader
// answer checker). Runs upstream's published test corpus (the two CSVs,
// copied verbatim from github.com/qbreader/qb-answer-checker/test) plus a
// handful of reader-specific cases. Run: node tests/answer_checker/run_tests.js
'use strict';
const fs = require('fs');
const path = require('path');
const { checkAnswer } = require('../../lib/js/answer_checker.js');

// minimal RFC-4180 CSV parser (quoted fields + "" escapes)
function parseCsv(text) {
  const rows = [];
  let row = [], field = '', inQ = false;
  for (let i = 0; i < text.length; i++) {
    const c = text[i];
    if (inQ) {
      if (c === '"') {
        if (text[i + 1] === '"') { field += '"'; i++; }
        else inQ = false;
      } else field += c;
    } else if (c === '"') inQ = true;
    else if (c === ',') { row.push(field); field = ''; }
    else if (c === '\n' || c === '\r') {
      if (c === '\r' && text[i + 1] === '\n') i++;
      row.push(field); field = '';
      if (row.some(f => f !== '')) rows.push(row);
      row = [];
    } else field += c;
  }
  row.push(field);
  if (row.some(f => f !== '')) rows.push(row);
  return rows;
}

let total = 0, failed = 0;
function expect(answerline, given, directive, directedPrompt = '', origin = '') {
  total++;
  const r = checkAnswer(answerline, given);
  if (r.directive !== directive || (r.directedPrompt || '') !== directedPrompt) {
    failed++;
    console.error(`FAIL${origin} given=${JSON.stringify(given)} ` +
      `expected=${directive}${directedPrompt ? '/' + directedPrompt : ''} ` +
      `got=${r.directive}${r.directedPrompt ? '/' + r.directedPrompt : ''}`);
    console.error(`     answerline=${answerline}`);
  }
}

for (const file of ['formatted-tests.csv', 'unformatted-tests.csv']) {
  const rows = parseCsv(fs.readFileSync(path.join(__dirname, file), 'utf-8')).slice(1);
  for (const [directive, given, directedPrompt, answerline] of rows) {
    if (answerline) expect(answerline, given, directive, directedPrompt || '', ` [${file}]`);
  }
}

// reader-specific cases: the punctuated-abbreviation bug that motivated the
// vendoring (R.U.R. must accept "RUR"), plus prompt/reject plumbing the
// reader relies on.
expect('<b><u>R.U.R.</u></b> [or <b><u>Rossum’s Universal Robots</u></b>]', 'RUR', 'accept');
expect('<b><u>R.U.R.</u></b>', 'rur', 'accept');
expect('<b><u>Rossum’s Universal Robots</u></b>', 'RUR', 'accept');
expect('<b><u>mitochondria</u></b> [prompt on organelle by asking "which organelle?"]', 'organelle', 'prompt', 'which organelle?');
expect('<b><u>Gogol</u></b> [reject "Google"]', 'google', 'reject');
expect('<b><u>Mendelssohn</u></b> [or Felix <b><u>Mendelssohn</u></b> Bartholdy]', 'bartholdy', 'reject');
expect('<b><u>Mendelssohn</u></b>', 'mendelssohn', 'accept');
expect('anything', '', 'reject'); // empty answer concedes

console.log(`${total - failed}/${total} answer-checker cases pass`);
process.exit(failed ? 1 : 0);
