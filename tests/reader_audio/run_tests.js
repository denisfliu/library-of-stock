// Regression test for the reader's read-aloud queue restriction
// (lib/js/reader.js: audioMode / hasAudio gate in rowInScope). When
// read-aloud is on AND the audio manifest has loaded, only questions that
// have audio may enter scope; before the manifest loads (AUDIO_HAVE null),
// nothing is filtered (so the queue never collapses to empty mid-load); with
// read-aloud off, audio is irrelevant. Executes the REAL sliced functions
// against a synthetic catalog. Run: node tests/reader_audio/run_tests.js
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

// Slice the real audio gate (AUDIO_HAVE + hasAudio + audioMode) and the real
// filtering stack (filters, taxonomy maps, catName..rowInScope). settings is
// stubbed to just {voice}; the rest of the audio module (playback, fetch) is
// not included — only the queue-gate functions matter here.
const code = [
  'let CAT = null;',
  'const settings = { voice: false };',
  slice('let AUDIO_HAVE = null;', '\nfunction loadAudioIndex'),
  'function voiceAvailable(){return true;}',
  slice('const filters = {', '\n// Subcategories whose'),
  slice('let SUBTYPED_SUBS = null;', '\n// Standard quizbowl'),
  slice('const catName =', '\nfunction chip('),
].join('\n');

const ctx = vm.createContext({
  console, Set, Map, Object, Array, JSON, Number, String, Math,
  ID2SLUG: new Map(), TOPICS: {}, eraOf: () => null,
});
vm.runInContext(code +
  '\n; globalThis.__api = { filters, settings, rowInScope, refreshBranchScopes,' +
  ' setCAT: c => { CAT = c; }, setAudio: s => { AUDIO_HAVE = s; }, audioMode, hasAudio };',
  ctx, { filename: 'reader.js (sliced)' });
const api = ctx.__api;

/* ---- synthetic catalog: 3 tossups, distinct ids ---- */
const CAT = {
  category_values: ['Science'], subcategory_values: ['Biology'],
  alternate_subcategory_values: [], section_values: [],
  tossups: {
    id: ['aa1', 'aa2', 'bb3'],
    category: [0, 0, 0], subcategory: [0, 0, 0],
    alternate_subcategory: [-1, -1, -1], difficulty: [7, 8, 9], section: [-1, -1, -1],
  },
};
api.setCAT(CAT);
api.filters.diffs.clear();   // isolate the audio gate from the default diff-7 filter
api.refreshBranchScopes();

let pass = 0, fail = 0;
function check(name, cond) {
  if (cond) { pass++; console.log('  ok  ' + name); }
  else { fail++; console.log('FAIL  ' + name); }
}
const inScope = () => [0, 1, 2].filter(r => api.rowInScope(r, 'all'));

// 1. read-aloud OFF: all three rows in scope regardless of audio set
api.settings.voice = false;
api.setAudio(new Set(['aa1']));
check('voice off -> all rows in scope', inScope().length === 3);

// 2. read-aloud ON, manifest NOT loaded (AUDIO_HAVE null): no filtering
api.settings.voice = true;
api.setAudio(null);
check('voice on, manifest unloaded -> all rows (no premature filter)', inScope().length === 3);

// 3. read-aloud ON, manifest loaded: only rows whose id has audio
api.settings.voice = true;
api.setAudio(new Set(['aa1', 'bb3']));
const scoped = inScope();
check('voice on + manifest -> only audio-backed rows', scoped.length === 2);
check('voice on + manifest -> excludes the no-audio row', !scoped.includes(1));
check('voice on + manifest -> includes both audio rows', scoped.includes(0) && scoped.includes(2));

// 4. empty audio set -> nothing in scope (honest: no audio, no questions)
api.setAudio(new Set());
check('voice on + empty manifest -> zero rows in scope', inScope().length === 0);

console.log(`\n${pass} passed, ${fail} failed`);
process.exit(fail ? 1 : 0);
