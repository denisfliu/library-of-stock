"""Tier B, step 2: the clause universe for one scope.

Rows 0..Q-1 are the scope's CLAUSES (clauses.split_clauses of every scope
unit), embedded fresh. Rows Q.. are every OTHER corpus unit, kept as
whole sentences with their stored vectors, so conflicts from outside the
scope stay visible. Each clause inherits its sentence's answer, question,
position and sentence-level mentions (mention_u). Labels, links and
mention_q are the sentence-level ones (copied in), so the rest of the
pipeline runs unchanged with BINARY_OUT_SUB=clauses_{scope}.

Writes out/clauses_{scope}/: units.pkl (+ "query" and "parent" columns),
vecs.npy, labels.pkl, mention_u.npz, and copies of links.npz,
mention_q.npz, label_cap.npz.

Usage: python dev/binary/build_clauses.py [--scope music]
Then:  BINARY_OUT_SUB=clauses_music python anchors.py / sweep.py --queries / binaries.py / topic.py
"""
import argparse
import pickle
import shutil
import time

import numpy as np
import scipy.sparse as sp

from clauses import split_clauses
from common import BASE_OUT, load

SCOPES = {"music": lambda U, i: U["subcategory"][i] == "Auditory Fine Arts",
          "literature": lambda U, i: U["category"][i] == "Literature",
          "extra": lambda U, i: U["category"][i] in ("Mythology", "Religion", "Philosophy", "Social Science")
          or U["subcategory"][i] == "Biology",
          "history": lambda U, i: U["category"][i] == "History",
          "csmath": lambda U, i: U["subcategory"][i] == "Other Science" and U["alt"][i] in ("Math", "Computer Science")}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scope", default="music", choices=sorted(SCOPES))
    ap.add_argument("--relabel", action="store_true",
                    help="only refresh labels / mentions / links after answerlines.py or "
                         "links.py changed (no re-split, no re-embedding)")
    a = ap.parse_args()
    t0 = time.time()
    dst = BASE_OUT / f"clauses_{a.scope}"
    dst.mkdir(exist_ok=True)
    U = load("units.pkl")
    L = load("labels.pkl")
    if a.relabel:
        with open(dst / "units.pkl", "rb") as f:
            parent = pickle.load(f)["parent"]
        relabel(dst, L, parent)
        print(f"relabelled {dst} ({time.time() - t0:.0f}s)")
        return
    n = len(U["text"])
    in_scope = SCOPES[a.scope]
    scope = [i for i in range(n) if in_scope(U, i)]
    rest = [i for i in range(n) if not in_scope(U, i)]
    texts, parent = [], []
    for i in scope:
        for c in split_clauses(U["text"][i]):
            texts.append(c)
            parent.append(i)
    parent = np.array(parent + rest, dtype=np.int64)
    Q = len(texts)
    print(f"{len(scope):,} scope sentences -> {Q:,} clauses; {len(rest):,} other units kept "
          f"({time.time() - t0:.0f}s)", flush=True)

    from lib.embed.model import get_shared_embedder
    E = get_shared_embedder()
    cv = E.encode_documents(texts, batch_size=64).astype(np.float16)
    V = np.load(BASE_OUT / "vecs.npy", mmap_mode="r")
    vecs = np.empty((len(parent), V.shape[1]), np.float16)
    vecs[:Q] = cv
    vecs[Q:] = V[np.array(rest)]
    np.save(dst / "vecs.npy", vecs)
    print(f"embedded {Q:,} clauses ({time.time() - t0:.0f}s)", flush=True)

    cols = {}
    for k, v in U.items():
        if isinstance(v, np.ndarray):
            cols[k] = v[parent]
        else:
            cols[k] = [v[j] for j in parent]
    cols["text"] = texts + [U["text"][j] for j in rest]
    cols["query"] = np.arange(len(parent)) < Q
    cols["parent"] = parent
    with open(dst / "units.pkl", "wb") as f:
        pickle.dump(cols, f, protocol=pickle.HIGHEST_PROTOCOL)
    relabel(dst, L, parent)
    print(f"wrote {dst} ({time.time() - t0:.0f}s)")


def relabel(dst, L, parent):
    """Everything label-derived, recomputed from the sentence-level files."""
    L2 = dict(L)
    L2["unit_label"] = L["unit_label"][parent]
    with open(dst / "labels.pkl", "wb") as f:
        pickle.dump(L2, f, protocol=pickle.HIGHEST_PROTOCOL)
    MU = sp.load_npz(BASE_OUT / "mention_u.npz").tocsr()
    sp.save_npz(dst / "mention_u.npz", MU[parent])
    for name in ("links.npz", "mention_q.npz", "label_cap.npz"):
        shutil.copy2(BASE_OUT / name, dst / name)


if __name__ == "__main__":
    main()
