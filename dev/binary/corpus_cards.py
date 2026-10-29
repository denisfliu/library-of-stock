"""Corpus-wide binary cards for one scope (the data behind browse.py).

topic.py + cards.py build one topic's deck; this builds EVERY answerline's
deck in a scope at once:
  1. binary facts per tier, vectorised: the scope's units whose status is
     binary, grouped per answerline by star clustering on same-label
     same-fact edges (as topic.py does, without its per-label loop);
  2. the cards.py merge per answerline: clause facts are base cards, an
     overlapping sentence fact confirms one, a key phrase joins the card it
     fits (front, or >= KEY_FIT of its sentences) or stands alone.

Writes out/corpus_cards_{scope}.json:
    {"answerlines": [{id, answer, key, cat, sub, alt, parent, cards: [...]}], ...}
    card = {f: front, t: tiers bitmask (1 key, 2 sentence, 4 clause),
            q: questions, p: placement 0-100 or -1, d: [difficulties],
            y: [set years], ty: 1 tossup | 2 bonus, w: 1 if the phrase is a
            title (a work; titles.py), k: [key phrases],
            x: one other phrasing}
    with cat / sub / alt = the answerline's qbreader category, subcategory
    and alternate subcategory (its most common within the scope).

Usage: python dev/binary/corpus_cards.py --scope music
"""
import argparse
import json
import re
import time
from collections import defaultdict

import numpy as np

from cards import KEY_FIT, display_answer
from common import BASE_OUT, fold
from keys import SCOPES, ParentRule

TIER_KEY, TIER_SENT, TIER_CLAUSE = 1, 2, 4


_SMALL = r"(?:of|the|and|for|de|von|van|la|le|du|des|del)"
_CAP = r"(?:[A-Z][a-z]{0,2}\.|[A-Z0-9][\w'’\-]*)"       # "St." yes, "Raskolnikov." no


def display_phrase(phrase, text, known=frozenset()):
    """A key as written in its example ("Duke Bluebeard's Castle", not
    "duke bluebeard s castle"). A capitalised key widens to the whole title
    around it ("Percussion, and Celesta" -> "Music for Strings, Percussion,
    and Celesta") only when the widened span is a known answerline name;
    otherwise the exact phrase stays ("St Matthew Passion", not "Along with
    the St Matthew Passion")."""
    m = re.search(r"\b(" + r"[\W_]+".join(map(re.escape, phrase.split())) + r")\b", text or "", re.I)
    if not m:
        return phrase
    # 'spam" and "eggs' -> 'spam and eggs'
    span = re.sub(r"\s+", " ", re.sub(r'\s*["“”]\s*', " ", m.group(1))).strip()
    if not re.match(r"[A-Z0-9]", span):
        return span
    left = re.search(r"(?:(?:" + _CAP + "|" + _SMALL + r"),?\s+)+$", text[:m.start(1)])
    right = re.match(r"(?:,?\s+(?:" + _CAP + "|" + _SMALL + r"))+", text[m.end(1):])
    full = (left.group(0) if left else "") + span + (right.group(0) if right else "")
    at = len(left.group(0)) if left else 0
    if not re.search(r"\band\b|,", span, re.I):
        pos = 0
        for part in re.split(r",\s+(?:and\s+)?|\s+and\s+", full):
            start = full.find(part, pos)
            if start <= at < start + len(part):
                full = part
                break
            pos = start + len(part)
    full = re.sub(r"^(?:" + _SMALL + r"\s+)+", "", full, flags=re.I)
    full = re.sub(r"(?:,?\s+" + _SMALL + r")+$", "", full, flags=re.I).strip(" ,")
    return full if full and fold(full) in known else span


def pure(display, known):
    """Is the displayed phrase ONE thing? Lists of names ("Ivan, and Alyosha",
    "Underground and The Idiot", "father, Fyodor") and glued tokens
    ("TheWell") are fragments, unless the phrase is a known title."""
    if fold(display) in known:
        return True
    if "," in display:
        return False
    if re.search(r"\b[A-Z][\w'’-]*\s+and\s+[A-Z]", display):
        return False
    if re.fullmatch(r"[A-Z][a-z]+[A-Z][a-z]+", display):
        return False
    return True


def _norm(s):
    """Spelling-insensitive form: folded, articles/particles dropped,
    plural endings trimmed ("Brandenburg Concertos" ~ "brandenburg concerti")."""
    t = [w for w in fold(s).split() if w not in ("the", "a", "an", "s")]
    t = [w[:-1] + "o" if len(w) > 4 and w.endswith("i") else w.rstrip("s") if len(w) > 3 else w for w in t]
    return " ".join(t)


def _close(a, b):
    if abs(len(a) - len(b)) > 2 or min(len(a), len(b)) < 7:
        return False
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1] <= 2


def dedupe(cards):
    """One row per binary: same phrase up to spelling (Svidrigailov /
    Svidrigaylov), or a phrase inside a longer one of the same deck
    ("Alyona" in "Alyona Ivanova") -> the longer phrase stays, keeping the
    best evidence of both."""
    keep = []
    for c in sorted(cards, key=lambda c: -len(_norm(c["front"]))):
        n = _norm(c["front"])
        hit = next((k for k in keep if k["_n"] == n or _close(k["_n"], n)
                    or f" {n} " in f" {k['_n']} "), None)
        if hit:
            hit["q"] = max(hit["q"], c["q"])
            hit["tiers"] |= c["tiers"]
            hit["diffs"] |= c["diffs"]
            hit["years"] = sorted(set(hit["years"]) | set(c["years"]))
            hit["types"] |= c["types"]
            hit["under"] = hit.get("under") or c.get("under", "")
            hit["keys"] += [p for p in c["keys"] if p not in hit["keys"]]
        else:
            keep.append(dict(c, _n=n))
    for k in keep:
        k.pop("_n")
    return keep


def _load(sub):
    import pickle
    d = BASE_OUT / sub if sub else BASE_OUT
    with open(d / "units.pkl", "rb") as f:
        U = pickle.load(f)
    with open(d / "labels.pkl", "rb") as f:
        L = pickle.load(f)
    st = np.load(d / "unit_status.npz")
    idx = np.load(d / "nbr_idx.npy", mmap_mode="r")
    cos = np.load(d / "nbr_cos.npy", mmap_mode="r")
    th = {"SUPPORT_COS": 0.78, "SUPPORT_FRAC": 0.35}
    if (d / "thresholds.json").exists():
        th.update({k: v for k, v in json.loads((d / "thresholds.json").read_text()).items() if k in th})
    return d, U, L, st["status"], st["support"], idx, cos, th


def facts(sub, rows):
    """Binary facts among `rows` (unit ids) of one universe, per label."""
    d, U, L, status, support, idx, cos, th = _load(sub)
    import scipy.sparse as sp
    X = sp.load_npz(d / "anchors.npz").tocsr()
    B = (X > 0).astype(np.float32).tocsr()
    mass = np.asarray(X.sum(1)).ravel()
    lab = L["unit_label"]
    _, qcode = np.unique(np.array(U["qid"]), return_inverse=True)
    rows = np.asarray(rows)
    rows = rows[status[rows] == 0]
    is_b = np.zeros(len(lab), bool)
    is_b[rows] = True
    uu = np.repeat(rows, idx.shape[1])
    vv = np.asarray(idx[rows]).ravel().astype(np.int64)
    cc = np.asarray(cos[rows]).ravel().astype(np.float32)
    ok = (vv >= 0) & (cc >= th["SUPPORT_COS"])
    uu, vv = uu[ok], vv[ok]
    ok = is_b[vv] & (lab[uu] == lab[vv]) & (qcode[uu] != qcode[vv])
    uu, vv = uu[ok], vv[ok]
    shared = np.asarray(X[uu].multiply(B[vv]).sum(1)).ravel() if len(uu) else np.zeros(0)
    frac = shared / np.maximum(np.minimum(mass[uu], mass[vv]), 1e-6)
    ok = frac >= th["SUPPORT_FRAC"]
    adj = defaultdict(set)
    for u, v in zip(uu[ok].tolist(), vv[ok].tolist()):
        adj[u].add(v); adj[v].add(u)
    by_label = defaultdict(list)
    for u in rows.tolist():
        by_label[int(lab[u])].append(u)
    out = defaultdict(list)
    for b, units in by_label.items():
        assigned = set()
        for u in sorted(units, key=lambda x: -len(adj[x])):
            if u in assigned:
                continue
            g = [u] + [v for v in adj[u] if v not in assigned]
            assigned.update(g)
            texts = sorted(g, key=lambda m: len(U["text"][m]))
            rep = next((m for m in texts if len(U["text"][m].split()) >= 6), texts[0])
            pos = [U["part"][m] / max(U["nparts"][m] - 1, 1) for m in g if U["kind"][m] == 0]
            out[b].append(dict(
                front=U["text"][rep],
                other=next((U["text"][m] for m in texts if m != rep), ""),
                q=max(len({qcode[m] for m in g}), int(max(support[m] for m in g))),
                pos=float(np.mean(pos)) if pos else None,
                diffs={int(U["diff"][m]) for m in g if U["diff"][m] > 0},
                sentences={int(U["parent"][m]) if "parent" in U else int(m) for m in g}))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scope", default="music", choices=sorted(SCOPES))
    a = ap.parse_args()
    t0 = time.time()
    import pickle
    with open(BASE_OUT / "units.pkl", "rb") as f:
        U = pickle.load(f)
    with open(BASE_OUT / "labels.pkl", "rb") as f:
        L = pickle.load(f)
    in_scope = SCOPES[a.scope]
    scope_rows = [i for i in range(len(U["text"])) if in_scope(U, i)]
    s_facts = facts(None, scope_rows)
    print(f"sentence facts: {sum(map(len, s_facts.values())):,} ({time.time() - t0:.0f}s)", flush=True)
    # The clause tier is optional evidence (a tier dot): scopes built
    # without a clause universe still get their key cards.
    c_facts = {}
    if (BASE_OUT / f"clauses_{a.scope}" / "unit_status.npz").exists():
        with open(BASE_OUT / f"clauses_{a.scope}" / "units.pkl", "rb") as f:
            q = pickle.load(f)["query"]
        c_facts = facts(f"clauses_{a.scope}", np.flatnonzero(q))
    print(f"clause facts: {sum(map(len, c_facts.values())):,} ({time.time() - t0:.0f}s)", flush=True)
    keys = json.load(open(BASE_OUT / f"keys_{a.scope}.json", encoding="utf-8"))["keys"]
    pr = ParentRule(L, len(set(U["qid"])), U)
    # every answerline name, for title widening in display_phrase
    known = {re.sub(r"^the ", "", v) for vs in L["variants"] for v in vs}
    keys_by = defaultdict(list)
    for k in keys:
        keys_by[k["owner_id"]].append(k)

    # Display name, category, subcategory per label (from its scope units).
    lab = L["unit_label"]
    # Display name = the most common written form across ALL the label's
    # questions ("Virginia Woolf", not the first-seen "Adeline Virginia Woolf");
    # category = the label's most common one within the scope.
    from collections import Counter
    names, cats = defaultdict(Counter), defaultdict(Counter)
    allcats = defaultdict(Counter)
    # (category, subcategory, alternate subcategory): qbreader's taxonomy
    for i in range(len(lab)):
        names[int(lab[i])][display_answer(U["answer"][i])] += 1
        allcats[int(lab[i])][(U["category"][i], U["subcategory"][i], U["alt"][i])] += 1
    for i in scope_rows:
        cats[int(lab[i])][(U["category"][i], U["subcategory"][i], U["alt"][i])] += 1
    # Labels reached only through key phrases may have no scope question:
    # fall back to their category anywhere in the corpus.
    info = {b: (names[b].most_common(1)[0][0], *(cats[b] or allcats[b]).most_common(1)[0][0])
            for b in set(cats) | set(names)}
    name_of_key = {L["keys"][b]: names[b].most_common(1)[0][0] for b in names}
    # Works and characters of the scope that belong to someone stay in even
    # without binaries of their own, so the browser can still nest them
    # (Raskolnikov under Crime and Punishment under Dostoevsky).
    placed = {b for b in cats if L["kind"][b] in ("work", "person") and pr.parents(b)}
    labels = set(s_facts) | set(c_facts) | set(keys_by) | placed
    sent_fold = {}

    def stext(sid):
        s = sent_fold.get(sid)
        if s is None:
            s = sent_fold[sid] = f" {fold(U['text'][sid])} "
        return s

    out = []
    for b in labels:
        cards = [dict(f, tiers=TIER_CLAUSE, keys=[]) for f in c_facts.get(b, [])]
        for f in s_facts.get(b, []):
            hit = [c for c in cards if c["sentences"] & f["sentences"]]
            if hit:
                for c in hit:
                    c["tiers"] |= TIER_SENT
                    c["q"] = max(c["q"], f["q"])
                    c["diffs"] |= f["diffs"]
            else:
                cards.append(dict(f, tiers=TIER_SENT, keys=[]))
        for k in keys_by.get(b, []):
            pad = f" {k['phrase']} "

            def fit(c):
                if pad in f" {fold(c['front'])} ":
                    return 1.0
                return sum(1 for s in c["sentences"] if pad in stext(s)) / max(len(c["sentences"]), 1)

            hit = [c for c in cards if fit(c) >= KEY_FIT]
            if hit:
                best = max(hit, key=lambda c: (fit(c), c["q"]))
                best["keys"].append(k["phrase"])
                best["tiers"] |= TIER_KEY
                best["q"] = max(best["q"], k["support"])
                best["diffs"] |= set(k.get("diffs", []))
            else:
                ex = k["examples"]
                cards.append(dict(front=ex[0] if ex else k["phrase"], other=ex[1] if len(ex) > 1 else "",
                                  q=k["support"], pos=None, diffs=set(k.get("diffs", [])),
                                  sentences=set(), tiers=TIER_KEY, keys=[k["phrase"]]))
        # Pure binaries: one row per key phrase. The sentence / clause tiers
        # are evidence (the tier dots), never rows of their own.
        tiers_of = {}
        for c in cards:
            for p in c["keys"]:
                tiers_of[p] = c["tiers"]
        cards = []
        for k in keys_by.get(b, []):
            ex = k["examples"][0] if k["examples"] else ""
            cards.append(dict(front=display_phrase(k["phrase"], ex, known), tiers=tiers_of.get(k["phrase"], TIER_KEY),
                              q=k["support"], pos=k.get("pos"), diffs=set(k.get("diffs", [])),
                              keys=[k["phrase"]], other=ex, years=k.get("years", []), types=k.get("types", 3),
                              title=k.get("form") == "title",
                              under=name_of_key.get(k.get("under"), k.get("under")) if k.get("under") else ""))
        cards = dedupe([c for c in cards if pure(c["front"], known)])
        if not cards and b not in placed:
            continue
        cards.sort(key=lambda c: (-c["q"], -bin(c["tiers"]).count("1")))
        # The work's creator (keys.ParentRule: a dominant person its questions name).
        pids = pr.parents(b)
        parent = [name_of_key.get(L["keys"][x], L["keys"][x]) for x in pids]
        name, cat, sub, alt = info.get(b, (L["keys"][b], None, None, None))
        out.append(dict(
            id=int(b), answer=name, key=L["keys"][b], cat=cat, sub=sub, alt=alt, kind=L["kind"][b], parent=parent,
            parent_id=[int(x) for x in pids],
            cards=[dict(f=c["front"], t=c["tiers"], q=int(c["q"]),
                        p=-1 if c["pos"] is None else round(100 * c["pos"]),
                        d=sorted(c["diffs"]), y=c.get("years", []), ty=c.get("types", 3),
                        w=int(c.get("title", False)), u=c.get("under", ""), k=c["keys"], x=c.get("other", ""))
                   for c in cards]))
    out.sort(key=lambda a: -len(a["cards"]))
    path = BASE_OUT / f"corpus_cards_{a.scope}.json"
    json.dump(dict(scope=a.scope, answerlines=out), open(path, "w", encoding="utf-8"), ensure_ascii=False)
    n = sum(len(a["cards"]) for a in out)
    print(f"{len(out):,} answerlines, {n:,} cards -> {path.name} "
          f"({path.stat().st_size / 1e6:.1f} MB, {time.time() - t0:.0f}s)")


if __name__ == "__main__":
    main()
