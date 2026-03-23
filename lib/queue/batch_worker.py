#!/usr/bin/env python3
"""
batch_worker.py — Pop a topic from the active batch queue (with file locking).

Used by agents to claim work without race conditions.

Usage:
    python3 lib/batch_worker.py pop          # pop next topic, print JSON
    python3 lib/batch_worker.py complete "Topic Name"  # mark topic as done
    python3 lib/batch_worker.py status       # print batch status
"""
import json, sys, fcntl, time
from pathlib import Path
from datetime import datetime
import re

ROOT = Path(__file__).parent.parent
PROJECT_ROOT = ROOT.parent
sys.path.insert(0, str(PROJECT_ROOT))
BATCH_FILE = ROOT / 'queue' / 'current_batch.json'
LOCK_FILE = ROOT / 'queue' / '.batch.lock'


def _locked(fn):
    """Execute fn while holding an exclusive file lock."""
    LOCK_FILE.parent.mkdir(exist_ok=True)
    lock_fd = open(LOCK_FILE, 'w')
    fcntl.flock(lock_fd, fcntl.LOCK_EX)
    try:
        return fn()
    finally:
        fcntl.flock(lock_fd, fcntl.LOCK_UN)
        lock_fd.close()


def _load():
    if BATCH_FILE.exists():
        with open(BATCH_FILE) as f:
            return json.load(f)
    return None


def _save(data):
    with open(BATCH_FILE, 'w') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def pop(pass_type=None, category=None):
    """Pop the next available topic from the batch queue. Returns the item dict or None.

    Filters by pass_type ('first'/'second') and/or category ('Literature'/'Fine Arts'/etc).
    """
    def _pop():
        data = _load()
        if not data:
            return None
        queue = data.get('queue', [])
        for i, item in enumerate(queue):
            if pass_type and item.get('pass_type') != pass_type:
                continue
            if category and item.get('category', '').lower() != category.lower():
                continue
            # Claim it
            claimed = queue.pop(i)
            claimed['started_at'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            data['in_progress'] = data.get('in_progress', [])
            data['in_progress'].append(claimed)
            _save(data)
            return claimed
        return None

    return _locked(_pop)


def complete(topic_name):
    """Mark a topic as completed in the batch."""
    def _complete():
        data = _load()
        if not data:
            print(f'No active batch')
            return

        # Move from in_progress to completed
        in_progress = data.get('in_progress', [])
        completed_item = None
        remaining = []
        for item in in_progress:
            if item['topic'].lower() == topic_name.lower() and not completed_item:
                completed_item = item
            else:
                remaining.append(item)

        if completed_item:
            completed_item['completed_at'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            data['in_progress'] = remaining
            data['completed'] = data.get('completed', [])
            data['completed'].append(completed_item)
            _save(data)
            print(f'Completed: {topic_name}')
            # Automatically enqueue for second pass
            if completed_item.get('pass_type') == 'first':
                from lib.queue.topic_queue import add_second
                add_second(topic_name, reason='first pass done')
        else:
            # Might not be in in_progress if agent didn't pop properly, just add to completed
            data['completed'] = data.get('completed', [])
            data['completed'].append({
                'topic': topic_name,
                'completed_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            })
            _save(data)
            print(f'Completed (direct): {topic_name}')

    _locked(_complete)


def init(name, first_count=0, second_count=0, category=None):
    """Initialize a new batch from the global queues.

    Pops items from the global queues and creates current_batch.json.
    """
    from lib.queue.topic_queue import pop_first, pop_second

    batch_queue = []

    if first_count > 0:
        first_items = pop_first(first_count, category=category)
        for item in first_items:
            batch_queue.append({
                'topic': item['topic'],
                'category': item.get('category', ''),
                'difficulties': item.get('difficulties', '7,8,9,10'),
                'pass_type': 'first',
            })

    if second_count > 0:
        second_items = pop_second(second_count, category=category)
        for item in second_items:
            batch_queue.append({
                'topic': item['topic'],
                'slug': item.get('slug', ''),
                'category': item.get('category', ''),
                'difficulties': item.get('difficulties', '7,8,9,10'),
                'pass_type': 'second',
            })

    batch = {
        'name': name,
        'started_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'queue': batch_queue,
        'in_progress': [],
        'completed': [],
    }

    _save(batch)
    print(f'Batch "{name}" initialized: {len(batch_queue)} items '
          f'({sum(1 for i in batch_queue if i["pass_type"]=="first")} first, '
          f'{sum(1 for i in batch_queue if i["pass_type"]=="second")} second)')
    return batch


def status():
    """Print batch status."""
    data = _load()
    if not data:
        print('No active batch')
        return

    queued = len(data.get('queue', []))
    in_prog = len(data.get('in_progress', []))
    done = len(data.get('completed', []))
    total = queued + in_prog + done

    print(f'Batch: {data.get("name", "unnamed")}')
    print(f'  Queued: {queued}')
    print(f'  In progress: {in_prog}')
    print(f'  Completed: {done}')
    print(f'  Total: {total}')

    if data.get('in_progress'):
        print(f'\n  Currently working:')
        for item in data['in_progress']:
            print(f'    {item["topic"]} (started {item.get("started_at", "?")})')


if __name__ == '__main__':
    args = sys.argv[1:]
    if not args:
        print(__doc__)
        sys.exit(0)

    cmd = args[0]
    if cmd == 'pop':
        # pop [pass_type] [--category CAT]
        pass_type = None
        category = None
        rest = args[1:]
        if '--category' in rest:
            idx = rest.index('--category')
            if idx + 1 < len(rest):
                category = rest[idx + 1]
            rest = rest[:idx] + rest[idx+2:]
        if rest and rest[0] in ('first', 'second'):
            pass_type = rest[0]
        item = pop(pass_type, category)
        if item:
            print(json.dumps(item))
        else:
            print('EMPTY')

    elif cmd == 'complete':
        if len(args) < 2:
            print('Usage: complete "Topic Name"')
            sys.exit(1)
        complete(args[1])

    elif cmd == 'init':
        # init "batch name" --first N --second M [--category CAT]
        name = args[1] if len(args) > 1 else f'batch-{datetime.now().strftime("%Y%m%d-%H%M")}'
        first_n = 0
        second_n = 0
        category = None
        i = 2
        while i < len(args):
            if args[i] == '--first' and i + 1 < len(args):
                first_n = int(args[i + 1]); i += 2
            elif args[i] == '--second' and i + 1 < len(args):
                second_n = int(args[i + 1]); i += 2
            elif args[i] == '--category' and i + 1 < len(args):
                category = args[i + 1]; i += 2
            else:
                i += 1
        init(name, first_count=first_n, second_count=second_n, category=category)

    elif cmd == 'status':
        status()

    else:
        print(f'Unknown command: {cmd}')
        print(__doc__)
