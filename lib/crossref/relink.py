"""relink.py — re-derive mechanical cross_refs for every topic.

Replaces the old fill-only backfill: runs over ALL topics each time, so
old pages gain links when new topics get pages. Per topic it rewrites
the machine-owned refs (source "backfill"/"override") from a fresh
linker scan and preserves judgment refs (source "agent", or legacy refs
with no source) verbatim. Unresolvable ambiguous surfaces are queued in
dev/crossref_candidates.json for the /crossref adjudication agent
(decisions land in output/crossref_overrides.json and apply on the next
run — nothing is asked twice).

Local-only: it mutates analysis.json, so it runs via post_batch.py or
by hand, never in CI.

Usage:
    python lib/crossref/relink.py [--dry-run] [--topic SLUG]
"""
import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from lib.common import DEV_DIR, load_cards, resolve_analyses, write_json_if_changed
from lib.crossref.linker import Linker

CANDIDATES_FILE = DEV_DIR / 'crossref_candidates.json'

MACHINE_SOURCES = {'backfill', 'override'}


def get_text_fields(d: dict, cards: list) -> str:
    """All prose the linker scans: summaries, work names+descriptions,
    and the topic's cards."""
    texts = []
    if d.get('summary'):
        texts.append(d['summary'])
    if d.get('comprehensive_summary'):
        texts.append(d['comprehensive_summary'])
    for work in d.get('works', []):
        if work.get('name'):
            texts.append(work['name'])
        if work.get('description'):
            texts.append(work['description'])
    for card in cards:
        if card.get('clue'):
            texts.append(card['clue'])
        if card.get('answer'):
            texts.append(card['answer'])
    return '\n'.join(texts)


def relink_topic(linker: Linker, slug: str, d: dict) -> tuple[list, list]:
    """Compute the topic's new cross_refs list + open candidates."""
    preserved = [r for r in d.get('cross_refs') or []
                 if r.get('source', 'agent') not in MACHINE_SOURCES]
    preserved_targets = {(r.get('topic'), r.get('work')) for r in preserved}
    preserved_names = {r.get('name') for r in preserved}

    text = get_text_fields(d, load_cards(slug))
    refs, candidates = linker.scan(text, topic_slug=slug,
                                   topic_name=d.get('topic', ''),
                                   category=d.get('category', ''))

    new_refs = [r for r in refs
                if (r['topic'], r['work']) not in preserved_targets]
    # A surface an agent ref already covers needs no adjudication.
    open_candidates = [c for c in candidates
                       if c['surface'] not in preserved_names]
    return preserved + new_refs, open_candidates


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('--dry-run', action='store_true')
    ap.add_argument('--topic', help='relink only this slug')
    args = ap.parse_args()

    analyses = resolve_analyses()
    linker = Linker(analyses=analyses)
    print(f'Lexicon: {len(linker.auto)} canonical names, '
          f'{len(linker.gated)} gated surfaces, '
          f'{sum(len(v) for v in linker.overrides["per_topic"].values())} '
          f'per-topic + '
          f'{sum(len(v) for v in linker.overrides["global"].values())} '
          f'global overrides')

    changed = 0
    all_candidates = []
    totals = {'agent': 0, 'backfill': 0, 'override': 0}
    for slug, path, d in analyses:
        if args.topic and slug != args.topic:
            continue
        new_refs, open_candidates = relink_topic(linker, slug, d)
        for r in new_refs:
            totals[r.get('source', 'agent')] = \
                totals.get(r.get('source', 'agent'), 0) + 1
        for c in open_candidates:
            all_candidates.append({
                'slug': slug, 'topic': d.get('topic', slug),
                'category': d.get('category', ''), **c})

        if new_refs != (d.get('cross_refs') or []):
            changed += 1
            if not args.dry_run:
                d['cross_refs'] = new_refs
                write_json_if_changed(path, d)
            else:
                old = d.get('cross_refs') or []
                added = [r for r in new_refs if r not in old]
                removed = [r for r in old if r not in new_refs]
                print(f'  {slug}: +{len(added)} -{len(removed)}'
                      + (f"  (+ {', '.join(r['name'] for r in added[:4])})"
                         if added else ''))

    if not args.dry_run and not args.topic:
        # Grouped by surface so the adjudicator judges "Eliot" once
        # across all its instances (and may set one global rule).
        by_surface: dict[str, list] = {}
        for c in all_candidates:
            by_surface.setdefault(c['surface'], []).append(
                {k: c[k] for k in ('slug', 'topic', 'category',
                                   'snippet', 'targets')})
        surfaces = {s: {'instances': v}
                    for s, v in sorted(by_surface.items(),
                                       key=lambda kv: -len(kv[1]))}
        DEV_DIR.mkdir(exist_ok=True)
        write_json_if_changed(CANDIDATES_FILE, {
            'generated': time.strftime('%Y-%m-%d'),
            'count': len(all_candidates),
            'surfaces': surfaces,
        })

    print(f'Relink: {changed} topics {"would change" if args.dry_run else "updated"}; '
          f'refs by source {totals}; '
          f'{len(all_candidates)} open candidates'
          + ('' if args.dry_run or args.topic
             else f' -> {CANDIDATES_FILE}'))


if __name__ == '__main__':
    main()
