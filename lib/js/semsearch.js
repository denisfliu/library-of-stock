// semsearch.js — the semantic search page (search.html).
//
// Free-text semantic search over every embedded tossup sentence and bonus
// part, with qbreader.org/db's filter set (category bundle, difficulties,
// year range, question type, set name). The page POSTs to /search on the
// sync Worker (session-gated — same GitHub login as reader sync), which
// embeds the query at the edge and scans the R2-hosted IVF-binary index;
// results resolve to question text via the sets/{slug}.json shards
// (lib/js/qdata.js).
//
// The page template (lib/render/build_search.py) defines window.SEM_CFG:
//   { syncBase, cats, subs, alts, catToSubs, catToAlts, diffNames }
// cats/subs/alts are lib/mirror/query.py's canonical ordered lists — the
// SAME order build_search_index.py used, so name->index here IS the
// ordinal contract with the Worker.
(function () {
'use strict';

const CFG = window.SEM_CFG;
const $ = id => document.getElementById(id);
const esc = s => String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
// answerlines may contain only these formatting tags; escape everything else
const ANS_OK = /<\/?(b|u|i|em|strong)>/;
function answerHTML(a) {
  return String(a).split(/(<\/?(?:b|u|i|em|strong)>)/g)
    .map(p => ANS_OK.test(p) ? p : esc(p)).join('');
}

/* ---------- sentence splitting ----------
   Port of lib/pipeline/parse.py split_sentences (same as reader.js) —
   MUST stay in lockstep: the search index keys sentences on these
   boundaries, and result rows carry sentence indices into this split. */
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

/* ---------- category-bundle expansion ----------
   Port of lib/mirror/query.py _expand_category_bundle (itself a port of
   qbreader's category-bundle.js): make the three selections mutually
   consistent — a sub/alt implies its category; a selected category with
   no selected subs (or alts) gets all of them. Returns null when nothing
   is selected (no filtering). */
function expandBundle(selCats, selSubs, selAlts) {
  const cats = selCats.filter(c => CFG.catToSubs[c]);
  const subs = selSubs.filter(s => CFG.subToCat[s]);
  const alts = selAlts.filter(a => CFG.altToCat[a]);
  if (!cats.length && !subs.length && !alts.length) return null;
  for (const s of subs) {
    if (!cats.includes(CFG.subToCat[s])) cats.push(CFG.subToCat[s]);
  }
  for (const a of alts) {
    if (!cats.includes(CFG.altToCat[a])) cats.push(CFG.altToCat[a]);
  }
  for (const c of cats) {
    if (!CFG.catToSubs[c].some(s => subs.includes(s))) {
      subs.push.apply(subs, CFG.catToSubs[c]);
    }
  }
  for (const c of cats) {
    const catAlts = CFG.catToAlts[c] || [];
    if (!catAlts.some(a => alts.includes(a))) {
      alts.push.apply(alts, catAlts);
    }
  }
  return { cats, subs, alts };
}

function bundleOrdinals(bundle) {
  if (!bundle) return null;
  return {
    cats: bundle.cats.map(c => CFG.cats.indexOf(c)).filter(i => i >= 0),
    subs: bundle.subs.map(s => CFG.subs.indexOf(s)).filter(i => i >= 0),
    alts: bundle.alts.map(a => CFG.alts.indexOf(a)).filter(i => i >= 0),
  };
}

/* ---------- session (shared with reader sync) ----------
   The sync token lives in localStorage under the reader's key; signing in
   here goes through the same Worker OAuth flow. Account SWITCHES are the
   reader's ceremony (it owns the local-history merge prompt), so a token
   for a different account than this browser's synced history bounces to
   reader.html with the token hash intact. */
const SYNC_KEY = 'losSyncV1';
const READER_LOG_KEY = 'losReaderStatsV1';

function syncState() {
  try { return JSON.parse(localStorage.getItem(SYNC_KEY) || 'null') || {}; }
  catch (e) { return {}; }
}

function tokenPayload(token) {
  try {
    const body = token.split('.')[0].replace(/-/g, '+').replace(/_/g, '/');
    return JSON.parse(atob(body));
  } catch (e) { return null; }
}

(function captureToken() {
  const m = location.hash.match(/[#&]sync=([^&]+)/);
  if (!m) return;
  const token = m[1];
  const p = tokenPayload(token);
  if (!p || !p.u) { history.replaceState(null, '', location.pathname + location.search); return; }
  const st = syncState();
  let readerLogLen = 0;
  try { readerLogLen = (JSON.parse(localStorage.getItem(READER_LOG_KEY) || '[]') || []).length; }
  catch (e) {}
  if (st.uid && st.uid !== p.u && readerLogLen) {
    // Different account with local history: the reader owns that decision.
    location.href = 'reader.html' + location.hash;
    return;
  }
  history.replaceState(null, '', location.pathname + location.search);
  const next = Object.assign({ cursor: 0, lastSync: 0 }, st,
    { token, uid: p.u, login: p.l || p.u });
  if (st.uid !== p.u) next.cursor = 0;
  try { localStorage.setItem(SYNC_KEY, JSON.stringify(next)); } catch (e) {}
})();

function authHeader() {
  const st = syncState();
  return st.token ? { Authorization: 'Bearer ' + st.token } : null;
}

/* ---------- clue-search engine (lib/js/clue_search.js) ----------
   Routes each query to the Worker (cloud) or the in-browser pipeline
   (local embedding + client-side index scan; no sign-in), per the same
   per-device toggle the reader uses. */
losClueSearch.configure({ syncBase: CFG.syncBase, getAuth: authHeader });

/* ---------- filter UI ---------- */
function chip(label, cls, pressed) {
  return '<button type="button" class="fchip' + (cls ? ' ' + cls : '') + '"'
    + ' aria-pressed="' + (pressed ? 'true' : 'false') + '">' + esc(label) + '</button>';
}

function buildFilterPanel() {
  $('cats').innerHTML = CFG.cats.map(c => chip(c, 'cat', false)).join('');
  $('diffs').innerHTML = CFG.diffNames.map((name, d) =>
    '<button type="button" class="fchip diff" aria-pressed="false" title="'
    + esc(name) + '">' + d + '</button>').join('');
  $('cats').addEventListener('click', onChipToggle);
  $('subs').addEventListener('click', onChipToggle);
  $('alts').addEventListener('click', onChipToggle);
  $('diffs').addEventListener('click', onChipToggle);
}

function onChipToggle(e) {
  const btn = e.target.closest('.fchip');
  if (!btn) return;
  btn.setAttribute('aria-pressed',
    btn.getAttribute('aria-pressed') === 'true' ? 'false' : 'true');
  if (btn.classList.contains('cat')) renderSubPanels();
}

function pressed(containerId, cls) {
  return Array.from($(containerId).querySelectorAll('.fchip[aria-pressed="true"]'))
    .map(b => cls === 'diff' ? Number(b.textContent) : b.textContent);
}

// Sub/alt chips only render for selected categories (qbreader's modal
// behavior); deselecting a category drops its children's pressed state.
function renderSubPanels() {
  const cats = pressed('cats', 'cat');
  const keepSubs = new Set(pressed('subs', 'sub'));
  const keepAlts = new Set(pressed('alts', 'alt'));
  const subs = [], alts = [];
  for (const c of cats) {
    for (const s of CFG.catToSubs[c] || []) if (s !== c) subs.push(s);
    for (const a of CFG.catToAlts[c] || []) alts.push(a);
  }
  $('subrow').style.display = subs.length ? '' : 'none';
  $('altrow').style.display = alts.length ? '' : 'none';
  $('subs').innerHTML = subs.map(s => chip(s, 'sub', keepSubs.has(s))).join('');
  $('alts').innerHTML = alts.map(a => chip(a, 'alt', keepAlts.has(a))).join('');
}

function readFilters() {
  const bundle = expandBundle(pressed('cats', 'cat'), pressed('subs', 'sub'),
                              pressed('alts', 'alt'));
  const ords = bundleOrdinals(bundle);
  const f = {};
  if (ords) { f.cats = ords.cats; f.subs = ords.subs; f.alts = ords.alts; }
  const diffs = pressed('diffs', 'diff');
  if (diffs.length) f.diffs = diffs;
  const qtype = $('qtype').value;
  if (qtype !== 'all') f.qtype = qtype;
  const ymin = parseInt($('ymin').value, 10), ymax = parseInt($('ymax').value, 10);
  if (!isNaN(ymin)) f.minYear = ymin;
  if (!isNaN(ymax)) f.maxYear = ymax;
  const set = $('setname').value.trim();
  if (set) f.set = set;
  return f;
}

/* ---------- shareable URL state ---------- */
function stateToHash() {
  const p = new URLSearchParams();
  const q = $('q').value.trim();
  if (q) p.set('q', q);
  const put = (key, vals) => { if (vals.length) p.set(key, vals.join('|')); };
  put('cats', pressed('cats', 'cat'));
  put('subs', pressed('subs', 'sub'));
  put('alts', pressed('alts', 'alt'));
  put('diffs', pressed('diffs', 'diff'));
  if ($('qtype').value !== 'all') p.set('qtype', $('qtype').value);
  if ($('ymin').value) p.set('ymin', $('ymin').value);
  if ($('ymax').value) p.set('ymax', $('ymax').value);
  if ($('setname').value.trim()) p.set('set', $('setname').value.trim());
  history.replaceState(null, '', p.toString() ? '#' + p.toString() : location.pathname);
}

function hashToState() {
  const raw = location.hash.replace(/^#/, '');
  if (!raw || raw.startsWith('sync=')) return false;
  const p = new URLSearchParams(raw);
  $('q').value = p.get('q') || '';
  const press = (containerId, key) => {
    const want = new Set((p.get(key) || '').split('|').filter(Boolean));
    for (const b of $(containerId).querySelectorAll('.fchip')) {
      b.setAttribute('aria-pressed', want.has(b.textContent) ? 'true' : 'false');
    }
  };
  press('cats', 'cats');
  renderSubPanels();
  press('subs', 'subs');
  press('alts', 'alts');
  press('diffs', 'diffs');
  $('qtype').value = p.get('qtype') || 'all';
  $('ymin').value = p.get('ymin') || '';
  $('ymax').value = p.get('ymax') || '';
  $('setname').value = p.get('set') || '';
  return !!$('q').value;
}

/* ---------- search + rendering ---------- */
const setCache = new Map(); // set slug -> {tossups: Map, bonuses: Map}
function setShard(slug) {
  if (setCache.has(slug)) return Promise.resolve(setCache.get(slug));
  return qdataFetch('sets/' + slug + '.json').then(shard => {
    const t = new Map(), b = new Map();
    for (const pk of shard.packets) {
      for (const tu of pk.tossups || []) t.set(tu._id, tu);
      for (const bn of pk.bonuses || []) b.set(bn._id, bn);
    }
    const entry = { tossups: t, bonuses: b };
    setCache.set(slug, entry);
    return entry;
  });
}

let searchSeq = 0;

function runSearch() {
  const q = $('q').value.trim();
  if (!q) return;
  stateToHash();
  if (losClueSearch.mode() !== 'local' && !authHeader()) {
    $('results').innerHTML = '<div class="note">Sign in to search, or run it in '
      + 'your browser. <button type="button" class="linkbtn" id="signin">'
      + 'Sign in with GitHub</button> &middot; <button type="button" class="linkbtn" '
      + 'id="uselocal">In browser (600 MB model)</button></div>';
    $('signin').onclick = signIn;
    $('uselocal').onclick = () => { losClueSearch.setMode('local'); syncCsBtn(); runSearch(); };
    return;
  }
  const seq = ++searchSeq;
  $('results').innerHTML = '<div class="note">Searching&hellip;</div>';
  losClueSearch.search(q, readFilters())
    .then(res => { if (seq === searchSeq) renderResults(res.results || []); })
    .catch(e => {
      if (seq !== searchSeq) return;
      $('results').innerHTML = '<div class="note">Search failed: '
        + esc(String(e && e.signin ? 'Session expired. Sign in again.' : e.message || e)) + '</div>';
    });
}

function signIn() {
  const ret = location.origin + location.pathname + location.hash;
  location.href = CFG.syncBase + '/auth/login?return=' + encodeURIComponent(ret);
}

function badge(r) {
  const bits = [];
  if (r.set) bits.push(esc(r.set.replace(/_/g, ' ')));
  if (r.diff != null) bits.push('diff ' + r.diff);
  const tax = r.alt || r.sub || r.cat;
  if (tax) bits.push(esc(tax));
  bits.push(r.kind === 1 ? 'bonus' : 'tossup');
  return bits.join(' &middot; ');
}

function renderResults(results) {
  if (!results.length) {
    $('results').innerHTML = '<div class="note">No matches within these filters. '
      + 'Try widening them.</div>';
    return;
  }
  $('results').innerHTML = results.map((r, i) =>
    '<div class="hit" id="hit' + i + '"><div class="hit-head">'
    + '<span class="hit-score">' + (r.score != null ? r.score.toFixed(2) : '') + '</span>'
    + '<span class="hit-badge">' + badge(r) + '</span></div>'
    + '<div class="hit-body"><span class="note">loading&hellip;</span></div></div>'
  ).join('');
  results.forEach((r, i) => {
    if (!r.set) { fillHit(i, null, r); return; }
    setShard(r.set)
      .then(shard => fillHit(i, shard, r))
      .catch(() => fillHit(i, null, r));
  });
}

function fillHit(i, shard, r) {
  const body = document.querySelector('#hit' + i + ' .hit-body');
  if (!body) return;
  const doc = shard && (r.kind === 1 ? shard.bonuses : shard.tossups).get(r.id);
  if (!doc) {
    body.innerHTML = '<span class="note">question text unavailable</span>';
    return;
  }
  if (r.kind === 1) {
    const leadin = doc.leadin_sanitized || doc.leadin || '';
    const parts = doc.parts_sanitized || doc.parts || [];
    const answers = doc.answers_sanitized || doc.answers || [];
    let html = r.s === 255
      ? '<p><mark>' + esc(leadin) + '</mark></p>'
      : '<p>' + esc(leadin) + '</p>';
    parts.forEach((part, pi) => {
      const hit = r.s !== 255 && pi === r.s;
      html += '<p class="bpart">[10] ' + (hit ? '<mark>' + esc(part) + '</mark>' : esc(part))
        + '</p><p class="ans">ANSWER: ' + answerHTML(answers[pi] || '') + '</p>';
    });
    body.innerHTML = html;
  } else {
    const text = doc.question_sanitized || doc.question || '';
    const sents = splitSentences(text);
    const html = sents.map((s, si) =>
      si === r.s ? '<mark>' + esc(s) + '</mark>' : esc(s)).join(' ');
    body.innerHTML = '<p>' + html + '</p><p class="ans">ANSWER: '
      + answerHTML(doc.answer_sanitized || doc.answer || '') + '</p>';
  }
}

/* ---------- boot ---------- */
buildFilterPanel();
$('gobtn').onclick = runSearch;
$('q').addEventListener('keydown', e => { if (e.key === 'Enter') runSearch(); });
$('clearbtn').onclick = () => {
  for (const b of document.querySelectorAll('.fchip')) b.setAttribute('aria-pressed', 'false');
  renderSubPanels();
  $('qtype').value = 'all'; $('ymin').value = ''; $('ymax').value = ''; $('setname').value = '';
  stateToHash();
};
const st = syncState();
if (st.token && st.login) {
  $('whoami').textContent = 'signed in as ' + st.login;
} else {
  $('whoami').innerHTML = '<button type="button" class="linkbtn" id="signin2">sign in</button>';
  $('signin2').onclick = signIn;
}
function syncCsBtn() {
  $('csmode2').textContent = 'search: '
    + (losClueSearch.mode() === 'local' ? 'in browser' : 'cloud');
}
$('csmode2').onclick = () => {
  losClueSearch.setMode(losClueSearch.mode() === 'local' ? 'cloud' : 'local');
  syncCsBtn();
  if (losClueSearch.mode() === 'local') losClueSearch.prepare().catch(() => {});
};
losClueSearch.onProgress(p => {
  if (p.phase === 'model')
    $('csmode2').textContent = 'downloading model · ' + p.loadedMB + ' / ' + p.totalMB + ' MB';
  else if (p.phase === 'ready') syncCsBtn();
});
syncCsBtn();
if (hashToState()) runSearch();

// exposed for tests (sliced by tests/semsearch/run_tests.js)
window.__semsearch = { expandBundle, bundleOrdinals, splitSentences };
})();
