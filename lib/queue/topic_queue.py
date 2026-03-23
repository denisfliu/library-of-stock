#!/usr/bin/env python3
"""Queue management for stock guide generation.

Two queues:
  - first_pass: New topics to generate from scratch (higher priority)
  - second_pass: Existing topics to enrich/deepen

Usage:
  python3 lib/topic_queue.py add-first "Frida Kahlo" --category "Fine Arts" --diff "7,8,9,10"
  python3 lib/topic_queue.py add-second "Thomas Cole" --reason "sparse"
  python3 lib/topic_queue.py list
  python3 lib/topic_queue.py pop-first 10
  python3 lib/topic_queue.py pop-second 10
  python3 lib/topic_queue.py status          # JSON summary for index page
"""
import json, sys, re
from pathlib import Path
from datetime import date

ROOT = Path(__file__).parent.parent
FIRST_PASS = ROOT / 'queue' / 'queue_first_pass.json'
SECOND_PASS = ROOT / 'queue' / 'queue_second_pass.json'


def _load(path):
    if path.exists():
        with open(path) as f:
            return json.load(f)
    return {"queue": []}


def _save(path, data):
    path.parent.mkdir(exist_ok=True)
    with open(path, 'w') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def _slugify(name):
    return re.sub(r'[^a-z0-9]+', '_', name.lower()).strip('_')


def add_first(topic, category='', difficulties='7,8,9,10', notes=''):
    data = _load(FIRST_PASS)
    # Check for duplicates
    if any(item['topic'].lower() == topic.lower() for item in data['queue']):
        print(f'Already in first pass queue: {topic}')
        return
    data['queue'].append({
        'topic': topic,
        'difficulties': difficulties,
        'category': category,
        'min_year': 2012,
        'requested': str(date.today()),
        'notes': notes,
    })
    _save(FIRST_PASS, data)
    print(f'Added to first pass: {topic}')


def add_second(topic, reason='', difficulties='7,8,9,10'):
    data = _load(SECOND_PASS)
    slug = _slugify(topic)
    # Check for duplicates
    if any(item['topic'].lower() == topic.lower() for item in data['queue']):
        print(f'Already in second pass queue: {topic}')
        return
    # Check that analysis JSON exists
    analysis_file = ROOT / 'output' / slug / 'analysis.json'
    if not analysis_file.exists():
        print(f'Warning: no analysis JSON found for {topic} ({slug}). Use first pass instead?')
    category = ''
    if analysis_file.exists():
        with open(analysis_file) as f:
            cat_data = json.load(f)
        category = cat_data.get('category', '')
    data['queue'].append({
        'topic': topic,
        'slug': slug,
        'difficulties': difficulties,
        'category': category,
        'min_year': 2012,
        'requested': str(date.today()),
        'reason': reason,
    })
    _save(SECOND_PASS, data)
    print(f'Added to second pass: {topic} (reason: {reason})')


def remove_first(topic):
    data = _load(FIRST_PASS)
    before = len(data['queue'])
    data['queue'] = [item for item in data['queue'] if item['topic'].lower() != topic.lower()]
    _save(FIRST_PASS, data)
    removed = before - len(data['queue'])
    if removed:
        print(f'Removed from first pass: {topic}')
    else:
        print(f'Not found in first pass queue: {topic}')


def remove_second(topic):
    data = _load(SECOND_PASS)
    before = len(data['queue'])
    data['queue'] = [item for item in data['queue'] if item['topic'].lower() != topic.lower()]
    _save(SECOND_PASS, data)
    removed = before - len(data['queue'])
    if removed:
        print(f'Removed from second pass: {topic}')
    else:
        print(f'Not found in second pass queue: {topic}')


def pop_first(n=10, category=None):
    data = _load(FIRST_PASS)
    if category:
        # Pop up to n items matching category
        popped = []
        remaining = []
        for item in data['queue']:
            if len(popped) < n and item.get('category', '').lower() == category.lower():
                popped.append(item)
            else:
                remaining.append(item)
        data['queue'] = remaining
    else:
        popped = data['queue'][:n]
        data['queue'] = data['queue'][n:]
    _save(FIRST_PASS, data)
    for item in popped:
        print(f'  {item["topic"]} ({item.get("category", "?")})')
    return popped


def pop_second(n=10, category=None):
    data = _load(SECOND_PASS)
    if category:
        popped = []
        remaining = []
        for item in data['queue']:
            if len(popped) < n and item.get('category', '').lower() == category.lower():
                popped.append(item)
            else:
                remaining.append(item)
        data['queue'] = remaining
    else:
        popped = data['queue'][:n]
        data['queue'] = data['queue'][n:]
    _save(SECOND_PASS, data)
    for item in popped:
        print(f'  {item["topic"]} ({item.get("reason", item.get("category", "?"))})')
    return popped


def list_queues():
    first = _load(FIRST_PASS)
    second = _load(SECOND_PASS)
    print(f'=== First Pass ({len(first["queue"])}) ===')
    for item in first['queue']:
        print(f'  {item["topic"]} ({item.get("category", "?")}) [{item.get("requested", "")}]')
    print(f'\n=== Second Pass ({len(second["queue"])}) ===')
    for item in second['queue']:
        print(f'  {item["topic"]} ({item.get("reason", "?")}) [{item.get("requested", "")}]')
    print(f'\nTotal: {len(first["queue"])} first pass, {len(second["queue"])} second pass')


def summary():
    """Show counts by category for dispatch planning."""
    from collections import Counter
    first = _load(FIRST_PASS)
    second = _load(SECOND_PASS)

    first_cats = Counter(item.get('category', 'Unknown') for item in first['queue'])
    second_cats = Counter(item.get('category', 'Unknown') for item in second['queue'])

    print('=== First Pass by Category ===')
    for cat, n in first_cats.most_common():
        print(f'  {cat}: {n}')
    print(f'  Total: {len(first["queue"])}')

    print('\n=== Second Pass by Category ===')
    for cat, n in second_cats.most_common():
        print(f'  {cat}: {n}')
    print(f'  Total: {len(second["queue"])}')


def status():
    """JSON summary for index page."""
    first = _load(FIRST_PASS)
    second = _load(SECOND_PASS)
    return {
        'first_pass': len(first['queue']),
        'second_pass': len(second['queue']),
        'total': len(first['queue']) + len(second['queue']),
        'first_topics': [item['topic'] for item in first['queue']],
        'second_topics': [item['topic'] for item in second['queue']],
    }


if __name__ == '__main__':
    args = sys.argv[1:]
    if not args or args[0] in ('--help', '-h', 'help'):
        print(__doc__)
        sys.exit(0)

    cmd = args[0]

    if cmd == 'add-first':
        topic = args[1] if len(args) > 1 else ''
        if not topic:
            print('Usage: add-first "Topic Name" [--category CAT] [--diff DIFFS] [--notes NOTES]')
            sys.exit(1)
        kwargs = {}
        i = 2
        while i < len(args):
            if args[i] == '--category' and i + 1 < len(args):
                kwargs['category'] = args[i + 1]; i += 2
            elif args[i] == '--diff' and i + 1 < len(args):
                kwargs['difficulties'] = args[i + 1]; i += 2
            elif args[i] == '--notes' and i + 1 < len(args):
                kwargs['notes'] = args[i + 1]; i += 2
            else:
                i += 1
        add_first(topic, **kwargs)

    elif cmd == 'add-second':
        topic = args[1] if len(args) > 1 else ''
        if not topic:
            print('Usage: add-second "Topic Name" [--reason REASON]')
            sys.exit(1)
        reason = ''
        if '--reason' in args:
            idx = args.index('--reason')
            if idx + 1 < len(args):
                reason = args[idx + 1]
        add_second(topic, reason=reason)

    elif cmd == 'list':
        list_queues()

    elif cmd == 'pop-first':
        cat = None
        clean = [a for a in args[1:] if not a.startswith('--')]
        n = int(clean[0]) if clean else 10
        if '--category' in args:
            idx = args.index('--category')
            if idx + 1 < len(args):
                cat = args[idx + 1]
        popped = pop_first(n, category=cat)
        label = f' ({cat})' if cat else ''
        print(f'\nPopped {len(popped)} items from first pass queue{label}')

    elif cmd == 'pop-second':
        cat = None
        clean = [a for a in args[1:] if not a.startswith('--')]
        n = int(clean[0]) if clean else 10
        if '--category' in args:
            idx = args.index('--category')
            if idx + 1 < len(args):
                cat = args[idx + 1]
        popped = pop_second(n, category=cat)
        label = f' ({cat})' if cat else ''
        print(f'\nPopped {len(popped)} items from second pass queue{label}')

    elif cmd == 'summary':
        summary()

    elif cmd == 'remove-first':
        topic = args[1] if len(args) > 1 else ''
        if not topic:
            print('Usage: remove-first "Topic Name"')
            sys.exit(1)
        remove_first(topic)

    elif cmd == 'remove-second':
        topic = args[1] if len(args) > 1 else ''
        if not topic:
            print('Usage: remove-second "Topic Name"')
            sys.exit(1)
        remove_second(topic)

    elif cmd == 'status':
        print(json.dumps(status(), indent=2))

    else:
        print(f'Unknown command: {cmd}')
        print(__doc__)
        sys.exit(1)
