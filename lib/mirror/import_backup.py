"""import_backup.py — Seed the mirror from an official qbreader backup.

qbreader publishes full database dumps (linked from
https://www.qbreader.org/db/backups, Google Drive). The most recent
backup includes mongoexport JSON alongside the BSON: one document per
line, extended-JSON wrappers around ids/numbers/dates. Download
sets.json, packets.json, tossups.json, bonuses.json into mirror/raw/
and run:

    python lib/mirror/import_backup.py

This is a full rebuild: existing question tables are dropped and
re-imported (~330k docs, a couple of minutes). Incremental updates after
seeding go through lib/mirror/sync.py instead.
"""
import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from lib.common import MIRROR_DIR
from lib.mirror import db as mirror_db

BATCH_SIZE = 5000

COLLECTIONS = [
    ("sets", mirror_db.flatten_set),
    ("packets", mirror_db.flatten_packet),
    ("tossups", mirror_db.flatten_tossup),
    ("bonuses", mirror_db.flatten_bonus),
]


def import_collection(conn, raw_dir: Path, table: str, flatten) -> int:
    path = raw_dir / f"{table}.json"
    if not path.exists():
        raise FileNotFoundError(f"{path} missing — download it from the "
                                f"qbreader backup folder first")
    print(f"Importing {table} from {path}...")
    count, batch = 0, []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            doc = mirror_db.decode_extended(json.loads(line))
            batch.append(flatten(doc))
            count += 1
            if len(batch) >= BATCH_SIZE:
                mirror_db.upsert_rows(conn, table, batch)
                batch = []
                if count % 50000 == 0:
                    print(f"    {count}...")
    mirror_db.upsert_rows(conn, table, batch)
    print(f"    {count} {table} imported")
    return count


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--raw-dir", type=Path, default=MIRROR_DIR / "raw",
                        help="directory holding the backup *.json dumps")
    parser.add_argument("--db", type=Path, default=mirror_db.DB_PATH)
    parser.add_argument("--backup-date", default="",
                        help="date of the backup being imported (recorded "
                             "in meta for sync bookkeeping)")
    args = parser.parse_args()

    start = time.time()
    conn = mirror_db.open_db(args.db, create=True)
    try:
        for table, _ in COLLECTIONS:
            conn.execute(f"DELETE FROM {table}")
        for table, flatten in COLLECTIONS:
            with conn:
                import_collection(conn, args.raw_dir, table, flatten)
        with conn:
            mirror_db.set_meta(conn, "seeded_from_backup", args.backup_date)
            mirror_db.set_meta(conn, "imported_at",
                               time.strftime("%Y-%m-%dT%H:%M:%S"))
        conn.execute("VACUUM")
    finally:
        conn.close()

    print(f"Done in {time.time() - start:.0f}s → {args.db}")


if __name__ == "__main__":
    main()
