"""Tier A: key phrases -> the one answerline they point to.

The short, evocative binaries are mostly NAMES: titles (Stimmen...
Verstummen), movements and arias ("Interrupted Intermezzo", "Sheep May
Safely Graze"), characters (Schlendrian), tags ("conductor solos"). For
those, identity is lexical, so this tier is lexical too.

1. Candidates (from the units of SCOPE, e.g. music questions only):
   quoted strings, capitalised spans, rare single words, and the names
   of the scope's answerlines. A candidate must contain a rare token
   (alias_ok).
2. Occurrences: every unit in the WHOLE corpus whose text contains the
   phrase (so "Offertorium" inside a Requiem question counts against
   Gubaidulina).
3. World of an occurrence = the unit's answer, plus every answerline its
   own sentence names (mention_u.npz), plus one level of parents (a
   Concerto for Orchestra question is in Bartók's world). Per question
   the worlds of its occurrence units are merged.
4. Owner = the answerline present in >= PURITY of the phrase's
   independent questions (>= MIN_Q of them). The phrase's own label
   (the phrase IS its name) is not a candidate owner, so a work's title
   yields work -> creator. When several labels qualify, the most specific
   (one not a parent of another) is the owner; the rest are recorded as
   the chain upward.
5. Hygiene and minimality: a key may not contain its owner's name
   ("gubaidulina s canticle" leaks the answer); a key whose shorter
   sub-phrase is already a key for the same owner is dropped; an
   AMBIGUOUS phrase (some owner at >= EXTEND_FLOOR but < PURITY) is
   retried with the 1-2 words that precede it in scope occurrences
   ("offertorium" 59% -> "violin concerto offertorium").

Writes out/keys_{scope}.json: [{phrase, owner, share, questions,
chain, kind, form (title / clue), examples, outside}] for qualifying keys, plus the
near-misses with their competing owners.

Usage: python dev/binary/keys.py [--scope music]
"""
import argparse
import json
import re
import time
from collections import Counter, defaultdict

import numpy as np
import scipy.sparse as sp

from common import ALIAS_MIN_IDF, OUT, STOP, alias_ok, fold, fold_case, load
from titles import classify as classify_forms
from links import shares_word

PURITY = 0.80
MIN_Q = 2
EXTEND_FLOOR = 0.30
MAX_OCC_Q = 4000            # phrases in more questions than this are not keys
CHILD_SHARE = 0.30          # c is a child of a when >= 30% of c's questions name a
                            # (and a dominates any rival parent; see parents())
SPECIFIC_SHARE = 0.005      # owners/parents must be named in <= 0.5% of all questions
SYNONYM_LINK = 0.50         # two owners naming each other this often are one answer
PROPER_CAP = 0.70           # a label is a proper name when >= 70% of its matches are capitalised
SCOPE_SHARE = 0.50          # a key's questions must be mostly in scope
CONCEPT_NQ = 20             # a concept answerline this big is a descriptor, not a key
RARE_WORD_IDF = 9.0         # single lowercase words this rare are candidates
LOWER_NGRAM_IDF = 8.0       # a lowercase n-gram needs one word this rare
LOWER_EDGE_IDF = 6.0        # ...and, with only 2 support, content words at both edges
MAX_TOKENS = 8

SCOPES = {
    "music": lambda U, i: U["subcategory"][i] == "Auditory Fine Arts",
    "literature": lambda U, i: U["category"][i] == "Literature",
    "extra": lambda U, i: U["category"][i] in ("Mythology", "Religion", "Philosophy", "Social Science")
    or U["subcategory"][i] == "Biology",
    "history": lambda U, i: U["category"][i] == "History",
    "csmath": lambda U, i: U["subcategory"][i] == "Other Science" and U["alt"][i] in ("Math", "Computer Science"),
    # the rest of the corpus (key tier only: no clause universe)
    "arts": lambda U, i: U["category"][i] == "Fine Arts" and U["subcategory"][i] != "Auditory Fine Arts",
    "science": lambda U, i: U["category"][i] == "Science" and U["subcategory"][i] != "Biology"
    and not (U["subcategory"][i] == "Other Science" and U["alt"][i] in ("Math", "Computer Science")),
    "geography": lambda U, i: U["category"][i] == "Geography",
    "misc": lambda U, i: U["category"][i] in ("Current Events", "Other Academic"),
    "pop": lambda U, i: U["category"][i] == "Pop Culture",
}

_LEAD = set("""this these that those in for name his her its their one after during a an the
when while although like with by on at as he she it they another some many both each ftp
points 10 ten identify give what which who whose from to of and or but not so if also its
following following""".split())
QUALIFIERS = set("""concerto symphony opera ballet quartet quintet trio sonata suite cantata
oratorio mass requiem song songs cycle overture prelude fugue etude etudes nocturne waltz march
piano violin viola cello flute oboe clarinet bassoon horn trumpet trombone tuba harp organ guitar
harpsichord string strings orchestral choral chamber symphonic tone poem major minor sharp flat
first second third fourth fifth sixth seventh eighth ninth tenth no""".split())
_QUOTE = re.compile(r'["“”]([^"“”]{3,80})["“”]')
_CAPS = re.compile(r"(?:[A-Z][\w'’.\-]*)(?:(?:\s+(?:of|the|for|and|in|a|an|de|du|la|le|von|van|"
                   r"der|des|di|del|on|to|with|at|from|by)\s+|\s+)(?:[A-Z0-9][\w'’.\-]*))*")


def _clean(p):
    t = fold(p).split()
    while t and t[0] in _LEAD:
        t = t[1:]
    while t and (t[-1] in STOP or t[-1] == "s"):      # "telemann s" (possessive)
        t = t[:-1]
    while t and t[0] == "s":
        t = t[1:]
    if not t or len(t) > MAX_TOKENS:
        return None
    s = " ".join(t)
    return s if len(s) >= 4 and alias_ok(s) else None


def lower_ngrams(text, idf):
    """Lowercase descriptive phrases ("lake of tears", "conductor solos"):
    2-4 lowercase words, no filler at either edge, at least one rare word."""
    fc = fold_case(text).split()
    fl = [w.lower() for w in fc]
    out = set()
    for n in range(2, 5):
        for i in range(len(fl) - n + 1):
            win = fl[i:i + n]
            if any(w[:1].isupper() or w.isdigit() for w in fc[i:i + n]):
                continue
            if win[0] in _LEAD or win[0] in STOP or win[-1] in STOP or win[-1] == "s":
                continue
            if any(idf.get(w, 0) >= LOWER_NGRAM_IDF for w in win):
                out.add(" ".join(win))
    return out


_CHARACTER = re.compile(r"\bth(?:is|ese)\s+(?:[a-z'-]+\s+){0,2}?"
                        r"(?:character|protagonist|narrator|heroine|anti-?hero)s?\b", re.I)
_MAKER = re.compile(r"\bth(?:is|ese)\s+(?:[a-z'-]+\s+){0,2}?(?:author|writer|poet|novelist|"
                    r"playwright|dramatist|composer|artist|painter|sculptor|architect|philosopher|"
                    r"thinker|director|filmmaker|photographer|songwriter|lyricist|librettist|"
                    r"choreographer|essayist|critic|historian|theorist)s?\b", re.I)
_REAL = re.compile(r"\bth(?:is|ese)\s+(?:[a-z'-]+\s+){0,2}?(?:man|woman|person|scientist|ruler|"
                   r"king|queen|leader|general|god|goddess|deity|hero)s?\b", re.I)
ROLE_SHARE = 0.30
MAKER_NQ = 20                # a maker this asked about may skip the two-sided check
UNDER_SHARE = 0.5               # a key sits under its owner's work carrying this share of support
TITLE_FWD, TITLE_REV = 0.50, 0.10  # common-word titles (The Idiot) climb on this much evidence


def person_roles(U, L):
    """-> (character, maker): per label, is it a fictional character or a
    maker of works, read off how its questions refer to it.
    character: >= ROLE_SHARE of its questions say "this character /
        protagonist / narrator", and no fewer than say "this author / man /
        king ..." (Raskolnikov 0.72 vs 0.10; Kafka 0.05 vs 0.98; Odysseus,
        a hero of myth, 0.15). Characters climb from a person to a work.
    maker: >= ROLE_SHARE say "this author / composer / painter ...". A
        work's parent is preferably a maker (Othello -> Shakespeare, not
        the "Moors" its questions also name)."""
    lab, kind = L["unit_label"], L["kind"]
    allq, ch, mk, real = (defaultdict(set) for _ in range(4))
    for i in range(len(lab)):
        b = int(lab[i])
        if kind[b] not in ("person", None):
            continue
        q, t = U["qid"][i], U["text"][i]
        allq[b].add(q)
        if _CHARACTER.search(t):
            ch[b].add(q)
        if _MAKER.search(t):
            mk[b].add(q)
        if _REAL.search(t):
            real[b].add(q)
    character, maker = np.zeros(len(kind), bool), np.zeros(len(kind), bool)
    for b, qs in allq.items():
        character[b] = len(ch[b]) >= ROLE_SHARE * len(qs) and len(ch[b]) >= len(mk[b] | real[b])
        maker[b] = len(mk[b]) >= ROLE_SHARE * len(qs) and not character[b]
    return character, maker


class ParentRule:
    """Which person a work (or unclassified proper name) belongs to, from
    links.py: shared by keys.py and corpus_cards.py so both agree."""

    def __init__(self, L, n_questions, U, out=OUT):
        self.L = L
        self.character, self.maker = person_roles(U, L)
        self.creators = None            # people some work climbs to (lazy)
        named_q = np.asarray(sp.load_npz(out / "mention_q.npz").sum(0)).ravel()
        self.specific = named_q <= SPECIFIC_SHARE * n_questions
        capz = np.load(out / "label_cap.npz")
        cap_ratio = capz["cap"] / np.maximum(capz["all"], 1)
        self.proper = (cap_ratio >= PROPER_CAP) & (capz["cap"] >= 3)
        # Who may own a key or be a parent: specific labels, plus proper-named
        # people and works however often they are named (Beethoven is named in
        # >0.5% of questions but must still own "Grosse Fuge"; "hungarian" may not).
        self.ownable = self.specific | (self.proper & np.array([k in ("person", "work") for k in L["kind"]]))
        self.linkT = sp.load_npz(out / "links.npz").tocsr().T.tocsr()
        self.cache = {}

    def parents(self, c):
        p = self.cache.get(c)
        if p is not None:
            return p
        L = self.L
        if self.character[c]:
            p = self._character_of(c)
        elif L["kind"][c] == "work" and not self.proper[c]:
            p = self._common_word_title(c)
        elif not self.proper[c] or L["kind"][c] not in ("work", None):
            # Only proper-named works (or unclassified names) climb: a
            # question answered "suites" or "fugue" is not in Bach's world,
            # one answered "Concerto for Orchestra" is in Bartók's. People
            # and places never climb (Romania's most-named person is
            # Ceausescu; Bach's is not his "parent").
            p = []
        else:
            row = self.linkT[c]
            # Climb only to ONE person-kind parent (creator, god) that is
            # specific and clearly dominant: "hungarian" is not Bartók's
            # parent, and "night music" (Bartók's style AND Mozart's
            # Nachtmusik) has no single parent, so it climbs nowhere.
            # Never to a character (Metamorphosis -> Kafka, not Gregor), nor
            # through a one-sided name collision (see two_sided). A maker,
            # when one qualifies, beats everyone else.
            cand = sorted(((float(s), int(x)) for x, s in zip(row.indices, row.data)
                           if s >= CHILD_SHARE and x != c and self.ownable[x]
                           and L["kind"][x] == "person" and not self.character[x]
                           and self.two_sided(c, x)), reverse=True)
            if any(self.maker[x] for _, x in cand):
                # Between makers, the one whose own questions name c wins:
                # Dover Beach is Arnold's (0.66 x 0.76), not Sophocles'
                # (0.55 x 0.08), and Gitanjali Tagore's, not Yeats's.
                # A duplicate label of the same maker (Alessandro beside Sandro
                # Botticelli) may tie on that score: the maker clearly ahead
                # on share alone then still wins.
                makers = [(s, x) for s, x in cand if self.maker[x]]
                if len(makers) > 1 and makers[1][0] <= 0.6 * makers[0][0]:
                    cand = makers
                else:
                    cand = sorted(((s * max(self.linkT[x, c], 0.05), x) for s, x in makers), reverse=True)
            else:
                # Drop a candidate that sits below another one, i.e. its
                # questions name the other more than the other's name it
                # (the harpsichordist Goldberg -> Bach 1.0 vs 0.39).
                xs = {x for _, x in cand}
                cand = [(s, x) for s, x in cand
                        if not any(y != x and self.linkT[x, y] >= CHILD_SHARE and self.linkT[x, y] > self.linkT[y, x]
                                   for y in xs)]
            p = [cand[0][1]] if cand and (len(cand) == 1 or cand[1][0] <= 0.6 * cand[0][0]) else []
        self.cache[c] = p
        return p

    def _common_word_title(self, c):
        """A work titled with common words (The Idiot, The Stranger, Las
        Meninas) fails the capitalisation test that keeps "suites" from
        climbing, so it climbs only on strong two-sided evidence: one maker
        named in >= TITLE_FWD of its questions, whose own questions name it
        in >= TITLE_REV, clearly ahead of any other. Movements labelled as
        works (surrealism -> Breton) never climb."""
        L, row = self.L, self.linkT[c]
        if re.search(r"is(m|mo)$", L["keys"][c]):
            return []
        cand = sorted(((float(s), int(x)) for x, s in zip(row.indices, row.data)
                       if s >= TITLE_FWD and x != c and self.maker[x] and self.linkT[x, c] >= TITLE_REV),
                      reverse=True)
        return [cand[0][1]] if cand and (len(cand) == 1 or cand[1][0] <= 0.6 * cand[0][0]) else []

    def two_sided(self, c, x):
        """c's questions name x, and x's own questions name c at least once,
        unless x is a well-asked maker (Shakespeare's 161 questions never
        name The Merchant of Venice). Catches name collisions: "Regan" in
        King Lear questions links the ethicist Tom Regan, "Atticus" links
        Herodes Atticus; neither's questions ever name the book."""
        return self.linkT[x, c] > 0 or (self.maker[x] and self.L["nq"][x] >= MAKER_NQ)

    def _character_of(self, c):
        """A character climbs to its work: one proper, specific work that
        >= CHILD_SHARE of c's questions name, that has a creator of its own,
        and that clearly dominates any rival work (Raskolnikov -> Crime and
        Punishment -> Dostoevsky). Failing that, to the one creator its
        works share (Stephen Dedalus: Portrait and Ulysses -> Joyce), or to
        a dominant creator its questions name (Emma Bovary -> Flaubert;
        a creator is someone a work climbs to)."""
        L, row = self.L, self.linkT[c]
        named = sorted(((float(s), int(x)) for x, s in zip(row.indices, row.data)
                        if s >= CHILD_SHARE and x != c and not self.character[x]
                        and self.two_sided(c, x)), reverse=True)
        works = [(s, x) for s, x in named if self.specific[x] and self.proper[x] and L["kind"][x] == "work"
                 and self.parents(x) and c not in self.parents(x)]
        if works and (len(works) == 1 or works[1][0] <= 0.6 * works[0][0]):
            return [works[0][1]]
        creators = {tuple(self.parents(x)) for _, x in works}
        if len(creators) == 1:
            return list(creators.pop())
        if self.creators is None:
            self.creators = {y for x in range(len(L["kind"])) if L["kind"][x] == "work" for y in self.parents(x)}
        people = [(s, x) for s, x in named if x in self.creators]
        if not works and people and (len(people) == 1 or people[1][0] <= 0.6 * people[0][0]):
            return [people[0][1]]
        return []

    def ancestors(self, c):
        """parents(), transitively: a character's work and its creator."""
        out, todo = [], list(self.parents(c))
        while todo:
            x = todo.pop()
            if x != c and x not in out:
                out.append(x)
                todo.extend(self.parents(x))
        return out


def candidates(U, L, scope_units, idf, lower=False):
    """-> (candidate phrases, the subset that came only from lowercase n-grams)."""
    cnt = Counter()
    lower_cnt = Counter()
    for i in scope_units:
        # Parentheticals are mostly pronunciation guides ("vin-ter-RYE-zuh").
        text = re.sub(r"\([^)]*\)|\[[^\]]*\]", " ", U["text"][i])
        found = set()
        for m in _QUOTE.finditer(text):
            found.add(_clean(m.group(1)))
        for m in _CAPS.finditer(text):
            found.add(_clean(m.group(0)))
        for w in fold(text).split():
            if len(w) >= 6 and idf.get(w, 0) >= RARE_WORD_IDF:
                found.add(w)
        found.discard(None)
        cnt.update(found)
        if lower:
            lower_cnt.update(lower_ngrams(text, idf) - found)
    # Names of the scope's answerlines are always candidates (work -> creator).
    lab = L["unit_label"]
    scope_labels = Counter(int(lab[i]) for i in scope_units)
    for b, c in scope_labels.items():
        if c >= 2:
            for k in L["variants"][b]:
                if alias_ok(k) and len(k.split()) <= MAX_TOKENS:
                    cnt[k] += 2
    base = {p for p, c in cnt.items() if c >= 2}
    low = {p for p, c in lower_cnt.items() if c >= 2} - base
    return base | low, low


class PhraseIndex:
    """Find which candidate phrases occur in each unit (token match)."""

    def __init__(self, phrases):
        self.single = defaultdict(list)
        self.pair = defaultdict(list)
        self.phrases = list(phrases)
        for j, p in enumerate(self.phrases):
            t = tuple(p.split())
            (self.single[t[0]] if len(t) == 1 else self.pair[t[:2]]).append((t, j))

    def scan(self, toks):
        found = set()
        for p in range(len(toks)):
            for t, j in self.single.get(toks[p], ()):
                found.add(j)
            if p + 1 < len(toks):
                for t, j in self.pair.get((toks[p], toks[p + 1]), ()):
                    if len(t) == 2 or tuple(toks[p:p + len(t)]) == t:
                        found.add(j)
        return found


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scope", default="music", choices=sorted(SCOPES))
    ap.add_argument("--explain", nargs="*", default=[], help="print the decision for these phrases")
    ap.add_argument("--lower", action="store_true",
                    help="also try lowercase descriptive n-grams as candidates")
    a = ap.parse_args()
    t0 = time.time()
    U = load("units.pkl")
    L = load("labels.pkl")
    lab = L["unit_label"]
    n = len(lab)
    _, qcode = np.unique(np.array(U["qid"]), return_inverse=True)
    MU = sp.load_npz(OUT / "mention_u.npz").tocsr()
    link = sp.load_npz(OUT / "links.npz").tocsr()           # link[a, c]: share of c's q naming a
    v = load("vocab.pkl")
    idf = dict(zip(v["vocab"], v["idf"].tolist()))
    in_scope = SCOPES[a.scope]
    scope_units = [i for i in range(n) if in_scope(U, i)]
    scope_set = set(scope_units)
    print(f"{len(scope_units):,} {a.scope} units ({time.time() - t0:.0f}s)", flush=True)

    pr = ParentRule(L, len(set(qcode.tolist())), U)
    specific, proper, ownable, parents = pr.specific, pr.proper, pr.ownable, pr.ancestors

    # Which labels does a phrase NAME? (exact key / alternative match)
    name_of = defaultdict(set)
    for b, vs in enumerate(L["variants"]):
        for k in vs:
            name_of[k].add(b)
        for k in L["alts"][b]:
            if alias_ok(k) and (" " not in k or shares_word(k, L["variants"][b])):
                name_of[k].add(b)

    # One-word surnames -> the dominant person (>= 3x the questions of any
    # rival), as links.py resolves them: "bach" -> J. S. Bach.
    sur = defaultdict(list)
    for b, vs in enumerate(L["variants"]):
        if L["kind"][b] == "person":
            for k in vs:
                t = k.split()
                if len(t) >= 2 and len(t[-1]) >= 4:
                    sur[t[-1]].append(b)
    for w, bs in list(sur.items()):
        bs = sorted(set(bs), key=lambda b: -L["nq"][b])
        if len(bs) == 1 or L["nq"][bs[0]] >= 3 * L["nq"][bs[1]]:
            name_of[w].add(bs[0])

    # Phrases that ARE a person's name: a full variant, or a span of it
    # that keeps its first or last token ("villa lobos", "carl philipp emanuel").
    person_ref = defaultdict(set)
    for b, vs in enumerate(L["variants"]):
        if L["kind"][b] != "person":
            continue
        for k in vs:
            t = k.split()
            for i in range(len(t)):
                for j in range(i + 1, len(t) + 1):
                    if (i == 0 or j == len(t)) and len(" ".join(t[i:j])) >= 4:
                        person_ref[" ".join(t[i:j])].add(b)

    def named_inside(p):
        """Every label a sub-phrase of p names. None of them can own p:
        "edouard lalo s symphonie espagnole" names Lalo, the work and
        Spain, so it is not a clue for any of them."""
        t = p.split()
        out = set()
        for i in range(len(t)):
            for j in range(i + 1, min(len(t), i + MAX_TOKENS) + 1):
                out |= name_of.get(" ".join(t[i:j]), set())
        return out

    def surname_set(b):
        out = set(L["variants"][b])
        for k in L["variants"][b]:
            t = k.split()
            if len(t) >= 2 and len(t[-1]) >= 4:
                out.add(t[-1])
        return out

    toks_all = None
    kind = L["kind"]

    def evaluate(phrases):
        """Per phrase and candidate owner c, classify every question that
        contains the phrase (see the module docstring):
            support  - the hidden answer is c, or a work of c's
            neutral  - c is named there (visible: context, not a clue), or
                       every answer is a different kind of thing than c
            conflict - another same-kind answer, c not named
        share = support / (support + conflict)."""
        nonlocal toks_all
        if toks_all is None:
            toks_all = [fold(t).split() for t in U["text"]]
        idx = PhraseIndex(phrases)
        occ = defaultdict(list)
        for i, ts in enumerate(toks_all):
            for j in idx.scan(ts):
                occ[j].append(i)
        results = {}
        for j, units in occ.items():
            p = idx.phrases[j]
            ans, nam = defaultdict(set), defaultdict(set)
            for u in units:
                ans[qcode[u]].add(int(lab[u]))
                nam[qcode[u]].update(MU.indices[MU.indptr[u]:MU.indptr[u + 1]].tolist())
            if len(ans) > MAX_OCC_Q:
                continue
            selfs = named_inside(p)
            cands = Counter()
            for q, A in ans.items():
                world = set(A)
                for x in A:
                    world.update(parents(x))
                cands.update(world - selfs)
            ranked = []
            for c, _ in cands.most_common(8):
                sup = con = 0
                for q, A in ans.items():
                    if c in A or any(c in parents(x) for x in A):
                        sup += 1
                    elif c in nam[q] or any(c in parents(x) for x in nam[q]):
                        continue
                    elif kind[c] is not None and all(kind[x] is not None and kind[x] != kind[c] for x in A):
                        continue
                    else:
                        con += 1
                if sup:
                    ranked.append((c, sup / (sup + con), sup, con))
            ranked.sort(key=lambda x: (-x[1], -x[2]))
            results[p] = dict(nq=len(ans), ranked=ranked, units=units,
                              in_scope=sum(1 for u in units if u in scope_set),
                              scope_q=len({qcode[u] for u in units if u in scope_set}),
                              **(dict(ans=ans, nam=nam) if p in a.explain else {}))
        return results

    cands, lower_only = candidates(U, L, scope_units, idf, lower=a.lower)
    print(f"{len(cands):,} candidate phrases ({len(lower_only):,} lowercase n-grams) "
          f"({time.time() - t0:.0f}s)", flush=True)
    res = evaluate(cands)
    print(f"evaluated ({time.time() - t0:.0f}s)", flush=True)

    # Extension round for ambiguous phrases.
    ext = Counter()
    for p, r in res.items():
        if r["ranked"] and r["ranked"][0][2] >= MIN_Q and EXTEND_FLOOR <= r["ranked"][0][1] < PURITY:
            pt = p.split()
            for u in r["units"]:
                if u not in scope_set:
                    continue
                ts = toks_all[u]
                tc = fold_case(U["text"][u]).split()
                if len(tc) != len(ts):
                    continue
                for s in range(len(ts) - len(pt) + 1):
                    if ts[s:s + len(pt)] == pt:
                        for k in (1, 2):
                            if s - k < 0:
                                continue
                            # Qualifiers only: genre / instrument / key words or
                            # capitalised words ("violin concerto offertorium",
                            # "g minor piano trio"), never verbs ("include the").
                            if all((w in QUALIFIERS or c[:1].isupper()) and w not in _LEAD
                                   for w, c in zip(ts[s - k:s], tc[s - k:s])):
                                ext[" ".join(ts[s - k:s] + pt)] += 1
    ext_phr = {e for e, c in ext.items() if c >= 2 and e not in res}
    if ext_phr:
        res.update(evaluate(ext_phr))
    print(f"extension round: {len(ext_phr):,} phrases ({time.time() - t0:.0f}s)", flush=True)

    # Decide owners. decide() returns (reason, owner); reason "key" accepts.
    def decide(p, r):
        if not r["ranked"]:
            return "no candidate", None
        qual = [b for b, s, sup, con in r["ranked"]
                if s >= PURITY and sup >= MIN_Q and ownable[b] and L["nq"][b] >= 2]
        if len(qual) > 1 and any(proper[b] for b in qual):
            # Prefer proper names: "joaquin", "violin", "concert" drop out
            # when a real name qualifies too.
            qual = [b for b in qual if proper[b]]
        if len(qual) > 1:
            # Synonyms split across labels (Moldau / Die Moldau / Vltava)
            # link strongly both ways: keep the most asked one.
            qual.sort(key=lambda b: -L["nq"][b])
            merged = []
            for b in qual:
                if not any(link[b, m] >= SYNONYM_LINK and link[m, b] >= SYNONYM_LINK for m in merged):
                    merged.append(b)
            qual = merged
        if not qual:
            return "below purity", None
        # most specific: not a parent of another qualifier
        narrowest = [b for b in qual if not any(b in parents(c) for c in qual if c != b)]
        if len(narrowest) > 1:
            return "two owners", narrowest          # Suite bergamasque: Debussy and Bach
        owner = narrowest[0] if narrowest else qual[0]
        if r["scope_q"] < SCOPE_SHARE * r["nq"]:
            return "mostly outside scope", owner     # "huns"
        pad = f" {p} "
        if any(f" {x} " in pad for x in surname_set(owner)):
            return "contains the answer", owner
        if any(pad in f" {x} " for x in L["variants"][owner]):
            return "part of the answer", owner       # "johann sebastian"
        if L["kind"][owner] is None and not proper[owner]:
            return "generic owner", owner            # "themes"
        named = named_inside(p)
        # A phrase that is only a big concept plus filler ("baroque era",
        # "this german baroque") describes, it does not identify: drop it
        # when nothing rare is left once the concept's words are removed.
        # "bluebeard s castle" keeps "bluebeard".
        concept_tok = set()
        for b in named:
            if L["kind"][b] is None and L["nq"][b] >= CONCEPT_NQ:
                for k in L["variants"][b]:
                    concept_tok.update(k.split())
        rest = [w for w in p.split() if w not in concept_tok]
        if concept_tok and not any(idf.get(w, 0) >= ALIAS_MIN_IDF for w in rest):
            return "only a concept", owner
        if p in lower_only:
            # Ordinary wording can hit 2/0 by coincidence ("imitated in this
            # work"). Lowercase phrases need 3+ support, or content words at
            # both edges plus one genuinely rare word ("bird cages").
            st = {x[0]: x for x in r["ranked"]}[owner]
            t = p.split()
            edges_ok = idf.get(t[0], 0) >= LOWER_EDGE_IDF and idf.get(t[-1], 0) >= LOWER_EDGE_IDF
            if not (st[2] >= 3 or (edges_ok and any(idf.get(w, 0) >= RARE_WORD_IDF for w in t))):
                return "weak lowercase evidence", owner
            # A cut-off phrase ("idea of the categorical" -> imperative, "compile
            # folk" -> songs): in most occurrences the next word is another
            # lowercase content word, so the phrase is not a whole unit.
            pat = re.compile(r"\b" + r"[\W_]+".join(map(re.escape, t)) + r"\b[\"'”’)]?\s+([A-Za-z][\w'’-]*)", re.I)
            occ = cont = 0
            for u in r["units"][:60]:
                if u not in scope_set:
                    continue
                m = pat.search(U["text"][u])
                if not m:
                    continue
                occ += 1
                w = m.group(1)
                cont += w[:1].islower() and w.lower() not in STOP
            if occ and cont / occ >= 0.5:
                return "cut-off phrase", owner
        # A person's name pointing at another person is a connection, not a
        # clue (Villa-Lobos -> Bach), unless the named one belongs to the
        # owner: a character of theirs (Raskolnikov -> Crime and Punishment).
        if L["kind"][owner] == "person" and any(
                b != owner and L["nq"][b] >= 5 and owner not in parents(b) for b in person_ref.get(p, ())):
            return "person -> person connection", owner   # Villa-Lobos -> Bach
        return "key", (owner, qual)

    keys, near = [], []
    for p, r in res.items():
        reason, val = decide(p, r)
        if p in a.explain:
            print(f"\n[explain] {p!r}: {reason}; nq={r['nq']} scope_q={r['scope_q']}")
            for b, sh, sup, con in r["ranked"]:
                print(f"    {sh:5.0%} sup={sup} con={con} {L['keys'][b]} [{L['kind'][b]}] proper={bool(proper[b])} "
                      f"ownable={bool(ownable[b])} nq={L['nq'][b]} parents={[L['keys'][x] for x in parents(b)]}")
            if r["ranked"]:
                # what the top candidate's conflicting questions were answered
                c, conf = r["ranked"][0][0], Counter()
                for q, A in r["ans"].items():
                    if not (c in A or any(c in parents(x) for x in A)) and not (
                            c in r["nam"][q] or any(c in parents(x) for x in r["nam"][q])):
                        conf.update(L["keys"][x] for x in A)
                print("    conflicts:", ", ".join(f"{k} {n}" for k, n in conf.most_common(12)))
        if reason != "key":
            if reason in ("below purity", "two owners") and r["ranked"] and \
                    r["ranked"][0][1] >= EXTEND_FLOOR and r["in_scope"] >= 2:
                comp = val if reason == "two owners" else [x[0] for x in r["ranked"][:4]]
                sh = {x[0]: x[1] for x in r["ranked"]}
                near.append(dict(phrase=p, questions=r["nq"], reason=reason,
                                 competing=[(L["keys"][b], round(sh[b], 2)) for b in comp]))
            continue
        owner, qual = val
        stats = {x[0]: x for x in r["ranked"]}
        share, sup, con = stats[owner][1], stats[owner][2], stats[owner][3]
        chain = [L["keys"][b] for b in qual if b != owner]
        # Which of the owner's works the phrase points into,
        # when it is not specific enough to own on its own: the best-supported
        # descendant, if it carries most of the owner's support and leads any
        # rival ("rogozhin" -> Dostoevsky, under The Idiot).
        below = sorted(((x[2], x[0]) for x in r["ranked"]
                        if x[0] != owner and L["kind"][x[0]] == "work" and owner in parents(x[0])), reverse=True)
        under = None
        if below and below[0][0] >= UNDER_SHARE * sup and (len(below) == 1 or below[1][0] <= 0.6 * below[0][0]):
            under = L["keys"][below[0][1]]
        ex = []
        for u in r["units"]:
            if u in scope_set and len(ex) < 3:
                ex.append(U["text"][u])
        outside = [(L["keys"][x[0]], round(x[1], 2)) for x in r["ranked"] if x[0] not in qual][:3]
        keys.append(dict(phrase=p, owner=L["keys"][owner], owner_id=int(owner),
                         kind=L["kind"][owner], share=round(share, 2), questions=r["nq"],
                         support=sup, conflicts=con,
                         owner_parent=[L["keys"][x] for x in parents(owner)],
                         source="lowercase" if p in lower_only else "name",
                         # set difficulties (qbreader 1-10) of the scope questions using it
                         diffs=sorted({int(U["diff"][u]) for u in r["units"] if u in scope_set}),
                         years=sorted({int(U["year"][u]) for u in r["units"] if u in scope_set}),
                         # 1 = used in a tossup, 2 = in a bonus
                         types=int(any(U["kind"][u] == 0 for u in r["units"] if u in scope_set))
                         | 2 * int(any(U["kind"][u] != 0 for u in r["units"] if u in scope_set)),
                         # mean position (0 lead-in, 1 giveaway) in the tossups where
                         # the phrase is a clue for the owner or one of its works
                         pos=round(float(np.mean(sup_pos)), 2) if (sup_pos := [
                             U["part"][u] / max(U["nparts"][u] - 1, 1) for u in r["units"]
                             if U["kind"][u] == 0 and u in scope_set
                             and (lab[u] == owner or owner in parents(int(lab[u])))]) else None,
                         chain=chain, under=under, names=sorted(L["keys"][b] for b in name_of.get(p, ()))[:3],
                         examples=ex, outside=outside,
                         _qids={U["qid"][u] for u in r["units"]}))
    # Minimality, per owner: a key containing a shorter key is redundant,
    # EXCEPT that a full title (an exact answerline name) beats its own
    # fragments: keep "eine kleine nachtmusik", drop "kleine".
    def subs_of(ph):
        t = ph.split()
        return {" ".join(t[i:j]) for i in range(len(t)) for j in range(i + 1, len(t) + 1)} - {ph}

    by_owner = defaultdict(list)
    for k in keys:
        by_owner[k["owner_id"]].append(k)
    final = []
    for owner, ks in by_owner.items():
        phr = {k["phrase"] for k in ks}
        titles = {k["phrase"] for k in ks if k["phrase"] in name_of}
        inside_title = set().union(*(subs_of(t) for t in titles)) if titles else set()
        for k in ks:
            ph = k["phrase"]
            if ph in titles:
                if not (subs_of(ph) & titles):
                    final.append(k)
            elif ph not in inside_title and not (subs_of(ph) & phr):
                final.append(k)
    final.sort(key=lambda k: (-k["questions"], k["phrase"]))
    # Title (a work: "Space Oddity") or clue (Jareth, "sped-up vocals"),
    # read off the writers' italics and quotation marks (titles.py).
    work_names = {v for b, vs in enumerate(L["variants"]) if L["kind"][b] == "work" for v in vs}
    classify_forms(final, {k["phrase"]: k["_qids"] for k in final}, work_names)
    for k in keys:
        k.pop("_qids")
    out = OUT / f"keys_{a.scope}.json"
    json.dump(dict(keys=final, near=sorted(near, key=lambda x: -x["questions"])),
              open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    kinds = Counter(k["kind"] for k in final)
    print(f"{len(final):,} keys ({len(keys) - len(final):,} non-minimal dropped), "
          f"{len(near):,} ambiguous near-misses; owner kinds {dict(kinds)}; "
          f"{sum(k['form'] == 'title' for k in final):,} titles "
          f"({time.time() - t0:.0f}s) -> {out.name}")


if __name__ == "__main__":
    main()
