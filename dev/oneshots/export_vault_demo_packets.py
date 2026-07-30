"""One-shot: export 2025 VAULT packets 1-3 from the qbreader mirror into
qb-td's demo packet sources (../qb-td/tools/demo/round{1,2,3}.json).

The demo tournament (qb-td app/demo.html) ships three real packets; this
regenerates its committed sources from the mirror. Formatted text is kept,
with <i> converted to <em> because MODAQ's FormattedTextParser throws on
unknown tags (it supports b/u/em/req/sub/sup only). Run from repo root:

    python dev/oneshots/export_vault_demo_packets.py
"""
import json
import re
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from lib.common import ROOT  # noqa: E402

SET_NAME = "2025 VAULT"
PACKETS = [1, 2, 3]
OUT_DIR = ROOT.parent / "qb-td" / "tools" / "demo"

I_TAG = re.compile(r"<(/?)i>", re.IGNORECASE)


def modaq_text(s):
    """qbreader formatted text -> MODAQ-safe formatted text."""
    return I_TAG.sub(r"<\1em>", s or "").strip()


def main():
    db = sqlite3.connect(ROOT / "mirror" / "qbreader.sqlite")
    db.row_factory = sqlite3.Row
    sid_row = db.execute("SELECT id FROM sets WHERE name = ?", (SET_NAME,)).fetchone()
    if not sid_row:
        raise SystemExit(f"set not in mirror: {SET_NAME}")
    sid = sid_row["id"]

    for n in PACKETS:
        pid = db.execute(
            "SELECT id FROM packets WHERE set_id = ? AND number = ?", (sid, n)
        ).fetchone()["id"]
        tossups = [
            {
                "question": modaq_text(t["question"]),
                "answer": modaq_text(t["answer"]),
                "category": t["category"],
                "subcategory": t["subcategory"] or "",
            }
            for t in db.execute(
                "SELECT * FROM tossups WHERE packet_id = ? ORDER BY number", (pid,)
            )
        ]
        bonuses = [
            {
                "leadin": modaq_text(b["leadin"]),
                "parts": [modaq_text(p) for p in json.loads(b["parts"])],
                "answers": [modaq_text(a) for a in json.loads(b["answers"])],
                "values": json.loads(b["values"]) if b["values"] else [10, 10, 10],
                "category": b["category"],
                "subcategory": b["subcategory"] or "",
            }
            for b in db.execute(
                "SELECT * FROM bonuses WHERE packet_id = ? ORDER BY number", (pid,)
            )
        ]
        out = {
            "name": f"{SET_NAME} Packet {n}",
            "tossups": tossups,
            "bonuses": bonuses,
        }
        path = OUT_DIR / f"round{n}.json"
        path.write_text(
            json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8"
        )
        print(f"{path}: {len(tossups)} TU / {len(bonuses)} B")


if __name__ == "__main__":
    main()
