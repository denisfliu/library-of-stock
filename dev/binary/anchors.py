"""Step 3a: rare-term ("anchor") vectors for same-fact verification.

Cosine alone cannot separate "same fact" from "related fact" (the
Interrupted Intermezzo probe: true matches 0.77-0.82, the Elgar Enigma
intermezzo 0.797). What separates them is shared RARE vocabulary — the
same terms that make a clue identifying in the first place.

Each unit becomes a sparse row of idf weights over its non-stopword
tokens whose document frequency is <= MAX_DF (common words carry no
identity). Pair features (vectorised over millions of pairs):
    shared  — idf mass of the tokens both units contain
    frac    — shared / min(own mass of u, own mass of v)
              (1.0 = the sparser unit's rare vocabulary is fully shared)

Writes out/anchors.npz (CSR matrix) + out/vocab.pkl.

Usage: python dev/binary/anchors.py
"""
import time
from collections import Counter

import numpy as np
import scipy.sparse as sp

from common import OUT, STOP, load, save, tokens

MAX_DF = 0.005        # tokens in > 0.5% of units are not anchors


def build():
    t0 = time.time()
    U = load("units.pkl")
    toks = [set(t for t in tokens(x) if t not in STOP and len(t) > 1) for x in U["text"]]
    n = len(toks)
    df = Counter()
    for s in toks:
        df.update(s)
    vocab = {t: i for i, (t, c) in enumerate(df.items()) if c / n <= MAX_DF}
    # re-index densely
    vocab = {t: j for j, t in enumerate(vocab)}
    idf = np.zeros(len(vocab), np.float32)
    for t, j in vocab.items():
        idf[j] = np.log(n / df[t])
    indptr, ind = [0], []
    for s in toks:
        ind.extend(vocab[t] for t in s if t in vocab)
        indptr.append(len(ind))
    ind = np.array(ind, np.int32)
    X = sp.csr_matrix((idf[ind], ind, np.array(indptr, np.int64)), shape=(n, len(vocab)))
    sp.save_npz(OUT / "anchors.npz", X)
    save("vocab.pkl", dict(vocab=list(vocab), idf=idf))
    mass = np.asarray(X.sum(1)).ravel()
    print(f"{n} units, vocab {len(vocab)} anchor tokens (of {len(df)}), "
          f"median anchor mass {np.median(mass):.1f}, zero-anchor units {np.mean(mass == 0):.1%}, "
          f"{time.time() - t0:.0f}s")


class Anchors:
    def __init__(self):
        self.X = sp.load_npz(OUT / "anchors.npz").tocsr()
        self.mass = np.asarray(self.X.sum(1)).ravel()
        v = load("vocab.pkl")
        self.vocab, self.idf = v["vocab"], v["idf"]

    def pair(self, u, v, chunk=2_000_000):
        """Vectorised (shared, frac) for index arrays u, v."""
        u = np.asarray(u); v = np.asarray(v)
        shared = np.empty(len(u), np.float32)
        B = (self.X > 0).astype(np.float32).tocsr()
        for s in range(0, len(u), chunk):
            a = self.X[u[s:s + chunk]]
            b = B[v[s:s + chunk]]
            shared[s:s + chunk] = np.asarray(a.multiply(b).sum(1)).ravel()
        denom = np.minimum(self.mass[u], self.mass[v])
        frac = np.where(denom > 0, shared / np.maximum(denom, 1e-6), 0.0)
        return shared, frac.astype(np.float32)

    def shared_terms(self, u, v):
        a, b = self.X[u], self.X[v]
        common = set(a.indices) & set(b.indices)
        return [self.vocab[j] for j in sorted(common, key=lambda j: -self.idf[j])]


if __name__ == "__main__":
    build()
