"""answerlines.py — Cleaning and normalizing qbreader answerlines.

Two distinct operations:

- ``clean_answerline`` turns a raw answerline (HTML or sanitized) into a
  display-worthy canonical string: "kites [accept fighter kites; ...]"
  -> "kites". Used when extracting answerlines from sets/frequency lists.

- ``normalize`` builds the *comparison key* used for matching and for
  answerline_overrides.json keys: accent-folded, lowercased, punctuation
  stripped. It reconciles common.topic_slug (accent-keeping) with
  topic_queue._slugify (accent-stripping).
"""
import re
import unicodedata

_TAG_RE = re.compile(r'<[^>]+>')
_WS_RE = re.compile(r'\s+')
_PUNCT_RE = re.compile(r'[^\w\s]', re.UNICODE)
_ARTICLE_RE = re.compile(r'^(the|a|an)\s+', re.IGNORECASE)

# Letters NFD can't fold (no combining-mark decomposition). Without
# this, "Søren" != "Soren" and the matcher misses accent variants.
_TRANSLIT = str.maketrans({
    'ø': 'o', 'Ø': 'O', 'đ': 'd', 'Đ': 'D', 'ð': 'd', 'Ð': 'D',
    'ł': 'l', 'Ł': 'L', 'æ': 'ae', 'Æ': 'AE', 'œ': 'oe', 'Œ': 'OE',
    'ß': 'ss', 'þ': 'th', 'Þ': 'Th', 'ħ': 'h', 'Ħ': 'H', 'ı': 'i',
})


def clean_answerline(raw: str) -> str:
    """Canonical display form of a raw answerline.

    Strips HTML, then cuts at the first bracketed/parenthesized clause
    ("[accept ...]", "[or ...]", "(It was written by ...)"), which is
    where qbreader answerlines keep their accept/prompt directives.
    """
    s = _TAG_RE.sub('', raw or '')
    s = s.split('[', 1)[0]
    s = s.split('(', 1)[0]
    s = _WS_RE.sub(' ', s).strip().strip(';,').strip()
    return s


def normalize(name: str) -> str:
    """Comparison key: accent-folded, lowercase, no punctuation, no
    leading article, collapsed whitespace."""
    s = unicodedata.normalize('NFD', name or '')
    s = ''.join(c for c in s if not unicodedata.combining(c))
    s = s.translate(_TRANSLIT)
    s = s.lower()
    s = _PUNCT_RE.sub(' ', s)
    s = _WS_RE.sub(' ', s).strip()
    s = _ARTICLE_RE.sub('', s)
    return s
