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

/* ---------- answer checking ----------
   Modeled on qbreader's checker: the underlined span of the raw answerline
   is the minimal required answer; bracket clauses add acceptable alternates
   and directed prompts; comparison is diacritic/punctuation-insensitive with
   Levenshtein typo tolerance and last-name (surname) acceptance. It stays a
   suggestion — the reader always lets you override the verdict. */
function normAns(s) {
  return s.normalize('NFD').replace(/[̀-ͯ]/g, '')
    .toLowerCase().replace(/[^a-z0-9\s]/g, ' ').replace(/\s+/g, ' ').trim()
    .replace(/^(the|a|an) /, '');
}
// underlined (<u>…</u>) spans of the raw answer = the required core(s);
// fall back to bold, then to the whole string when there's no markup.
function requiredCores(raw) {
  const grab = re => { const out = []; let m; while ((m = re.exec(raw))) out.push(m[1].replace(/<[^>]+>/g, '')); return out; };
  const u = grab(/<u>(.*?)<\/u>/gis);
  return u.length ? u : grab(/<b>(.*?)<\/b>/gis);
}
function levWithin(a, b, max) {
  if (Math.abs(a.length - b.length) > max) return false;
  const dp = Array.from({ length: a.length + 1 }, (_, i) => i);
  for (let j = 1; j <= b.length; j++) {
    let prev = dp[0]; dp[0] = j; let rowMin = dp[0];
    for (let i = 1; i <= a.length; i++) {
      const cur = Math.min(dp[i] + 1, dp[i - 1] + 1, prev + (a[i - 1] === b[j - 1] ? 0 : 1));
      prev = dp[i]; dp[i] = cur; if (cur < rowMin) rowMin = cur;
    }
    if (rowMin > max) return false;   // no cell in this row is reachable
  }
  return dp[a.length] <= max;
}
// fuzzy token/phrase equality with length-scaled typo tolerance
function fuzzy(u, c) {
  if (!u || !c) return false;
  if (u === c) return true;
  const L = Math.max(u.length, c.length);
  const tol = L < 5 ? 0 : L < 10 ? 1 : 2;      // short answers must be exact
  return tol > 0 && levWithin(u, c, tol);
}
function parseAnswerline(raw, san) {
  const accept = [], prompt = [];
  const src = san || (raw || '').replace(/<[^>]+>/g, '');
  const main = src.split(/[\[(]/)[0];
  if (main.trim()) accept.push(main);
  // cores = the minimal required answer(s); these (not the descriptive full
  // name) drive surname/token matching, so "Bartholdy" alone doesn't pass for
  // "…Mendelssohn Bartholdy". No markup -> fall back to the main answer.
  let cores = requiredCores(raw || '').filter(s => s.trim());
  if (!cores.length && main.trim()) cores = [main];
  accept.push(...cores);
  const inner = src.match(/\[([^\]]*)\]/);
  if (inner) {
    for (const seg of inner[1].split(/[;]/)) {
      const s = seg.trim();
      if (/^(do not|reject|antiprompt)/i.test(s)) continue;
      if (/^prompt/i.test(s)) { prompt.push(s.replace(/^prompt (on|for)\s*/i, '')); continue; }
      accept.push(s.replace(/^(or|accept|and|also accept)\s+/i, ''));
    }
  }
  return {
    accept: accept.map(normAns).filter(Boolean),
    cores: cores.map(normAns).filter(Boolean),
    prompt: prompt.map(normAns).filter(Boolean),
  };
}
function matchAny(user, list) {   // whole-answer fuzzy match
  return list.some(c => fuzzy(user, c));
}
function matchCores(user, cores) {
  const ut = user.split(' ').filter(Boolean);
  for (const c of cores) {
    const ct = c.split(' ').filter(Boolean);
    if (ct.length === 1) {
      // single-token core (usually a surname): user must contain it
      if (ct[0].length >= 4 && ut.some(t => fuzzy(t, ct[0]))) return true;
    } else if (ut.length === 1) {
      // user gave the surname (last token) of a multi-word required answer
      const last = ct[ct.length - 1];
      if (last.length >= 4 && fuzzy(ut[0], last)) return true;
    }
  }
  return false;
}
function matches(user, cand) {   // cand = parseAnswerline result
  if (!user) return false;
  return matchAny(user, cand.accept) || matchCores(user, cand.cores);
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
const filters = { cats: new Set(), subs: new Set(), subsubs: new Set(), tags: new Set(), eras: new Set(), sections: new Set(), diffs: new Set([7]) };
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
const altName = i => i >= 0 ? CAT.alternate_subcategory_values[i] : null;

function rowInScope(r, upTo) {
  const T = CAT.tossups;
  if (filters.cats.size && !filters.cats.has(catName(T.category[r]))) return false;
  if (upTo === 'cat') return true;
  if (filters.subs.size && !filters.subs.has(subName(T.subcategory[r]))) return false;
  if (filters.subsubs.size && !filters.subsubs.has(altName(T.alternate_subcategory[r]))) return false;
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
  const SEC = CAT.section_values || [];
  // Dynamic faceted counts: each facet's chip number = how many questions
  // it would represent GIVEN the other active filters, so counts react as
  // you pick a difficulty, category, etc. Each facet is restricted by its
  // ancestors (category > subcategory > subtype > group) plus the
  // orthogonal difficulty filter, but NOT by its own selection (so you can
  // still see and multi-select siblings). Difficulty is restricted by the
  // whole taxonomy above it, so it reacts symmetrically.
  const catCount = {}, subCount = {}, subsubCount = {}, secCount = {}, diffCount = {};
  let subsubHave = 0, subsubTot = 0;
  const hasCats = filters.cats.size, hasSubs = filters.subs.size,
        hasSubsub = filters.subsubs.size, hasSec = filters.sections.size,
        hasDiff = filters.diffs.size;
  for (let r = 0; r < n; r++) {
    const c = catName(T.category[r]);
    if (!c) continue;
    const s = subName(T.subcategory[r]);
    const a = altName(T.alternate_subcategory[r]);
    const sec = T.section ? T.section[r] : -1;
    const d = T.difficulty[r];
    const pCat = !hasCats || filters.cats.has(c);
    const pSub = !hasSubs || (s && filters.subs.has(s));
    const pSubsub = !hasSubsub || (a && filters.subsubs.has(a));
    const pSec = !hasSec || filters.sections.has(sec);
    const pDiff = !hasDiff || filters.diffs.has(d);
    if (pDiff) catCount[c] = (catCount[c] || 0) + 1;
    if (pCat && pDiff && s) subCount[s] = (subCount[s] || 0) + 1;
    if (pCat && pSub && pDiff) {
      subsubTot++;
      if (a) { subsubHave++; subsubCount[a] = (subsubCount[a] || 0) + 1; }
    }
    if (T.section && pCat && pSub && pSubsub && pDiff)
      secCount[sec] = (secCount[sec] || 0) + 1;
    if (pCat && pSub && pSubsub && pSec && d > 0)
      diffCount[d] = (diffCount[d] || 0) + 1;
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

  // Subtype (alternate_subcategory) facet. qbreader only populates this
  // column where it fully partitions the subcategory — Other Fine Arts
  // (Film/Opera/Architecture/…), Other Science (Math/Astronomy/…), Social
  // Science (Economics/Psychology/…); elsewhere it's near-null noise. So we
  // show it only once a category is chosen AND most in-scope rows actually
  // carry a subtype, which self-gates to exactly those three umbrellas.
  // (counts computed in the faceted pass above)
  const subsubEntries = bySize(subsubCount).filter(e => e[1] >= 5);
  const showSubsub = filters.cats.size > 0 && subsubTot > 0
    && subsubHave / subsubTot >= 0.5 && subsubEntries.length >= 2;
  $('subsub-head').style.display = showSubsub ? '' : 'none';
  if (showSubsub) {
    // keep an active selection visible even if it dips below the threshold
    for (const s of filters.subsubs)
      if (!subsubEntries.some(e => e[0] === s)) subsubEntries.push([s, subsubCount[s] || 0]);
    renderChipSet($('f-subsub'), subsubEntries, filters.subsubs, onFilter);
  } else {
    filters.subsubs.clear();
    $('f-subsub').innerHTML = '';
  }

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

  // Group (overview section) facet. Sections are unit-specific, so the
  // chips are coherent only once the scope resolves to a SINGLE overview
  // unit — however that happens: a subcategory pick (Fine Arts ▸ Visual
  // Fine Arts), a single-unit category with no subcategory to pick
  // (Mythology, Religion, Philosophy, Geography), or a Subtype pick that
  // narrows an umbrella subcategory to one genre unit (Other Fine Arts ▸
  // Opera, Social Science ▸ Psychology). Sectioned ids first (by count),
  // then an "Unsectioned" chip for the -1 bucket.
  const secIds = Object.keys(secCount).map(Number);
  const sectioned = secIds.filter(id => id >= 0)
    .sort((a, b) => secCount[b] - secCount[a]).slice(0, 40);
  const scopeUnits = new Set(secIds.filter(id => id >= 0)
    .map(id => SEC[id] && SEC[id][0]).filter(Boolean));
  const showGroups = sectioned.length > 1 && scopeUnits.size === 1;
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
  } else {
    filters.sections.clear();  // groups hidden -> drop any stale section picks
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
    subsub: doc.alternate_subcategory || altName(T.alternate_subcategory[r]) || '',
    d: T.difficulty[r], setName: set.name, year: set.year,
    slug: ID2SLUG.get(doc._id) || null,
    sectionId: (T.section && T.section[r] >= 0) ? T.section[r] : -1,
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
  cur = { q, units, skipWords, startSent, sents, slow: slowSpans(units.map(u => u.t)), showSkipped: false, prompted: false, userRaw: null };
  wordIdx = 0; buzzAt = null;
  $('m-set').textContent = q.setName;
  $('m-diff').textContent = 'diff ' + q.d;
  $('m-cat').textContent = q.cat + (q.sub && q.sub !== q.cat ? ' · ' + q.sub : '')
    + (q.subsub ? ' · ' + q.subsub : '');
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
  const raw = $('answerinput').value.trim();
  const user = normAns(raw);
  const cand = parseAnswerline(cur.q.a, cur.q.as);
  $('answerrow').classList.remove('show');
  if (matches(user, cand)) { judged('C', raw); return; }
  // one directed prompt, qbreader-style, before deciding
  if (!cur.prompted && user && matchAny(user, cand.prompt)) {
    cur.prompted = true;
    setStatus('buzzed', 'Prompt — be more specific');
    $('verdict').className = 'verdict p';
    $('verdict').textContent = '“' + raw + '” — prompt. One more try:';
    $('judge').classList.add('show');
    $('answerline').innerHTML = '';
    $('selfgrade').style.display = 'none';
    $('answerrow').classList.add('show');
    $('answerinput').value = ''; $('answerinput').focus();
    return;
  }
  judged('W', raw);
}

// auto-verdict, then let the reader override it (checking isn't perfect)
function judged(res, raw) {
  phase = 'done';
  cur.userRaw = raw;
  record(res, buzzPct());
  renderVerdict(res);
  showJudge(res);
  updateButtons();
}
function regrade(newRes) {
  const last = LOG[LOG.length - 1];
  if (last && last.res !== newRes) {
    last.res = newRes;
    last.pow = newRes === 'C' && poweredBuzz();
    saveLog();
  }
  renderVerdict(newRes);
  showJudge(newRes);
}
function renderVerdict(res) {
  const pct = buzzPct();
  setStatus(res === 'C' ? 'done-c' : 'done-w',
    (res === 'C' ? (poweredBuzz() ? 'Power!' : 'Correct') : 'Wrong') + (pct != null ? ' · ' + pct + '%' : ''));
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
  $('judge').classList.add('show');
  const overridable = res === 'C' || res === 'W';   // you actually answered
  const said = cur.userRaw != null && cur.userRaw !== ''
    ? ' <span style="color:var(--faint)">— you said “' + esc(cur.userRaw) + '”</span>' : '';
  if (res === 'C') { $('verdict').className = 'verdict c'; $('verdict').innerHTML = (poweredBuzz() ? 'Correct — in power' : 'Correct') + said; }
  else if (res === 'W') { $('verdict').className = 'verdict w'; $('verdict').innerHTML = 'Incorrect' + said; }
  else { $('verdict').className = 'verdict'; $('verdict').textContent = 'No buzz — the answer was:'; }
  $('answerline').innerHTML = answerHTML(cur.q.a);
  // override row — the auto-check is a suggestion; let the reader correct it
  const sg = $('selfgrade');
  sg.style.display = overridable ? 'flex' : 'none';
  $('sg-right').classList.toggle('on', res === 'C');
  $('sg-wrong').classList.toggle('on', res === 'W');
  showWiki();
}

// Scope the reader to a taxonomy slice and jump straight into it — powers
// the "Practice more" chips (e.g. drill the rest of a Romantic-composer group
// after a miss).
function practiceScope(opts) {
  for (const k of ['cats', 'subs', 'subsubs', 'sections', 'tags', 'eras']) filters[k].clear();
  if (opts.cat) filters.cats.add(opts.cat);
  if (opts.sub) filters.subs.add(opts.sub);
  if (opts.subsub) filters.subsubs.add(opts.subsub);
  if (opts.section != null && opts.section >= 0) filters.sections.add(opts.section);
  onFilter();
  loadNext();
  window.scrollTo({ top: 0 });
}

function showWiki() {
  const q = cur.q;
  const slug = q.slug;
  let t = slug ? TOPICS[slug] : null;
  // Trust the wiki topic only when its category matches the question's — a
  // "Mendelssohn" music tossup must not resolve to a philosophy page.
  if (t && q.cat && t.category && t.category !== q.cat) t = null;

  const topicBlock = $('w-topicblock');
  if (t) {
    topicBlock.style.display = '';
    $('w-topic').textContent = t.name;
    $('w-topic').href = 'output/' + slug + '/stock.html';
    const bits = [];
    if (t.year != null) bits.push(t.year < 0 ? Math.abs(t.year) + ' BCE' : String(t.year));
    if (t.country) bits.push(t.country);
    bits.push(t.category + (t.subcategory && t.subcategory !== t.category ? ' · ' + t.subcategory : ''));
    $('w-meta').textContent = bits.join(' · ');
    const tagEl = $('w-tags'); tagEl.innerHTML = '';
    for (const tag of (t.tags || [])) {
      const c = chip(tag, null, false);
      if (FACETS_ON) { c.title = 'Practice this: add to scope'; c.onclick = () => { filters.tags.add(tag); onFilter(); window.scrollTo({ top: 0 }); }; }
      tagEl.appendChild(c);
    }
    // Related — restricted to the SAME category, so a composer suggests other
    // composers (Schumann), not cross-domain co-mentions (Spinoza/Lessing).
    const relEl = $('w-rel'); relEl.innerHTML = '';
    const rel = (t.related || [])
      .filter(x => { const rt = TOPICS[x.slug]; return rt && (!q.cat || rt.category === q.cat); })
      .slice(0, 5);
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
  } else {
    topicBlock.style.display = 'none';
  }

  // "Practice more" — always available, driven by the question's own taxonomy
  // (works for every category, wiki-linked or not). Group chip drills the
  // overview section (e.g. Romanticism); subcategory chip broadens.
  const pEl = $('w-practice'); pEl.innerHTML = '';
  const addChip = (label, title, fn) => {
    const c = chip(label, null, false);
    c.title = title; c.style.color = 'var(--wiki)';
    c.onclick = fn; pEl.appendChild(c);
  };
  if (q.section && q.sectionId >= 0)
    addChip('▸ ' + q.section, 'Drill this group',
      () => practiceScope({ cat: q.cat, sub: q.sub, subsub: q.subsub, section: q.sectionId }));
  if (q.sub)
    addChip('▸ ' + q.sub, 'Drill this subcategory',
      () => practiceScope({ cat: q.cat, sub: q.sub === q.cat ? '' : q.sub }));
  $('w-practiceblock').style.display = pEl.children.length ? '' : 'none';

  if (t || pEl.children.length) $('wikibox').classList.add('show');
  else $('wikibox').classList.remove('show');
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
let statsDim = 'cat';                     // pivot dimension (coarseness)
let statsSort = { col: 'acc', dir: 1 };   // 1 asc (weakest first), -1 desc
// Scope filters the WHOLE stats view; the pivot dimension then chooses how
// coarse the breakdown is. Scope by category+subcategory and pivot by Group
// to see, e.g., celerity per overview section within Visual Fine Arts.
const statsScope = { cat: '', sub: '', diff: '' };
const DIMS = { cat: r => r.cat, sub: r => r.sub, section: r => r.section, diff: r => r.diff != null ? 'Diff ' + r.diff : null };

function scopedLog() {
  return LOG.filter(r =>
    (!statsScope.cat || r.cat === statsScope.cat) &&
    (!statsScope.sub || r.sub === statsScope.sub) &&
    (!statsScope.diff || String(r.diff) === statsScope.diff));
}
// distinct values of a field across the log (optionally within the chosen
// category), for populating the scope dropdowns.
function distinctVals(field, withinCat) {
  const s = new Set();
  for (const r of LOG) {
    if (withinCat && statsScope.cat && r.cat !== statsScope.cat) continue;
    const v = r[field];
    if (v != null && v !== '') s.add(String(v));
  }
  return [...s];
}

function aggBy(keyFn, data) {
  const m = new Map();
  for (const r of (data || LOG)) {
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
      + '<td>' + (r.cel == null ? '<span class="pct" style="color:var(--faint)">—</span>'
          : '<span class="bar"><i style="width:' + Math.round(r.cel * 100) + '%;background:' + pctCol(r.cel) + '"></i></span><span class="pct">' + fmtPct(r.cel) + '</span>') + '</td>'
      + '<td class="pct">' + fmtPct(r.neg) + '</td>'
      + '<td>' + (opts.action ? opts.action(r.k) : '') + '</td></tr>';
  }
  return h + '</table>';
}

function trendBlock(data) {
  // last 50 vs prior 50 attempts: accuracy + celerity deltas
  if (data.length < 20) return '';
  const N = Math.min(50, Math.floor(data.length / 2));
  const recent = data.slice(-N), prior = data.slice(-2 * N, -N);
  const acc = a => a.filter(r => r.res === 'C').length / a.length;
  const cel = a => { const b = a.filter(r => r.res === 'C' && r.bf != null); return b.length ? b.reduce((s, r) => s + (1 - r.bf), 0) / b.length : null; };
  const dAcc = acc(recent) - acc(prior), dCel = (cel(recent) || 0) - (cel(prior) || 0);
  const arrow = d => d > 0.01 ? '<span style="color:var(--good)">▲ ' + Math.round(d * 100) + '%</span>' : d < -0.01 ? '<span style="color:var(--bad)">▼ ' + Math.round(-d * 100) + '%</span>' : '<span style="color:var(--faint)">flat</span>';
  return '<div class="statnote">Trend (last ' + N + ' vs prior ' + N + '): accuracy ' + arrow(dAcc) + ' · celerity ' + arrow(dCel) + '</div>';
}

/* ---------- buzz calibration: accuracy vs buzz depth ----------
   A fitted logistic curve P(correct)=sigmoid(a+b·depth) with a 95% band,
   over the empirical per-band rates. Fitting (not interpolating) is what
   keeps it stable on the sparse per-user history; the band widens honestly
   where data is thin, and below ~40 buzzes we show nothing but a nudge. */
const CALIB_MIN = 40;
function calibrationBlock(data) {
  const buzzed = data.filter(r => r.bf != null);
  if (buzzed.length < 12) return '';
  let h = '<h2 class="sechead">Buzz calibration</h2><div class="statnote">How your accuracy changes with buzz depth. The curve is a fitted trend, the band is 95% uncertainty (wider where you have fewer buzzes); dots are your actual rate in each depth band, and the faint bars show <b style="color:var(--muted)">where you tend to buzz</b>.</div>';
  if (buzzed.length < CALIB_MIN)
    return h + '<div class="statnote" style="margin-top:-0.7rem">Keep playing — the calibration curve needs about ' + CALIB_MIN + ' buzzes to fit reliably (you have ' + buzzed.length + ' in this scope).</div>';
  return h + '<canvas id="calibcanvas" width="720" height="280" class="calibcv"></canvas>';
}

// logistic regression P(correct)=sigmoid(a+b·depth) via IRLS, + covariance
function logisticFit(pts) {
  let a = 0, b = 0; const ridge = 1e-3;
  for (let it = 0; it < 30; it++) {
    let g0 = 0, g1 = 0, h00 = ridge, h01 = 0, h11 = ridge;
    for (const p of pts) { const eta = a + b * p.x, pr = 1 / (1 + Math.exp(-eta)), w = Math.max(pr * (1 - pr), 1e-6); g0 += p.y - pr; g1 += (p.y - pr) * p.x; h00 += w; h01 += w * p.x; h11 += w * p.x * p.x; }
    const det = h00 * h11 - h01 * h01; if (Math.abs(det) < 1e-12) break;
    const d0 = (h11 * g0 - h01 * g1) / det, d1 = (h00 * g1 - h01 * g0) / det; a += d0; b += d1;
    if (Math.abs(d0) + Math.abs(d1) < 1e-8) break;
  }
  let h00 = ridge, h01 = 0, h11 = ridge;
  for (const p of pts) { const eta = a + b * p.x, pr = 1 / (1 + Math.exp(-eta)), w = Math.max(pr * (1 - pr), 1e-6); h00 += w; h01 += w * p.x; h11 += w * p.x * p.x; }
  const det = h00 * h11 - h01 * h01;
  return { a, b, c00: h11 / det, c01: -h01 / det, c11: h00 / det };
}
function calibPred(fit, x) {
  const eta = fit.a + fit.b * x;
  const se = Math.sqrt(Math.max(fit.c00 + 2 * fit.c01 * x + fit.c11 * x * x, 0));
  const s = z => 1 / (1 + Math.exp(-z));
  return { p: s(eta), lo: s(eta - 1.96 * se), hi: s(eta + 1.96 * se) };
}
function drawCalib(data) {
  const cv = $('calibcanvas'); if (!cv || !cv.getContext) return;
  const buzzed = data.filter(r => r.bf != null); if (buzzed.length < CALIB_MIN) return;
  const ctx = cv.getContext('2d'); const W = cv.width, H = cv.height; ctx.clearRect(0, 0, W, H);
  const L = 46, R = 14, T = 16, B = 36, px0 = L, px1 = W - R, py0 = T, py1 = H - B;
  const X = x => px0 + x * (px1 - px0), Y = y => py1 - y * (py1 - py0);
  const cBorder = '#3a3f47', cFaint = '#808790', cAccent = '#e8b04a', cText = '#c8ccd1';
  const pcol = v => v < 0.5 ? '#e0655f' : v < 0.75 ? '#e8b04a' : '#5dbb7a';
  // histogram — where you buzz (own scale, subtle)
  const NB = 12, bins = new Array(NB).fill(0);
  for (const r of buzzed) bins[Math.min(NB - 1, Math.floor(r.bf * NB))]++;
  const maxB = Math.max(...bins, 1);
  ctx.fillStyle = 'rgba(128,135,144,0.16)';
  for (let i = 0; i < NB; i++) { const bw = (px1 - px0) / NB, bh = (bins[i] / maxB) * (py1 - py0) * 0.42; ctx.fillRect(px0 + i * bw + 1, py1 - bh, bw - 2, bh); }
  // grid + labels
  ctx.font = '11px -apple-system,Segoe UI,sans-serif'; ctx.lineWidth = 1;
  for (const gy of [0, 0.25, 0.5, 0.75, 1]) { ctx.strokeStyle = cBorder; ctx.globalAlpha = gy === 0 ? 0.6 : 0.28; ctx.beginPath(); ctx.moveTo(px0, Y(gy)); ctx.lineTo(px1, Y(gy)); ctx.stroke(); ctx.globalAlpha = 1; ctx.fillStyle = cFaint; ctx.textAlign = 'right'; ctx.fillText(Math.round(gy * 100) + '%', px0 - 6, Y(gy) + 3); }
  ctx.textAlign = 'center'; ctx.fillStyle = cFaint;
  for (const gx of [0, 0.25, 0.5, 0.75, 1]) ctx.fillText(Math.round(gx * 100) + '%', X(gx), py1 + 16);
  ctx.fillText('buzz depth  (0% = start of question → 100% = end)', (px0 + px1) / 2, py1 + 30);
  // fitted curve + band
  const fit = logisticFit(buzzed.map(r => ({ x: r.bf, y: r.res === 'C' ? 1 : 0 })));
  const xs = []; for (let i = 0; i <= 60; i++) xs.push(i / 60);
  const pr = xs.map(x => calibPred(fit, x));
  ctx.fillStyle = 'rgba(232,176,74,0.14)'; ctx.beginPath();
  xs.forEach((x, i) => { const p = ctx[i ? 'lineTo' : 'moveTo'](X(x), Y(pr[i].hi)); });
  for (let i = xs.length - 1; i >= 0; i--) ctx.lineTo(X(xs[i]), Y(pr[i].lo));
  ctx.closePath(); ctx.fill();
  ctx.strokeStyle = cAccent; ctx.lineWidth = 2.2; ctx.beginPath();
  xs.forEach((x, i) => { ctx[i ? 'lineTo' : 'moveTo'](X(x), Y(pr[i].p)); }); ctx.stroke();
  // empirical dots per depth band (skip bands with <3 buzzes)
  const NBK = 5;
  for (let bi = 0; bi < NBK; bi++) {
    const lo = bi / NBK, hi = (bi + 1) / NBK, cx = (lo + hi) / 2;
    const bd = buzzed.filter(r => r.bf >= lo && (bi === NBK - 1 ? r.bf <= hi : r.bf < hi));
    if (bd.length < 3) continue;
    const acc = bd.filter(r => r.res === 'C').length / bd.length, rad = Math.min(9, 3.5 + Math.sqrt(bd.length));
    ctx.beginPath(); ctx.arc(X(cx), Y(acc), rad, 0, 6.2832); ctx.fillStyle = pcol(acc); ctx.globalAlpha = 0.92; ctx.fill(); ctx.globalAlpha = 1;
    ctx.lineWidth = 1.5; ctx.strokeStyle = '#101418'; ctx.stroke();
    ctx.fillStyle = cText; ctx.textAlign = 'center'; ctx.font = '10px -apple-system,sans-serif'; ctx.fillText(bd.length + '', X(cx), Y(acc) - rad - 4);
  }
  // axis frame
  ctx.strokeStyle = cBorder; ctx.globalAlpha = 0.6; ctx.lineWidth = 1; ctx.beginPath(); ctx.moveTo(px0, py0); ctx.lineTo(px0, py1); ctx.lineTo(px1, py1); ctx.stroke(); ctx.globalAlpha = 1;
}

function exposureBlock(data) {
  const seenAns = new Set(data.map(r => r.ans).filter(Boolean)).size;
  const seenSec = new Set(data.map(r => r.section).filter(Boolean)).size;
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
  const data = scopedLog();
  const dn = data.length;
  const c = data.filter(r => r.res === 'C').length;
  const negs = data.filter(r => r.res === 'W').length;
  const dead = data.filter(r => r.res === 'D').length;
  const celA = data.filter(r => r.res === 'C' && r.bf != null);
  const cel = celA.length ? celA.reduce((s, r) => s + (1 - r.bf), 0) / celA.length : null;
  const tile = (k, v) => '<div class="stat"><div class="k">' + k + '</div><div class="v">' + v + '</div></div>';
  g.innerHTML = tile('Questions', dn)
    + tile('Accuracy', dn ? Math.round(c / dn * 100) + '<small>%</small>' : '—')
    + tile('Celerity', cel == null ? '—' : Math.round(cel * 100) + '<small>%</small>')
    + tile('Neg rate', dn ? Math.round(negs / dn * 100) + '<small>%</small>' : '—')
    + tile('Dead', dn ? Math.round(dead / dn * 100) + '<small>%</small>' : '—');
  $('statnote').innerHTML = '<button class="btn primary" id="drillbtn">&#9654; Drill my weaknesses</button>'
    + ' <span style="color:var(--faint)">Celerity = how early you buzz on correct answers (higher = earlier).</span> '
    + '<button class="linkbtn" id="clearstats">Clear history</button>';
  $('drillbtn').onclick = () => {
    settings.drill = true; $('drill').checked = true; $('drillrow').style.display = '';
    rebuildQueue(); showView('play');
  };
  $('clearstats').onclick = () => { if (confirm('Clear all reader history?')) { LOG = []; saveLog(); renderStats(); rebuildQueue(); } };

  const DIM_LABEL = { cat: 'Category', sub: 'Subcategory', section: 'Group', diff: 'Difficulty' };
  // Scope control — filters the whole stats view. Subcategory options
  // follow the chosen category; difficulty is a plain value list.
  const opt = (v, cur, label) => '<option value="' + esc(v) + '"' + (v === cur ? ' selected' : '') + '>' + esc(label || v) + '</option>';
  const sel = (id, cur, vals, allLabel) => '<select class="scopesel" id="' + id + '">'
    + opt('', cur, allLabel) + vals.map(v => opt(v, cur)).join('') + '</select>';
  const alpha = a => a.slice().sort();
  let h = '<div class="scoperow">'
    + '<span class="scopelbl">Scope</span>'
    + sel('sc-cat', statsScope.cat, alpha(distinctVals('cat', false)), 'All categories')
    + sel('sc-sub', statsScope.sub, alpha(distinctVals('sub', true)), 'All subcategories')
    + sel('sc-diff', statsScope.diff, distinctVals('diff', false).sort((a, b) => a - b), 'All difficulties')
    + (statsScope.cat || statsScope.sub || statsScope.diff
        ? ' <button class="linkbtn" id="sc-reset">Reset</button>' : '')
    + '</div>';
  h += trendBlock(data) + exposureBlock(data);
  // dimension selector = how coarse the breakdown is
  h += '<h2 class="sechead">Breakdown</h2>'
    + '<div class="statnote">Pick how coarse to slice — sort any column (weakest first).</div>'
    + '<div class="dimsel" id="dimsel">';
  for (const d of ['cat', 'sub', 'section', 'diff'])
    h += '<button class="dimbtn' + (statsDim === d ? ' on' : '') + '" data-dim="' + d + '">' + DIM_LABEL[d] + '</button>';
  h += '</div>';
  h += statTable(aggBy(DIMS[statsDim], data), { label: DIM_LABEL[statsDim], min: statsDim === 'section' ? 2 : 1 });
  h += calibrationBlock(data);
  // weakest answerlines — the drill seed
  h += '<h2 class="sechead">Weakest answerlines</h2>'
    + '<div class="statnote">Individual answers you miss most (seen ≥ 2), weakest first.</div>'
    + statTable(aggBy(r => r.ans, data), {
        label: 'Answerline', min: 2,
        name: k => {
          const rec = data.find(r => r.ans === k);
          const disp = rec ? rec.aDisp : k;
          return rec && rec.t ? '<a href="output/' + esc(rec.t) + '/stock.html">' + esc(disp) + '</a>' : esc(disp);
        },
      });
  body.innerHTML = h;
  $('sc-cat').onchange = e => { statsScope.cat = e.target.value; statsScope.sub = ''; renderStats(); };
  $('sc-sub').onchange = e => { statsScope.sub = e.target.value; renderStats(); };
  $('sc-diff').onchange = e => { statsScope.diff = e.target.value; renderStats(); };
  if ($('sc-reset')) $('sc-reset').onclick = () => { statsScope.cat = statsScope.sub = statsScope.diff = ''; renderStats(); };
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
  drawCalib(data);   // paint the calibration canvas once it's in the DOM
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
  $('sg-right').onclick = () => regrade('C');
  $('sg-wrong').onclick = () => regrade('W');

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
