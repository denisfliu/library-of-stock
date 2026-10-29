"""Step 1: canonical answerlines.

Every unit's raw answer string is parsed into a *key* (the folded main
answer, parentheticals / pronunciation guides / tags removed) plus its
alternative answers (or/accept clauses, and prompt clauses separately).

Keys are merged into *labels* conservatively — accept clauses are far too
loose to merge on ("Napoleonic Wars [or French Revolutionary Wars]",
"natural selection [accept directional selection]"):
  1. identical keys, and surface-form variants (spaces, possessive "s",
     plural last token: "derekwalcott", "hess s law", "photons");
  2. accept-linked NAME VARIANTS: A lists B as or/accept, both are
     person-like (>= PERSON_MIN of their tossup sentences use he/she/
     "this composer"...), same first and last token, one key's tokens
     inside the other's ("alexander pushkin" ~ "alexander sergeyevich
     pushkin"; NOT "t cells" ~ "helper t cells");
  3. surname: a one-token key t joins the dominant person-like
     multi-token key ending in t (>= 3x the runner-up, same top
     category).

Alternatives are kept per label (not merged on) for two later uses:
mention detection (does a clue name another answerline?) and
compatibility (would one answer be accepted on the other's question?).

Writes out/labels.pkl:
    unit_label  np.int32[N]
    keys        list[str]          representative key per label
    count       np.int32[L]        units per label
    nq          np.int32[L]        distinct questions per label
    cat         list[str]          dominant category
    variants    list[set[str]]     merged keys
    alts        list[set[str]]     or/accept alternatives (folded)
    prompts     list[set[str]]     prompt-on alternatives (folded)
    kind        list[str|None]     person/place/work/event (>= KIND_MIN of
                                   its units say "this <kind noun>")

Usage: python dev/binary/answerlines.py
"""
import re
from collections import Counter, defaultdict

import numpy as np

from common import OUT, STOP, fold, load, save

_DROP_ITEM = re.compile(r"\b(do not|don ?t|reject|anti ?prompt|not|no credit)\b")
# Moderator notes inside brackets ("the first three concertos are
# Prokofiev, Gubaidulina...", "first line refers to Out of Doors") are not
# alternative answers.
_NOTE = re.compile(r"\b(is|are|was|were|refers?|mentioned|described|clue|line|question)\b")
_VAGUE = re.compile(r"\b(equivalent|equivalents|either order|any |reasonable|word forms|"
                    r"similar|answers? (mentioning|that)|obvious|specific)\b")
_TAIL = re.compile(r"\s+\b(until|before|after|once|if|when|by asking|since)\b.*$")
_LEAD = re.compile(r"^(also |or |and )?(accept|or|prompt on|prompt|also accept|"
                   r"accept either|be lenient)\b\s*:?\s*")


def parse(answer: str):
    """-> (key, alts, prompts). key is '' when nothing usable remains."""
    a = re.sub(r"<[^>]*>", " ", answer or "")
    # Remove bracket groups rather than truncating at the first one:
    # "Bela (Viktor Janos) Bartok" -> "Bela Bartok", not "Bela".
    groups = re.findall(r"[\[\(]([^\]\)]*)[\]\)]", a)
    main = re.sub(r"[\[\(][^\]\)]*[\]\)]", " ", a)
    main = re.split(r"[\[\(]", main)[0]          # unbalanced trailing group
    key = fold(main)
    key = re.sub(r"^the ", "", key)
    alts, prompts = set(), set()
    for grp in groups:
        for item in re.split(r";", grp):
            low = item.strip().lower()
            if not low or _DROP_ITEM.search(low) or _NOTE.search(low):
                continue
            is_prompt = low.startswith(("prompt", "also prompt", "or prompt"))
            body = _LEAD.sub("", low)
            body = _LEAD.sub("", body)
            for piece in re.split(r",\s*(?:or\s+)?|\s+or\s+", body):
                piece = _TAIL.sub("", piece.strip())
                if not piece or _VAGUE.search(piece + " "):
                    continue
                f = re.sub(r"^the ", "", fold(piece))
                if len(f) >= 3 and f != key and len(f.split()) <= 8:
                    (prompts if is_prompt else alts).add(f)
    return key, alts, prompts


_PARTICLES = {"s", "van", "von", "de", "di", "da", "del", "der", "du", "la", "le"}


CENTROID_SAME = 0.93       # middle-name variants (John Adams / J. Q. Adams: 0.871)
CENTROID_GENERIC = 0.90    # "parable of the grand inquisitor" ~ "grand inquisitor": 0.909
_GENERIC_OF = re.compile(r"^(?:the )?(?:parable|legend|tale|myth) of (?:the )?")


def _form_key(k: str) -> str:
    # Name particles drop out too: "ludwig van beethoven" = "ludwig von beethoven".
    t = [w for w in k.split() if w not in _PARTICLES]
    if t and len(t[-1]) > 3 and t[-1].endswith("s") and not t[-1].endswith("ss"):
        t[-1] = t[-1][:-1]
    return "".join(t)


class DSU:
    def __init__(self):
        self.p = {}

    def find(self, x):
        p = self.p
        p.setdefault(x, x)
        while p[x] != x:
            p[x] = p[p[x]]
            x = p[x]
        return x

    def union(self, a, b):
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.p[rb] = ra


_PERSON = re.compile(r"\b(he|his|him|she|her|hers|himself|herself)\b|\bth(is|ese) (man|woman|person|"
                     r"author|writer|poet|novelist|playwright|dramatist|composer|artist|painter|"
                     r"sculptor|architect|photographer|philosopher|thinker|scientist|chemist|"
                     r"physicist|biologist|mathematician|economist|ruler|king|queen|leader|"
                     r"president|emperor|general|monarch|pope|saint|figure|god|goddess|deity|"
                     r"hero|explorer|director|singer|musician|conductor|psychologist)\b", re.I)
PERSON_MIN = 0.5

# Coarse answer kinds. Two answers of different kinds cannot fill the same
# blank ("this Hungarian composer" is never Hungary), so the binary test
# only counts a conflict between labels of the same kind (or unknown).
# "thing" lumps physical/biological/abstract objects: coarse on purpose.
KIND_NOUNS = {
    "person": """man woman men women person people author writer poet novelist playwright
        dramatist composer artist painter sculptor architect photographer philosopher
        thinker scientist chemist physicist biologist mathematician economist ruler king
        queen leader president emperor general monarch pope saint figure god goddess deity
        hero heroine explorer director singer musician conductor psychologist sociologist
        character protagonist narrator figure titan giant prophet apostle sultan shah tsar
        pharaoh dynasty family brothers sisters""",
    "place": """country nation city town state island river lake mountain region province
        capital empire kingdom republic colony sea ocean desert valley peninsula continent
        site location place planet moon star galaxy""",
    "work": """novel poem opera symphony piece work play painting ballet story film book song
        quartet concerto suite sonata cantata oratorio collection essay treatise novella
        sculpture statue album cycle mass requiem epic text scripture tragedy comedy
        series trilogy movement aria overture etude""",
    "thing": """instrument element compound molecule substance mineral protein enzyme hormone
        organ organelle cell gene particle device machine ship vessel weapon animal plant
        species disease drug color colour number letter word language""",
    "event": """war battle revolution rebellion revolt event treaty conflict crisis massacre
        uprising election expedition siege conference council""",
}
_KIND_OF = {w: k for k, ws in KIND_NOUNS.items() for w in ws.split()}
_THIS_NOUN = re.compile(r"\b(?:this|these)\s+(?:[a-z'-]+\s+){0,3}?(" +
                        "|".join(sorted(_KIND_OF, key=len, reverse=True)) + r")s?\b", re.I)
KIND_MIN = 0.4


def _name_variant(a: str, b: str) -> bool:
    """Same first and last name, one key's tokens inside the other's
    (middle names). Only called on person-like keys."""
    ta, tb = a.split(), b.split()
    if len(ta) < 2 or len(tb) < 2 or ta[-1] != tb[-1]:
        return False
    if ta[0] != tb[0]:
        # The shorter may drop LEADING names ("joseph haydn" ~ "franz joseph
        # haydn"); "john adams" is no suffix of "john quincy adams".
        short, long_ = (ta, tb) if len(ta) < len(tb) else (tb, ta)
        return long_[len(long_) - len(short):] == short
    sa, sb = set(ta), set(tb)
    return sa <= sb or sb <= sa


def _spelling_variant(a: str, b: str) -> bool:
    """One-token spelling difference in a person's name: a first name
    ("josef haydn" ~ "joseph haydn"; both >= 5 letters) or a transliterated
    surname ("fyodor dostoevsky" ~ "fyodor dostoyevsky"; both >= 6 letters).
    Same token count, every other token identical, same first three
    letters, edit distance <= 2."""
    ta, tb = a.split(), b.split()
    if len(ta) != len(tb) or len(ta) < 2:
        return False
    diff = [(i, x, y) for i, (x, y) in enumerate(zip(ta, tb)) if x != y]
    if len(diff) != 1:
        return False
    i, x, y = diff[0]
    min_len = 6 if i == len(ta) - 1 else 5
    if min(len(x), len(y)) < min_len or x[:3] != y[:3]:
        return False
    prev = list(range(len(y) + 1))
    for i, cx in enumerate(x, 1):
        cur = [i]
        for j, cy in enumerate(y, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (cx != cy)))
        prev = cur
    return prev[-1] <= 2


def main():
    U = load("units.pkl")
    n = len(U["answer"])
    parsed = {}
    unit_key = []
    for a in U["answer"]:
        r = parsed.get(a)
        if r is None:
            r = parsed[a] = parse(a)
        unit_key.append(r[0])

    key_units = Counter(unit_key)
    key_q = defaultdict(set)
    key_cat = defaultdict(Counter)
    key_person = defaultdict(lambda: [0, 0])     # [person-register hits, tossup units]
    key_kind = defaultdict(Counter)
    key_alts = defaultdict(set)
    key_prompts = defaultdict(set)
    for i, k in enumerate(unit_key):
        key_q[k].add((U["kind"][i], U["qid"][i], U["part"][i] if U["kind"][i] else -1))
        key_cat[k][U["category"][i]] += 1
        if U["kind"][i] == 0:
            kp = key_person[k]
            kp[1] += 1
            kp[0] += bool(_PERSON.search(U["text"][i]))
        km = _THIS_NOUN.search(U["text"][i])
        key_kind[k][_KIND_OF[km.group(1).lower()] if km else None] += 1
    for a, (k, alts, prompts) in parsed.items():
        key_alts[k] |= alts
        key_prompts[k] |= prompts

    def is_person(k):
        hits, tot = key_person.get(k, (0, 0))
        return tot >= 2 and hits / tot >= PERSON_MIN

    dsu = DSU()
    for k in key_units:
        dsu.find(k)
    n_alias = n_surname = n_form = 0
    # Surface-form variants of one answerline: run-together tokens
    # ("derekwalcott"), possessive "s" ("hess s law"), plural last token
    # ("photons", "clarinets"). Grouped by a form key; all members merge.
    by_form = defaultdict(list)
    for k in key_units:
        if k:
            by_form[_form_key(k)].append(k)
    for ks in by_form.values():
        for k in ks[1:]:
            if dsu.find(ks[0]) != dsu.find(k):
                n_form += 1
            dsu.union(ks[0], k)
    for k, alts in key_alts.items():
        for a in alts:
            if a in key_units and _name_variant(k, a) and (is_person(k) or is_person(a)):
                if dsu.find(k) != dsu.find(a):
                    n_alias += 1
                dsu.union(k, a)
    # Spelling variants of person names ("josef haydn" ~ "joseph haydn").
    n_spell = 0
    person_keys = [k for k in key_units if is_person(k) and len(k.split()) >= 2]
    # Candidates share either the surname, or the first name plus the
    # surname's first three letters (transliterated surnames).
    by_last_p = defaultdict(list)
    for k in person_keys:
        t = k.split()
        by_last_p[("last", t[-1])].append(k)
        by_last_p[("first", t[0], t[-1][:3], len(t))].append(k)
    for ks in by_last_p.values():
        for i in range(len(ks)):
            for j in range(i + 1, len(ks)):
                if _spelling_variant(ks[i], ks[j]) and dsu.find(ks[i]) != dsu.find(ks[j]):
                    dsu.union(ks[i], ks[j])
                    n_spell += 1
    # Vector-checked merges: the two answerlines' clues must say nearly the
    # same things (centroid cosine >= CENTROID_SAME):
    #  - middle names without an accept-clause link ("rodion raskolnikov" ~
    #    "rodion romanovich raskolnikov" 0.957; "john adams" ~ "john quincy
    #    adams" is 0.871 and stays apart);
    #  - "parable / legend / tale / myth of X" ~ "X" ("the grand inquisitor").
    V = np.load(OUT / "vecs.npy", mmap_mode="r")
    units_of = defaultdict(list)
    for i, k in enumerate(unit_key):
        units_of[k].append(i)

    def centroid(k):
        x = np.asarray(V[units_of[k][:400]], dtype=np.float32).mean(0)
        return x / max(np.linalg.norm(x), 1e-9)

    n_vec = 0
    pairs = []
    by_ends = defaultdict(list)            # any multi-word key, by (first, last) word
    for k in key_units:
        t = k.split()
        if len(t) >= 2:
            by_ends[(t[0], t[-1])].append(k)
    for ks in by_ends.values():
        for i in range(len(ks)):
            for j in range(i + 1, len(ks)):
                ta, tb = ks[i].split(), ks[j].split()
                if len(ta) != len(tb) and (set(ta) <= set(tb) or set(tb) <= set(ta)):
                    pairs.append((ks[i], ks[j], CENTROID_SAME))
    for k in key_units:
        m = _GENERIC_OF.match(k)
        if m and k[m.end():] in key_units:
            pairs.append((k, k[m.end():], CENTROID_GENERIC))
    for a, b, th in pairs:
        if dsu.find(a) != dsu.find(b) and centroid(a) @ centroid(b) >= th:
            dsu.union(b, a)
            n_vec += 1
    # Initials: "j s bach" = "johann sebastian bach", "c p e bach" = "carl
    # philipp emanuel bach". Every initial must line up with the full
    # name's tokens in order, and the surname must match exactly.
    n_init = 0
    full_by_last = defaultdict(list)
    for k in key_units:
        t = k.split()
        if len(t) >= 2 and all(len(w) > 1 for w in t[:-1]):
            full_by_last[t[-1]].append(t)
    for k in key_units:
        t = k.split()
        if len(t) < 2 or not all(len(w) == 1 for w in t[:-1]):
            continue
        initials = t[:-1]
        matches = [f for f in full_by_last.get(t[-1], ())
                   if len(f) - 1 == len(initials) and all(f[i][0] == initials[i] for i in range(len(initials)))]
        matches.sort(key=lambda f: -len(key_q[" ".join(f)]))
        if matches and (len(matches) == 1 or
                        len(key_q[" ".join(matches[0])]) >= 3 * len(key_q[" ".join(matches[1])])):
            if dsu.find(k) != dsu.find(" ".join(matches[0])):
                n_init += 1
            dsu.union(" ".join(matches[0]), k)
    # Surname rule.
    by_last = defaultdict(list)
    for k in key_units:
        t = k.split()
        if len(t) >= 2:
            by_last[t[-1]].append(k)
    for k in key_units:
        if " " in k or not k or k in STOP:
            continue
        # "philip ii of macedon" is not a person named Macedon.
        cands = sorted((c for c in by_last.get(k, ()) if " of " not in c and " de " not in c),
                       key=lambda c: -len(key_q[c]))
        if not cands:
            continue
        top = cands[0]
        second = len(key_q[cands[1]]) if len(cands) > 1 else 0
        same_cat = key_cat[top].most_common(1)[0][0] == key_cat[k].most_common(1)[0][0]
        if len(key_q[top]) >= 3 * max(second, 1) and same_cat and is_person(top):
            dsu.union(top, k)
            n_surname += 1

    # Labels: one per DSU root; representative = most-asked variant.
    groups = defaultdict(list)
    for k in key_units:
        groups[dsu.find(k)].append(k)
    keys, variants, alts, prompts, cats, counts, nqs, kinds = [], [], [], [], [], [], [], []
    key_label = {}
    for root, members in groups.items():
        lid = len(keys)
        members.sort(key=lambda m: -len(key_q[m]))
        keys.append(members[0])
        variants.append(set(members))
        alts.append(set().union(*(key_alts[m] for m in members)) - set(members))
        prompts.append(set().union(*(key_prompts[m] for m in members)) - set(members))
        cc = Counter()
        for m in members:
            cc.update(key_cat[m])
        cats.append(cc.most_common(1)[0][0])
        kc = Counter()
        for m in members:
            kc.update(key_kind[m])
        tot = sum(kc.values())
        named = [(c, k) for k, c in kc.items() if k is not None]
        best = max(named) if named else (0, None)
        kinds.append(best[1] if tot and best[0] / tot >= KIND_MIN else None)
        counts.append(sum(key_units[m] for m in members))
        nqs.append(len(set().union(*(key_q[m] for m in members))))
        for m in members:
            key_label[m] = lid
    unit_label = np.array([key_label[k] for k in unit_key], dtype=np.int32)
    save("labels.pkl", dict(unit_label=unit_label, keys=keys, count=np.array(counts, np.int32),
                            nq=np.array(nqs, np.int32), cat=cats, variants=variants,
                            alts=alts, prompts=prompts, kind=kinds))

    nq = np.array(nqs)
    print(f"units {n}; raw answer strings {len(parsed)}; keys {len(key_units)}; "
          f"labels {len(keys)} (form merges {n_form}, alias merges {n_alias}, initials merges {n_init}, spelling merges {n_spell}, "
          f"vector-checked merges {n_vec}, "
          f"surname merges {n_surname})")
    for th in (1, 2, 5, 10, 25):
        sel = nq >= th
        print(f"  labels with >= {th:>2} questions: {sel.sum():>6}  "
              f"covering {np.array(counts)[sel].sum() / n:.1%} of units")
    print("largest merged labels:")
    for lid in sorted(range(len(keys)), key=lambda l: -len(variants[l]))[:12]:
        print(f"  {keys[lid]!r}: {sorted(variants[lid], key=len)[:8]}")
    for probe in ("bela bartok", "odin", "yggdrasil", "john adams", "john quincy adams",
                  "napoleonic wars", "alexander pushkin", "concerto for orchestra", "hungary",
                  "franz liszt", "gustav holst"):
        lid = key_label.get(probe)
        if lid is None:
            print(f"  {probe!r}: no label"); continue
        print(f"  {probe!r} -> label {keys[lid]!r} [{kinds[lid]}] nq={nqs[lid]} variants={sorted(variants[lid])[:6]}"
              f" alts={sorted(alts[lid])[:6]}")


if __name__ == "__main__":
    main()
