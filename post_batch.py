#!/usr/bin/env python3
"""
post_batch.py — Prepare post-batch steps and print the Sonnet crossref agent prompt.

Usage:
    python3 post_batch.py

Reads completed topics from queue/current_batch.json, rebuilds the cross-ref index,
and prints the ready-to-use Sonnet agent prompt. The controller then:
  1. Launches the Sonnet agent with the printed prompt
  2. After Sonnet finishes, runs: render_cards.py, render_questions.py
"""

import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parent
BATCH_FILE = ROOT / 'queue' / 'current_batch.json'


def main():
    if not BATCH_FILE.exists():
        print("ERROR: queue/current_batch.json not found.")
        sys.exit(1)

    with open(BATCH_FILE) as f:
        batch = json.load(f)

    completed = batch.get('completed', [])
    in_progress = batch.get('in_progress', [])

    if in_progress:
        print(f"WARNING: {len(in_progress)} topics still in progress:")
        for item in in_progress:
            print(f"  - {item['topic']}")
        print()

    # Build a lookup from all analysis JSONs: normalized topic name -> (topic, slug)
    output_dir = ROOT / 'output'
    index = {}  # normalized name -> (canonical_topic, slug)
    for json_path in output_dir.glob('*_analysis.json'):
        slug = json_path.stem.replace('_analysis', '')
        with open(json_path) as f:
            data = json.load(f)
        canonical = data.get('topic', '')
        # Index by canonical name and by slug-derived name (handles accents, punctuation)
        index[canonical.lower()] = (canonical, slug)
        index[slug.replace('_', ' ')] = (canonical, slug)

    # Resolve completed items to canonical topic names, deduplicate by slug
    seen_slugs = set()
    topics = []
    for item in completed:
        raw = item['topic']
        # Try exact match, then slug-based match, then strip non-alpha match
        raw_lower = raw.strip().lower()
        slug_guess = raw_lower.replace(' ', '_')  # matches pipeline slug logic
        slug_clean = re.sub(r'[^a-z0-9]+', '_', raw_lower).strip('_')

        # Substring fallback: "Strange Loop" matches "A Strange Loop"
        def _substr_match(needle):
            for key, val in index.items():
                if needle in key or key in needle:
                    return val
            return None

        match = (index.get(raw_lower)
                 or index.get(slug_guess.replace('_', ' '))
                 or index.get(slug_clean.replace('_', ' '))
                 or _substr_match(raw_lower))
        if match:
            canonical, slug = match
            if slug not in seen_slugs:
                topics.append(canonical)
                seen_slugs.add(slug)
        # If no match found, skip (mangled duplicate with no corresponding JSON)

    if not topics:
        print("No completed topics found in current batch.")
        sys.exit(0)

    print(f"Batch: {batch.get('name', 'unknown')}")
    print(f"Completed topics: {len(topics)}")

    # Step 1: Rebuild cross-ref index
    print("\n[1/2] Rebuilding cross-reference index...")
    result = subprocess.run("python3 lib/crossref.py", shell=True, cwd=ROOT)
    if result.returncode != 0:
        print("ERROR: crossref rebuild failed")
        sys.exit(1)

    # Step 2: Print Sonnet agent prompt
    topic_list = "\n".join(f"- {t}" for t in topics)
    print("\n[2/2] Launch this Sonnet crossref backfill agent:\n")
    print("=" * 60)
    print(f"""Read /home/laufey/code/stock/docs/crossref_backfill.md for full instructions.

Add cross_refs to these topics (working directory: /home/laufey/code/stock):
{topic_list}

For each topic:
1. Read output/{{slug}}_analysis.json
2. Read output/topic_index.json
3. Scan all text fields for mentions of indexed topics/works
4. Add cross_refs array
5. Save the JSON

After all topics:
```
python3 rerender.py
python3 build_index.py
```

Important: Don't modify any field except cross_refs. Don't add refs for the topic itself.""")
    print("=" * 60)
    print()
    print("After the Sonnet agent finishes, run:")
    print("  python3 render_cards.py && python3 render_questions.py")


if __name__ == '__main__':
    main()
