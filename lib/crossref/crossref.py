#!/usr/bin/env python3
"""Cross-reference index for stock guides.

Maintains output/topic_index.json — a lookup of all topics and works.
The LLM uses this during analysis to add cross_refs to each page.

Usage:
    python3 lib/crossref.py                    # rebuild index
    python3 lib/crossref.py --lookup "Kant"    # look up a name
    python3 lib/crossref.py --lookup "Guernica"
"""
import json, re, sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
INDEX_FILE = ROOT / 'output' / 'topic_index.json'


def rebuild_index():
    """Rebuild topic_index.json from all analysis JSONs."""
    index = {}

    for f in sorted((ROOT / 'output').glob('*/analysis.json')):
        with open(f) as fh:
            data = json.load(fh)
        slug = f.parent.name
        topic = data.get('topic', '')
        cat = data.get('category', '')

        entry = {'slug': slug, 'topic': topic, 'type': 'topic', 'category': cat}

        # Full name
        index[topic] = entry

        # Last name for multi-word names
        parts = topic.split()
        if len(parts) >= 2:
            last = parts[-1]
            skip = {'the', 'van', 'von', 'de', 'del', 'di', 'der', 'den', 'le', 'la', 'el'}
            if last.lower() not in skip and len(last) >= 3:
                index.setdefault(last, entry)

        # Works
        for w in data.get('works', []):
            wname = w.get('name', '')
            if any(x in wname for x in ['General', 'Biographical', 'Other Works', 'Other ']):
                continue

            work_entry = {
                'slug': slug, 'topic': topic, 'type': 'work',
                'work': wname, 'category': cat,
            }
            index[wname] = work_entry

            # Clean name without parentheticals
            clean = re.sub(r'\s*\(.*?\)', '', wname).strip()
            if clean != wname and len(clean) > 3:
                index.setdefault(clean, work_entry)
            if '/' in clean:
                first_part = clean.split('/')[0].strip()
                if len(first_part) > 3:
                    index.setdefault(first_part, work_entry)

    with open(INDEX_FILE, 'w') as f:
        json.dump(index, f, indent=2, ensure_ascii=False)

    topics_count = len(set(v['slug'] for v in index.values()))
    print(f'Index rebuilt: {len(index)} entries across {topics_count} topics', flush=True)
    return index


def lookup(name, index=None):
    """Look up a name in the index. Returns the entry or None."""
    if index is None:
        if INDEX_FILE.exists():
            with open(INDEX_FILE) as f:
                index = json.load(f)
        else:
            return None
    return index.get(name)


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--lookup', help='Look up a name')
    args = parser.parse_args()

    index = rebuild_index()

    if args.lookup:
        entry = lookup(args.lookup, index)
        if entry:
            target = entry['topic']
            if entry['type'] == 'work':
                target += f" / {entry['work']}"
            print(f'"{args.lookup}" -> {target} (output/{entry["slug"]}/stock.html)')
        else:
            print(f'"{args.lookup}" -> NOT FOUND (would be a red link)')


if __name__ == '__main__':
    main()
