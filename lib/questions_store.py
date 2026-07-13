"""questions_store.py — per-topic question refs (and set-slug helper).

Historical note: until July 2026 this module also managed the committed
question store (output/_questions/ shards). That store is retired — the
full corpus lives in the local qbreader mirror (lib/mirror/, gitignored
SQLite) and question text reaches the website at view time from the R2
data plane (lib/mirror/publish.py, docs/mirror.md). What remains
committed are the per-topic REFS: which qbreader ids back each topic's
questions.html.

API:
    record_fetch(topic_dir, data, mentions=False)  # write/merge a ref entry
    ref_entry_from_fetch(data, mentions=False)
    shard_slug(set_name)                           # set-name file slug
"""
import json
import re
import sys as _sys
from pathlib import Path as _Path

_sys.path.insert(0, str(_Path(__file__).resolve().parent.parent))
from lib.common import write_json_if_changed


def shard_slug(set_name: str) -> str:
    """File slug for a set name (used by the R2 publisher's sets/ and
    the sweep pages' fallback slug — see lib/mirror/publish._unique_slugs
    for collision handling)."""
    slug = re.sub(r'[^\w\-]+', '_', (set_name or '').strip().lower()).strip('_')
    return slug or '_unknown'


# ---------------------------------------------------------------------------
# Topic refs: output/{slug}/questions_ref.json — an ordered list of query
# entries whose tossups/bonuses are qbreader _id lists. This is the
# committed record of which questions back a topic's questions.html; the
# ids resolve against the mirror at publish time (topic_questions/ on R2).

def ref_entry_from_fetch(data: dict, mentions: bool = False) -> dict:
    """Build a ref entry from a fetch_topic/fetch_text_mentions result."""
    m = data.get('answer_matches') or data.get('text_mentions') or {}
    return {
        'query_string': data.get('query_string', ''),
        'difficulties': data.get('difficulties'),
        'min_year': data.get('min_year'),
        'mentions': bool(mentions),
        'tossups': [q['_id'] for q in m.get('tossups', []) if q.get('_id')],
        'bonuses': [q['_id'] for q in m.get('bonuses', []) if q.get('_id')],
    }


def _ref_key(entry: dict):
    return (entry.get('query_string'), tuple(entry.get('difficulties') or ()),
            entry.get('min_year'), bool(entry.get('mentions')))


def record_fetch(topic_dir, data: dict, mentions: bool = False) -> None:
    """The post-fetch write path: merge the query's ref entry into the
    topic's questions_ref.json (replacing a previous entry for the same
    query). Question text itself is not persisted here — the mirror
    already holds it."""
    entry = ref_entry_from_fetch(data, mentions=mentions)
    ref_path = _Path(topic_dir) / 'questions_ref.json'
    refs = []
    if ref_path.exists():
        with open(ref_path, encoding='utf-8') as f:
            refs = json.load(f)
    for i, existing in enumerate(refs):
        if _ref_key(existing) == _ref_key(entry):
            refs[i] = entry
            break
    else:
        refs.append(entry)
    write_json_if_changed(ref_path, refs)
