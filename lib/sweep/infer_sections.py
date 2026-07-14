"""infer_sections.py — mechanically section the residual from question text.

Most unsectioned answerlines are freq-1 tail, but their question BODIES
name entities we've already sectioned. This infers a section with no LLM
by two signals over the mirror's question text:

  1. Co-mention vote (universal): scan each of an answerline's questions
     for already-sectioned entities (people/works/places from the unit's
     lexicon) and take the weighted-majority section. Self-adapting — in a
     chronological unit the co-mentioned dated figures vote their period,
     in a region unit the co-mentioned places vote their region, in a
     creator unit the works/artists vote their movement.
  2. Date vote (chronological history units only): the modal year in the
     body maps to a period section via PERIOD_TABLES.

Fills blanks only — never overwrites a section already set by the
mechanical index, Wikidata, or the LLM. Results are written to the KB
shards (source="inferred"), so publish picks them up like any other KB
section. Re-derivable and incremental.

    python lib/sweep/infer_sections.py UNIT [--min-weight N]
    python lib/sweep/infer_sections.py --all
"""
import argparse
import re
import sys as _sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path as _Path

_sys.path.insert(0, str(_Path(__file__).resolve().parent.parent.parent))
from lib.pipeline.fetch import fetch_unit_questions
from lib.sweep.answerline_kb import (_primary_key, clean_answerline, collect,
                                     load_kb, save_kb)
from lib.sweep.answerlines import normalize
from lib.sweep.section_index import SectionIndex
from lib.units import UNITS, UNITS_BY_SLUG

MIN_WEIGHT = 3.0     # minimum winning weight to assign
MIN_MARGIN = 1.5     # winner must beat runner-up by this factor

_YEAR = re.compile(r'\b(1[0-9]{3}|20[0-2][0-9])\b')
_BCE = re.compile(r'\b(\d{1,4})\s*(?:BCE?|B\.C\.?)\b', re.I)
# capitalized multi-word spans (proper-noun co-mentions)
_ENT = re.compile(r'\b([A-Z][a-zA-Z.\'-]+(?: [A-Z][a-zA-Z.\'-]+){0,4})\b')

# Chronological history units: modal body-year -> period section. Ranges
# are [lo, hi); section names match the overview verbatim.
PERIOD_TABLES = {
    'american_history': [
        (1490, 1765, 'Colonial America'),   # floor: pre-Columbian -> no match
        (1765, 1789, 'American Revolution and the Founding'),
        (1789, 1845, 'The Early Republic and Jacksonian America'),
        (1845, 1877, 'Civil War and Reconstruction'),
        (1877, 1900, 'The Gilded Age and the West'),
        (1900, 1919, 'The Progressive Era and World War I'),
        (1919, 1945, 'The Depression, New Deal, and World War II'),
        (1945, 1975, 'The Cold War and Civil Rights'),
        (1975, 9999, 'Contemporary America'),
    ],
    'european_history': [
        (-9999, 500, 'Antiquity, Late Antiquity, and Byzantium'),
        (500, 1000, 'Early Medieval Europe'),
        (1000, 1450, 'High and Late Medieval Europe'),
        (1450, 1517, 'Renaissance and the Age of Exploration'),
        (1517, 1650, 'Reformation and the Wars of Religion'),
        (1650, 1750, 'Absolutism and the Early Modern State'),
        (1750, 1815, 'Revolution and Napoleonic Europe'),
        (1815, 1900, 'Nationalism and Reform in Nineteenth-Century Europe'),
        (1900, 1918, 'World War I and Revolutionary Europe'),
        (1918, 1945, 'Interwar Crisis and World War II'),
        (1945, 9999, 'Cold War and Contemporary Europe'),
    ],
}

# Surfaces too generic to trust as co-mention votes.
_STOP = {normalize(w) for w in (
    'the united states', 'united states', 'america', 'god', 'europe',
    'god', 'the church', 'church', 'the bible', 'england', 'france',
    'rome', 'greece', 'the roman empire')}


def _period_section(year, unit_slug):
    for lo, hi, name in PERIOD_TABLES.get(unit_slug, []):
        if lo <= year < hi:
            return name
    return None


def _build_lexicon(unit_slug, idx, kb):
    """normalized surface -> (section, weight). Sectioned answerlines from
    the mechanical index + the KB; weighted by frequency, filtered to
    distinctive (multi-word, or long typed person/work) surfaces so bare
    place/number surfaces don't dominate the vote."""
    lex = {}
    freq = {k: v['freq'] for k, v in collect(unit_slug).items()}

    def consider(surface_key, section, typ=None):
        if not section or surface_key in _STOP:
            return
        words = surface_key.split()
        distinctive = (len(words) >= 2
                       or (typ in ('person', 'work') and len(surface_key) >= 6))
        if not distinctive:
            return
        w = 1.0 + 0.3 * min(freq.get(surface_key, 1), 10)
        if typ in ('person', 'work', 'movement'):
            w *= 1.4
        prev = lex.get(surface_key)
        if prev is None or w > prev[1]:
            lex[surface_key] = (section, w)

    for key, section in idx._by_unit.get(unit_slug, {}).items():
        consider(key, section)
    for key, rec in kb.items():
        if rec.get('section'):
            consider(key, rec['section'], rec.get('type'))
    return lex


def _infer_one(texts, lex, unit_slug):
    votes = Counter()
    # co-mention votes
    for t in texts:
        seen = set()
        for m in _ENT.finditer(t):
            k = normalize(m.group(1))
            hit = lex.get(k)
            if hit and k not in seen:
                seen.add(k)
                votes[hit[0]] += hit[1]
    # date votes (chronological units)
    if unit_slug in PERIOD_TABLES:
        # count each year once per question (so the topic's period year,
        # repeated across its questions, beats one-off incidental dates);
        # drop >=2005 meta/reference years (a history topic is ~never about
        # the year it was recently written about).
        years = Counter()
        for t in texts:
            yy = set()
            for y in _YEAR.findall(t):
                iy = int(y)
                if iy < 2005:
                    yy.add(iy)
            for y in _BCE.findall(t):
                yy.add(-int(y))
            years.update(yy)
        if years:
            modal = years.most_common(1)[0][0]
            sec = _period_section(modal, unit_slug)
            if sec:
                votes[sec] += 3.0   # a decisive body-year is strong signal
    if not votes:
        return None
    ranked = votes.most_common(2)
    top_sec, top_w = ranked[0]
    if top_w < MIN_WEIGHT:
        return None
    if len(ranked) > 1 and top_w < MIN_MARGIN * ranked[1][1]:
        return None
    return top_sec


def infer(unit_slug, min_weight=MIN_WEIGHT):
    global MIN_WEIGHT
    MIN_WEIGHT = min_weight
    unit = UNITS_BY_SLUG.get(unit_slug)
    if unit is None:
        raise SystemExit(f'Unknown unit {unit_slug!r}')
    idx = SectionIndex()
    kb = load_kb(unit_slug)
    lex = _build_lexicon(unit_slug, idx, kb)

    # gather question bodies per answerline, for blanks only
    sectioned = set(idx._by_unit.get(unit_slug, {}))
    sectioned |= {k for k, r in kb.items() if r.get('section')}
    data = fetch_unit_questions(unit.freq_params)
    bodies = defaultdict(list)

    def add(ans_san, text):
        key = _primary_key(ans_san)
        if key and key not in sectioned:
            bodies[key].append(text or '')

    for tu in data.get('tossups', []):
        add(tu.get('answer_sanitized', ''),
            tu.get('question_sanitized') or tu.get('question', ''))
    for bo in data.get('bonuses', []):
        parts = bo.get('answers_sanitized') or []
        texts = bo.get('parts_sanitized') or []
        lead = bo.get('leadin_sanitized', '')
        for i, part in enumerate(parts):
            add(part, lead + ' ' + (texts[i] if i < len(texts) else ''))

    disp = {k: v['display'] for k, v in collect(unit_slug).items()}
    ts = datetime.now(timezone.utc).strftime('%Y-%m-%d')
    added = 0
    for key, texts in bodies.items():
        if key in kb:      # blanks only
            continue
        section = _infer_one(texts, lex, unit_slug)
        if section:
            kb[key] = {
                'display': disp.get(key, key), 'type': None,
                'section': section, 'movement': [], 'era': None,
                'country': None, 'creator': None,
                'source': 'inferred', 'ts': ts,
            }
            added += 1
    save_kb(unit_slug, kb)
    print(f'Inferred {unit_slug}: +{added} sections from question text '
          f'({len(bodies)} blank answerlines examined)')
    return added


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('unit', nargs='?')
    ap.add_argument('--all', action='store_true')
    ap.add_argument('--min-weight', type=float, default=MIN_WEIGHT)
    args = ap.parse_args()
    units = [u.slug for u in UNITS] if args.all else [args.unit]
    total = 0
    for u in units:
        total += infer(u, min_weight=args.min_weight)
    if args.all:
        print(f'TOTAL inferred: {total}')


if __name__ == '__main__':
    main()
