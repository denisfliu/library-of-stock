"""
rerender.py — Re-render all stock.html study guides from analysis.json.

The JSON is the source of truth; HTML is never parsed or written back
to JSON. Incremental by default (skips pages whose HTML is newer than
their JSON); pass --force to re-render everything.

Usage:
    python lib/rerender.py [--force]
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from lib.common import OUTPUT_DIR
from lib.render.render import render_html


def main():
    force = "--force" in sys.argv

    count = 0
    skipped_up_to_date = 0
    skipped_orphan = 0
    for json_path in sorted(OUTPUT_DIR.glob("*/analysis.json")):
        stock_path = json_path.parent / "stock.html"

        # Incremental: skip if HTML is newer than JSON (unless --force)
        if not force and stock_path.exists() and stock_path.stat().st_mtime >= json_path.stat().st_mtime:
            skipped_up_to_date += 1
            continue

        with open(json_path, encoding='utf-8') as f:
            analysis = json.load(f)

        total_clues = sum(len(w.get("clues", [])) for w in analysis.get("works", []))
        total_images = sum(len(w.get("images", [])) for w in analysis.get("works", []))
        topic = analysis.get("topic", "?")
        print(f"  {topic}: {len(analysis.get('works', []))} works, {total_clues} clues, {total_images} images")

        render_html(analysis, stock_path)
        count += 1

    # Warn about orphaned HTML files with no JSON
    for html_path in sorted(OUTPUT_DIR.glob("*/stock.html")):
        json_path = html_path.parent / "analysis.json"
        if not json_path.exists():
            print(f"  WARNING: {html_path.parent.name}/stock.html has no analysis.json — skipped")
            skipped_orphan += 1

    parts = [f"Re-rendered {count} guides"]
    if skipped_up_to_date:
        parts.append(f"{skipped_up_to_date} up-to-date")
    if skipped_orphan:
        parts.append(f"{skipped_orphan} orphaned HTML")
    print(f"\nDone! {', '.join(parts)}.")


if __name__ == "__main__":
    main()
