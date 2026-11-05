"""ttscorpus — torch-free corpus helpers shared by gen_tts, verify_tts, and
queue_db: the worklist (which questions to synthesize), chunk splitting, and the
output-path layout. Kept free of torch/numpy so the queue can be claimed over SSH
without paying a multi-second model import on every call.
"""
import os
import re
import sys
from pathlib import Path

try:
    from ttsclean import clean   # single source of truth for guide/note stripping
except ModuleNotFoundError:      # repo checkout: it lives in lib/audio/, not beside us
    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "lib" / "audio"))
    from ttsclean import clean

WORK = Path.home() / "los_tts"
# LOS_TTS_DB points a machine at an existing mirror (e.g. the repo's
# mirror/qbreader.sqlite on the Mac) instead of a copy under WORK.
DB = Path(os.environ.get("LOS_TTS_DB") or WORK / "qbreader.sqlite")
OUT = WORK / "out"
DIFFS = (7, 8, 9)
# Sets voiced in full regardless of difficulty, chosen by name (Nov 2026: the
# five post-2026-Nationals sets imported from quizbowlpackets.com).
VOICE_SETS = ("2026 ACF Fall", "2026 PARAGONE", "2026 NEET", "2026 Notepad++",
              "2026 VOPS")
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

def scope_where():
    """(SQL WHERE clause, params) selecting the in-scope tossups: every DIFFS
    tossup plus every tossup of a VOICE_SETS set, whatever its difficulty."""
    marks = lambda xs: ",".join("?" * len(xs))
    clause = f"difficulty IN ({marks(DIFFS)})"
    if VOICE_SETS:
        clause = f"({clause} OR set_name IN ({marks(VOICE_SETS)}))"
    return clause, (*DIFFS, *VOICE_SETS)

def worklist(conn):
    """(kind, qid, cleaned_text) for every in-scope tossup (scope_where), id-ordered.
    The canonical set of items every worker and the queue agree on.
    Tossups only since July 20, 2026 — bonuses were dropped from scope (the
    reader only plays tossup audio; cutting them halved the remaining run).
    The ~15k bonus files generated before the cut stay on HF and in the
    manifest; out_path stays kind-generic so they remain addressable."""
    items = []
    where, params = scope_where()
    q = f"SELECT id, question_sanitized FROM tossups WHERE {where} ORDER BY id"
    for qid, text in conn.execute(q, params):
        items.append(("tossups", qid, clean(text)))
    return items

HF_BASE = "https://huggingface.co/datasets/uild42/qb-audio/resolve/main"

def published_ids(kind="tossups"):
    """Ids already in the published HF audio_index.json, or None if it can't be
    fetched. Lets a machine whose out/ lacks other machines' files skip what's
    already published instead of regenerating it."""
    import json, urllib.request
    try:
        with urllib.request.urlopen(f"{HF_BASE}/audio_index.json", timeout=60) as r:
            return set(json.loads(r.read()).get(kind, []))
    except Exception:
        return None

def out_path(kind, qid):
    # Shard on the LAST two hex chars (the ObjectId counter — uniform), not the
    # first two: every qbreader id starts with "62" (2022 creation timestamp),
    # which funneled all files into one directory and hit HF's 10k/dir limit.
    return OUT / kind / qid[-2:] / f"{qid}.opus"
