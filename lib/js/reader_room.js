// reader_room.js — multiplayer rooms for the reader (reader.html).
//
// Transport + the pure pieces of room play; the game glue lives in
// reader.js ("multiplayer rooms" block). Rooms run on the qb-scorekeeper
// room server (qbsuite/qb-scorekeeper rooms/worker.js — one Durable Object
// per room, protocol in that repo's SPEC.md), which is a payload-blind
// relay: atomic latency-equalized first-buzz arbitration, fan-out, a
// stored snapshot for late joiners, and a server clock echo. Everything
// with game meaning runs in the HOST's reader:
//
//   - the host picks questions from its own queue/filters, runs the
//     answer checker, keeps scores, and broadcasts a display snapshot
//     (shape: snapshot() in reader.js) after every change;
//   - every participant, the host included, holds a PLAYER socket and
//     buzzes through the DO's arbitration, so the host gets no latency
//     edge. The host additionally holds a HOST socket (state out,
//     answers in);
//   - the reveal is a deterministic function of server time: a reading
//     snapshot carries {t0, u0, wpm} (unit u0 became visible at server
//     time t0) and each client derives the visible unit from its own
//     clock-synced serverNow() via unitAt(). Nothing streams per word.
//
// Classic script (no modules — reader.js is a classic IIFE); exposes
// globalThis.qbReaderRoom and module.exports for the node tests
// (tests/reader_rooms).
(function (root) {
'use strict';

const DEFAULT_SERVER = 'https://qb-rooms.denisliu10.workers.dev';
const CODE_RE = /^[A-Z2-9]{4}$/;

/* ---------- reveal clock ----------
   Mirrors reader.js scheduleStep exactly: advancing from unit i to i+1
   takes msPerWord, times SLOW_FACTOR when either i or i+1 sits in a slow
   (score-clue note-run) span. unitAt(elapsed) is the number of visible
   units after `elapsed` ms of reading that began with u0 visible. */
function stepMs(i, slow, msPerWord, slowFactor) {
  return msPerWord * ((slow.has(i) || slow.has(i + 1)) ? slowFactor : 1);
}
function unitAt(elapsed, u0, nUnits, slow, msPerWord, slowFactor) {
  let u = u0, t = 0;
  if (elapsed <= 0) return Math.min(u0, nUnits);
  while (u < nUnits) {
    const d = stepMs(u, slow, msPerWord, slowFactor);
    if (t + d > elapsed) break;
    t += d; u++;
  }
  return u;
}
// ms after t0 at which unit index `u` becomes visible (inverse of unitAt).
function msUntilUnit(u, u0, slow, msPerWord, slowFactor) {
  let t = 0;
  for (let i = u0; i < u; i++) t += stepMs(i, slow, msPerWord, slowFactor);
  return t;
}

/* ---------- buzz position ----------
   A buzz carries the unit index the buzzer SAW (their own clock). The host
   trusts it within a window behind its own frozen position — enough for
   arbitration delay + one-way latency — and never ahead of it, so a
   tampered client can't claim a power it didn't earn by more than the
   slack. Claims outside the window fall back to the host's own index. */
const CLAIM_SLACK_MS = 700;
function clampBuzz(claimed, hostU, msPerWord) {
  if (!Number.isInteger(claimed)) return hostU;
  const slack = Math.ceil(CLAIM_SLACK_MS / Math.max(1, msPerWord)) + 1;
  if (claimed > hostU || claimed < hostU - slack) return hostU;
  return claimed;
}

/* ---------- scoring ----------
   The qb-scorekeeper rule table (SPEC.md): correct before the power mark
   15, else 10; wrong while the question is still being read -5, wrong
   after it finished 0. powerIdx = unit index of '(*)', -1 when unpowered.
   Power matches reader.js poweredBuzz: buzzing AT the mark counts. */
function buzzPoints(correct, u, powerIdx, nUnits) {
  if (correct) return (powerIdx >= 0 && u <= powerIdx) ? 15 : 10;
  return u < nUnits ? -5 : 0;
}
// Room totals from the finished-question log ([{buzzes:[{name,res,pts}]}],
// voided questions excluded by the caller) plus the live question's buzzes.
function tally(questions) {
  const s = {};
  const row = n => (s[n] || (s[n] = { pts: 0, p: 0, g: 0, n: 0 }));
  for (const q of questions) for (const b of q.buzzes || []) {
    if (b.res == null) continue;
    const r = row(b.name);
    r.pts += b.pts || 0;
    if (b.res === 'C') { if (b.pts >= 15) r.p++; else r.g++; }
    else if ((b.pts || 0) < 0) r.n++;
  }
  return s;
}

/* ---------- server clock ----------
   NTP-style offset from {t:'sync', c} -> {t:'sync', c, s} echoes; keep the
   lowest-RTT sample of the burst (least queueing noise). */
function makeClock() {
  let best = null;   // {rtt, offset}
  return {
    sample(c, s, now) {
      const rtt = now - c;
      if (rtt < 0) return;
      const offset = s - (c + rtt / 2);
      if (!best || rtt <= best.rtt) best = { rtt, offset };
    },
    now(local) { return (local == null ? Date.now() : local) + (best ? best.offset : 0); },
    rtt() { return best ? best.rtt : null; },
    synced() { return !!best; },
  };
}

/* ---------- transport ---------- */
function normCode(s) {
  const c = String(s || '').trim().toUpperCase();
  return CODE_RE.test(c) ? c : null;
}
function createRoom(server) {
  return fetch((server || DEFAULT_SERVER) + '/rooms', { method: 'POST' }).then(r => {
    if (!r.ok) throw new Error('room create failed: HTTP ' + r.status);
    return r.json();
  }).then(j => j.code);
}

// One auto-reconnecting socket. role 'player' answers the DO's RTT pings
// (latency-equalized arbitration needs them). Every socket runs a short
// clock-sync burst on open. handlers: {onMessage(m), onOpen(), onClose()}.
function connect(opts) {
  const server = opts.server || DEFAULT_SERVER;
  const clock = opts.clock;
  let ws = null, closed = false, retry = null;
  const url = () => server.replace(/^http/, 'ws') + '/rooms/' + opts.code + '/ws?name='
    + encodeURIComponent(opts.name) + '&role=' + (opts.role === 'host' ? 'host' : 'player');
  function send(obj) {
    if (ws && ws.readyState === 1) { ws.send(JSON.stringify(obj)); return true; }
    return false;
  }
  function open() {
    ws = new WebSocket(url());
    ws.onopen = () => {
      if (clock) for (let i = 0; i < 5; i++) setTimeout(() => send({ t: 'sync', c: Date.now() }), i * 120);
      if (opts.onOpen) opts.onOpen();
    };
    ws.onmessage = e => {
      let m;
      try { m = JSON.parse(e.data); } catch (err) { return; }
      if (m.t === 'ping') { send({ t: 'pong', n: m.n, ts: m.ts }); return; }
      if (m.t === 'sync') { if (clock && typeof m.s === 'number') clock.sample(m.c, m.s, Date.now()); return; }
      if (m.t === 'closed') closed = true;   // host ended the room: stop reconnecting
      if (opts.onMessage) opts.onMessage(m);
    };
    ws.onclose = () => {
      if (opts.onClose) opts.onClose(closed);
      if (!closed) retry = setTimeout(open, 2000);
    };
  }
  open();
  return {
    send,
    close() { closed = true; if (retry) clearTimeout(retry); try { ws.close(); } catch (e) {} },
    open() { return !!ws && ws.readyState === 1; },
  };
}

// Shareable join link for a room (the reader page itself with ?room=).
function joinUrl(code, server, href) {
  const u = new URL(href || location.href);
  u.search = ''; u.hash = '';
  u.searchParams.set('room', code);
  if (server && server !== DEFAULT_SERVER) u.searchParams.set('server', server);
  return u.toString();
}

const api = { DEFAULT_SERVER, unitAt, msUntilUnit, clampBuzz, CLAIM_SLACK_MS, buzzPoints, tally,
  makeClock, normCode, createRoom, connect, joinUrl };
root.qbReaderRoom = api;
if (typeof module !== 'undefined' && module.exports) module.exports = api;
})(typeof globalThis !== 'undefined' ? globalThis : this);
