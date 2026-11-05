// notation_scan.js — per-question "has a musical note run" bits for the
// catalog's notation column (score-clue mode's corpus restriction).
//
// Invoked by publish.py: `node notation_scan.js texts.jsonl` where each
// line of the input file is one JSON-encoded question_sanitized string.
// Emits one '0'/'1' character per line to stdout, in order.
//
// Detection is THE shared note-run logic from lib/js/reveal_units.js
// (buildUnits splits dash runs like "D–D–C♯" into per-note tokens, then
// slowSpans finds runs of >=3 notes) — required via the file itself so the
// publish-time bit can never drift from what reader.js scoreMask reveals.
'use strict';
const fs = require('fs');
const path = require('path');

require(path.join(__dirname, '..', 'js', 'reveal_units.js'));
const { buildUnits, slowSpans } = globalThis.qbRevealUnits;

function hasNotation(text) {
  const toks = buildUnits(String(text).split(/\s+/).filter(Boolean)).map(u => u.t);
  return slowSpans(toks).size > 0;
}

const lines = fs.readFileSync(process.argv[2], 'utf8').split('\n');
let out = '';
for (const line of lines) {
  if (!line) continue;   // trailing newline
  out += hasNotation(JSON.parse(line)) ? '1' : '0';
}
process.stdout.write(out);
