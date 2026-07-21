// sync.js — cross-device sync for the reader, gated behind GitHub OAuth.
//
// Talks to the sync/ Cloudflare Worker (worker.js): pulls remote attempt
// rows by server-assigned cursor, pushes local LOG entries that haven't
// been pushed yet (tracked by a `_p` flag on each record, so the protocol
// is immune to device clock skew), and exchanges the prefs blob
// last-write-wins. localStorage stays the source of truth — sync is pure
// transport, and a failed sync just retries later.
//
// Integration surface: window.losReaderHook (defined in reader.js) exposes
// getLog/mergeLog/save and an onRecord callback slot.
(function () {
'use strict';

// Worker URL, e.g. 'https://los-sync.<subdomain>.workers.dev'.
// Empty string disables sync entirely (panel stays hidden).
const SYNC_BASE = 'https://los-sync.denisliu10.workers.dev';

const KEY = 'losSyncV1';
const PREFS_KEY = 'losReaderPrefsV1';
const PUSH_BATCH = 400;
const RECORD_DEBOUNCE = 45 * 1000;   // sync this long after the last buzz
const MIN_INTERVAL = 20 * 1000;      // don't hammer on rapid triggers

const hook = window.losReaderHook;
const panel = document.getElementById('syncpanel');
if (!SYNC_BASE || !hook || !panel || !/^https?:$/.test(location.protocol)) return;

let st = { token: null, uid: null, login: null, cursor: 0, lastSync: 0 };
try { st = Object.assign(st, JSON.parse(localStorage.getItem(KEY) || 'null') || {}); } catch (e) {}
function saveSt() { try { localStorage.setItem(KEY, JSON.stringify(st)); } catch (e) {} }

// Session surface for other reader features (clue lookup calls /search on
// the same Worker): base URL + current auth header, or null when signed out.
hook.searchBase = SYNC_BASE;
hook.searchAuth = () => (st.token ? { Authorization: 'Bearer ' + st.token } : null);

function tokenPayload(token) {
  try {
    const body = token.split('.')[0].replace(/-/g, '+').replace(/_/g, '/');
    return JSON.parse(atob(body));
  } catch (e) { return null; }
}

/* ---------- capture the session token from the oauth redirect ---------- */
// A login for a DIFFERENT account than this browser last synced (or a first
// login with pre-existing guest history) never merges silently: the user
// chooses between merging the local log into the account and starting fresh.
function adoptAccount(token, p, discardLocal) {
  if (discardLocal) {
    const log = hook.getLog();
    log.length = 0;                    // in place — reader shares this array
    hook.save();
    try { localStorage.removeItem(PREFS_KEY); } catch (e) {}  // adopt account prefs on next load
  } else {
    // Restart the push protocol: everything local uploads to this account.
    for (const r of hook.getLog()) delete r._p;
    hook.save();
  }
  st.cursor = 0; st.token = token; st.uid = p.u; st.login = p.l || p.u;
  saveSt();
}

function showMergePrompt(token, p, count) {
  const esc = s => String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
  const switching = !!st.uid;   // browser history was synced under another account
  const ov = document.createElement('div');
  ov.style.cssText = 'position:fixed;inset:0;background:rgba(0,0,0,0.65);z-index:100;' +
    'display:flex;align-items:center;justify-content:center;padding:1rem';
  const card = document.createElement('div');
  card.className = 'panel';
  card.style.cssText = 'max-width:26rem;margin:0';
  card.innerHTML =
    '<h2>Signed in as ' + esc(p.l || p.u) + '</h2>' +
    '<div style="font-size:0.88rem;margin-bottom:0.8rem">This browser has <b>' +
    count.toLocaleString() + '</b> recorded question' + (count === 1 ? '' : 's') + ' ' +
    (switching
      ? 'from a different account (<b>' + esc(st.login || st.uid) + '</b>).'
      : 'that aren&rsquo;t linked to an account yet.') +
    ' What should happen to them?</div>' +
    '<div style="display:flex;flex-direction:column;gap:0.5rem">' +
    '<button class="btn' + (switching ? '' : ' primary') + '" id="mergekeep">Merge them into this account</button>' +
    '<button class="btn' + (switching ? ' primary' : '') + '" id="mergefresh">Start fresh: discard this browser&rsquo;s local history</button>' +
    '<button class="linkbtn" id="mergecancel" style="align-self:center">Cancel sign-in</button></div>';
  ov.appendChild(card);
  document.body.appendChild(ov);
  const done = () => { ov.remove(); renderPanel(); };
  card.querySelector('#mergekeep').onclick = () => {
    adoptAccount(token, p, false); done(); syncNow(true);
  };
  card.querySelector('#mergefresh').onclick = () => {
    if (!confirm('Discard the ' + count.toLocaleString() + ' locally recorded questions on this browser? ' +
                 'Your account’s synced history is unaffected.')) return;
    adoptAccount(token, p, true); done(); syncNow(true);
  };
  card.querySelector('#mergecancel').onclick = done;   // stays signed out; nothing synced
}

(function captureToken() {
  const m = location.hash.match(/[#&]sync=([^&]+)/);
  if (!m) return;
  history.replaceState(null, '', location.pathname + location.search);
  const token = m[1];
  const p = tokenPayload(token);
  if (!p || !p.u) return;
  if (p.u === st.uid) {              // same account: token refresh, no ceremony
    st.token = token; st.login = p.l || p.u; saveSt();
    return;
  }
  const count = hook.getLog().length;
  if (!count) { adoptAccount(token, p, false); return; }   // nothing local to decide about
  showMergePrompt(token, p, count);
})();

/* ---------- api ---------- */
async function api(method, path, body) {
  const res = await fetch(SYNC_BASE + path, {
    method,
    headers: Object.assign(
      { 'Authorization': 'Bearer ' + st.token },
      body !== undefined ? { 'Content-Type': 'application/json' } : {}),
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });
  if (res.status === 401) { signOut('Session expired. Sign in again to sync.'); throw new Error('unauthorized'); }
  if (!res.ok) throw new Error('sync http ' + res.status);
  return res.json();
}

function signOut(msg) {
  st.token = null;
  saveSt();
  renderPanel(msg);
}

/* ---------- the sync cycle ---------- */
let syncing = false, lastAttempt = 0, debounceTimer = null;

async function syncNow(force) {
  if (!st.token || syncing) return;
  if (!force && Date.now() - lastAttempt < MIN_INTERVAL) return;
  syncing = true; lastAttempt = Date.now();
  // The account can change mid-flight (login merge prompt while a sync for
  // the previous account is running): after every await, discard the stale
  // response instead of writing the old account's cursor/flags/prefs into
  // the new account's state.
  const session = st.token;
  const stale = () => st.token !== session;
  renderPanel('Syncing…');
  try {
    // Pull: everything past our cursor, page by page. Rows we pushed
    // ourselves come back too; mergeLog dedupes them by (id, ts).
    for (;;) {
      const page = await api('GET', '/sync/pull?cursor=' + st.cursor);
      if (stale()) return;
      const entries = [];
      for (const row of page.rows) {
        try { const r = JSON.parse(row.data); r._p = 1; entries.push(r); } catch (e) {}
      }
      if (entries.length) hook.mergeLog(entries);
      st.cursor = page.next; saveSt();
      if (!page.more) break;
    }
    // Push: local records not yet flagged, in batches. Flag exactly the
    // objects we sent (records added mid-flight keep their unflagged state).
    const pending = hook.getLog().filter(r => !r._p);
    for (let i = 0; i < pending.length; i += PUSH_BATCH) {
      const batch = pending.slice(i, i + PUSH_BATCH);
      await api('POST', '/sync/push', {
        rows: batch.map(r => {
          const clean = Object.assign({}, r); delete clean._p;
          return { qid: String(r.id), ts: r.ts, data: JSON.stringify(clean) };
        }),
      });
      if (stale()) return;
      for (const r of batch) r._p = 1;
      hook.save();
    }
    // Prefs: last-write-wins by the `up` stamp savePrefs writes.
    let local = null;
    try { local = JSON.parse(localStorage.getItem(PREFS_KEY) || 'null'); } catch (e) {}
    const localUp = (local && local.up) || 0;
    const remote = local
      ? await api('PUT', '/sync/prefs', { data: JSON.stringify(local), updated: localUp })
      : await api('GET', '/sync/prefs');
    if (stale()) return;
    if (remote.data && remote.updated > localUp) {
      try { localStorage.setItem(PREFS_KEY, remote.data); } catch (e) {}
    }
    st.lastSync = Date.now(); saveSt();
    renderPanel();
  } catch (e) {
    if (e.message !== 'unauthorized') renderPanel('Sync failed. Will retry.');
  } finally {
    syncing = false;
    // If the account changed while we were in flight, the new account still
    // needs its initial sync (the merge prompt's call no-oped on `syncing`).
    if (st.token && stale()) syncNow(true);
  }
}

/* ---------- triggers ---------- */
hook.onRecord = () => {
  clearTimeout(debounceTimer);
  debounceTimer = setTimeout(() => syncNow(false), RECORD_DEBOUNCE);
};
document.addEventListener('visibilitychange', () => {
  if (document.visibilityState === 'hidden') syncNow(true);
});

/* ---------- panel ---------- */
function fmtAgo(ts) {
  if (!ts) return 'never';
  const s = Math.round((Date.now() - ts) / 1000);
  if (s < 60) return 'just now';
  if (s < 3600) return Math.round(s / 60) + ' min ago';
  if (s < 86400) return Math.round(s / 3600) + ' h ago';
  return new Date(ts).toLocaleDateString();
}

function renderPanel(status) {
  panel.style.display = '';
  const body = document.getElementById('syncbody');
  if (!st.token) {
    body.innerHTML = '<button class="btn" id="synclogin">Sign in with GitHub</button>' +
      '<div class="hint">' + (status ? status + ' ' : '') +
      'Syncs stats and settings across devices and enables clue search.</div>';
    document.getElementById('synclogin').onclick = () => {
      const ret = location.origin + location.pathname;
      location.href = SYNC_BASE + '/auth/login?return=' + encodeURIComponent(ret);
    };
    return;
  }
  const esc = s => String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
  body.innerHTML =
    '<div class="hint" style="margin-top:0">Signed in as <b style="color:var(--bright)">' + esc(st.login) + '</b>' +
    ' &middot; <span id="syncstatus">' + (status || 'synced ' + fmtAgo(st.lastSync)) + '</span></div>' +
    '<div style="display:flex;gap:0.5rem;margin-top:0.5rem">' +
    '<button class="btn" id="syncnow">Sync now</button>' +
    '<button class="linkbtn" id="syncout">Sign out</button></div>' +
    '<div class="hint">Synced settings from another device apply on the next page load.</div>';
  document.getElementById('syncnow').onclick = () => syncNow(true);
  document.getElementById('syncout').onclick = () => signOut();
}

renderPanel();
if (st.token) syncNow(true);
})();
