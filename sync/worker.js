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
    if (path === '/sync/pull' && request.method === 'GET') return syncPull(url, env, user);
    if (path === '/sync/push' && request.method === 'POST') return syncPush(request, env, user);
    if (path === '/sync/prefs' && request.method === 'GET') return prefsGet(env, user);
    if (path === '/sync/prefs' && request.method === 'PUT') return prefsPut(request, env, user);

    return err(env, 404, 'not found');
  },
};
