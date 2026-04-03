#!/usr/bin/env python3
"""Scan existing topics for shallow first-pass analyses that need a redo.

Identifies topics where the analysis has few work sections relative to the
amount of raw clue data available — i.e., the agent crammed everything into
1-2 sections instead of properly breaking out individual works.

Single-work topics (films, operas, specific compositions, specific novels)
are excluded since having few sections is expected for them.

Usage:
  python3 lib/queue/scan_redo.py                  # print ranked candidates
  python3 lib/queue/scan_redo.py --enqueue        # also add to redo queue
  python3 lib/queue/scan_redo.py --min-questions 15  # adjust threshold
  python3 lib/queue/scan_redo.py --json           # JSON output
"""
import json, sys, re
from pathlib import Path

ROOT = Path(__file__).parent.parent.parent
OUTPUT = ROOT / 'output'
REDO_QUEUE = ROOT / 'queue' / 'queue_redo_first.json'

# Subcategories that are typically about a single work, not a creator/concept.
# Topics in these subcategories with few works are expected, not broken.
SINGLE_WORK_SUBCATEGORIES = {
    'Film', 'Opera', 'Musicals', 'Dance',
}

# Keywords in topic names that suggest a single-work topic
SINGLE_WORK_PATTERNS = [
    r'\bSymphony\b', r'\bConcerto\b', r'\bSonata\b', r'\bQuartet\b',
    r'\bOverture\b', r'\bSuite\b', r'\bFanfare\b', r'\bRequiem\b',
    r'\bMass\b', r'\bOratorio\b', r'\bBallade\b', r'\bNocturne\b',
    r'\bRhapsody\b', r'\bPrelude\b', r'\bFugue\b', r'\bEtude\b',
]


def is_single_work_topic(data):
    """Heuristic: is this topic about a single work rather than a creator?"""
    topic = data.get('topic', '')
    subcat = data.get('subcategory', '')
    genre = data.get('genre', '')

    # Check subcategory / genre
    if genre in SINGLE_WORK_SUBCATEGORIES:
        return True
    if subcat in SINGLE_WORK_SUBCATEGORIES:
        return True

    # Check topic name patterns (specific compositions)
    for pat in SINGLE_WORK_PATTERNS:
        if re.search(pat, topic, re.IGNORECASE):
            return True

    # Check if every work section is about the same piece (no "General" section,
    # all works are aspects like "Plot", "Characters", "Production")
    works = data.get('works', [])
    if len(works) <= 1:
        return False  # Can't tell from 1 section

    work_names = [w.get('name', '') for w in works]
    # If no "General" or "Biographical" section and topic name appears in work names,
    # it's likely a single-work deep dive
    has_general = any('general' in n.lower() or 'biographical' in n.lower()
                      for n in work_names)
    if not has_general and len(works) <= 4:
        # Small number of sections with no general = likely single work
        # But only if the topic name doesn't look like a person
        # (persons usually have first+last name pattern)
        if not re.match(r'^[A-Z][a-z]+ [A-Z]', topic):
            return True

    return False


def count_questions(clues_path):
    """Extract tossup + bonus counts from clues.txt header."""
    if not clues_path.exists():
        return 0, 0
    try:
        header = clues_path.read_text(encoding='utf-8')[:500]
    except Exception:
        return 0, 0
    t = b = 0
    m = re.search(r'Tossup questions: (\d+)', header)
    if m:
        t = int(m.group(1))
    m = re.search(r'Bonus questions: (\d+)', header)
    if m:
        b = int(m.group(1))
    return t, b


def scan(min_questions=10, max_works=3):
    """Scan all topics and return ranked redo candidates."""
    candidates = []

    for analysis_path in sorted(OUTPUT.glob('*/analysis.json')):
        slug = analysis_path.parent.name
        with open(analysis_path) as f:
            data = json.load(f)

        topic = data.get('topic', slug)
        works = data.get('works', [])
        num_works = len(works)
        category = data.get('category', '')
        subcategory = data.get('subcategory', '')

        # Count raw questions available
        clues_path = analysis_path.parent / 'clues.txt'
        tossups, bonuses = count_questions(clues_path)
        total_q = tossups + bonuses

        if total_q < min_questions:
            continue
        if num_works > max_works:
            continue

        # Skip single-work topics
        if is_single_work_topic(data):
            continue

        # Score: lower = more likely underanalyzed
        # works per question, scaled to 0-100
        ratio = num_works / total_q * 100

        # Count analyzed clues vs potential
        analyzed_clues = sum(
            sum(c.get('frequency', 1) for c in w.get('clues', []))
            for w in works
        )

        candidates.append({
            'topic': topic,
            'slug': slug,
            'category': category,
            'subcategory': subcategory,
            'works': num_works,
            'analyzed_clues': analyzed_clues,
            'tossups': tossups,
            'bonuses': bonuses,
            'total_questions': total_q,
            'ratio': ratio,
        })

    # Sort by ratio ascending (worst first)
    candidates.sort(key=lambda x: x['ratio'])
    return candidates


def classify(candidate):
    """Assign a confidence tier to a candidate."""
    w = candidate['works']
    q = candidate['total_questions']
    r = candidate['ratio']

    if w <= 2 and q >= 15:
        return 'definite'
    if w <= 3 and q >= 20:
        return 'likely'
    if w <= 3 and q >= 10 and r < 25:
        return 'maybe'
    return 'maybe'


def print_report(candidates):
    """Print a human-readable report."""
    by_tier = {'definite': [], 'likely': [], 'maybe': []}
    for c in candidates:
        tier = classify(c)
        by_tier[tier].append(c)

    total = len(candidates)
    print(f'Redo scan: {total} candidates found\n')

    for tier_name, label in [('definite', 'DEFINITE REDO'),
                              ('likely', 'LIKELY REDO'),
                              ('maybe', 'MAYBE REDO')]:
        items = by_tier[tier_name]
        if not items:
            continue
        print(f'=== {label} ({len(items)}) ===')
        for c in items:
            print(f"  {c['topic']:40s}  works={c['works']}  "
                  f"Q={c['total_questions']:3d} (T={c['tossups']:2d} B={c['bonuses']:2d})  "
                  f"clues={c['analyzed_clues']:3d}  "
                  f"ratio={c['ratio']:.1f}  {c['category']}")
        print()


def enqueue(candidates, tiers=('definite', 'likely')):
    """Add candidates to the redo queue."""
    queue_data = {'queue': []}
    if REDO_QUEUE.exists():
        with open(REDO_QUEUE) as f:
            queue_data = json.load(f)

    existing = {item['topic'].lower() for item in queue_data['queue']}
    added = 0

    for c in candidates:
        tier = classify(c)
        if tier not in tiers:
            continue
        if c['topic'].lower() in existing:
            continue

        queue_data['queue'].append({
            'topic': c['topic'],
            'slug': c['slug'],
            'category': c['category'],
            'difficulties': '7,8,9,10',
            'min_year': 2012,
            'requested': str(__import__('datetime').date.today()),
            'reason': f"redo: {c['works']} works from {c['total_questions']} questions (tier={tier})",
            'works_before': c['works'],
            'questions_available': c['total_questions'],
            'tier': tier,
        })
        existing.add(c['topic'].lower())
        added += 1

    REDO_QUEUE.parent.mkdir(exist_ok=True)
    with open(REDO_QUEUE, 'w') as f:
        json.dump(queue_data, f, indent=2, ensure_ascii=False)

    print(f'Added {added} topics to {REDO_QUEUE.relative_to(ROOT)}')
    print(f'Queue now has {len(queue_data["queue"])} topics')


if __name__ == '__main__':
    args = sys.argv[1:]

    min_q = 10
    do_enqueue = '--enqueue' in args
    as_json = '--json' in args

    if '--min-questions' in args:
        idx = args.index('--min-questions')
        if idx + 1 < len(args):
            min_q = int(args[idx + 1])

    tiers = ('definite', 'likely')
    if '--include-maybe' in args:
        tiers = ('definite', 'likely', 'maybe')

    candidates = scan(min_questions=min_q)

    if as_json:
        for c in candidates:
            c['tier'] = classify(c)
        print(json.dumps(candidates, indent=2, ensure_ascii=False))
    else:
        print_report(candidates)

    if do_enqueue:
        enqueue(candidates, tiers=tiers)
