"""
finalize.py — Compute, check and stamp a v2 analysis (pipeline v2).

The analysis agent writes judgment only: sections, clue statements, prose,
cards — each clue entry and card citing the digest cluster ids it rests
on (`src: ["C3", "C17:2"]` — a whole cluster, or one phrasing of it). Everything countable is computed here from
clusters.json (written by gather.py), so it is exact and reproducible:

    frequency  distinct questions across the cited clusters' members
    tendency   giveaway / power / mid from the members' giveaway & power flags
    placement  {avg, n}: mean position within its tossups (0 opening, 1 giveaway)
    examples   up to 3 real member phrasings

Then it checks the draft and reports, in order of severity:

    ERROR  unknown or missing src ids; a cluster asked about in 2+
           questions that nothing cites and `uncited` does not excuse;
           missing required fields; card structure violations
    WARN   singleton clusters left uncited; clue entries with no card; multi-fact or answer-leaking card fronts; short
           descriptions

Usage:
    python lib/pipeline/finalize.py OUTDIR            # compute + write + report
    python lib/pipeline/finalize.py OUTDIR --check    # report only

Also writes evidence.txt (each entry/card beside the sentences it cites)
for the independent verify pass.

Exit status 1 when any ERROR remains — the agent loops until it is 0.
"""
import argparse
import datetime
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
import lib.common  # noqa: F401 — UTF-8 stdio
from lib.pipeline.digest import _tidy

REQUIRED = ['topic', 'summary', 'works', 'comprehensive_summary', 'category',
            'subcategory', 'genre', 'year', 'continent', 'country', 'tags']
GENERAL = re.compile(r'general|biograph|other works|connections', re.I)
EXAMPLE_MAX = 220


def tendency(members: list[dict]) -> str:
    tossup = [m for m in members if m['type'] == 'tossup']
    if not tossup:
        # Bonus parts carry no buzz position; an ask line is still a giveaway.
        return 'giveaway' if sum(m['give'] for m in members) * 2 > len(members) else 'mid'
    if sum(m['give'] for m in tossup) * 2 >= len(tossup):
        return 'giveaway'
    if sum(m['power'] for m in tossup) * 2 >= len(tossup):
        return 'power'
    return 'mid'


def placement(members: list[dict]):
    """Average position of the clue within its tossups, 0 = opening line,
    1 = giveaway, with the number of tossup sentences it rests on. Bonus
    parts have no buzz position and are left out; None when no tossup
    sentence backs the clue (or clusters.json predates positions)."""
    pos = [m['pos'] for m in members if m['type'] == 'tossup' and m.get('pos') is not None]
    if not pos:
        return None
    return {'avg': round(sum(pos) / len(pos), 2), 'n': len(pos)}


def examples(members: list[dict], statement: str) -> list[str]:
    out, seen = [], set()
    for m in sorted(members, key=lambda m: len(m['text'])):
        t = _tidy(m['text'])
        if len(t) > EXAMPLE_MAX:
            t = t[:EXAMPLE_MAX].rsplit(' ', 1)[0] + '…'
        k = t.lower()
        if k in seen or k == statement.lower():
            continue
        seen.add(k)
        out.append(t)
        if len(out) == 3:
            break
    return out


def resolve(src, clusters, where, errors) -> list[dict]:
    if not src:
        errors.append(f"{where}: no `src` ids")
        return []
    members = []
    for ref in src:
        cid, _, k = ref.partition(':')
        if cid not in clusters:
            errors.append(f"{where}: unknown cluster id {ref}")
            continue
        mem = clusters[cid]['members']
        if k:
            if not k.isdigit() or not 1 <= int(k) <= len(mem):
                errors.append(f"{where}: {ref} — {cid} has {len(mem)} phrasings")
                continue
            members.append(mem[int(k) - 1])
        else:
            members.extend(mem)
    return members


def _expand(src) -> set:
    """Refs as (cluster, phrasing) pairs; '*' = the whole cluster."""
    return {(r.partition(':')[0], r.partition(':')[2] or '*') for r in src or []}


def _covers(entry: set, card: set) -> bool:
    """Every card ref is cited by the entry (C3 covers C3:2)."""
    return bool(card) and all(ref in entry or (ref[0], '*') in entry for ref in card)


def leak_words(back: str) -> set[str]:
    """Distinctive words of the card's answer (title only, not the creator
    in parentheses) — if they appear on the front, the card gives itself
    away."""
    title = re.sub(r'\([^)]*\)', '', back)
    return {w for w in re.findall(r"[A-Za-zÀ-ÿ']{5,}", title)
            if w.lower() not in _GENERIC_TITLE_WORDS}


# Title words that name a genre or forces rather than the work itself —
# "string groups" on the front doesn't give away "String Quartets".
_GENERIC_TITLE_WORDS = {
    'other', 'works', 'general', 'their', 'about', 'string', 'strings', 'quartet',
    'quartets', 'piano', 'pianos', 'orchestra', 'percussion', 'concerto', 'concertos',
    'symphony', 'sonata', 'sonatas', 'violin', 'violins', 'viola', 'cello', 'suite',
    'dances', 'music', 'opera', 'ballet', 'painting', 'portrait', 'series', 'poems',
    'novel', 'stories', 'theory', 'principle', 'number'}


EVIDENCE_PER_ENTRY = 6


def write_evidence(path: Path, a: dict, cards: list, clusters: dict) -> None:
    """Every clue entry next to the exact source sentences it cites, then
    every card pointing at the entries it tests — what an independent
    verifier reads to check faithfulness without loading clusters.json."""
    def cited(src):
        seen, out = set(), []
        for ref in src or []:
            cid, _, k = ref.partition(':')
            mem = clusters.get(cid, {}).get('members', [])
            if k.isdigit() and 1 <= int(k) <= len(mem):
                mem = [mem[int(k) - 1]]
            for m in mem:
                if m['text'] not in seen:
                    seen.add(m['text'])
                    out.append(f"      {cid} [{m['type']} {m['set']} d{m['diff']}"
                               f"{' ans: ' + m['answer'][:40] if m['answer'] else ''}] {_tidy(m['text'])}")
        if len(out) > EVIDENCE_PER_ENTRY:
            out = out[:EVIDENCE_PER_ENTRY] + [f"      (+{len(out) - EVIDENCE_PER_ENTRY} more phrasings)"]
        return out
    lines = [f"EVIDENCE: {a.get('topic')} — each entry with the source sentences it cites; "
             f"then each card with the entries (S#.E#) it tests", ""]
    entries = []   # (label, section, src set)
    for si, w in enumerate(a.get('works', []), 1):
        lines.append(f"## S{si} {w.get('name')} [{w.get('indicator')}]")
        for i, c in enumerate(w.get('clues', []), 1):
            label = f"S{si}.E{i}"
            entries.append((label, w.get('name'), _expand(c.get('src'))))
            lines.append(f"  {label} ({c.get('frequency', '?')}q): {c.get('clue')}")
            if c.get('note'):
                lines.append(f"      note: {c['note']}")
            lines.extend(cited(c.get('src')))
        lines.append("")
    lines.append("## CARDS")
    for i, card in enumerate(cards, 1):
        if card.get('type') == 'image':
            continue
        csrc = _expand(card.get('src'))
        tests = [lab for lab, sec, esrc in entries if sec == card.get('work') and _covers(esrc, csrc)]
        lines.append(f"  K{i}: {card.get('front')}  =>  {card.get('back')}   "
                     f"[{card.get('work')}] tests {', '.join(tests) or '(no matching entry)'}")
        if not tests:
            lines.extend(cited(card.get('src')))
    path.write_text("\n".join(lines) + "\n", encoding='utf-8')


def finalize(outdir: Path, write: bool) -> int:
    clusters = json.loads((outdir / 'clusters.json').read_text(encoding='utf-8'))
    a = json.loads((outdir / 'analysis.json').read_text(encoding='utf-8'))
    cards_path = outdir / 'cards.json'
    cards = json.loads(cards_path.read_text(encoding='utf-8')) if cards_path.exists() else []
    errors, warns = [], []

    for k in REQUIRED:
        if k not in a or (k in ('summary', 'comprehensive_summary', 'works') and not a[k]):
            errors.append(f"missing/empty field `{k}`")
    if len(a.get('comprehensive_summary', '')) < 400:
        warns.append("comprehensive_summary under 400 chars")

    cited = {}
    names = set()
    n_entries = 0
    for w in a.get('works', []):
        names.add(w.get('name'))
        if not w.get('indicator'):
            errors.append(f"section '{w.get('name')}': no indicator")
        if not GENERAL.search(w.get('name', '')) and len(w.get('description', '')) < 120:
            warns.append(f"section '{w.get('name')}': description under 120 chars")
        for i, c in enumerate(w.get('clues', [])):
            n_entries += 1
            where = f"'{w.get('name')}' clue {i + 1}"
            members = resolve(c.get('src'), clusters, where, errors)
            for ref in c.get('src') or []:
                cited.setdefault(ref.partition(':')[0], []).append(where)
            if not members:
                continue
            c['frequency'] = len({m['qid'] for m in members})
            c['tendency'] = tendency(members)
            c['examples'] = examples(members, c.get('clue', ''))
            pl = placement(members)
            if pl is None:
                c.pop('placement', None)
            else:
                c['placement'] = pl

    # Coverage: every cluster is either cited or explicitly excused.
    excused = a.get('uncited', {})
    for cid in excused:
        if cid not in clusters:
            errors.append(f"`uncited` names unknown id {cid}")
    weight = lambda ids: sum(len(clusters[i]['members']) for i in ids)
    core = [cid for cid, c in clusters.items() if c['rel'] in ('topic', 'work')]
    missing = [cid for cid in clusters if cid not in cited and cid not in excused]
    for cid in missing:
        c = clusters[cid]
        msg = f"{cid} ({c['count']}q, {c['rel']}, {c['group']}) uncited: {_tidy(c['rep'])[:110]}"
        if c['rel'] == 'sibling':
            continue   # sibling parts are mostly off-topic: never nag
        (errors if c['count'] >= 2 and c['rel'] in ('topic', 'work') else warns).append(msg)

    # Cards
    card_keys = []
    fronts = set()
    for i, card in enumerate(cards):
        where = f"card {i + 1}"
        if card.get('type') not in ('basic', 'image'):
            errors.append(f"{where}: type must be basic|image")
        if card.get('work') not in names:
            errors.append(f"{where}: work '{card.get('work')}' matches no section name")
        if card.get('type') == 'image':
            continue
        front, back = card.get('front', ''), card.get('back', '')
        ind = card.get('indicator', '')
        if not front.startswith(f"{ind}: "):
            errors.append(f"{where}: front must start with '{ind}: '")
        if not back:
            errors.append(f"{where}: empty back")
        if front in fronts:
            errors.append(f"{where}: duplicate front")
        fronts.add(front)
        body = front[len(ind) + 2:]
        if ';' in body:
            warns.append(f"{where}: ';' on front — one fact per card? {body[:90]}")
        leaked = [w for w in leak_words(back) if re.search(r'\b' + re.escape(w) + r'\b', body, re.I)]
        if leaked:
            warns.append(f"{where}: front contains answer word(s) {leaked}: {body[:90]}")
        members = resolve(card.get('src'), clusters, where, errors)
        card_keys.append((card.get('work'), _expand(card.get('src'))))
        if members:
            card['frequency'] = len({m['qid'] for m in members})
        card['tags'] = card.get('tags') or []

    uncarded = 0
    for w in a.get('works', []):
        for c in w.get('clues', []):
            # A card covers an entry when it sits in the same section and
            # cites a subset of the entry's sources — sharing one cluster
            # with a sibling entry's card is not enough.
            esrc = _expand(c.get('src'))
            if not any(k[0] == w['name'] and _covers(esrc, k[1]) for k in card_keys):
                uncarded += 1
                warns.append(f"no card for '{w['name']}' clue (freq {c.get('frequency', '?')}): "
                             f"{c.get('clue', '')[:80]}")

    # Excused clusters (noise the agent deliberately set aside) leave the
    # denominator: coverage measures material skipped, not noise gathered.
    units_core = weight([cid for cid in core if cid not in excused])
    units_cited = weight([cid for cid in core if cid in cited])
    stats = {
        'pipeline': 'v2',
        'date': datetime.date.today().isoformat(),
        'questions': len({m['qid'] for c in clusters.values() for m in c['members']}),
        'clusters': len(clusters),
        'clue_entries': n_entries,
        'cards': len(cards),
        'coverage': round(units_cited / units_core, 3) if units_core else 1.0,
    }
    a['build'] = stats

    print(f"sections {len(a.get('works', []))} | clue entries {n_entries} | cards {len(cards)} | "
          f"coverage {stats['coverage']:.0%} of non-excused topic/work clue units cited "
          f"({len(missing)} clusters uncited, {len(excused)} excused) | "
          f"{uncarded} entries without a card")
    for w in a.get('works', []):
        qs = set()
        for c in w.get('clues', []):
            qs |= {m['qid'] for m in resolve(c.get('src'), clusters, '', [])}
        print(f"  {len(qs):3d}q  {w.get('name')}")
    for e in errors:
        print(f"ERROR {e}")
    for w in warns:
        print(f"WARN  {w}")

    write_evidence(outdir / 'evidence.txt', a, cards, clusters)

    if write:
        (outdir / 'analysis.json').write_text(json.dumps(a, ensure_ascii=False, indent=2) + "\n",
                                              encoding='utf-8')
        cards_path.write_text(json.dumps(cards, ensure_ascii=False, indent=2) + "\n",
                              encoding='utf-8')
    return 1 if errors else 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('outdir')
    ap.add_argument('--check', action='store_true', help='report only; do not write')
    args = ap.parse_args()
    sys.exit(finalize(Path(args.outdir), write=not args.check))


if __name__ == '__main__':
    main()
