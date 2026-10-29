"""Step 1b: which answerlines each question names -> label-to-label links.

Every question's folded text (all its units) is scanned for every label's
name phrases (merged keys, or/accept/prompt alternatives, surnames of
person labels). A match counts only where the matched words are
capitalised, as proper names are, so "squares", "angles" and lowercase
"glass" name nothing. Single-token alternatives must also be rare (unit
df <= RARE_DF), so junk alternatives like "fifth" or "blue" name nothing.

    link[a, b] = share of label b's questions that name label a

A high link means b lives inside a's world: Concerto for Orchestra
questions name Bartók 95% of the time. The binary test treats linked
labels as one fact seen from two ends (never a conflict), and topic.py
uses the same matrix to discover a topic's answerlines.

Writes out/links.npz (CSR, L x L, float32 shares; only entries with
>= 2 naming questions kept), out/mention_q.npz (Q x L 0/1) and
out/mention_u.npz (units x L 0/1: what each sentence itself names) and
out/label_cap.npz (per label: capitalised / all matches of its names).

Usage: python dev/binary/links.py
"""
import sqlite3
import time
from collections import defaultdict

import numpy as np
import scipy.sparse as sp

from common import MIRROR, OUT, STOP, alias_ok, fold, fold_case, load

RARE_DF = 0.001
MIN_NAMING_Q = 2
MAX_NAMED_SHARE = 0.02


def shares_word(alt, own):
    """A multi-word ALTERNATIVE names its answerline only if it shares a
    real word with one of the answerline's own names: "bluebeard s castle"
    in a "blue" answerline's accept clause, or a moderator's "goldberg
    variations" in Beethoven's, names neither."""
    words = {w for k in own for w in k.split() if len(w) >= 3 and w not in STOP}
    return any(w in words for w in alt.split())


def name_phrases(L, df, n_units):
    """label -> set of token tuples."""
    out = []
    claims = defaultdict(set)                 # one-word name -> labels claiming it
    strong = defaultdict(set)                 # ...as their OWN name or a person's surname
    for lab in range(len(L["keys"])):
        ph = set()
        own = L["variants"][lab]
        for k in own | L["alts"][lab] | L["prompts"][lab]:
            t = tuple(k.split())
            if not t or len(t) > 8:
                continue
            if len(t) == 1:
                w = t[0]
                if len(w) < 3 or w in STOP:
                    continue
                # The label's own one-word name always counts ("odin");
                # one-word ALTERNATIVES only when rare ("fifth" doesn't).
                if k not in own and (len(w) < 5 or df.get(w, 0) / n_units > RARE_DF):
                    continue
                claims[w].add(lab)
                if k in own:
                    strong[w].add(lab)
                continue
            if k not in own and not (alias_ok(k) and shares_word(k, own)):
                continue
            ph.add(t)
        if L["kind"][lab] == "person":          # surnames name people only
            for k in L["variants"][lab]:
                t = k.split()
                # No rarity test here: "beethoven" and "bach" are common
                # words in this corpus precisely because they are famous.
                # Capitalisation, person-only and the 3x dominance rule
                # below keep surnames honest.
                if len(t) >= 2 and len(t[-1]) >= 4:
                    claims[t[-1]].add(lab)
                    strong[t[-1]].add(lab)
        out.append(ph)
    # A one-word name belongs to the label that claims it with >= 3x the
    # questions of any rival, else to nobody: "carter" and "giselle" in
    # Beyoncé's accept clause must not make Elliott Carter or the ballet
    # Giselle "name" her; "bach" goes to J. S. Bach.
    # Own names and surnames outrank accept-clause claims: a moderator
    # note in the Soviet Union's answerline ("...concertos are Prokofiev,
    # Gubaidulina...") must not take "gubaidulina" from Gubaidulina.
    nq = L["nq"]
    for w, labs in claims.items():
        labs = strong.get(w) or labs
        ranked = sorted(labs, key=lambda b: -nq[b])
        if len(ranked) == 1 or nq[ranked[0]] >= 3 * nq[ranked[1]]:
            out[ranked[0]].add((w,))
    return out


def main():
    t0 = time.time()
    U = load("units.pkl")
    L = load("labels.pkl")
    n = len(U["text"])
    toks = [fold(t).split() for t in U["text"]]
    ctoks = [fold_case(t).split() for t in U["text"]]
    df = defaultdict(int)
    for ts in toks:
        for w in set(ts):
            df[w] += 1
    phrases = name_phrases(L, df, n)
    # One-token phrases by token; longer ones by their first two tokens
    # (a first-token index alone puts thousands of "john ..." phrases on
    # every "john").
    single = defaultdict(list)
    pair = defaultdict(list)
    for lab, ph in enumerate(phrases):
        for t in ph:
            (single[t[0]] if len(t) == 1 else pair[t[:2]]).append((t, lab))
    print(f"phrase index: {sum(len(p) for p in phrases):,} phrases ({time.time() - t0:.0f}s)",
          flush=True)

    qids, qcode = np.unique(np.array(U["qid"]), return_inverse=True)
    lab = L["unit_label"]
    rows, cols, urows = [], [], []
    cap_n = np.zeros(len(L["keys"]), np.int64)     # matches written capitalised
    all_n = np.zeros(len(L["keys"]), np.int64)     # all matches

    def scan(ts, tc, count=True):
        """Labels a token list names. A sentence NAMES an answerline only
        where the words are capitalised, as proper names are: "squares",
        "angles", "concerto" and lowercase "glass" name nothing."""
        if tc is not None and len(tc) != len(ts):
            tc = None

        def capitalised(p, k):
            return tc is None or any(w[:1].isupper() for w in tc[p:p + k])

        spans = []                              # (start, end, label)
        for p in range(len(ts)):
            for t, b in single.get(ts[p], ()):
                if count:
                    all_n[b] += 1
                if capitalised(p, 1):
                    spans.append((p, p + 1, b))
                    if count:
                        cap_n[b] += 1
            cands = pair.get((ts[p], ts[p + 1])) if p + 1 < len(ts) else None
            if not cands:
                continue
            for t, b in cands:
                if len(t) == 2 or tuple(ts[p:p + len(t)]) == t:
                    if count:
                        all_n[b] += 1
                    if capitalised(p, len(t)):
                        spans.append((p, p + len(t), b))
                        if count:
                            cap_n[b] += 1
        # Longest match wins: "Variations" inside "Goldberg Variations" or
        # "Sun" inside "Canticle of the Sun" names nothing by itself.
        spans.sort(key=lambda x: x[0] - x[1])           # longest first
        kept, found = [], set()
        for s0, e0, b in spans:
            if any(s1 <= s0 and e0 <= e1 and (e1 - s1) > (e0 - s0) for s1, e1 in kept):
                continue
            kept.append((s0, e0))
            found.add(b)
        return found

    for i, ts in enumerate(toks):
        own = lab[i]
        for b in scan(ts, ctoks[i]):
            if b != own:
                rows.append(qcode[i]); cols.append(b); urows.append(i)
    # Bonus lead-ins are not units, but "...answer these questions about
    # Sofia Gubaidulina" is context for every part: each part inherits the
    # names its lead-in uses.
    parts_of = defaultdict(list)
    for i in range(n):
        if U["kind"][i] == 1:
            parts_of[U["qid"][i]].append(i)
    qdb = sqlite3.connect(MIRROR / "qbreader.sqlite")
    n_lead = 0
    for bid, leadin in qdb.execute("select id, leadin_sanitized from bonuses"):
        units_b = parts_of.get(bid)
        if not units_b or not leadin:
            continue
        found = scan(fold(leadin).split(), fold_case(leadin).split(), count=False)
        for i in units_b:
            for b in found:
                if b != lab[i]:
                    rows.append(qcode[i]); cols.append(b); urows.append(i); n_lead += 1
    print(f"lead-in mentions added: {n_lead:,} ({time.time() - t0:.0f}s)", flush=True)
    Q, NL = len(qids), len(L["keys"])
    M = sp.csr_matrix((np.ones(len(rows), np.float32), (rows, cols)), shape=(Q, NL))
    M.sum_duplicates(); M.data[:] = 1.0     # dedupe multiple units of a question
    # A label "named" by > MAX_NAMED_SHARE of all questions is generic
    # ("man", "two") or carries a junk phrase ("of the" from a mangled
    # accept clause): its mentions carry no link information.
    named = np.asarray(M.sum(0)).ravel()
    generic = np.flatnonzero(named > MAX_NAMED_SHARE * Q)
    M = M.tocsc()
    for b in generic:
        M.data[M.indptr[b]:M.indptr[b + 1]] = 0
    M.eliminate_zeros()
    M = M.tocsr()
    print(f"dropped {len(generic)} generic labels from mentions", flush=True)
    sp.save_npz(OUT / "mention_q.npz", M)
    # Sentence-level: which labels each unit's own text (plus, for a bonus
    # part, its lead-in) names. keys.py needs it per sentence: a bonus part
    # naming Gubaidulina says nothing about the bonus's other parts.
    keep = ~np.isin(np.array(cols), generic)
    MU = sp.csr_matrix((np.ones(int(keep.sum()), np.float32),
                        (np.array(urows)[keep], np.array(cols)[keep])), shape=(n, NL))
    MU.sum_duplicates(); MU.data[:] = 1.0
    sp.save_npz(OUT / "mention_u.npz", MU)
    # How "proper" each answerline's name is: the share of its matches
    # written capitalised. "Concerto for Orchestra", "Mikrokosmos" ~1;
    # "suites", "fugue" ~0. keys.py lets only proper names climb to a parent.
    np.savez(OUT / "label_cap.npz", cap=cap_n, all=all_n)
    print(f"mentions: {M.nnz:,} (question, label) pairs ({time.time() - t0:.0f}s)")

    # A[b, q] = 1 if question q is answered by label b.
    qa = sp.csr_matrix((np.ones(n, np.float32), (lab, qcode)), shape=(NL, Q))
    qa.data[:] = 1.0
    qa.sum_duplicates(); qa.data[:] = 1.0
    nq = np.asarray(qa.sum(1)).ravel()
    C = (qa @ M).tocsr()            # C[b, a] = #questions of b naming a
    C.data[C.data < MIN_NAMING_Q] = 0
    C.eliminate_zeros()
    share = sp.diags(1.0 / np.maximum(nq, 1)).dot(C).tocsr()   # share[b, a]
    link = share.T.tocsr()          # link[a, b] = share of b's questions naming a
    sp.save_npz(OUT / "links.npz", link.astype(np.float32))
    print(f"links: {link.nnz:,} label pairs with >= {MIN_NAMING_Q} naming questions "
          f"({time.time() - t0:.0f}s)")
    keys = L["keys"]
    kl = {k: i for i, k in enumerate(keys)}
    for probe in ("bela bartok", "odin"):
        a = kl[probe]
        row = link[a]
        top = sorted(zip(row.indices, row.data), key=lambda x: -x[1] * nq[x[0]])[:12]
        print(f"  {probe}: " + ", ".join(f"{keys[b]} {s:.0%}/{int(nq[b])}q" for b, s in top))


if __name__ == "__main__":
    main()
