"""Embed corpus text into embeddings.sqlite. Resumable — re-running skips
rows already embedded for the current model.

Usage:
    python lib/embed/embed_corpus.py tossups [--limit N] [--category "Fine Arts"]
    python lib/embed/embed_corpus.py bonuses [--limit N] [--category ...]
    python lib/embed/embed_corpus.py topics            # all output/*/analysis.json

'topics' embeds summary + comprehensive_summary per topic (kind='topic',
id=slug). Tossups embed question_sanitized. Bonuses embed each part bare
(kind='bonus_part', part=index) and the leadin as part=-1.
"""
import argparse
import sqlite3
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from lib.common import MIRROR_DIR, iter_analyses
from lib.embed.model import MODEL_ID, Embedder
from lib.embed.store import EmbeddingStore

QBREADER_DB = MIRROR_DIR / "qbreader.sqlite"
BATCH = 512  # rows fetched per DB chunk; encode batches are handled by the model


def _mirror():
    return sqlite3.connect(QBREADER_DB)


def iter_tossups(category=None, limit=None):
    q = "select id, question_sanitized from tossups"
    params = []
    if category:
        q += " where category=?"
        params.append(category)
    if limit:
        q += f" limit {int(limit)}"
    for id_, text in _mirror().execute(q, params):
        if text and text.strip():
            yield id_, -1, text.strip()


def iter_bonus_parts(category=None, limit=None):
    import json

    q = "select id, leadin_sanitized, parts_sanitized from bonuses"
    params = []
    if category:
        q += " where category=?"
        params.append(category)
    if limit:
        q += f" limit {int(limit)}"
    for id_, leadin, parts in _mirror().execute(q, params):
        if leadin and leadin.strip():
            yield id_, -1, leadin.strip()
        try:
            parts = json.loads(parts) if parts else []
        except ValueError:
            continue
        for i, part in enumerate(parts):
            if part and part.strip():
                yield id_, i, part.strip()


MIN_SENTENCE_CHARS = 15  # skip stray fragments; part index still counts them


def iter_sentences(category=None, limit=None):
    """Tossup sentences, reader-aligned split. part = the sentence's index
    in split_sentences(question_sanitized) — the same index the reader
    derives on screen, so clue-taps key straight into the store."""
    from lib.pipeline.parse import split_sentences

    for id_, _part, text in iter_tossups(category=category, limit=limit):
        for i, sent in enumerate(split_sentences(text)):
            if len(sent) >= MIN_SENTENCE_CHARS:
                yield id_, i, sent


def iter_topics():
    for slug, _path, data in iter_analyses():
        text = " ".join(
            t for t in (data.get("summary", ""), data.get("comprehensive_summary", "")) if t
        ).strip()
        if text:
            yield slug, -1, text


KINDS = {
    "tossups": ("tossup", iter_tossups),
    "bonuses": ("bonus_part", iter_bonus_parts),
    "sentences": ("sentence", iter_sentences),
    "topics": ("topic", lambda category=None, limit=None: iter_topics()),
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("what", choices=KINDS)
    ap.add_argument("--limit", type=int)
    ap.add_argument("--category")
    ap.add_argument("--batch-size", type=int, default=32)
    args = ap.parse_args()

    kind, source = KINDS[args.what]
    store = EmbeddingStore()
    done = store.existing_ids(kind, MODEL_ID)
    embedder = Embedder()
    print(f"model={MODEL_ID} device={embedder.device} kind={kind} already={len(done)}")

    pending, total, t0 = [], 0, time.time()

    def flush():
        nonlocal pending, total
        if not pending:
            return
        vecs = embedder.encode_documents([t for _, _, t in pending], args.batch_size)
        store.put_many(kind, MODEL_ID, ((i, p, v) for (i, p, _), v in zip(pending, vecs)))
        total += len(pending)
        rate = total / max(time.time() - t0, 1e-9)
        print(f"  {total} embedded ({rate:.0f}/s)", flush=True)
        pending = []

    for id_, part, text in source(category=args.category, limit=args.limit):
        if (id_, part) in done:
            continue
        pending.append((id_, part, text))
        if len(pending) >= BATCH:
            flush()
    flush()
    print(f"done: +{total}, store now has {store.count(kind, MODEL_ID)} {kind} rows")


if __name__ == "__main__":
    main()
