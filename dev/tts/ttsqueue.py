"""ttsqueue — cross-machine work queue for TTS generation.

One SQLite file on the queue host (`~/los_tts/tts_queue.db`) is the single source
of truth for which of the ~120k diff-7-9 items still need synthesizing. Any number
of workers, on any machine, claim disjoint batches so each qid is generated exactly
once across the fleet — real parallelism, since each machine has its own GPU (two
streams on one GPU just time-share it).

Transport is SSH, not an HTTP port: MSL sits behind the Stanford firewall, so a
worker elsewhere invokes `ssh <host> python ttsqueue.py claim ...` — works wherever
ssh already works, no tunnels or exposed ports. Claims are batched (~100 items =
~15 min of work), so one ssh round-trip per batch is negligible overhead.

Robustness:
  - claim() runs in a BEGIN IMMEDIATE transaction with a busy timeout, so two
    concurrent claimers (local + remote) can never grab the same rows.
  - a claim carries a lease timestamp; an item claimed but not completed within
    LEASE_S (a crashed/killed worker) is re-served to the next claimer. Completion
    is idempotent and HF upload overwrites, so a re-done item is harmless.

Library API (used in-process by gen_tts when it hosts the queue): init, claim,
complete, stats. Client wraps these to run either locally or over ssh.

CLI (used over ssh by remote workers, and by hand):
  python ttsqueue.py init [--reseed]   # seed from the mirror; mark existing out/ done
  python ttsqueue.py claim --worker W --n 100    # prints "kind qid" lines
  python ttsqueue.py complete          # reads "kind qid" lines from stdin
  python ttsqueue.py stats             # JSON counts by status
"""
import argparse
import json
import sqlite3
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from ttscorpus import WORK, DB, worklist, out_path

QUEUE_DB = WORK / "tts_queue.db"
LEASE_S = 1800            # a claimed-but-not-completed item re-serves after this (30 min:
                         # a paused/killed worker's in-flight items recover promptly)
BUSY_MS = 30000          # wait up to this for the write lock instead of erroring

# Default remote invocation (a worker on another machine reaching MSL's queue).
REMOTE_PY = "~/venvs/chatterbox-tts/bin/python"
REMOTE_SCRIPT = "~/los_tts/ttsqueue.py"


def _connect():
    con = sqlite3.connect(QUEUE_DB, timeout=BUSY_MS / 1000)
    con.execute(f"PRAGMA busy_timeout={BUSY_MS}")
    con.execute("PRAGMA journal_mode=WAL")     # readers don't block the claimer
    return con


def init(reseed=False):
    """Create the queue and seed it from the mirror worklist, marking as done any
    item already present in this host's out/. Idempotent; --reseed wipes first.
    Also seeds/backfills set_name per qid — claim() serves sets nearest 100%
    tossup audio first, so the moderator's pickable-set list grows fastest."""
    con = _connect()
    if reseed:
        con.execute("DROP TABLE IF EXISTS items")
    con.execute("""CREATE TABLE IF NOT EXISTS items(
        qid TEXT PRIMARY KEY, kind TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'todo', worker TEXT, lease REAL,
        set_name TEXT)""")
    con.execute("CREATE INDEX IF NOT EXISTS idx_status ON items(status)")
    try:
        con.execute("ALTER TABLE items ADD COLUMN set_name TEXT")   # pre-existing db
    except sqlite3.OperationalError:
        pass                                                        # already there
    mirror = sqlite3.connect(DB)
    wl = worklist(mirror)
    sets = dict(mirror.execute(
        "SELECT id, set_name FROM tossups WHERE difficulty IN (7,8,9)"))
    sets.update(mirror.execute(
        "SELECT id, set_name FROM bonuses WHERE difficulty IN (7,8,9)"))
    con.executemany("INSERT OR IGNORE INTO items(qid, kind, set_name) VALUES(?, ?, ?)",
                    [(qid, kind, sets.get(qid)) for kind, qid, _ in wl])
    con.executemany("UPDATE items SET set_name=? WHERE qid=? AND set_name IS NULL",
                    [(sets.get(qid), qid) for kind, qid, _ in wl])
    done = [(qid,) for kind, qid, _ in wl if out_path(kind, qid).exists()]
    con.executemany("UPDATE items SET status='done' WHERE qid=? AND status!='done'", done)
    con.commit()
    n = con.execute("SELECT COUNT(*) FROM items").fetchone()[0]
    print(f"seeded {n:,} items, marked {len(done):,} already-done", flush=True)
    return stats()


def claim(worker, n):
    """Atomically claim up to n todo (or lease-expired) items. Returns [(kind, qid)].

    Serve order finishes sets, not ids: sets with the fewest not-done tossups
    first (a set whose tossups are all done ranks 0, so its bonuses lead),
    tossups before bonuses within a set. Every finished set immediately becomes
    pickable in the moderator's TTS-audio mode; ids without a set_name (not in
    the current mirror — shouldn't happen after init) go last."""
    con = _connect()
    con.execute("BEGIN IMMEDIATE")             # take the write lock up front
    cutoff = time.time() - LEASE_S
    rows = con.execute(
        "WITH remaining AS (SELECT set_name, COUNT(*) AS r FROM items "
        "  WHERE kind='tossups' AND status!='done' GROUP BY set_name) "
        "SELECT i.kind, i.qid FROM items i LEFT JOIN remaining USING(set_name) "
        "WHERE i.status='todo' OR (i.status='claimed' AND i.lease < ?) "
        "ORDER BY CASE WHEN i.set_name IS NULL THEN 1000000 "
        "  ELSE COALESCE(remaining.r, 0) END, "
        "  i.kind DESC, i.set_name, i.qid LIMIT ?",
        (cutoff, n)).fetchall()
    now = time.time()
    con.executemany("UPDATE items SET status='claimed', worker=?, lease=? WHERE qid=?",
                    [(worker, now, qid) for _, qid in rows])
    con.commit()
    return [(kind, qid) for kind, qid in rows]


def complete(items):
    """Mark [(kind, qid), ...] done. Idempotent."""
    if not items:
        return
    con = _connect()
    con.executemany("UPDATE items SET status='done' WHERE qid=?", [(qid,) for _, qid in items])
    con.commit()


def stats():
    con = _connect()
    return {s: c for s, c in con.execute("SELECT status, COUNT(*) FROM items GROUP BY status")}


def reconcile():
    """Reset to 'todo' any item marked done whose .opus isn't in the host's out/.
    Closes the gap where a worker completed an item but died before push_out
    shipped the file. Run on the host after the queue drains, then refill."""
    con = _connect()
    rows = con.execute("SELECT kind, qid FROM items WHERE status='done'").fetchall()
    missing = [(qid,) for kind, qid in rows if not out_path(kind, qid).exists()]
    con.executemany("UPDATE items SET status='todo', worker=NULL, lease=NULL WHERE qid=?", missing)
    con.commit()
    print(f"reconcile: {len(missing):,} done-but-missing reset to todo", flush=True)
    return len(missing)


class Client:
    """Queue access for gen_tts. host="" -> call the library in-process (this
    machine hosts the queue); host="msl" -> run the CLI over ssh."""
    def __init__(self, host="", remote_py=REMOTE_PY, remote_script=REMOTE_SCRIPT):
        self.host = host
        self.remote = [remote_py, remote_script] if host else None

    def _ssh(self, args, stdin=None):
        cmd = ["ssh", self.host, " ".join(self.remote + args)]
        return subprocess.run(cmd, input=stdin, capture_output=True, text=True, check=True).stdout

    def claim(self, worker, n):
        if not self.host:
            return claim(worker, n)
        out = self._ssh(["claim", "--worker", worker, "--n", str(n)])
        return [(ln.split()[0], ln.split()[1]) for ln in out.splitlines() if ln.strip()]

    def complete(self, items):
        if not self.host:
            return complete(items)
        if items:
            self._ssh(["complete"], stdin="".join(f"{k} {q}\n" for k, q in items))

    def stats(self):
        if not self.host:
            return stats()
        return json.loads(self._ssh(["stats"]))


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    p_init = sub.add_parser("init"); p_init.add_argument("--reseed", action="store_true")
    p_claim = sub.add_parser("claim")
    p_claim.add_argument("--worker", required=True); p_claim.add_argument("--n", type=int, default=100)
    sub.add_parser("complete")
    sub.add_parser("stats")
    sub.add_parser("reconcile")
    args = ap.parse_args()

    if args.cmd == "init":
        json.dump(init(reseed=args.reseed), sys.stdout)
    elif args.cmd == "claim":
        for kind, qid in claim(args.worker, args.n):
            print(f"{kind} {qid}")
    elif args.cmd == "complete":
        items = [(p[0], p[1]) for p in (ln.split() for ln in sys.stdin) if len(p) == 2]
        complete(items)
    elif args.cmd == "stats":
        json.dump(stats(), sys.stdout)
    elif args.cmd == "reconcile":
        reconcile()


if __name__ == "__main__":
    main()
