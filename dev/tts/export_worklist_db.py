"""export_worklist_db.py — package the TTS work still to do as a small sqlite.

The TTS machine (the 4070 laptop since MSL went away, Nov 2026) doesn't need
the 860 MB mirror: the generator reads only `tossups`. This writes the
in-scope tossups (ttscorpus.scope_where: DIFFS + VOICE_SETS) that aren't in
the published HF manifest yet — a few MB — to copy over and point
LOS_TTS_DB at. The default output is committed (dev/tts/worklist/), so the
handoff is: export here -> commit + push -> `git pull` on the TTS machine.

  python dev/tts/export_worklist_db.py --mirror mirror/qbreader.sqlite
  (add --include-published to package every in-scope tossup regardless)

Also copies the mirror's id_remap table (if any) so remap_audio.py can run
against the same file on the TTS machine.
"""
import argparse
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from ttscorpus import published_ids, scope_where

DEFAULT_OUT = Path(__file__).resolve().parent / "worklist" / "tts_worklist.sqlite"


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--mirror", type=Path, required=True)
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT,
                    help="default: dev/tts/worklist/tts_worklist.sqlite (committed)")
    ap.add_argument("--include-published", action="store_true")
    args = ap.parse_args()

    published = set() if args.include_published else published_ids()
    if published is None:
        sys.exit("couldn't fetch the published manifest (use --include-published "
                 "to package everything in scope)")
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.unlink(missing_ok=True)
    out = sqlite3.connect(args.out)
    out.execute("ATTACH DATABASE ? AS m", (str(args.mirror),))
    where, params = scope_where()
    out.execute("CREATE TEMP TABLE skip (id TEXT PRIMARY KEY)")
    out.executemany("INSERT OR IGNORE INTO skip VALUES (?)", [(q,) for q in published])
    out.execute(f"CREATE TABLE tossups AS SELECT * FROM m.tossups WHERE {where} "
                f"AND id NOT IN (SELECT id FROM skip)", params)
    out.execute("CREATE INDEX idx_tossups_set ON tossups(set_name)")
    has_remap = out.execute("SELECT 1 FROM m.sqlite_master WHERE name = 'id_remap'").fetchone()
    if has_remap:
        out.execute("CREATE TABLE id_remap AS SELECT * FROM m.id_remap")
    out.commit()
    rows = out.execute("SELECT set_name, COUNT(*) FROM tossups GROUP BY 1 "
                       "ORDER BY 2 DESC").fetchall()
    out.close()
    total = sum(n for _, n in rows)
    print(f"{args.out}: {total:,} tossups in {len(rows)} set(s)"
          + (" + id_remap" if has_remap else ""))
    for name, n in rows[:20]:
        print(f"  {n:5,}  {name}")


if __name__ == "__main__":
    main()
