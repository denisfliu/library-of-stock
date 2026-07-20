"""build_set.py — Build/refresh a tournament sweep page.

Fetches every packet of a set, extracts each tossup and bonus-part
answerline, matches them against existing topic pages, and writes:

    output/_sets/{set_slug}/set.json     mechanical source data
    output/_sets/{set_slug}/report.json  alias/unmatched review report
    output/_sets/{set_slug}/sweep.html   rendered page
    output/_sets/sets.json               registry of swept sets

Usage:
    python lib/sweep/build_set.py "2022 ACF Winter"     # fetch + build
    python lib/sweep/build_set.py --list-sets [FILTER]  # find exact set names
    python lib/sweep/build_set.py "2022 ACF Winter" --rematch-only
    python lib/sweep/build_set.py --all --rematch-only  # build.sh mode: no network

set.json question row schema:
    {packet, number, type: "tossup"|"bonus", part: null|0-2,
     answer_raw   (sanitized text incl. accept clauses),
     answer_clean (display/matching form),
     category, subcategory, alternate_subcategory,
     match: {status, slug, topic, via}}
"""
import argparse
import json
import sys as _sys
import time
from collections import Counter
from pathlib import Path as _Path

_sys.path.insert(0, str(_Path(__file__).resolve().parent.parent.parent))
from lib.common import SETS_DIR, topic_slug, write_json_if_changed
from lib.sweep.answerlines import clean_answerline, normalize
from lib.sweep.matcher import TopicMatcher

REGISTRY_FILE = SETS_DIR / 'sets.json'

_write_json = write_json_if_changed


def _write_report(path, report):
    """Write report.json, keeping the old ``generated`` stamp when the
    substance is unchanged — otherwise every rematch run would churn a
    committed file just by re-dating it."""
    if path.exists():
        try:
            with open(path, encoding='utf-8') as f:
                old = json.load(f)
        except (json.JSONDecodeError, OSError):
            old = None
        if old is not None and \
                {**old, 'generated': ''} == {**report, 'generated': ''}:
            return
    _write_json(path, report)


def extract_questions(set_data: dict) -> list[dict]:
    """Flatten a fetched set into answerline rows (no matching yet).

    Rows carry the question's qbreader id instead of its text; the sweep
    page resolves text at view time from the set's R2 shard."""
    rows = []
    for i, packet in enumerate(set_data['packets'], start=1):
        for t in packet.get('tossups', []):
            raw = t.get('answer_sanitized') or t.get('answer', '')
            rows.append({
                'packet': i,
                'number': t.get('number'),
                'type': 'tossup',
                'part': None,
                'id': t.get('_id'),
                'answer_raw': raw,
                'answer_clean': clean_answerline(raw),
                'category': t.get('category', ''),
                'subcategory': t.get('subcategory', ''),
                'alternate_subcategory': t.get('alternate_subcategory') or '',
            })
        for b in packet.get('bonuses', []):
            answers = b.get('answers_sanitized') or b.get('answers', [])
            for j, raw in enumerate(answers):
                rows.append({
                    'packet': i,
                    'number': b.get('number'),
                    'type': 'bonus',
                    'part': j,
                    'id': b.get('_id'),
                    'answer_raw': raw,
                    'answer_clean': clean_answerline(raw),
                    'category': b.get('category', ''),
                    'subcategory': b.get('subcategory', ''),
                    'alternate_subcategory': b.get('alternate_subcategory') or '',
                })
    return rows


def apply_matches(rows: list[dict], matcher: TopicMatcher) -> None:
    for row in rows:
        row['match'] = matcher.match_dict(row['answer_clean'],
                                          category=row.get('category'))


def _near_misses(key: str, matcher: TopicMatcher, n: int = 3) -> list[dict]:
    """Mechanical near-miss candidates for an unmatched answerline, so
    the LLM review pass only adjudicates plausible cases instead of
    re-deriving them. Fuzzy match against exact-tier topic keys."""
    import difflib
    hits = difflib.get_close_matches(key, matcher.exact.keys(), n=n, cutoff=0.82)
    out = []
    seen = set()
    for h in hits:
        topic, slug = matcher.exact[h]
        if slug not in seen:
            seen.add(slug)
            out.append({'topic': topic, 'slug': slug})
    return out


def build_report(set_slug: str, rows: list[dict],
                 matcher: TopicMatcher | None = None) -> dict:
    """Aggregate alias-tier and unmatched rows for review.

    Grouped by normalized answerline; null overrides (confirmed
    no-topic) are excluded — they've already been reviewed. Unmatched
    entries carry mechanical near-miss candidates when any exist.
    """
    alias_groups: dict[str, dict] = {}
    unmatched_groups: dict[str, dict] = {}
    for row in rows:
        m = row['match']
        key = normalize(row['answer_clean'])
        if not key:
            continue
        if m['status'] == 'alias':
            g = alias_groups.setdefault(key, {
                'answer_clean': row['answer_clean'],
                'topic': m['topic'], 'slug': m['slug'], 'via': m['via'],
                'count': 0,
            })
            g['count'] += 1
        elif m['status'] == 'unmatched':
            g = unmatched_groups.setdefault(key, {
                'answer_clean': row['answer_clean'],
                'count': 0,
                'categories': Counter(),
            })
            g['count'] += 1
            g['categories'][(row['category'], row['subcategory'])] += 1

    unmatched = []
    for key, g in unmatched_groups.items():
        (cat, subcat), _n = g['categories'].most_common(1)[0]
        entry = {
            'answer_clean': g['answer_clean'],
            'count': g['count'],
            'category': cat,
            'subcategory': subcat,
            'proposal': {'topic': g['answer_clean'], 'category': cat},
        }
        if matcher is not None:
            candidates = _near_misses(key, matcher)
            if candidates:
                entry['candidates'] = candidates
        unmatched.append(entry)
    unmatched.sort(key=lambda g: (-g['count'], g['answer_clean']))

    alias_matches = sorted(alias_groups.values(),
                           key=lambda g: (-g['count'], g['answer_clean']))
    return {
        'set_slug': set_slug,
        'generated': time.strftime('%Y-%m-%d'),
        'alias_matches': alias_matches,
        'unmatched': unmatched,
    }


def load_registry() -> list[dict]:
    if REGISTRY_FILE.exists():
        with open(REGISTRY_FILE, encoding='utf-8') as f:
            return json.load(f)
    return []


def register_set(set_name: str, set_slug: str,
                 linked: int = 0, total: int = 0) -> None:
    """Add/update a registry entry, including coverage stats consumed
    by build_index.py for the explore strip."""
    registry = load_registry()
    entry = next((e for e in registry if e['set_slug'] == set_slug), None)
    if entry is None:
        entry = {'set_name': set_name, 'set_slug': set_slug,
                 'added': time.strftime('%Y-%m-%d')}
        registry.append(entry)
    entry['linked'] = linked
    entry['total'] = total
    registry.sort(key=lambda e: e['set_name'])
    _write_json(REGISTRY_FILE, registry)


def _r2_set_slug(set_name: str) -> str:
    """The published R2 file slug for a set (sets/{slug}.json). Uses the
    same collision-suffixed map as lib/mirror/publish.py, which needs
    the mirror's set list — available here because non-rematch builds
    always run on the machine with the mirror. Kept in set.json so CI
    rematch/render never needs the mirror."""
    from qbmirror import db as mirror_db
    from qbmirror import query as mirror_query
    from lib.mirror.publish import _unique_slugs
    conn = mirror_db.open_db()
    try:
        return _unique_slugs(mirror_query.set_list(conn=conn))[set_name]
    finally:
        conn.close()


def build_set(set_name: str, rematch_only: bool = False,
              matcher: TopicMatcher | None = None) -> dict:
    """Build or refresh one sweep set. Returns the set data dict."""
    set_slug = topic_slug(set_name)
    set_dir = SETS_DIR / set_slug
    set_file = set_dir / 'set.json'

    if rematch_only:
        if not set_file.exists():
            raise SystemExit(f'{set_file} does not exist — run without '
                             f'--rematch-only to fetch it first')
        with open(set_file, encoding='utf-8') as f:
            data = json.load(f)
        rows = data['questions']
    else:
        from lib.pipeline.fetch import fetch_set
        fetched = fetch_set(set_name)
        rows = extract_questions(fetched)
        data = {
            'set_name': set_name,
            'set_slug': set_slug,
            'r2_set': _r2_set_slug(set_name),
            'fetched': time.strftime('%Y-%m-%d'),
            'num_packets': fetched['num_packets'],
            'questions': rows,
        }

    if matcher is None:
        matcher = TopicMatcher()
    apply_matches(rows, matcher)

    _write_json(set_file, data)
    report = build_report(set_slug, rows, matcher=matcher)
    _write_report(set_dir / 'report.json', report)

    statuses = Counter(r['match']['status'] for r in rows)
    linked = sum(1 for r in rows if r['match']['slug'])
    register_set(data['set_name'], set_slug, linked=linked, total=len(rows))

    from lib.render.render_sweep import render_sweep
    render_sweep(data, set_dir / 'sweep.html')
    print(f"{data['set_name']}: {len(rows)} answerlines, {linked} linked "
          f"({', '.join(f'{k}={v}' for k, v in sorted(statuses.items()))})")
    print(f"  report: {len(report['alias_matches'])} alias matches to verify, "
          f"{len(report['unmatched'])} unmatched")
    return data


def rematch_all(matcher: TopicMatcher | None = None) -> None:
    """Re-match + re-render every registered set without fetching.

    The build's no-network sweep step; red links self-heal to blue as
    topics gain pages."""
    registry = load_registry()
    if not registry:
        print('No sweep sets registered.')
        return
    if matcher is None:
        matcher = TopicMatcher()
    for entry in registry:
        build_set(entry['set_name'], rematch_only=True, matcher=matcher)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('set_name', nargs='?')
    ap.add_argument('--list-sets', nargs='?', const='', metavar='FILTER',
                    help='print set names (optionally filtered), then exit')
    ap.add_argument('--all', action='store_true',
                    help='process every registered set')
    ap.add_argument('--rematch-only', action='store_true',
                    help='re-run matching + rendering without fetching')
    args = ap.parse_args()

    if args.list_sets is not None:
        from lib.pipeline.fetch import fetch_set_list
        names = fetch_set_list()
        needle = args.list_sets.lower()
        for name in names:
            if needle in name.lower():
                print(name)
        return

    if args.all:
        registry = load_registry()
        if not registry:
            print('No sweep sets registered yet.')
            return
        matcher = TopicMatcher()
        for entry in registry:
            build_set(entry['set_name'], rematch_only=args.rematch_only,
                      matcher=matcher)
        return

    if not args.set_name:
        ap.error('set name required (or --list-sets / --all)')
    build_set(args.set_name, rematch_only=args.rematch_only)


if __name__ == '__main__':
    main()
