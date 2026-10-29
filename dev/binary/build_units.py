"""Step 0: materialise every clue unit with its vector, text and answer.

Reads mirror/embeddings.sqlite (sentence + bonus_part rows, leadins
excluded) and mirror/qbreader.sqlite, writes:
    out/vecs.npy    N x 1024 fp16, L2-normalised (as stored)
    out/units.pkl   column dict, row-aligned with vecs.npy

Vectors whose question is no longer in the mirror are dropped.

Usage: python dev/binary/build_units.py
"""
import json
import re
import sqlite3
import time

import numpy as np

from common import MIRROR, OUT, save
from lib.pipeline.parse import split_sentences

GIVEAWAY = re.compile(r"\bfor (10|ten) points\b|\bftp\b", re.I)


def main():
    t0 = time.time()
    q = sqlite3.connect(MIRROR / "qbreader.sqlite")
    tossups = {r[0]: r[1:] for r in q.execute(
        "select id, question_sanitized, answer_sanitized, category, subcategory, "
        "set_name, set_year, difficulty, alternate_subcategory from tossups")}
    bonuses = {r[0]: r[1:] for r in q.execute(
        "select id, parts_sanitized, answers_sanitized, category, subcategory, "
        "set_name, set_year, difficulty, alternate_subcategory from bonuses")}

    e = sqlite3.connect(MIRROR / "embeddings.sqlite")
    n = e.execute("select count(*) from embeddings where kind in ('sentence','bonus_part') "
                  "and part >= 0").fetchone()[0]
    vecs = np.empty((n, 1024), dtype=np.float16)
    cols = {k: [] for k in ("kind", "qid", "part", "nparts", "text", "answer",
                            "category", "subcategory", "alt", "set", "year", "diff", "giveaway")}
    split_cache = {}
    i = 0
    for kind, qid, part, blob in e.execute(
            "select kind, id, part, vector from embeddings where kind in "
            "('sentence','bonus_part') and part >= 0 order by kind, id, part"):
        if kind == "sentence":
            row = tossups.get(qid)
            if row is None:
                continue
            sents = split_cache.get(qid)
            if sents is None:
                split_cache.clear()          # rows arrive grouped by id
                sents = split_cache[qid] = split_sentences(row[0])
            if part >= len(sents):
                continue
            text, answer, nparts = sents[part], row[1], len(sents)
            k = 0
        else:
            row = bonuses.get(qid)
            if row is None:
                continue
            parts, answers = json.loads(row[0]), json.loads(row[1])
            if part >= len(parts) or part >= len(answers):
                continue
            text, answer, nparts = parts[part], answers[part], len(parts)
            k = 1
        vecs[i] = np.frombuffer(blob, dtype=np.float16)
        cols["kind"].append(k); cols["qid"].append(qid); cols["part"].append(part)
        cols["nparts"].append(nparts); cols["text"].append(text); cols["answer"].append(answer)
        cols["category"].append(row[2]); cols["subcategory"].append(row[3]); cols["alt"].append(row[7])
        cols["set"].append(row[4]); cols["year"].append(row[5] or 0)
        cols["diff"].append(row[6] or 0)
        cols["giveaway"].append(bool(k == 0 and GIVEAWAY.search(text)))
        i += 1
    vecs = vecs[:i]
    np.save(OUT / "vecs.npy", vecs)
    for k in ("kind", "part", "nparts", "year", "diff"):
        cols[k] = np.array(cols[k], dtype=np.int32)
    cols["giveaway"] = np.array(cols["giveaway"], dtype=bool)
    save("units.pkl", cols)
    print(f"{i} units ({n - i} dropped) in {time.time() - t0:.0f}s")


if __name__ == "__main__":
    main()
