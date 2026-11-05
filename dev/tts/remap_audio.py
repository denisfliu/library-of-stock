"""remap_audio.py — carry existing audio over to re-issued question ids.

A set we imported from quizbowlpackets.com (`qbmirror import-packets`) gets
replaced by qbreader's copy once qbreader publishes it, and qbreader's
questions have different ids. `qbmirror sync` records old_id -> new_id for
every surviving question in the mirror's `id_remap` table (exact text match,
or a light edit with the same answer). This script copies each old id's
.opus + sidecar to the new id's path in out/, so the generator's
skip-existing check leaves those questions alone and the uploader publishes
them under the new ids. Only questions with no remap (new or rewritten)
get synthesized.

Run it on the TTS machine AFTER `qbmirror sync` and BEFORE gen_tts.py:
  python remap_audio.py --db PATH/TO/mirror.sqlite            # local out/ only
  python remap_audio.py --db PATH/TO/mirror.sqlite --from-hf  # fetch missing old files
  python remap_audio.py ... --dry-run
--from-hf downloads an old file from the public HF dataset when this
machine's out/ doesn't hold it (e.g. it was generated elsewhere).
Idempotent: a new id whose .opus already exists is skipped. Fuzzy-matched
items keep the old text in their sidecar; `verify_tts.py --no-asr --requeue`
flags any whose text has drifted enough to need a re-take.
"""
import argparse
import shutil
import sqlite3
import sys
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from ttscorpus import DB, HF_BASE, out_path


def _fetch(rel: str, dest: Path) -> bool:
    try:
        with urllib.request.urlopen(f"{HF_BASE}/{rel}", timeout=60) as r:
            data = r.read()
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return False
        raise
    tmp = dest.with_name(dest.name + ".tmp")
    tmp.write_bytes(data)
    tmp.rename(dest)
    return True


def remap_one(kind: str, old: str, new: str, from_hf: bool) -> str:
    """Returns 'skip' (new already present), 'copy', 'fetch', or 'missing'."""
    dst = out_path(kind, new)
    if dst.exists():
        return "skip"
    src = out_path(kind, old)
    dst.parent.mkdir(parents=True, exist_ok=True)
    # Sidecar first, .opus last: a present .opus is the resume key and must
    # always imply a present sidecar (same invariant as gen_tts.write_sidecar).
    if src.exists():
        if src.with_suffix(".json").exists():
            shutil.copyfile(src.with_suffix(".json"), dst.with_suffix(".json"))
        shutil.copyfile(src, dst)
        return "copy"
    if from_hf:
        rel = f"{kind}/{old[-2:]}/{old}"
        if _fetch(f"{rel}.opus", dst.with_name(dst.name + ".dl")):
            _fetch(f"{rel}.json", dst.with_suffix(".json"))
            dst.with_name(dst.name + ".dl").rename(dst)
            return "fetch"
    return "missing"


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--db", type=Path, default=DB,
                    help="mirror holding the id_remap table (default: ttscorpus.DB)")
    ap.add_argument("--from-hf", action="store_true",
                    help="download old files missing from this machine's out/")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    conn = sqlite3.connect(args.db)
    try:
        rows = conn.execute("SELECT kind, old_id, new_id FROM id_remap "
                            "WHERE kind = 'tossups' ORDER BY set_name, old_id").fetchall()
    except sqlite3.OperationalError:
        rows = []          # no set has been replaced yet
    if args.dry_run:
        have = sum(out_path(k, o).exists() for k, o, _ in rows)
        done = sum(out_path(k, n).exists() for k, _, n in rows)
        print(f"{len(rows):,} remapped tossups; {done:,} already at the new id, "
              f"{have:,} old files present locally")
        return
    counts = {}
    for kind, old, new in rows:
        outcome = remap_one(kind, old, new, args.from_hf)
        counts[outcome] = counts.get(outcome, 0) + 1
    print(f"{len(rows):,} remapped tossups: " +
          ", ".join(f"{k} {v:,}" for k, v in sorted(counts.items())))


if __name__ == "__main__":
    main()
