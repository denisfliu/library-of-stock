"""verify_tts.py — backfill QA over existing TTS output, run on MSL.

Two independent reasons to regenerate an already-made file:
  (1) TEXT CHANGED: the question's clean+chunk text differs from what the file
      was made with (e.g. the new abbreviation expansion, or a chunk-split change).
      Deterministic — no ASR needed; compared against the sidecar's stored chunk
      texts (pre-sidecar files have none, so they always regenerate).
  (2) CLIP/BABBLE: a chunk fails the ttsverify ASR gate (mangled first word or
      runaway). Only files that survived (1) pay for ASR.

Deleting a flagged file's .opus + .json lets gen_tts's skip-existing resume
regenerate it with the fixed cleaner and the gate. Default is --dry-run (report
only, with examples) so the flag rate can be sanity-checked before mass deletion.

Usage (MSL):
  ~/venvs/chatterbox-tts/bin/python verify_tts.py               # dry-run report
  ~/venvs/chatterbox-tts/bin/python verify_tts.py --limit 300   # sample
  ~/venvs/chatterbox-tts/bin/python verify_tts.py --apply       # delete flagged
"""
import argparse
import json
import sqlite3
import subprocess
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ttsverify
from ttscorpus import worklist, chunk_text, out_path, DB

SR = 24000    # opus was encoded at model sr; decode at a fixed rate for ASR


def decode_opus(path):
    r = subprocess.run(
        ["ffmpeg", "-hide_banner", "-loglevel", "error", "-i", str(path),
         "-f", "f32le", "-ac", "1", "-ar", str(SR), "pipe:1"], capture_output=True)
    if r.returncode != 0:
        raise RuntimeError(r.stderr.decode(errors="replace")[:200])
    return np.frombuffer(r.stdout, dtype="<f4")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0, help="check only the first N existing files")
    ap.add_argument("--apply", action="store_true", help="delete flagged files (default: dry-run)")
    args = ap.parse_args()

    conn = sqlite3.connect(DB)
    items = [(k, qid, chunk_text(text)) for k, qid, text in worklist(conn)]
    existing = [(k, qid, ch) for k, qid, ch in items if out_path(k, qid).exists()]
    if args.limit:
        existing = existing[: args.limit]
    print(f"{len(existing):,} existing files to check", flush=True)

    wm = None
    changed, clipped, ok = [], [], 0
    for n, (kind, qid, chunks) in enumerate(existing, 1):
        path = out_path(kind, qid)
        sc = path.with_suffix(".json")
        stored = None
        if sc.exists():
            try:
                stored = json.loads(sc.read_text(encoding="utf-8")).get("texts")
            except Exception:
                stored = None
        if stored != chunks:                 # (1) text changed (or no sidecar)
            changed.append((kind, qid, "no-sidecar" if stored is None else "text-changed"))
        else:                                # (2) ASR gate on unchanged files
            if wm is None:
                wm = ttsverify.load_whisper()
            try:
                w = decode_opus(path)
            except Exception as e:
                clipped.append((kind, qid, f"decode-error: {e}")); continue
            spans = json.loads(sc.read_text(encoding="utf-8"))["chunks"]
            bad = None
            for i, (a, b) in enumerate(spans):
                seg = w[int(a * SR): int(a * SR) + int(3.0 * SR)]
                words = ttsverify.transcribe(wm, seg, SR)
                heard = words[0][0] if words else ""
                if not ttsverify.first_word_ok(heard, ttsverify.first_content_word(chunks[i])):
                    bad = f"chunk{i} {chunks[i][:30]!r} heard {heard!r}"
                    break
            if bad:
                clipped.append((kind, qid, bad))
            else:
                ok += 1
        if n % 200 == 0:
            print(f"  ...{n:,}/{len(existing):,}  changed={len(changed)} clipped={len(clipped)} ok={ok}",
                  flush=True)

    flagged = changed + clipped
    print(f"\n{'APPLY' if args.apply else 'DRY-RUN'}: {len(existing):,} checked | "
          f"{len(changed):,} text-changed | {len(clipped):,} clipped/babble | {ok:,} ok | "
          f"{len(flagged):,} to regenerate ({len(flagged)/max(1,len(existing))*100:.1f}%)", flush=True)
    print("\nsample clip/babble flags:")
    for kind, qid, why in clipped[:20]:
        print(f"  {kind}/{qid}: {why}")

    if args.apply:
        for kind, qid, _ in flagged:
            p = out_path(kind, qid)
            p.unlink(missing_ok=True)
            p.with_suffix(".json").unlink(missing_ok=True)
        print(f"\ndeleted {len(flagged):,} files — rerun gen_tts to regenerate", flush=True)


if __name__ == "__main__":
    main()
