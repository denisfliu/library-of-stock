"""capture_questions.py — Capture a unit's actual questions for its
overview page.

Fetches every tossup/bonus in the unit's taxonomy slice, upserts the
questions into the shared store (output/_questions/), and writes

    output/_categories/{unit}/questions.json

as {normalized answerline: [{id, part}, ...]} refs — part indexes a
bonus part, null means a tossup. The page's questions_data.js payload
is generated from these refs at render time by build_overviews.py.

The overview page shows a per-entry "N q" button when the entry's
normalized answerline has captured questions (see render_overview.py).

Usage:
    python lib/sweep/capture_questions.py opera [--refresh]
    python lib/sweep/capture_questions.py opera --show "soldiers"

--show prints the captured question texts for one answerline — for
authoring agents adjudicating ambiguous/common-link answerlines.
"""
import argparse
import json
import sys as _sys
from pathlib import Path as _Path

_sys.path.insert(0, str(_Path(__file__).resolve().parent.parent.parent))
from lib.common import CATEGORIES_DIR, write_json_if_changed
from lib.pipeline.fetch import fetch_unit_questions
from lib.questions_store import load_store, upsert
from lib.sweep.answerlines import clean_answerline, normalize
from lib.units import UNITS_BY_SLUG


def ref_text(ref: dict, store: dict) -> dict | None:
    """Resolve a {id, part} ref to the display dict the overview page
    uses: {type, text, set, diff}."""
    doc = store.get(ref.get('id') or '')
    if doc is None:
        return None
    if ref.get('part') is None:
        qtype, text = 'tossup', doc.get('question_sanitized', '')
    else:
        parts = doc.get('parts_sanitized', [])
        j = ref['part']
        part = parts[j] if j < len(parts) else ''
        qtype, text = 'bonus', f"{doc.get('leadin_sanitized', '')} {part}".strip()
    if not text:
        return None
    return {'type': qtype, 'text': text,
            'set': (doc.get('set') or {}).get('name', ''),
            'diff': doc.get('difficulty', '')}


def capture(unit_slug: str, refresh: bool = False) -> None:
    unit = UNITS_BY_SLUG.get(unit_slug)
    if unit is None:
        raise SystemExit(f'Unknown unit {unit_slug!r}')

    data = fetch_unit_questions(unit.freq_params, use_cache=not refresh)
    upsert([dict(q, type='tossup') for q in data['tossups']]
           + [dict(q, type='bonus') for q in data['bonuses']])

    grouped: dict[str, list] = {}

    def add(answer_raw: str, has_text: str, q: dict, part: int | None) -> None:
        key = normalize(clean_answerline(answer_raw))
        if not key or not has_text.strip() or not q.get('_id'):
            return
        grouped.setdefault(key, []).append(
            {'id': q['_id'], 'part': part,
             '_set': (q.get('set') or {}).get('name', '')})

    for t in data['tossups']:
        add(t.get('answer_sanitized', ''), t.get('question_sanitized', ''),
            t, None)
    for b in data['bonuses']:
        leadin = b.get('leadin_sanitized', '')
        parts = b.get('parts_sanitized', [])
        for j, ans in enumerate(b.get('answers_sanitized', [])):
            part = parts[j] if j < len(parts) else ''
            add(ans, f'{leadin} {part}', b, j)

    # Newest sets first within each answerline; the sort key is dropped
    # from the committed refs (it lives in the store).
    for qs in grouped.values():
        qs.sort(key=lambda r: r['_set'], reverse=True)
        for r in qs:
            del r['_set']

    out_dir = CATEGORIES_DIR / unit_slug
    out_dir.mkdir(parents=True, exist_ok=True)
    write_json_if_changed(out_dir / 'questions.json', grouped)

    n_q = sum(len(v) for v in grouped.values())
    print(f'{unit_slug}: {n_q} questions across {len(grouped)} answerlines '
          f'-> questions.json refs')


def show(unit_slug: str, answerline: str) -> None:
    ref_path = CATEGORIES_DIR / unit_slug / 'questions.json'
    if not ref_path.exists():
        raise SystemExit(f'No captured questions for {unit_slug!r}')
    with open(ref_path, encoding='utf-8') as f:
        grouped = json.load(f)
    key = normalize(clean_answerline(answerline))
    refs = grouped.get(key)
    if not refs:
        raise SystemExit(f'No captured questions for answerline {key!r}')
    store = load_store()
    print(f'{key}: {len(refs)} question(s)')
    for ref in refs:
        q = ref_text(ref, store)
        if q:
            print(f"\n[{q['type']} | {q['set']} | diff {q['diff']}]")
            print(q['text'])


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('unit')
    ap.add_argument('--refresh', action='store_true')
    ap.add_argument('--show', metavar='ANSWERLINE',
                    help='print captured question texts for one answerline')
    args = ap.parse_args()
    if args.show:
        show(args.unit, args.show)
    else:
        capture(args.unit, refresh=args.refresh)
