#!/usr/bin/env python3
"""Generate dev/crossrefs_data.json for the crossref graph visualization."""

import json
import glob
import os

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), '..', 'output')
OUT_FILE = os.path.join(os.path.dirname(__file__), 'crossrefs_data.json')

def main():
    files = sorted(glob.glob(os.path.join(OUTPUT_DIR, '*/analysis.json')))
    print(f"Reading {len(files)} analysis.json files...")

    nodes = {}  # slug -> {id, label, category, out_degree}
    links = []  # {source, target}
    in_degree = {}  # slug -> count

    for f in files:
        with open(f) as fp:
            try:
                d = json.load(fp)
            except json.JSONDecodeError:
                continue

        slug = os.path.basename(os.path.dirname(f))
        topic = d.get('topic', slug)
        category = d.get('category', 'Unknown')
        refs = [r for r in d.get('cross_refs', []) if r.get('exists') and r.get('target_slug')]

        nodes[slug] = {
            'id': slug,
            'label': topic,
            'category': category,
            'out_degree': len(refs),
        }
        if slug not in in_degree:
            in_degree[slug] = 0

        for r in refs:
            target = r['target_slug']
            links.append({'source': slug, 'target': target})
            in_degree[target] = in_degree.get(target, 0) + 1

    # Attach in_degree and filter to nodes that appear in the graph
    active_slugs = set(n['id'] for n in nodes.values())
    # Also ensure target nodes that aren't source nodes get added (shouldn't happen if all exist, but just in case)
    for slug, count in in_degree.items():
        if slug not in nodes:
            # Referenced but no analysis.json - skip
            pass
        else:
            nodes[slug]['in_degree'] = count

    for slug in nodes:
        if 'in_degree' not in nodes[slug]:
            nodes[slug]['in_degree'] = 0

    # Filter links to only those where both endpoints exist
    valid_slugs = set(nodes.keys())
    links = [l for l in links if l['source'] in valid_slugs and l['target'] in valid_slugs]

    data = {
        'nodes': list(nodes.values()),
        'links': links,
    }

    with open(OUT_FILE, 'w') as fp:
        json.dump(data, fp, separators=(',', ':'))

    print(f"Written {len(data['nodes'])} nodes, {len(data['links'])} links -> {OUT_FILE}")

if __name__ == '__main__':
    main()
