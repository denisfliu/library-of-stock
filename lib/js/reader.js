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

// Focus (tags) and Era facets are off for now — they only cover
// wiki-linked questions, so the Group (overview-section) facet supersedes
// them. Flip to true to re-enable the facets and their practice-tag
// shortcuts (wiki-box tag chips, stats "practice ▸" links).
const FACETS_ON = false;

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
const filters = { cats: new Set(), subs: new Set(), tags: new Set(), eras: new Set(), sections: new Set(), diffs: new Set([7]) };
const settings = { wpm: 380, sent: 0, drill: false, focus: 1.3 };
let queue = [], qpos = -1;
let cur = null;
let phase = 'idle';      // idle|loading|reading|paused|buzzed|selfgrade|done
let wordIdx = 0, tick = null, graceTimer = null, graceAnim = null;
let buzzAt = null;

const STORE = 'losReaderStatsV1';
let LOG = [];
try { LOG = JSON.parse(localStorage.getItem(STORE) || '[]'); } catch (e) {}
// Migrate v1 entries: old records stored `pct` (buzz depth 0–100) instead of
// `bf` (buzz fraction 0–1); section/diff/ans/pow are simply absent (treated
// as unknown by the aggregators).
for (const r of LOG) {
  if (r.bf === undefined) r.bf = (r.pct != null) ? r.pct / 100 : null;
}
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
  // Overview-section filter: T.section is a catalog column, so it applies
  // to every question, wiki-linked or not (unlike tags/eras below).
  if (filters.sections.size && T.section && !filters.sections.has(T.section[r])) return false;
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
  if (!CAT) return;   // clicks before the catalog loads
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
  // Section (overview group) counts — over the sub-scope, so the chips
  // reflect the chosen subcategory. Section ids index CAT.section_values.
  const secCount = {};
  const SEC = CAT.section_values || [];
  if (T.section) {
    for (let r = 0; r < n; r++) {
      if (!rowInScope(r, 'sub')) continue;
      secCount[T.section[r]] = (secCount[T.section[r]] || 0) + 1;
    }
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

  // Focus (tags) and Era facets — gated by the module-level FACETS_ON.
  if (FACETS_ON) {
    const tags = bySize(tagCount).filter(e => e[1] >= 6).slice(0, 22);
    for (const t of filters.tags) if (!tags.some(e => e[0] === t)) tags.push([t, tagCount[t] || 0]);
    $('tags-head').style.display = tags.length ? '' : 'none';
    renderChipSet($('f-tags'), tags, filters.tags, onFilter);

    const eras = ERA_ORDER.filter(e => eraCount[e] >= 6).map(e => [e, eraCount[e]]);
    $('eras-head').style.display = eras.length > 1 ? '' : 'none';
    renderChipSet($('f-eras'), eras, filters.eras, onFilter);
  } else {
    filters.tags.clear(); filters.eras.clear();
    $('tags-head').style.display = 'none'; $('f-tags').innerHTML = '';
    $('eras-head').style.display = 'none'; $('f-eras').innerHTML = '';
  }

  // Group (overview section) facet: shown once a subcategory is chosen,
  // since sections are unit-specific. Sectioned ids first (by count),
  // then an "Unsectioned" chip for the -1 bucket.
  const secIds = Object.keys(secCount).map(Number);
  const sectioned = secIds.filter(id => id >= 0)
    .sort((a, b) => secCount[b] - secCount[a]).slice(0, 24);
  const showGroups = filters.subs.size > 0 && sectioned.length > 1;
  $('groups-head').style.display = showGroups ? '' : 'none';
  const gEl = $('f-groups');
  gEl.innerHTML = '';
  if (showGroups) {
    for (const id of sectioned) {
      const label = SEC[id] ? SEC[id][1] : '?';
      const c = chip(label, secCount[id], filters.sections.has(id));
      c.onclick = () => { filters.sections.has(id) ? filters.sections.delete(id) : filters.sections.add(id); onFilter(); };
      gEl.appendChild(c);
    }
    if (secCount[-1]) {
      const c = chip('Unsectioned', secCount[-1], filters.sections.has(-1));
      c.title = 'Rare / uncategorized answerlines';
      c.onclick = () => { filters.sections.has(-1) ? filters.sections.delete(-1) : filters.sections.add(-1); onFilter(); };
      gEl.appendChild(c);
    }
  } else if (!filters.subs.size) {
    filters.sections.clear();  // sections are meaningless without a subcategory
  }

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
        if (r != null && rowInScope(r, 'all')) rows.push(r);
      }
    }
    return rows;
  }
  const rows = [];
  for (let r = 0; r < T.id.length; r++) if (rowInScope(r, 'all')) rows.push(r);
  return rows;
}
function queueSize() { return candidateRows().length; }

function onFilter() { renderFilters(); rebuildQueue(); }

/* ---------- drill: weakness-weighted queue ----------
   Per-attempt weakness: a miss (neg/dead) = 1.0; a correct buzz = GAMMA x
   buzz-fraction (a late correct is partially weak). Item weakness is that
   average, shrunk toward your global baseline so low-count items don't
   spike (M = prior strength). A question's drill weight combines its
   group weakness and its topic weakness (hierarchical), plus an
   exploration bonus for rarely-seen topics and a spaced-repetition factor
   (boost last-missed, suppress just-seen). The focus slider is a
   temperature on the final weights: broad (flat) <-> targeted (peaked). */
const GAMMA = 0.5, PRIOR_M = 5, EXPLORE = 0.4;
function _attemptWeakness(r) {
  return r.res === 'C' ? GAMMA * (r.bf == null ? 0.5 : r.bf) : 1.0;
}
function weaknessModel() {
  let sumAll = 0, nAll = 0;
  const sec = new Map(), slug = new Map();
  const add = (m, k, w) => { if (k == null) return; let a = m.get(k); if (!a) { a = { s: 0, n: 0 }; m.set(k, a); } a.s += w; a.n++; };
  for (const r of LOG) { const w = _attemptWeakness(r); sumAll += w; nAll++; add(sec, r.section, w); add(slug, r.t, w); }
  const W0 = nAll ? sumAll / nAll : 0.5;
  const wk = (m, k) => { const a = m.get(k); return a ? (a.s + PRIOR_M * W0) / (a.n + PRIOR_M) : W0; };
  const lastRes = new Map(); const recent = new Set();
  for (let i = 0; i < LOG.length; i++) { const r = LOG[i]; if (r.t) { lastRes.set(r.t, r.res); if (i >= LOG.length - 12) recent.add(r.t); } }
  return {
    W0, secWk: k => wk(sec, k), slugWk: k => wk(slug, k),
    slugN: k => { const a = slug.get(k); return a ? a.n : 0; },
    lastMiss: k => { const v = lastRes.get(k); return v === 'W' || v === 'D'; },
    recent: k => recent.has(k),
  };
}
function drillWeight(r, m) {
  const T = CAT.tossups;
  const sid = T.section[r];
  const S = sid >= 0 && CAT.section_values[sid] ? CAT.section_values[sid][1] : null;
  const slug = ID2SLUG.get(T.id[r]);
  let score = (S ? m.secWk(S) : m.W0) * (slug ? m.slugWk(slug) : m.W0);
  score += EXPLORE / Math.sqrt((slug ? m.slugN(slug) : 0) + 1);
  if (slug) { if (m.lastMiss(slug)) score *= 1.6; if (m.recent(slug)) score *= 0.15; }
  return Math.max(score, 1e-4);
}

function rebuildQueue() {
  const rows = candidateRows();
  const T = CAT.tossups;
  if (settings.drill && LOG.length) {
    // weighted sampling without replacement (Efraimidis–Spirakis), with
    // the focus slider as a temperature on the weights.
    const m = weaknessModel(), tau = settings.focus;
    queue = rows.map(r => {
      const w = Math.pow(drillWeight(r, m), 1 / tau);
      return [Math.pow(Math.random(), 1 / w), r];
    }).sort((a, b) => b[0] - a[0]).map(x => x[1]);
  } else {
    const seen = new Set(LOG.map(rec => rec.id));
    const shuffle = a => { for (let i = a.length - 1; i > 0; i--) { const j = Math.floor(Math.random() * (i + 1)); [a[i], a[j]] = [a[j], a[i]]; } return a; };
    const unseen = [], done = [];
    for (const r of rows) (seen.has(T.id[r]) ? done : unseen).push(r);
    queue = shuffle(unseen).concat(shuffle(done));
  }
  qpos = -1;
}

/* ---------- reading engine ---------- */
function setStatus(cls, text) { const s = $('m-status'); s.className = 'status ' + cls; s.textContent = text; }
function msPerWord() { return 60000 / settings.wpm; }

function loadNext() {
  if (!CAT) return;   // Start pressed before the catalog loads
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
    d: T.difficulty[r], setName: set.name, year: set.year,
    slug: ID2SLUG.get(doc._id) || null,
    section: (T.section && T.section[r] >= 0 && CAT.section_values[T.section[r]])
      ? CAT.section_values[T.section[r]][1] : null,
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
    // Practice-by-tag only works when the Focus facet is enabled; render
    // static informational chips otherwise (no dead clicks).
    if (FACETS_ON) {
      c.title = 'Practice this: add to scope';
      c.onclick = () => { filters.tags.add(tag); onFilter(); window.scrollTo({ top: 0 }); };
    }
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

/* ---------- stats ----------
   Each attempt: res C(correct)/W(neg — buzzed wrong)/D(dead — no buzz);
   bf = buzz fraction into the FULL question (0=start, 1=end), null if no
   buzz; celerity = mean(1-bf) over correct buzzes. */
function record(res, pct) {
  const total = cur.skipWords + cur.units.length;
  const bf = buzzAt == null ? null : (cur.skipWords + buzzAt) / total;
  const q = cur.q;
  LOG.push({
    id: q.id, t: q.slug || null, ans: q.as ? normAns(q.as) : null,
    aDisp: (q.as || '').split('[')[0].split('(')[0].trim() || q.as || '',
    cat: q.cat, sub: q.sub, section: q.section || null, diff: q.d,
    res, bf: bf == null ? null : Math.round(bf * 1000) / 1000,
    pow: res === 'C' && poweredBuzz(), sent: settings.sent, ts: Date.now(),
  });
  saveLog();
}

// --- stats state ---
let statsDim = 'cat';                     // pivot dimension
let statsSort = { col: 'acc', dir: 1 };   // 1 asc (weakest first), -1 desc
const DIMS = { cat: r => r.cat, sub: r => r.sub, section: r => r.section, diff: r => r.diff != null ? 'Diff ' + r.diff : null };

function aggBy(keyFn) {
  const m = new Map();
  for (const r of LOG) {
    const keys = keyFn(r); if (keys == null) continue;
    for (const k of (Array.isArray(keys) ? keys : [keys])) {
      if (k == null || k === '') continue;
      let a = m.get(k);
      if (!a) { a = { n: 0, c: 0, neg: 0, dead: 0, celSum: 0, celN: 0, pow: 0 }; m.set(k, a); }
      a.n++;
      if (r.res === 'C') { a.c++; if (r.pow) a.pow++; if (r.bf != null) { a.celSum += 1 - r.bf; a.celN++; } }
      else if (r.res === 'W') a.neg++;
      else if (r.res === 'D') a.dead++;
    }
  }
  return [...m.entries()].map(([k, a]) => ({
    k, n: a.n, acc: a.c / a.n, neg: a.neg / a.n, dead: a.dead / a.n,
    cel: a.celN ? a.celSum / a.celN : null,
  }));
}

const pctCol = v => v < 0.5 ? 'var(--bad)' : v < 0.75 ? 'var(--accent)' : 'var(--good)';
const fmtPct = v => v == null ? '—' : Math.round(v * 100) + '%';

// sortable stat table. cols: seen, acc, cel, neg. weakest metric first.
function statTable(rows, opts) {
  opts = opts || {};
  rows = rows.filter(r => r.n >= (opts.min || 1));
  if (!rows.length) return '<div class="statnote">Not enough data yet.</div>';
  const col = statsSort.col, dir = statsSort.dir;
  rows.sort((a, b) => {
    let va = a[col], vb = b[col];
    if (va == null) va = dir > 0 ? Infinity : -Infinity;
    if (vb == null) vb = dir > 0 ? Infinity : -Infinity;
    return dir * (va - vb) || b.n - a.n;
  });
  const arrow = c => statsSort.col === c ? (statsSort.dir > 0 ? ' ▲' : ' ▼') : '';
  const th = (c, label) => '<th class="sorth" data-col="' + c + '">' + label + arrow(c) + '</th>';
  let h = '<table class="acc"><tr><th>' + (opts.label || '') + '</th>'
    + th('n', 'Seen') + th('acc', 'Accuracy') + th('cel', 'Celerity')
    + th('neg', 'Neg') + '<th></th></tr>';
  for (const r of rows) {
    h += '<tr><td class="name">' + (opts.name ? opts.name(r.k) : esc(r.k)) + '</td>'
      + '<td>' + r.n + '</td>'
      + '<td><span class="bar"><i style="width:' + Math.round(r.acc * 100) + '%;background:' + pctCol(r.acc) + '"></i></span><span class="pct">' + fmtPct(r.acc) + '</span></td>'
      + '<td class="pct" style="color:' + (r.cel == null ? 'var(--faint)' : pctCol(r.cel)) + '">' + fmtPct(r.cel) + '</td>'
      + '<td class="pct">' + fmtPct(r.neg) + '</td>'
      + '<td>' + (opts.action ? opts.action(r.k) : '') + '</td></tr>';
  }
  return h + '</table>';
}

function trendBlock() {
  // last 50 vs prior 50 attempts: accuracy + celerity deltas
  if (LOG.length < 20) return '';
  const N = Math.min(50, Math.floor(LOG.length / 2));
  const recent = LOG.slice(-N), prior = LOG.slice(-2 * N, -N);
  const acc = a => a.filter(r => r.res === 'C').length / a.length;
  const cel = a => { const b = a.filter(r => r.res === 'C' && r.bf != null); return b.length ? b.reduce((s, r) => s + (1 - r.bf), 0) / b.length : null; };
  const dAcc = acc(recent) - acc(prior), dCel = (cel(recent) || 0) - (cel(prior) || 0);
  const arrow = d => d > 0.01 ? '<span style="color:var(--good)">▲ ' + Math.round(d * 100) + '%</span>' : d < -0.01 ? '<span style="color:var(--bad)">▼ ' + Math.round(-d * 100) + '%</span>' : '<span style="color:var(--faint)">flat</span>';
  return '<div class="statnote">Trend (last ' + N + ' vs prior ' + N + '): accuracy ' + arrow(dAcc) + ' · celerity ' + arrow(dCel) + '</div>';
}

function calibrationBlock() {
  // accuracy by buzz-depth bucket — reckless (early) vs timid (late)?
  const buckets = [['Early (0–35%)', r => r.bf != null && r.bf < 0.35],
                   ['Mid (35–65%)', r => r.bf != null && r.bf >= 0.35 && r.bf < 0.65],
                   ['Late (65–100%)', r => r.bf != null && r.bf >= 0.65]];
  const buzzed = LOG.filter(r => r.bf != null);
  if (buzzed.length < 10) return '';
  let h = '<h2 class="sechead">Buzz calibration</h2><div class="statnote">Accuracy at each buzz depth — low accuracy when you buzz early means you\'re buzzing recklessly.</div><div class="calib">';
  for (const [label, f] of buckets) {
    const b = LOG.filter(f); const acc = b.length ? b.filter(r => r.res === 'C').length / b.length : null;
    h += '<div class="calib-cell"><div class="k">' + label + '</div><div class="v" style="color:' + (acc == null ? 'var(--faint)' : pctCol(acc)) + '">' + fmtPct(acc) + '</div><div class="k">' + b.length + ' buzzes</div></div>';
  }
  return h + '</div>';
}

function exposureBlock() {
  const seenAns = new Set(LOG.map(r => r.ans).filter(Boolean)).size;
  const seenSec = new Set(LOG.map(r => r.section).filter(Boolean)).size;
  const totSec = (CAT.section_values || []).length;
  return '<div class="statnote">Exposure: <b>' + seenAns + '</b> distinct answerlines seen · <b>' + seenSec + '</b> of ' + totSec + ' groups touched.</div>';
}

function renderStats() {
  const g = $('statgrid'); const body = $('statbody');
  if (!CAT) {   // topic links need TOPICS; wait for boot
    body.innerHTML = '<div class="empty">Loading&hellip;</div>';
    return;
  }
  const n = LOG.length;
  if (!n) {
    g.innerHTML = '';
    body.innerHTML = '<div class="empty">No history yet — play a few questions first.</div>';
    $('statnote').textContent = '';
    return;
  }
  const c = LOG.filter(r => r.res === 'C').length;
  const negs = LOG.filter(r => r.res === 'W').length;
  const dead = LOG.filter(r => r.res === 'D').length;
  const celA = LOG.filter(r => r.res === 'C' && r.bf != null);
  const cel = celA.length ? celA.reduce((s, r) => s + (1 - r.bf), 0) / celA.length : null;
  const tile = (k, v) => '<div class="stat"><div class="k">' + k + '</div><div class="v">' + v + '</div></div>';
  g.innerHTML = tile('Questions', n)
    + tile('Accuracy', Math.round(c / n * 100) + '<small>%</small>')
    + tile('Celerity', cel == null ? '—' : Math.round(cel * 100) + '<small>%</small>')
    + tile('Neg rate', Math.round(negs / n * 100) + '<small>%</small>')
    + tile('Dead', Math.round(dead / n * 100) + '<small>%</small>');
  $('statnote').innerHTML = '<button class="btn primary" id="drillbtn">&#9654; Drill my weaknesses</button>'
    + ' <span style="color:var(--faint)">Celerity = how early you buzz on correct answers (higher = earlier).</span> '
    + '<button class="linkbtn" id="clearstats">Clear history</button>';
  $('drillbtn').onclick = () => {
    settings.drill = true; $('drill').checked = true; $('drillrow').style.display = '';
    rebuildQueue(); showView('play');
  };
  $('clearstats').onclick = () => { if (confirm('Clear all reader history?')) { LOG = []; saveLog(); renderStats(); rebuildQueue(); } };

  const DIM_LABEL = { cat: 'Category', sub: 'Subcategory', section: 'Group', diff: 'Difficulty' };
  let h = trendBlock() + exposureBlock();
  // dimension selector for the pivot
  h += '<h2 class="sechead">Breakdown</h2><div class="dimsel" id="dimsel">';
  for (const d of ['cat', 'sub', 'section', 'diff'])
    h += '<button class="dimbtn' + (statsDim === d ? ' on' : '') + '" data-dim="' + d + '">' + DIM_LABEL[d] + '</button>';
  h += '</div>';
  h += statTable(aggBy(DIMS[statsDim]), { label: DIM_LABEL[statsDim], min: statsDim === 'section' ? 2 : 1 });
  h += calibrationBlock();
  // weakest answerlines — the drill seed
  h += '<h2 class="sechead">Weakest answerlines</h2>'
    + '<div class="statnote">Individual answers you miss most (seen ≥ 2), weakest first.</div>'
    + statTable(aggBy(r => r.ans), {
        label: 'Answerline', min: 2,
        name: k => {
          const rec = LOG.find(r => r.ans === k);
          const disp = rec ? rec.aDisp : k;
          return rec && rec.t ? '<a href="output/' + esc(rec.t) + '/stock.html">' + esc(disp) + '</a>' : esc(disp);
        },
      });
  body.innerHTML = h;
  $('dimsel').addEventListener('click', e => {
    const b = e.target.closest('.dimbtn'); if (!b) return;
    statsDim = b.dataset.dim; renderStats();
  });
  for (const th of body.querySelectorAll('.sorth')) {
    th.onclick = () => {
      const c2 = th.dataset.col;
      if (statsSort.col === c2) statsSort.dir *= -1;
      else statsSort = { col: c2, dir: c2 === 'n' ? -1 : 1 };
      renderStats();
    };
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
  // Drill mode + focus slider (temperature). focus 0->broad(tau 2.5),
  // 100->targeted(tau 0.4).
  const focusTau = v => 2.5 - (v / 100) * 2.1;
  const focusLabel = v => v < 33 ? 'broad review' : v < 67 ? 'balanced' : 'targeted';
  $('drill').onchange = e => {
    settings.drill = e.target.checked;
    $('drillrow').style.display = settings.drill ? '' : 'none';
    rebuildQueue();
  };
  $('focus').oninput = e => {
    settings.focus = focusTau(Number(e.target.value));
    $('focusval').textContent = focusLabel(Number(e.target.value));
    if (settings.drill) rebuildQueue();
  };
  settings.focus = focusTau(55);
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
