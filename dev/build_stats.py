#!/usr/bin/env python3
"""Generate dev/stats_data.json for the stats visualization page."""

import json
import glob
import os
from collections import defaultdict

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), '..', 'output')
OUT_FILE = os.path.join(os.path.dirname(__file__), 'stats_data.json')

def main():
    files = sorted(glob.glob(os.path.join(OUTPUT_DIR, '*/analysis.json')))
    print(f"Reading {len(files)} analysis.json files...")

    summary = {
        'total_topics': 0,
        'total_works': 0,
        'total_cards': 0,
        'second_pass_done': 0,
        'topics_with_images': 0,
        'works_with_images': 0,
        'score_clues_total': 0,
        'score_clues_needs_review': 0,
    }

    # cat -> subcat -> {topics, second_pass, topics_with_images, works, works_with_images}
    cat_data = defaultdict(lambda: defaultdict(lambda: {
        'topics': 0,
        'second_pass': 0,
        'topics_with_images': 0,
        'total_works': 0,
        'works_with_images': 0,
        'total_cards': 0,
    }))

    score_clue_rows = []

    for f in files:
        with open(f) as fp:
            try:
                d = json.load(fp)
            except json.JSONDecodeError:
                continue

        slug = os.path.basename(os.path.dirname(f))
        cat = d.get('category') or 'Unknown'
        subcat = d.get('subcategory') or '(none)'
        works = d.get('works', [])
        cards = d.get('cards', [])
        score_clues = d.get('score_clues', [])
        has_images = any(w.get('images') for w in works)
        second_pass = bool(d.get('second_pass'))

        summary['total_topics'] += 1
        summary['total_works'] += len(works)
        summary['total_cards'] += len(cards)
        if second_pass:
            summary['second_pass_done'] += 1
        if has_images:
            summary['topics_with_images'] += 1
        summary['works_with_images'] += sum(1 for w in works if w.get('images'))
        summary['score_clues_total'] += len(score_clues)
        summary['score_clues_needs_review'] += sum(1 for sc in score_clues if sc.get('needs_review'))

        bucket = cat_data[cat][subcat]
        bucket['topics'] += 1
        bucket['total_works'] += len(works)
        bucket['works_with_images'] += sum(1 for w in works if w.get('images'))
        bucket['total_cards'] += len(cards)
        if second_pass:
            bucket['second_pass'] += 1
        if has_images:
            bucket['topics_with_images'] += 1

        if score_clues:
            needs_review = sum(1 for sc in score_clues if sc.get('needs_review'))
            score_clue_rows.append({
                'topic': d.get('topic', slug),
                'slug': slug,
                'category': cat,
                'subcategory': subcat,
                'total': len(score_clues),
                'needs_review': needs_review,
                'reviewed': len(score_clues) - needs_review,
            })

    score_clue_rows.sort(key=lambda r: r['topic'])

    # Flatten cat_data into a list sorted by topic count desc
    categories = []
    for cat, subcats in sorted(cat_data.items()):
        cat_total = {'topics': 0, 'second_pass': 0, 'topics_with_images': 0,
                     'total_works': 0, 'works_with_images': 0, 'total_cards': 0}
        subcat_list = []
        for subcat, vals in sorted(subcats.items(), key=lambda x: -x[1]['topics']):
            for k in cat_total:
                cat_total[k] += vals[k]
            subcat_list.append({'name': subcat, **vals})
        categories.append({'name': cat, **cat_total, 'subcategories': subcat_list})

    categories.sort(key=lambda c: -c['topics'])

    data = {
        'summary': summary,
        'categories': categories,
        'score_clues': score_clue_rows,
    }

    with open(OUT_FILE, 'w') as fp:
        json.dump(data, fp, indent=2)

    print(f"Written -> {OUT_FILE}")
    print(f"  {summary['total_topics']} topics, {summary['total_works']} works, "
          f"{summary['second_pass_done']} 2nd pass, "
          f"{summary['score_clues_total']} score clues")

if __name__ == '__main__':
    main()
