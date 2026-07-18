"""Embedding-based thematic grouping of short texts (clue sentences).

The digest's word-overlap clustering catches near-duplicate phrasings of
the SAME fact; this module groups DIFFERENT facts by theme so a flat
single-answerline clue list (History figures: 40+ unrelated [1x] lines)
reads as sections-in-waiting instead.

Recipe from the July 2026 Andrew Jackson pilot: a single global cosine
cut fails (0.6 → one blob, 0.5 → shards), so cut loose first and
recursively re-split any oversized group at a tighter threshold.

Loads the Qwen3 embedder lazily on first use and keeps it for the
process lifetime (~20s model load, GPU when available).
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

INIT_THRESHOLD = 0.60
SPLIT_THRESHOLD = 0.52
MAX_THEME_SIZE = 8
MIN_TEXT_CHARS = 30   # splitter fragments ("The St.") — route to misc

_embedder = None


def _get_embedder():
    global _embedder
    if _embedder is None:
        from lib.embed.model import Embedder
        _embedder = Embedder()
    return _embedder


def theme_indices(texts: list[str]) -> tuple[list[list[int]], list[int]]:
    """Group texts by theme. Returns (themes, misc): themes is a list of
    index lists sorted largest-first; misc collects fragments and
    singletons that belong to no theme.

    Raises ImportError/OSError etc. when the embedding stack is absent —
    callers degrade to flat output.
    """
    import numpy as np
    from sklearn.cluster import AgglomerativeClustering

    usable = [i for i, t in enumerate(texts) if len(t) >= MIN_TEXT_CHARS]
    misc = [i for i in range(len(texts)) if i not in set(usable)]
    if len(usable) < 4:
        return ([usable] if usable else []), misc

    vecs = _get_embedder().encode_documents([texts[i] for i in usable])

    def agglo(v, **kw):
        return AgglomerativeClustering(
            metric="cosine", linkage="average", **kw).fit_predict(v)

    labels = agglo(vecs, n_clusters=None, distance_threshold=INIT_THRESHOLD)

    next_label = labels.max() + 1
    changed = True
    while changed:
        changed = False
        for c in sorted(set(labels)):
            idx = np.where(labels == c)[0]
            if len(idx) <= MAX_THEME_SIZE:
                continue
            sub = agglo(vecs[idx], n_clusters=None,
                        distance_threshold=SPLIT_THRESHOLD)
            if len(set(sub)) == 1:
                continue
            for s in set(sub):
                if s == 0:
                    continue
                labels[idx[sub == s]] = next_label
                next_label += 1
            changed = True

    themes = []
    for c in set(labels):
        group = [usable[i] for i in np.where(labels == c)[0]]
        if len(group) >= 2:
            themes.append(group)
        else:
            misc.extend(group)
    themes.sort(key=len, reverse=True)
    return themes, sorted(misc)
