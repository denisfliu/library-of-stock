"""sync.py — Pull new/updated sets from qbreader into the mirror.

After the one-time backup seed (lib/mirror/import_backup.py), this is
the pipeline's ONLY live-API dependency: it diffs /api/set-list against
the mirror's sets table and fetches whole missing sets through the
rate-limited packet endpoint (~1 request per packet). Question edits
inside already-mirrored sets are picked up by --refresh (or by
re-seeding from a newer backup).

    python lib/mirror/sync.py                  # fetch sets missing from the mirror
    python lib/mirror/sync.py --dry-run        # list what would be fetched
    python lib/mirror/sync.py --refresh "2026 PACE NSC"   # force-refetch a set
"""
import argparse
import sys
import time
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from lib.mirror import db as mirror_db
from lib.pipeline import fetch


def sync_set(conn, set_name: str, use_cache: bool) -> tuple[int, int]:
    """Fetch every packet of a set and upsert it. Returns (tossups, bonuses)."""
    data = fetch.api_fetch_set(set_name, use_cache=use_cache)
    tossups, bonuses = [], []
    for packet in data["packets"]:
        tossups.extend(packet.get("tossups", []))
        bonuses.extend(packet.get("bonuses", []))

    questions = tossups + bonuses
    if not questions:
        print(f"    WARNING: '{set_name}' returned no questions — skipped")
        return 0, 0

    # Set/packet rows come from the embedded objects on the questions.
    # The embedded set carries no set-level difficulty; use the modal
    # question difficulty as a best-effort stand-in.
    set_doc = dict(questions[0]["set"])
    difficulties = Counter(q.get("difficulty") for q in questions
                           if q.get("difficulty") is not None)
    set_doc.setdefault("difficulty",
                       difficulties.most_common(1)[0][0] if difficulties else None)

    packet_docs = {}
    for q in questions:
        p = q.get("packet") or {}
        if p.get("_id") and p["_id"] not in packet_docs:
            packet_docs[p["_id"]] = {**p, "set": {"_id": set_doc["_id"],
                                                  "name": set_doc["name"]}}

    with conn:
        mirror_db.upsert_rows(conn, "sets", [mirror_db.flatten_set(set_doc)])
        mirror_db.upsert_rows(conn, "packets",
                              [mirror_db.flatten_packet(p)
                               for p in packet_docs.values()])
        mirror_db.upsert_rows(conn, "tossups",
                              [mirror_db.flatten_tossup(t) for t in tossups])
        mirror_db.upsert_rows(conn, "bonuses",
                              [mirror_db.flatten_bonus(b) for b in bonuses])
    return len(tossups), len(bonuses)


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--db", type=Path, default=mirror_db.DB_PATH)
    parser.add_argument("--dry-run", action="store_true",
                        help="list missing sets without fetching")
    parser.add_argument("--refresh", action="append", default=[],
                        metavar="SET_NAME",
                        help="force-refetch this set even if already mirrored "
                             "(repeatable)")
    args = parser.parse_args()

    conn = mirror_db.open_db(args.db)
    live_sets = fetch.api_set_list()
    mirrored = {row["name"] for row in
                conn.execute("SELECT name FROM sets").fetchall()}

    missing = [s for s in live_sets if s not in mirrored]
    gone = sorted(mirrored - set(live_sets))
    if gone:
        print(f"NOTE: {len(gone)} mirrored set(s) no longer on qbreader "
              f"(renamed or removed upstream): {', '.join(gone[:10])}"
              + (" ..." if len(gone) > 10 else ""))

    todo = missing + [s for s in args.refresh if s not in missing]
    print(f"{len(live_sets)} sets live, {len(mirrored)} mirrored, "
          f"{len(missing)} missing, {len(args.refresh)} refresh requested")
    if args.dry_run or not todo:
        for s in todo:
            print(f"  would fetch: {s}")
        if not todo:
            print("Mirror is up to date.")
        return

    total_t = total_b = 0
    for i, set_name in enumerate(todo, 1):
        print(f"[{i}/{len(todo)}] {set_name}")
        t, b = sync_set(conn, set_name, use_cache=set_name not in args.refresh)
        total_t += t
        total_b += b

    with conn:
        mirror_db.set_meta(conn, "last_sync", time.strftime("%Y-%m-%dT%H:%M:%S"))
    conn.close()
    print(f"Done: {len(todo)} sets, +{total_t} tossups, +{total_b} bonuses")


if __name__ == "__main__":
    main()
