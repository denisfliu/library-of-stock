"""Text cleaning for TTS reading of quizbowl questions.

Handles three bracket/paren conventions, verified against the mirror:
  - moderator directions  [emphasize] [read slowly] [pause]   -> remove
  - pronunciation guides   ("kun-doo-REE")  SUR [sir]          -> remove guide,
                                                                  keep real word
  - editorial insertions   hat[ing]  "[his]"  "[this concept]" -> keep text,
                                                                  drop brackets
The distinguishing tells: quotes mark paren guides; a bracket ATTACHED to a
word (no space) completes it; a SPACED bracket is a guide unless its content
starts with a pronoun/demonstrative/article/suffix (then it's editorial).
"""
import re

# ("...") quoted parenthetical pronunciation guide
PAREN_GUIDE = re.compile(r'\s*\(["“][^)]*["”]\)')

DIRECTIONS = {
    'emphasize', 'emphasized', 'read slowly', 'read quickly', 'read fast',
    'slowly', 'quickly', 'slow', 'pause', 'beat', 'read carefully',
    'editor', "editor's note", 'moderator note',
}
# bracket content that is editorial (KEEP the words) rather than a guide
KEEP_START = re.compile(
    r'^(this|that|these|those|his|her|hers|him|he|she|it|its|they|their|them|'
    r'the|a|an|and|or|s|es|ed|ing|d|n|to|of|in)\b', re.I)


def _bracket(m):
    pre = m.group(1)          # the char immediately before '[' ('' at start)
    content = m.group(2).strip()
    low = content.lower()
    if low in DIRECTIONS:                       # stage direction -> drop
        return pre
    if pre and not pre.isspace():               # attached: hat[ing] -> hating
        return pre + content
    if KEEP_START.match(low):                   # editorial insertion -> keep
        return pre + content
    return pre.rstrip() if pre else pre         # pronunciation guide -> drop it


BRACKET = re.compile(r'(^|.)\[([^\]]{1,40})\]')


def clean(text: str) -> str:
    text = PAREN_GUIDE.sub('', text)
    text = BRACKET.sub(_bracket, text)
    text = text.replace('(*)', ' ')
    return re.sub(r'\s+', ' ', text).strip()


if __name__ == '__main__':
    cases = [
        ('action is controlled by binding to SUR [sir], part of an', 'guide'),
        ('recount his travels despite "hat[ing] traveling', 'merge'),
        ('An Analysis of [this concept]" that identified', 'keep'),
        ('color of this substance can be attributed [emphasize] not to', 'direction'),
        ('kenduri ("kun-doo-REE") is conducted', 'paren-guide'),
        ('the notes [read slowly] "A [pause] A G-sharp E', 'directions'),
        ('speaker "stop[s] somewhere waiting"', 'merge-s'),
    ]
    for t, tag in cases:
        print(f'[{tag}]')
        print('  in :', t)
        print('  out:', clean(t))
