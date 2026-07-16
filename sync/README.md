# Reader sync backend

OAuth-gated cross-device sync for `reader.html`: a Cloudflare Worker
(`worker.js`) in front of a D1 database (`schema.sql`). Every read and
write requires a GitHub-OAuth-derived session token — there is no
anonymous path.

The client half is `lib/js/sync.js` (loaded by reader.html); it stays
inert until its `SYNC_BASE` constant points at the deployed Worker.

## How it syncs

- **Attempt log** (`losReaderStatsV1`): append-only. Each device pushes
  records it hasn't pushed yet (a `_p` flag per record), and pulls by a
  server-assigned `seq` cursor — both directions are immune to device
  clock skew. `UNIQUE(uid, qid, ts)` makes duplicate pushes no-ops.
  Because stats/drill state is a deterministic replay of the log, every
  device converges to identical SRS state once logs match.
- **Prefs** (`losReaderPrefsV1`): whole-blob last-write-wins by the `up`
  stamp `savePrefs` writes. Remote prefs apply on the next page load.
- **Identity**: `uid = "gh:<github user id>"`, namespaced so another
  provider (Google) can be added later without a migration. The session
  is a stateless 90-day HMAC token delivered via URL fragment; "sign out"
  just discards it client-side.
- **Login merge prompt**: if a browser has local history that isn't tied
  to the account signing in (guest play, or a different account than last
  time), the client asks before syncing — merge the local log into this
  account, start fresh (discard local, confirm-guarded), or cancel the
  sign-in. Nothing syncs until the user chooses, and a sync already in
  flight for the previous account discards its writes when the account
  changes mid-flight.

## One-time setup

All commands from this directory (`sync/`).

1. **Create the D1 database**

   ```
   npx wrangler d1 create los-sync
   ```

   Paste the printed `database_id` into `wrangler.toml`, then apply the
   schema:

   ```
   npx wrangler d1 execute los-sync --remote --file schema.sql
   ```

2. **First deploy** (to learn the Worker URL):

   ```
   npx wrangler deploy
   ```

   Note the URL, e.g. `https://los-sync.<subdomain>.workers.dev`.

3. **Create the GitHub OAuth app**: GitHub → Settings → Developer
   settings → OAuth Apps → New OAuth App.
   - Homepage URL: `https://denisfliu.github.io/library-of-stock/`
   - Authorization callback URL: `https://<worker-url>/auth/callback`

   Copy the Client ID into `wrangler.toml` (`GITHUB_CLIENT_ID`), generate
   a client secret, and store both secrets:

   ```
   npx wrangler secret put GITHUB_CLIENT_SECRET
   npx wrangler secret put SESSION_SECRET        # any long random string, e.g. `openssl rand -hex 32`
   ```

4. **Redeploy** with the final vars:

   ```
   npx wrangler deploy
   ```

5. **Point the client at it**: set `SYNC_BASE` in `lib/js/sync.js` to the
   Worker URL, run `python lib/render/build_reader.py`, and push to
   GitHub Pages. A "Sync" panel appears in the reader's sidebar.

Rotating `SESSION_SECRET` invalidates every session (all devices must
sign in again) — that's the kill switch if a token ever leaks.

## Costs / limits

Runs on the Workers **Free** plan: hard caps, never billed. D1 free tier
is 100k row writes + 5M row reads per day — roughly 300 heavily active
daily users. Over-limit requests fail with errors and the client retries
later; localStorage keeps everything in the meantime. Per-user storage is
capped at 200k attempt rows (`MAX_ROWS_PER_USER`). If the site outgrows
this, the $5/mo Workers Paid plan raises D1 to tens of millions of writes
per month.

Optional hardening: add a Cloudflare WAF rate-limiting rule on the
Worker's route (e.g. 60 req/min per IP) — not needed at friends-and-
teammates scale.
