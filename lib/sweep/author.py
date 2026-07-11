"""author.py — Token-lean scaffolding/assembly for overview authoring.

The authoring agent should only spend tokens on judgment (sections,
notes, canonical names, nesting) — everything mechanical lives here.

    python lib/sweep/author.py scaffold UNIT [--threshold N] [--appendix-threshold N] [--refresh]
        Creates or UPDATES output/_categories/{unit}/overview.json:
        intro/sections and their notes are preserved; freq_source and
        appendix are recomputed; frequencies of placed entries are
        refreshed; curated answerlines not yet placed land in
        `unplaced`. Also writes work.txt — the compact table for the
        agent (freq TAB answer TAB match-status TAB placed|NEW).

    python lib/sweep/author.py assemble UNIT
        Reads sections.txt + intro.txt (written by the agent next to
        overview.json), validates coverage, and completes overview.json.

sections.txt format:
    # Section Name
    > optional one-sentence section blurb
    Raw Answer | note text
    Raw Answer = Variant Answer -> Canonical Topic | note text
    - Nested Raw Answer | note text

`- ` nests an answerline under the previous top-level entry (a work
under its author). `= Variant` merges another curated answerline into
the entry (frequency summed, raw string kept in `variants`). `-> Topic`
sets the canonical display name when it differs from the raw answer.

intro.txt: encyclopedia intro, paragraphs separated by blank lines.
"""
import argparse
import json
import sys as _sys
from pathlib import Path as _Path

_sys.path.insert(0, str(_Path(__file__).resolve().parent.parent.parent))
from lib.common import CATEGORIES_DIR
from lib.sweep.freq import (DEFAULT_APPENDIX_THRESHOLD, DEFAULT_THRESHOLD,
                            build_freq_table)
from lib.units import UNITS_BY_SLUG


def _unit_dir(unit_slug: str) -> _Path:
    return CATEGORIES_DIR / unit_slug


def _iter_entries(overview: dict):
    """Yield every placed entry (including nested works)."""
    for s in overview.get('sections', []):
        for e in s.get('entries', []):
            yield e
            yield from e.get('works', [])


def _placed_answerlines(overview: dict) -> set[str]:
    placed = set()
    for e in _iter_entries(overview):
        placed.add(e['answerline'])
        for v in e.get('variants', []):
            placed.add(v['answerline'])
    return placed


def scaffold(unit_slug: str, threshold: int, appendix_threshold: int,
             refresh: bool = False) -> None:
    unit = UNITS_BY_SLUG.get(unit_slug)
    if unit is None:
        raise SystemExit(f'Unknown unit {unit_slug!r}')

    table = build_freq_table(unit_slug, threshold=threshold,
                             appendix_threshold=appendix_threshold,
                             refresh=refresh)
    freq_by_answer = {r['answer']: r['frequency'] for r in table['curated']}

    out_dir = _unit_dir(unit_slug)
    ov_path = out_dir / 'overview.json'
    if ov_path.exists():
        with open(ov_path, encoding='utf-8') as f:
            overview = json.load(f)
    else:
        overview = {
            'unit': unit.slug, 'title': unit.title,
            'category': unit.category, 'subcategory': unit.subcategory,
            'genre': unit.genre,
            'intro': [], 'sections': [], 'unplaced': [],
        }

    overview['freq_source'] = table['freq_source']
    overview['appendix'] = [
        {'answer': r['answer'], 'frequency': r['frequency']}
        for r in table['appendix']
    ]

    # Refresh frequencies of already-placed entries from the new table.
    for e in _iter_entries(overview):
        own = freq_by_answer.get(e['answerline'])
        if own is not None:
            e['frequency'] = own + sum(
                freq_by_answer.get(v['answerline'], v['frequency'])
                for v in e.get('variants', []))

    placed = _placed_answerlines(overview)
    known_unplaced = {e['answerline'] for e in overview.get('unplaced', [])}
    new_rows = [r for r in table['curated']
                if r['answer'] not in placed and r['answer'] not in known_unplaced]
    # Refresh unplaced freqs and drop unplaced rows no longer curated.
    overview['unplaced'] = [
        {**e, 'frequency': freq_by_answer.get(e['answerline'], e['frequency'])}
        for e in overview.get('unplaced', [])
        if e['answerline'] in freq_by_answer
    ] + [
        {'topic': r['answer'], 'answerline': r['answer'],
         'frequency': r['frequency'], 'note': ''}
        for r in new_rows
    ]

    out_dir.mkdir(parents=True, exist_ok=True)
    with open(ov_path, 'w', encoding='utf-8') as f:
        json.dump(overview, f, indent=2, ensure_ascii=False)

    unplaced_set = {e['answerline'] for e in overview['unplaced']}
    work_lines = [
        f"{r['frequency']}\t{r['answer']}\t{r['match']['status']}"
        f"\t{'NEW' if r['answer'] in unplaced_set else 'placed'}"
        for r in table['curated']
    ]
    (out_dir / 'work.txt').write_text('\n'.join(work_lines) + '\n',
                                      encoding='utf-8')
    print(f'Scaffolded {ov_path}: {len(table["curated"])} curated '
          f'({len(overview["unplaced"])} unplaced/NEW), '
          f'{len(table["appendix"])} appendix rows')


def assemble(unit_slug: str) -> None:
    out_dir = _unit_dir(unit_slug)
    ov_path = out_dir / 'overview.json'
    with open(ov_path, encoding='utf-8') as f:
        overview = json.load(f)

    # Pool of placeable entries, keyed by exact raw answer string.
    pool = {e['answerline']: e for e in overview.get('unplaced', [])}
    for e in _iter_entries(overview):
        pool[e['answerline']] = {k: v for k, v in e.items()
                                 if k not in ('works', 'variants')}
        for v in e.get('variants', []):
            pool[v['answerline']] = {'topic': v['answerline'],
                                     'answerline': v['answerline'],
                                     'frequency': v['frequency'],
                                     'note': ''}

    intro_path = out_dir / 'intro.txt'
    if not intro_path.exists():
        raise SystemExit(f'{intro_path} missing')
    intro = [p.strip().replace('\n', ' ')
             for p in intro_path.read_text(encoding='utf-8').split('\n\n')
             if p.strip()]

    sections_path = out_dir / 'sections.txt'
    if not sections_path.exists():
        raise SystemExit(f'{sections_path} missing')

    sections = []
    current = None          # current section
    last_top = None         # last top-level entry (nesting target)
    errors = []
    used = set()

    def parse_entry(line: str, lineno: int) -> dict | None:
        if '|' not in line:
            errors.append(f'line {lineno}: missing " | note": {line[:60]!r}')
            return None
        head, note = line.split('|', 1)
        note = note.strip()
        topic = None
        if '->' in head:
            head, topic = head.rsplit('->', 1)
            topic = topic.strip()
        answers = [a.strip() for a in head.split('=') if a.strip()]
        if not answers:
            errors.append(f'line {lineno}: no answer before "|"')
            return None
        missing = [a for a in answers if a not in pool]
        if missing:
            errors.append(f'line {lineno}: not in curated list: {missing}')
            return None
        dup = [a for a in answers if a in used]
        if dup:
            errors.append(f'line {lineno}: already placed: {dup}')
            return None
        used.update(answers)
        primary = pool[answers[0]]
        entry = {
            'topic': topic or primary['answerline'],
            'answerline': primary['answerline'],
            'frequency': sum(pool[a]['frequency'] for a in answers),
            'note': note,
        }
        if len(answers) > 1:
            entry['variants'] = [
                {'answerline': a, 'frequency': pool[a]['frequency']}
                for a in answers[1:]
            ]
        return entry

    for lineno, raw in enumerate(
            sections_path.read_text(encoding='utf-8').splitlines(), 1):
        line = raw.strip()
        if not line:
            continue
        if line.startswith('#'):
            current = {'name': line.lstrip('#').strip(), 'blurb': '',
                       'entries': []}
            sections.append(current)
            last_top = None
            continue
        if line.startswith('>'):
            if current is None:
                errors.append(f'line {lineno}: blurb before any section')
            else:
                current['blurb'] = line.lstrip('>').strip()
            continue
        if current is None:
            errors.append(f'line {lineno}: entry before any # section header')
            continue
        nested = line.startswith('- ')
        entry = parse_entry(line[2:].strip() if nested else line, lineno)
        if entry is None:
            continue
        if nested:
            if last_top is None:
                errors.append(f'line {lineno}: "- " entry has no parent above')
                continue
            last_top.setdefault('works', []).append(entry)
        else:
            current['entries'].append(entry)
            last_top = entry

    leftovers = [e for a, e in pool.items() if a not in used]
    if errors:
        print(f'ASSEMBLY FAILED — {len(errors)} error(s):')
        for e in errors[:30]:
            print('  ' + e)
        raise SystemExit(1)

    overview['intro'] = intro
    overview['sections'] = [s for s in sections if s['entries']]
    overview['unplaced'] = leftovers
    with open(ov_path, 'w', encoding='utf-8') as f:
        json.dump(overview, f, indent=2, ensure_ascii=False)

    placed = sum(1 for _ in _iter_entries(overview))
    print(f'Assembled {ov_path}: {len(overview["sections"])} sections, '
          f'{placed} entries, {len(leftovers)} unplaced, '
          f'{len(intro)} intro paragraphs')
    if leftovers:
        print('UNPLACED (should usually be empty):')
        for e in leftovers[:20]:
            print(f"  {e['frequency']}\t{e['answerline']}")


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    sub = ap.add_subparsers(dest='cmd', required=True)

    sc = sub.add_parser('scaffold')
    sc.add_argument('unit')
    sc.add_argument('--threshold', type=int, default=DEFAULT_THRESHOLD)
    sc.add_argument('--appendix-threshold', type=int,
                    default=DEFAULT_APPENDIX_THRESHOLD)
    sc.add_argument('--refresh', action='store_true')

    asm = sub.add_parser('assemble')
    asm.add_argument('unit')

    args = ap.parse_args()
    if args.cmd == 'scaffold':
        scaffold(args.unit, args.threshold, args.appendix_threshold,
                 refresh=args.refresh)
    else:
        assemble(args.unit)


if __name__ == '__main__':
    main()
