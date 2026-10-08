"""
apply_checks.py — Apply sharded /guide-check edits to a v2 guide.

Big guides (evidence.txt over ~100 KB) are checked by several agents in
parallel, one per range of sections. Concurrent edits to one
analysis.json would collide, so each shard writes its fixes as edit ops
to checks/shard_*.json, and this script applies them all at once
(entries are addressed as they were when evidence.txt was written, so
ops are resolved before anything moves).

Op format (a JSON list per shard):
    {"op": "entry", "section": "S3", "entry": 5, "set": {"clue": "...", "src": [...], "note": "..."}}
    {"op": "entry", "section": "S3", "entry": 5, "move_to": "S1"}
    {"op": "entry", "section": "S3", "entry": 5, "delete": true}
    {"op": "entry", "section": "S3", "add": {"clue": "...", "src": [...]}}
    {"op": "card", "card": 12, "set": {"front": "...", "back": "...", "work": "...", "src": [...]}}
    {"op": "card", "card": 12, "delete": true}
    {"op": "prose", "field": "summary" | "comprehensive_summary", "find": "old text", "replace": "new text"}
    {"op": "prose", "section": "S3", "field": "description", "find": "...", "replace": "..."}
    {"op": "uncite", "id": "C123", "reason": "not identifying"}   # excuse a cluster in `uncited`

Sections are S# and cards K# exactly as numbered in evidence.txt
(1-based). After applying, run finalize.py.

Usage:
    python lib/pipeline/apply_checks.py OUTDIR
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
import lib.common  # noqa: F401 — UTF-8 stdio


def main():
    outdir = Path(sys.argv[1])
    a = json.loads((outdir / 'analysis.json').read_text(encoding='utf-8'))
    cards = json.loads((outdir / 'cards.json').read_text(encoding='utf-8'))
    ops = []
    for f in sorted((outdir / 'checks').glob('shard_*.json')):
        ops += json.loads(f.read_text(encoding='utf-8'))
    works = a['works']
    sec = lambda s: works[int(str(s).lstrip('S')) - 1]
    # Resolve every target to an object reference before mutating.
    resolved, problems = [], []
    for op in ops:
        try:
            if op['op'] == 'entry' and 'add' not in op:
                w = sec(op['section'])
                resolved.append((op, w, w['clues'][op['entry'] - 1]))
            elif op['op'] == 'card':
                resolved.append((op, None, cards[op['card'] - 1]))
            elif op['op'] == 'uncite':
                resolved.append((op, None, None))
            else:
                resolved.append((op, sec(op['section']) if 'section' in op else None, None))
        except (IndexError, KeyError, ValueError) as e:
            problems.append(f"unresolvable op {op}: {e!r}")
    dead_entries, dead_cards = [], []
    applied = 0
    for op, w, target in resolved:
        if op['op'] == 'entry':
            if 'add' in op:
                w['clues'].append(op['add'])
            elif op.get('delete'):
                dead_entries.append((w, target))
            elif 'move_to' in op:
                dead_entries.append((w, target))
                sec(op['move_to'])['clues'].append(target)
            else:
                target.update(op['set'])
        elif op['op'] == 'card':
            if op.get('delete'):
                dead_cards.append(target)
            else:
                target.update(op['set'])
        elif op['op'] == 'uncite':
            a.setdefault('uncited', {})[op['id']] = op.get('reason', 'not identifying')
        elif op['op'] == 'prose':
            holder = w if w is not None else a
            text = holder.get(op['field'], '')
            if op['find'] not in text:
                problems.append(f"prose find not matched in {op.get('section', '')}{op['field']}: {op['find'][:60]}")
                continue
            holder[op['field']] = text.replace(op['find'], op['replace'], 1)
        applied += 1
    for w, entry in dead_entries:
        w['clues'] = [c for c in w['clues'] if c is not entry]
    cards = [c for c in cards if not any(c is d for d in dead_cards)]
    (outdir / 'analysis.json').write_text(json.dumps(a, ensure_ascii=False, indent=2) + "\n", encoding='utf-8')
    (outdir / 'cards.json').write_text(json.dumps(cards, ensure_ascii=False, indent=2) + "\n", encoding='utf-8')
    print(f"applied {applied}/{len(ops)} ops")
    for p in problems:
        print(f"PROBLEM {p}")
    sys.exit(1 if problems else 0)


if __name__ == '__main__':
    main()
