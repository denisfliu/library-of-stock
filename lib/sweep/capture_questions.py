"""capture_questions.py — Capture a unit's actual questions for its
overview page.

Fetches every tossup/bonus in the unit's taxonomy slice, groups them by
normalized answerline, and writes:

    output/_categories/{unit}/questions.json      raw grouped data
    output/_categories/{unit}/questions_data.js   what the page loads

The overview page shows a per-entry "N q" button when the entry's
normalized answerline has captured questions (see render_overview.py).

Usage:
    python lib/sweep/capture_questions.py opera [--refresh]

NOTE (roadmap): question text fetched here overlaps the per-topic
caches in output/{slug}/ — a shared question store should eventually
dedupe this; see CLAUDE.md deferred improvements.
"""
import argparse
import json
import sys as _sys
from pathlib import Path as _Path

_sys.path.insert(0, str(_Path(__file__).resolve().parent.parent.parent))
from lib.common import CATEGORIES_DIR
from lib.pipeline.fetch import fetch_unit_questions
from lib.sweep.answerlines import clean_answerline, normalize
from lib.units import UNITS_BY_SLUG


def capture(unit_slug: str, refresh: bool = False) -> None:
    unit = UNITS_BY_SLUG.get(unit_slug)
    if unit is None:
        raise SystemExit(f'Unknown unit {unit_slug!r}')

    data = fetch_unit_questions(unit.freq_params, use_cache=not refresh)

    grouped: dict[str, list] = {}

    def add(answer_raw: str, text: str, q: dict, qtype: str) -> None:
        key = normalize(clean_answerline(answer_raw))
        if not key or not text:
            return
        grouped.setdefault(key, []).append({
            'type': qtype,
            'text': text.strip(),
            'set': (q.get('set') or {}).get('name', ''),
            'diff': q.get('difficulty', ''),
        })

    for t in data['tossups']:
        add(t.get('answer_sanitized', ''), t.get('question_sanitized', ''),
            t, 'tossup')
    for b in data['bonuses']:
        leadin = b.get('leadin_sanitized', '')
        parts = b.get('parts_sanitized', [])
        for j, ans in enumerate(b.get('answers_sanitized', [])):
            part = parts[j] if j < len(parts) else ''
            text = f'{leadin} {part}'.strip()
            add(ans, text, b, 'bonus')

    # Newest sets first within each answerline.
    for qs in grouped.values():
        qs.sort(key=lambda q: q['set'], reverse=True)

    out_dir = CATEGORIES_DIR / unit_slug
    out_dir.mkdir(parents=True, exist_ok=True)
    with open(out_dir / 'questions.json', 'w', encoding='utf-8') as f:
        json.dump(grouped, f, ensure_ascii=False)
    with open(out_dir / 'questions_data.js', 'w', encoding='utf-8') as f:
        f.write('const QUESTIONS_DATA = ')
        f.write(json.dumps(grouped, ensure_ascii=False).replace('</', '<\\/'))
        f.write(';\n')

    n_q = sum(len(v) for v in grouped.values())
    size_kb = (out_dir / 'questions_data.js').stat().st_size // 1024
    print(f'{unit_slug}: {n_q} questions across {len(grouped)} answerlines '
          f'-> questions_data.js ({size_kb} KB)')


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('unit')
    ap.add_argument('--refresh', action='store_true')
    args = ap.parse_args()
    capture(args.unit, refresh=args.refresh)
