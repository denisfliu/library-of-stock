"""infer.py — mirror-powered related-topics inference.

Builds a bidirectional co-mention graph over QUESTION text: topic A is
related to topic B when A's questions name B (or B's works), and vice
versa. Only the linker's auto tier (canonical names) is used — no
single-word gambling. Scores are occurrence counts, forward + reverse.

Per topic, the top neighbors that are NOT already cross-ref'd land in
output/{slug}/related.json (machine-owned file, cards.json precedent):
    [{slug, topic, score, fwd, rev}]
rendered as the "Related topics" strip on stock.html and shipped in the
R2 topics.json overlay.

Local-only: resolves question ids against the mirror. Run after relink
(it excludes cross-ref'd targets) — post_batch does both.

Usage: python lib/crossref/infer.py [--top N] [--min-score N]
"""
import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from lib.common import OUTPUT_DIR, resolve_analyses, write_json_if_changed
from lib.crossref.linker import Linker
from lib.mirror import db as mirror_db
from lib.mirror import query as mirror_query
from lib.mirror.publish import _docs_by_id

DEFAULT_TOP = 8
DEFAULT_MIN_SCORE = 2


def _question_text(doc: dict) -> str:
    if doc.get('type') == 'bonus':
        parts = ' '.join(doc.get('parts_sanitized') or [])
        return f"{doc.get('leadin_sanitized', '')} {parts}"
    return doc.get('question_sanitized', '')


def _topic_question_ids(slug: str) -> list[str]:
    """The topic's answer-query question ids (mentions queries excluded —
    those questions are about OTHER answers and would double-count)."""
    ref_path = OUTPUT_DIR / slug / 'questions_ref.json'
    if not ref_path.exists():
        return []
    ids = []
    for entry in json.loads(ref_path.read_text(encoding='utf-8')):
        if entry.get('mentions'):
            continue
        ids.extend(entry.get('tossups', []))
        ids.extend(entry.get('bonuses', []))
    return ids


def build_mention_graph(analyses, linker: Linker) -> dict[str, Counter]:
    """fwd[a][b] = how often topic b (or its works) is named in topic a's
    question text."""
    conn = mirror_db.open_db()
    try:
        catalog = mirror_query._Catalog(conn)
        ids_by_slug = {slug: _topic_question_ids(slug)
                       for slug, _p, _d in analyses}
        docs = _docs_by_id(conn, catalog,
                           {i for ids in ids_by_slug.values() for i in ids})
    finally:
        conn.close()

    fwd: dict[str, Counter] = {}
    for slug, _path, d in analyses:
        text = '\n'.join(_question_text(docs[i])
                         for i in ids_by_slug.get(slug, []) if i in docs)
        if not text:
            continue
        refs, _ = linker.scan(text, topic_slug=slug,
                              topic_name=d.get('topic', ''),
                              category=d.get('category', ''))
        counts = Counter()
        for ref in refs:
            # Auto tier only; overrides are prose-context decisions and
            # don't necessarily transfer to question text.
            if ref['source'] != 'backfill' or not ref['exists']:
                continue
            n = len(re.findall(r'\b' + re.escape(ref['name']) + r'\b', text))
            counts[ref['slug']] += max(n, 1)
        if counts:
            fwd[slug] = counts
    return fwd


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('--top', type=int, default=DEFAULT_TOP)
    ap.add_argument('--min-score', type=int, default=DEFAULT_MIN_SCORE)
    args = ap.parse_args()

    analyses = resolve_analyses()
    by_slug = {slug: d for slug, _p, d in analyses}
    linker = Linker(analyses=analyses)
    print('Scanning question text for co-mentions (this reads the mirror)...')
    fwd = build_mention_graph(analyses, linker)

    written = 0
    for slug, _path, d in analyses:
        already = {r.get('slug') for r in d.get('cross_refs') or []}
        scores: dict[str, tuple] = {}
        neighbors = set(fwd.get(slug, {})) | {a for a, c in fwd.items()
                                              if slug in c}
        for other in neighbors:
            if other == slug or other in already or other not in by_slug:
                continue
            f = fwd.get(slug, {}).get(other, 0)
            r = fwd.get(other, {}).get(slug, 0)
            score = f + r
            if score >= args.min_score:
                scores[other] = (score, f, r)

        ranked = sorted(scores.items(),
                        key=lambda kv: (-kv[1][0], kv[0]))[:args.top]
        related = [{'slug': o, 'topic': by_slug[o].get('topic', o),
                    'score': s, 'fwd': f, 'rev': r}
                   for o, (s, f, r) in ranked]
        path = OUTPUT_DIR / slug / 'related.json'
        if related:
            written += write_json_if_changed(path, related)
        elif path.exists():
            path.unlink()
            written += 1

    n_topics = sum(1 for slug, _p, _d in analyses
                   if (OUTPUT_DIR / slug / 'related.json').exists())
    print(f'Related topics: {written} files written/updated; '
          f'{n_topics} topics have a related.json')


if __name__ == '__main__':
    main()
