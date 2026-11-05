// Regression tests for the reader's read-aloud mode (lib/js/reader.js), in two
// parts:
//
// 1. QUEUE RESTRICTION (audioMode / hasAudio gate in rowInScope). When
//    read-aloud is on AND the audio manifest has loaded, only questions that
//    have audio may enter scope; before the manifest loads (AUDIO_HAVE null),
//    nothing is filtered (so the queue never collapses to empty mid-load); with
//    read-aloud off, audio is irrelevant.
// 2. SIDECAR MAPPING (audio time -> text position). The {qid}.json sidecar's
//    spoken words (cleaned text: guides stripped, "Mrs." -> "Missus", "(*)"
//    silent) are aligned to the displayed words, so buzz depth is the word the
//    voice reached — exactly, and in last-n-sentence mode too, where the audio
//    reads the whole question. Covers v1 (chunk offsets) and v2 (word offsets)
//    sidecars and the proportional fallback when there is no sidecar.
//
// Executes the REAL sliced functions. Run: node tests/reader_audio/run_tests.js
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
  'const settings = { voice: false, sent: 0 };',
  'function scoreModeOn() { return settings.sent === \'score\'; }',
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

// 5. score-clue mode wins over voice: the audio restriction must not stack
// onto the notation one (read-aloud is disabled in score mode).
api.settings.sent = 'score';
check('score mode -> audio gate off even with voice on', inScope().length === 3);
api.settings.sent = 0;

/* ================= part 2: sidecar audio-time -> text mapping ================= */
// Second context: the pure mapping block plus the real audioWordIdx (whose
// globals — cur, audioEl, wordIdx — are stubbed so both branches are reachable).
const mapCode = [
  slice('const NORM_W =', '/* ---------- end sidecar mapping ---------- */'),
  slice('// Map the audio clock to a reveal-unit index', '\nfunction playAudio'),
].join('\n');
const ctx2 = vm.createContext({ console, Set, Map, Object, Array, JSON, Number, String, Math });
vm.runInContext(fs.readFileSync(path.join(__dirname, '../../lib/js/reveal_units.js'), 'utf8'),
                ctx2, { filename: 'reveal_units.js' });
vm.runInContext('let cur = null, wordIdx = 0; const audioEl = { currentTime: 0, duration: 0 };\n'
  + mapCode
  + '\n; globalThis.__m = { alignSpokenToDisplay, spokenTimeline, buildAudioMap, dispWordsHeard,'
  + ' audioTimeForDispWord, wordUnitStarts, unitIdxForDispWord, audioWordIdx,'
  + ' buildUnits: globalThis.qbRevealUnits.buildUnits,'
  + ' setCur: c => { cur = c; }, setWordIdx: w => { wordIdx = w; }, audioEl };',
  ctx2, { filename: 'reader.js (sliced: sidecar mapping)' });
const m = ctx2.__m;

// -- alignment across the cleaner's edits --
check('align skips a stripped pronunciation guide',
  JSON.stringify(m.alignSpokenToDisplay(
    ['Grignard', 'reagents', 'add'],
    ['Grignard', 'reagents', '[green-YARR]', 'add'])) === '[0,1,3]');
check('align handles an expanded abbreviation (Mrs. -> Missus)',
  JSON.stringify(m.alignSpokenToDisplay(
    ['This', 'novel', 'opens', 'as', 'Missus', 'Dalloway'],
    ['This', 'novel', 'opens', 'as', 'Mrs.', 'Dalloway'])) === '[0,1,2,3,4,5]');
check('align skips the silent power mark',
  JSON.stringify(m.alignSpokenToDisplay(
    ['name', 'this', 'author'], ['name', '(*)', 'this', 'author'])) === '[0,2,3]');
check('align is monotone across a stripped moderator note',
  JSON.stringify(m.alignSpokenToDisplay(
    ['The', 'clue', 'follows'],
    ['The', '[Note', 'to', 'moderator:', 'read', 'slowly.]', 'clue', 'follows'])) === '[0,6,7]');

// -- timelines from both sidecar versions --
const v1 = { v: 1, chunks: [[0, 4], [4, 6]], texts: ['a b c d', 'e f'] };
const t1 = m.spokenTimeline(v1);
check('v1 sidecar interpolates words across the chunk span',
  t1.length === 6 && t1[0].s === 0 && t1[1].s === 1 && t1[3].s === 3);
check('v1 sidecar keeps chunk boundaries exact', t1[4].s === 4 && t1[5].s === 5);
const v2 = { v: 2, chunks: [[0, 1]], texts: ['a b'], words: [['a', 0, 0.4], ['b', 0.55, 1.0]] };
const t2 = m.spokenTimeline(v2);
check('v2 sidecar uses the aligned word times',
  t2.length === 2 && t2[0].e === 0.4 && t2[1].s === 0.55);
check('v2 wins over chunk interpolation when both are present', m.spokenTimeline(v2)[1].s === 0.55);
check('empty sidecar -> no timeline', m.spokenTimeline(null).length === 0);
check('buildAudioMap needs both sides', m.buildAudioMap(v2, []) === null
  && m.buildAudioMap({}, ['a']) === null);

// -- time -> display word --
const map = m.buildAudioMap(
  { v: 2, chunks: [[0, 3]], texts: ['Alpha beta gamma'],
    words: [['Alpha', 0.0, 0.9], ['beta', 1.0, 1.9], ['gamma', 2.0, 2.9]] },
  ['Alpha', '(*)', 'beta', 'gamma']);
check('before the first word -> nothing heard', m.dispWordsHeard(map, -1) === 0);
check('inside the first word -> one display word heard', m.dispWordsHeard(map, 0.5) === 1);
check('inside the second word -> past the silent mark', m.dispWordsHeard(map, 1.5) === 3);
check('after the last word -> whole question heard', m.dispWordsHeard(map, 9) === 4);
check('seek target is the first spoken word at/after the display index',
  m.audioTimeForDispWord(map, 2) === 1.0 && m.audioTimeForDispWord(map, 0) === 0.0);
check('seek target is null past the end', m.audioTimeForDispWord(map, 99) === null);

// -- display words -> reveal units (note runs split into several units) --
const units = m.buildUnits(['The', 'motif', 'E–F♯–G–E', 'recurs']);
const starts = m.wordUnitStarts(units);
check('note run splits into units but stays one display word',
  units.length > 4 && starts.length === 4);
check('unit index respects the note-run split',
  m.unitIdxForDispWord(starts, units.length, 0, 3) === starts[3]);
check('nothing heard -> no units revealed', m.unitIdxForDispWord(starts, units.length, 0, 0) === 0);
check('all heard -> every unit revealed',
  m.unitIdxForDispWord(starts, units.length, 0, 4) === units.length);
check('skipped sentences shift the frame (last-n mode)',
  m.unitIdxForDispWord(starts, units.length, 2, 3) === starts[1]
  && m.unitIdxForDispWord(starts, units.length, 2, 2) === 0);

// -- audioWordIdx: exact with a map, proportional without --
const words10 = ['w0', 'w1', 'w2', 'w3', 'w4', 'w5', 'w6', 'w7', 'w8', 'w9'];
const u10 = m.buildUnits(words10);
const exactMap = m.buildAudioMap(
  { v: 2, chunks: [[0, 10]], texts: words10.join(' '),
    words: words10.map((w, i) => [w, i, i + 0.9]) },
  words10);
m.setCur({ units: u10, unitStarts: m.wordUnitStarts(u10), skipWords: 0, audioMap: exactMap });
m.audioEl.duration = 10;
m.audioEl.currentTime = 4.5;
check('exact mapping reads the spoken word, not the clock ratio', m.audioWordIdx() === 5);
m.audioEl.currentTime = 0.1;
check('exact mapping at the very start', m.audioWordIdx() === 1);
// Last-n mode: the audio covers all 10 words, the reader reveals the last 4.
const u4 = m.buildUnits(words10.slice(6));
m.setCur({ units: u4, unitStarts: m.wordUnitStarts(u4), skipWords: 6, audioMap: exactMap });
m.audioEl.currentTime = 7.5;
check('last-n mode: depth is measured from the read portion', m.audioWordIdx() === 2);
m.audioEl.currentTime = 3.0;
check('last-n mode: audio before the read portion is depth 0', m.audioWordIdx() === 0);
// No sidecar -> the old proportional estimate, and an unknown duration holds
// the current index rather than jumping.
m.setCur({ units: u10, unitStarts: m.wordUnitStarts(u10), skipWords: 0, audioMap: null });
m.audioEl.currentTime = 5;
check('no sidecar -> proportional fallback', m.audioWordIdx() === 5);
m.audioEl.duration = NaN;
m.setWordIdx(3);
check('unknown duration -> keep the current index', m.audioWordIdx() === 3);

console.log(`\n${pass} passed, ${fail} failed`);
process.exit(fail ? 1 : 0);
