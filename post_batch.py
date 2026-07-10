#!/usr/bin/env python
"""
post_batch.py — Run all post-batch steps after analysis agents finish.

Usage:
    python post_batch.py

Steps:
  1. Rebuild cross-ref index (lib/crossref/crossref.py)
  2. Deterministic crossref backfill (lib/crossref/backfill_crossrefs.py)
  3. Print card-agent prompts (chunked topics; agents follow the /cards skill)
  4. Print the crossref-agent prompt (follows the /crossref skill)

After BOTH agent kinds finish, run: ./build.sh
"""

import json
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib.common import ROOT, OUTPUT_DIR, QUEUE_DIR

BATCH_FILE = QUEUE_DIR / 'current_batch.json'
CARD_BATCH_SIZE = 4  # 3-5 topics per card agent


def resolve_completed_topics(completed):
    """Map completed batch items to (canonical topic, slug) via analysis JSONs.

    Batch 'topic' strings may be mangled (short names, accents stripped),
    so match against every analysis.json by name and slug.
    """
    index = {}  # normalized name -> (canonical_topic, slug)
    for json_path in OUTPUT_DIR.glob('*/analysis.json'):
        slug = json_path.parent.name
        with open(json_path, encoding='utf-8') as f:
            data = json.load(f)
        canonical = data.get('topic', '')
        index[canonical.lower()] = (canonical, slug)
        index[slug.replace('_', ' ')] = (canonical, slug)

    def substr_match(needle):
        for key, val in index.items():
            if needle in key or key in needle:
                return val
        return None

    seen_slugs = set()
    resolved = []
    for item in completed:
        raw_lower = item['topic'].strip().lower()
        slug_clean = re.sub(r'[^a-z0-9]+', '_', raw_lower).strip('_')
        match = (index.get(raw_lower)
                 or index.get(slug_clean.replace('_', ' '))
                 or substr_match(raw_lower))
        if match and match[1] not in seen_slugs:
            resolved.append(match)
            seen_slugs.add(match[1])
        # No match: mangled duplicate with no corresponding JSON — skip.
    return resolved


def main():
    if not BATCH_FILE.exists():
        print('ERROR: queue/current_batch.json not found.')
        sys.exit(1)

    with open(BATCH_FILE, encoding='utf-8') as f:
        batch = json.load(f)

    completed = batch.get('completed', [])
    in_progress = batch.get('in_progress', [])

    if in_progress:
        print(f'WARNING: {len(in_progress)} topics still in progress:')
        for item in in_progress:
            print(f'  - {item["topic"]}')
        print()

    topics = resolve_completed_topics(completed)
    if not topics:
        print('No completed topics found in current batch.')
        sys.exit(0)

    print(f'Batch: {batch.get("name", "unknown")}')
    print(f'Completed topics: {len(topics)}')

    # Step 1: Rebuild cross-ref index
    print('\n[1/4] Rebuilding cross-reference index...')
    result = subprocess.run([sys.executable, 'lib/crossref/crossref.py'], cwd=ROOT)
    if result.returncode != 0:
        print('ERROR: crossref rebuild failed')
        sys.exit(1)

    # Step 2: Deterministic backfill (fast, no LLM needed)
    print('\n[2/4] Running deterministic crossref backfill...')
    result = subprocess.run([sys.executable, 'lib/crossref/backfill_crossrefs.py'], cwd=ROOT)
    if result.returncode != 0:
        print('ERROR: backfill_crossrefs.py failed')
        sys.exit(1)

    # Step 3: Card agent prompts (run in parallel with the crossref agent)
    chunks = [topics[i:i + CARD_BATCH_SIZE]
              for i in range(0, len(topics), CARD_BATCH_SIZE)]
    print(f'\n[3/4] Launch {len(chunks)} card agent(s) '
          f'({CARD_BATCH_SIZE} topics each) in parallel with the crossref agent:\n')
    for idx, chunk in enumerate(chunks, 1):
        topic_list = '\n'.join(f'- {name} -> output/{slug}/analysis.json'
                               for name, slug in chunk)
        print(f'--- Card agent {idx}/{len(chunks)} ({len(chunk)} topics) ---')
        print('=' * 60)
        print(f"""Follow the /cards skill for each of these {len(chunk)} topics, in order
(working directory: {ROOT}):

{topic_list}

Finish all topics before rendering. After the last topic:
    python lib/render/render_cards.py
Do NOT ask for confirmation.""")
        print('=' * 60)
        print()

    # Step 4: Crossref agent prompt
    topic_names = '\n'.join(f'- {name}' for name, _ in topics)
    print('\n[4/4] Launch this crossref backfill agent for richer semantic links:\n')
    print('=' * 60)
    print(f"""Follow the /crossref skill for full instructions.

Add cross_refs to these topics (working directory: {ROOT}):
{topic_names}

Important: Don't modify any field except cross_refs. Don't add refs for the
topic itself. Do not run any render scripts — the controller runs ./build.sh
after you finish.""")
    print('=' * 60)
    print()
    print('After BOTH agents finish, run:')
    print('  ./build.sh')


if __name__ == '__main__':
    main()
