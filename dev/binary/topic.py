"""Step 5: per-topic view — answerlines, facts, binaries.

Given a topic answerline (and optional seed phrases for a system such as
a mythology), this:
  1. discovers the topic's answerlines: the topic itself plus every label
     with >= MIN_Q questions whose questions name the topic (or a seed)
     in >= LINK_SHARE of cases;
  2. groups each answerline's units into FACTS (connected components of
     same-label same-fact edges);
  3. rates each fact from its units' status: shared if any member has an
     unforgiven conflict, else binary (>= 2 independent questions) or
     single;
  4. picks the minimal form: the shortest member of >= 6 words, plus the
     fact's anchor terms (rare tokens most members share).

Writes out/topic_{slug}.json and out/topic_{slug}.html.

Usage: python dev/binary/topic.py "bela bartok"
       python dev/binary/topic.py "odin" --seed norse --seed asgard --name "Norse mythology"
"""
import argparse
import html
import json
import re
from collections import Counter, defaultdict

import numpy as np
import scipy.sparse as sp

from anchors import Anchors
from binaries import (CONFLICT_COS, DUP_COS, STATUS_NAMES, ST_BINARY, ST_SHARED, ST_SINGLE,
                      ST_UNCLEAR, ST_UNKNOWN, SUPPORT_COS, SUPPORT_FRAC, Mentions)
from common import OUT, fold, load
from lib.render.theme import theme_vars_css

MIN_Q = 3
LINK_SHARE = 0.30
MAX_ANSWERLINES = 60
KEY_IDF = 8.0          # candidate key terms: df <= ~0.03% of units
KEY_PURITY = 0.80      # >= 80% of the term's corpus units answer this (or a linked) label
KEY_MIN_UNITS = 3


def discover(U, L, M, topic_lab, seeds):
    lab = L["unit_label"]
    qcode = U["_qcode"]
    named_q = set()
    if topic_lab is not None:
        # Which questions name the topic: links.py's capitalised, longest-match
        # mention scan (the raw substring match pulled in The Raft of the
        # Medusa and William Howard Taft for Dostoevsky).
        col = sp.load_npz(OUT / "mention_u.npz").tocsc()[:, topic_lab]
        named_q.update(qcode[col.indices].tolist())
    if seeds:                             # free-text seeds ("norse") are not answerlines
        phrases = [f" {fold(s)} " for s in seeds]
        for i, t in enumerate(U["text"]):
            if any(p in f" {fold(t)} " for p in phrases):
                named_q.add(qcode[i])
    q_of_label = defaultdict(set)
    for i in range(len(lab)):
        q_of_label[int(lab[i])].add(qcode[i])
    out = []
    for b, qs in q_of_label.items():
        if b == topic_lab or len(qs) < MIN_Q:
            continue
        share = len(qs & named_q) / len(qs)
        if share >= LINK_SHARE:
            out.append((b, share, len(qs)))
    out.sort(key=lambda x: (-x[2] * x[1]))
    lines = ([(topic_lab, 1.0, len(q_of_label[topic_lab]))] if topic_lab is not None else []) + out
    return lines[:MAX_ANSWERLINES]


class KeyCheck:
    """Corpus-wide purity of a rare term for a label: of all units
    containing the term, the share whose answer is the label or a label
    linked to it (links.py, either direction >= LINK_SHARE)."""

    def __init__(self, A, L):
        self.cols = A.X.tocsc()
        self.lab = L["unit_label"]
        self.link = sp.load_npz(OUT / "links.npz").tocsr()
        self.linkT = self.link.T.tocsr()
        self._linked = {}

    def linked(self, a):
        s = self._linked.get(a)
        if s is None:
            s = {a}
            for M in (self.link, self.linkT):
                row = M[a]
                s.update(row.indices[row.data >= LINK_SHARE].tolist())
            self._linked[a] = s
        return s

    def purity(self, j, a):
        units = self.cols.indices[self.cols.indptr[j]:self.cols.indptr[j + 1]]
        if not len(units):
            return 0.0, 0
        ok = self.linked(a)
        good = sum(1 for b in self.lab[units].tolist() if b in ok)
        return good / len(units), len(units)


def facts_for(label, U, L, A, idx, cos, status, support, conflicts, keycheck):
    lab = L["unit_label"]
    qcode = U["_qcode"]
    mask = lab == label
    if "query" in U:                      # clause universe: judge the clauses only
        mask &= U["query"]
    mask &= status != 5                   # context units (no reference to the answer)
    units = np.flatnonzero(mask).tolist()
    uset = set(units)

    # Same-label same-fact edges.
    eu, ev = [], []
    for u in units:
        for v, c in zip(idx[u], cos[u]):
            if v < 0 or c < SUPPORT_COS or v not in uset or qcode[u] == qcode[v]:
                continue
            eu.append(u); ev.append(int(v))
    adj = defaultdict(set)
    if eu:
        _, frac = A.pair(np.array(eu), np.array(ev))
        for u, v, f in zip(eu, ev, frac):
            if f >= SUPPORT_FRAC:
                adj[u].add(v); adj[v].add(u)
    # Star clustering: the best-connected unassigned unit seeds a fact and
    # takes its DIRECT neighbours only. Union-find chained every "name
    # this Hungarian composer of X" giveaway into one blob.
    assigned = {}
    groups = []
    for u in sorted(units, key=lambda x: -len(adj[x])):
        if u in assigned:
            continue
        g = [u] + [v for v in adj[u] if v not in assigned]
        for m in g:
            assigned[m] = len(groups)
        groups.append(g)

    facts = []
    for members in groups:
        qs = {qcode[m] for m in members}
        st = [status[m] for m in members]
        texts = sorted(members, key=lambda m: len(U["text"][m]))
        rep = next((m for m in texts if len(U["text"][m].split()) >= 6), texts[0])
        tok = Counter()
        for m in members:
            tok.update(A.X[m].indices.tolist())
        need = max(1, (len(members) + 1) // 2)
        anchors = [A.vocab[j] for j, c in sorted(tok.items(), key=lambda x: -A.idf[x[0]])
                   if c >= need and A.idf[j] >= 7.0][:4] if len(members) > 1 else []
        strong_any = ST_SHARED in st
        comp = Counter()
        conflict_terms = set()
        for m in members:
            for v, b, c, strong in conflicts.get(m, []):
                if strong_any and not strong:
                    continue          # a shared fact is explained by its strong conflicts
                comp[L["keys"][b]] += 1
                conflict_terms |= set(A.X[m].indices.tolist()) & set(A.X[v].indices.tolist())
        keys = []
        if strong_any:
            # Minimum binary inside a shared fact: rare terms the
            # conflicts do NOT run through, verified corpus-wide.
            for j, c in sorted(tok.items(), key=lambda x: -A.idf[x[0]]):
                if j in conflict_terms or A.idf[j] < KEY_IDF:
                    continue
                pur, n = keycheck.purity(j, label)
                if pur >= KEY_PURITY and n >= KEY_MIN_UNITS:
                    keys.append((A.vocab[j], round(pur, 2), n))
        sup = int(max(support[m] for m in members))
        if strong_any:
            fstat = "binary-key" if keys else "shared"
        elif ST_UNCLEAR in st:
            fstat = "unclear"
        elif len(qs) >= 2 or sup >= 2:
            fstat = "binary"
        elif ST_UNKNOWN in st:
            fstat = "unknown"
        else:
            fstat = "single"
        pos = [U["part"][m] / max(U["nparts"][m] - 1, 1) for m in members if U["kind"][m] == 0]
        facts.append(dict(
            status=fstat, questions=len(qs), units=len(members), support=sup,
            rep=U["text"][rep], anchors=anchors, keys=keys[:4],
            shared_on=[A.vocab[j] for j in sorted(conflict_terms & set(tok), key=lambda j: -A.idf[j])][:4],
            position=round(float(np.mean(pos)), 2) if pos else None,
            giveaway=bool(any(U["giveaway"][m] for m in members)),
            competitors=comp.most_common(5),
            examples=[U["text"][m] for m in texts if m != rep][:3],
            # Sentence-level unit ids behind this fact (a clause maps to the
            # sentence it came from): cards.py merges facts across tiers on these.
            sentences=sorted({int(U["parent"][m]) if "parent" in U else int(m) for m in members})))
    order = {"binary": 0, "binary-key": 1, "unclear": 2, "shared": 3, "unknown": 4, "single": 5,
             "context": 6}
    facts.sort(key=lambda f: (order[f["status"]], -max(f["questions"], f["support"]),
                              f["position"] or 0))
    return facts


def render(name, lines, data):
    e = html.escape
    parts = []
    tot = Counter()
    for (lab, share, nq), (key, facts) in zip(lines, data):
        c = Counter(f["status"] for f in facts)
        tot.update(c)
        rows = []
        for f in facts:
            if f["status"] == "single":
                continue
            comp = ""
            if f["competitors"]:
                comp = '<div class="comp">also points to: ' + ", ".join(
                    f'{e(k)} <span class="n">×{n}</span>' for k, n in f["competitors"]) + "</div>"
            anchors = "".join(f'<span class="anc">{e(a)}</span>' for a in f["anchors"])
            keyline = ""
            if f["keys"]:
                keyline = ('<div class="keys">binary key: ' + ", ".join(
                    f'<span class="key" title="{n} corpus units, {p:.0%} on this answerline or a linked one">'
                    f'{e(k)}</span>' for k, p, n in f["keys"]) + "</div>")
            if f["shared_on"]:
                keyline += ('<div class="sharedon">shared on: ' +
                            ", ".join(e(t) for t in f["shared_on"]) + "</div>")
            pos = "" if f["position"] is None else f'<span class="pos" title="mean position in tossup (0 = lead-in, 1 = giveaway)">pos {f["position"]:.2f}</span>'
            ex = ""
            if f["examples"]:
                ex = '<details><summary>other phrasings</summary><ul>' + "".join(
                    f"<li>{e(x)}</li>" for x in f["examples"]) + "</ul></details>"
            rows.append(f'<li class="fact {f["status"]}"><div class="meta"><span class="badge">{f["status"]}</span>'
                        f'<span class="nq" title="questions stating it (incl. from linked answerlines)">'
                        f'{max(f["questions"], f["support"])}q</span>{pos}{anchors}</div>'
                        f'<div class="rep">{e(f["rep"])}</div>{keyline}{comp}{ex}</li>')
        singles = [f for f in facts if f["status"] == "single"]
        single_html = ""
        if singles:
            single_html = (f'<details class="singles"><summary>{len(singles)} single-question facts '
                           f'(unique but unconfirmed)</summary><ul>' +
                           "".join(f"<li>{e(f['rep'])}</li>" for f in singles[:60]) + "</ul></details>")
        parts.append(f'<section><h2>{e(key)} <span class="sub">{nq} questions · '
                     f'{c["binary"]} binary · {c["binary-key"]} with binary key · {c["unclear"]} unclear · '
                     f'{c["shared"]} shared · '
                     f'{c["single"]} single'
                     f'{" · link " + format(share, ".0%") if share < 1 else ""}</span></h2>'
                     f'<ul class="facts">{"".join(rows)}</ul>{single_html}</section>')
    summary = (f'{len(lines)} answerlines · {tot["binary"]} binary facts · {tot["binary-key"]} shared facts '
               f'with a verified binary key · {tot["unclear"]} unclear · {tot["shared"]} shared · '
               f'{tot["single"]} single-question · {tot["unknown"]} unknown')
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Binaries: {e(name)}</title>
<style>
{theme_vars_css()}
body {{ background: var(--c-bg); color: var(--c-text); font: 15px/1.5 system-ui, sans-serif;
       max-width: 980px; margin: 0 auto; padding: 1.5rem 16px 4rem; }}
h1 {{ font-size: 1.5rem; margin: 0 0 .25rem; }}
.lede {{ color: var(--c-muted); margin: 0 0 1.5rem; }}
h2 {{ font-size: 1.1rem; margin: 2rem 0 .5rem; padding-bottom: .3rem; border-bottom: 1px solid var(--c-border); }}
h2 .sub {{ font-weight: 400; font-size: .8rem; color: var(--c-muted); margin-left: .4rem; }}
.facts {{ list-style: none; padding: 0; margin: 0; }}
.fact {{ padding: .55rem .7rem; border-radius: 8px; margin: .35rem 0; background: var(--c-raised2); border-left: 3px solid var(--c-border); }}
.fact.binary {{ border-left-color: var(--c-good); }}
.fact.shared {{ border-left-color: var(--c-warn); }}
.fact.binary-key {{ border-left-color: var(--c-link); }}
.binary-key .badge {{ color: var(--c-link); }}
.keys {{ font-size: .82rem; margin-top: .25rem; color: var(--c-muted); }}
.key {{ background: var(--c-selbg); color: var(--c-text); border-radius: 99px; padding: 0 .45rem; font-weight: 600; }}
.sharedon {{ font-size: .8rem; color: var(--c-muted); }}
.fact.unknown, .fact.unclear {{ border-left-color: var(--c-faint2); }}
.unclear .comp {{ color: var(--c-muted); }}
.meta {{ display: flex; flex-wrap: wrap; gap: .4rem; align-items: center; font-size: .75rem; color: var(--c-muted); margin-bottom: .2rem; }}
.badge {{ font-weight: 600; text-transform: uppercase; letter-spacing: .04em; }}
.binary .badge {{ color: var(--c-good); }} .shared .badge {{ color: var(--c-warn); }}
.anc {{ background: var(--c-hl); color: var(--c-text); border-radius: 99px; padding: 0 .45rem; }}
.rep {{ font-size: .95rem; }}
.comp {{ font-size: .8rem; color: var(--c-warn); margin-top: .2rem; }}
.n {{ color: var(--c-muted); }}
details {{ font-size: .82rem; color: var(--c-muted); margin-top: .25rem; }}
details ul {{ margin: .3rem 0 0 1rem; padding: 0; }}
.singles {{ margin-top: .6rem; }}
</style></head><body>
<h1>Binary clues: {e(name)}</h1>
<p class="lede">{summary}.</p>
<p class="lede"><b>binary</b>: no other answerline states this fact, and 2+ independent questions
state it. Same fact under a linked answerline, an accepted alternative, a different kind of answer,
or with the other answer named in the text is the same fact asked from its other end, not a
conflict. <b>binary key</b>: the sentence also states a shared fact, but these rare terms are
not what the conflicts share, and 80%+ of their uses corpus-wide point to this answerline or one
linked to it. <b>shared</b>: another answerline states the same fact (high-precision rule).
<b>unclear</b>: another answerline states something close; maybe the same fact. Same fact means cos ≥
{SUPPORT_COS} and rare-term overlap ≥ {SUPPORT_FRAC}; conflicts are searched from cos ≥
{CONFLICT_COS}.</p>
{"".join(parts)}
</body></html>"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("topic", help="answerline key, e.g. 'bela bartok'; '' for seed-only")
    ap.add_argument("--seed", action="append", default=[])
    ap.add_argument("--name")
    a = ap.parse_args()
    U = load("units.pkl")
    L = load("labels.pkl")
    _, U["_qcode"] = np.unique(np.array(U["qid"]), return_inverse=True)
    key_label = {k: i for i, vs in enumerate(L["variants"]) for k in vs}
    topic_lab = key_label.get(fold(a.topic)) if a.topic else None
    if a.topic and topic_lab is None:
        raise SystemExit(f"no answerline {a.topic!r}")
    M = Mentions(L)
    A = Anchors()
    keycheck = KeyCheck(A, L)
    idx = np.load(OUT / "nbr_idx.npy", mmap_mode="r")
    cos = np.load(OUT / "nbr_cos.npy", mmap_mode="r")
    st = np.load(OUT / "unit_status.npz")
    conflicts = load("conflicts.pkl")
    lines = discover(U, L, M, topic_lab, a.seed)
    data = []
    for lab, share, nq in lines:
        data.append((L["keys"][lab], facts_for(lab, U, L, A, idx, cos, st["status"], st["support"], conflicts, keycheck)))
    name = a.name or a.topic
    slug = re.sub(r"\W+", "_", fold(name))
    json.dump([dict(answerline=k, share=s, questions=n, facts=f) for (l, s, n), (k, f) in zip(lines, data)],
              open(OUT / f"topic_{slug}.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    (OUT / f"topic_{slug}.html").write_text(render(name, lines, data).replace("�", "&#xFFFD;"),
                                            encoding="utf-8")       # broken source chars
    print(f"{len(lines)} answerlines:")
    for (lab, share, nq), (k, facts) in zip(lines, data):
        c = Counter(f["status"] for f in facts)
        print(f"  {k[:40]:40} {nq:>4}q link {share:.0%}  binary {c['binary']:>3} key {c['binary-key']:>3} unclear {c['unclear']:>3} shared {c['shared']:>3} "
              f"single {c['single']:>3}")
    print(f"-> out/topic_{slug}.html")


if __name__ == "__main__":
    main()
