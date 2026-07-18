"""gaps.py — First-pass candidate report from frequency-list gaps.

The scope-approval artifact for first-pass rollouts: run the matcher over
one unit, a whole category, or every unit, keep only UNMATCHED curated
answerlines, and print them ranked by frequency. Place-name answerlines
(country/state/city common-links like "Hungary" or "Chicago") are split
into their own section — they need a page-shape decision, not a normal
first pass. Nothing is enqueued; feed the approved names to
`topic_queue.py add-first`.

Usage:
    python lib/sweep/gaps.py History --floor 25 --top 40
    python lib/sweep/gaps.py european_history
    python lib/sweep/gaps.py --all --floor 15       # per-unit summary table
    python lib/sweep/gaps.py Religion --json --out report.json
"""
import argparse
import sys as _sys
from pathlib import Path as _Path

_sys.path.insert(0, str(_Path(__file__).resolve().parent.parent.parent))
from lib.sweep.freq import build_freq_table
from lib.units import UNITS, UNITS_BY_SLUG

DEFAULT_FLOOR = 10

# Common-link place answerlines: flagged, not filtered. Countries and the
# US states/world cities that actually surface as history/literature
# answerlines. Matched case-sensitively against the raw answer string so
# people named after places ("Jack London") stay unflagged.
PLACE_NAMES = {
    # countries + frequent historical polities
    'Afghanistan', 'Albania', 'Algeria', 'Argentina', 'Armenia', 'Australia',
    'Austria', 'Austria-Hungary', 'Belgium', 'Bolivia', 'Brazil', 'Bulgaria',
    'Cambodia', 'Canada', 'Chile', 'China', 'Colombia', 'Congo', 'Cuba',
    'Czechoslovakia', 'Denmark', 'Ecuador', 'Egypt', 'England', 'Ethiopia',
    'Finland', 'France', 'Germany', 'Ghana', 'Greece', 'Guatemala', 'Haiti',
    'Hungary', 'Iceland', 'India', 'Indonesia', 'Iran', 'Iraq', 'Ireland',
    'Israel', 'Italy', 'Jamaica', 'Japan', 'Kenya', 'Korea', 'Laos',
    'Lebanon', 'Liberia', 'Libya', 'Madagascar', 'Malaysia', 'Mali',
    'Mexico', 'Mongolia', 'Morocco', 'Myanmar', 'Netherlands', 'New Zealand',
    'Nicaragua', 'Nigeria', 'Norway', 'Pakistan', 'Panama', 'Paraguay',
    'Peru', 'Philippines', 'Poland', 'Portugal', 'Prussia', 'Romania',
    'Russia', 'Rwanda', 'Saudi Arabia', 'Scotland', 'Senegal', 'Serbia',
    'Somalia', 'South Africa', 'South Korea', 'North Korea', 'Spain',
    'Sudan', 'Sweden', 'Switzerland', 'Syria', 'Taiwan', 'Thailand',
    'Tibet', 'Turkey', 'Uganda', 'Ukraine', 'Uruguay', 'Venezuela',
    'Vietnam', 'Wales', 'Yugoslavia', 'Zimbabwe',
    # US states that show up as American History answerlines
    'Alabama', 'Alaska', 'Arizona', 'California', 'Colorado', 'Florida',
    'Georgia', 'Hawaii', 'Illinois', 'Kansas', 'Kentucky', 'Louisiana',
    'Maryland', 'Massachusetts', 'Michigan', 'Minnesota', 'Mississippi',
    'Missouri', 'Nebraska', 'Nevada', 'New Jersey', 'New Mexico',
    'New York', 'North Carolina', 'Ohio', 'Oklahoma', 'Oregon',
    'Pennsylvania', 'South Carolina', 'Tennessee', 'Texas', 'Utah',
    'Virginia', 'Washington', 'West Virginia', 'Wisconsin', 'Wyoming',
    # cities that behave as common-links
    'Athens', 'Baghdad', 'Beijing', 'Berlin', 'Boston', 'Cairo',
    'Carthage', 'Chicago', 'Constantinople', 'Corinth', 'Istanbul',
    'Jerusalem', 'London', 'Los Angeles', 'Mecca', 'Moscow', 'New Orleans',
    'New York City', 'Paris', 'Philadelphia', 'Rome', 'San Francisco',
    'Sparta', 'Thebes', 'Venice', 'Vienna',
    # islands/regions that behave the same way
    'Bavaria', 'Catalonia', 'Crete', 'Cyprus', 'Florence', 'Hong Kong',
    'Puerto Rico', 'Quebec', 'Sicily', 'Sri Lanka',
}


def is_place(answer: str) -> bool:
    return answer in PLACE_NAMES or answer.removeprefix('The ') in PLACE_NAMES


def resolve_units(target: str | None, all_units: bool) -> list:
    """Resolve a unit slug, a category name, or --all into Unit objects."""
    if all_units:
        return list(UNITS)
    if target in UNITS_BY_SLUG:
        return [UNITS_BY_SLUG[target]]
    by_cat = [u for u in UNITS if u.category.lower() == (target or '').lower()]
    if by_cat:
        return by_cat
    raise SystemExit(
        f"Unknown unit or category '{target}'. Units: "
        + ', '.join(sorted(UNITS_BY_SLUG)) + '. Categories: '
        + ', '.join(sorted({u.category for u in UNITS})))


def build_gap_report(units: list, floor: int = DEFAULT_FLOOR) -> dict:
    """Collect unmatched curated answerlines >= floor across units.

    Returns {floor, units: [slug...], topics: [...], places: [...]} with
    each row {answer, frequency, unit, category}. Both lists are sorted
    by descending frequency.
    """
    topics, places = [], []
    for unit in units:
        table = build_freq_table(unit.slug)
        for r in table['curated']:
            if r['frequency'] < floor or r['match']['status'] != 'unmatched':
                continue
            row = {
                'answer': r['answer'],
                'frequency': r['frequency'],
                'unit': unit.slug,
                'category': unit.category,
            }
            (places if is_place(r['answer']) else topics).append(row)
    topics.sort(key=lambda r: -r['frequency'])
    places.sort(key=lambda r: -r['frequency'])
    return {
        'floor': floor,
        'units': [u.slug for u in units],
        'topics': topics,
        'places': places,
    }


def print_summary(units: list):
    """Per-unit tier table (>=25 / >=15 / >=10 / >=5 unmatched counts)."""
    tiers = (25, 15, 10, 5)
    header = ' '.join(f'>={t:<3}' for t in tiers)
    print(f"{'unit':<24} {'category':<16} {header}")
    totals = [0] * len(tiers)
    for unit in units:
        table = build_freq_table(unit.slug)
        un = [r['frequency'] for r in table['curated']
              if r['match']['status'] == 'unmatched']
        counts = [sum(1 for f in un if f >= t) for t in tiers]
        totals = [a + b for a, b in zip(totals, counts)]
        cells = ' '.join(f'{c:>4}' for c in counts)
        print(f'{unit.slug:<24} {unit.category:<16} {cells}')
    cells = ' '.join(f'{c:>4}' for c in totals)
    print(f"{'TOTAL':<24} {'':<16} {cells}")


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('target', nargs='?',
                    help='unit slug or category name (e.g. european_history, History)')
    ap.add_argument('--all', action='store_true', help='every unit')
    ap.add_argument('--floor', type=int, default=DEFAULT_FLOOR,
                    help=f'minimum frequency (default {DEFAULT_FLOOR})')
    ap.add_argument('--top', type=int, default=0,
                    help='cap each section at N rows (0 = no cap)')
    ap.add_argument('--summary', action='store_true',
                    help='per-unit tier counts instead of the ranked list')
    ap.add_argument('--json', action='store_true',
                    help='dump the report as JSON instead of text')
    ap.add_argument('--out', metavar='FILE',
                    help='write the JSON report to FILE (implies --json)')
    args = ap.parse_args()

    if not args.all and not args.target:
        ap.error('give a unit slug, a category name, or --all')
    units = resolve_units(args.target, args.all)

    if args.summary:
        print_summary(units)
        return

    report = build_gap_report(units, floor=args.floor)
    if args.top:
        report['topics'] = report['topics'][:args.top]
        report['places'] = report['places'][:args.top]

    if args.out:
        import json
        with open(args.out, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        print(f'Wrote {args.out}')
        return
    if args.json:
        import json
        print(json.dumps(report, indent=2, ensure_ascii=False))
        return

    label = ', '.join(report['units'])
    print(f"Unmatched curated answerlines (freq >= {report['floor']}) in: {label}\n")
    print(f"=== Topic candidates ({len(report['topics'])}) ===")
    for r in report['topics']:
        print(f"{r['frequency']:4d}  {r['unit']:<22} {r['answer']}")
    print(f"\n=== Place common-links ({len(report['places'])}) — "
          "page-shape decision needed ===")
    for r in report['places']:
        print(f"{r['frequency']:4d}  {r['unit']:<22} {r['answer']}")


if __name__ == '__main__':
    main()
