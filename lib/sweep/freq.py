"""freq.py — Frequency-list working table for overview authoring.

The first step of the /overview skill: fetch a unit's frequency list,
apply the curation/appendix thresholds, run the matcher over every
answerline, and print a table the authoring agent works from.

Usage:
    python lib/sweep/freq.py american_literature
    python lib/sweep/freq.py film --threshold 8 --appendix-threshold 3
    python lib/sweep/freq.py biology --refresh

Exit table columns: frequency | tier | match status | answer -> topic.
"""
import argparse
import sys as _sys
from pathlib import Path as _Path

_sys.path.insert(0, str(_Path(__file__).resolve().parent.parent.parent))
from lib.pipeline.fetch import (DEFAULT_DIFFICULTIES, DEFAULT_FREQ_LIMIT,
                                DEFAULT_MIN_YEAR, fetch_frequency_list)
from lib.sweep.matcher import TopicMatcher
from lib.units import UNITS_BY_SLUG

# Curation floor: answerlines at or above this frequency belong in the
# curated thematic sections of an overview page. Below it (down to the
# appendix floor) they are listed mechanically in a collapsed appendix.
# Depth over brevity per user direction: curate everything asked 3+
# times; appendix catches the 2-mention tail.
DEFAULT_THRESHOLD = 3
DEFAULT_APPENDIX_THRESHOLD = 2


def build_freq_table(unit_slug: str, threshold: int = DEFAULT_THRESHOLD,
                     appendix_threshold: int = DEFAULT_APPENDIX_THRESHOLD,
                     difficulties: list[int] | None = None,
                     min_year: int = DEFAULT_MIN_YEAR,
                     limit: int = DEFAULT_FREQ_LIMIT,
                     refresh: bool = False) -> dict:
    """Fetch + match a unit's frequency list.

    Returns {unit, freq_source, curated, appendix} where curated and
    appendix are lists of {answer, answer_normalized, frequency, match}.
    """
    unit = UNITS_BY_SLUG.get(unit_slug)
    if unit is None:
        raise SystemExit(f"Unknown unit '{unit_slug}'. Valid: "
                         + ', '.join(sorted(UNITS_BY_SLUG)))
    difficulties = difficulties or DEFAULT_DIFFICULTIES

    data = fetch_frequency_list(unit.freq_params, difficulties=difficulties,
                                min_year=min_year, limit=limit,
                                use_cache=not refresh)
    matcher = TopicMatcher()

    curated, appendix = [], []
    for entry in data['frequency_list']:
        freq = entry['frequency']
        if freq < appendix_threshold:
            break  # list is sorted desc
        row = {
            'answer': entry['answer'],
            'answer_normalized': entry['answer_normalized'],
            'frequency': freq,
            'match': matcher.match_dict(entry['answer'],
                                        category=unit.category),
        }
        (curated if freq >= threshold else appendix).append(row)

    return {
        'unit': unit.slug,
        'freq_source': {
            'fetched': data['fetched'],
            'difficulties': difficulties,
            'min_year': min_year,
            'question_type': 'all',
            'threshold': threshold,
            'appendix_threshold': appendix_threshold,
            'answerlines_curated': len(curated),
            'answerlines_appendix': len(appendix),
        },
        'curated': curated,
        'appendix': appendix,
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('unit')
    ap.add_argument('--threshold', type=int, default=DEFAULT_THRESHOLD)
    ap.add_argument('--appendix-threshold', type=int,
                    default=DEFAULT_APPENDIX_THRESHOLD)
    ap.add_argument('--limit', type=int, default=DEFAULT_FREQ_LIMIT)
    ap.add_argument('--refresh', action='store_true',
                    help='bypass the frequency-list cache')
    ap.add_argument('--json', action='store_true',
                    help='dump the full table as JSON instead of text')
    ap.add_argument('--out', metavar='FILE',
                    help='write the JSON table to FILE (implies --json, '
                         'keeps progress prints off the data)')
    args = ap.parse_args()

    table = build_freq_table(args.unit, threshold=args.threshold,
                             appendix_threshold=args.appendix_threshold,
                             limit=args.limit, refresh=args.refresh)

    if args.out:
        import json
        with open(args.out, 'w', encoding='utf-8') as f:
            json.dump(table, f, indent=2, ensure_ascii=False)
        print(f'Wrote {args.out}')
        return
    if args.json:
        import json
        print(json.dumps(table, indent=2, ensure_ascii=False))
        return

    def _print_rows(rows, tier):
        for r in rows:
            m = r['match']
            target = f" -> {m['topic']} ({m['slug']})" if m['slug'] else ''
            via = f" [via {m['via']}]" if m['via'] and m['status'] == 'alias' else ''
            print(f"{r['frequency']:4d}  {tier:8s} {m['status']:9s} "
                  f"{r['answer']}{target}{via}")

    _print_rows(table['curated'], 'curated')
    _print_rows(table['appendix'], 'appendix')

    fs = table['freq_source']
    counts = {}
    for r in table['curated'] + table['appendix']:
        counts[r['match']['status']] = counts.get(r['match']['status'], 0) + 1
    print(f"\n{table['unit']}: {fs['answerlines_curated']} curated "
          f"(freq>={fs['threshold']}), {fs['answerlines_appendix']} appendix "
          f"(freq>={fs['appendix_threshold']})")
    print('match statuses:', ', '.join(f'{k}={v}' for k, v in sorted(counts.items())))


if __name__ == '__main__':
    main()
