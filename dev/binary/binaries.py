"""Step 4: the binary test, corpus-wide.

For every unit u (answer label a) and each sweep neighbour v (label b,
different question):
    same-fact   := cos >= SUPPORT_COS and frac >= SUPPORT_FRAC  (high precision)
    may-conflict:= cos >= CONFLICT_COS and frac >= CONFLICT_FRAC (high recall)
A may-conflict neighbour with b != a is FORGIVEN when
    - linked: b's questions name a in >= LINK_SHARE of cases or vice
      versa (links.py) — parent and child answerlines, e.g. Bartók and
      his Concerto for Orchestra, are one fact seen from two ends, or
    - compatible: one answer is listed as or/accept/prompt on the other
      (Yggdrasil vs "trees [accept any specific tree]"), or
    - kind mismatch: both labels have a known kind (answerlines.py) and
      they differ — "this Hungarian composer" is never answered
      "Hungary", so a shared fact is seen from another entity, or
    - role swap: u's text names b (or one of b's children), or v's text
      names a (or a child of a), or one answerline's own name contains
      the other's ("bartok s piano concertos") — the same fact
      asked from its other end (Odin hanged on Yggdrasil -> "Odin" /
      "Yggdrasil" / "nine").
Unit status:
    binary   — no unforgiven conflict, >= MIN_SUPPORT independent
               questions state it (near-duplicate reprints collapse)
    single   — no conflict but only this question states it
    shared   — >= 1 unforgiven conflict at SUPPORT strength (the
               high-precision same-fact rule; competing answers recorded)
    unclear  — only loose-rule conflicts (cos >= CONFLICT_COS, frac >=
               CONFLICT_FRAC): maybe the same fact, maybe just related
    unknown  — every one of the K neighbour slots is a possible conflict
               above CONFLICT_COS: more may lie beyond K (generic text)

Writes out/unit_status.npz (status, support, n_conflict per unit) and
out/conflicts.pkl ({unit: [(v, label_b, cos, strong)]} for shared/unclear units).

Usage: python dev/binary/binaries.py
"""
import re
import time

import numpy as np
import scipy.sparse as sp

from anchors import Anchors
from common import OUT, alias_ok, fold, load, save

SUPPORT_COS, SUPPORT_FRAC = 0.78, 0.35
SUPPORT_SHARED = 12.0   # ...and >= this much shared idf mass: one moderately
                        # rare word ("concerto") in two short giveaways is not
                        # the same fact
CHILD_SHARE = 0.50      # c is a's child when >= half of c's questions name a
CONFLICT_COS, CONFLICT_FRAC = 0.74, 0.15

# A unit universe may carry its own calibrated thresholds (calib.py run on
# that universe): out/<sub>/thresholds.json overrides the four values above.
# Clauses need stricter ones: short texts look alike far more often than
# they state the same fact.
if (OUT / "thresholds.json").exists():
    import json as _json
    globals().update({k: v for k, v in _json.loads((OUT / "thresholds.json").read_text()).items()
                      if k in ("SUPPORT_COS", "SUPPORT_FRAC", "CONFLICT_COS", "CONFLICT_FRAC")})
DUP_COS = 0.97          # near-identical reprint: not independent support
MIN_SUPPORT = 2         # questions (incl. u's own)
LINK_SHARE = 0.30       # linked labels: one names the other this often
SPECIFIC_SHARE = 0.005  # ...and the named one is in <= 0.5% of all questions

ST_BINARY, ST_SINGLE, ST_SHARED, ST_UNKNOWN, ST_UNCLEAR, ST_CONTEXT = 0, 1, 2, 3, 4, 5
STATUS_NAMES = ["binary", "single", "shared", "unknown", "unclear", "context"]

# Does a unit refer to its question's answer (the blank)? A clause that
# doesn't ("Indian classical music uses rhythmic patterns called talas",
# split out of a question answered "clapping") is context: it is no clue
# for that answer, so it can neither support nor contest anything.
REFERS = re.compile(r"\b(this|these|he|she|his|her|him|hers|himself|herself|they|their|them|"
                    r"it|its|itself|what|which|whose|one of)\b", re.I)


class Mentions:
    """Does a (folded) text name a label? Phrase match on the label's
    merged keys + or/accept alternatives, and the surname of person-like
    multi-token keys."""

    def __init__(self, L):
        self.L = L
        self.cache = {}

    def phrases(self, lab):
        p = self.cache.get(lab)
        if p is None:
            own = self.L["variants"][lab]
            p = {k for k in own if len(k) >= 3}
            p |= {k for k in self.L["alts"][lab] | self.L["prompts"][lab]
                  if len(k) >= 3 and alias_ok(k)}
            for k in self.L["variants"][lab]:
                t = k.split()
                if len(t) >= 2 and len(t[-1]) >= 4:
                    p.add(t[-1])
            p = self.cache[lab] = [f" {x} " for x in p]
        return p

    def names(self, ftext, lab):
        return any(x in ftext for x in self.phrases(lab))


def compatible(L, a, b):
    ka, kb = L["variants"][a], L["variants"][b]
    oa = L["alts"][a] | L["prompts"][a]
    ob = L["alts"][b] | L["prompts"][b]
    return bool(ka & ob or kb & oa)


def main():
    t0 = time.time()
    U = load("units.pkl")
    L = load("labels.pkl")
    lab = L["unit_label"]
    qid = np.array(U["qid"])
    idx = np.load(OUT / "nbr_idx.npy")
    cos = np.load(OUT / "nbr_cos.npy").astype(np.float32)
    n, K = idx.shape

    # Flatten valid pairs, drop same-question pairs.
    uu = np.repeat(np.arange(n, dtype=np.int64), K)
    vv = idx.ravel().astype(np.int64)
    cc = cos.ravel()
    ok = vv >= 0
    uu, vv, cc = uu[ok], vv[ok], cc[ok]
    # qid compare via integer codes
    _, qcode = np.unique(qid, return_inverse=True)
    ok = qcode[uu] != qcode[vv]
    uu, vv, cc = uu[ok], vv[ok], cc[ok]
    print(f"{len(uu):,} cross-question candidate pairs ({time.time() - t0:.0f}s)")

    A = Anchors()
    cand = cc >= CONFLICT_COS
    uu, vv, cc = uu[cand], vv[cand], cc[cand]
    shared, frac = A.pair(uu, vv)
    print(f"{len(uu):,} pairs >= {CONFLICT_COS} scored ({time.time() - t0:.0f}s)")

    # Context units (no reference to the blank) take no part: drop every
    # pair touching one. Whole sentences almost always refer.
    refers = np.array([bool(REFERS.search(t)) for t in U["text"]])
    keep = refers[uu] & refers[vv]
    uu, vv, cc, shared, frac = uu[keep], vv[keep], cc[keep], shared[keep], frac[keep]
    print(f"context units (no reference to the answer): {np.mean(~refers):.1%}; "
          f"{len(uu):,} pairs left", flush=True)
    same_lab = lab[uu] == lab[vv]
    strong = ((cc >= SUPPORT_COS) & (frac >= SUPPORT_FRAC) & (shared >= SUPPORT_SHARED)
              & (cc < DUP_COS))
    support_edge = same_lab & strong
    conflict_cand = (~same_lab) & (frac >= CONFLICT_FRAC)

    # Forgiveness checks on conflict candidates only.
    M = Mentions(L)
    # What each sentence names: links.py's capitalisation-gated scan, so
    # this test and topic discovery share one definition of "names".
    MU = sp.load_npz(OUT / "mention_u.npz").tocsr()
    _named = {}

    def ft(i):
        s = _named.get(i)
        if s is None:
            s = _named[i] = set(MU.indices[MU.indptr[i]:MU.indptr[i + 1]].tolist())
        return s

    cu, cv, ccos = uu[conflict_cand], vv[conflict_cand], cc[conflict_cand]
    cstrong = strong[conflict_cand]
    print(f"{len(cu):,} conflict candidates to check ({time.time() - t0:.0f}s)")
    # Forgiven pairs at support strength are the same fact asked from
    # another answerline: they count as independent support too.
    fu, fq = [uu[support_edge]], [qcode[vv[support_edge]]]

    # Linked labels (links.py): b's questions name a (or vice versa) in
    # >= LINK_SHARE of cases, and the named label is specific enough for
    # that to mean something. Concerto for Orchestra <-> Bartók.
    link = sp.load_npz(OUT / "links.npz").tocoo()
    named = np.asarray(sp.load_npz(OUT / "mention_q.npz").sum(0)).ravel()
    nq_total = sp.load_npz(OUT / "mention_q.npz").shape[0]
    specific = named <= SPECIFIC_SHARE * nq_total
    keep = (link.data >= LINK_SHARE) & specific[link.row]
    NL = len(L["keys"])
    lk = np.unique(np.concatenate([link.row[keep].astype(np.int64) * NL + link.col[keep],
                                   link.col[keep].astype(np.int64) * NL + link.row[keep]]))
    la, lb = lab[cu].astype(np.int64), lab[cv].astype(np.int64)
    linked = np.isin(la * NL + lb, lk)
    n_link = int(linked.sum())
    fu.append(cu[linked & cstrong]); fq.append(qcode[cv[linked & cstrong]])
    cu, cv, ccos, cstrong = cu[~linked], cv[~linked], ccos[~linked], cstrong[~linked]

    compat_cache = {}
    conflicts = {}
    n_compat = n_kind = n_swap = n_child = 0
    child_sample = []
    kind = L["kind"]
    # Generalised role swap: naming a's CHILD (a label whose questions
    # name a >= CHILD_SHARE of the time) also places the text in a's
    # world — "paired with Duke Bluebeard's Castle" in a Schoenberg
    # question is context, not a competing Bartók clue.
    child_link = sp.load_npz(OUT / "links.npz").tocsr()
    children = {}

    def names_world(named, a):
        if a in named:
            return True
        ch = children.get(a)
        if ch is None:
            row = child_link[a]
            ch = children[a] = [c for c, s in zip(row.indices.tolist(), row.data.tolist())
                                if s >= CHILD_SHARE and c != a and specific[c]
                                and " " in L["keys"][c]]   # multi-word names only:
                                                            # "requiem" is not Mozart's
        return any(c in named for c in ch)

    def key_names(b, a):
        """b's own answerline names a: "bartok s piano concertos"."""
        kb = f" {L['keys'][b]} "
        return any(p in kb for p in M.phrases(a))
    extra_u, extra_q = [], []
    for u, v, c, st in zip(cu.tolist(), cv.tolist(), ccos.tolist(), cstrong.tolist()):
        a, b = int(lab[u]), int(lab[v])
        key = (a, b) if a < b else (b, a)
        comp = compat_cache.get(key)
        if comp is None:
            comp = compat_cache[key] = compatible(L, a, b)
        if comp:
            n_compat += 1
        elif kind[a] is not None and kind[b] is not None and kind[a] != kind[b]:
            n_kind += 1
        elif a in ft(v) or b in ft(u) or key_names(b, a) or key_names(a, b):
            n_swap += 1
        elif names_world(ft(v), a) or names_world(ft(u), b):
            n_child += 1
            if len(child_sample) < 400 and st:
                child_sample.append((u, v))
        else:
            conflicts.setdefault(u, []).append((v, b, round(c, 3), bool(st)))
            continue
        if st:
            extra_u.append(u); extra_q.append(qcode[v])
    fu.append(np.array(extra_u, np.int64)); fq.append(np.array(extra_q, np.int64))

    # Independent support: distinct other questions per unit.
    sup = np.ones(n, np.int32)
    pair_q = np.unique(np.stack([np.concatenate(fu), np.concatenate(fq)], 1), axis=0)
    np.add.at(sup, pair_q[:, 0], 1)
    print(f"forgiven: {n_link:,} linked, {n_compat:,} compatible, {n_kind:,} kind-mismatch, "
          f"{n_swap:,} role-swap, {n_child:,} child-role-swap; "
          f"{sum(len(x) for x in conflicts.values()):,} conflicts on {len(conflicts):,} units "
          f"({time.time() - t0:.0f}s)")

    status = np.where(sup >= MIN_SUPPORT, ST_BINARY, ST_SINGLE).astype(np.int8)
    ncon = np.zeros(n, np.int32)
    for u, lst in conflicts.items():
        ncon[u] = len(lst)
        status[u] = ST_SHARED if any(x[3] for x in lst) else ST_UNCLEAR
    full = (idx[:, -1] >= 0) & (cos[:, -1] >= CONFLICT_COS)
    status[full & (status != ST_SHARED) & (status != ST_UNCLEAR)] = ST_UNKNOWN
    status[~refers] = ST_CONTEXT
    np.savez(OUT / "unit_status.npz", status=status, support=sup, n_conflict=ncon)
    save("conflicts.pkl", conflicts)
    save("child_forgiven_sample.pkl", child_sample)   # audit of the widest forgiveness rule
    for s, name in enumerate(STATUS_NAMES):
        print(f"  {name:8} {np.mean(status == s):6.1%}")
    print(f"done in {time.time() - t0:.0f}s")


if __name__ == "__main__":
    main()
