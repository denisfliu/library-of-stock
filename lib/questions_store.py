"""questions_store.py — the single committed copy of every fetched question.

Design: docs/question_store.md. Every qbreader question we have ever
fetched lives in exactly one shard file under output/_questions/, keyed
by its qbreader ``_id``; per-topic refs, sweep set.json rows, and unit
captures reference into it instead of embedding question text.

Shards are per qbreader set (one tournament per file): new fetches touch
few shards, diffs stay local, and sweep pages read exactly their shard.
Both raw and sanitized text variants are kept verbatim — raw carries the
power-mark/italics markup that parse.py and questions.html depend on,
sanitized feeds sentence splitting and match keys.

Usage:
    python lib/questions_store.py backfill   # ingest all legacy caches
    python lib/questions_store.py stats      # shard/doc counts

API:
    load_store() -> dict[_id, doc]
    upsert(docs) -> (added, updated)         # updatedAt-gated, locked
"""
import json
import re
import sys as _sys
from pathlib import Path as _Path

_sys.path.insert(0, str(_Path(__file__).resolve().parent.parent))
from lib.common import (CACHE_DIR, CATEGORIES_DIR, OUTPUT_DIR, SETS_DIR,
                        file_lock, write_json_if_changed)

STORE_DIR = OUTPUT_DIR / '_questions'
_LOCK_FILE = CACHE_DIR / 'questions_store.lock'

# Fields copied into a store doc. set/packet are trimmed to the parts
# renderers use ({name, year} / {number}); both text variants are kept.
_COMMON_FIELDS = ('_id', 'type', 'category', 'subcategory',
                  'alternate_subcategory', 'difficulty', 'number',
                  'updatedAt')
_TOSSUP_FIELDS = ('question', 'question_sanitized',
                  'answer', 'answer_sanitized')
_BONUS_FIELDS = ('leadin', 'leadin_sanitized', 'parts', 'parts_sanitized',
                 'answers', 'answers_sanitized')


def shard_slug(set_name: str) -> str:
    slug = re.sub(r'[^\w\-]+', '_', (set_name or '').strip().lower()).strip('_')
    return slug or '_unknown'


def shard_path(set_name: str) -> _Path:
    return STORE_DIR / f'{shard_slug(set_name)}.json'


def trim_doc(q: dict, qtype: str | None = None) -> dict:
    """Reduce a raw qbreader question object to its store form."""
    doc = {k: q[k] for k in _COMMON_FIELDS if k in q}
    if qtype:
        doc['type'] = qtype
    body = _BONUS_FIELDS if doc.get('type') == 'bonus' else _TOSSUP_FIELDS
    for k in body:
        if k in q:
            doc[k] = q[k]
    s = q.get('set') or {}
    doc['set'] = {'name': s.get('name', ''), 'year': s.get('year')}
    p = q.get('packet') or {}
    if p.get('number') is not None:
        doc['packet'] = {'number': p['number']}
    return doc


def _load_shard(path: _Path) -> dict:
    if not path.exists():
        return {}
    with open(path, encoding='utf-8') as f:
        return json.load(f)


def load_store() -> dict:
    """All shards as one {_id: doc} dict. One parse per build."""
    store = {}
    for path in sorted(STORE_DIR.glob('*.json')):
        store.update(_load_shard(path))
    return store


def _newer(a: str | None, b: str | None) -> bool:
    """True if updatedAt a is strictly newer than b (ISO strings compare
    lexicographically; a missing stamp never wins)."""
    return bool(a) and (not b or a > b)


def upsert(docs, qtype: str | None = None) -> tuple[int, int]:
    """Add or refresh store docs. Accepts raw qbreader question objects
    (trimmed here) or already-trimmed docs. Existing docs are only
    replaced when the incoming updatedAt is strictly newer, so re-running
    a backfill is a no-op. Returns (added, updated)."""
    by_shard: dict[_Path, list[dict]] = {}
    for q in docs:
        doc = trim_doc(q, qtype)
        if not doc.get('_id'):
            continue
        by_shard.setdefault(shard_path(doc['set']['name']), []).append(doc)

    added = updated = 0
    with file_lock(_LOCK_FILE):
        for path, shard_docs in sorted(by_shard.items()):
            shard = _load_shard(path)
            changed = False
            for doc in shard_docs:
                old = shard.get(doc['_id'])
                if old is None:
                    shard[doc['_id']] = doc
                    added += 1
                    changed = True
                elif _newer(doc.get('updatedAt'), old.get('updatedAt')):
                    shard[doc['_id']] = doc
                    updated += 1
                    changed = True
            if changed:
                write_json_if_changed(
                    path, dict(sorted(shard.items())))
    return added, updated


# ---------------------------------------------------------------------------
# Backfill: ingest every legacy cache shape that still carries _ids.

def _iter_topic_cache_questions():
    for d in sorted(OUTPUT_DIR.iterdir()):
        if not (d / 'analysis.json').is_file():
            continue
        for f in sorted(d.glob('*.json')):
            if f.name in ('analysis.json', 'cards.json',
                          'questions_ref.json'):
                continue
            try:
                data = json.loads(f.read_text(encoding='utf-8'))
            except (json.JSONDecodeError, OSError):
                print(f'  WARNING: unreadable cache {f}', file=_sys.stderr)
                continue
            m = data.get('answer_matches') or data.get('text_mentions') or {}
            yield from ((q, 'tossup') for q in m.get('tossups', []))
            yield from ((q, 'bonus') for q in m.get('bonuses', []))


def _iter_unit_cache_questions():
    unit_dir = CACHE_DIR / 'unit_questions'
    for f in sorted(unit_dir.glob('*.json')) if unit_dir.exists() else []:
        data = json.loads(f.read_text(encoding='utf-8'))
        yield from ((q, 'tossup') for q in data.get('tossups', []))
        yield from ((q, 'bonus') for q in data.get('bonuses', []))


def _iter_set_cache_questions():
    sets_dir = CACHE_DIR / 'sets'
    for sd in sorted(sets_dir.iterdir()) if sets_dir.exists() else []:
        if not sd.is_dir():
            continue
        for f in sorted(sd.glob('packet_*.json')):
            data = json.loads(f.read_text(encoding='utf-8'))
            yield from ((q, 'tossup') for q in data.get('tossups', []))
            yield from ((q, 'bonus') for q in data.get('bonuses', []))


def backfill() -> None:
    STORE_DIR.mkdir(parents=True, exist_ok=True)
    for label, it in (('topic caches', _iter_topic_cache_questions()),
                      ('unit caches', _iter_unit_cache_questions()),
                      ('set packet caches', _iter_set_cache_questions())):
        batch = [dict(q, type=qtype) for q, qtype in it]
        added, updated = upsert(batch)
        print(f'{label}: {len(batch)} questions seen, '
              f'{added} added, {updated} refreshed')
    stats()


def stats() -> None:
    shards = sorted(STORE_DIR.glob('*.json'))
    total = sum(len(_load_shard(p)) for p in shards)
    size = sum(p.stat().st_size for p in shards)
    print(f'Store: {total} questions across {len(shards)} set shards, '
          f'{size / 1e6:.1f} MB')


if __name__ == '__main__':
    cmd = _sys.argv[1] if len(_sys.argv) > 1 else 'stats'
    if cmd == 'backfill':
        backfill()
    elif cmd == 'stats':
        stats()
    else:
        raise SystemExit(f'unknown command {cmd!r} (use backfill|stats)')
