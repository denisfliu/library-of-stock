#!/usr/bin/env python3
"""
migrate_to_topic_dirs.py — One-time migration to per-topic directory structure.

Moves all files from the flat output/ structure to per-topic directories:
  output/{slug}_analysis.json       → output/{slug}/analysis.json
  output/{slug}_stock.html          → output/{slug}/stock.html
  output/{slug}_cards.html          → output/{slug}/cards.html
  output/{slug}_questions.html      → output/{slug}/questions.html
  output/{slug}_clues.txt           → output/{slug}/clues.txt
  output/audio/{slug}/N.mp3         → output/{slug}/audio/N.mp3
  cache/{key}.json (via cache_file) → output/{slug}/{key}.json
  cache/{key}_mentions.json         → output/{slug}/{key}_mentions.json

Also updates mp3 paths in analysis.json score_clues:
  "audio/{slug}/N.mp3" → "audio/N.mp3"

And updates cache_file field to just the filename (no "cache/" prefix).

Usage:
    python3 lib/migrate_to_topic_dirs.py [--dry-run]
"""

import json
import shutil
import sys
from pathlib import Path

DRY_RUN = "--dry-run" in sys.argv
ROOT = Path(__file__).parent.parent
OUTPUT_DIR = ROOT / "output"
CACHE_DIR = ROOT / "cache"
OLD_AUDIO_DIR = OUTPUT_DIR / "audio"


def migrate():
    analysis_files = sorted(OUTPUT_DIR.glob("*_analysis.json"))
    if not analysis_files:
        print("No analysis JSON files found in output/. Already migrated?")
        return

    print(f"Found {len(analysis_files)} analysis JSON files to migrate.")
    if DRY_RUN:
        print("[DRY RUN — no files will be moved]")
    print()

    migrated = 0
    cache_matched = 0
    cache_missing = 0
    mp3_updated = 0

    for json_path in analysis_files:
        slug = json_path.stem.replace("_analysis", "")
        topic_dir = OUTPUT_DIR / slug

        # Skip if already migrated (topic dir exists with analysis.json inside)
        if (topic_dir / "analysis.json").exists():
            print(f"  SKIP {slug}: already migrated")
            continue

        print(f"  {slug}")

        if not DRY_RUN:
            topic_dir.mkdir(exist_ok=True)

        # Load analysis JSON
        with open(json_path) as f:
            analysis = json.load(f)

        # --- Update mp3 paths in score_clues ---
        changed_mp3 = False
        for clue in analysis.get("score_clues", []):
            mp3 = clue.get("mp3", "")
            # Old format: "audio/{slug}/N.mp3" → new: "audio/N.mp3"
            old_prefix = f"audio/{slug}/"
            if mp3.startswith(old_prefix):
                new_mp3 = "audio/" + mp3[len(old_prefix):]
                clue["mp3"] = new_mp3
                changed_mp3 = True
                mp3_updated += 1

        # --- Handle cache file ---
        recorded_cache = analysis.get("cache_file", "")
        if recorded_cache:
            # Remove "cache/" prefix if present (old style)
            if recorded_cache.startswith("cache/"):
                recorded_cache = recorded_cache[len("cache/"):]

            src_cache = CACHE_DIR / recorded_cache
            dst_cache = topic_dir / recorded_cache

            if src_cache.exists():
                if not DRY_RUN:
                    shutil.copy2(src_cache, dst_cache)
                # Also copy _mentions.json if it exists
                mentions_name = recorded_cache.replace(".json", "_mentions.json")
                src_mentions = CACHE_DIR / mentions_name
                if src_mentions.exists():
                    if not DRY_RUN:
                        shutil.copy2(src_mentions, topic_dir / mentions_name)
                # Update cache_file to just the filename
                analysis["cache_file"] = recorded_cache
                cache_matched += 1
            else:
                print(f"    WARNING: cache_file '{recorded_cache}' not found in cache/")
                # Still update to remove cache/ prefix
                analysis["cache_file"] = recorded_cache
                cache_missing += 1

        # --- Save updated analysis.json to new location ---
        if not DRY_RUN:
            with open(topic_dir / "analysis.json", "w") as f:
                json.dump(analysis, f, indent=2, ensure_ascii=False)

        # --- Move other output files ---
        for suffix, new_name in [
            ("_stock.html", "stock.html"),
            ("_cards.html", "cards.html"),
            ("_questions.html", "questions.html"),
            ("_clues.txt", "clues.txt"),
        ]:
            src = OUTPUT_DIR / f"{slug}{suffix}"
            if src.exists():
                if not DRY_RUN:
                    shutil.move(str(src), topic_dir / new_name)

        # --- Move audio directory ---
        old_audio = OLD_AUDIO_DIR / slug
        if old_audio.exists():
            new_audio = topic_dir / "audio"
            if not DRY_RUN:
                shutil.move(str(old_audio), new_audio)

        # --- Remove the original analysis JSON ---
        if not DRY_RUN:
            json_path.unlink()

        migrated += 1

    # --- Remove old audio/ directory if empty ---
    if not DRY_RUN and OLD_AUDIO_DIR.exists():
        try:
            OLD_AUDIO_DIR.rmdir()  # only removes if empty
            print(f"\nRemoved empty {OLD_AUDIO_DIR}")
        except OSError:
            remaining = list(OLD_AUDIO_DIR.iterdir())
            print(f"\nWARNING: {OLD_AUDIO_DIR} not empty — {len(remaining)} items remain")
            for item in remaining[:5]:
                print(f"  {item.name}")

    # --- Report unmatched cache files ---
    if not DRY_RUN:
        topic_slugs = {d.name for d in OUTPUT_DIR.iterdir() if d.is_dir() and d.name not in ("audio",)}
        copied_cache_files = set()
        for slug_dir in OUTPUT_DIR.iterdir():
            if not slug_dir.is_dir():
                continue
            for f in slug_dir.glob("*_d*.json"):
                if "_mentions" not in f.name:
                    copied_cache_files.add(f.name)

        all_cache_files = {f.name for f in CACHE_DIR.glob("*_d*.json") if "_mentions" not in f.name}
        unmatched = all_cache_files - copied_cache_files
        if unmatched:
            print(f"\nUnmatched cache files still in cache/ ({len(unmatched)}):")
            for name in sorted(unmatched)[:20]:
                print(f"  {name}")
            if len(unmatched) > 20:
                print(f"  ... and {len(unmatched) - 20} more")

    print(f"\nMigration complete:")
    print(f"  Topics migrated: {migrated}")
    print(f"  Cache files copied: {cache_matched}")
    print(f"  Cache files missing: {cache_missing}")
    print(f"  MP3 paths updated: {mp3_updated}")
    if DRY_RUN:
        print("\n[DRY RUN — no files were actually moved]")


if __name__ == "__main__":
    migrate()
