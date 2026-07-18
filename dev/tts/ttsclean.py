"""Text cleaning for TTS reading of quizbowl questions. Single source of
truth — gen_tts.py imports `clean` from here.

Removes three kinds of non-spoken annotations, in either () or [] delimiters:
  - moderator notes:      [Note to moderator: ...] (Moderator's Note: ...)
  - moderator directions: (read slowly) [emphasize] (pause) (end read slowly)
  - pronunciation guides:  ("kun-doo-REE")  Grignard (green-YARR)  SUR [sir]
while KEEPING (reading): notes addressed to players/readers — [Note to
players: Two answers required] — real parentheticals — (II), (1710),
(After Fragonard), (The Banana Boat Song), (log n) — and editorial bracket
insertions — hat[ing] -> hating, "[this concept]", "[his]".

Moderator-vs-player note distinction: a note *to the moderator* is an
operator instruction and is dropped; a note *to players/readers* is
information the answerer needs and is read.

Detection (calibrated on the mirror, diff 7-9):
  - a direction = the content contains a known stage-direction keyword.
  - a phonetic guide = content is letters/hyphens/apostrophes only, has a
    hyphen, no digits, AND shows a 2+ letter ALL-CAPS stressed syllable
    (YARR / NOY / KRAHL) — the tell real hyphenated content lacks. Quoted
    parens ("...") are always guides (quizbowl convention), stress-caps or not.
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

def _is_guide(c):
    return bool(DIR_RE.search(c)) or _is_phonetic(c)

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
PAREN = re.compile(r'\s*\(([^)]{1,40})\)')
BRACKET = re.compile(r'(^|.)\[([^\]]{1,40})\]')

def _paren(m):
    return '' if _is_guide(m.group(1)) else m.group(0)

def _bracket(m):
    pre, content = m.group(1), m.group(2).strip()
    if PLAYER_NOTE.match(content):                 # note to players/readers -> keep+read
        return pre + content
    if _is_guide(content):                         # direction or phonetic -> drop
        return pre.rstrip() if pre else pre
    if pre and not pre.isspace():                  # attached: hat[ing] -> hating
        return pre + content
    if KEEP_START.match(content.lower()):          # editorial insertion -> keep
        return pre + content
    return pre.rstrip() if pre else pre            # spaced unknown (e.g. SUR [sir]) -> drop

def clean(text: str) -> str:
    text = MOD_NOTE.sub('', text or '')            # bracketed moderator notes -> drop
    text = MOD_NOTE_BARE.sub(' ', text)            # bare "Note to moderator: ..." -> drop
    text = QUOTED_PAREN.sub('', text)
    text = PAREN.sub(_paren, text)
    text = BRACKET.sub(_bracket, text)
    text = text.replace('(*)', ' ')
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
    ]
    KEEP = [
        ('Henry (II) was king', 'Henry (II) was king'),
        ('born in (1710) to', 'born in (1710) to'),
        ('the painting (After Fragonard) hangs', 'the painting (After Fragonard) hangs'),
        ('sang (The Banana Boat Song) live', 'sang (The Banana Boat Song) live'),
        ('complexity (log n) time', 'complexity (log n) time'),
        ('despite "hat[ing] traveling"', 'despite "hating traveling"'),
        ('An Analysis of [this concept]" that', 'An Analysis of this concept" that'),
        ('[Note to players: Two answers required] Name these', 'Note to players: Two answers required Name these'),
        ('[Note to reader: emojis are spelled out] Name this', 'Note to reader: emojis are spelled out Name this'),
    ]
    ok = 0; bad = 0
    for src, want in STRIP + KEEP:
        got = clean(src)
        good = got == want
        ok += good; bad += (not good)
        print(('ok  ' if good else 'BAD ') + repr(src) + '\n     -> ' + repr(got)
              + ('' if good else '\n   want ' + repr(want)))
    print(f'\n{ok} ok, {bad} bad')
