// Tests for reader multiplayer rooms (lib/js/reader_room.js + the
// "multiplayer rooms" block of lib/js/reader.js).
//
// Part 1 checks the pure helpers: the reveal clock against reader.js's own
// scheduleStep timing, buzz clamping, the scoring table, the tally, and the
// clock-offset estimate.
//
// Part 2 plays whole games. Several REAL reader clients (the sliced room
// block + startQuestion + record, each in its own vm context with its own
// state and a different local clock skew) talk through an in-process
// stand-in for the qb-scorekeeper room server (rooms/worker.js semantics:
// armed gate, first-arrival buzz arbitration with a short window, buzz
// position relay, host-only answer relay, stored snapshot + welcome, sync
// echo). Time is virtual; messages carry per-client latency.
// Run: node tests/reader_rooms/run_tests.js
'use strict';
const fs = require('fs');
const path = require('path');
const vm = require('vm');
const { checkAnswer } = require('../../lib/js/answer_checker.js');
const RRmod = require('../../lib/js/reader_room.js');

const ROOT = path.join(__dirname, '../..');
const readerSrc = fs.readFileSync(path.join(ROOT, 'lib/js/reader.js'), 'utf8');
const roomSrc = fs.readFileSync(path.join(ROOT, 'lib/js/reader_room.js'), 'utf8');
const unitsSrc = fs.readFileSync(path.join(ROOT, 'lib/js/reveal_units.js'), 'utf8');

function slice(startMarker, endMarker) {
  const i = readerSrc.indexOf(startMarker);
  const j = readerSrc.indexOf(endMarker, i);
  if (i < 0 || j < 0) throw new Error('marker not found: ' + startMarker);
  return readerSrc.slice(i, j);
}

let pass = 0, fail = 0;
function check(name, cond, extra) {
  if (cond) { pass++; console.log('  ok  ' + name); }
  else { fail++; console.log('FAIL  ' + name + (extra !== undefined ? '  ' + JSON.stringify(extra) : '')); }
}

/* ================= part 1: pure helpers ================= */
console.log('pure helpers');
{
  // scheduleStep reference: the wait before unit i -> i+1 is
  // msPerWord * (slow.has(i) || slow.has(i+1) ? SLOW : 1)
  const ctx = vm.createContext({ globalThis: {} }); ctx.globalThis = ctx;
  vm.runInContext(unitsSrc, ctx);
  const { SLOW_FACTOR } = ctx.qbRevealUnits;
  const slow = new Set([3, 4, 5, 9]);
  const n = 14, mpw = 100;
  const edges = [0];   // edges[k] = ms when unit k+1 becomes visible... built like the timer chain
  let t = 0;
  for (let i = 0; i < n; i++) { t += mpw * ((slow.has(i) || slow.has(i + 1)) ? SLOW_FACTOR : 1); edges.push(t); }
  let ok = true;
  for (let ms = 0; ms <= t + 500; ms += 7) {
    let ref = 0; while (ref < n && edges[ref + 1] <= ms) ref++;
    if (RRmod.unitAt(ms, 0, n, slow, mpw, SLOW_FACTOR) !== ref) { ok = false; break; }
  }
  check('unitAt matches the scheduleStep timer chain (slow spans included)', ok);
  check('unitAt resumes from u0', RRmod.unitAt(0, 7, n, slow, mpw, SLOW_FACTOR) === 7
    && RRmod.unitAt(edges[8] - edges[7], 7, n, slow, mpw, SLOW_FACTOR) === 8);
  check('unitAt clamps at the end', RRmod.unitAt(1e9, 0, n, slow, mpw, SLOW_FACTOR) === n);
  check('unitAt before t0 shows u0', RRmod.unitAt(-50, 4, n, slow, mpw, SLOW_FACTOR) === 4);
  check('msUntilUnit inverts unitAt', [1, 5, 9, 14].every(u =>
    RRmod.unitAt(RRmod.msUntilUnit(u, 0, slow, mpw, SLOW_FACTOR), 0, n, slow, mpw, SLOW_FACTOR) === u));

  check('clampBuzz keeps an honest claim', RRmod.clampBuzz(18, 20, 100) === 18);
  check('clampBuzz rejects a claim ahead of the host', RRmod.clampBuzz(25, 20, 100) === 20);
  check('clampBuzz rejects a claim far behind the host', RRmod.clampBuzz(5, 20, 100) === 20);
  check('clampBuzz without a claim uses the host position', RRmod.clampBuzz(undefined, 20, 100) === 20);

  check('scoring: power / ten / neg / late miss', RRmod.buzzPoints(true, 4, 5, 10) === 15
    && RRmod.buzzPoints(true, 5, 5, 10) === 15 && RRmod.buzzPoints(true, 6, 5, 10) === 10
    && RRmod.buzzPoints(true, 2, -1, 10) === 10 && RRmod.buzzPoints(false, 9, 5, 10) === -5
    && RRmod.buzzPoints(false, 10, 5, 10) === 0);
  const tl = RRmod.tally([{ buzzes: [{ name: 'A', res: 'W', pts: -5 }, { name: 'B', res: 'C', pts: 15 }] },
    { buzzes: [{ name: 'A', res: 'C', pts: 10 }, { name: 'B', res: 'W', pts: 0 }] }]);
  check('tally sums points and P/G/N/0', tl.A.pts === 5 && tl.A.g === 1 && tl.A.n === 1 && tl.A.z === 0
    && tl.B.pts === 15 && tl.B.p === 1 && tl.B.n === 0 && tl.B.z === 1, tl);

  const clk = RRmod.makeClock();
  clk.sample(1000, 6050, 1100);   // rtt 100, server 5000 ahead
  clk.sample(2000, 7020, 2040);   // rtt 40 -> best: offset = 7020 - 2020 = 5000
  check('clock keeps the lowest-RTT sample', clk.now(10000) === 15000 && clk.rtt() === 40);
  check('room code normalization', RRmod.normCode(' abcd ') === 'ABCD' && RRmod.normCode('AB1D') === null
    && RRmod.normCode('ABC') === null);
}

/* ================= part 2: simulated games ================= */

// ---- virtual time ----
let NOW = 1_700_000_000_000;
let seqT = 0;
const timers = [];
function addTimer(fn, ms, interval) {
  const t = { at: NOW + Math.max(0, ms || 0), fn, ms: Math.max(1, ms || 0), interval, id: ++seqT, live: true };
  timers.push(t);
  return t;
}
function clearT(t) { if (t) t.live = false; }
const flush = () => new Promise(r => setImmediate(r));
async function advance(ms) {
  const end = NOW + ms;
  for (;;) {
    let next = null;
    for (const t of timers) if (t.live && t.at <= end && (!next || t.at < next.at || (t.at === next.at && t.id < next.id))) next = t;
    if (!next) break;
    NOW = next.at;
    if (next.interval) next.at += next.ms; else next.live = false;
    next.fn();
    await flush(); await flush();
  }
  NOW = end;
  for (let i = timers.length - 1; i >= 0; i--) if (!timers[i].live) timers.splice(i, 1);
  await flush();
}

// ---- the room server stand-in (rooms/worker.js semantics) ----
const WINDOW_MS = 30;
function makeServer() {
  const S = { conns: [], snapshot: null, armed: false, pending: null, closed: false, dropU: false, states: 0 };
  const deliver = (c, m) => { if (c.open) addTimer(() => { if (c.open) c.onmsg(JSON.parse(JSON.stringify(m))); }, c.lat); };
  const bcast = (m, except) => { for (const c of S.conns) if (c !== except) deliver(c, m); };
  const withU = (m, u) => (u == null || S.dropU ? m : Object.assign({}, m, { u }));
  S.connect = (role, name, lat, onmsg, onopen) => {
    const c = { role, name, lat, onmsg, open: true };
    // the client's frames reach the server after its latency
    c.send = m => addTimer(() => S.recv(c, m), lat);
    addTimer(() => {
      S.conns.push(c);
      onopen && onopen();
      deliver(c, { t: 'welcome', snapshot: S.snapshot, armed: S.armed,
        roster: S.conns.map(x => ({ name: x.name, role: x.role })) });
      bcast({ t: 'join', name, role }, c);
    }, lat);
    return c;
  };
  S.drop = c => { c.open = false; S.conns = S.conns.filter(x => x !== c); bcast({ t: 'leave', name: c.name, role: c.role }); };
  S.recv = (c, m) => {
    if (!c.open) return;
    if (m.t === 'sync') { deliver(c, { t: 'sync', c: m.c, s: NOW }); return; }
    if (m.t === 'typing') { bcast({ t: 'typing', name: c.name, text: String(m.text || '').slice(0, 300) }, c); return; }
    if (m.t === 'chat') { const text = String(m.text || '').trim().slice(0, 300); if (text) bcast({ t: 'chat', name: c.name, text }); return; }
    if (c.role === 'player') {
      if (m.t === 'request') { for (const h of S.conns) if (h.role === 'host') deliver(h, { t: 'request', name: c.name, data: m.data }); return; }
      if (m.t === 'answer') { for (const h of S.conns) if (h.role === 'host') deliver(h, { t: 'answer', name: c.name, text: m.text }); return; }
      if (m.t !== 'buzz') return;
      const u = Number.isInteger(m.u) && m.u >= 0 ? m.u : null;
      if (S.pending) { S.pending.push({ c, u }); return; }
      if (!S.armed) { deliver(c, { t: 'rejected' }); return; }
      S.armed = false;
      S.pending = [{ c, u }];
      bcast(withU({ t: 'buzz_pending', name: c.name }, u));
      addTimer(() => {
        const cands = S.pending; S.pending = null;
        for (const x of cands.slice(1)) deliver(x.c, { t: 'rejected' });
        bcast(withU({ t: 'buzz', name: cands[0].c.name }, cands[0].u));
      }, WINDOW_MS);
      return;
    }
    if (m.t === 'state') { if (m.store !== false) S.snapshot = m.snapshot; S.states++; bcast({ t: 'state', snapshot: m.snapshot }, c); }
    else if (m.t === 'arm') { S.armed = true; bcast({ t: 'arm' }, c); }
    else if (m.t === 'disarm') { S.armed = false; bcast({ t: 'disarm' }, c); }
    else if (m.t === 'close') {
      // like the DO: {t:'closed'} goes out first, then the sockets close
      S.closed = true; bcast({ t: 'closed' });
      const all = S.conns; S.conns = [];
      for (const x of all) addTimer(() => { x.open = false; }, x.lat + 1);
    }
  };
  return S;
}

// ---- question corpus ----
const ANS = 'Igor <b><u>Stravinsky</u></b> [accept Igor Fyodorovich Stravinsky; prompt on Igor]';
function mkDoc(i) {
  const lead = 'This composer wrote a ballet whose opening bassoon solo sits in a high register and whose '
    + 'premiere in Paris caused a riot in the year nineteen thirteen at the theatre';
  return {
    _id: 'q' + i,
    question_sanitized: lead + ' (*) where Nijinsky danced. For 10 points, name this Russian composer of The Rite of Spring.',
    answer: ANS, answer_sanitized: 'Igor Stravinsky [accept Igor Fyodorovich Stravinsky; prompt on Igor]',
    category: 'Fine Arts', subcategory: 'Auditory Fine Arts', alternate_subcategory: '',
    packet: { number: 1, name: '1' }, number: i + 1,
  };
}
const NQ = 12;
const DOCS = new Map(); for (let i = 0; i < NQ; i++) DOCS.set('q' + i, mkDoc(i));

// ---- one reader client ----
const roomBlock = slice('/* ---------- multiplayer rooms ----------', '/* ---------- boot ----------');
const clientCode = [
  `
let CAT = null, ID2ROW = null, ID2SLUG = new Map();
let queue = [], qpos = -1;
let room = null, cur = null, phase = 'idle';
let wordIdx = 0, tick = null, graceTimer = null, graceAnim = null, buzzAt = null;
let history = [], prevIdx = -1;
let LOG = [];
const sessionRows = [];
let HEARD_LOG = [];
const HEARD_MAX = 5000;
function saveHeard() {}
const sessionHeard = [];
const settings = { wpm: 600, sent: 0, scoreGiveaway: true, voice: false, drill: false, useDist: true, exactDist: false };
const filters = { cats: new Set(), subsOff: new Set(), altsOff: new Set(), sections: new Set(), diffs: new Set([7]) };
const setPick = { slug: null, from: null, to: null };
let SET_IDX = null;
const window = { losReaderHook: {}, history: { replaceState() {} }, addEventListener() {} };
const location = { href: 'https://example.test/reader.html', search: '' };
let __saves = 0;
const localStorage = { getItem: () => null, setItem() { __saves++; } };
const PREFS = 'losReaderPrefsV1';
const DEFAULT_DIST = { 'Literature': 4, 'History': 4, 'Science': 4, 'Fine Arts': 3 };
let AUDIO_HAVE = null;
function loadAudioIndex() { return Promise.resolve(null); }
function enterAudioMode() {}
function syncControls() {}
function renderFilters() {}
function rebuildQueue() {}
function onFilter() { savePrefs(); }   // the real one also prunes + rebuilds the queue
const document = { body: { dataset: {} }, createElement: () => ({ className: '', innerHTML: '' }) };
const navigator = {};
const audioEl = null;
const POPS = {};
const esc = s => String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
const answerHTML = a => a;
const qdataErrorHtml = e => 'ERR ' + e;
const __els = new Map();
function $(id) {
  if (!__els.has(id)) __els.set(id, {
    id, classList: { _s: new Set(), add(c) { this._s.add(c); }, remove(c) { this._s.delete(c); },
      toggle(c, on) { (on === undefined ? !this._s.has(c) : on) ? this._s.add(c) : this._s.delete(c); },
      contains(c) { return this._s.has(c); } },
    style: {}, dataset: {}, value: '', textContent: '', innerHTML: '', className: '', hidden: false, disabled: false,
    focus() {}, select() {}, blur() {}, addEventListener() {},
    children: [], appendChild(c) { this.children.push(c); }, removeChild(c) { this.children.splice(this.children.indexOf(c), 1); },
    get firstChild() { return this.children[0]; }, scrollHeight: 0, scrollTop: 0, clientHeight: 0,
  });
  return __els.get(id);
}
let __status = { cls: '', text: '' };
function setStatus(cls, text) { __status = { cls, text }; }
let __renders = 0;
function renderQText() { __renders++; }
function setProgress() {}
function clearTimers() {}
function stopAudio() {}
function pushHistory() { if (cur) history.push({ snap: cur, buzzAt, res: cur.res != null ? cur.res : null }); }
function togglePop() {}
function showWiki() {}
function scoreModeOn() { return settings.sent === 'score'; }
function syncMobileBar() {}
function syncSession() {}
function renderScoreboard() {}
function syncQPane() {}
function prefetchAudio() {}
function audioMode() { return false; }
function hasAudio() { return false; }
function voiceAvailable() { return false; }
function voiceRate() { return 1; }
function attachSidecar() { return Promise.resolve(null); }
function saveLog() {}
function queueSize() { return queue.length; }
function updateButtons() { if (room) roomButtons(); }
function catName() { return ''; } function subName() { return ''; } function altName() { return ''; }
function answerKey(a, as) { return (as || a || '').split('[')[0].trim().toLowerCase(); }
function shardFor() { return Promise.resolve(__DOCS); }
const { buildUnits, slowSpans, SLOW_FACTOR } = globalThis.qbRevealUnits;
`,
  slice('const ABBREV', 'const { buildUnits'),
  slice('/* ---------- reading plan', '\n/* ---------- answer checking'),
  slice('function wordUnitStarts', '\n// Reveal-unit index for'),
  slice('function startQuestion(', '\nfunction scheduleStep()'),
  slice('function renderVerdict', '\nfunction showJudge'),
  slice('function record(', '\n// --- stats state ---'),
  slice('function pillLabels()', '\nfunction syncPills()'),
  slice('function prefsObject()', '\n// Sentences-read control'),
  roomBlock,
  `
globalThis.__api = {
  get room() { return room; }, get cur() { return cur; }, get phase() { return phase; },
  get wordIdx() { return wordIdx; }, get buzzAt() { return buzzAt; }, get LOG() { return LOG; },
  get HEARD() { return HEARD_LOG; },
  get status() { return __status; }, get queue() { return queue; },
  get saves() { return __saves; },
  settings, filters, setPick, $, roomPillsChanged, savePrefs, roomNext, roomSkip, roomPause, roomChatSend, roomTyping, roomEnter, roomLeave, roomMain, roomBuzz, roomSubmit, roomOverride,
  roomHostPause, roomHostSkip, roomHostNext,
  boot(cat, id2row, q) { CAT = cat; ID2ROW = id2row; queue = q; qpos = -1; },
};`,
].join('\n');

function makeCat() {
  const ids = [...DOCS.keys()];
  return {
    cat: {
      tossups: { id: ids, set: ids.map(() => 0), category: ids.map(() => 0), subcategory: ids.map(() => 0),
        alternate_subcategory: ids.map(() => -1), difficulty: ids.map(() => 7), section: ids.map(() => -1) },
      sets: [{ slug: '2026-test', name: '2026 Test Set', year: 2026 }],
      section_values: [],
    },
    id2row: new Map(ids.map((id, r) => [id, r])),
  };
}

function makeClient(S, name, { skew = 0, lat = 20, host = false, code = 'TEST' } = {}) {
  const ctx = vm.createContext({
    console, Set, Map, Object, Array, JSON, Number, String, Math, Promise, Error, URL, URLSearchParams,
    Blob: function () {}, ArrayBuffer, DataView, Uint8Array,
    Date: { now: () => NOW + skew },
    setTimeout: (fn, ms) => addTimer(fn, ms, false), clearTimeout: clearT,
    setInterval: (fn, ms) => addTimer(fn, ms, true), clearInterval: clearT,
    confirm: () => true, globalThis: {},
  });
  ctx.globalThis = ctx;
  ctx.qbCheckAnswer = checkAnswer;
  ctx.__DOCS = DOCS;
  vm.runInContext(unitsSrc, ctx, { filename: 'reveal_units.js' });
  vm.runInContext(roomSrc, ctx, { filename: 'reader_room.js' });
  // Swap the WebSocket transport for the in-process server; everything
  // else in reader_room.js (clock, rules) is the real code.
  const sockets = [];
  ctx.qbReaderRoom.connect = opts => {
    let c = null, closed = false;
    const sock = {
      send(m) { if (c && c.open) { c.send(m); return true; } return false; },
      close() { closed = true; if (c && c.open) S.drop(c); },
      open() { return !!c && c.open; },
    };
    c = S.connect(opts.role, opts.name, lat, m => {
      if (closed) return;
      if (m.t === 'sync') { opts.clock.sample(m.c, m.s, ctx.Date.now()); return; }
      if (m.t === 'closed') closed = true;
      opts.onMessage && opts.onMessage(m);
    }, () => {
      for (let i = 0; i < 5; i++) addTimer(() => sock.send({ t: 'sync', c: ctx.Date.now() }), i * 120);
      opts.onOpen && opts.onOpen();
    });
    sockets.push({ sock, c: () => c, role: opts.role });
    return sock;
  };
  vm.runInContext(clientCode, ctx, { filename: 'reader.js (rooms slice)' });
  const api = ctx.__api;
  const { cat, id2row } = makeCat();
  api.boot(cat, id2row, [...Array(NQ).keys()]);
  api.roomEnter({ code, name, isHost: host });
  api.name = name;
  api.sockets = sockets;
  return api;
}

const answer = (cl, text) => { cl.$('answerinput').value = text; cl.roomSubmit(); };
const n = cl => cl.cur.units.length;
const powerIdx = cl => cl.cur.units.findIndex(u => u.t === '(*)');
const logRow = (cl, qid) => cl.LOG.find(r => r.id === qid);

(async function main() {
  /* ---- game 1: a neg, a resume, a correct; then a dead question ---- */
  console.log('game: neg -> resume -> correct');
  let S = makeServer();
  const H = makeClient(S, 'Host', { host: true, skew: 0, lat: 15 });
  const K = makeClient(S, 'Kim', { skew: 4321, lat: 40 });
  const M = makeClient(S, 'Sam', { skew: -2500, lat: 25 });
  await advance(1000);
  check('roster: everyone sees three players', [H, K, M].every(c => c.room.roster.size === 3));
  check('clocks synced despite skew', [K, M].every(c => Math.abs(c.room.clock.now() - NOW) < 30));

  H.roomMain();                         // Start
  await advance(200);
  check('everyone is loading question 1', [H, K, M].every(c => c.phase === 'loading' && c.cur && c.cur.q.id === 'q0'));
  await advance(1200 + 300 + 50);
  check('reading on every screen', [H, K, M].every(c => c.phase === 'reading'));
  await advance(1000);   // ~10 units at 600 wpm
  const us = [H, K, M].map(c => c.wordIdx);
  check('reveal positions agree across clients (±1 unit)', Math.max(...us) - Math.min(...us) <= 1, us);
  check('reveal advanced about 12 units (1.25 s at 600 wpm)', us[0] >= 11 && us[0] <= 13, us);

  // guests may not pause/skip/advance
  K.roomHostPause(); K.roomHostSkip();
  await advance(20);
  check('host-only functions stay host-only', H.room.g.phase === 'reading');

  K.roomBuzz();
  const kimU = K.room.myBuzz.u;
  check('buzzer freezes immediately', K.phase === 'buzzed' || K.room.myBuzz);
  await advance(300);
  check('host state: Kim buzzed', H.room.g.phase === 'buzzed' && H.room.g.buzzer === 'Kim');
  check('credited position is what Kim saw', H.room.g.buzzU === kimU, [H.room.g.buzzU, kimU]);
  check('everyone frozen on Kim', [H, K, M].every(c => c.phase === 'buzzed') && M.status.text.includes('Kim'));
  const frozen = M.wordIdx;
  await advance(500);
  check('reading stays frozen while Kim answers', M.wordIdx === frozen);
  check('only Kim gets the answer box', K.$('answerrow').classList.contains('show') && !M.$('answerrow').classList.contains('show'));
  M.roomBuzz();
  await advance(100);
  check('nobody else can buzz during an answer', H.room.g.buzzer === 'Kim' && !M.room.myBuzz);

  check('a buzz line opens in everyone\'s chat', [H, M].every(c => c.room.chat.some(x => x.name === 'Kim' && x.text === 'buzzed…')));
  K.$('answerinput').value = 'Prok'; K.roomTyping();
  K.$('answerinput').value = 'Prokof'; K.roomTyping();   // within 150ms: folded into a trailing send
  await advance(100);
  check('others see the answer as it\'s typed (throttled)', M.room.typing && M.room.typing.text === 'Prok'
    && /Prok/.test(M.$('liveans').innerHTML) && !M.$('liveans').hidden);
  await advance(200);
  check('the trailing send lands the latest text', M.room.typing.text === 'Prokof'
    && M.room.chat.some(x => x.name === 'Kim' && x.text === 'buzzed: Prokof'));
  check('the buzzer doesn\'t get the live box', K.$('liveans').hidden);
  answer(K, 'Prokofiev');
  await advance(300);
  check('the buzz line becomes the verdict', [H, K, M].every(c => c.room.chat.some(x => x.name === 'Kim' && x.text === 'buzzed: Prokofiev, wrong −5')),
    M.room.chat.map(x => x.text));
  check('the live box closes', M.$('liveans').hidden);
  check('wrong answer: Kim locked out, -5 while reading', H.room.g.locked.includes('Kim')
    && H.room.g.buzzes[0].pts === -5 && H.room.g.phase === 'reading');
  check('reading resumed for everyone', [H, K, M].every(c => c.phase === 'reading'));
  check('Kim is locked out on her screen', K.status.text.includes('Locked out') && K.$('mainbtn').disabled);
  K.roomBuzz();
  await advance(50);
  check('a locked-out player cannot buzz', !K.room.myBuzz && H.room.g.phase === 'reading');
  const before = M.wordIdx;
  await advance(800);
  check('the reveal continues past the buzz point', M.wordIdx > before);

  M.roomBuzz();
  const samU = M.room.myBuzz.u;
  await advance(200);
  answer(M, 'Stravinsky');
  await advance(300);
  check('correct: question over on every screen', [H, K, M].every(c => c.phase === 'done'));
  const pts = samU <= powerIdx(H) ? 15 : 10;
  check('Sam scores ' + pts + ', Kim -5', H.room.snap.scores.Sam.pts === pts && H.room.snap.scores.Kim.pts === -5,
    H.room.snap.scores);
  check('scores reach the guests', K.room.snap.scores.Sam.pts === pts);
  const kRow = logRow(K, 'q0'), sRow = logRow(M, 'q0');
  check('Kim logged a neg with her buzz depth', kRow && kRow.res === 'W' && kRow.room === true
    && Math.abs(kRow.bf - kimU / n(K)) < 0.002, kRow);
  check('Sam logged a correct', sRow && sRow.res === 'C' && sRow.pow === (pts === 15), sRow);
  check('the host (no buzz, someone got it) logs no stats row', !logRow(H, 'q0'));
  const heard = H.HEARD.find(r => r.id === 'q0');
  check('...but keeps it as heard, with who got it', heard && heard.by === 'Sam' && heard.room === true && !heard.res, heard);
  check('heard once, buzzers never', H.HEARD.length === 1 && !K.HEARD.length && !M.HEARD.length);
  check('one row per player per question', K.LOG.length === 1 && M.LOG.length === 1);

  // host override of the last buzz, then back
  H.roomOverride('W');
  await advance(200);
  check('override: Sam marked wrong (-5 during the reading, 0 after)', H.room.snap.scores.Sam.pts === (samU < n(H) ? -5 : 0));
  check('override regrades Sam\'s own row', logRow(M, 'q0').res === 'W');
  K.roomOverride('C');
  await advance(100);
  check('a guest cannot override', logRow(M, 'q0').res === 'W');
  H.roomOverride('C');
  await advance(200);
  check('override back restores Sam', logRow(M, 'q0').res === 'C' && H.room.snap.scores.Sam.pts === pts);
  check('the heard entry follows the override', H.HEARD.find(r => r.id === 'q0').by === 'Sam');

  console.log('game: dead question');
  H.roomMain();   // Next
  await advance(1800);
  check('question 2 reading', [H, K, M].every(c => c.phase === 'reading' && c.cur.q.id === 'q1'));
  check('lockouts reset for the new question', !H.room.g.locked.length && !K.$('mainbtn').disabled);
  await advance(n(H) * 100 + 1000);
  check('buzz window after the reading', H.room.g.graceEnd != null && M.status.text === 'Buzz window');
  await advance(5200);
  check('dead after the buzz window', [H, K, M].every(c => c.phase === 'done'));
  check('everyone logs a dead', [H, K, M].every(c => (logRow(c, 'q1') || {}).res === 'D'));

  console.log('game: prompt, then power');
  H.roomMain();
  await advance(1800);
  // buzz before the power mark
  const pi = powerIdx(H);
  await advance((pi - 6) * 100);
  K.roomBuzz();
  await advance(200);
  const end0 = H.room.g.answerEnd, start0 = H.room.g.answerStart;
  check('10 seconds to answer', end0 - start0 === 10000);
  answer(K, 'Igor');
  await advance(300);
  check('a prompt adds 10 seconds', H.room.g.answerEnd === end0 + 10000);
  check('prompt goes back to the buzzer', H.room.g.prompt && K.status.text.startsWith('Prompt')
    && K.$('answerrow').classList.contains('show'));
  check('others see the prompt', M.status.text.includes('prompted'));
  answer(K, 'Igor');   // the same answer again still reopens the box (prompt rounds)
  await advance(300);
  check('a repeated prompt reopens the box', K.$('answerrow').classList.contains('show') && H.room.g.prompt.n === 2);
  check('the prompt shows in the buzz line', M.room.chat.some(x => x.name === 'Kim' && /^buzzed: Igor \(prompt/.test(x.text)));
  answer(K, 'Igor Stravinsky');
  await advance(300);
  check('power: +15 and pow logged', H.room.g.buzzes[0].pts === 15 && logRow(K, 'q2').pow === true
    && logRow(K, 'q2').res === 'C');

  console.log('game: skip, simultaneous buzz, timeout, late join');
  H.roomMain();
  await advance(1800);
  await advance(500);
  M.roomBuzz();
  await advance(200);
  answer(M, 'Debussy');
  await advance(300);
  const samBefore = H.room.snap.scores.Sam.pts;
  H.roomHostSkip();
  await advance(300);
  check('skip voids the question: the neg is not scored', H.room.snap.scores.Sam.pts === samBefore + 5);
  check('skip moves on and logs nothing', !logRow(M, 'q3') && H.room.g.qn === 5);
  check('a skipped question isn\'t "heard" either', ![H, K, M].some(c => c.HEARD.some(r => r.id === 'q3')));
  await advance(1800);

  // simultaneous buzz: same tick
  await advance(400);
  K.roomBuzz(); M.roomBuzz();
  await advance(300);
  const winner = H.room.g.buzzer;
  const loser = winner === 'Kim' ? M : K;
  check('one winner of a simultaneous buzz', winner === 'Kim' || winner === 'Sam');
  check('the loser\'s answer box closes', !loser.$('answerrow').classList.contains('show') && !loser.room.myBuzz);
  // the winner never answers: timeout after 10 s
  await advance(9000);
  check('still answering at 9 s', H.room.g.buzzer === winner);
  await advance(1500);
  check('answer timeout counts as a wrong answer', H.room.g.locked.includes(winner) && H.room.g.phase === 'reading');

  const L = makeClient(S, 'Lee', { skew: 99999, lat: 60 });
  await advance(1200);
  check('late joiner loads the live question', L.cur && L.cur.q.id === H.cur.q.id && L.phase === 'reading');
  await advance(300);
  check('late joiner catches up to the clock', Math.abs(L.wordIdx - H.wordIdx) <= 1, [L.wordIdx, H.wordIdx]);
  check('late joiner gets the scoreboard', L.room.snap.scores.Kim != null);
  check('the server never stored a snapshot (the host re-sent it to the joiner)', S.snapshot === null && S.states > 0);

  // the host's settings reach the players' own controls
  H.settings.wpm = 450; H.filters.cats.add('Literature'); H.filters.diffs.add(3);
  H.roomPillsChanged();
  await advance(600);
  check('players mirror the host settings', K.settings.wpm === 450 && [...K.filters.cats].join() === 'Literature'
    && [...K.filters.diffs].sort().join() === '3,7', [K.settings.wpm, [...K.filters.cats]]);
  const seqNow = H.room.g.seq;
  H.roomPillsChanged();
  await advance(600);
  check('unchanged settings send nothing', H.room.g.seq === seqNow);

  // a player edits the settings: the host applies them, everyone mirrors
  const kSaves = K.saves;
  K.settings.wpm = 320; K.filters.cats.clear(); K.filters.cats.add('History');
  K.savePrefs();
  await advance(1500);
  check('a player\'s edit reaches the host', H.settings.wpm === 320 && [...H.filters.cats].join() === 'History',
    [H.settings.wpm, [...H.filters.cats]]);
  check('...and the other players', M.settings.wpm === 320 && [...M.filters.cats].join() === 'History');
  check('a player\'s own saved settings are untouched', K.saves === kSaves);
  K.settings.wpm = 9999; K.savePrefs();
  await advance(1500);
  check('the host clamps a player\'s settings', H.settings.wpm === 700);
  K.settings.wpm = 600; K.savePrefs();
  await advance(1500);

  // sets are pickable in a room: a player's set pick reaches the host (whose
  // queue it drives) and every other player; an unknown set is ignored
  K.setPick.slug = '2026-test'; K.setPick.from = 2; K.setPick.to = 3;
  K.savePrefs();
  await advance(1500);
  check('a player\'s set pick reaches the host', H.setPick.slug === '2026-test' && H.setPick.from === 2 && H.setPick.to === 3,
    JSON.stringify(H.setPick));
  check('...and the other players', M.setPick.slug === '2026-test' && M.setPick.to === 3, JSON.stringify(M.setPick));
  H.setPick.slug = 'no-such-set'; H.roomPillsChanged();
  await advance(1500);
  check('an unknown set is ignored', K.setPick.slug === null, JSON.stringify(K.setPick));
  H.setPick.slug = null; H.setPick.from = H.setPick.to = null; H.roomPillsChanged();
  await advance(1500);

  // chat
  K.$('chatinput').value = 'nice buzz';
  K.roomChatSend();
  await advance(200);
  check('chat reaches everyone, sender included', [H, K, M, L].every(c => c.room.chat.some(x => x.name === 'Kim' && x.text === 'nice buzz')));
  check('join lines in the chat', H.room.chat.some(x => x.name == null && x.text === 'Lee joined.'));

  // duplicate name -> renamed
  const K2 = makeClient(S, 'Kim', { lat: 30 });
  await advance(1500);
  check('a duplicate name is renamed', K2.room.name === 'Kim 2' && H.room.roster.has('Kim 2'));

  // host pause / resume, partway into a fresh question
  if (H.room.g.phase === 'done') H.roomNext(); else H.roomHostSkip();
  await advance(1800 + 800);
  H.roomHostPause();
  await advance(200);
  const pz = M.wordIdx;
  await advance(800);
  check('pause freezes every screen', M.phase === 'paused' && M.wordIdx === pz);
  M.roomBuzz();
  await advance(200);
  check('no buzzing while paused', !M.room.myBuzz && H.room.g.phase === 'paused');
  H.roomHostPause();
  await advance(800);
  check('resume continues from the pause point', M.phase === 'reading' && M.wordIdx > pz && pz < n(M), [M.phase, M.wordIdx, pz, n(M)]);

  // players drive the game: pause, resume, skip, next
  M.roomPause();
  await advance(300);
  check('a player can pause', H.room.g.phase === 'paused' && K.phase === 'paused');
  M.roomPause();
  await advance(300);
  check('a player can resume', H.room.g.phase === 'reading');
  const qnBefore = H.room.g.qn;
  K.roomSkip();
  await advance(300);
  check('a player can skip (voids, moves on)', H.room.g.qn === qnBefore + 1);
  await advance(2000);
  M.roomBuzz(); await advance(200); answer(M, 'Stravinsky'); await advance(300);
  check('question over', H.room.g.phase === 'done');
  const qnDone = H.room.g.qn;
  K.roomNext(); M.roomNext();   // both press Next at once
  await advance(400);
  check('two Next presses advance once', H.room.g.qn === qnDone + 1, [qnDone, H.room.g.qn]);
  await advance(2000);
  M.roomPause();   // a stale press: pressed on question qnDone+1, then the host skips past it
  H.roomHostSkip();
  await advance(400);
  check('a request for a question that\'s gone is ignored', H.room.g.phase !== 'paused');

  // host ends the room
  H.roomLeave(false);
  await advance(500);
  check('ending the room drops the guests back to solo', K.room === null && M.room === null && L.room === null);
  check('leaving restores a player\'s own settings', K.settings.wpm === 600 && K.filters.cats.size === 0);

  /* ---- an older room server that drops the claimed position ---- */
  console.log('old server (no buzz position relay)');
  S = makeServer(); S.dropU = true;
  const H2 = makeClient(S, 'Host', { host: true, lat: 10, code: 'OLDS' });
  const P2 = makeClient(S, 'Pat', { lat: 80, skew: 777, code: 'OLDS' });
  await advance(1000);
  H2.roomMain();
  await advance(1800 + 1000);
  P2.roomBuzz();
  const patU = P2.room.myBuzz.u;
  await advance(400);
  check('falls back to the host position (never earlier than the claim)', H2.room.g.buzzU >= patU
    && H2.room.g.buzzU - patU <= 3, [H2.room.g.buzzU, patU]);
  answer(P2, 'Stravinsky');
  await advance(400);
  check('game still completes', P2.phase === 'done' && logRow(P2, 'q0').res === 'C');
  H2.roomLeave(false);
  await advance(200);

  /* ---- solo host: a neg ends the question (everyone locked out) ---- */
  console.log('host alone');
  S = makeServer();
  const H3 = makeClient(S, 'Solo', { host: true, code: 'ALON' });
  await advance(800);
  H3.roomMain();
  await advance(1800 + 600);
  H3.roomBuzz();
  await advance(200);
  answer(H3, 'Mahler');
  await advance(300);
  check('the only player negged: question over', H3.phase === 'done' && logRow(H3, 'q0').res === 'W');
  H3.roomLeave(false);
  await advance(200);

  console.log(pass + ' passed, ' + fail + ' failed');
  process.exit(fail ? 1 : 0);
})().catch(e => { console.error(e); process.exit(1); });
