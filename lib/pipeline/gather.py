"""
gather.py — One-shot corpus builder for a topic (pipeline v2).

Replaces the first-pass/second-pass fetch dance (answerline fetch, then
"--mentions if sparse", then hand-picked subitem queries) with a single
deterministic pass that an agent never has to steer:

1. Answerline AND text-mention searches for every alias, merged and
   de-duplicated by qbreader _id.
2. Every clue unit is tagged by how it relates to the topic:
     topic    — tossup sentence / bonus part whose answer IS the topic
     work     — question whose answer is one of the topic's works. A
                mention-hit tossup counts as a work when the topic is named
                in its giveaway line or answerline ("...this ballet by
                Bartók" / "Bartók's"); a bonus part counts when its text
                names the topic as creator.
     related  — a passing mention (another answer's question that names
                the topic). Only the sentences naming the topic are kept.
   Bonus parts on answer-hit bonuses that are NOT about the topic (the
   Kodály part of a "Hungarian music" bonus) are dropped unless they name
   the topic — the old digest counted them as topic clues.
3. Tossup sentences and bonus parts are grouped by normalized answerline
   together (so "Concerto for Orchestra" tossups and bonus parts land in
   one group), clustered by digest.cluster_clues, and given stable ids
   (C1, C2, ...). The analysis cites ids instead of estimating counts;
   finalize.py computes frequency/tendency/examples from them and reports
   which clusters no clue entry covers.

Outputs (in --outdir):
    clusters.json      id -> {group, rel, count, rep, members[]}
    digest.txt         what the analysis agent reads (ids, counts, flags)
    questions_ref.json refs for the questions page (via record_fetch)

Usage:
    python lib/pipeline/gather.py "Béla Bartók" --alias Bartok --outdir output/béla_bartók
    python lib/pipeline/gather.py "Carolee Schneemann" --outdir ... [--diff 5-10]
        [--min-year 0] [--category "Fine Arts"]
"""
import argparse
import json
import re
import sys
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
import lib.common  # noqa: F401 — UTF-8 stdio, QBMIRROR_DB
from lib.pipeline.digest import cluster_clues, _is_boilerplate, _tidy
from lib.pipeline.fetch import query_page
from lib.pipeline.parse import extract_tossup_clues, extract_bonus_clues, split_sentences
from lib.questions_store import record_fetch

# Questions below difficulty 5 are middle/high-school; their clues are
# almost always restatements of the college canon.
DEFAULT_DIFFS = [5, 6, 7, 8, 9, 10]
# No year floor: the mirror has no paging cost, and pre-2012 questions add
# ~40% more Bartók tossups. Clusters carry their year range, so stale
# clues are visible as such.
DEFAULT_MIN_YEAR = 0
# Stricter than the old digest's 0.45: frequency is now computed from
# clusters, so an over-merged cluster inflates counts, while an
# under-merged one costs nothing (the agent cites several ids).
SIM_THRESHOLD = 0.6
# Below this many answer-hit questions a topic is sparse (see gather()).
SPARSE_CORE_QUESTIONS = 20


_ASK = re.compile(r"^\s*(name|identify|give|what|which)\b", re.IGNORECASE)


def fold(s: str) -> str:
    s = unicodedata.normalize('NFKD', s or '')
    return ''.join(ch for ch in s if not unicodedata.combining(ch)).lower()


def make_matcher(terms: list[str]):
    pats = [re.compile(r'\b' + re.escape(fold(t)) + r'\b') for t in terms]
    return lambda text: any(p.search(fold(text)) for p in pats)


def norm_answer(answer: str) -> str:
    """Answerline head for display: drop [accept ...], (notes), <tags>,
    leading articles. Bracketed text is removed wherever it sits, so
    "Bela (Viktor Janos) Bartok [accept ...]" -> "Bela Bartok"."""
    a = re.sub(r"<[^>]+>", "", answer or "")
    a = re.sub(r"\[[^\]]*\]?|\([^)]*\)?", " ", a)
    a = re.sub(r"\s+", " ", a).strip().strip('_').strip(' "\'').strip()
    a = re.sub(r"^(the|a|an)\s+", "", a, flags=re.IGNORECASE)
    return a or "?"


def group_key(head: str) -> str:
    """Merge key for answerline heads: case/punctuation/diacritics-blind,
    catalog numbers dropped ("Music for Strings, Percussion and Celesta,
    Sz. 106, BB 114" == "Music for Strings, Percussion, and Celesta")."""
    k = fold(head)
    k = re.sub(r",?\s*\b(sz|bb|op|k|bwv|d|hob|woo)\.?\s*\d+[a-z]?\b.*$", "", k)
    k = re.sub(r"\band\b", " ", k)
    return re.sub(r"[^a-z0-9]+", " ", k).strip()


def _query(term, search_type, diffs, cats, min_year):
    return query_page(term, search_type=search_type, difficulties=diffs,
                      categories=cats, min_year=min_year, exact_phrase=True)


def gather(topic: str, aliases: list[str], diffs, cats, min_year):
    terms = [topic] + aliases
    names = make_matcher(terms)
    words = [w for t in terms for w in t.split() if len(w) > 2]
    tossups, bonuses = {}, {}            # _id -> (question, hit)
    ref_data = []
    for term in terms:
        for st, hit in (("answer", "answer"), ("question", "mention")):
            r = _query(term, st, diffs, cats, min_year)
            ref_data.append((term, st, r))
            for q in r['tossups']:
                if q['_id'] not in tossups or hit == 'answer':
                    tossups[q['_id']] = (q, hit)
            for q in r['bonuses']:
                if q['_id'] not in bonuses or hit == 'answer':
                    bonuses[q['_id']] = (q, hit)

    units = []   # clue dicts with 'rel' and 'group'
    dropped = Counter()
    # Sparse topics keep every sentence of the questions that mention
    # them: a neighbouring sentence often describes the topic's work
    # without naming it ("a book which reimagines this painter as a
    # woman"), and at this size the extra text is cheap. Big topics would
    # drown in it (Bartók: 500+ sentences on violas and Kodály).
    n_core = sum(1 for q, hit in list(tossups.values()) + list(bonuses.values()) if hit == 'answer')
    keep_siblings = n_core < SPARSE_CORE_QUESTIONS
    for q, hit in tossups.values():
        clues = extract_tossup_clues(q)
        # Where each sentence sits in its tossup: 0 = opening line, 1 = the
        # giveaway. finalize.py averages it into a clue's `placement`.
        for i, c in enumerate(clues):
            c['pos'] = round(i / (len(clues) - 1), 3) if len(clues) > 1 else 1.0
        ans = q.get('answer_sanitized', '')
        group = norm_answer(ans)
        if names(ans):
            rel = 'topic' if hit == 'answer' and _is_topic_answer(ans, names) else 'work'
        elif clues and _names_as_creator(clues[-1]['text'], words):
            # "...name this ballet by Bartók" — the whole tossup is about
            # one of the topic's works. A giveaway that merely names the
            # topic ("Acconci and Schneemann worked in which city?") is not.
            rel = 'work'
        else:
            rel = 'related'
        for c in clues:
            r = rel
            if rel == 'related' and not names(c['text']):
                if not keep_siblings or c['is_giveaway']:
                    dropped['related_tossup_sentence'] += 1
                    continue
                r = 'sibling'
            c['rel'], c['group'] = r, ('TOPIC' if r == 'topic' else group)
            units.append(c)

    for q, hit in bonuses.values():
        leadin = q.get('leadin_sanitized', '')
        leadin_names = names(leadin)
        parts = extract_bonus_clues(q)
        # A part that never names the topic can still be about it ("a book
        # which reimagines this painter as a woman" beside a Schneemann
        # part), so siblings of a part that names the topic are kept, in
        # their own low tier, unless the bonus is answered by the topic.
        any_names = any(names(c['text']) or names(c['part_answer']) for c in parts)
        for c in parts:
            pa = c['part_answer']
            if names(pa):
                rel = 'topic' if _is_topic_answer(pa, names) else 'work'
            elif _names_as_creator(c['text'], words) or (
                    _names_as_creator(leadin, words) and not names(pa)
                    and _ASK.search(c['text']) and re.search(r'\b(this|these) (work|piece|opera|ballet|painting|film|novel|poem|play|book|collection|movement|quartet|concerto|symphony|sonata|series|performance)', c['text'], re.I)):
                rel = 'work'
            elif names(c['text']):
                rel = 'related'
            elif any_names and (hit == 'mention' or keep_siblings):
                rel = 'sibling'
            else:
                dropped['offtopic_bonus_part'] += 1
                continue
            c['source']['answer'] = pa
            # Bonus parts run 2-3 facts long; whole parts become clustering
            # magnets that glue unrelated facts together. Split them like
            # tossups; the "Name this..." ask is the part's giveaway.
            for sent in split_sentences(c['text']):
                if rel == 'related' and not names(sent):
                    continue
                if rel == 'sibling' and _ASK.match(sent):
                    continue   # "Name this material" carries no fact
                u = dict(c, text=sent, rel=rel,
                         group='TOPIC' if rel == 'topic' else norm_answer(pa),
                         is_giveaway=bool(_ASK.match(sent)))
                units.append(u)
        if (leadin_names or (keep_siblings and any_names)) and not _is_boilerplate(leadin):
            # The leadin itself often carries a clue ("This composer
            # collected folk songs with Zoltán Kodály...").
            for s in split_sentences(leadin):
                if names(s) or keep_siblings or re.search(r'\bthis (composer|artist|author|man|woman)\b', s, re.I):
                    units.append({'text': s, 'in_power': False, 'is_giveaway': False,
                                  'rel': 'related', 'group': 'bonus leadins',
                                  'source': {'type': 'leadin', 'id': q['_id'],
                                             'set': q.get('set', {}).get('name', ''),
                                             'year': q.get('set', {}).get('year', ''),
                                             'difficulty': q.get('difficulty', ''),
                                             'answer': ''}})

    units = [u for u in units if not _is_boilerplate(u['text'])]
    return units, ref_data, dropped, len(tossups), len(bonuses)


def _is_topic_answer(ans: str, names) -> bool:
    """The answerline names the topic itself rather than one of its works
    ("Béla Bartók [accept Bartók Béla]" vs "Concerto for Orchestra
    [accept Bartók's...]"): the topic's name must be in the head."""
    return names(norm_answer(ans))


def _names_as_creator(text: str, words: list[str]) -> bool:
    """The topic made the thing being asked about: "by Bartók",
    "Bartók's ...", "this Bartók opera", "this five-movement Bartók work",
    "Bartók composed this ...". Such a part/tossup is a work clue, not a
    passing mention."""
    alt = '(?:' + '|'.join(re.escape(fold(w)) for w in words) + ')'
    t = fold(text)
    return bool(
        re.search(r"\bby\s+(?:\w+\s+){0,2}" + alt + r"\b", t)
        or re.search(r"\b" + alt + r"'s\b", t)
        or re.search(r"\b(?:this|these)\s+(?:[\w-]+\s+){0,2}" + alt + r"\b", t)
        or re.search(r"\b" + alt + r"\s+(?:wrote|composed|created|painted|made|performed|"
                     r"designed|directed|built)\s+(?:\w+\s+){0,4}(?:this|these|what)\b", t))


def build(topic, aliases, diffs, cats, min_year, outdir: Path):
    units, ref_data, dropped, n_t, n_b = gather(topic, aliases, diffs, cats, min_year)

    by_group = defaultdict(list)
    labels = defaultdict(Counter)
    for u in units:
        key = group_key(u['group'])
        labels[key][u['group']] += 1
        by_group[(u['rel'], key)].append(u)
    for u in units:
        u['group'] = labels[group_key(u['group'])].most_common(1)[0][0]

    clusters = {}
    order = {'topic': 0, 'work': 1, 'related': 2, 'sibling': 3}
    groups = sorted(by_group.items(),
                    key=lambda kv: (order[kv[0][0]], -len({u['source']['id'] for u in kv[1]})))
    lines = []
    n = 0
    rel_header = None
    for (rel, key), members in groups:
        group = members[0]['group']
        if rel != rel_header:
            rel_header = rel
            lines.append("")
            lines.append({
                'topic': "##### ANSWER IS THE TOPIC #####",
                'work': "##### ANSWER IS ONE OF THE TOPIC'S WORKS / SUBTOPICS #####",
                'related': "##### PASSING MENTIONS (other answers; only sentences naming the topic) #####",
                'sibling': "##### NEIGHBOURING SENTENCES/PARTS of questions that name the topic (mostly "
                           "off-topic; cite only what is indirectly about the topic, ignore the rest) #####",
            }[rel])
        qids = {u['source']['id'] for u in members}
        lines.append("")
        lines.append(f"== {group} ({len(qids)} question{'s' if len(qids) != 1 else ''}) ==")
        for c in _themed(cluster_clues(members, keep_members=True, threshold=SIM_THRESHOLD), lines):
            n += 1
            cid = f"C{n}"
            # Representative first, so digest phrasing ~k == members[k-1]
            # and agents can cite one phrasing as "C12:3".
            mem = sorted(c['members_full'], key=lambda m: m['text'] != c['representative'])
            clusters[cid] = {
                'group': group, 'rel': rel, 'count': len({m['source']['id'] for m in mem}),
                'rep': c['representative'],
                'members': [{
                    'text': m['text'], 'qid': m['source']['id'],
                    'type': m['source']['type'], 'set': m['source'].get('set', ''),
                    'year': m['source'].get('year', ''), 'diff': m['source'].get('difficulty', ''),
                    'power': bool(m.get('in_power')), 'give': bool(m.get('is_giveaway')),
                    'answer': m['source'].get('answer', ''),
                    'pos': m.get('pos'),
                } for m in mem],
            }
            lines.append(_digest_line(cid, clusters[cid], c))

    header = [
        f"=== CLUE DIGEST v2: {topic} ===",
        f"aliases: {', '.join(aliases) or '-'} | diff {diffs} | min_year {min_year} | "
        f"{n_t} tossups + {n_b} bonuses gathered | {len(units)} clue units -> {n} clusters",
        f"dropped: {dict(dropped)}",
        "Each line: [Cid | Nq = distinct questions | diff | years | flags] text (= phrasing 1), "
        "then ~k other phrasings. Cite `C12` for the whole cluster, `C12:3` for one phrasing; "
        "finalize.py computes frequency/tendency/examples.",
        "Flags: PWR = in power, GIVE = giveaway line, B = from bonus parts, L = bonus leadin.",
    ]
    outdir.mkdir(parents=True, exist_ok=True)
    (outdir / 'digest.txt').write_text("\n".join(header + lines) + "\n", encoding='utf-8')
    (outdir / 'clusters.json').write_text(json.dumps(clusters, ensure_ascii=False, indent=1),
                                          encoding='utf-8')
    for term, st, r in ref_data:
        data = {'query_string': term, 'difficulties': diffs, 'min_year': min_year,
                ('answer_matches' if st == 'answer' else 'text_mentions'): r}
        record_fetch(outdir, data, mentions=(st == 'question'))
    digest_chars = sum(len(l) + 1 for l in header + lines)
    print(f"{n_t} tossups + {n_b} bonuses -> {len(units)} units -> {n} clusters "
          f"in {len(by_group)} groups; digest {digest_chars} chars (~{digest_chars // 4} tokens)")
    print(f"dropped: {dict(dropped)}")
    print(f"ANALYZE THIS -> {outdir / 'digest.txt'}")


# A group this large is a single-answerline blob (the composer's own
# answerline carries clues about every work); theme it so the agent reads
# sections-in-waiting instead of a flat list.
_THEME_MIN_CLUSTERS = 14


def _themed(clusters: list[dict], lines: list):
    """Yield clusters in theme order, appending '-- theme --' markers to
    lines as each theme starts. Falls back to flat order without the
    embedding stack."""
    if len(clusters) < _THEME_MIN_CLUSTERS:
        yield from clusters
        return
    give = [c for c in clusters if c['is_giveaway_count'] * 2 >= c['count']]
    rest = [c for c in clusters if c['is_giveaway_count'] * 2 < c['count']]
    try:
        from lib.embed.cluster import theme_indices
        themes, misc = theme_indices([_tidy(c['representative']) for c in rest])
    except Exception as e:  # noqa: BLE001 — no torch/model: flat
        print(f"  (theme grouping unavailable: {e.__class__.__name__}; flat output)")
        yield from clusters
        return
    for group in themes:
        lines.append(f"  -- theme ({sum(rest[i]['count'] for i in group)} clue units) --")
        yield from (rest[i] for i in group)
    if misc:
        lines.append("  -- ungrouped --")
        yield from (rest[i] for i in misc)
    if give:
        # Identifier lines pack many facts into one sentence and glue
        # themes together, so they are emitted un-themed.
        lines.append("  -- giveaway / identifier lines --")
        yield from give


def _digest_line(cid, cl, c) -> str:
    mem = cl['members']
    diffs = sorted({m['diff'] for m in mem if m['diff'] != ''})
    years = sorted({m['year'] for m in mem if m['year']})
    parts = [cid, f"{cl['count']}q"]
    if diffs:
        parts.append(f"d{diffs[0]}" if len(diffs) == 1 else f"d{diffs[0]}-{diffs[-1]}")
    if years:
        parts.append(str(years[0]) if len(years) == 1 else f"{years[0]}-{years[-1]}")
    flags = []
    if sum(m['power'] for m in mem) * 2 >= len(mem) and any(m['power'] for m in mem):
        flags.append('PWR')
    if sum(m['give'] for m in mem) * 2 >= len(mem) and any(m['give'] for m in mem):
        flags.append('GIVE')
    if any(m['type'] == 'bonus' for m in mem):
        flags.append('B')
    if any(m['type'] == 'leadin' for m in mem):
        flags.append('L')
    if flags:
        parts.append(','.join(flags))
    out = f"[{' | '.join(parts)}] {_tidy(cl['rep'])}"
    if cl['rel'] == 'related' or cl['group'] == 'bonus leadins':
        answers = sorted({norm_answer(m['answer']) for m in mem if m['answer']})
        if answers and cl['group'] == 'bonus leadins':
            out += f"  (answers: {'; '.join(answers)})"
    # Show every distinct phrasing up to 3, so the agent can see when a
    # cluster holds two different facts and cite it from both entries.
    seen = {cl['rep']}
    for k, m in enumerate(mem, 1):
        if m['text'] not in seen and len(seen) < 4:
            seen.add(m['text'])
            out += f"\n      ~{k} {_tidy(m['text'])}"
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('topic')
    ap.add_argument('--alias', action='append', default=[],
                    help='extra search term (surname, alternate spelling); repeatable')
    ap.add_argument('--diff', default='5-10')
    ap.add_argument('--min-year', type=int, default=DEFAULT_MIN_YEAR)
    ap.add_argument('--category', action='append', default=None)
    ap.add_argument('--outdir', required=True)
    a = ap.parse_args()
    lo, _, hi = a.diff.partition('-')
    diffs = list(range(int(lo), int(hi or lo) + 1))
    build(a.topic, a.alias, diffs, a.category, a.min_year, Path(a.outdir))


if __name__ == '__main__':
    main()
