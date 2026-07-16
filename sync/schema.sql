-- D1 schema for the reader sync backend (sync/worker.js).
-- Apply with: npx wrangler d1 execute los-sync --remote --file schema.sql

CREATE TABLE IF NOT EXISTS users (
  uid TEXT PRIMARY KEY,              -- provider-namespaced id, e.g. "gh:12345"
  login TEXT NOT NULL,               -- display handle at last login
  created INTEGER NOT NULL,          -- ms epoch of first login
  attempts_count INTEGER NOT NULL DEFAULT 0
);

-- Append-only attempt log, one row per LOG entry from reader.js.
-- seq is the delta-sync cursor: clients pull "rows with seq > N", which is
-- immune to client clock skew (ts is client-reported and only used for
-- idempotent dedup via the UNIQUE constraint).
CREATE TABLE IF NOT EXISTS attempts (
  seq INTEGER PRIMARY KEY AUTOINCREMENT,
  uid TEXT NOT NULL,
  qid TEXT NOT NULL,                 -- qbreader question _id
  ts REAL NOT NULL,                  -- client Date.now() at record time
  data TEXT NOT NULL,                -- the full LOG record as JSON
  UNIQUE (uid, qid, ts)
);
CREATE INDEX IF NOT EXISTS idx_attempts_uid_seq ON attempts(uid, seq);

-- Reading settings + scope, one blob per user, last-write-wins by `updated`.
CREATE TABLE IF NOT EXISTS prefs (
  uid TEXT PRIMARY KEY,
  data TEXT NOT NULL,                -- the losReaderPrefsV1 blob as JSON
  updated REAL NOT NULL              -- client Date.now() stamp inside the blob
);
