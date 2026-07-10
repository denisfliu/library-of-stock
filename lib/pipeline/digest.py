"""
digest.py — Compress parsed clues into a token-efficient digest for analysis.

Quizbowl clues are highly redundant: the same fact recurs across dozens of
questions, phrased slightly differently. The analysis step only needs one
representative phrasing per fact plus an accurate count — so we cluster
near-duplicate sentences deterministically *before* the LLM reads anything.

On a big topic (Beethoven: ~100 tossups) this cuts the analysis input from
~50k tokens of raw clues to <10k, while making the `frequency` field a
computed count instead of an LLM estimate.

The full formatted clue text is still written alongside (clues_full.txt)
for spot-checking and for the questions page.
"""

import re
from collections import Counter

# Words too common to signal that two clues share a fact.
_STOPWORDS = {
    'a', 'an', 'and', 'are', 'as', 'at', 'be', 'by', 'for', 'from', 'had',
    'has', 'have', 'he', 'her', 'his', 'in', 'is', 'it', 'its', 'name',
    'of', 'on', 'one', 'or', 'that', 'the', 'this', 'these', 'those', 'to',
    'was', 'were', 'which', 'with', 'points', 'ten', 'work', 'works',
    'composer', 'author', 'artist', 'man', 'title', 'titular',
}

_MIN_SHARED = 2       # clusters must share at least this many content words
_SIM_THRESHOLD = 0.45


_BOILERPLATE = re.compile(
    r"^\s*(note to (players|moderator|teams)|description acceptable"
    r"|two answers required|name the|answer the following)"
    r"|(composer and (genre|type|piece) .{0,20}required)", re.IGNORECASE)


def _is_boilerplate(text: str) -> bool:
    """Moderator instructions carry no study value."""
    return bool(_BOILERPLATE.search(text)) and len(text) < 120


def _norm_answer(answer: str) -> str:
    """Collapse an answerline to its accepted head form for grouping."""
    a = re.sub(r"[\[(].*", "", answer)         # drop [accept ...] / (...)
    a = re.sub(r"<[^>]+>", "", a)
    return a.strip().strip("_").strip() or "?"


def _content_words(text: str) -> frozenset:
    words = re.findall(r"[a-zà-ÿ0-9']+", text.lower())
    return frozenset(w for w in words if len(w) > 2 and w not in _STOPWORDS)


def _weighted_containment(a: frozenset, b: frozenset, weight: dict) -> float:
    """Overlap score dominated by *rare* shared words.

    Two clues about the same fact share its distinctive entities
    ("Heiligenstadt", "Waldstein") but little of their long connective
    phrasing, so plain Jaccard under-merges badly. Weight each word by
    inverse document frequency and normalize by the smaller set, so a
    short restatement of a long clue still matches.
    """
    shared = a & b
    if len(shared) < _MIN_SHARED:
        return 0.0
    shared_w = sum(weight[w] for w in shared)
    denom = min(sum(weight[w] for w in a), sum(weight[w] for w in b))
    return shared_w / denom if denom else 0.0


def cluster_clues(clues: list[dict]) -> list[dict]:
    """Greedy single-pass clustering of clue dicts by content-word overlap.

    Each clue dict needs 'text' and 'source'. Returns clusters sorted by
    size descending:
        {representative, count, variants, sources, in_power_count,
         is_giveaway_count}
    """
    word_sets = [_content_words(c.get('text', '')) for c in clues]
    df = Counter(w for ws in word_sets for w in ws)
    n = max(len(clues), 1)
    # Inverse document frequency; words in half the clues are near-worthless
    # signals, words in one or two clues are strong ones.
    weight = {w: 1.0 / (1.0 + 10.0 * dfw / n) for w, dfw in df.items()}

    clusters: list[dict] = []
    for clue, words in zip(clues, word_sets):
        best, best_sim = None, 0.0
        for c in clusters:
            sim = _weighted_containment(words, c['_words'], weight)
            if sim > best_sim:
                best, best_sim = c, sim
        if best is not None and best_sim >= _SIM_THRESHOLD:
            best['count'] += 1
            best['members'].append(clue)
            # Extend the cluster's word set so paraphrase chains attach,
            # but only with words already seen twice somewhere — keeps a
            # single verbose member from making the cluster a magnet.
            best['_words'] = best['_words'] | frozenset(
                w for w in words if df[w] >= 2)
        else:
            clusters.append({
                'representative': clue.get('text', ''),
                'count': 1,
                'members': [clue],
                '_words': words,
            })

    for c in clusters:
        members = c['members']
        # Median-length member: informative without being the bloated one.
        by_len = sorted(members, key=lambda m: len(m.get('text', '')))
        c['representative'] = by_len[len(by_len) // 2]['text']
        c['in_power_count'] = sum(1 for m in members if m.get('in_power'))
        c['is_giveaway_count'] = sum(1 for m in members if m.get('is_giveaway'))
        variants = [m['text'] for m in members if m['text'] != c['representative']]
        # One variant phrasing is enough to sanity-check the cluster.
        c['variants'] = variants[:1]
        years = [m.get('source', {}).get('year') for m in members]
        years = [y for y in years if y]
        c['year_range'] = (min(years), max(years)) if years else None
        diffs = [m.get('source', {}).get('difficulty') for m in members]
        diffs = [d for d in diffs if d != '']
        c['diff_range'] = (min(diffs), max(diffs)) if diffs else None
        del c['_words']
        del c['members']

    clusters.sort(key=lambda c: -c['count'])
    return clusters


def _cluster_header(c: dict) -> str:
    parts = [f"{c['count']}x"]
    if c['diff_range']:
        lo, hi = c['diff_range']
        parts.append(f"diff {lo}" if lo == hi else f"diff {lo}-{hi}")
    if c['year_range']:
        lo, hi = c['year_range']
        parts.append(str(lo) if lo == hi else f"{lo}-{hi}")
    flags = []
    if c['in_power_count'] >= max(1, c['count'] // 2):
        flags.append('PWR')
    if c['is_giveaway_count'] >= max(1, c['count'] // 2):
        flags.append('GIVE')
    if flags:
        parts.append(','.join(flags))
    return ' | '.join(parts)


_SINGLETON_MAX_CHARS = 200
_FTP = re.compile(r"[—–,-]?\s*for (10|ten) points[,:]?\s*", re.IGNORECASE)


def _tidy(text: str) -> str:
    """Drop the 'For 10 points' marker — the GIVE flag already carries it."""
    return _FTP.sub(" ", text).strip()


def _emit_clusters(lines: list, clusters: list) -> None:
    singletons = []
    for c in clusters:
        if c['count'] == 1:
            singletons.append(c)
            continue
        lines.append(f"[{_cluster_header(c)}]")
        lines.append(f"  {_tidy(c['representative'])}")
        for v in c['variants']:
            lines.append(f"  ~ {_tidy(v)}")
    for c in singletons:
        text = _tidy(c['representative'])
        if len(text) > _SINGLETON_MAX_CHARS:
            text = text[:_SINGLETON_MAX_CHARS] + "…"
        lines.append(f"  [1x] {text}")


def format_digest(parsed: dict, bonus_parsed: dict | None = None) -> str:
    """Render a parsed clue set (from parse.parse_answer_clues) as a digest.

    Clues are grouped by answerline first (an answerline search returns
    questions on many related answers — symphonies, sonatas, the composer
    himself), then clustered within each group. The answer groups map
    directly onto the analysis's work sections.
    """
    lines = []
    query = parsed['query_string']
    stats = parsed['stats']

    def usable(clues):
        return [c for c in clues if not _is_boilerplate(c.get('text', ''))]

    tossups = usable(parsed['tossup_clues'])
    bonuses = usable(parsed['bonus_clues'])

    # Group tossup clues by their (normalized) answerline.
    by_answer: dict[str, list] = {}
    for c in tossups:
        by_answer.setdefault(_norm_answer(c.get('source', {}).get('answer', '?')), []).append(c)

    lines.append(f"=== CLUE DIGEST: {query} ===")
    lines.append(
        f"{stats['tossup_questions']} tossups ({stats['tossup_clue_sentences']} sentences) | "
        f"{stats['bonus_questions']} bonuses ({stats['bonus_clue_parts']} parts)")
    lines.append("Grouped by answerline, then clustered; counts are computed — "
                 "use them directly as the `frequency` field. Full text: clues.txt")
    lines.append("")
    lines.append("--- TOSSUP CLUES BY ANSWERLINE ---")

    for answer, group in sorted(by_answer.items(), key=lambda kv: -len(kv[1])):
        n_questions = len({c['source']['id'] for c in group})
        lines.append("")
        lines.append(f"== ANSWER: {answer} ({n_questions} question{'s' if n_questions != 1 else ''}) ==")
        _emit_clusters(lines, cluster_clues(group))

    lines.append("")
    lines.append("--- BONUS PART CLUSTERS ---")
    _emit_clusters(lines, cluster_clues(bonuses))
    lines.append("")

    # Bonus answers matter for sub-topic discovery: list distinct part
    # answers with counts so the analysis can spot recurring sub-answers.
    part_answers = Counter(
        re.sub(r'\s*[\[(].*', '', clue.get('part_answer', '')).strip()
        for clue in parsed['bonus_clues'] if clue.get('part_answer'))
    part_answers.pop('', None)
    if part_answers:
        lines.append("--- RECURRING BONUS PART ANSWERS ---")
        for ans, n in part_answers.most_common():
            if n >= 2:
                lines.append(f"  {n}x {ans}")
        lines.append("")

    return "\n".join(lines)
