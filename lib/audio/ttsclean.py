"""Text cleaning for TTS reading of quizbowl questions. Single source of
truth — gen_tts.py imports `clean` from here.

Removes non-spoken annotations, in either () or [] delimiters:
  - moderator notes:      [Note to moderator: ...] (Moderator's Note: ...)
  - moderator directions: (read slowly) [emphasize] (pause) (end read slowly)
  - pronunciation guides:  ("kun-doo-REE")  Grignard (green-YARR)  SUR [sir]
                           Homais (oh-may)  fMRI [F-M-R-I]  Peles ["peh-lesh"]
while KEEPING (reading): notes addressed to players/readers — [Note to
players: Two answers required] — real parentheticals — (II), (1710),
(After Fragonard), (The Banana Boat Song), (log n) — editorial insertions —
hat[ing] -> hating, "[this concept]", "[his]" — and, crucially, editorial
SUBSTITUTIONS that stand in for a redacted answerline: "When My Brother Was
[one of these people]", "[title object]", "[blank]", "[who]", plus bracketed
chemistry/notation like [3,3] and [2+2].

Brackets DEFAULT TO KEEP. A bracket is read unless there is strong evidence it
is a guide/direction/redaction — the inverse (drop-by-default) silenced the
editorial substitutions above (the 2022 ACF Regionals TU1 "[one of these
people]" drop that motivated this). Missed edge guides read as a mild "GINS
jins" stutter; dropping a real clue word is the failure this refuses.

Guide detection (calibrated on the mirror, diff 7-9). A bracket/paren body is a
guide if any of:
  - it contains a double-quote (quizbowl phonetic convention): ["de-ronn"];
  - the content contains a known stage-direction keyword;
  - ALL-CAPS-stress phonetic: letters/hyphens/apostrophes, a hyphen, no digits,
    a 2+ letter ALL-CAPS stressed syllable (YARR / NOY / KRAHL);
  - lowercase-hyphen respelling: a single hyphenated all-lowercase token
    (oh-may, jing-duh-jen, ah-luhn-soh) — no ALL-CAPS tell, so previously leaked;
  - letter/acronym spell-out: hyphen-joined, most segments single letters
    (F-M-R-I, C-D-C-forty-five, M-O-seventeen);
  - an echo respelling: a single all-lowercase token that near-duplicates the
    word right before it (Lie [lee], SUR [sir]) — shared first letter, edit
    distance <= 1, kept tight so [his]/[they] as substitutions never match.
Bracketed [MISSING]/[REDACTED] placeholders are dropped (never voice "missing").

Moderator-vs-player note distinction: a note *to the moderator* is an operator
instruction and is dropped; a note *to players/readers* is information the
answerer needs and is read.
"""
import re

# --- moderator directions (strip in () or []): content contains one of these ---
DIR_RE = re.compile(
    r'\b(emphasi[sz]ed?|read\s+(?:slowly|quickly|fast|carefully)|slowly|quickly|'
    r'pause|beat|end\s+read|editor(?:\'s)?\s*note|moderator\s*note)\b', re.I)

# --- phonetic guide body ---
STRESS = re.compile(r'[A-Z]{2,}')                       # an all-caps stressed syllable
BODY = re.compile(r"[A-Za-z’'.\- ]+")                   # letters/hyphens/apostrophes/spaces only
def _is_phonetic(c):
    c = c.strip()
    if not c or re.search(r'\d', c):
        return False
    return '-' in c and bool(STRESS.search(c)) and bool(BODY.fullmatch(c))

# A lowercase single-token hyphenated respelling — oh-may, jing-duh-jen,
# ah-luhn-soh, chick-uhn-goon-yuh. Distinct from _is_phonetic (which keys on an
# ALL-CAPS stressed syllable) so it also catches guides written without stress
# caps, which otherwise leaked through and got read aloud (834 in the mirror).
# Single-token (no interior space) so an editorial phrase like "this two-word
# phrase" is NOT mistaken for a guide.
LOWER_RESPELL = re.compile(r"[a-z’'\-]+")
def _is_phonetic_respelling(c):
    c = c.strip().strip('"“”\'’')
    if not c or ' ' in c or '-' not in c or re.search(r'\d', c):
        return False
    return bool(LOWER_RESPELL.fullmatch(c))

# A letter/acronym spell-out guide — F-M-R-I, C-D-C-forty-five, M-O-seventeen,
# L-F-A-one, V-O-C. Hyphen-joined segments, most of them a single letter: this is
# how a hard-to-say acronym is respelled, and it echoes a token right before it.
# Editorial substitutions are never shaped like this, so dropping is safe.
def _is_letter_spellout(c):
    c = c.strip()
    segs = [s for s in c.split('-') if s]
    if len(segs) < 2 or not all(re.fullmatch(r"[A-Za-z]+", s) for s in segs):
        return False
    singles = sum(len(s) == 1 for s in segs)
    return singles >= 2 and singles * 2 >= len(segs)

def _is_guide(c):
    if '"' in c or '“' in c or '”' in c:               # any internal quote => guide
        return True
    return (bool(DIR_RE.search(c)) or _is_phonetic(c)
            or _is_phonetic_respelling(c) or _is_letter_spellout(c))

# --- echo guide: an unquoted, single-token, all-lowercase respelling of the word
# immediately before it — Lie [lee], Qing [ching], GINS [jins], SUR [sir]. The
# tell is near-identity to the preceding word (shared first letter, edit distance
# <= 1). Kept deliberately tight: a real editorial substitution ([his] after "in",
# [they] after "that") is edit-distance 2+ or a different first letter, so it
# never fires on one. Missed guides at worst read as a mild "Qing ching" stutter;
# dropping a real clue word is the failure we refuse. Needs the preceding word, so
# it lives in the sub-callbacks, not in _is_guide.
def _norm_word(s):
    return re.sub(r"[^a-z0-9]", "", s.lower())

def _lev1(a, b):
    """True iff edit distance between a and b is 0 or 1 (cheap, bounded)."""
    if a == b:
        return True
    la, lb = len(a), len(b)
    if abs(la - lb) > 1:
        return False
    if la > lb:
        a, b, la, lb = b, a, lb, la          # a is now the shorter
    i = j = edits = 0
    while i < la and j < lb:
        if a[i] == b[j]:
            i += 1; j += 1
        else:
            edits += 1
            if edits > 1:
                return False
            if la == lb:
                i += 1; j += 1               # substitution
            else:
                j += 1                        # deletion from the longer
    return True

ECHO_TOKEN = re.compile(r"[a-z’'\-]+")                  # single all-lowercase token
def _is_echo(content, prev):
    c = content.strip()
    if ' ' in c or not ECHO_TOKEN.fullmatch(c):
        return False
    cn, pn = _norm_word(c), _norm_word(prev)
    if not cn or not pn:
        return False
    return cn[:1] == pn[:1] and _lev1(cn, pn)

def _preceding_word(m):
    words = re.findall(r"[\w’'\-]+", m.string[:m.start()])
    return words[-1] if words else ""

# Literal redaction placeholders — a corrupted/redacted source question. Never
# voice the word "missing"; drop it (the question is broken regardless).
MISSING_RE = re.compile(r'^(missing|redacted|inaudible)$', re.I)

# editorial bracket content to KEEP (pronoun/demonstrative/article/suffix)
KEEP_START = re.compile(
    r'^(this|that|these|those|his|her|hers|him|he|she|it|its|they|their|them|'
    r'the|a|an|and|or|s|es|ed|ing|d|n|to|of|in)\b', re.I)

# Notes addressed to the moderator/operator (any length) -> drop. Kept
# separate because these run long, past the short () / [] handlers' cap.
MOD_NOTE = re.compile(
    r'\s*[\[(]\s*(?:notes?\s+to\s+(?:the\s+)?moderators?|moderator[’\']?s?\s+notes?)'
    r'\b[^\])]{0,240}[\])]', re.I)
# Bare (undelimited) moderator note: a leading/inline "Note to moderator: ..."
# through the end of that sentence. Moderator-only, so bare player notes stay
# read; "moderator" as a plain word (no "note to") is never matched.
MOD_NOTE_BARE = re.compile(
    r'\s*\b(?:notes?\s+to\s+(?:the\s+)?moderators?|moderator[’\']?s?\s+notes?)\b'
    r'\s*:?[^.!?]{0,240}[.!?]\s*', re.I)
# Notes addressed to players/readers -> keep and read (info for the answerer).
PLAYER_NOTE = re.compile(r'^\s*notes?\s+to\s+(?:the\s+)?(?:players?|readers?)\b', re.I)

QUOTED_PAREN = re.compile(r'\s*\(["“][^)]*["”]\)')      # always a guide
QUOTED_BRACKET = re.compile(r'\s*\[["“][^\]]*["”]\]')   # ["de-ronn"] — always a guide
PAREN = re.compile(r'\s*\(([^)]{1,40})\)')
BRACKET = re.compile(r'(^|.)\[([^\]]{1,40})\]')

# Abbreviation expansion for spoken output. Chatterbox has no lexicon, so a bare
# "Mr." reads oddly and — worse — its trailing period makes the sentence splitter
# cut "Mrs. Dalloway" into two chunks with a gap through the name. Expanding to the
# spoken form fixes pronunciation AND removes the splitter-tripping period.
# High-confidence only; ambiguous ones (Ft.=Fort/Feet) are left for the splitter
# to protect rather than risk a wrong expansion.
ABBREV = [
    (re.compile(r'\bMrs\.'), 'Missus'),
    (re.compile(r'\bMr\.'), 'Mister'),
    (re.compile(r'\bMs\.'), 'Miss'),
    (re.compile(r'\bDr\.'), 'Doctor'),
    (re.compile(r'\bMt\.'), 'Mount'),
    (re.compile(r'\bJr\.'), 'Junior'),
    (re.compile(r'\bSr\.'), 'Senior'),
    (re.compile(r'\bvs\.', re.I), 'versus'),
    (re.compile(r'\bOp\.(?=\s*\d)'), 'Opus'),          # Op. 27 -> Opus 27
    (re.compile(r'\bNo\.(?=\s*\d)'), 'Number'),        # No. 5 -> Number 5
    (re.compile(r'\bSt\.(?=\s+[A-Z])'), 'Saint'),      # St. Louis -> Saint Louis (not "Street")
]

def expand_abbrev(text: str) -> str:
    for rx, repl in ABBREV:
        text = rx.sub(repl, text)
    return text

# Poetry line-break slashes — a quoted passage like `"summer's day? / Rough winds
# do shake"` uses " / " to separate verse lines; read through it (never voice
# "slash"). Only SPACED slashes are line separators — "10/ten points", "and/or",
# "km/h", "9/11" have no surrounding spaces and are left intact. The existing
# line-end punctuation supplies the pause; a bare line break just reads on.
POETRY_SLASH = re.compile(r'\s+/+\s+')

def _paren(m):
    c = m.group(1)
    if _is_guide(c) or _is_echo(c, _preceding_word(m)):
        return ''
    return m.group(0)

def _bracket(m):
    # Default is KEEP — a bracket is read unless there's strong evidence it is a
    # guide/direction/redaction. The inverse (drop-by-default) silenced editorial
    # substitutions the answerer needs: "When My Brother Was [one of these
    # people]", "[title object]", "[blank]", "[who]", and bracketed chemistry
    # like [3,3] / [2+2]. Missed edge guides read as a mild stutter; a dropped
    # clue word is the failure we refuse.
    pre, content = m.group(1), m.group(2).strip()
    if PLAYER_NOTE.match(content):                 # note to players/readers -> keep+read
        return pre + content
    if MISSING_RE.match(content):                  # redaction placeholder -> drop
        return pre.rstrip() if pre else pre
    if _is_guide(content):                         # direction or phonetic -> drop
        return pre.rstrip() if pre else pre
    if _is_echo(content, _preceding_word(m)):      # respelling echo (SUR [sir]) -> drop
        return pre.rstrip() if pre else pre
    if pre and not pre.isspace():                  # attached: hat[ing] -> hating
        return pre + content
    return pre + content                           # editorial substitution -> keep+read

def clean(text: str) -> str:
    text = MOD_NOTE.sub('', text or '')            # bracketed moderator notes -> drop
    text = MOD_NOTE_BARE.sub(' ', text)            # bare "Note to moderator: ..." -> drop
    text = QUOTED_PAREN.sub('', text)
    text = QUOTED_BRACKET.sub('', text)            # ["de-ronn"] -> drop
    text = PAREN.sub(_paren, text)
    text = BRACKET.sub(_bracket, text)
    text = text.replace('(*)', ' ')
    text = expand_abbrev(text)
    text = POETRY_SLASH.sub(' ', text)             # verse line breaks: read through, never "slash"
    return re.sub(r'\s+', ' ', text).strip()


if __name__ == '__main__':
    STRIP = [
        ('Grignard reagents [green-YARR] add', 'Grignard reagents add'),
        ('named for Victor Grignard (green-YARR) who', 'named for Victor Grignard who'),
        ('the compound (GREEN-yar) is used', 'the compound is used'),
        ('the surname Neumann (NOY-mahn) appears', 'the surname Neumann appears'),
        ('the color [emphasize] not to', 'the color not to'),
        ('the theme (read slowly) returns', 'the theme returns'),
        ('notes (end read slowly) then', 'notes then'),
        ('kenduri ("kun-doo-REE") is', 'kenduri is'),
        ('binding to SUR [sir], part', 'binding to SUR, part'),
        ('[Note to moderator: read the answerline carefully.] The clue', 'The clue'),
        ('the county (Note to moderators: this is on a county) is large', 'the county is large'),
        ("A theme (Moderator's Note: emphasize the italics) recurs", 'A theme recurs'),
        ('This novel opens as Mrs. Dalloway buys flowers', 'This novel opens as Missus Dalloway buys flowers'),
        ('created by Dr. Seuss and Mr. Rochester', 'created by Doctor Seuss and Mister Rochester'),
        ('St. Petersburg on the Neva', 'Saint Petersburg on the Neva'),
        ('the Beethoven Op. 27 sonata', 'the Beethoven Opus 27 sonata'),
        ('Symphony No. 5 in C minor', 'Symphony Number 5 in C minor'),
        ('Martin Luther King Jr. spoke', 'Martin Luther King Junior spoke'),
        ('Mt. Everest is tall', 'Mount Everest is tall'),
        ('Ali vs. Frazier fight', 'Ali versus Frazier fight'),
        ('reads "a summer\'s day? / Rough winds do shake" here', 'reads "a summer\'s day? Rough winds do shake" here'),
        ('the line "burning bright, / In the forests" appears', 'the line "burning bright, In the forests" appears'),
        ('a stanza break "night // In what" here', 'a stanza break "night In what" here'),
        # unquoted lowercase respelling guides (were leaking, read aloud)
        ('porcelain from Jingdezhen (jing-duh-jen) inspired', 'porcelain from Jingdezhen inspired'),
        ('the pharmacist Monsieur Homais [oh-may] left', 'the pharmacist Monsieur Homais left'),
        ('worshipped by the orishas [oh-ree-shahs] here', 'worshipped by the orishas here'),
        ('advisor to John of Alencon [ah-luhn-soh] was', 'advisor to John of Alencon was'),
        # quoted-bracket guides
        ('the movement included Andre Derain ["de-ronn"] and', 'the movement included Andre Derain and'),
        # echo respellings (single lowercase token ~= preceding word)
        ('named for Lie [lee] groups', 'named for Lie groups'),
        ('the function sinc [sink] appears', 'the function sinc appears'),
        # redaction placeholder -> never voice "missing"
        ('the county [MISSING] borders', 'the county borders'),
    ]
    KEEP = [
        ('For 10/ten points, name', 'For 10/ten points, name'),   # unspaced slash -> keep
        ('this and/or that', 'this and/or that'),
        ('a speed in km/h units', 'a speed in km/h units'),
        ('Henry (II) was king', 'Henry (II) was king'),
        ('born in (1710) to', 'born in (1710) to'),
        ('the painting (After Fragonard) hangs', 'the painting (After Fragonard) hangs'),
        ('sang (The Banana Boat Song) live', 'sang (The Banana Boat Song) live'),
        ('complexity (log n) time', 'complexity (log n) time'),
        ('despite "hat[ing] traveling"', 'despite "hating traveling"'),
        ('An Analysis of [this concept]" that', 'An Analysis of this concept" that'),
        ('[Note to players: Two answers required] Name these', 'Note to players: Two answers required Name these'),
        ('[Note to reader: emojis are spelled out] Name this', 'Note to reader: emojis are spelled out Name this'),
        # editorial substitutions for a redacted answerline -> keep+read (the bug)
        ('titled When My Brother Was [one of these people].', 'titled When My Brother Was one of these people.'),
        ('Exit, pursued by [one of these animals].', 'Exit, pursued by one of these animals.'),
        ('the line "this [blank] of York."', 'the line "this blank of York."'),
        ('titled Beyond [what concept] and Evil?', 'titled Beyond what concept and Evil?'),
        ('the [title object] is gone', 'the title object is gone'),
        ('Why Do [people with this profession] Still Live', 'Why Do people with this profession Still Live'),
        ('"you women [who] called me"', '"you women who called me"'),
        # bracketed chemistry / notation is content, not a guide -> read the
        # numbers ("three three", "two plus two"); only the [] punctuation is silent
        ('a [3,3] sigmatropic rearrangement', 'a 3,3 sigmatropic rearrangement'),
        ('unlike a similar [2+2] reaction', 'unlike a similar 2+2 reaction'),
        ('name this [4+2] cycloaddition', 'name this 4+2 cycloaddition'),
        ('the [2.2.2]cryptand ligand', 'the 2.2.2cryptand ligand'),
        # editorial phrase in parens describing the answer -> keep
        ('summarized by (this two-word phrase) here', 'summarized by (this two-word phrase) here'),
        # editorial pronoun/suffix substitution -> keep (echo rule must not fire)
        ('says that he "armed [himself] against"', 'says that he "armed himself against"'),
        ('a note that "that [they] called"', 'a note that "that they called"'),
    ]
    ok = 0; bad = 0
    for src, want in STRIP + KEEP:
        got = clean(src)
        good = got == want
        ok += good; bad += (not good)
        print(('ok  ' if good else 'BAD ') + repr(src) + '\n     -> ' + repr(got)
              + ('' if good else '\n   want ' + repr(want)))
    print(f'\n{ok} ok, {bad} bad')
