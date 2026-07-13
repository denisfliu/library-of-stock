"""draft_author.py — Cheap, batched drafting of overview pages.

The full authoring flow (see author.py and the /batch-era overview
sessions) spends agent judgment on bucketing, nesting, merging, and
per-entry notes. This module is the budget alternative used to scale
overviews to ALL units: everything mechanical is done here, and a single
Sonnet agent per unit only (a) picks era/school sections, (b) writes an
intro, and (c) writes a 10-20-word note per curated answerline, in
batches. Pages produced this way carry ``"draft": true`` in
overview.json and render with an "AI draft" banner until a proper
editing pass (un-AI-ify) upgrades them.

    python lib/sweep/draft_author.py prep UNIT [--batch-size N]
        Scaffolds the unit (author.scaffold), then writes
        output/_categories/{unit}/_draft/: INSTRUCTIONS.txt (the agent
        brief), batch_NN.txt (freq TAB answer TAB metadata-hint). Refuses
        units that already have authored sections unless --force.

    python lib/sweep/draft_author.py compose UNIT
        Reads the agent-written _draft/plan.txt, _draft/intro.txt and
        _draft/batch_NN.out.txt files, mechanically assembles
        sections.txt/intro.txt (merging duplicate answerlines, appending
        stragglers to an "Other" section), runs author.assemble, marks
        the overview as a draft, and captures the unit's questions.

    python lib/sweep/draft_author.py status
        Table of all units: authored / draft / pending.

Agent-facing file formats (also spelled out in INSTRUCTIONS.txt):
    plan.txt      # Section Name        (5-12 sections, page order)
                  > one-sentence blurb
    batch_NN.out.txt   answer TAB Section Name TAB note
"""
import argparse
import json
import sys as _sys
from pathlib import Path as _Path

_sys.path.insert(0, str(_Path(__file__).resolve().parent.parent.parent))
from lib.common import CATEGORIES_DIR, resolve_analyses
from lib.sweep import author
from lib.sweep.answerlines import normalize
from lib.sweep.capture_questions import capture
from lib.sweep.freq import DEFAULT_APPENDIX_THRESHOLD, DEFAULT_THRESHOLD
from lib.sweep.matcher import TopicMatcher
from lib.units import UNITS, UNITS_BY_SLUG

DEFAULT_BATCH_SIZE = 80
OTHER_SECTION = 'Other'

# Style exemplars for the note-writing agent, lifted from the opera page
# (the format model Denis iterated on).
STYLE_EXAMPLES = """\
Claudio Monteverdi | Early Baroque composer of L'Orfeo (1607), among the first operas still regularly performed; helped establish recitative-based drama.
Lucia di Lammermoor | Opera of a bride forced into marriage who murders her husband and descends into madness in the Mad Scene.
Orpheus | Common-link answerline spanning Monteverdi's L'Orfeo, Gluck's Orfeo ed Euridice, and Offenbach's Orpheus in the Underworld.
Singspiel | German-language genre alternating spoken dialogue with song, as in Mozart's Abduction from the Seraglio and The Magic Flute.
Giuseppe Verdi | Mid-Romantic composer of Rigoletto, La Traviata, and Aida; tightened Italian opera's drama and psychological focus.
Figaro | Beaumarchais's clever barber-valet, hero of both Rossini's Barber of Seville and its Mozart-composed sequel The Marriage of Figaro.
Maria Callas | Greek-American soprano who defined the bel canto revival; famed Tosca and Norma; "La Divina."
verismo | Late-19th-century Italian movement favoring gritty realism, launched by Cavalleria Rusticana and I Pagliacci."""

INSTRUCTIONS_TEMPLATE = """\
You are drafting the study-guide overview page for the quizbowl unit
"{title}" (category: {category}). Everything mechanical is scripted; you
supply ONLY: section plan, intro, and one short note per answerline.
Work entirely inside this directory ({draft_dir}); do not read or write
anything else. Do not run any commands.

STEP 1 — write plan.txt in this directory.
  5-12 sections that organize this unit the way an encyclopedia would:
  by era, school, movement, tradition, national grouping, or type —
  whatever fits "{title}" (e.g. art movements for painting, historical
  eras for a history unit, subfields for a science). Order them as they
  should appear on the page (usually chronological). Format, exactly:
      # Section Name
      > One-sentence blurb for the section.
  Every entry you later label must use one of these section names
  verbatim, so choose names that can absorb every answerline in the
  batch files (skim them before committing). Include a final catch-all
  section only if truly needed; the script adds an "Other" bucket for
  anything left over.

STEP 2 — write intro.txt in this directory: 2-4 encyclopedia-style
  paragraphs describing what this unit's questions ask about — the major
  clusters, the most-asked answers, how the canon is distributed. Plain
  factual prose, no bullet lists, no editorializing, no meta-references
  to "this page".

STEP 3 — for EACH batch_NN.txt here, write batch_NN.out.txt.
  Input lines are: frequency<TAB>answerline<TAB>hint
  The hint, when present, gives the matched wiki topic's metadata
  (y=year, c=country, t=tags); "?" means no wiki page exists — rely on
  your own knowledge. Output one line per input line, in the same order:
      answerline<TAB>Section Name<TAB>note
  - Echo the answerline EXACTLY as given (byte-for-byte, column 2 of
    the input). Never invent, merge, skip, or reorder lines.
  - Section Name must be one of your plan.txt names.
  - The note: 10-20 words, identifying facts only — who/what it is,
    era/school, key works or relations. Match the tone and density of
    these examples:
{style_examples}
  - No tabs or pipe characters inside notes. No trailing periods needed
    beyond normal prose. If you genuinely cannot identify an answerline,
    leave the note empty rather than guessing.

Accuracy beats coverage: a wrong identification is worse than an empty
note. These pages are marked as AI drafts, but wrong facts still poison
them.
"""


def _unit_dir(unit_slug: str) -> _Path:
    return CATEGORIES_DIR / unit_slug


def _load_overview(unit_slug: str) -> dict:
    with open(_unit_dir(unit_slug) / 'overview.json', encoding='utf-8') as f:
        return json.load(f)


def _save_overview(unit_slug: str, overview: dict) -> None:
    with open(_unit_dir(unit_slug) / 'overview.json', 'w', encoding='utf-8') as f:
        json.dump(overview, f, indent=2, ensure_ascii=False)


def prep(unit_slug: str, batch_size: int = DEFAULT_BATCH_SIZE,
         force: bool = False) -> None:
    unit = UNITS_BY_SLUG.get(unit_slug)
    if unit is None:
        raise SystemExit(f'Unknown unit {unit_slug!r}')

    ov_path = _unit_dir(unit_slug) / 'overview.json'
    if ov_path.exists() and not force:
        overview = _load_overview(unit_slug)
        if overview.get('sections') and not overview.get('draft'):
            raise SystemExit(
                f'{unit_slug} already has authored sections — refusing to '
                f'draft over it (use --force to override)')

    author.scaffold(unit_slug, DEFAULT_THRESHOLD, DEFAULT_APPENDIX_THRESHOLD)
    overview = _load_overview(unit_slug)
    entries = overview.get('unplaced', [])
    if not entries:
        print(f'{unit_slug}: nothing unplaced — already fully authored?')
        return

    analyses = resolve_analyses()
    meta = {}
    for slug, _path, data in analyses:
        meta[slug] = (data.get('year'), data.get('country'),
                      data.get('tags') or [])
    matcher = TopicMatcher(analyses=analyses)

    def hint_for(answer: str) -> str:
        m = matcher.match(answer, category=unit.category)
        if not m.slug or m.slug not in meta:
            return '?'
        y, c, tags = meta[m.slug]
        bits = []
        if y is not None:
            bits.append(f'y={y}')
        if c:
            bits.append(f'c={c}')
        if tags:
            bits.append('t=' + ','.join(tags[:3]))
        return '; '.join(bits) or '?'

    draft_dir = _unit_dir(unit_slug) / '_draft'
    draft_dir.mkdir(parents=True, exist_ok=True)
    for old in draft_dir.glob('batch_*.txt'):
        old.unlink()

    rows = sorted(entries, key=lambda e: -e['frequency'])
    n_batches = 0
    for i in range(0, len(rows), batch_size):
        n_batches += 1
        lines = [f"{e['frequency']}\t{e['answerline']}\t{hint_for(e['answerline'])}"
                 for e in rows[i:i + batch_size]]
        (draft_dir / f'batch_{n_batches:02d}.txt').write_text(
            '\n'.join(lines) + '\n', encoding='utf-8')

    (draft_dir / 'INSTRUCTIONS.txt').write_text(
        INSTRUCTIONS_TEMPLATE.format(
            title=unit.title, category=unit.category,
            draft_dir=str(draft_dir),
            style_examples='\n'.join('      ' + ln
                                     for ln in STYLE_EXAMPLES.splitlines())),
        encoding='utf-8')
    print(f'Prepped {unit_slug}: {len(rows)} entries in {n_batches} '
          f'batch file(s) under {draft_dir}')


def _parse_plan(plan_path: _Path):
    """plan.txt -> ordered [(name, blurb)]."""
    sections, name, blurb = [], None, ''
    for raw in plan_path.read_text(encoding='utf-8').splitlines():
        line = raw.strip()
        if line.startswith('#'):
            if name:
                sections.append((name, blurb))
            name, blurb = line.lstrip('#').strip(), ''
        elif line.startswith('>') and name:
            blurb = line.lstrip('>').strip()
    if name:
        sections.append((name, blurb))
    return sections


def compose(unit_slug: str) -> None:
    draft_dir = _unit_dir(unit_slug) / '_draft'
    plan_path = draft_dir / 'plan.txt'
    intro_path = draft_dir / 'intro.txt'
    if not plan_path.exists() or not intro_path.exists():
        raise SystemExit(f'{draft_dir} is missing plan.txt or intro.txt')

    plan = _parse_plan(plan_path)
    if not plan:
        raise SystemExit('plan.txt parsed to zero sections')
    section_names = [n for n, _ in plan]

    overview = _load_overview(unit_slug)
    pool = {e['answerline']: e for e in overview.get('unplaced', [])}
    by_norm = {}
    for a in pool:
        by_norm.setdefault(normalize(a), []).append(a)

    # Collect agent assignments: answerline -> (section, note).
    assigned = {}
    bad_lines = 0
    for out in sorted(draft_dir.glob('batch_*.out.txt')):
        for raw in out.read_text(encoding='utf-8').splitlines():
            if not raw.strip():
                continue
            parts = raw.split('\t')
            if len(parts) < 2:
                bad_lines += 1
                continue
            ans = parts[0].strip()
            sec = parts[1].strip()
            note = parts[2].strip().replace('|', ';') if len(parts) > 2 else ''
            if ans not in pool:
                # tolerate near-miss echoes via normalization
                cands = by_norm.get(normalize(ans), [])
                if len(cands) == 1:
                    ans = cands[0]
                else:
                    bad_lines += 1
                    continue
            if sec not in section_names:
                sec = OTHER_SECTION
            assigned.setdefault(ans, (sec, note))

    # Merge answerlines that normalize identically (diacritics/aliases):
    # keep the highest-frequency spelling as primary, fold the rest in
    # as `=` variants; the primary's note wins.
    merged_into = {}
    for _norm, group in by_norm.items():
        if len(group) < 2:
            continue
        group = sorted(group, key=lambda a: -pool[a]['frequency'])
        primary = group[0]
        for dup in group[1:]:
            merged_into[dup] = primary

    by_section = {name: [] for name in section_names}
    by_section.setdefault(OTHER_SECTION, [])
    for ans, entry in pool.items():
        if ans in merged_into:
            continue
        sec, note = assigned.get(ans, (OTHER_SECTION, ''))
        variants = [d for d, p in merged_into.items() if p == ans]
        by_section[sec].append((entry['frequency'], ans, variants, note))

    lines = []
    for name, blurb in plan + ([(OTHER_SECTION, '')]
                               if OTHER_SECTION not in section_names else []):
        rows = sorted(by_section.get(name, []), key=lambda r: -r[0])
        if not rows:
            continue
        lines.append(f'# {name}')
        if blurb:
            lines.append(f'> {blurb}')
        for _freq, ans, variants, note in rows:
            head = ' = '.join([ans] + variants)
            lines.append(f'{head} | {note}')
        lines.append('')

    unit_dir = _unit_dir(unit_slug)
    (unit_dir / 'sections.txt').write_text('\n'.join(lines), encoding='utf-8')
    (unit_dir / 'intro.txt').write_text(
        intro_path.read_text(encoding='utf-8'), encoding='utf-8')

    author.assemble(unit_slug)

    overview = _load_overview(unit_slug)
    overview['draft'] = True
    _save_overview(unit_slug, overview)

    n_missing = sum(1 for a in pool
                    if a not in assigned and a not in merged_into)
    print(f'Composed {unit_slug} as DRAFT '
          f'({n_missing} entries fell back to "{OTHER_SECTION}"/no-note, '
          f'{bad_lines} malformed agent lines ignored)')

    capture(unit_slug)


def status() -> None:
    for unit in UNITS:
        ov_path = _unit_dir(unit.slug) / 'overview.json'
        state = 'pending'
        if ov_path.exists():
            with open(ov_path, encoding='utf-8') as f:
                ov = json.load(f)
            if ov.get('draft'):
                state = 'draft'
            elif ov.get('sections'):
                state = 'authored'
            elif (_unit_dir(unit.slug) / '_draft').exists():
                state = 'prepped'
        print(f'{state:9} {unit.slug}')


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    sub = ap.add_subparsers(dest='cmd', required=True)

    pr = sub.add_parser('prep')
    pr.add_argument('unit')
    pr.add_argument('--batch-size', type=int, default=DEFAULT_BATCH_SIZE)
    pr.add_argument('--force', action='store_true')

    co = sub.add_parser('compose')
    co.add_argument('unit')

    sub.add_parser('status')

    args = ap.parse_args()
    if args.cmd == 'prep':
        prep(args.unit, batch_size=args.batch_size, force=args.force)
    elif args.cmd == 'compose':
        compose(args.unit)
    else:
        status()


if __name__ == '__main__':
    main()
