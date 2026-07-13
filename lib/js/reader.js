// reader.js — the question reader (reader.html).
//
// Runtime data comes entirely from the R2 data plane via qdata.js:
//   catalog.json  — columnar index of every tossup (set/packet/taxonomy/difficulty)
//   topics.json   — wiki overlay: per-topic metadata + backing question ids
//   sets/{slug}.json — full question docs, fetched lazily per set and cached
//
// Everything else (reveal engine, answer checking, stats) runs client-side;
// history lives in localStorage. Tossups only for now — bonuses later.
(function () {
'use strict';

const $ = id => document.getElementById(id);
const esc = s => s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
// answerlines may contain only these formatting tags; escape everything else
const ANS_OK = /<\/?(b|u|i|em|strong)>/;
function answerHTML(a) { return a.split(/(<\/?(?:b|u|i|em|strong)>)/g).map(p => ANS_OK.test(p) ? p : esc(p)).join(''); }

/* ---------- era buckets (subsubcategory facet, derived from topic year) ---------- */
function eraOf(y) {
  if (y == null) return null;
  if (y < 1500) return 'Pre-1500';
  if (y < 1600) return '1500s';
  if (y < 1700) return '1600s';
  if (y < 1800) return '1700s';
  if (y < 1900) return '1800s';
  if (y < 1946) return '1900–1945';
  return 'Post-1945';
}
const ERA_ORDER = ['Pre-1500', '1500s', '1600s', '1700s', '1800s', '1900–1945', 'Post-1945'];

/* ---------- sentence splitting (for the last-n-sentences mode) ---------- */
const ABBREV = /(?:Mr|Mrs|Ms|Dr|St|Sts|Mt|vs|etc|Jr|Sr|Prof|Gen|Col|Fr|ca|c|e\.g|i\.e|No|Op|Nos)\.$/;
function splitSentences(text) {
  const parts = []; let buf = '';
  const tokens = text.split(/(\s+)/);
  for (let i = 0; i < tokens.length; i++) {
    buf += tokens[i];
    const t = tokens[i];
    if (/[.!?][”")\]]*$/.test(t) && !ABBREV.test(t.replace(/[”")\]]+$/, ''))) {
      const rest = tokens.slice(i + 1).join('');
      if (/^\s*[“A-Z0-9”"(]/.test(rest) || !rest.trim()) { parts.push(buf); buf = ''; }
    }
  }
  if (buf.trim()) parts.push(buf);
  return parts.map(s => s.trim()).filter(Boolean);
}

/* ---------- score-clue pacing ----------
   Note-name runs ("E-flat, G, B-flat, D") fly by at prose speed: runs of 3+
   note-ish tokens read slower. Dash-joined runs ("E–F♯–G–E") arrive as ONE
   token and would pop all at once, so they split into per-note reveal units. */
const NOTEISH = /^["“(«]?(?:[A-G](?:♯|♭|#|b)?(?:-?(?:sharp|flat|natural))?|[Dd]o|[Rr]e|[Mm]i|[Ff]a|[Ss]ol|[Ll]a|[Tt]i|[Ss]i)[”")»\],.;:!?–—-]*$/;
const SLOW_FACTOR = 2.4;
function splitNoteRun(w) {
  if (!/[–—-]/.test(w) || w.length < 3) return null;
  const parts = w.split(/(?<=[–—-])/);
  const merged = [];
  for (const p of parts) {
    if (merged.length && /^(sharp|flat|natural)[–—-]?["”")\],.;:!?]*$/i.test(p)) merged[merged.length - 1] += p;
    else merged.push(p);
  }
  if (merged.length < 3) return null;
  if (!merged.every(p => NOTEISH.test(p))) return null;
  return merged;
}
function buildUnits(words) {
  const units = [];
  for (const w of words) {
    const parts = splitNoteRun(w);
    if (parts) parts.forEach((p, i) => units.push({ t: p, sep: i === 0 ? ' ' : '' }));
    else units.push({ t: w, sep: ' ' });
  }
  return units;
}
function slowSpans(words) {
  const slow = new Set();
  let runStart = -1, noteCount = 0, gap = 0;
  const flush = end => {
    if (noteCount >= 3) for (let k = runStart; k < end; k++) slow.add(k);
    runStart = -1; noteCount = 0; gap = 0;
  };
  for (let i = 0; i < words.length; i++) {
    const isNote = NOTEISH.test(words[i]);
    const isGlue = /^(and|then|to|a|an|or)[,.;]?$/i.test(words[i]);
    if (isNote) { if (runStart < 0) runStart = i; noteCount++; gap = 0; }
    else if (runStart >= 0 && isGlue && gap < 1) { gap++; }
    else if (runStart >= 0) { flush(i); }
  }
  flush(words.length);
  return slow;
}

/* ---------- answer checking ---------- */
function normAns(s) {
  return s.normalize('NFD').replace(/[̀-ͯ]/g, '')
    .toLowerCase().replace(/[^a-z0-9\s]/g, ' ').replace(/\s+/g, ' ').trim()
    .replace(/^(the|a|an) /, '');
}
function candidates(ansSan) {
  const out = []; const prompts = [];
  const main = ansSan.split(/[\[(]/)[0];
  if (main.trim()) out.push(main);
  const inner = ansSan.match(/\[([^\]]*)\]/);
  if (inner) {
    for (const seg of inner[1].split(';')) {
      const s = seg.trim();
      if (/^(do not|reject|antiprompt)/i.test(s)) continue;
      if (/^prompt/i.test(s)) { prompts.push(s.replace(/^prompt (on|for)\s*/i, '')); continue; }
      out.push(s.replace(/^(or|accept|and|also accept)\s+/i, ''));
    }
  }
  return { accept: out.map(normAns).filter(Boolean), prompt: prompts.map(normAns).filter(Boolean) };
}
function matches(user, cand) {
  if (!user) return false;
  for (const c of cand) {
    if (c === user) return true;
    if (c.split(' ').length > 1 && (' ' + c + ' ').includes(' ' + user + ' ') && user.length > 3) return true;
    const last = c.split(' ').pop();
    if (last === user && last.length > 3) return true;
  }
  return false;
}

/* ---------- data plane ---------- */
let CAT = null;          // catalog.json
let TOPICS = null;       // topics.json .topics
let ID2SLUG = null;      // tossup id -> topic slug
let ID2ROW = null;       // tossup id -> catalog row index
const shardDocs = new Map();   // set slug -> Map(tossup id -> doc)

function shardFor(setIdx) {
  const slug = CAT.sets[setIdx].slug;
  if (shardDocs.has(slug)) return Promise.resolve(shardDocs.get(slug));
  return qdataFetch('sets/' + slug + '.json').then(shard => {
    const m = new Map();
    for (const pk of shard.packets) for (const tu of pk.tossups) m.set(tu._id, tu);
    shardDocs.set(slug, m);
    return m;
  });
}

/* ---------- state ---------- */
const filters = { cats: new Set(), subs: new Set(), tags: new Set(), eras: new Set(), diffs: new Set([7]) };
const settings = { wpm: 380, sent: 0 };
let queue = [], qpos = -1;
let cur = null;
let phase = 'idle';      // idle|loading|reading|paused|buzzed|selfgrade|done
let wordIdx = 0, tick = null, graceTimer = null, graceAnim = null;
let buzzAt = null;

const STORE = 'losReaderStatsV1';
let LOG = [];
try { LOG = JSON.parse(localStorage.getItem(STORE) || '[]'); } catch (e) {}
function saveLog() { try { localStorage.setItem(STORE, JSON.stringify(LOG)); } catch (e) {} }

/* ---------- filtering over the catalog ---------- */
const catName = i => i >= 0 ? CAT.category_values[i] : null;
const subName = i => i >= 0 ? CAT.subcategory_values[i] : null;

function rowInScope(r, upTo) {
  const T = CAT.tossups;
  if (filters.cats.size && !filters.cats.has(catName(T.category[r]))) return false;
  if (upTo === 'cat') return true;
  if (filters.subs.size && !filters.subs.has(subName(T.subcategory[r]))) return false;
  if (filters.diffs.size && !filters.diffs.has(T.difficulty[r])) return false;
  if (upTo === 'sub') return true;
  if (filters.tags.size || filters.eras.size) {
    const slug = ID2SLUG.get(T.id[r]);
    if (!slug) return false;
    const t = TOPICS[slug];
    if (filters.tags.size && !(t.tags || []).some(x => filters.tags.has(x))) return false;
    if (filters.eras.size && !filters.eras.has(eraOf(t.year))) return false;
  }
  return true;
}

function chip(label, count, on) {
  const b = document.createElement('button');
  b.className = 'chip' + (on ? ' on' : '');
  b.innerHTML = esc(label) + (count != null ? ' <span class="n">' + count + '</span>' : '');
  return b;
}
function renderChipSet(el, entries, set, onChange) {
  el.innerHTML = '';
  for (const [label, count] of entries) {
    const c = chip(label, count, set.has(label));
    c.onclick = () => { set.has(label) ? set.delete(label) : set.add(label); onChange(); };
    el.appendChild(c);
  }
}

function renderFilters() {
  const T = CAT.tossups, n = T.id.length;
  const catCount = {}, subCount = {}, diffCount = {};
  for (let r = 0; r < n; r++) {
    const c = catName(T.category[r]);
    if (!c) continue;
    catCount[c] = (catCount[c] || 0) + 1;
    if (filters.cats.size && !filters.cats.has(c)) continue;
    const s = subName(T.subcategory[r]);
    if (s) subCount[s] = (subCount[s] || 0) + 1;
    diffCount[T.difficulty[r]] = (diffCount[T.difficulty[r]] || 0) + 1;
  }
  // tag/era facets exist only for wiki-linked questions; count via topics
  const tagCount = {}, eraCount = {};
  for (const slug in TOPICS) {
    const t = TOPICS[slug];
    let m = 0;
    for (const id of (t.tossups || [])) {
      const r = ID2ROW.get(id);
      if (r != null && rowInScope(r, 'sub')) m++;
    }
    if (!m) continue;
    for (const tag of (t.tags || [])) tagCount[tag] = (tagCount[tag] || 0) + m;
    const e = eraOf(t.year); if (e) eraCount[e] = (eraCount[e] || 0) + m;
  }
  const bySize = o => Object.entries(o).sort((a, b) => b[1] - a[1]);
  renderChipSet($('f-cats'), bySize(catCount), filters.cats, onFilter);

  const subs = bySize(subCount).filter(e => e[1] >= 10 && !filters.cats.has(e[0]));
  $('subs-head').style.display = filters.cats.size && subs.length > 1 ? '' : 'none';
  renderChipSet($('f-subs'), filters.cats.size ? subs : [], filters.subs, onFilter);

  const tags = bySize(tagCount).filter(e => e[1] >= 6).slice(0, 22);
  for (const t of filters.tags) if (!tags.some(e => e[0] === t)) tags.push([t, tagCount[t] || 0]);
  $('tags-head').style.display = tags.length ? '' : 'none';
  renderChipSet($('f-tags'), tags, filters.tags, onFilter);

  const eras = ERA_ORDER.filter(e => eraCount[e] >= 6).map(e => [e, eraCount[e]]);
  $('eras-head').style.display = eras.length > 1 ? '' : 'none';
  renderChipSet($('f-eras'), eras, filters.eras, onFilter);

  const diffs = Object.keys(diffCount).map(Number).sort((a, b) => a - b)
    .filter(d => d > 0).map(d => [String(d), diffCount[d]]);
  $('f-diffs').innerHTML = '';
  for (const [d, cnt] of diffs) {
    const c = chip(d, cnt, filters.diffs.has(Number(d)));
    c.onclick = () => { const v = Number(d); filters.diffs.has(v) ? filters.diffs.delete(v) : filters.diffs.add(v); onFilter(); };
    $('f-diffs').appendChild(c);
  }
  $('scopecount').innerHTML = '<b>' + queueSize().toLocaleString() + '</b> questions';
}

function candidateRows() {
  const T = CAT.tossups;
  // facet filters restrict to wiki-linked questions; walk those ids directly
  if (filters.tags.size || filters.eras.size) {
    const rows = [];
    for (const slug in TOPICS) {
      const t = TOPICS[slug];
      if (filters.tags.size && !(t.tags || []).some(x => filters.tags.has(x))) continue;
      if (filters.eras.size && !filters.eras.has(eraOf(t.year))) continue;
      for (const id of (t.tossups || [])) {
        const r = ID2ROW.get(id);
        if (r != null && rowInScope(r, 'sub')) rows.push(r);
      }
    }
    return rows;
  }
  const rows = [];
  for (let r = 0; r < T.id.length; r++) if (rowInScope(r, 'sub')) rows.push(r);
  return rows;
}
function queueSize() { return candidateRows().length; }

function onFilter() { renderFilters(); rebuildQueue(); }

function rebuildQueue() {
  const seen = new Set(LOG.map(rec => rec.id));
  const rows = candidateRows();
  const shuffle = a => { for (let i = a.length - 1; i > 0; i--) { const j = Math.floor(Math.random() * (i + 1)); [a[i], a[j]] = [a[j], a[i]]; } return a; };
  const T = CAT.tossups;
  const unseen = [], done = [];
  for (const r of rows) (seen.has(T.id[r]) ? done : unseen).push(r);
  queue = shuffle(unseen).concat(shuffle(done));
  qpos = -1;
}

/* ---------- reading engine ---------- */
function setStatus(cls, text) { const s = $('m-status'); s.className = 'status ' + cls; s.textContent = text; }
function msPerWord() { return 60000 / settings.wpm; }

function loadNext() {
  clearTimers();
  qpos++;
  if (qpos >= queue.length) {
    $('qtext').innerHTML = '<div class="empty">No more questions in this scope. Widen the filters, or clear your history in My stats to replay.</div>';
    phase = 'idle'; updateButtons(); return;
  }
  const r = queue[qpos];
  const T = CAT.tossups;
  phase = 'loading';
  $('qtext').innerHTML = '<div class="empty">Loading&hellip;</div>';
  $('answerrow').classList.remove('show');
  $('judge').classList.remove('show');
  $('wikibox').classList.remove('show');
  $('selfgrade').style.display = 'none';
  $('timerfill').style.width = '0%';
  setStatus('', '');
  updateButtons();
  const myPos = qpos;
  shardFor(T.set[r]).then(docs => {
    if (qpos !== myPos || phase !== 'loading') return;  // user moved on
    const doc = docs.get(T.id[r]);
    if (!doc) { loadNext(); return; }
    startQuestion(r, doc);
    prefetchNext();
  }).catch(err => {
    if (qpos !== myPos) return;
    phase = 'idle'; updateButtons();
    $('qtext').innerHTML = qdataErrorHtml(err);
  });
}

function prefetchNext() {
  const nxt = queue[qpos + 1];
  if (nxt != null) shardFor(CAT.tossups.set[nxt]).catch(() => {});
}

function startQuestion(r, doc) {
  const T = CAT.tossups;
  const set = CAT.sets[T.set[r]];
  const q = {
    id: doc._id,
    text: doc.question_sanitized || doc.question,
    a: doc.answer || doc.answer_sanitized,
    as: doc.answer_sanitized || doc.answer,
    cat: doc.category || catName(T.category[r]) || '',
    sub: doc.subcategory || subName(T.subcategory[r]) || '',
    d: T.difficulty[r], setName: set.name,
    slug: ID2SLUG.get(doc._id) || null,
  };
  const sents = splitSentences(q.text);
  const nSent = settings.sent;
  const startSent = (nSent > 0 && sents.length > nSent) ? sents.length - nSent : 0;
  const skippedText = sents.slice(0, startSent).join(' ');
  const readText = sents.slice(startSent).join(' ');
  const skipWords = skippedText ? skippedText.split(/\s+/).length : 0;
  const units = buildUnits(readText.split(/\s+/));
  cur = { q, units, skipWords, startSent, sents, slow: slowSpans(units.map(u => u.t)), showSkipped: false };
  wordIdx = 0; buzzAt = null;
  $('m-set').textContent = q.setName;
  $('m-diff').textContent = 'diff ' + q.d;
  $('m-cat').textContent = q.cat + (q.sub && q.sub !== q.cat ? ' · ' + q.sub : '');
  phase = 'reading';
  renderQText();
  setStatus('reading', 'Reading');
  updateButtons();
  scheduleStep();
}

function scheduleStep() {
  const f = (cur.slow.has(wordIdx) || cur.slow.has(wordIdx + 1)) ? SLOW_FACTOR : 1;
  tick = setTimeout(step, msPerWord() * f);
}
function step() {
  tick = null;
  wordIdx++;
  renderQText();
  if (wordIdx >= cur.units.length) { startGrace(); return; }
  scheduleStep();
}

function startGrace() {
  setStatus('reading', 'Buzz window');
  const ms = 5000; const t0 = performance.now();
  graceAnim = setInterval(() => { $('timerfill').style.width = Math.min(100, (performance.now() - t0) / ms * 100) + '%'; }, 100);
  graceTimer = setTimeout(goDead, ms);
}
function goDead() {
  clearTimers();
  record('D', null);
  phase = 'done';
  setStatus('dead', 'Dead — no buzz');
  showJudge(null);
  updateButtons();
}

function renderQText() {
  if (!cur) return;
  const el = $('qtext');
  let html = '';
  if (cur.startSent > 0) {
    const n = cur.startSent;
    html += '<button class="skiptoggle" id="skiptoggle">'
      + (cur.showSkipped ? '▾ hide the ' : '▸ ') + n + ' earlier sentence' + (n > 1 ? 's' : '')
      + (cur.showSkipped ? '' : ' hidden — show') + '</button><br>';
    if (cur.showSkipped) html += '<span class="skipped">' + esc(cur.sents.slice(0, n).join(' ')) + '</span> ';
  }
  const U = cur.units;
  const upto = (phase === 'done') ? U.length : wordIdx;
  const mark = t => t === '(*)' ? '<span class="powermark">(*)</span>' : esc(t);
  let readHtml = buzzAt === 0 ? '<span class="buzzmark">●</span> ' : '';
  for (let i = 0; i < upto; i++) {
    readHtml += (i ? U[i].sep : '') + mark(U[i].t);
    if (buzzAt != null && i === buzzAt - 1) readHtml += ' <span class="buzzmark">●</span>';
  }
  html += readHtml;
  if (upto < U.length && phase === 'done') {
    let unreadHtml = '';
    for (let i = upto; i < U.length; i++) unreadHtml += (i > upto ? U[i].sep : '') + mark(U[i].t);
    html += ' <span class="unread">' + unreadHtml + '</span>';
  }
  el.innerHTML = html;
}

function clearTimers() {
  if (tick) { clearTimeout(tick); tick = null; }
  if (graceTimer) { clearTimeout(graceTimer); graceTimer = null; }
  if (graceAnim) { clearInterval(graceAnim); graceAnim = null; }
}

/* ---------- buzz + judge ---------- */
function buzz() {
  if (phase !== 'reading' && phase !== 'paused') return;
  clearTimers();
  buzzAt = wordIdx;
  phase = 'buzzed';
  setStatus('buzzed', 'Buzzed — answer?');
  renderQText();
  $('answerrow').classList.add('show');
  $('answerinput').value = '';
  $('answerinput').focus();
  updateButtons();
}

function submitAnswer() {
  const raw = $('answerinput').value;
  const user = normAns(raw);
  const cand = candidates(cur.q.as);
  $('answerrow').classList.remove('show');
  if (matches(user, cand.accept)) {
    finish('C');
  } else if (matches(user, cand.prompt)) {
    setStatus('buzzed', 'Prompt — more specific?');
    $('verdict').className = 'verdict p';
    $('verdict').textContent = '“' + raw + '” — prompted. One more try:';
    $('judge').classList.add('show');
    $('answerline').innerHTML = '';
    $('answerrow').classList.add('show');
    $('answerinput').value = ''; $('answerinput').focus();
  } else {
    phase = 'selfgrade';
    $('verdict').className = 'verdict';
    $('verdict').textContent = 'You said: “' + (raw || '—') + '”';
    $('answerline').innerHTML = answerHTML(cur.q.a);
    $('judge').classList.add('show');
    $('selfgrade').style.display = 'flex';
    $('sg-right').focus();
    updateButtons();
  }
}

function finish(res) {
  phase = 'done';
  const pct = buzzPct();
  record(res, pct);
  const powered = res === 'C' && poweredBuzz();
  setStatus(res === 'C' ? 'done-c' : 'done-w',
    res === 'C' ? (powered ? 'Power!' : 'Correct') + ' · ' + pct + '%' : 'Wrong · ' + pct + '%');
  showJudge(res);
  updateButtons();
}
function buzzPct() {
  if (buzzAt == null) return null;
  const total = cur.skipWords + cur.units.length;
  return Math.round((cur.skipWords + buzzAt) / total * 100);
}
function poweredBuzz() {
  const pi = cur.units.findIndex(u => u.t === '(*)');
  return pi >= 0 && buzzAt != null && buzzAt <= pi;
}
function showJudge(res) {
  renderQText();
  $('selfgrade').style.display = 'none';
  $('judge').classList.add('show');
  if (res === 'C') { $('verdict').className = 'verdict c'; $('verdict').textContent = poweredBuzz() ? 'Correct — in power' : 'Correct'; }
  else if (res === 'W') { $('verdict').className = 'verdict w'; $('verdict').textContent = 'Wrong'; }
  else { $('verdict').className = 'verdict'; $('verdict').textContent = 'No buzz — the answer was:'; }
  $('answerline').innerHTML = answerHTML(cur.q.a);
  showWiki();
}

function showWiki() {
  const slug = cur.q.slug;
  const t = slug ? TOPICS[slug] : null;
  if (!t) { $('wikibox').classList.remove('show'); return; }
  $('w-topic').textContent = t.name;
  $('w-topic').href = 'output/' + slug + '/stock.html';
  const bits = [];
  if (t.year != null) bits.push(t.year < 0 ? Math.abs(t.year) + ' BCE' : String(t.year));
  if (t.country) bits.push(t.country);
  bits.push(t.category + (t.subcategory && t.subcategory !== t.category ? ' · ' + t.subcategory : ''));
  $('w-meta').textContent = bits.join(' · ');
  const tagEl = $('w-tags'); tagEl.innerHTML = '';
  for (const tag of (t.tags || [])) {
    const c = chip(tag, null, filters.tags.has(tag));
    c.title = 'Practice this: add to scope';
    c.onclick = () => { filters.tags.add(tag); onFilter(); window.scrollTo({ top: 0 }); };
    tagEl.appendChild(c);
  }
  const relEl = $('w-rel'); relEl.innerHTML = '';
  const rel = (t.related || []).slice(0, 4).filter(x => TOPICS[x.slug]);
  if (rel.length) {
    const lbl = document.createElement('span');
    lbl.className = 'subhead'; lbl.style.margin = '0.1rem 0.4rem 0 0'; lbl.textContent = 'Related:';
    relEl.appendChild(lbl);
    for (const x of rel) {
      const a = document.createElement('a');
      a.className = 'chip'; a.style.color = 'var(--wiki)';
      a.textContent = x.topic; a.href = 'output/' + x.slug + '/stock.html';
      relEl.appendChild(a);
    }
  }
  $('wikibox').classList.add('show');
}

/* ---------- stats ---------- */
function record(res, pct) {
  const t = cur.q.slug ? TOPICS[cur.q.slug] : null;
  LOG.push({ id: cur.q.id, t: cur.q.slug, cat: cur.q.cat, sub: cur.q.sub,
             tags: t ? (t.tags || []) : [], era: t ? eraOf(t.year) : null,
             res, pct, sent: settings.sent, ts: Date.now() });
  saveLog();
}

function aggRows(keyFn) {
  const m = new Map();
  for (const r of LOG) {
    const keys = keyFn(r); if (!keys) continue;
    for (const k of (Array.isArray(keys) ? keys : [keys])) {
      if (!k) continue;
      let a = m.get(k); if (!a) { a = { n: 0, c: 0, pcts: [] }; m.set(k, a); }
      a.n++; if (r.res === 'C') a.c++;
      if (r.pct != null) a.pcts.push(r.pct);
    }
  }
  return [...m.entries()].map(([k, a]) => ({ k, n: a.n, acc: a.c / a.n,
    depth: a.pcts.length ? Math.round(a.pcts.reduce((x, y) => x + y, 0) / a.pcts.length) : null }));
}

function accTable(rows, opts) {
  opts = opts || {};
  rows = rows.filter(r => r.n >= (opts.min || 1)).sort((a, b) => a.acc - b.acc || b.n - a.n);
  if (!rows.length) return '';
  let h = '<table class="acc"><tr><th>' + (opts.label || '') + '</th><th>Seen</th><th>Accuracy</th><th>Avg buzz depth</th><th></th></tr>';
  for (const r of rows) {
    const col = r.acc < 0.5 ? 'var(--bad)' : r.acc < 0.75 ? 'var(--accent)' : 'var(--good)';
    h += '<tr><td class="name">' + (opts.name ? opts.name(r.k) : esc(r.k)) + '</td>'
      + '<td>' + r.n + '</td>'
      + '<td><span class="bar"><i style="width:' + Math.round(r.acc * 100) + '%;background:' + col + '"></i></span><span class="pct">' + Math.round(r.acc * 100) + '%</span></td>'
      + '<td class="pct">' + (r.depth != null ? r.depth + '%' : '—') + '</td>'
      + '<td>' + (opts.action ? opts.action(r.k) : '') + '</td></tr>';
  }
  return h + '</table>';
}

function renderStats() {
  const g = $('statgrid'); const body = $('statbody');
  const n = LOG.length;
  if (!n) {
    g.innerHTML = '';
    body.innerHTML = '<div class="empty">No history yet — play a few questions first.</div>';
    $('statnote').textContent = '';
    return;
  }
  const c = LOG.filter(r => r.res === 'C').length;
  const dead = LOG.filter(r => r.res === 'D').length;
  const pcts = LOG.filter(r => r.pct != null).map(r => r.pct);
  const depth = pcts.length ? Math.round(pcts.reduce((a, b) => a + b, 0) / pcts.length) : null;
  g.innerHTML =
    '<div class="stat"><div class="k">Questions</div><div class="v">' + n + '</div></div>'
    + '<div class="stat"><div class="k">Accuracy</div><div class="v">' + Math.round(c / n * 100) + '<small>%</small></div></div>'
    + '<div class="stat"><div class="k">Avg buzz depth</div><div class="v">' + (depth != null ? depth + '<small>%</small>' : '—') + '</div></div>'
    + '<div class="stat"><div class="k">Dead (no buzz)</div><div class="v">' + dead + '</div></div>';
  $('statnote').innerHTML = 'Buzz depth = how far into the full question you buzzed (lower is earlier). Rows sort weakest-first. '
    + '<button class="linkbtn" id="clearstats">Clear history</button>';
  $('clearstats').onclick = () => { if (confirm('Clear all reader history?')) { LOG = []; saveLog(); renderStats(); rebuildQueue(); } };

  const practice = k => '<span class="playtag" data-tag="' + esc(k) + '">practice ▸</span>';
  let h = '<h2 class="sechead">By category</h2>' + accTable(aggRows(r => r.cat), { label: 'Category' });
  h += '<h2 class="sechead">By subcategory</h2>' + accTable(aggRows(r => r.sub), { label: 'Subcategory', min: 2 });
  h += '<h2 class="sechead">By movement / school</h2>'
    + (accTable(aggRows(r => r.tags), { label: 'Tag', min: 3, action: practice }) || '<div class="statnote">Need 3+ questions on a tag to rank it.</div>');
  h += '<h2 class="sechead">By era</h2>' + accTable(aggRows(r => r.era), { label: 'Era', min: 3 });
  h += '<h2 class="sechead">Weakest topics</h2>'
    + accTable(aggRows(r => r.t), { label: 'Topic', min: 2,
        name: k => { const t = TOPICS[k]; return t ? '<a href="output/' + esc(k) + '/stock.html">' + esc(t.name) + '</a> <span class="sub">' + esc(t.subcategory || '') + '</span>' : esc(k); } });
  body.innerHTML = h;
  for (const el of body.querySelectorAll('.playtag')) {
    el.onclick = () => { filters.tags.add(el.dataset.tag); onFilter(); showView('play'); };
  }
}

/* ---------- controls ---------- */
function updateButtons() {
  const main = $('mainbtn');
  if (phase === 'idle') { main.textContent = 'Start'; main.disabled = false; }
  else if (phase === 'loading') { main.textContent = 'Loading…'; main.disabled = true; }
  else if (phase === 'reading' || phase === 'paused') { main.textContent = 'Buzz'; main.disabled = false; }
  else if (phase === 'buzzed' || phase === 'selfgrade') { main.textContent = 'Buzz'; main.disabled = true; }
  else { main.textContent = 'Next question'; main.disabled = false; }
  $('pausebtn').disabled = !(phase === 'reading' || phase === 'paused');
  $('pausebtn').textContent = phase === 'paused' ? 'Resume' : 'Pause';
  $('skipbtn').disabled = !(phase === 'reading' || phase === 'paused' || phase === 'buzzed' || phase === 'selfgrade');
}

function wireUp() {
  $('mainbtn').onclick = () => {
    if (phase === 'idle' || phase === 'done') loadNext();
    else if (phase === 'reading' || phase === 'paused') buzz();
  };
  $('pausebtn').onclick = () => {
    if (phase === 'reading') { clearTimers(); phase = 'paused'; setStatus('reading', 'Paused'); }
    else if (phase === 'paused') { phase = 'reading'; setStatus('reading', 'Reading');
      if (wordIdx >= cur.units.length) startGrace(); else scheduleStep(); }
    updateButtons();
  };
  $('skipbtn').onclick = () => { // throw the question away — nothing recorded
    if (phase === 'reading' || phase === 'paused' || phase === 'buzzed' || phase === 'selfgrade') { clearTimers(); loadNext(); }
  };
  $('qtext').addEventListener('click', e => {
    if (cur && e.target.closest('#skiptoggle')) { cur.showSkipped = !cur.showSkipped; renderQText(); return; }
    if (e.target.closest('a')) return;
    // the question text is the biggest touch target: tap = buzz / next / start
    if (phase === 'reading' || phase === 'paused') buzz();
    else if (phase === 'done' || phase === 'idle') loadNext();
  });
  $('answerinput').addEventListener('keydown', e => {
    if (e.key === 'Enter') { e.preventDefault(); submitAnswer(); }
    e.stopPropagation();
  });
  $('sg-right').onclick = () => finish('C');
  $('sg-wrong').onclick = () => finish('W');

  document.addEventListener('keydown', e => {
    if (e.target.tagName === 'INPUT') return;
    if (e.code === 'Space') { e.preventDefault();
      if (phase === 'reading' || phase === 'paused') buzz();
      else if (phase === 'done' || phase === 'idle') loadNext();
    }
    else if (e.key === 'n' || e.key === 'N') { if (phase === 'done' || phase === 'idle') loadNext(); }
    else if (e.key === 's' || e.key === 'S') { $('skipbtn').click(); }
    else if (e.key === 'p' || e.key === 'P') { $('pausebtn').click(); }
  });

  $('wpm').value = settings.wpm;
  $('wpmval').textContent = settings.wpm;
  $('wpm').oninput = e => {
    settings.wpm = Number(e.target.value);
    $('wpmval').textContent = settings.wpm;
  };
  for (const b of $('sentmode').querySelectorAll('button')) {
    b.onclick = () => {
      for (const x of $('sentmode').querySelectorAll('button')) x.classList.remove('on');
      b.classList.add('on');
      settings.sent = Number(b.dataset.n);
    };
  }
  $('clearfilters').onclick = () => {
    for (const k of Object.keys(filters)) filters[k].clear();
    onFilter();
  };
  $('tab-play').onclick = () => showView('play');
  $('tab-stats').onclick = () => showView('stats');
}

function showView(v) {
  $('view-play').style.display = v === 'play' ? '' : 'none';
  $('view-stats').style.display = v === 'stats' ? '' : 'none';
  $('tab-play').classList.toggle('on', v === 'play');
  $('tab-stats').classList.toggle('on', v === 'stats');
  if (v === 'stats') renderStats();
}

/* ---------- boot ---------- */
wireUp();
$('qtext').innerHTML = '<div class="empty">Loading the question catalog&hellip;</div>';
Promise.all([qdataFetch('catalog.json'), qdataFetch('topics.json')]).then(([cat, top]) => {
  CAT = cat;
  TOPICS = top.topics;
  ID2SLUG = new Map();
  for (const slug in TOPICS) for (const id of (TOPICS[slug].tossups || [])) ID2SLUG.set(id, slug);
  ID2ROW = new Map();
  for (let r = 0; r < CAT.tossups.id.length; r++) ID2ROW.set(CAT.tossups.id[r], r);
  renderFilters();
  rebuildQueue();
  $('qtext').innerHTML = '<div class="empty">' + queueSize().toLocaleString()
    + ' questions in scope. Press <b>Start</b> (or tap here).</div>';
  phase = 'idle';
  updateButtons();
}).catch(err => {
  $('qtext').innerHTML = qdataErrorHtml(err);
});
})();
