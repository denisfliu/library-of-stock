"""Is a key phrase a TITLE (a work: Space Oddity, Goldberg Variations) or
a CLUE (a character, a detail, a description: Jareth, sped-up vocals)?

Quizbowl writers mark titles: long works in italics, short works (songs,
poems, stories) in quotation marks. The mirror keeps that markup in the
raw question text, so a phrase's form is read off its occurrences:

  marked       the occurrence is mostly inside <i>/<em>; or it is quoted
               and written in Title Case ("Space Oddity"); or it is the
               whole quotation, capitalised, with no English function
               word ("Nessun dorma"). A quoted lyric such as "I'm an
               alligator" is none of these;
  informative  the question has any italics at all (so an unitalicised
               occurrence is evidence against a title), or the
               occurrence is quoted.

title share = marked / informative. A phrase with no informative
occurrence falls back to the answerlines: it is a title if it is the
name of a work answerline.

Self-test: python dev/binary/titles.py
"""
import json
import re
import sqlite3
import unicodedata
from collections import defaultdict

from common import MIRROR, STOP

TITLE_SHARE = 0.5
_TAG = re.compile(r"<(/?)(i|em|b|strong|u|span|br|p)\b[^>]*>", re.I)
_QUOTE = re.compile(r"[\"“”]([^\"“”]{1,150})[\"“”]")
_SMALL = set("a an the of and or for in on at to by with from as but nor de du la le les von van der des di del y e et".split())


def _plain(raw):
    """Raw question HTML -> (plain text, italic flag per char)."""
    out, ital, depth, pos = [], [], 0, 0
    for m in _TAG.finditer(raw):
        seg = raw[pos:m.start()]
        out.append(seg)
        ital.extend([depth > 0] * len(seg))
        if m.group(2).lower() in ("i", "em"):
            depth = max(0, depth + (-1 if m.group(1) else 1))
        pos = m.end()
    seg = raw[pos:]
    out.append(seg)
    ital.extend([depth > 0] * len(seg))
    return "".join(out), ital


def _fold_chars(s):
    """fold() one char at a time, so offsets line up with the plain text."""
    out = []
    for c in s:
        b = unicodedata.normalize("NFKD", c)[:1].lower()
        out.append(b if b.isalnum() else " ")
    return "".join(out)


_WORD = re.compile(r"[^\W_]+(?:['’][^\W_]+)*")   # "Man's" is one word
_ENGLISH = STOP | {"i", "you", "me", "my", "we", "is", "are"}


def _title_case(s):
    words = _WORD.findall(s)
    return bool(words) and words[0][0].isupper() and \
        all(w[0].isupper() or w[0].isdigit() or w.lower() in _SMALL for w in words)


def _foreign_title(span, quote):
    """The whole quotation, capitalised, and not English prose."""
    quote = quote.strip()
    return len(span.strip()) >= 0.8 * len(quote) and quote[:1].isupper() and \
        not any(w.lower() in _ENGLISH for w in _WORD.findall(quote))


class Question:
    """One question's raw HTML, parsed once for every phrase tested on it."""

    def __init__(self, raw):
        self.text, self.ital = _plain(raw)
        self.folded = _fold_chars(self.text)
        self.has_ital = any(self.ital)
        self.quoted = [(m.start(1), m.end(1)) for m in _QUOTE.finditer(self.text)]

    def quote_at(self, a, b):
        return next(((qa, qb) for qa, qb in self.quoted if qa <= a and b <= qb), None)

    def occurrences(self, phrase):
        """(marked, informative) occurrences of a folded phrase."""
        pat = re.compile(r"(?<![^\W_])" + r"\s+".join(map(re.escape, phrase.split())) + r"(?![^\W_])")
        marked = informative = 0
        for m in pat.finditer(self.folded):
            a, b = m.start(), m.end()
            q = self.quote_at(a, b)
            if not (self.has_ital or q):
                continue
            informative += 1
            span = self.text[a:b]
            if sum(self.ital[a:b]) * 2 > b - a or \
                    (q and (_title_case(span) or _foreign_title(span, self.text[q[0]:q[1]]))):
                marked += 1
        return marked, informative


def occurrences(phrase, raw):
    return Question(raw).occurrences(phrase)


def raw_texts(qids):
    """Raw HTML per question id (tossup text, or bonus lead-in + parts)."""
    con = sqlite3.connect(MIRROR / "qbreader.sqlite")
    qids, out = list(qids), {}
    for i in range(0, len(qids), 900):
        chunk = qids[i:i + 900]
        marks = ",".join("?" * len(chunk))
        for qid, q in con.execute(f"select id, question from tossups where id in ({marks})", chunk):
            out[qid] = q or ""
        for qid, lead, parts in con.execute(f"select id, leadin, parts from bonuses where id in ({marks})", chunk):
            out[qid] = " ".join([lead or ""] + (json.loads(parts) if parts else []))
    return out


def someone_elses(phrase):
    """ "coetzee s the master of petersburg": another creator's work, named
    by its creator's possessive. It points toward the owner as a clue."""
    t = phrase.split()
    return len(t) >= 3 and t[1] == "s"


def classify(keys, qids_of, work_names):
    """Set k["form"] ("title" / "clue") and k["title_share"] on each key.
    qids_of: phrase -> question ids; work_names: names of work answerlines."""
    parsed = {q: Question(r) for q, r in raw_texts({q for qs in qids_of.values() for q in qs}).items()}
    for k in keys:
        marked = informative = 0
        for q in qids_of[k["phrase"]]:
            m, n = parsed[q].occurrences(k["phrase"]) if q in parsed else (0, 0)
            marked, informative = marked + m, informative + n
        if someone_elses(k["phrase"]):
            k["title_share"], k["form"] = None, "clue"
        elif informative:
            share = marked / informative
            k["title_share"] = round(share, 2)
            k["form"] = "title" if share >= TITLE_SHARE else "clue"
        else:
            k["title_share"] = None
            k["form"] = "title" if k["phrase"] in work_names else "clue"


def _selftest():
    cases = [
        ("space oddity", 'He wrote "Space Oddity" and sang', (1, 1)),
        ("i m an alligator", 'opened with "I\'m an alligator."', (0, 1)),
        ("well tempered", "wrote <i>The Well-Tempered Clavier</i>.", (1, 1)),
        ("jareth", "He played Jareth in <i>Labyrinth</i>.", (0, 1)),
        ("nessun dorma", 'the aria "Nessun dorma" is sung', (1, 1)),
        ("jesu joy of man s desiring", "the chorale \"Jesu, Joy of Man's Desiring\"", (1, 1)),
        ("planet earth is blue", 'observes that "planet earth is blue and"', (0, 1)),
        ("jareth", "He played Jareth in Labyrinth.", (0, 0)),
        ("the prestige", "Nikola Tesla in <em>The Prestige</em>", (1, 1)),
        ("nikola tesla in the prestige", "Nikola Tesla in <em>The Prestige</em>", (0, 1)),
    ]
    bad = 0
    for ph, raw, want in cases:
        got = occurrences(ph, raw)
        if got != want:
            bad += 1
            print(f"FAIL {ph!r} in {raw!r}: {got} != {want}")
    for ph, want in (("coetzee s the master of petersburg", True), ("jesu joy of man s desiring", False)):
        if someone_elses(ph) != want:
            bad += 1
            print(f"FAIL someone_elses({ph!r}) != {want}")
    print(f"{len(cases) + 2 - bad}/{len(cases) + 2} pass")
    return bad


if __name__ == "__main__":
    raise SystemExit(_selftest())
