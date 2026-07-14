"""answerline_kb.py — a durable, reusable metadata store for answerlines.

Most question answerlines are never curated into an overview or given a
wiki page, so the reader can't group or facet them. This builds a
persistent knowledge base keyed by normalized answerline (per unit) with
a structured record — derived once, committed, and re-derived cheaply
for new sets only:

    output/_answerlines/{unit}.json
      "salvador dali": {
        "display": "Salvador Dalí", "type": "person",
        "section": "Surrealism and Dada", "movement": ["Surrealism"],
        "era": "1900–1945", "country": "Spain", "creator": null,
        "source": "llm", "model": "...", "ts": "..."
      }

Consumers: publish.py fills catalog section/era/movement from here (so
the reader sections + facets the whole corpus); the sweep matcher and
overview gap-finding read `type`/`display`; the map reads `country`.

Mechanical fields (section via SectionIndex, plus anything a wiki page
already knows) pre-fill records so the LLM only spends tokens on genuine
gaps. Enrichment is incremental — answerlines already in the store are
skipped, so a re-run after `sync` touches only new answerlines.

    python lib/sweep/answerline_kb.py prep UNIT [--limit N]
        Collect the unit's answerlines not yet in the store, attach a
        disambiguating giveaway snippet, and emit _work/{unit}/batch_NN
        .jsonl + INSTRUCTIONS.txt for one enrichment agent.
    python lib/sweep/answerline_kb.py compose UNIT
        Merge the agent's batch_NN.out.jsonl into the committed store.
    python lib/sweep/answerline_kb.py status
"""
import argparse
import json
import re
import sys as _sys
from pathlib import Path as _Path

_sys.path.insert(0, str(_Path(__file__).resolve().parent.parent.parent))
from lib.common import CATEGORIES_DIR, OUTPUT_DIR
from lib.sweep.answerlines import normalize
from lib.sweep.capture_questions import fetch_unit_questions
from lib.sweep.section_index import SectionIndex, candidate_keys
from lib.units import UNITS, UNITS_BY_SLUG

KB_DIR = OUTPUT_DIR / '_answerlines'
WORK_DIR = KB_DIR / '_work'
BATCH_SIZE = 100

ERA_BUCKETS = ['Pre-1500', '1500s', '1600s', '1700s', '1800s',
               '1900–1945', 'Post-1945']
TYPES = ['person', 'work', 'movement', 'place', 'concept',
         'common-link', 'other']

_SENT = re.compile(r'(?<=[.!?])\s+')


def kb_path(unit_slug: str) -> _Path:
    return KB_DIR / f'{unit_slug}.json'


def load_kb(unit_slug: str) -> dict:
    p = kb_path(unit_slug)
    if p.exists():
        try:
            return json.loads(p.read_text(encoding='utf-8'))
        except (OSError, json.JSONDecodeError):
            pass
    return {}


def save_kb(unit_slug: str, kb: dict) -> None:
    KB_DIR.mkdir(parents=True, exist_ok=True)
    kb_path(unit_slug).write_text(
        json.dumps(kb, indent=1, ensure_ascii=False, sort_keys=True),
        encoding='utf-8')


def _primary_key(answer_sanitized: str) -> str:
    keys = candidate_keys(answer_sanitized)
    return keys[0] if keys else ''


def _giveaway(question: str) -> str:
    """A short identifying snippet — the last (giveaway) sentence."""
    if not question:
        return ''
    sents = [s.strip() for s in _SENT.split(question) if s.strip()]
    tail = sents[-1] if sents else question
    tail = re.sub(r'^for (?:10|ten|15|fifteen|20|twenty) points,?\s*', '',
                  tail, flags=re.I)
    return tail[:220]


def collect(unit_slug: str) -> dict:
    """Distinct answerlines in the unit's questions -> {key: {display,
    freq, clue, section}} (section is the mechanical result or None)."""
    unit = UNITS_BY_SLUG[unit_slug]
    data = fetch_unit_questions(unit.freq_params)
    idx = SectionIndex()
    agg: dict[str, dict] = {}

    def add(answer_san: str, answer_raw: str, question: str):
        key = _primary_key(answer_san)
        if not key:
            return
        rec = agg.get(key)
        if rec is None:
            section = idx.section_for(unit.category, unit.subcategory, '',
                                      answer_raw or answer_san)
            rec = agg[key] = {
                'display': (answer_san.split('[')[0].split('(')[0].strip()
                            or answer_san),
                'freq': 0, 'clue': _giveaway(question),
                'section': section[1] if section else None,
            }
        rec['freq'] += 1

    for tu in data.get('tossups', []):
        add(tu.get('answer_sanitized', ''), tu.get('answer', ''),
            tu.get('question_sanitized') or tu.get('question', ''))
    for bo in data.get('bonuses', []):
        parts = bo.get('answers_sanitized') or []
        raws = bo.get('answers') or []
        texts = bo.get('parts_sanitized') or bo.get('parts') or []
        for i, part in enumerate(parts):
            add(part, raws[i] if i < len(raws) else part,
                texts[i] if i < len(texts) else '')
    return agg


INSTRUCTIONS = """\
You are enriching answerline metadata for the quizbowl unit "{title}"
(category: {category}). Work only in this directory ({work_dir}); write
each output file once, do NOT re-read or re-verify — a script validates.

For every batch_NN.jsonl here, write batch_NN.out.jsonl: one JSON object
per input line, SAME ORDER, echoing the input "id" exactly. Input lines:
  {{"id": <int>, "answer": "<display>", "freq": <n>, "clue": "<giveaway>"}}
The clue is one sentence from a real question — use it to disambiguate
(e.g. which "Vincent"). Output objects:
  {{"id": <int>, "type": "...", "section": "...", "movement": [...],
    "era": "...", "country": "...", "creator": "..."}}

Fields (leave "" / [] when genuinely unsure — a blank beats a wrong guess):
- type: one of {types}. Use "common-link" for thematic "what is depicted
  / what concept" answerlines (e.g. journalists, nudity, prayer, red);
  "work" for a specific artwork/piece; "person" for a creator/figure.
- section: the ONE best-fitting section from this unit's list below, or
  "" if it is a common-link / does not fit any:
{sections}
- movement: art movement(s) / school(s) / style(s), e.g. ["Surrealism"];
  [] if none apply.
- era: one of {eras}, by the work's creation or the person's floruit; ""
  if timeless/unknown.
- country: the primary country of origin/association; "" if none.
- creator: for a "work", the artist/creator's common name; else "".

Accuracy over coverage. Do not invent. Echo ids exactly; never drop,
merge, add, or reorder lines.
"""


def prep(unit_slug: str, limit: int | None = None) -> None:
    unit = UNITS_BY_SLUG.get(unit_slug)
    if unit is None:
        raise SystemExit(f'Unknown unit {unit_slug!r}')
    agg = collect(unit_slug)
    kb = load_kb(unit_slug)

    # Target the answerlines that need enrichment: not already in the store
    # (incremental) and not already sectioned by the mechanical index. The
    # frequent curated answerlines are sectioned mechanically and typically
    # have wiki metadata, so the LLM's tokens go to the uncovered tail.
    in_store = sum(1 for k in agg if k in kb)
    todo = [(k, v) for k, v in agg.items()
            if k not in kb and v['section'] is None]
    todo.sort(key=lambda kv: -kv[1]['freq'])
    if limit:
        todo = todo[:limit]

    wdir = WORK_DIR / unit_slug
    wdir.mkdir(parents=True, exist_ok=True)
    for old in wdir.glob('batch_*.jsonl'):
        old.unlink()

    id_map = {}
    n_batches = 0
    for start in range(0, len(todo), BATCH_SIZE):
        n_batches += 1
        lines = []
        for i, (key, rec) in enumerate(todo[start:start + BATCH_SIZE]):
            gid = start + i
            id_map[gid] = key
            lines.append(json.dumps({
                'id': gid, 'answer': rec['display'],
                'freq': rec['freq'], 'clue': rec['clue'],
            }, ensure_ascii=False))
        (wdir / f'batch_{n_batches:02d}.jsonl').write_text(
            '\n'.join(lines) + '\n', encoding='utf-8')

    (wdir / 'id_map.json').write_text(
        json.dumps(id_map, ensure_ascii=False), encoding='utf-8')

    ov = json.loads((CATEGORIES_DIR / unit_slug / 'overview.json')
                    .read_text(encoding='utf-8')) if (
        CATEGORIES_DIR / unit_slug / 'overview.json').exists() else {}
    sections = [s['name'] for s in ov.get('sections', [])]
    (wdir / 'INSTRUCTIONS.txt').write_text(
        INSTRUCTIONS.format(
            title=unit.title, category=unit.category, work_dir=str(wdir),
            types=', '.join(TYPES), eras=', '.join(ERA_BUCKETS),
            sections='\n'.join('    - ' + s for s in sections) or '    (none)'),
        encoding='utf-8')
    deferred = max(0, len(agg) - in_store - len(todo))
    print(f'Prepped {unit_slug}: {len(todo)} answerlines to enrich '
          f'({in_store} already in store'
          + (f', {deferred} deferred by --limit' if deferred else '')
          + f') in {n_batches} batch(es) under {wdir}')


def _clean(rec: dict) -> dict:
    section = (rec.get('section') or '').strip() or None
    era = (rec.get('era') or '').strip()
    out = {
        'type': (rec.get('type') or '').strip() or None,
        'section': section,
        'movement': [m for m in (rec.get('movement') or []) if m],
        'era': era if era in ERA_BUCKETS else None,
        'country': (rec.get('country') or '').strip() or None,
        'creator': (rec.get('creator') or '').strip() or None,
    }
    return out


def compose(unit_slug: str) -> None:
    from datetime import datetime, timezone
    wdir = WORK_DIR / unit_slug
    id_map = json.loads((wdir / 'id_map.json').read_text(encoding='utf-8'))
    agg = collect(unit_slug)
    key_display = {k: v['display'] for k, v in agg.items()}

    kb = load_kb(unit_slug)
    ts = datetime.now(timezone.utc).strftime('%Y-%m-%d')
    added = bad = 0
    for out in sorted(wdir.glob('batch_*.out.jsonl')):
        for raw in out.read_text(encoding='utf-8').splitlines():
            raw = raw.strip()
            if not raw:
                continue
            try:
                rec = json.loads(raw)
            except json.JSONDecodeError:
                bad += 1
                continue
            key = id_map.get(str(rec.get('id')))
            if not key or key in kb:
                bad += 1 if not key else 0
                continue
            entry = _clean(rec)
            entry['display'] = key_display.get(key, key)
            entry['source'] = 'llm'
            entry['ts'] = ts
            kb[key] = entry
            added += 1
    save_kb(unit_slug, kb)
    print(f'Composed {unit_slug}: +{added} enriched answerlines '
          f'({len(kb)} total in store, {bad} malformed lines ignored)')


class KBLookup:
    """Read-side view over all committed answerline shards, for publish
    and any other consumer: resolve a question's (taxonomy, answer) to its
    enriched record."""

    def __init__(self, kb_dir: _Path = KB_DIR):
        self._by_unit = {}
        for unit in UNITS:
            kb = load_kb(unit.slug)
            if kb:
                self._by_unit[unit.slug] = kb

    def record(self, category: str, subcategory: str,
               alternate_subcategory: str, answer: str):
        from lib.units import unit_for_guide
        u = unit_for_guide(category or '', subcategory or '',
                           alternate_subcategory or '')
        if not u:
            return None
        kb = self._by_unit.get(u.slug)
        if not kb:
            return None
        for key in candidate_keys(answer):
            rec = kb.get(key)
            if rec:
                return rec
        return None

    def __bool__(self):
        return bool(self._by_unit)


def status() -> None:
    for unit in UNITS:
        kb = load_kb(unit.slug)
        secd = sum(1 for v in kb.values() if v.get('section'))
        print(f'{len(kb):6} enriched ({secd} sectioned)  {unit.slug}')


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    sub = ap.add_subparsers(dest='cmd', required=True)
    pr = sub.add_parser('prep'); pr.add_argument('unit')
    pr.add_argument('--limit', type=int, default=None)
    co = sub.add_parser('compose'); co.add_argument('unit')
    sub.add_parser('status')
    args = ap.parse_args()
    if args.cmd == 'prep':
        prep(args.unit, limit=args.limit)
    elif args.cmd == 'compose':
        compose(args.unit)
    else:
        status()


if __name__ == '__main__':
    main()
