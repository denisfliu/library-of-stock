// worker.js — OAuth-gated cross-device sync for the reader (Cloudflare
// Worker + D1). Deploy/setup: sync/README.md.
//
// Every /sync route requires a session token minted by the GitHub OAuth
// flow; there is NO anonymous read or write path — an unauthenticated
// request never touches D1. Sessions are stateless HMAC tokens (payload
// {u: uid, l: login, exp}), so there is no session table to manage.
//
// Storage model (see schema.sql):
//   attempts — append-only rows; server-assigned `seq` is the pull cursor,
//              UNIQUE(uid, qid, ts) makes pushes idempotent.
//   prefs    — one blob per user, last-write-wins by client `updated` stamp.

const TOKEN_TTL = 90 * 24 * 3600 * 1000; // session lifetime: 90 days
const STATE_TTL = 10 * 60 * 1000;        // oauth state lifetime: 10 minutes
const PULL_LIMIT = 800;                  // rows per pull page
const PUSH_LIMIT = 400;                  // rows per push call
const MAX_ROW_BYTES = 4096;              // per-record JSON cap
const MAX_PREFS_BYTES = 32768;           // prefs blob cap
const MAX_ROWS_PER_USER = 200000;        // abuse cap (~years of heavy play)

/* ---------- base64url + HMAC helpers ---------- */
const enc = new TextEncoder();

function b64url(bytes) {
  let s = '';
  for (const b of new Uint8Array(bytes)) s += String.fromCharCode(b);
  return btoa(s).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
}
function b64urlToBytes(s) {
  const bin = atob(s.replace(/-/g, '+').replace(/_/g, '/'));
  const out = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i++) out[i] = bin.charCodeAt(i);
  return out;
}

async function hmacKey(secret) {
  return crypto.subtle.importKey('raw', enc.encode(secret),
    { name: 'HMAC', hash: 'SHA-256' }, false, ['sign', 'verify']);
}
// Token format: b64url(payload JSON) + '.' + b64url(HMAC-SHA256 of that).
async function signToken(payload, secret) {
  const body = b64url(enc.encode(JSON.stringify(payload)));
  const sig = await crypto.subtle.sign('HMAC', await hmacKey(secret), enc.encode(body));
  return body + '.' + b64url(sig);
}
async function verifyToken(token, secret) {
  if (typeof token !== 'string') return null;
  const dot = token.indexOf('.');
  if (dot < 0) return null;
  const body = token.slice(0, dot), sig = token.slice(dot + 1);
  let ok = false;
  try {
    ok = await crypto.subtle.verify('HMAC', await hmacKey(secret),
      b64urlToBytes(sig), enc.encode(body));
  } catch (e) { return null; }
  if (!ok) return null;
  let payload;
  try { payload = JSON.parse(new TextDecoder().decode(b64urlToBytes(body))); }
  catch (e) { return null; }
  if (!payload || typeof payload.exp !== 'number' || payload.exp < Date.now()) return null;
  return payload;
}

/* ---------- responses ---------- */
function corsHeaders(env) {
  return {
    'Access-Control-Allow-Origin': env.ALLOWED_ORIGIN,
    'Access-Control-Allow-Methods': 'GET,POST,PUT,OPTIONS',
    'Access-Control-Allow-Headers': 'Authorization, Content-Type',
    'Vary': 'Origin',
  };
}
function json(env, data, status = 200) {
  return new Response(JSON.stringify(data), {
    status,
    headers: { 'Content-Type': 'application/json', ...corsHeaders(env) },
  });
}
function err(env, status, message) { return json(env, { error: message }, status); }

async function requireUser(request, env) {
  const auth = request.headers.get('Authorization') || '';
  if (!auth.startsWith('Bearer ')) return null;
  return verifyToken(auth.slice(7), env.SESSION_SECRET);
}

/* ---------- oauth flow ---------- */
async function authLogin(url, env) {
  // `return` must land back on the site we serve — prevents open redirects.
  const ret = url.searchParams.get('return') || '';
  if (!ret.startsWith(env.ALLOWED_ORIGIN)) {
    return new Response('bad return url (must be on ' + env.ALLOWED_ORIGIN + ')', { status: 400 });
  }
  const state = await signToken({ r: ret, exp: Date.now() + STATE_TTL }, env.SESSION_SECRET);
  const gh = new URL('https://github.com/login/oauth/authorize');
  gh.searchParams.set('client_id', env.GITHUB_CLIENT_ID);
  gh.searchParams.set('redirect_uri', url.origin + '/auth/callback');
  gh.searchParams.set('state', state);
  // No scope: default grant exposes only the public profile (we use id+login).
  return Response.redirect(gh.toString(), 302);
}

async function authCallback(url, env) {
  const state = await verifyToken(url.searchParams.get('state') || '', env.SESSION_SECRET);
  if (!state || !state.r) return new Response('bad or expired oauth state', { status: 400 });
  const code = url.searchParams.get('code');
  if (!code) return new Response('missing code', { status: 400 });

  const tokenRes = await fetch('https://github.com/login/oauth/access_token', {
    method: 'POST',
    headers: { 'Accept': 'application/json', 'Content-Type': 'application/json', 'User-Agent': 'los-sync' },
    body: JSON.stringify({ client_id: env.GITHUB_CLIENT_ID, client_secret: env.GITHUB_CLIENT_SECRET, code }),
  });
  const tok = await tokenRes.json().catch(() => ({}));
  if (!tok.access_token) return new Response('github token exchange failed', { status: 502 });

  const userRes = await fetch('https://api.github.com/user', {
    headers: { 'Authorization': 'Bearer ' + tok.access_token, 'Accept': 'application/vnd.github+json', 'User-Agent': 'los-sync' },
  });
  const gh = await userRes.json().catch(() => ({}));
  if (!gh.id) return new Response('github user lookup failed', { status: 502 });

  const uid = 'gh:' + gh.id;
  const login = String(gh.login || uid);
  await env.DB.prepare(
    'INSERT INTO users (uid, login, created) VALUES (?1, ?2, ?3) ON CONFLICT(uid) DO UPDATE SET login = ?2'
  ).bind(uid, login, Date.now()).run();

  const session = await signToken({ u: uid, l: login, exp: Date.now() + TOKEN_TTL }, env.SESSION_SECRET);
  // Fragment, not query: never hits server logs, and the client strips it.
  return Response.redirect(state.r + '#sync=' + session, 302);
}

/* ---------- sync routes (all require a valid session) ---------- */
async function syncPull(url, env, user) {
  const cursor = Math.max(0, Number(url.searchParams.get('cursor')) || 0);
  const { results } = await env.DB.prepare(
    'SELECT seq, data FROM attempts WHERE uid = ?1 AND seq > ?2 ORDER BY seq LIMIT ?3'
  ).bind(user.u, cursor, PULL_LIMIT).all();
  return json(env, {
    rows: results,
    next: results.length ? results[results.length - 1].seq : cursor,
    more: results.length === PULL_LIMIT,
  });
}

async function syncPush(request, env, user) {
  let body;
  try { body = await request.json(); } catch (e) { return err(env, 400, 'bad json'); }
  const rows = body && body.rows;
  if (!Array.isArray(rows) || rows.length > PUSH_LIMIT) return err(env, 400, 'rows must be an array of <= ' + PUSH_LIMIT);
  for (const r of rows) {
    if (!r || typeof r.qid !== 'string' || r.qid.length === 0 || r.qid.length > 64 ||
        !Number.isFinite(r.ts) ||
        typeof r.data !== 'string' || r.data.length > MAX_ROW_BYTES) {
      return err(env, 400, 'bad row');
    }
  }
  if (!rows.length) return json(env, { inserted: 0 });

  const { results } = await env.DB.prepare(
    'SELECT attempts_count FROM users WHERE uid = ?1'
  ).bind(user.u).all();
  const count = results.length ? results[0].attempts_count : 0;
  if (count + rows.length > MAX_ROWS_PER_USER) return err(env, 403, 'row cap reached');

  const stmt = env.DB.prepare('INSERT OR IGNORE INTO attempts (uid, qid, ts, data) VALUES (?1, ?2, ?3, ?4)');
  const outcomes = await env.DB.batch(rows.map(r => stmt.bind(user.u, r.qid, r.ts, r.data)));
  const inserted = outcomes.reduce((n, o) => n + ((o.meta && o.meta.changes) || 0), 0);
  if (inserted) {
    await env.DB.prepare('UPDATE users SET attempts_count = attempts_count + ?2 WHERE uid = ?1')
      .bind(user.u, inserted).run();
  }
  return json(env, { inserted });
}

async function prefsGet(env, user) {
  const { results } = await env.DB.prepare(
    'SELECT data, updated FROM prefs WHERE uid = ?1'
  ).bind(user.u).all();
  return json(env, results.length ? results[0] : { data: null, updated: 0 });
}

async function prefsPut(request, env, user) {
  let body;
  try { body = await request.json(); } catch (e) { return err(env, 400, 'bad json'); }
  if (!body || typeof body.data !== 'string' || body.data.length > MAX_PREFS_BYTES ||
      !Number.isFinite(body.updated)) {
    return err(env, 400, 'bad prefs');
  }
  // Last-write-wins: only overwrite if the incoming stamp is newer, then
  // return whatever won so the client can adopt the server copy if it lost.
  await env.DB.prepare(
    'INSERT INTO prefs (uid, data, updated) VALUES (?1, ?2, ?3) ' +
    'ON CONFLICT(uid) DO UPDATE SET data = excluded.data, updated = excluded.updated ' +
    'WHERE excluded.updated > prefs.updated'
  ).bind(user.u, body.data, body.updated).run();
  return prefsGet(env, user);
}

/* ---------- semantic clue search ----------
   IVF-binary index staged by lib/embed/build_search_index.py and uploaded
   under search/ in the data bucket. Pipeline: embed the query with the
   SAME model the corpus used (Workers AI qwen3-embedding-0.6b, with the
   Qwen3 query instruction prefix), pick NPROBE partitions by centroid dot
   product, range-read them from the bundle objects, scan Hamming distance
   over the 1024-bit sign codes. Clients resolve ids to question text via
   the published sets/{slug}.json shards. */
const SEARCH_MODEL = '@cf/qwen/qwen3-embedding-0.6b';
const QUERY_PREFIX = 'Instruct: Given a web search query, retrieve relevant '
  + 'passages that answer the query\nQuery: ';
const NPROBE = 24, NPROBE_FILTERED = 40, TOPK = 40, MAX_QUERY_CHARS = 500;
const CODE_BYTES = 128;
const ORD_NULL = 255; // taxonomy byte for NULL (see build_search_index.py)

function f16One(bytes, off) {
  const h = bytes[off] | (bytes[off + 1] << 8);
  const s = (h & 0x8000) >> 15, e = (h & 0x7C00) >> 10, f = h & 0x3FF;
  let v;
  if (e === 0) v = f * Math.pow(2, -24);
  else if (e === 31) v = f ? NaN : Infinity;
  else v = (1 + f / 1024) * Math.pow(2, e - 15);
  return s ? -v : v;
}

let searchIndex = null; // cached across requests in this isolate

function f16ToF32(bytes) {
  const n = bytes.length / 2;
  const u16 = new Uint16Array(bytes.buffer, bytes.byteOffset, n);
  const out = new Float32Array(n);
  for (let i = 0; i < n; i++) {
    const h = u16[i], s = (h & 0x8000) >> 15, e = (h & 0x7C00) >> 10, f = h & 0x3FF;
    let v;
    if (e === 0) v = f * Math.pow(2, -24);
    else if (e === 31) v = f ? NaN : Infinity;
    else v = (1 + f / 1024) * Math.pow(2, e - 15);
    out[i] = s ? -v : v;
  }
  return out;
}

async function loadSearchIndex(env) {
  if (searchIndex) return searchIndex;
  const [mObj, cObj] = await Promise.all([
    env.DATA.get('search/search_manifest.json'),
    env.DATA.get('search/centroids.f16'),
  ]);
  if (!mObj || !cObj) throw new Error('search index not published');
  const manifest = await mObj.json();
  const centroids = f16ToF32(new Uint8Array(await cObj.arrayBuffer()));
  const popcnt = new Uint8Array(256);
  for (let i = 1; i < 256; i++) popcnt[i] = (i & 1) + popcnt[i >> 1];
  searchIndex = { manifest, centroids, popcnt };
  return searchIndex;
}

const HEX = '0123456789abcdef';
function rowIdHex(bytes, off) {
  let s = '';
  for (let i = 0; i < 12; i++) { const b = bytes[off + i]; s += HEX[b >> 4] + HEX[b & 15]; }
  return s;
}

/* ---------- /search filters (qbreader-/db semantics) ----------
   The page sends the ALREADY-EXPANDED category bundle as ordinal arrays
   (ordinals into the manifest's canonical taxonomy lists — the expansion
   port lives in lib/js/semsearch.js). The Worker just masks rows during
   the scan. Composition mirrors lib/mirror/query.py _build_where:
   category IN cats AND subcategory IN subs AND (alt IN alts OR alt IS
   NULL) AND difficulty IN diffs AND year range AND set-name substring. */

function ordMask(list) {
  const m = new Uint8Array(256);
  for (const v of list) if (Number.isInteger(v) && v >= 0 && v < 256) m[v] = 1;
  return m;
}

function buildRowFilter(body, manifest) {
  const cats = Array.isArray(body.cats) ? body.cats : [];
  const subs = Array.isArray(body.subs) ? body.subs : [];
  const alts = Array.isArray(body.alts) ? body.alts : [];
  const diffs = Array.isArray(body.diffs) ? body.diffs : [];
  const qtype = body.qtype === 'tossup' ? 0 : body.qtype === 'bonus' ? 1 : -1;
  const minYear = Number.isInteger(body.minYear) ? body.minYear : null;
  const maxYear = Number.isInteger(body.maxYear) ? body.maxYear : null;
  const setQuery = typeof body.set === 'string' ? body.set.trim().toLowerCase() : '';

  const hasBundle = cats.length > 0; // expansion guarantees subs/alts follow cats
  const needSetPass = minYear !== null || maxYear !== null || setQuery !== '';
  if (!hasBundle && !diffs.length && qtype < 0 && !needSetPass) return null;

  const f = { qtype, hasBundle };
  if (hasBundle) {
    f.catOK = ordMask(cats);
    f.subOK = ordMask(subs);
    f.altOK = ordMask(alts);
  }
  f.diffOK = diffs.length ? ordMask(diffs) : null;
  if (needSetPass) {
    const years = manifest.set_years || [];
    const names = manifest.set_names || [];
    const n = Math.max(years.length, names.length);
    const setOK = new Uint8Array(n);
    for (let i = 0; i < n; i++) {
      const y = years[i] || 0;
      if (minYear !== null && (!y || y < minYear)) continue;
      if (maxYear !== null && (!y || y > maxYear)) continue;
      if (setQuery && !(names[i] || '').toLowerCase().includes(setQuery)) continue;
      setOK[i] = 1;
    }
    f.setOK = setOK;
  }
  return f;
}

function rowPasses(f, bytes, off) {
  if (f.qtype >= 0 && bytes[off + 12] !== f.qtype) return false;
  if (f.setOK) {
    const so = bytes[off + 14] | (bytes[off + 15] << 8);
    if (so >= f.setOK.length || !f.setOK[so]) return false;
  }
  if (f.hasBundle) {
    if (!f.catOK[bytes[off + 16]]) return false;
    if (!f.subOK[bytes[off + 17]]) return false;
    const alt = bytes[off + 18];
    if (alt !== ORD_NULL && !f.altOK[alt]) return false;
  }
  if (f.diffOK && !f.diffOK[bytes[off + 19]]) return false;
  return true;
}

async function search(url, request, env) {
  let q = url.searchParams.get('q') || '';
  let body = {};
  if (request.method === 'POST') {
    body = await request.json().catch(() => ({}));
    if (typeof body.q === 'string') q = body.q;
  }
  q = q.trim().slice(0, MAX_QUERY_CHARS);
  if (!q) return err(env, 400, 'empty query');

  let idx;
  try { idx = await loadSearchIndex(env); }
  catch (e) { return err(env, 503, String(e.message || e)); }
  const { manifest, centroids, popcnt } = idx;
  const dims = manifest.dims, k = manifest.k;
  const metaBytes = manifest.meta_bytes || 16;

  const filter = buildRowFilter(body, manifest);
  if (filter && metaBytes < 20) {
    return err(env, 400, 'published index predates filters — rebuild it');
  }

  const ai = await env.AI.run(SEARCH_MODEL, { text: [QUERY_PREFIX + q] });
  const vec = (ai.data && ai.data[0]) || ai;
  if (!vec || vec.length !== dims) return err(env, 502, 'embedding failed');

  // top-N centroids by dot product; probe wider when a filter narrows
  // the candidate pool (still within the free plan's subrequest cap).
  const nprobe = filter ? NPROBE_FILTERED : NPROBE;
  const scores = new Float32Array(k);
  for (let c = 0; c < k; c++) {
    let dot = 0; const base = c * dims;
    for (let d = 0; d < dims; d++) dot += centroids[base + d] * vec[d];
    scores[c] = dot;
  }
  const probes = Array.from(scores.keys())
    .sort((a, b) => scores[b] - scores[a]).slice(0, nprobe);

  // binary query code (sign bits)
  const qbits = new Uint8Array(CODE_BYTES);
  for (let d = 0; d < dims; d++) if (vec[d] > 0) qbits[d >> 3] |= 128 >> (d & 7);

  const reads = probes
    .map(p => manifest.parts[p])
    .filter(part => part[2] > 0)
    .map(part => env.DATA.get(`search/bundle_${String(part[0]).padStart(2, '0')}.bin`,
      { range: { offset: part[1], length: part[2] } })
      .then(o => o ? o.arrayBuffer() : null));
  const bufs = (await Promise.all(reads)).filter(Boolean);

  // Stage 1: Hamming scan over the binary codes; keep the top candidates.
  // Filtered rows drop here, before either ranking tier sees them, so
  // top-K is computed within the filter.
  const rowBytes = manifest.row_bytes;
  const rerankTop = manifest.rerank_top || 200;
  const cands = [];
  for (const buf of bufs) {
    const bytes = new Uint8Array(buf);
    for (let off = 0; off + rowBytes <= bytes.length; off += rowBytes) {
      if (filter && !rowPasses(filter, bytes, off)) continue;
      let dist = 0;
      for (let i = 0; i < CODE_BYTES; i++)
        dist += popcnt[bytes[off + metaBytes + i] ^ qbits[i]];
      cands.push({ dist, bytes, off });
    }
  }
  cands.sort((a, b) => a.dist - b.dist);
  cands.length = Math.min(cands.length, rerankTop);

  // Stage 2: rescore with the int8 rerank vector carried in each row —
  // no extra fetches (the Workers free plan caps subrequests at 50).
  const RD = manifest.rerank_dims || 512;
  const q512 = new Float32Array(RD);
  let qn = 0;
  for (let d = 0; d < RD; d++) qn += vec[d] * vec[d];
  qn = Math.sqrt(qn) || 1;
  for (let d = 0; d < RD; d++) q512[d] = vec[d] / qn;
  for (const c of cands) {
    const scaleOff = c.off + metaBytes + CODE_BYTES;
    const scale = f16One(c.bytes, scaleOff);
    let dot = 0;
    const base = scaleOff + 2;
    for (let d = 0; d < RD; d++) {
      let v = c.bytes[base + d];
      if (v > 127) v -= 256;
      dot += v * q512[d];
    }
    c.score = dot * scale;
  }
  cands.sort((a, b) => b.score - a.score);

  const named = (list, ord) =>
    (ord === undefined || ord >= 254) ? null : (list && list[ord]) || null;
  return json(env, {
    q,
    filtered: !!filter,
    results: cands.slice(0, TOPK).map(c => {
      const off = c.off, b = c.bytes;
      const setOrd = b[off + 14] | (b[off + 15] << 8);
      const out = {
        id: rowIdHex(b, off),
        kind: b[off + 12],
        s: b[off + 13],
        set: manifest.set_slugs[setOrd] || null,
        score: Math.round(c.score * 1000) / 1000,
      };
      if (metaBytes >= 20) {
        out.cat = named(manifest.categories, b[off + 16]);
        out.sub = named(manifest.subcategories, b[off + 17]);
        out.alt = named(manifest.alternate_subcategories, b[off + 18]);
        out.diff = b[off + 19] === ORD_NULL ? null : b[off + 19];
        out.year = (manifest.set_years || [])[setOrd] || null;
      }
      return out;
    }),
  });
}

/* ---------- router ---------- */
export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    const path = url.pathname;

    if (request.method === 'OPTIONS') {
      return new Response(null, { status: 204, headers: corsHeaders(env) });
    }

    // OAuth endpoints are navigations (no auth header yet).
    if (path === '/auth/login' && request.method === 'GET') return authLogin(url, env);
    if (path === '/auth/callback' && request.method === 'GET') return authCallback(url, env);

    if (path === '/') return new Response('los-sync: reader sync backend. See /auth/login.', { status: 200 });

    // Everything else requires a session — no anonymous reads or writes.
    const user = await requireUser(request, env);
    if (!user) return err(env, 401, 'sign in required');

    if (path === '/auth/me' && request.method === 'GET') {
      return json(env, { uid: user.u, login: user.l, exp: user.exp });
    }
    if (path === '/search' && (request.method === 'GET' || request.method === 'POST')) {
      return search(url, request, env);
    }
    if (path === '/sync/pull' && request.method === 'GET') return syncPull(url, env, user);
    if (path === '/sync/push' && request.method === 'POST') return syncPush(request, env, user);
    if (path === '/sync/prefs' && request.method === 'GET') return prefsGet(env, user);
    if (path === '/sync/prefs' && request.method === 'PUT') return prefsPut(request, env, user);

    return err(env, 404, 'not found');
  },
};
