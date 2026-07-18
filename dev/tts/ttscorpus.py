"""ttscorpus — torch-free corpus helpers shared by gen_tts, verify_tts, and
queue_db: the worklist (which questions to synthesize), chunk splitting, and the
output-path layout. Kept free of torch/numpy so the queue can be claimed over SSH
without paying a multi-second model import on every call.
"""
import json
import re
from pathlib import Path

from ttsclean import clean   # single source of truth for guide/note stripping

WORK = Path.home() / "los_tts"
DB = WORK / "qbreader.sqlite"
OUT = WORK / "out"
DIFFS = (7, 8, 9)
MAX_CHARS = 200     # split chunks longer than this (runaway risk)
MIN_CHARS = 12      # merge chunks shorter than this (babble risk)

# Abbreviations whose trailing period must NOT be treated as a sentence end.
# Most name-titles (Mr./Mrs./Dr./St./Mt./Jr./Sr.) are already expanded away by
# ttsclean, but these survive (undelimited scholarly/list abbreviations) and would
# otherwise split a chunk mid-phrase.
_ABBR = (r"(?:etc|al|vs|Prof|Rev|Gen|Col|Capt|Lt|Sgt|Fr|Dept|Rep|Sen|Gov|"
         r"Ave|Blvd|Sts|Ph|cf|ca|fl| Mus|e\.g|i\.e|No|Op| Vol|Nos)")
_ABBR_RE = re.compile(r"\b(" + _ABBR + r")\.", re.I)
_INITIAL_RE = re.compile(r"\b([A-Z])\.")          # single-letter initials: W. H. Auden
_SPLIT_RE = re.compile(r"(?<=[.!?])\s+(?=[\"'A-Z0-9(])")

def sentences(t):
    # Shield abbreviation/initial periods, split, then restore. Prevents the
    # splitter from ending a chunk on "Mrs.", "et al.", "e.g.", or "W."
    t = _ABBR_RE.sub(lambda m: m.group(0).replace(".", "\0"), t)
    t = _INITIAL_RE.sub(r"\1\0", t)
    return [p.replace("\0", ".").strip() for p in _SPLIT_RE.split(t) if p.strip()]

# Safe chunking: merge tiny fragments (e.g. the "H." from splitting "W. H.
# Auden") and chunks ending in a lone initial, and split over-long sentences
# at clause boundaries — no chunk is a glitch magnet (too short -> babble,
# too long -> runaway).
INITIAL_END = re.compile(r'(^|\s)[A-Z]\.$')
def chunk_text(text):
    merged = []
    for s in sentences(text):
        if merged and (len(s) < MIN_CHARS or INITIAL_END.search(merged[-1]) or len(merged[-1]) < MIN_CHARS):
            merged[-1] += ' ' + s
        else:
            merged.append(s)
    chunks = []
    for s in merged:
        if len(s) <= MAX_CHARS:
            chunks.append(s); continue
        buf = ''
        for p in re.split(r'(?<=[,;:])\s+', s):
            if buf and len(buf) + len(p) + 1 > MAX_CHARS:
                chunks.append(buf); buf = p
            else:
                buf = (buf + ' ' + p).strip()
        if buf: chunks.append(buf)
    return chunks

def worklist(conn):
    """(kind, qid, cleaned_text) for every diff 7-9 tossup and bonus, id-ordered.
    The canonical set of items every worker and the queue agree on."""
    items = []
    q = "SELECT id, question_sanitized FROM tossups WHERE difficulty IN (7,8,9) ORDER BY id"
    for qid, text in conn.execute(q):
        items.append(("tossups", qid, clean(text)))
    b = "SELECT id, leadin_sanitized, parts_sanitized FROM bonuses WHERE difficulty IN (7,8,9) ORDER BY id"
    for qid, leadin, parts in conn.execute(b):
        try:
            plist = json.loads(parts) if parts else []
        except Exception:
            plist = []
        text = " ".join([clean(leadin)] + [clean(p) for p in plist]).strip()
        items.append(("bonuses", qid, text))
    return items

def out_path(kind, qid):
    return OUT / kind / qid[:2] / f"{qid}.opus"
