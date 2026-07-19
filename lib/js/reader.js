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
/* Known abbreviations, plus single-letter initial(ism)s ("W.", "v.",
   "O.B.", "U.S."). MUST stay in lockstep with lib/pipeline/parse.py
   split_sentences — the sentence-embedding index keys on these boundaries. */
const ABBREV = /(?:\b(?:Mr|Mrs|Ms|Dr|St|Sts|Mt|vs|etc|Jr|Sr|Prof|Gen|Col|Fr|ca|e\.g|i\.e|No|Op|Nos)|(?:^|[^A-Za-z])(?:[A-Za-z]\.)*[A-Za-z])\.$/;
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
// A note token, tolerant of a plural/possessive suffix ("three C's",
// "repeated B-flats") and trailing punctuation.
const NOTEISH = /^["“(«]?(?:[A-G](?:♯|♭|#|b)?(?:-?(?:sharp|flat|natural))?|[Dd]o|[Rr]e|[Mm]i|[Ff]a|[Ss]ol|[Ll]a|[Tt]i|[Ss]i)(?:['’]?s)?[”")»\],.;:!?–—-]*$/;
// Words that DESCRIBE a note rather than being a note themselves — they
// extend a run without counting as a new note or breaking it, so score clues
// written in prose still slow down. Kept to genuinely musical descriptors
// (accidentals, register, key, duration, articulation, contour, small repeat
// counts) so ordinary prose terminators ("theme", "symphony", "section") do
// still break the run. Lone dashes ("E – F – G") are handled in slowSpans.
const NOTE_CONT = /^(?:double[-\s]?)?(?:sharps?|flats?|naturals?|longs?|shorts?|repeated|dotted|tied|slurred|staccato|triplets?|high(?:er)?|low(?:er)?|notes?|majors?|minors?|eighths?|quarters?|sixteenths?|thirty|second|halves|half|whole|ascending|descending|rising|falling|pause|rest|sustained|grace|augmented|diminished|perfect|two|three|four|five|six|seven|eight)[”")»\],.;:!?]*$/i;
// Short connective/direction words allowed BETWEEN notes ("C to G, then back
// up to E"). Only these function words bridge a run; any content word still
// breaks it, which keeps prose from being mistaken for a score clue.
const NOTE_GLUE = /^(?:and|then|to|or|a|an|back|up|down|again|from|by|via|of|followed)[,.;:]?$/i;
const LONE_DASH = /^[–—-]+$/;
const SLOW_FACTOR = 2.4, GLUE_MAX = 3;
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
    const w = words[i];
    if (NOTEISH.test(w)) { if (runStart < 0) runStart = i; noteCount++; gap = 0; }
    else if (runStart >= 0 && (NOTE_CONT.test(w) || LONE_DASH.test(w))) { /* describes/links a note: extend run, don't count */ }
    else if (runStart >= 0 && NOTE_GLUE.test(w) && gap < GLUE_MAX) { gap++; }
    else if (runStart >= 0) { flush(i); }
  }
  flush(words.length);
  return slow;
}

/* ---------- answer checking ----------
   Grading is qbreader's own checker, vendored verbatim in answer_checker.js
   (window.qbCheckAnswer): full accept/prompt/reject clause parsing, directed
   prompts, abbreviation + underlining logic, typo tolerance. The verdict
   stays a suggestion — the reader always lets you override it. The helpers
   below only derive the drill/stats answerline KEY, not the verdict. */
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
// The drill/stats answerline key: the bold-underline CORE (not the full
// accept/prompt clause), so the same answer unifies across questions that
// phrase their accept clauses differently. Falls back to the pre-bracket
// main answer when there's no markup. Mirrors publish.py answer_key so the
// catalog's answerline_values line up with each LOG entry's key.
function answerKey(raw, san) {
  const cores = requiredCores(raw || '').filter(s => s.trim());
  const base = cores.length ? cores[0]
    : (san || (raw || '').replace(/<[^>]+>/g, '')).split(/[\[(]/)[0];
  return normAns(base);
}

/* ---------- data plane ---------- */
let CAT = null;          // catalog.json
let TOPICS = null;       // topics.json .topics
let ID2SLUG = null;      // tossup id -> topic slug
let ID2ROW = null;       // tossup id -> catalog row index
let AKEYS = null;        // distinct answerline id -> normalized key (catalog)
const shardDocs = new Map();   // set slug -> Map(tossup id -> doc)

// Normalized answerline for a catalog row, keyed to match each LOG entry
// (LOG stores normAns(answer_sanitized); the catalog's answerline_values are
// the deduped sanitized answers, re-normalized here so the JS normAns is
// authoritative on both sides). '' when the column isn't published yet.
function rowAns(r) {
  const T = CAT.tossups;
  if (!AKEYS || !T.answerline) return '';
  const id = T.answerline[r];
  return id >= 0 ? (AKEYS[id] || '') : '';
}

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
// Subcategories whose alternate_subcategory (subtype) genuinely partitions
// them — Other Science, Other Fine Arts, Social Science, the Literature
// forms. Computed once from the corpus: real partitions sit at ~100%
// coverage, incidental mis-tags (a few VFA/AFA/Mythology rows) at ~0-2%, so
// a 50% floor cleanly separates them. Only these feed the subtype facet.
let SUBTYPED_SUBS = null;
// Static taxonomy maps (from the corpus): which category each subcategory
// belongs to, and which subtypes occur under each subcategory / category.
// These drive the hierarchical filter semantics in rowInScope.
let CAT_OF_SUB = null;    // sub name -> its category name
let ALTS_OF_SUB = null;   // sub name -> Set of subtype names occurring in it
let CATS_OF_ALT = null;   // subtype name -> Set of category names it occurs in
// Max distinct overview units the Group facet will span — enough for an
// explicit multi-select of a few subtype units, below the many-unit count of
// an unfocused category-level scope. Only units with a real presence in the
// scope count (GROUP_UNIT_FLOOR rows) — the corpus has stray mis-sectioned
// rows (a "Math" question sectioned under religion) that must not trip this.
const GROUP_UNIT_CAP = 4;
const GROUP_UNIT_FLOOR = 5;
function computeSubtypedSubs() {
  const T = CAT.tossups, n = T.id.length, tot = {}, have = {}, pair = {};
  CAT_OF_SUB = {}; ALTS_OF_SUB = {}; CATS_OF_ALT = {};
  for (let r = 0; r < n; r++) {
    const s = subName(T.subcategory[r]); if (!s) continue;
    tot[s] = (tot[s] || 0) + 1;
    CAT_OF_SUB[s] = catName(T.category[r]);
    if (T.alternate_subcategory[r] >= 0) {
      have[s] = (have[s] || 0) + 1;
      const k = s + '\x00' + altName(T.alternate_subcategory[r]);
      pair[k] = (pair[k] || 0) + 1;
    }
  }
  SUBTYPED_SUBS = new Set();
  for (const s in tot) if ((have[s] || 0) >= 30 && have[s] / tot[s] >= 0.5) SUBTYPED_SUBS.add(s);
  // taxonomy maps only from real partitions: subtype-bearing subs and
  // (sub, subtype) pairs with a genuine presence — a lone mis-tagged row
  // (a Mythology question marked "Math") must not teach the hierarchy
  // that Math lives under Mythology.
  for (const k in pair) {
    const [s, a] = k.split('\x00');
    if (!SUBTYPED_SUBS.has(s) || pair[k] < 10) continue;
    (ALTS_OF_SUB[s] = ALTS_OF_SUB[s] || new Set()).add(a);
    (CATS_OF_ALT[a] = CATS_OF_ALT[a] || new Set()).add(CAT_OF_SUB[s]);
  }
}

// Hierarchical filter semantics: a sub/subtype pick narrows only its own
// category — a category selected with no descendants picked stays whole, so
// "CS + Math" can sit next to a whole Mythology (or next to Opera under Fine
// Arts) instead of a subtype pick strangling every row that lacks one.
// Derived from the current filters; refreshed before every scope walk.
let DESC_CATS = new Set();        // categories with a selected sub/subtype
let CONSTRAINED_SUBS = new Set(); // subs with >=1 of their subtypes selected
function refreshBranchScopes() {
  if (!CAT) return;
  if (!SUBTYPED_SUBS) computeSubtypedSubs();
  DESC_CATS = new Set([...filters.subs].map(s => CAT_OF_SUB[s]).filter(Boolean));
  for (const a of filters.subsubs) for (const c of (CATS_OF_ALT[a] || [])) DESC_CATS.add(c);
  CONSTRAINED_SUBS = new Set();
  for (const s in ALTS_OF_SUB)
    if ([...filters.subsubs].some(a => ALTS_OF_SUB[s].has(a))) CONSTRAINED_SUBS.add(s);
}
// Taxonomy membership under those semantics; c/s/a are the row's names.
function taxPass(c, s, a) {
  if (filters.cats.size && !filters.cats.has(c)) return false;
  if (!DESC_CATS.has(c)) return true;   // no descendant picks in this category
  if (a != null && filters.subsubs.has(a)) return true;
  return filters.subs.has(s) && !CONSTRAINED_SUBS.has(s);
}
// Deselecting a category orphans its sub/subtype picks — drop them so they
// can't keep filtering the queue from a hidden facet.
function pruneOrphanedPicks() {
  if (!CAT) return;
  if (!SUBTYPED_SUBS) computeSubtypedSubs();
  if (filters.cats.size) {
    for (const s of [...filters.subs]) if (!filters.cats.has(CAT_OF_SUB[s])) filters.subs.delete(s);
    for (const a of [...filters.subsubs])
      if (![...(CATS_OF_ALT[a] || [])].some(c => filters.cats.has(c))) filters.subsubs.delete(a);
  } else { filters.subs.clear(); filters.subsubs.clear(); }
}
// Standard quizbowl category distribution (relative weights, ~per 20-tossup
// packet) — what qbreader samples by, instead of the raw corpus frequency.
// Pop Culture is 0 by default (excluded from the academic distribution); the
// user can raise it. Keys must match catalog category values.
const DEFAULT_DIST = {
  'Literature': 4, 'History': 4, 'Science': 4, 'Fine Arts': 3,
  'Mythology': 1, 'Religion': 1, 'Philosophy': 1, 'Social Science': 1,
  'Geography': 1, 'Current Events': 0.5, 'Other Academic': 0.5, 'Pop Culture': 0,
};
const settings = { wpm: 380, sent: 0, drill: false, focus: 55,  // focus = raw 0..100 (broad..targeted)
  dist: { ...DEFAULT_DIST }, useDist: true, voice: false, vrate: 0.95, multibuzz: false };
let queue = [], qpos = -1;
let cur = null;
let phase = 'idle';      // idle|loading|reading|paused|buzzed|selfgrade|done
let wordIdx = 0, tick = null, graceTimer = null, graceAnim = null;
let buzzAt = null;
let history = [], reviewIdx = -1, liveSnap = null;   // previous-question review

const STORE = 'losReaderStatsV1';
let LOG = [];
try { LOG = JSON.parse(localStorage.getItem(STORE) || '[]'); } catch (e) {}
// Migrate v1 entries: old records stored `pct` (buzz depth 0–100) instead of
// `bf` (buzz fraction 0–1); section/diff/ans/pow are simply absent (treated
// as unknown by the aggregators). Pre-sync records also lack `ts` — they get
// small synthetic ordinals so cross-device dedup (keyed id+ts) stays unique
// while preserving their order.
let _synthTs = 0;
for (const r of LOG) {
  if (r.bf === undefined) r.bf = (r.pct != null) ? r.pct / 100 : null;
  if (typeof r.ts !== 'number') r.ts = ++_synthTs;
}
function saveLog() { try { localStorage.setItem(STORE, JSON.stringify(LOG)); } catch (e) {} }

/* ---------- cross-device sync surface (lib/js/sync.js) ----------
   sync.js is pure transport: it pushes LOG records to the backend and feeds
   remote records back through mergeLog. Records carry a private `_p` flag
   ("pushed") that the stats/drill aggregators ignore. */
window.losReaderHook = {
  getLog: () => LOG,
  save: saveLog,
  onRecord: null,   // sync.js assigns; fired after each attempt is recorded
  // Merge remote records into LOG: dedupe by (id, ts), keep chronological
  // order so the SRS replay stays deterministic across devices.
  mergeLog(entries) {
    const seen = new Set(LOG.map(r => r.id + '/' + r.ts));
    let added = 0;
    for (const r of entries) {
      if (r.bf === undefined) r.bf = (r.pct != null) ? r.pct / 100 : null;
      const k = r.id + '/' + r.ts;
      if (seen.has(k)) continue;
      seen.add(k); LOG.push(r); added++;
    }
    if (added) {
      LOG.sort((a, b) => (a.ts || 0) - (b.ts || 0));
      saveLog();
      if (settings.drill && CAT) rebuildQueue();
      if ($('view-stats').style.display !== 'none') renderStats();
    }
    return added;
  },
};

/* ---------- filtering over the catalog ---------- */
const catName = i => i >= 0 ? CAT.category_values[i] : null;
const subName = i => i >= 0 ? CAT.subcategory_values[i] : null;
const altName = i => i >= 0 ? CAT.alternate_subcategory_values[i] : null;

function rowInScope(r, upTo) {
  const T = CAT.tossups;
  // Read-aloud restricts the whole corpus to questions that have audio, so
  // every facet count and the queue reflect only playable questions.
  if (audioMode() && !hasAudio(T.id[r])) return false;
  const c = catName(T.category[r]);
  if (filters.cats.size && !filters.cats.has(c)) return false;
  if (upTo === 'cat') return true;
  if (!taxPass(c, subName(T.subcategory[r]), altName(T.alternate_subcategory[r]))) return false;
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
  refreshBranchScopes();
  const T = CAT.tossups, n = T.id.length;
  const SEC = CAT.section_values || [];
  // Dynamic faceted counts: each facet's chip number = how many questions
  // it would represent GIVEN the other active filters, so counts react as
  // you pick a difficulty, category, etc. Each facet is restricted by its
  // ancestors plus the orthogonal difficulty filter, but NOT by its own
  // selection (so you can still see and multi-select siblings). Taxonomy
  // membership is hierarchical (taxPass): sub/subtype picks narrow only
  // their own category, so cross-branch mixes (CS + Math next to Opera or a
  // whole Mythology) compose instead of strangling each other. Difficulty
  // is restricted by the whole taxonomy above it, so it reacts symmetrically.
  const catCount = {}, subCount = {}, subsubCount = {}, secCount = {}, diffCount = {};
  const hasSec = filters.sections.size, hasDiff = filters.diffs.size;
  for (let r = 0; r < n; r++) {
    const c = catName(T.category[r]);
    if (!c) continue;
    // Read-aloud: every facet count reflects only audio-backed questions, so
    // the chip numbers stay consistent with the audio-restricted scope total.
    if (audioMode() && !hasAudio(T.id[r])) continue;
    const s = subName(T.subcategory[r]);
    const a = altName(T.alternate_subcategory[r]);
    const sec = T.section ? T.section[r] : -1;
    const d = T.difficulty[r];
    const pCat = !filters.cats.size || filters.cats.has(c);
    const pTax = taxPass(c, s, a);   // full hierarchical taxonomy membership
    const pSec = !hasSec || filters.sections.has(sec);
    const pDiff = !hasDiff || filters.diffs.has(d);
    if (pDiff) catCount[c] = (catCount[c] || 0) + 1;
    if (pCat && pDiff && s) subCount[s] = (subCount[s] || 0) + 1;
    // Only subtype-bearing subcategories feed the subtype facet, so a sibling
    // without subtypes (e.g. Biology next to Other Science) can't dilute it.
    // Gated by category only (not sub/subtype picks): subtype chips stay
    // offered for the whole category scope so picks compose across branches.
    if (pCat && pDiff && a && SUBTYPED_SUBS.has(s))
      subsubCount[a] = (subsubCount[a] || 0) + 1;
    if (T.section && pTax && pDiff)
      secCount[sec] = (secCount[sec] || 0) + 1;
    if (pTax && pSec && d > 0)
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

  // Subtype (alternate_subcategory) facet. subsubCount already holds only
  // rows from subtype-bearing subcategories (SUBTYPED_SUBS — Other Science,
  // Other Fine Arts, Social Science, the Literature forms), so the gate is
  // just "a category is chosen and there are >=2 real subtypes in scope".
  // This shows the subtypes for a subtype-bearing subcategory even when it's
  // selected alongside siblings that have none (the old aggregate coverage
  // ratio hid the facet in that case).
  const subsubEntries = bySize(subsubCount).filter(e => e[1] >= 5);
  const showSubsub = filters.cats.size > 0 && subsubEntries.length >= 2;
  if (showSubsub) {
    // keep an active selection visible even if it dips below the threshold
    for (const s of filters.subsubs)
      if (!subsubEntries.some(e => e[0] === s)) subsubEntries.push([s, subsubCount[s] || 0]);
    renderChipSet($('f-subsub'), subsubEntries, filters.subsubs, onFilter);
  } else if (filters.subsubs.size) {
    // scope no longer supports the full facet, but active picks still filter
    // the queue — keep them visible and removable, never wipe them silently
    renderChipSet($('f-subsub'), [...filters.subsubs].map(a2 => [a2, subsubCount[a2] || 0]),
      filters.subsubs, onFilter);
  } else {
    $('f-subsub').innerHTML = '';
  }
  $('subsub-head').style.display = (showSubsub || filters.subsubs.size) ? '' : 'none';

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

  // Group (overview section) facet. Sections are unit-specific, so the chips
  // are coherent once the scope resolves to a single overview unit — a
  // subcategory pick (Fine Arts ▸ Visual Fine Arts), a single-unit category
  // (Mythology, Religion, Philosophy, Geography), or a Subtype pick that
  // narrows an umbrella to one genre unit (Other Fine Arts ▸ Opera) — OR to
  // a small, explicit multi-select of subtype units (Other Science ▸ Math +
  // Computer Science). A broad, unfocused scope spans many units and would
  // make an incoherent facet, so cap it. Sectioned ids first (by count),
  // then an "Unsectioned" chip for the -1 bucket.
  const secIds = Object.keys(secCount).map(Number);
  // chips: sections with a real presence (or already picked); a couple of
  // stray mis-sectioned rows must not surface foreign-unit chips
  const sectioned = secIds.filter(id => id >= 0)
    .filter(id => secCount[id] >= 3 || filters.sections.has(id))
    .sort((a, b) => secCount[b] - secCount[a]).slice(0, 40);
  // unit-cap gate: count only units the scope genuinely contains — stray
  // rows (e.g. one Math question sectioned under religion) don't add units
  const unitRows = {};
  for (const id of secIds) if (id >= 0 && SEC[id])
    unitRows[SEC[id][0]] = (unitRows[SEC[id][0]] || 0) + secCount[id];
  const scopeUnits = new Set(Object.keys(unitRows).filter(u => unitRows[u] >= GROUP_UNIT_FLOOR));
  const showGroups = sectioned.length > 1 && scopeUnits.size >= 1 && scopeUnits.size <= GROUP_UNIT_CAP;
  const gEl = $('f-groups');
  gEl.innerHTML = '';
  const secChip = (id, label, count) => {
    const c = chip(label, count, filters.sections.has(id));
    if (id === -1) c.title = 'Rare / uncategorized answerlines';
    c.onclick = () => { filters.sections.has(id) ? filters.sections.delete(id) : filters.sections.add(id); onFilter(); };
    gEl.appendChild(c);
  };
  if (showGroups) {
    for (const id of sectioned) secChip(id, SEC[id] ? SEC[id][1] : '?', secCount[id]);
    if (secCount[-1]) secChip(-1, 'Unsectioned', secCount[-1]);
  } else if (filters.sections.size) {
    // scope too broad for the full facet, but active picks still filter the
    // queue — keep them visible and removable, never wipe them silently
    for (const id of [...filters.sections].sort((a, b) => (secCount[b] || 0) - (secCount[a] || 0)))
      secChip(id, id === -1 ? 'Unsectioned' : (SEC[id] ? SEC[id][1] : '?'), secCount[id] || 0);
  }
  $('groups-head').style.display = (showGroups || filters.sections.size) ? '' : 'none';

  const diffs = Object.keys(diffCount).map(Number).sort((a, b) => a - b)
    .filter(d => d > 0).map(d => [String(d), diffCount[d]]);
  $('f-diffs').innerHTML = '';
  for (const [d, cnt] of diffs) {
    const c = chip(d, cnt, filters.diffs.has(Number(d)));
    c.onclick = () => { const v = Number(d); filters.diffs.has(v) ? filters.diffs.delete(v) : filters.diffs.add(v); onFilter(); };
    $('f-diffs').appendChild(c);
  }
  $('scopecount').innerHTML = '<b>' + queueSize().toLocaleString() + '</b> questions';
  updateScopeBadge();
}

function candidateRows() {
  const T = CAT.tossups;
  refreshBranchScopes();
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

function onFilter() { pruneOrphanedPicks(); renderFilters(); rebuildQueue(); savePrefs(); }

/* ---------- drill: buzz-graded spaced repetition ----------
   Anki without a wall clock: "time" is measured in attempts played, not
   days (LOG.length is the logical clock). Each ANSWERLINE carries an
   FSRS-lite state {stab, diff, reps, lapses, last} derived by replaying
   your whole history in order:

     - stab (stability) = the review interval, in attempts, at which
       retrievability decays to TARGET_R. It multiplies up on every pass
       (bigger jumps for early/quick buzzes) and collapses on a miss, so a
       well-known answer drifts to long intervals and a shaky one stays
       close — the schedule reviews strengths occasionally and weaknesses
       constantly from one mechanism.
     - diff (intrinsic difficulty) eases on quick correct buzzes, rises on
       misses (a neg is worse than a dead — you had a misconception).

   The grade is read straight off the buzz: celerity IS the review quality
   (power/early -> Easy -> big stability jump; giveaway -> Hard -> small).

   A candidate question's weight blends three drives:
     - DUE:  how overdue its answerline is (retrievability below TARGET_R).
     - WEAK: its answerline's difficulty and lapse count.
     - NEW:  unseen answerlines, steered toward your weak areas via a
       hierarchical section/subcategory weakness prior (cold-start).
   The focus slider morphs the blend (broad = schedule-driven, revisits
   strengths on time; targeted = hammer the worst items) and doubles as a
   sampling temperature. Sampling is Efraimidis–Spirakis (no replacement). */
const GAMMA = 0.5, PRIOR_M = 5, EXPLORE = 0.4;
const STAB0 = 2, STAB_MIN = 1, STAB_MAX = 500, DIFF0 = 5;
const FACTOR = 9, TARGET_R = 0.9, MIN_GAP = 8;
// per-attempt AREA weakness (drives cold-start priors): miss = 1.0, a
// correct buzz = GAMMA x buzz-fraction (a late correct is partially weak).
function _attemptWeakness(r) {
  return r.res === 'C' ? GAMMA * (r.bf == null ? 0.5 : r.bf) : 1.0;
}
const _clamp = (x, lo, hi) => Math.max(lo, Math.min(hi, x));
// Fold one attempt into an answerline's FSRS-lite state.
function _applyReview(st, r) {
  if (r.res === 'C') {
    const q = _clamp(1 - (r.bf == null ? 0.5 : r.bf), 0, 1);  // celerity = grade
    st.diff = _clamp(st.diff - 0.15 * (q - 0.4), 1, 10);
    const growth = 1 + (11 - st.diff) / 10 * (0.4 + q);       // ~1.1 .. ~2.4
    st.stab = Math.min(STAB_MAX, st.stab * growth);
  } else {
    st.diff = _clamp(st.diff + (r.res === 'W' ? 1.1 : 0.8), 1, 10);  // neg worse
    st.stab = Math.max(STAB_MIN, st.stab * 0.35);
    st.lapses++;
  }
  st.reps++;
}
function masteryModel() {
  const C = LOG.length;
  const item = new Map();                 // answerline -> FSRS-lite state
  let sumAll = 0, nAll = 0;
  const sec = new Map(), sub = new Map();
  const addP = (m, k, w) => { if (k == null) return; let a = m.get(k); if (!a) { a = { s: 0, n: 0 }; m.set(k, a); } a.s += w; a.n++; };
  for (let i = 0; i < LOG.length; i++) {
    const r = LOG[i];
    const w = _attemptWeakness(r); sumAll += w; nAll++;
    addP(sec, r.section, w); addP(sub, r.sub, w);
    const key = r.ans;
    if (key) {
      let st = item.get(key);
      if (!st) { st = { stab: STAB0, diff: DIFF0, reps: 0, lapses: 0, last: i }; item.set(key, st); }
      _applyReview(st, r);
      st.last = i;
    }
  }
  const W0 = nAll ? sumAll / nAll : 0.5;
  const prior = (m, k) => { const a = m.get(k); return a ? (a.s + PRIOR_M * W0) / (a.n + PRIOR_M) : W0; };
  return { C, W0, item, secWk: k => prior(sec, k), subWk: k => prior(sub, k) };
}
function drillWeight(row, M, mix) {
  const T = CAT.tossups;
  const sid = T.section[row];
  const S = sid >= 0 && CAT.section_values[sid] ? CAT.section_values[sid][1] : null;
  const subN = subName(T.subcategory[row]);
  const key = rowAns(row);
  const st = key ? M.item.get(key) : null;
  if (!st) {                               // unseen answerline: explore weak areas
    const prior = (S ? M.secWk(S) : M.W0) * (subN ? M.subWk(subN) : M.W0);
    return mix.wNew * (0.5 + prior) + EXPLORE;
  }
  const elapsed = M.C - st.last;
  if (elapsed < MIN_GAP) return 1e-3;      // just saw this answerline — hold off
  const R = 1 / (1 + elapsed / (FACTOR * st.stab));
  const due = Math.max(0, TARGET_R - R);            // overdue amount (0..0.9)
  const weak = (st.diff / 10) * (1 + 0.15 * st.lapses);
  return Math.max(mix.wDue * due + mix.wWeak * weak + 1e-3, 1e-4);
}

function rebuildQueue() {
  const rows = candidateRows();
  const T = CAT.tossups;
  if (settings.drill && LOG.length) {
    // focus 0 (broad) .. 1 (targeted): morphs the drive blend and the
    // sampling temperature together.
    const M = masteryModel();
    const f = settings.focus / 100;
    const tau = 2.5 - f * 2.1;
    const mix = { wDue: 1.0 - 0.6 * f, wWeak: 0.3 + 1.2 * f, wNew: 0.2 + 0.8 * (1 - f) };
    queue = rows.map(r => {
      const w = Math.pow(drillWeight(r, M, mix), 1 / tau);
      return [Math.pow(Math.random(), 1 / w), r];
    }).sort((a, b) => b[0] - a[0]).map(x => x[1]);
  } else if (settings.useDist) {
    // qbreader-style category-distribution sampling: each in-scope category's
    // share of the queue follows settings.dist (default = standard quizbowl
    // mix), uniform within a category, with a mild unseen-first preference.
    // A category explicitly chosen in the filter is never fully excluded even
    // if its distribution weight is 0.
    const seen = new Set(LOG.map(rec => rec.id));
    const explicit = filters.cats.size > 0;
    const weightFor = c => {
      let dw = Math.max(0, settings.dist[c] || 0);
      if (explicit && filters.cats.has(c) && dw === 0) dw = 1;
      return dw;
    };
    const cnt = {};
    for (const r of rows) { const c = catName(T.category[r]); if (c) cnt[c] = (cnt[c] || 0) + 1; }
    let totalW = 0; for (const c in cnt) totalW += weightFor(c);
    const scored = [];
    for (const r of rows) {
      const c = catName(T.category[r]);
      let w;
      if (totalW > 0) { const dw = weightFor(c); if (dw <= 0) continue; w = dw / cnt[c]; }
      else { w = 1 / (cnt[c] || 1); }   // no distribution weight in scope -> uniform
      w *= seen.has(T.id[r]) ? 0.5 : 1;
      scored.push([Math.pow(Math.random(), 1 / w), r]);
    }
    queue = scored.sort((a, b) => b[0] - a[0]).map(x => x[1]);
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
  if (reviewIdx >= 0) {   // leaving review: snap back to the live question first
    cur = liveSnap.cur; buzzAt = liveSnap.buzzAt; wordIdx = liveSnap.wordIdx; phase = liveSnap.phase;
    liveSnap = null; reviewIdx = -1; $('reviewbar').style.display = 'none';
  }
  clearTimers();
  pushHistory();          // stash the question we're leaving for later review
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
  if (nxt == null) return;
  shardFor(CAT.tossups.set[nxt]).catch(() => {});
  if (audioMode()) prefetchAudio(CAT.tossups.id[nxt]);   // warm next audio while this one plays
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
  cur = { q, units, skipWords, startSent, sents, slow: slowSpans(units.map(u => u.t)), showSkipped: false, prompted: false, userRaw: null,
    firstBuzzAt: null, negged: false, lateCorrect: false,
    voice: settings.voice && voiceAvailable() };
  wordIdx = 0; buzzAt = null;
  $('m-set').textContent = q.setName;
  $('m-diff').textContent = 'diff ' + q.d;
  $('m-cat').textContent = q.cat + (q.sub && q.sub !== q.cat ? ' · ' + q.sub : '')
    + (q.subsub ? ' · ' + q.subsub : '');
  phase = 'reading';
  renderQText();
  setStatus('reading', cur.voice ? 'Reading aloud' : 'Reading');
  updateButtons();
  if (cur.voice) playAudio(); else scheduleStep();
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
  const res = cur.negged ? 'W' : 'D';   // an unrecovered multibuzz neg is still a neg
  cur.res = res;
  record(res);
  phase = 'done';
  setStatus('dead', cur.negged ? 'Dead — neg recorded' : 'Dead — no buzz');
  showJudge(cur.negged ? 'W' : null);
  updateButtons();
}

function renderQText() {
  if (!cur) return;
  const el = $('qtext');
  // Voice mode hides the text until the question resolves — hearing it and
  // reading it at once would defeat the point.
  if (cur.voice && phase !== 'done') {
    el.innerHTML = '<div class="empty">&#128266; Reading aloud &mdash; the text appears when the question is over.</div>';
    return;
  }
  let html = '';
  const skiptoggleHtml = () => {
    const n = cur.startSent;
    return '<button class="skiptoggle" id="skiptoggle">'
      + (cur.showSkipped ? '▾ hide the ' : '▸ ') + n + ' earlier sentence' + (n > 1 ? 's' : '')
      + (cur.showSkipped ? '' : ' hidden — show') + '</button><br>';
  };
  if (phase === 'done') {
    // Question over (also every review screen — those render with phase
    // 'done'): each sentence becomes a clue-lookup tap target. Sentence
    // indices match the corpus search index (same splitter both sides).
    const clueBody = t => esc(t).replace(/\(\*\)/g, '<span class="powermark">(*)</span>');
    if (cur.startSent > 0) {
      html += skiptoggleHtml();
      if (cur.showSkipped) html += '<span class="skipped">'
        + cur.sents.slice(0, cur.startSent).map((s, i) =>
          '<span class="clue-s" data-si="' + i + '" title="tap to look up this clue">'
          + clueBody(s) + '</span>').join(' ')
        + '</span> ';
    }
    // Buzz position as a char offset into the read text — the units
    // reconstruct it exactly, so the mark lands mid-sentence where it fell.
    let buzzChar = null;
    if (buzzAt != null) {
      let s = '';
      for (let i = 0; i < buzzAt; i++) s += (i ? cur.units[i].sep : '') + cur.units[i].t;
      buzzChar = s.length;
    }
    if (buzzAt === 0) html += '<span class="buzzmark">●</span> ';
    let off = 0;
    cur.sents.slice(cur.startSent).forEach((sent, j) => {
      const start = off, end = off + sent.length;
      let body;
      if (buzzChar != null && buzzChar > start && buzzChar <= end) {
        body = clueBody(sent.slice(0, buzzChar - start))
          + ' <span class="buzzmark">●</span>' + clueBody(sent.slice(buzzChar - start));
      } else body = clueBody(sent);
      html += (j ? ' ' : '') + '<span class="clue-s" data-si="' + (cur.startSent + j)
        + '" title="tap to look up this clue">' + body + '</span>';
      off = end + 1;
    });
    el.innerHTML = html;
    return;
  }
  if (cur.startSent > 0) {
    html += skiptoggleHtml();
    if (cur.showSkipped) html += '<span class="skipped">' + esc(cur.sents.slice(0, cur.startSent).join(' ')) + '</span> ';
  }
  const U = cur.units;
  const upto = wordIdx;
  const mark = t => t === '(*)' ? '<span class="powermark">(*)</span>' : esc(t);
  let readHtml = buzzAt === 0 ? '<span class="buzzmark">●</span> ' : '';
  for (let i = 0; i < upto; i++) {
    readHtml += (i ? U[i].sep : '') + mark(U[i].t);
    if (buzzAt != null && i === buzzAt - 1) readHtml += ' <span class="buzzmark">●</span>';
  }
  html += readHtml;
  el.innerHTML = html;
}

// Timers only — buzz() uses this so a multibuzz resume can continue the
// audio from the buzz point instead of restarting a torn-down element.
function clearTicks() {
  if (tick) { clearTimeout(tick); tick = null; }
  if (graceTimer) { clearTimeout(graceTimer); graceTimer = null; }
  if (graceAnim) { clearInterval(graceAnim); graceAnim = null; }
}
function clearTimers() {
  clearTicks();
  stopAudio();
}

/* ---------- voice reading (pre-generated Chatterbox audio) ----------
   When "Read aloud" is on, the question plays from a pre-generated Opus file
   on the audio host instead of being shown — the text stays hidden until the
   question resolves (guard in renderQText), like a moderator reading to you.
   The queue is RESTRICTED to questions that have audio (audioMode gate in
   rowInScope), so a question that plays always has a file. Buzz depth comes
   straight from the audio clock (currentTime/duration -> reveal-unit index),
   so buzz depth, power, and stats keep working. The <audio> element's native
   pause/resume is reliable (unlike Web Speech), so pause just pauses. */
const AUDIO_BASE = 'https://huggingface.co/datasets/uild42/qb-audio/resolve/main';
let AUDIO_HAVE = null;      // Set of qids with audio (from audio_index.json); null = not loaded
let audioLoad = null;       // in-flight manifest load promise
const audioEl = typeof Audio !== 'undefined' ? new Audio() : null;
if (audioEl) audioEl.preload = 'auto';
// Prefetched next-question audio as object URLs (qid -> blobURL, or null while
// in flight). Each opus is ~130 KB; prefetching the next question during the
// current one's ~40 s of playback hides HF's ~0.5 s resolve→CDN latency, so
// every question after the first starts instantly. LRU-evicted + revoked.
const audioCache = new Map();
const AUDIO_CACHE_MAX = 6;

function voiceAvailable() { return !!audioEl; }
function hasAudio(qid) { return !!(AUDIO_HAVE && AUDIO_HAVE.has(qid)); }
// Audio mode is only "active" (queue-filtering) once the manifest has loaded;
// until then we don't want to filter the whole queue down to nothing.
function audioMode() { return !!(settings.voice && AUDIO_HAVE); }

// Load the manifest of audio-backed qids once (cached). Fetched from the audio
// host, not the R2 data plane. Idempotent; returns the in-flight promise.
function loadAudioIndex() {
  if (AUDIO_HAVE) return Promise.resolve(AUDIO_HAVE);
  if (audioLoad) return audioLoad;
  audioLoad = fetch(AUDIO_BASE + '/audio_index.json', { cache: 'no-cache' })
    .then(r => { if (!r.ok) throw new Error('HTTP ' + r.status); return r.json(); })
    .then(idx => { AUDIO_HAVE = new Set(idx.tossups || []); return AUDIO_HAVE; })
    .catch(err => { audioLoad = null; throw err; });
  return audioLoad;
}

function voiceRate() { return Math.min(2, Math.max(0.5, settings.vrate || 0.95)); }
// Shard = LAST two hex chars of the qid (ObjectId counter, uniform) — the
// timestamp prefix put every qid in one folder and hit HF's 10k/dir cap.
function audioUrl(qid) { return AUDIO_BASE + '/tossups/' + qid.slice(-2) + '/' + qid + '.opus'; }

// Warm the next question's audio into an object URL so its playback is
// instant. Dedupes in-flight, tolerates failure (falls back to network URL).
function prefetchAudio(qid) {
  if (!qid || !hasAudio(qid) || audioCache.has(qid)) return;
  audioCache.set(qid, null);   // in-flight marker (also dedupes)
  fetch(audioUrl(qid)).then(r => r.ok ? r.blob() : Promise.reject())
    .then(blob => {
      audioCache.set(qid, URL.createObjectURL(blob));
      while (audioCache.size > AUDIO_CACHE_MAX) {
        const k = audioCache.keys().next().value;
        const u = audioCache.get(k); if (typeof u === 'string') URL.revokeObjectURL(u);
        audioCache.delete(k);
      }
    })
    .catch(() => audioCache.delete(qid));
}
// The already-prefetched blob URL if ready, else the network URL.
function audioSrcFor(qid) {
  const c = audioCache.get(qid);
  return typeof c === 'string' ? c : audioUrl(qid);
}

function stopAudio() {
  if (!audioEl) return;
  audioEl.onended = audioEl.ontimeupdate = audioEl.onerror = null;
  try { audioEl.pause(); } catch (e) {}
  audioEl.removeAttribute('src');
  try { audioEl.load(); } catch (e) {}
}

// Map the audio clock to a reveal-unit index so buzz depth/power/stats work.
function audioWordIdx() {
  const d = audioEl.duration;
  if (!d || !isFinite(d)) return wordIdx;
  return Math.min(cur.units.length, Math.round(audioEl.currentTime / d * cur.units.length));
}

function playAudio() {
  stopAudio();
  audioEl.src = audioSrcFor(cur.q.id);
  audioEl.playbackRate = voiceRate();
  try { audioEl.preservesPitch = true; } catch (e) {}
  const degrade = () => {   // file missing/failed/blocked: fall back to text reveal
    if (phase === 'reading' && cur && cur.voice) { cur.voice = false; renderQText(); scheduleStep(); }
  };
  audioEl.ontimeupdate = () => {
    if (phase !== 'reading') return;
    wordIdx = audioWordIdx();
    const d = audioEl.duration;
    if (d && isFinite(d)) $('timerfill').style.width = Math.min(100, audioEl.currentTime / d * 100) + '%';
  };
  audioEl.onended = () => {
    if (phase !== 'reading') return;
    wordIdx = cur.units.length; $('timerfill').style.width = '0%'; startGrace();
  };
  audioEl.onerror = degrade;
  audioEl.play().catch(degrade);
}

// Turn on audio mode: load the audio manifest, then rebuild the queue with
// the audio restriction applied. On failure, revert the toggle cleanly.
function enterAudioMode() {
  loadAudioIndex().then(() => { onFilter(); }).catch(() => {
    settings.voice = false;
    if ($('voice')) $('voice').checked = false;
    $('voicerow').style.display = 'none';
    savePrefs();
    onFilter();
    alert('Could not load the audio index — read-aloud is unavailable right now.');
  });
}

/* ---------- buzz + judge ---------- */
function buzz() {
  if (phase !== 'reading' && phase !== 'paused') return;
  if (cur.voice && audioEl && audioEl.src) wordIdx = audioWordIdx();
  // Pause, don't tear down — a multibuzz neg resumes from here. Finalization
  // (judged/goDead/skip/loadNext) does the teardown.
  clearTicks();
  if (cur.voice && audioEl) { try { audioEl.pause(); } catch (e) {} }
  buzzAt = wordIdx;
  if (cur.firstBuzzAt == null) cur.firstBuzzAt = wordIdx;   // stats credit the first buzz
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
  $('answerrow').classList.remove('show');
  const { directive, directedPrompt } = qbCheckAnswer(cur.q.a || cur.q.as || '', raw);
  if (directive === 'accept') { judged('C', raw); return; }
  // qbreader-style prompting: re-prompt as long as the checker says prompt,
  // relaying the answerline's directed-prompt text when it has one. An empty
  // resubmission concedes (reject -> wrong).
  if (directive === 'prompt') {
    cur.prompted = true;
    const hint = directedPrompt ? 'Prompt: ' + directedPrompt : 'Prompt — be more specific';
    setStatus('buzzed', hint);
    $('verdict').className = 'verdict p';
    $('verdict').textContent = '“' + raw + '” — ' + (directedPrompt ? 'prompt: ' + directedPrompt : 'prompt.') + ' Try again:';
    $('judge').classList.add('show');
    $('answerline').innerHTML = '';
    $('selfgrade').style.display = 'none';
    $('answerrow').classList.add('show');
    $('answerinput').value = ''; $('answerinput').focus();
    return;
  }
  if (settings.multibuzz) { negContinue(raw); return; }
  judged('W', raw);
}

// Multibuzz: a wrong answer doesn't end the question — note the neg (no
// answerline reveal), then resume reading from the buzz point so the player
// can buzz again until correct or dead.
function negContinue(raw) {
  cur.negged = true;
  cur.userRaw = raw;
  $('judge').classList.remove('show');   // the prompt loop may have opened it
  setStatus('done-w', 'No — keep listening');
  // A short beat before reading resumes; phase stays 'buzzed' so Space/tap
  // are inert, and Skip's clearTimers() cancels the beat via tick.
  tick = setTimeout(resumeAfterNeg, 700);
}
function resumeAfterNeg() {
  tick = null;
  phase = 'reading';
  setStatus('reading', cur.voice ? 'Reading aloud' : 'Reading');
  renderQText();
  updateButtons();
  // A played-out audio element restarts from the top on play() — route the
  // ended case (buzz during the grace window) to a fresh grace instead.
  if (cur.voice && audioEl && audioEl.src && !audioEl.ended) audioEl.play().catch(() => {});
  else if (wordIdx >= cur.units.length) startGrace();
  else scheduleStep();
}

// auto-verdict, then let the reader override it (checking isn't perfect)
function judged(res, raw) {
  stopAudio();
  phase = 'done';
  cur.userRaw = raw;
  cur.lateCorrect = res === 'C' && cur.negged;
  const finalRes = cur.lateCorrect ? 'W' : res;   // a neg counts even if recovered
  cur.res = finalRes;
  record(finalRes);
  renderVerdict(finalRes);
  showJudge(finalRes);
  updateButtons();
}
function regrade(newRes) {
  const last = LOG[LOG.length - 1];
  if (last && last.res !== newRes) {
    last.res = newRes;
    last.pow = newRes === 'C' && poweredBuzz();
    saveLog();
  }
  if (cur) cur.res = newRes;
  renderVerdict(newRes);
  showJudge(newRes);
}

/* ---------- previous-question review ----------
   Step back through recently seen questions ('k' or the Prev button) to
   re-read them fully with answer + wiki, without touching the queue or your
   stats. Return with 'j' or "Return to current". Entry is only allowed once
   the live question is finished (done/idle), so restoring the live view is a
   plain re-render. */
const HISTORY_MAX = 50;
function reviewing() { return reviewIdx >= 0; }
function pushHistory() {
  if (!cur) return;
  history.push({ snap: cur, buzzAt, res: cur.res != null ? cur.res : null });
  if (history.length > HISTORY_MAX) history.shift();
}
function openPrev() {
  if (reviewing()) { if (reviewIdx > 0) { reviewIdx--; showReviewAt(); } return; }
  if (!history.length || !(phase === 'done' || phase === 'idle')) return;
  clearTimers();
  liveSnap = { cur, buzzAt, wordIdx, phase };
  reviewIdx = history.length - 1;
  showReviewAt();
}
function reviewForward() {
  if (!reviewing()) return;
  if (reviewIdx < history.length - 1) { reviewIdx++; showReviewAt(); }
  else exitReview();
}
/* ---------- clue lookup (semantic search over the whole corpus) ----------
   Tap a sentence on a finished or reviewed question -> POST /search on the
   sync Worker (session-gated; embeds the sentence with the same model the
   corpus index used) -> resolve the returned (id, kind, sentence/part,
   set) rows to text via the published sets/{slug}.json shards. Sentence
   indices line up because splitSentences here and split_sentences in the
   pipeline are ports of each other. */
const CLUE_TOPN = 8;
const clueSetCache = new Map(); // set slug -> {tossups: Map, bonuses: Map}

function clueSetFor(slug) {
  if (clueSetCache.has(slug)) return Promise.resolve(clueSetCache.get(slug));
  return qdataFetch('sets/' + slug + '.json').then(shard => {
    const t = new Map(), b = new Map();
    for (const pk of shard.packets) {
      for (const tu of pk.tossups || []) t.set(tu._id, tu);
      for (const bn of pk.bonuses || []) b.set(bn._id, bn);
    }
    const entry = { tossups: t, bonuses: b };
    clueSetCache.set(slug, entry);
    return entry;
  });
}

function closeCluePanel() { $('cluepanel').classList.remove('show'); }

function openCluePanel(si) {
  if (!cur || !cur.sents[si]) return;
  const sent = cur.sents[si];
  $('cluepanel').classList.add('show');
  $('cluequery').textContent = sent;
  const hook = window.losReaderHook;
  const auth = hook.searchAuth && hook.searchAuth();
  if (!hook.searchBase || !auth) {
    $('cluebody').innerHTML = '<div class="cluenote">Clue lookup runs on the '
      + 'sync backend &mdash; sign in from the Sync panel to use it.</div>';
    return;
  }
  $('cluebody').innerHTML = '<div class="cluenote">Searching the corpus&hellip;</div>';
  fetch(hook.searchBase + '/search', {
    method: 'POST',
    headers: Object.assign({ 'Content-Type': 'application/json' }, auth),
    body: JSON.stringify({ q: sent }),
  }).then(r => { if (!r.ok) throw new Error('HTTP ' + r.status); return r.json(); })
    .then(res => renderClueResults(res.results || []))
    .catch(e => {
      $('cluebody').innerHTML = '<div class="cluenote">Lookup failed ('
        + esc(String(e.message || e)) + ').</div>';
    });
}

function renderClueResults(results) {
  const mine = cur ? cur.q.id : null;
  const picks = results.filter(r => r.id !== mine && r.set).slice(0, CLUE_TOPN);
  if (!picks.length) {
    $('cluebody').innerHTML = '<div class="cluenote">No similar clues found.</div>';
    return;
  }
  Promise.all(picks.map(r => clueSetFor(r.set).then(shard => {
    if (r.kind === 0) {
      const doc = shard.tossups.get(r.id);
      if (!doc) return null;
      const sents = splitSentences(doc.question_sanitized || doc.question || '');
      return { r, text: sents[r.s] || '', ans: doc.answer_sanitized || doc.answer || '',
               pos: 'clue ' + (r.s + 1) + '/' + sents.length };
    }
    const doc = shard.bonuses.get(r.id);
    if (!doc) return null;
    const leadin = r.s === 255;
    return {
      r,
      text: leadin ? (doc.leadin_sanitized || doc.leadin || '')
                   : ((doc.parts_sanitized || doc.parts || [])[r.s] || ''),
      ans: leadin ? '' : ((doc.answers_sanitized || doc.answers || [])[r.s] || ''),
      pos: leadin ? 'bonus leadin' : 'bonus part',
    };
  }).catch(() => null))).then(rows => {
    const seen = new Set();
    let html = '';
    for (const row of rows) {
      if (!row || !row.text) continue;
      const key = row.text.slice(0, 80);
      if (seen.has(key)) continue; // same question recycled across sets
      seen.add(key);
      const slug = ID2SLUG ? ID2SLUG.get(row.r.id) : null;
      const ansHead = (row.ans || '').split('[')[0].split('(')[0].trim();
      html += '<div class="clueitem">'
        + '<div class="clueans">' + esc(ansHead || '—')
        + (slug ? ' <a href="output/' + slug + '/stock.html" target="_blank" rel="noopener">wiki ↗</a>' : '')
        + '<span class="cluepos">' + esc(row.pos) + '</span></div>'
        + '<div class="cluetext">' + esc(row.text) + '</div>'
        + '</div>';
    }
    $('cluebody').innerHTML = html || '<div class="cluenote">No similar clues found.</div>';
  });
}

function exitReview() {
  if (!reviewing()) return;
  const s = liveSnap; liveSnap = null; reviewIdx = -1;
  cur = s.cur; buzzAt = s.buzzAt; wordIdx = s.wordIdx; phase = s.phase;
  $('reviewbar').style.display = 'none';
  if (!cur) {
    $('qtext').innerHTML = '<div class="empty">' + queueSize().toLocaleString()
      + ' questions in scope. Press <b>Start</b> (or tap here).</div>';
    $('judge').classList.remove('show'); $('wikibox').classList.remove('show');
  } else {
    renderQText();
    if (phase === 'done') showJudge(cur.res != null ? cur.res : null);
  }
  updateButtons();
}
function showReviewAt() {
  const h = history[reviewIdx];
  cur = h.snap; buzzAt = h.buzzAt; wordIdx = cur.units.length; phase = 'done';
  $('answerrow').classList.remove('show');
  renderQText();
  showJudge(h.res);   // verdict + answerline + wiki (selfgrade suppressed in review)
  if (h.res) renderVerdict(h.res); else setStatus('', 'Reviewing');
  renderReviewBar();
  updateButtons();
}
function renderReviewBar() {
  const bar = $('reviewbar');
  const back = history.length - reviewIdx;   // 1 = most recent
  bar.style.display = '';
  bar.innerHTML = '<span class="rlbl">Reviewing</span> ' + back + ' question' + (back > 1 ? 's' : '') + ' back'
    + '<span class="rspacer"></span>'
    + '<button id="rv-older"' + (reviewIdx === 0 ? ' disabled' : '') + '>&#9664; Older</button>'
    + '<button id="rv-newer">Newer &#9654;</button>'
    + '<button id="rv-return">Return to current</button>';
  $('rv-older').onclick = openPrev;
  $('rv-newer').onclick = reviewForward;
  $('rv-return').onclick = exitReview;
}
function renderVerdict(res) {
  const pct = buzzPct();   // last buzz — what the player just did
  const word = res === 'C' ? (poweredBuzz() ? 'Power!' : 'Correct')
    : (res === 'W' && cur.lateCorrect) ? 'Correct, but negged' : 'Wrong';
  setStatus(res === 'C' ? 'done-c' : 'done-w', word + (pct != null ? ' · ' + pct + '%' : ''));
}
function buzzPct() {
  if (buzzAt == null) return null;
  const total = cur.skipWords + cur.units.length;
  return Math.round((cur.skipWords + buzzAt) / total * 100);
}
function poweredBuzz() {
  const pi = cur.units.findIndex(u => u.t === '(*)');
  const at = cur.firstBuzzAt != null ? cur.firstBuzzAt : buzzAt;   // power = first buzz
  return pi >= 0 && at != null && at <= pi;
}
function showJudge(res) {
  renderQText();
  $('judge').classList.add('show');
  const overridable = res === 'C' || res === 'W';   // you actually answered
  const said = cur.userRaw != null && cur.userRaw !== ''
    ? ' <span style="color:var(--faint)">— you said “' + esc(cur.userRaw) + '”</span>' : '';
  if (res === 'C') { $('verdict').className = 'verdict c'; $('verdict').innerHTML = (poweredBuzz() ? 'Correct — in power' : 'Correct') + said; }
  else if (res === 'W' && cur.lateCorrect) { $('verdict').className = 'verdict w'; $('verdict').innerHTML = 'Got it in the end &mdash; but your first buzz was wrong, so it counts as a neg' + said; }
  else if (res === 'W') { $('verdict').className = 'verdict w'; $('verdict').innerHTML = 'Incorrect' + said; }
  else { $('verdict').className = 'verdict'; $('verdict').textContent = 'No buzz — the answer was:'; }
  $('answerline').innerHTML = answerHTML(cur.q.a);
  // override row — the auto-check is a suggestion; let the reader correct it
  // (but not while reviewing a past question — that would regrade the wrong
  // log entry)
  const sg = $('selfgrade');
  sg.style.display = (overridable && reviewIdx < 0) ? 'flex' : 'none';
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
   buzz; celerity = mean(1-bf) over correct buzzes. Exactly one row per
   question even in multibuzz mode: res is 'W' if ANY buzz was wrong, and
   bf/pow are taken from the FIRST buzz. */
function record(res) {
  const total = cur.skipWords + cur.units.length;
  const fb = cur.firstBuzzAt != null ? cur.firstBuzzAt : buzzAt;
  const bf = fb == null ? null : (cur.skipWords + fb) / total;
  const q = cur.q;
  LOG.push({
    id: q.id, t: q.slug || null, ans: answerKey(q.a, q.as) || null,
    aDisp: (q.as || '').split('[')[0].split('(')[0].trim() || q.as || '',
    cat: q.cat, sub: q.sub, section: q.section || null, diff: q.d,
    res, bf: bf == null ? null : Math.round(bf * 1000) / 1000,
    pow: res === 'C' && poweredBuzz(), sent: settings.sent, ts: Date.now(),
  });
  saveLog();
  if (window.losReaderHook.onRecord) try { window.losReaderHook.onRecord(); } catch (e) {}
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
  return '<div class="tablewrap">' + h + '</table></div>';
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

/* ---------- history view: searchable log of played questions ----------
   Every attempt in LOG, newest first, filtered by a free-text query over
   the answer, taxonomy, and set name. A row expands to the full question
   text + answerline, resolved lazily from the set shard (same path the
   reader itself uses), with a wiki link when the answer has a page. */
const HIST_PAGE = 50;
let histShown = HIST_PAGE;
function histSetName(id) {
  const r = ID2ROW.get(id);
  return r != null ? CAT.sets[CAT.tossups.set[r]].name : '';
}
function histMatches() {
  const toks = $('histq').value.trim().toLowerCase().split(/\s+/).filter(Boolean);
  const out = [];
  for (let i = LOG.length - 1; i >= 0; i--) {
    const rec = LOG[i];
    if (toks.length) {
      const hay = [rec.aDisp, rec.ans, rec.cat, rec.sub, rec.section, histSetName(rec.id)]
        .filter(Boolean).join(' ').toLowerCase();
      if (!toks.every(t => hay.includes(t))) continue;
    }
    out.push(rec);
  }
  return out;
}
function renderHistory() {
  if (!CAT) { $('histlist').innerHTML = '<div class="empty">Loading&hellip;</div>'; return; }
  if (!LOG.length) {
    $('histnote').textContent = '';
    $('histlist').innerHTML = '<div class="empty">No history yet — play a few questions first.</div>';
    return;
  }
  const m = histMatches();
  const searching = !!$('histq').value.trim();
  $('histnote').textContent = (searching ? m.length + ' of ' + LOG.length + ' played questions match'
    : LOG.length + ' played questions') + ', newest first — click one to re-read it.';
  const RES = { C: ['c', 'Correct'], W: ['w', 'Neg'], D: ['d', 'Dead'] };
  let h = '';
  for (const rec of m.slice(0, histShown)) {
    const [cls, word] = RES[rec.res] || ['', rec.res || '?'];
    const depth = rec.bf != null ? ' · ' + Math.round(rec.bf * 100) + '%' : '';
    const when = rec.ts > 1e12 ? new Date(rec.ts).toLocaleDateString() : '';
    const meta = [rec.cat, rec.sub !== rec.cat ? rec.sub : null, when].filter(Boolean).join(' · ');
    h += '<div class="histrow" data-id="' + esc(rec.id) + '">'
      + '<div class="histhead"><span class="hist-ans">' + esc(rec.aDisp || rec.ans || '—') + '</span>'
      + '<span class="hist-meta">' + esc(meta) + '</span>'
      + '<span class="hist-res ' + cls + '">' + word + (rec.pow ? ' · power' : '') + depth + '</span></div>'
      + '<div class="histbody"></div></div>';
  }
  if (m.length > histShown)
    h += '<button class="btn" id="histmore">Show ' + Math.min(HIST_PAGE, m.length - histShown) + ' more</button>';
  $('histlist').innerHTML = h || '<div class="empty">Nothing matches.</div>';
  const more = $('histmore');
  if (more) more.onclick = () => { histShown += HIST_PAGE; renderHistory(); };
}
function histExpand(row) {
  const body = row.querySelector('.histbody');
  if (body.classList.contains('show')) { body.classList.remove('show'); return; }
  body.classList.add('show');
  if (body.dataset.loaded) return;
  body.dataset.loaded = '1';
  const id = row.dataset.id;
  const r = ID2ROW.get(id);
  if (r == null) {
    body.innerHTML = '<div class="statnote" style="margin:0">This question is no longer in the published catalog.</div>';
    return;
  }
  body.innerHTML = '<div class="statnote" style="margin:0">Loading&hellip;</div>';
  shardFor(CAT.tossups.set[r]).then(docs => {
    const doc = docs.get(id);
    if (!doc) { body.innerHTML = '<div class="statnote" style="margin:0">Question text unavailable.</div>'; return; }
    const slug = ID2SLUG.get(id);
    body.innerHTML = '<div class="qfull">' + esc(doc.question_sanitized || doc.question || '') + '</div>'
      + '<div class="answerline">' + answerHTML(doc.answer || doc.answer_sanitized || '') + '</div>'
      + (slug ? '<div style="margin-top:0.4rem"><a href="output/' + esc(slug) + '/stock.html">wiki page ↗</a></div>' : '');
  }).catch(() => {
    body.dataset.loaded = '';
    body.innerHTML = '<div class="statnote" style="margin:0">Couldn&rsquo;t load the question — try again.</div>';
  });
}

/* ---------- preferences: reading settings + scope, persisted ----------
   So a refresh keeps what you just set (speed, trim, drill/focus, and the
   category/subcategory/subtype/group/difficulty scope). Sections persist as
   [unit, name] pairs, not catalog ids, so they survive a republish that
   reorders section_values. */
const PREFS = 'losReaderPrefsV1';
const focusLabel = v => v < 33 ? 'broad review' : v < 67 ? 'balanced' : 'targeted';
function savePrefs() {
  try {
    const sections = [...filters.sections].map(id =>
      id === -1 ? [-1] : (CAT && CAT.section_values[id]) || null).filter(Boolean);
    localStorage.setItem(PREFS, JSON.stringify({
      wpm: settings.wpm, sent: settings.sent, drill: settings.drill, focus: settings.focus,
      dist: settings.dist, useDist: settings.useDist,
      voice: settings.voice, vrate: settings.vrate, multibuzz: settings.multibuzz,
      cats: [...filters.cats], subs: [...filters.subs], subsubs: [...filters.subsubs],
      diffs: [...filters.diffs], sections,
      up: Date.now(),   // last-write-wins stamp for cross-device sync
    }));
  } catch (e) {}
}
function loadPrefs() {
  let p; try { p = JSON.parse(localStorage.getItem(PREFS) || 'null'); } catch (e) {}
  if (!p) return;
  if (typeof p.wpm === 'number') settings.wpm = p.wpm;
  if (typeof p.sent === 'number') settings.sent = p.sent;
  if (typeof p.drill === 'boolean') settings.drill = p.drill;
  if (typeof p.focus === 'number') settings.focus = p.focus;
  if (p.dist && typeof p.dist === 'object') settings.dist = { ...DEFAULT_DIST, ...p.dist };
  if (typeof p.useDist === 'boolean') settings.useDist = p.useDist;
  if (typeof p.voice === 'boolean') settings.voice = p.voice;
  if (typeof p.vrate === 'number') settings.vrate = p.vrate;
  if (typeof p.multibuzz === 'boolean') settings.multibuzz = p.multibuzz;
  const setFrom = (set, arr) => { set.clear(); for (const v of (arr || [])) set.add(v); };
  setFrom(filters.cats, p.cats); setFrom(filters.subs, p.subs);
  setFrom(filters.subsubs, p.subsubs); setFrom(filters.diffs, p.diffs);
  filters.sections.clear();
  const SV = CAT.section_values || [];
  for (const pair of (p.sections || [])) {
    if (pair[0] === -1) { filters.sections.add(-1); continue; }
    const idx = SV.findIndex(s => s && s[0] === pair[0] && s[1] === pair[1]);
    if (idx >= 0) filters.sections.add(idx);
  }
}
// Sentences-read control: the Full button is "on" at sent=0, otherwise the
// manual last-n number field carries the value.
function syncSentUI() {
  $('sentmode').querySelector('button').classList.toggle('on', settings.sent === 0);
  const inp = $('sentn');
  inp.value = settings.sent > 0 ? settings.sent : '';
  inp.classList.toggle('on', settings.sent > 0);
}
// Push restored settings into the reading-panel controls (the filter chips
// re-render from state via renderFilters).
function syncControls() {
  $('wpm').value = settings.wpm;
  $('wpmval').textContent = settings.wpm;
  syncSentUI();
  $('voice').checked = settings.voice;
  $('voicerow').style.display = settings.voice ? '' : 'none';
  $('vrate').value = settings.vrate;
  $('vrateval').textContent = settings.vrate.toFixed(2) + 'x';
  $('multibuzz').checked = settings.multibuzz;
  $('multibuzzrow').style.display = settings.multibuzz ? '' : 'none';
  $('drill').checked = settings.drill;
  $('drillrow').style.display = settings.drill ? '' : 'none';
  $('focus').value = settings.focus;
  $('focusval').textContent = focusLabel(settings.focus);
  $('usedist').checked = settings.useDist;
  renderDistEditor();
}
// Per-category weight editor for the sampling distribution.
function renderDistEditor() {
  const grid = $('distgrid'); if (!grid) return;
  grid.innerHTML = '';
  for (const c of Object.keys(DEFAULT_DIST)) {
    const lab = document.createElement('label'); lab.textContent = c;
    const inp = document.createElement('input');
    inp.type = 'number'; inp.min = '0'; inp.step = '0.5';
    inp.value = settings.dist[c] != null ? settings.dist[c] : 0;
    inp.disabled = !settings.useDist;
    inp.onchange = () => {
      let v = parseFloat(inp.value); if (!(v >= 0)) v = 0;
      settings.dist[c] = v; inp.value = v;
      savePrefs(); if (!settings.drill) rebuildQueue();
    };
    grid.appendChild(lab); grid.appendChild(inp);
  }
}

/* ---------- controls ---------- */
function updateButtons() {
  const main = $('mainbtn');
  if (reviewing()) { main.textContent = 'Return to current'; main.disabled = false; }
  else if (phase === 'idle') { main.textContent = 'Start'; main.disabled = false; }
  else if (phase === 'loading') { main.textContent = 'Loading…'; main.disabled = true; }
  else if (phase === 'reading' || phase === 'paused') { main.textContent = 'Buzz'; main.disabled = false; }
  else if (phase === 'buzzed' || phase === 'selfgrade') { main.textContent = 'Buzz'; main.disabled = true; }
  else { main.textContent = 'Next question'; main.disabled = false; }
  $('pausebtn').disabled = reviewing() || !(phase === 'reading' || phase === 'paused');
  $('pausebtn').textContent = phase === 'paused' ? 'Resume' : 'Pause';
  $('skipbtn').disabled = reviewing() || !(phase === 'reading' || phase === 'paused' || phase === 'buzzed' || phase === 'selfgrade');
  // Prev enables once there's history and the live question is finished (or
  // while already reviewing, to step further back).
  const prev = $('prevbtn');
  if (prev) prev.disabled = !(history.length && (reviewing() || phase === 'done' || phase === 'idle'));
  syncMobileBar();
}

function wireUp() {
  $('mainbtn').onclick = () => {
    if (reviewing()) { exitReview(); return; }
    if (phase === 'idle' || phase === 'done') loadNext();
    else if (phase === 'reading' || phase === 'paused') buzz();
  };
  $('prevbtn').onclick = openPrev;
  $('pausebtn').onclick = () => {
    if (phase === 'reading') {
      // Audio pauses natively (reliable) — don't tear down the element via
      // clearTimers; just pause it. Text mode stops its reveal timer.
      if (cur.voice && audioEl) { audioEl.pause(); wordIdx = audioWordIdx(); }
      else clearTimers();
      phase = 'paused'; setStatus('reading', 'Paused');
    } else if (phase === 'paused') {
      phase = 'reading'; setStatus('reading', cur.voice ? 'Reading aloud' : 'Reading');
      if (wordIdx >= cur.units.length) startGrace();
      else if (cur.voice && audioEl) audioEl.play().catch(() => {});   // native resume
      else scheduleStep();
    }
    updateButtons();
  };
  $('skipbtn').onclick = () => { // throw the question away — nothing recorded,
    // except a multibuzz neg already made: skipping must not erase it
    if (phase === 'reading' || phase === 'paused' || phase === 'buzzed' || phase === 'selfgrade') {
      if (cur && cur.negged && cur.res == null) { cur.res = 'W'; record('W'); }
      clearTimers(); loadNext();
    }
  };
  $('qtext').addEventListener('click', e => {
    if (cur && e.target.closest('#skiptoggle')) { cur.showSkipped = !cur.showSkipped; renderQText(); return; }
    const cs = cur && phase === 'done' && e.target.closest('.clue-s');
    if (cs) { openCluePanel(Number(cs.dataset.si)); return; }
    if (e.target.closest('a')) return;
    if (window.getSelection && String(window.getSelection())) return;  // selecting text to copy
    // Tap the question to buzz while reading, or to start from the empty
    // state. A finished question is NOT advanced by a tap, so its revealed
    // text stays selectable for copy/paste — use Next / Space / the button.
    if (phase === 'reading' || phase === 'paused') buzz();
    else if (phase === 'idle' && !reviewing()) loadNext();
  });
  $('answerinput').addEventListener('keydown', e => {
    if (e.key === 'Enter') { e.preventDefault(); submitAnswer(); }
    e.stopPropagation();
  });
  $('clueclose').onclick = closeCluePanel;
  $('sg-right').onclick = () => regrade('C');
  $('sg-wrong').onclick = () => regrade('W');

  document.addEventListener('keydown', e => {
    if (e.target.tagName === 'INPUT') return;
    if (e.key === 'k' || e.key === 'K') { e.preventDefault(); openPrev(); return; }
    if (e.key === 'j' || e.key === 'J') { e.preventDefault(); reviewForward(); return; }
    if (reviewing()) {   // in review, Space/N step forward (toward the live question)
      if (e.code === 'Space' || e.key === 'n' || e.key === 'N') { e.preventDefault(); reviewForward(); }
      return;
    }
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
    savePrefs();
  };
  $('sentmode').querySelector('button').onclick = () => {
    settings.sent = 0;
    syncSentUI();
    savePrefs();
  };
  $('sentn').oninput = e => {
    const v = Math.floor(Number(e.target.value));
    settings.sent = Number.isFinite(v) && v > 0 ? Math.min(v, 99) : 0;
    // Don't rewrite the field mid-typing; just reflect the active state.
    $('sentmode').querySelector('button').classList.toggle('on', settings.sent === 0);
    $('sentn').classList.toggle('on', settings.sent > 0);
    savePrefs();
  };
  $('sentn').onblur = syncSentUI;
  // Voice reading — plays pre-generated audio; restricts the queue to
  // questions that have audio. Toggling loads the manifest, then rebuilds.
  if (!voiceAvailable()) {
    $('voicetoggle').style.display = 'none';
    $('voicerow').style.display = 'none';
  } else {
    $('voice').onchange = e => {
      settings.voice = e.target.checked;
      $('voicerow').style.display = settings.voice ? '' : 'none';
      savePrefs();
      if (settings.voice) enterAudioMode(); else { onFilter(); }
    };
    $('vrate').oninput = e => {
      settings.vrate = Number(e.target.value);
      $('vrateval').textContent = settings.vrate.toFixed(2) + 'x';
      if (audioEl) audioEl.playbackRate = voiceRate();   // live, mid-question
      savePrefs();
    };
  }
  // Multibuzz — a wrong answer resumes reading instead of ending the
  // question. Takes effect at the next wrong answer; no queue impact.
  $('multibuzz').onchange = e => {
    settings.multibuzz = e.target.checked;
    $('multibuzzrow').style.display = settings.multibuzz ? '' : 'none';
    savePrefs();
  };
  // Drill mode + focus slider. settings.focus holds the raw 0..100 value;
  // rebuildQueue derives the drive blend and sampling temperature from it
  // (0 -> broad/schedule-driven, 100 -> targeted/hammer-weaknesses).
  $('drill').onchange = e => {
    settings.drill = e.target.checked;
    $('drillrow').style.display = settings.drill ? '' : 'none';
    rebuildQueue();
    savePrefs();
  };
  $('focus').oninput = e => {
    settings.focus = Number(e.target.value);
    $('focusval').textContent = focusLabel(settings.focus);
    if (settings.drill) rebuildQueue();
    savePrefs();
  };
  $('usedist').onchange = e => {
    settings.useDist = e.target.checked;
    renderDistEditor();
    savePrefs();
    if (!settings.drill) rebuildQueue();
  };
  $('distreset').onclick = () => {
    settings.dist = { ...DEFAULT_DIST };
    renderDistEditor();
    savePrefs();
    if (!settings.drill) rebuildQueue();
  };
  $('clearfilters').onclick = () => {
    for (const k of Object.keys(filters)) filters[k].clear();
    onFilter();
  };
  $('tab-play').onclick = () => showView('play');
  $('tab-stats').onclick = () => showView('stats');
  $('tab-history').onclick = () => showView('history');
  $('histq').addEventListener('input', () => { histShown = HIST_PAGE; renderHistory(); });
  $('histq').addEventListener('keydown', e => e.stopPropagation());   // typing must not buzz/skip
  $('histlist').addEventListener('click', e => {
    if (e.target.closest('a')) return;
    const row = e.target.closest('.histrow');
    if (row) histExpand(row);
  });
  initMobile();
}

function showView(v) {
  for (const name of ['play', 'stats', 'history']) {
    $('view-' + name).style.display = name === v ? '' : 'none';
    $('tab-' + name).classList.toggle('on', name === v);
  }
  if (v === 'stats') renderStats();
  if (v === 'history') renderHistory();
}

/* ---------- mobile chrome ----------
 * Everything mobile-specific lives here. The layout mode is the
 * html[data-layout] attribute maintained by the inline head script
 * (theme.layout_switch_script); components come from lib/js/mobile.js
 * (losSheet/losSwipe/losLayout). The rail panels are single DOM nodes that
 * are REPARENTED between the desktop rail and the bottom sheets — never
 * cloned — so ids, listeners, and state travel with them. The bottom
 * action bar's buttons are pure proxies for the desktop buttons; all game
 * logic stays in the handlers above. */

let sheetScope = null, sheetReading = null;

function updateScopeBadge() {
  const b = $('scopebadge'); if (!b) return;
  const n = Object.values(filters).reduce((a, s) => a + s.size, 0);
  b.textContent = n;
  b.style.display = n ? '' : 'none';
}

// Mirror label + disabled state from the desktop controls onto the bottom
// bar. Called from updateButtons(), so the bar can never drift.
function syncMobileBar() {
  const m = $('m-main'); if (!m) return;
  m.textContent = $('mainbtn').textContent;
  m.disabled = $('mainbtn').disabled;
  $('m-pause').textContent = $('pausebtn').textContent;
  $('m-pause').disabled = $('pausebtn').disabled;
  $('m-skip').disabled = $('skipbtn').disabled;
  $('m-prev').disabled = $('prevbtn').disabled;
}

// Move the rail panels (and the timerbar) into the mobile chrome and back.
// appendChild moves the live nodes; the desktop homes (scope in the left
// rail, reading + sync in the right) and the timerbar's place at the end of
// .controls are restored on the way out.
function placePanels(mode) {
  const timerbar = document.querySelector('.timerbar');
  if (mode === 'mobile') {
    $('sheet-scope-body').appendChild($('panel-scope'));
    $('sheet-reading-body').appendChild($('panel-reading'));
    $('sheet-reading-body').appendChild($('syncpanel'));
    $('mbar-timer').appendChild(timerbar);
  } else {
    if (sheetScope) sheetScope.close();
    if (sheetReading) sheetReading.close();
    $('rail').appendChild($('panel-scope'));
    $('rail2').appendChild($('panel-reading'));
    $('rail2').appendChild($('syncpanel'));
    document.querySelector('.controls').appendChild(timerbar);
  }
}

// While the answer input is focused on mobile, ride the bottom bar above
// the on-screen keyboard (visualViewport gives the visible height) and
// center the input. Listeners detach on blur so no stale offsets stick.
function initKbInset() {
  const vv = window.visualViewport; if (!vv) return;
  const input = $('answerinput'), mbar = $('mbar');
  let active = false;
  const onVV = () => {
    if (!active) return;
    mbar.style.bottom = Math.max(0, window.innerHeight - vv.height - vv.offsetTop) + 'px';
  };
  input.addEventListener('focus', () => {
    if (losLayout() !== 'mobile') return;
    active = true;
    vv.addEventListener('resize', onVV);
    vv.addEventListener('scroll', onVV);
    setTimeout(() => {
      onVV();
      input.scrollIntoView({ block: 'center', behavior: 'smooth' });
    }, 300);
  });
  input.addEventListener('blur', () => {
    active = false;
    mbar.style.bottom = '';
    vv.removeEventListener('resize', onVV);
    vv.removeEventListener('scroll', onVV);
  });
}

function initMobile() {
  if (!window.losSheet || !$('mbar')) return;  // mobile.js not loaded
  sheetScope = losSheet($('sheet-scope'));
  sheetReading = losSheet($('sheet-reading'));
  $('open-scope').onclick = () => sheetScope.toggle();
  $('open-reading').onclick = () => sheetReading.toggle();

  // Bottom-bar proxies — route through the real buttons.
  $('m-main').onclick = () => $('mainbtn').click();
  $('m-pause').onclick = () => $('pausebtn').click();
  $('m-skip').onclick = () => $('skipbtn').click();
  $('m-prev').onclick = () => $('prevbtn').click();

  // Swipes on the question card. Left = advance (Next when finished, Skip
  // — uncounted — while live, step forward in review); right = previous.
  // Buzzing stays tap/button-only: a timing-critical action must not wait
  // on gesture disambiguation.
  losSwipe($('qcard'), {
    left: () => {
      if (reviewing()) { reviewForward(); return; }
      if (phase === 'done' || phase === 'idle') loadNext();
      else if (phase === 'reading' || phase === 'paused' || phase === 'buzzed' || phase === 'selfgrade') $('skipbtn').click();
    },
    right: openPrev,
  });

  window.addEventListener('loslayout', e => placePanels(e.detail));
  placePanels(losLayout());
  initKbInset();
  updateScopeBadge();
}

/* ---------- boot ---------- */
wireUp();
$('qtext').innerHTML = '<div class="empty">Loading the question catalog&hellip;</div>';
Promise.all([qdataFetch('catalog.json'), qdataFetch('topics.json')]).then(([cat, top]) => {
  CAT = cat;
  TOPICS = top.topics;
  // Deduped answerline keys for the drill scheduler; normAns is idempotent,
  // so re-normalizing the published (already-normalized) values is a no-op
  // safety net that keeps the JS normalizer authoritative vs LOG entries.
  AKEYS = (CAT.answerline_values || []).map(normAns);
  ID2SLUG = new Map();
  for (const slug in TOPICS) for (const id of (TOPICS[slug].tossups || [])) ID2SLUG.set(id, slug);
  ID2ROW = new Map();
  for (let r = 0; r < CAT.tossups.id.length; r++) ID2ROW.set(CAT.tossups.id[r], r);
  loadPrefs();       // restore reading settings + scope from a prior session
  syncControls();
  // If read-aloud was left on, load the audio manifest before building the
  // queue so the audio restriction applies from the first render.
  const ready = (settings.voice ? loadAudioIndex().catch(() => { settings.voice = false; if ($('voice')) $('voice').checked = false; $('voicerow').style.display = 'none'; }) : Promise.resolve());
  ready.then(() => {
    renderFilters();
    rebuildQueue();
    $('qtext').innerHTML = '<div class="empty">' + queueSize().toLocaleString()
      + ' questions in scope. Press <b>Start</b> (or tap here).</div>';
    phase = 'idle';
    updateButtons();
  });
}).catch(err => {
  $('qtext').innerHTML = qdataErrorHtml(err);
});
})();
