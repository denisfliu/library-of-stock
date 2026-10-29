"""Shared helpers for binary-clue detection (see README.md).

A *unit* is one clue-bearing text with one answerline: a tossup sentence
(kind 0, labelled with the tossup's answer) or a bonus part (kind 1,
labelled with that part's answer). Units are stored column-wise in
out/units.pkl, row-aligned with the vectors in out/vecs.npy.
"""
import pickle
import re
import sys
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

import os

# BINARY_OUT_SUB=clauses_music runs the same pipeline on another unit set
# (out/clauses_music/); BASE_OUT always holds the sentence-level corpus.
BASE_OUT = Path(__file__).resolve().parent / "out"
OUT = BASE_OUT / os.environ["BINARY_OUT_SUB"] if os.environ.get("BINARY_OUT_SUB") else BASE_OUT
OUT.mkdir(parents=True, exist_ok=True)
MIRROR = ROOT / "mirror"

STOP = set("""a an the and or of in on at to for from by with as is was were be been being
this these that those his her its their he she it they him them who whom whose which what
one ones also after before during into over under about than then but not no nor so such
has have had do does did can could would should will shall may might must when where while
name ftp points point for10 10""".split())


def fold(s: str) -> str:
    """Lowercase, strip diacritics and punctuation, collapse whitespace."""
    s = unicodedata.normalize("NFKD", s or "")
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = s.lower().replace("&", " and ")
    s = re.sub(r"[^\w\s]", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def fold_case(s: str) -> str:
    """fold() without lowercasing: tokens align 1:1 with fold(s).split()."""
    s = unicodedata.normalize("NFKD", s or "")
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = s.replace("&", " and ")
    s = re.sub(r"[^\w\s]", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def tokens(s: str) -> list[str]:
    return fold(s).split()


_IDF = None
ALIAS_MIN_IDF = 7.0     # unit df <= ~0.09%


def alias_ok(phrase: str) -> bool:
    """Can an or/accept/prompt ALTERNATIVE be trusted as a name? Only if
    it contains at least one rare token: accept clauses carry junk like
    "anything like that" or "as he has quite a few" (Odin's answerline),
    which would otherwise "name" Odin in thousands of questions. Needs
    out/vocab.pkl (anchors.py)."""
    global _IDF
    if _IDF is None:
        v = load("vocab.pkl")
        _IDF = dict(zip(v["vocab"], v["idf"].tolist()))
    return any(_IDF.get(t, 0.0) >= ALIAS_MIN_IDF for t in phrase.split())


def save(name: str, obj) -> None:
    with open(OUT / name, "wb") as f:
        pickle.dump(obj, f, protocol=pickle.HIGHEST_PROTOCOL)


def load(name: str):
    with open(OUT / name, "rb") as f:
        return pickle.load(f)
