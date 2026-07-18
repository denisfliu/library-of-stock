"""infer.py — mirror-powered related-topics inference.

Builds a bidirectional co-mention graph over QUESTION text: topic A is
related to topic B when A's questions name B (or B's works), and vice
versa. Only the linker's auto tier (canonical names) is used — no
single-word gambling. Scores are occurrence counts, forward + reverse.

Per topic, the top neighbors that are NOT already cross-ref'd land in
output/{slug}/related.json (machine-owned file, cards.json precedent):
    [{slug, topic, score, fwd, rev, source: 'comention'}]
rendered as the "Related topics" strip on stock.html and shipped in the
R2 topics.json overlay.

When mirror/embeddings.sqlite has topic vectors (lib/embed/), the strip
is topped up to --top with embedding nearest-neighbors above
MIN_EMBED_SIM, appended after the co-mention entries as
    {slug, topic, score: <cosine sim>, source: 'embedding'}.
Co-mentions rank first: an explicit mention in question text is stronger
evidence than corpus-summary similarity. Missing sidecar or deps degrade
to co-mention-only.

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
# Below ~0.5 cosine, Qwen3-0.6B topic-summary neighbors drift from "same
# scene" to "same country/era" (July 2026 pilot: alhambra → generic
# modern architects at 0.46-0.48).
MIN_EMBED_SIM = 0.50


def _load_topic_vectors():
    """(slugs, matrix) from the embeddings sidecar, or None if the
    sidecar/deps are absent — infer then runs co-mention-only."""
    try:
        from lib.embed.model import MODEL_ID
        from lib.embed.store import EmbeddingStore
        keys, mat = EmbeddingStore().load_matrix('topic', MODEL_ID)
        if not keys:
            return None
        return [k for k, _ in keys], mat
    except Exception as e:  # noqa: BLE001 — any failure means "no vectors"
        print(f'  (embedding neighbors unavailable: {e})')
        return None


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

    vectors = _load_topic_vectors()
    if vectors is not None:
        vec_slugs, vec_mat = vectors
        vec_index = {s: i for i, s in enumerate(vec_slugs)}
        print(f'  topping up with embedding neighbors '
              f'({len(vec_slugs)} topic vectors, sim >= {MIN_EMBED_SIM})')

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
                    'score': s, 'fwd': f, 'rev': r, 'source': 'comention'}
                   for o, (s, f, r) in ranked]

        if vectors is not None and slug in vec_index:
            import numpy as np
            sims = vec_mat @ vec_mat[vec_index[slug]]
            taken = {r['slug'] for r in related} | already | {slug}
            for j in np.argsort(-sims):
                if len(related) >= args.top or sims[j] < MIN_EMBED_SIM:
                    break
                other = vec_slugs[j]
                if other in taken or other not in by_slug:
                    continue
                related.append({'slug': other,
                                'topic': by_slug[other].get('topic', other),
                                'score': round(float(sims[j]), 3),
                                'source': 'embedding'})
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
