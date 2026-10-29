"""Tier B, step 1: split clue sentences into single-fact clauses.

Rule-based (no parser installed). A sentence becomes several clauses at:
  - sentence breaks the reader-aligned splitter missed ("... in 1982.
    They also wrote ...");
  - semicolons and statement-level conjunctions: ", while", ", whereas",
    ", although", ", but", " as well as ", and ", and" when a pronoun or a
    verb follows (", and he ...", ", and depicted ...") -- not when a title
    list continues (", and Ma vlast");
  - relative clauses (", which / who / whose / where"), which get their
    antecedent back: "..., who also wrote a pedagogical book" ->
    "Jean-Baptiste Arban also wrote a pedagogical book";
  - giveaway / work lists: "composer of A, B, and C" -> "composer of A",
    "composer of B", "composer of C".
Fragments under MIN_WORDS content words merge back into their neighbour.

    split_clauses(text) -> list[str]

Usage: python dev/binary/clauses.py --selftest
       python dev/binary/clauses.py --sample 30      # random music sentences
"""
import argparse
import random
import re

from common import STOP, fold

MIN_WORDS = 3

_ABBREV = re.compile(r"\b(?:Op|No|Nos|St|Mr|Mrs|Dr|vs|ca|cf|Jr|Sr|Mt|Ft|Vol|[A-Z])\.$")
_SENT = re.compile(r'[.!?]["”’\')]?(\s+)(?=["“(]?[A-Z])')
_CONJ = re.compile(r";\s+|,\s+(?:while|whereas|although|though|but|yet)\s+|\s+as well as\s+", re.I)
# ", and" only with a comma: "short and hunchbacked" is not two statements.
_AND = re.compile(r",\s+and\s+(?=(?:he|she|it|they|this|these|that|those|his|her|its|their|one|another|"
                  r"[a-z]+ed|[a-z]+s)\b)")
_REL = re.compile(r",\s+(which|who|whose|where)\s+")
_LIST_HEAD = re.compile(r"^(?P<head>.*?\b(?:composer|creator|author|artist|of|wrote|composed|"
                        r"including|includes|include|such as|like)\s+)(?P<tail>[A-Z\"“].*)$")
_LIST_SEP = re.compile(r",\s+(?:and\s+|or\s+)?|\s+and\s+(?=[A-Z\"“])")
_CAPSPAN = re.compile(r"[A-Z][\w'’.\-]*(?:(?:\s+(?:of|the|and|de|von|van|la|le|du|des|der|di))*\s+"
                      r"[A-Z][\w'’.\-]*)*")
_REFERENT = re.compile(r"\b(?:this|these)\s+(?:[\w-]+\s+){0,3}?(?:composer|man|woman|person|artist|"
                       r"musician|performer|singer|pianist|conductor|bandleader|drummer|violinist|"
                       r"cellist|guitarist|trumpeter|saxophonist|virtuoso|figure|author|poet)\b", re.I)
# A bare giveaway stub, or a bare referent ("This man"), with no title in it.
_STUB = re.compile(r"^(?:(?i:for (?:10|ten) points),?\s*)?(?:(?i:name|identify|give)\s+)?(?i:this|these)\s+[^A-Z]*$")


def _content_words(s):
    return [w for w in re.findall(r"[A-Za-z][\w'’-]*", s) if w.lower() not in STOP]


def _substantive(p):
    """Enough to state a fact: MIN_WORDS content words, or a name/title
    plus one more content word ("composer of Fidelio")."""
    cw = _content_words(p)
    if len(cw) >= MIN_WORDS:
        return True
    return len(cw) >= 2 and any(w[:1].isupper() for w in cw[1:] + [w for w in cw if w != cw[0]])


def _sentences(text):
    """Split at sentence ends the reader splitter missed, skipping
    abbreviations ("Op. 6", "St. Matthew", initials)."""
    out, start = [], 0
    for m in _SENT.finditer(text):
        piece = text[start:m.start(1)]
        if _ABBREV.search(piece.rstrip()):
            continue
        out.append(piece.strip())
        start = m.end(1)
    out.append(text[start:].strip())
    return [x for x in out if x]


def _antecedent(left, pron):
    """The thing a relative clause refers to. who/whose -> the person
    referent ("this composer") when the text has one; otherwise the last
    capitalised span ending at the comma ("The Ring of the Nibelung"), or
    the last few words."""
    if pron in ("who", "whose"):
        m = list(_REFERENT.finditer(left))
        if m:
            return re.sub(r"^(?:for (?:10|ten) points,?\s*)?(?:name|identify|give)\s+", "",
                          m[-1].group(0), flags=re.I)
    spans = list(_CAPSPAN.finditer(left))
    if spans and spans[-1].end() >= len(left.rstrip()) - 1:
        return spans[-1].group(0)
    words = left.split()
    return " ".join(words[-4:])


def _split_rel(s):
    m = _REL.search(s)
    if not m:
        return [s]
    left, pron, right = s[:m.start()], m.group(1).lower(), s[m.end():]
    ante = _antecedent(left, pron)
    # A bare giveaway stub with no title in it ("Name this composer").
    stub = bool(_STUB.match(left.strip()))
    if stub:
        ante = re.sub(r"^(?:for (?:10|ten) points,?\s*)?(?:name|identify|give)\s+", "", ante, flags=re.I)
    if pron == "whose":
        right = f"{ante}'s {right}"
    elif pron == "where":
        right = f"in {ante}, {right}"
    else:
        right = f"{ante} {right}"
    # A giveaway stub ("Name this composer, who ...") is replaced by its
    # relative clause instead of standing as a fragment.
    return _split_rel(right) if stub else [left] + _split_rel(right)


_TITLE_SMALL = {"of", "the", "and", "for", "in", "a", "an", "on", "to", "de", "la", "le", "du", "von",
                "van", "no", "op", "in", "at", "from", "with", "by", "his", "her", "its", "their",
                "major", "minor", "sharp", "flat"}


def _title_like(x):
    words = re.findall(r"[\w'’.\-]+", x.strip("\"“” "))
    big = [w for w in words if w.lower() not in _TITLE_SMALL]
    return bool(big) and sum(w[:1].isupper() or w[:1].isdigit() for w in big) == len(big)


def _split_list(s):
    m = _LIST_HEAD.match(s)
    if not m:
        return [s]
    head, tail = m.group("head"), m.group("tail").rstrip(" .")
    items = [x.strip() for x in _LIST_SEP.split(tail) if x and x.strip()]
    # Only a true list of titles: every substantive word of every item
    # capitalised ("the Concerto for Orchestra" yes; "Transfigured Night led
    # the Second Viennese School" no).
    if len(items) < 2 or not all(_title_like(x) for x in items):
        return [s]
    return [f"{head}{x}" for x in items]


class _Titles:
    """Known multi-word titles (answerline names of works / unclassified
    proper names, >= 3 words), matched on folded tokens so "Music for
    Strings, Percussion, and Celesta" finds the answerline "music for
    strings percussion and celesta". Loaded lazily from labels.pkl."""

    def __init__(self):
        self.by2 = None

    def _load(self):
        import numpy as np
        from common import BASE_OUT, load
        L = load("labels.pkl") if (BASE_OUT / "labels.pkl").exists() else None
        self.by2 = {}
        if L is None:
            return
        capz = np.load(BASE_OUT / "label_cap.npz") if (BASE_OUT / "label_cap.npz").exists() else None
        for b, vs in enumerate(L["variants"]):
            if L["kind"][b] not in ("work", None) or L["nq"][b] < 2:
                continue
            if capz is not None and capz["cap"][b] < 0.7 * max(capz["all"][b], 1):
                continue
            for k in vs:
                t = tuple(k.split())
                if 3 <= len(t) <= 12:
                    self.by2.setdefault(t[:2], set()).add(t)

    def spans(self, text):
        """Character spans of known titles in text (longest first, no overlap)."""
        if self.by2 is None:
            self._load()
        toks = [(m.start(), m.end(), fold(m.group(0))) for m in re.finditer(r"[\w'’.\-]+", text)]
        toks = [(a, b, w) for a, b, w in toks if w]
        words = [w for _, _, w in toks]
        found = []
        for i in range(len(words) - 1):
            for t in self.by2.get((words[i], words[i + 1]), ()):
                if tuple(words[i:i + len(t)]) == t:
                    found.append((toks[i][0], toks[i + len(t) - 1][1]))
        found.sort(key=lambda x: x[0] - x[1])
        kept = []
        for a, b in found:
            if not any(a < y and x < b for x, y in kept):
                kept.append((a, b))
        return sorted(kept)


_TITLES = _Titles()
_PH = re.compile(r"TITLEPH(\d+)X")


def _protect(text):
    """Replace known titles with placeholder words so their commas and
    "and"s cannot trigger a split."""
    saved, out, last = [], [], 0
    for a, b in _TITLES.spans(text):
        if "," not in text[a:b] and " and " not in text[a:b]:
            continue
        out.append(text[last:a])
        out.append(f"TITLEPH{len(saved)}X")
        saved.append(text[a:b])
        last = b
    out.append(text[last:])
    return "".join(out), saved


def split_clauses(text):
    text, saved = _protect(text)
    out = _split(text)
    return [_PH.sub(lambda m: saved[int(m.group(1))], c) for c in out] if saved else out


def _split(text):
    pieces = []
    for sent in _sentences(text):
        for a in _CONJ.split(sent):
            for b in _AND.split(a):
                for c in _split_rel(b):
                    pieces.extend(_split_list(c))
    # Merge fragments too short to state a fact into a neighbour.
    out = []
    for p in (x.strip(" ,.;") for x in pieces):
        if not p:
            continue
        if out and not _substantive(p):
            out[-1] = f"{out[-1]}, {p}"
        else:
            out.append(p)
    if len(out) > 1 and not _substantive(out[0]):
        out[1] = f"{out[0]}, {out[1]}"
        out = out[1:]
    # Strip giveaway boilerplate: in a short clause the template ("For 10
    # points, name this ... composer of") would dominate the embedding and
    # make every giveaway look like every other.
    out = [_BOILER.sub("", c).strip(" ,") or c for c in out]
    return out or [text]


_BOILER = re.compile(r"^(?:for (?:10|ten) points,?\s*|ftp,?\s*)?(?:(?:name|identify|give)\s+)?(?=this\b|these\b|what\b|which\b)|"
                     r"^(?:for (?:10|ten) points,?\s*|ftp,?\s*)", re.I)


_TESTS = [
    ("Name this composer, who first established themself by composing the score to Star Trek II: "
     "The Wrath of Khan in 1982. They also wrote the score for Avatar.", 2),
    ("Variations on Carnival of Venice that feature this instrument as a soloist were arranged by "
     "Jean-Baptiste Arban, who also wrote a pedagogical book for this instrument.", 2),
    ("For 10 points, name this Hungarian composer of Mikrokosmos, the Concerto for Orchestra, "
     "and Duke Bluebeard's Castle.", 3),
    ("This composer of Pierrot Lunaire and Transfigured Night led the Second Viennese School, "
     "which adopted this musician's atonal \"twelve-tone\" scale.", 2),
    ("The inversion of a third results in an interval of this number.", 1),
    ("this twentieth-century Hungarian composer also wrote Music for Strings, Percussion, and "
     "Celesta and Mikrokosmos.", 2),
    ("For 10 points, name this composer of Fidelio, whose nine symphonies culminated in the "
     "\"Choral Symphony.\"", 2),
    ("For 10 points, name this German Romantic composer of The Ring of the Nibelung, which "
     "includes the \"Ride of the Valkyries\".", 2),
    ("This man, whose childhood spinal tuberculosis left him short and hunchbacked, beat Benny "
     "Goodman in a 1937 battle of the bands.", 1),   # known limit: embedded relative
                                                       # clause stays packed (still correct)
    ("Frederick the Great composed over 100 sonatas for this instrument, which he played.", 2),
]


def selftest():
    bad = 0
    for text, n in _TESTS:
        got = split_clauses(text)
        ok = len(got) == n
        bad += not ok
        print(("ok  " if ok else "FAIL") + f" {len(got)}/{n}: " + " | ".join(got))
    print(f"{len(_TESTS) - bad}/{len(_TESTS)} pass")
    return bad == 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--sample", type=int, default=0)
    a = ap.parse_args()
    if a.selftest:
        raise SystemExit(0 if selftest() else 1)
    if a.sample:
        from common import load
        U = load("units.pkl")
        idx = [i for i in range(len(U["text"])) if U["subcategory"][i] == "Auditory Fine Arts"]
        random.seed(11)
        for i in random.sample(idx, a.sample):
            cl = split_clauses(U["text"][i])
            print(f"\n{U['text'][i]}\n  -> " + "\n  -> ".join(cl))
