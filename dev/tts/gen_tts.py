"""gen_tts.py — Chatterbox TTS generation for the reader, run on MSL (4090).

Reads the qbreader mirror, synthesizes every diff 7-9 tossup and bonus with
Chatterbox, encodes to Opus 24k mono, and writes to
  out/{tossups,bonuses}/{qid[:2]}/{qid}.opus
Sharded by the ObjectId's first 2 hex chars (256 buckets) to stay well under
HF's per-folder file limit. Resumable: existing files are skipped, so it can
be killed and relaunched freely.

Text cleaning strips pronunciation guides ("kun-doo-REE") / SUR [sir] and
moderator directions [emphasize]/[read slowly]/[pause] while keeping editorial
insertions (hat[ing]->hating, "[this concept]", "[his]"). Bonuses are read
verbatim: leadin + parts, no injected "for 10 points each".

Usage (under tmux):
  ~/venvs/chatterbox-tts/bin/python gen_tts.py            # generate all
  ~/venvs/chatterbox-tts/bin/python gen_tts.py --limit 20 # smoke test
"""
import argparse
import json
import re
import sqlite3
import subprocess
import sys
import time
from pathlib import Path

import numpy as np
import torch

WORK = Path.home() / "los_tts"
DB = WORK / "qbreader.sqlite"
OUT = WORK / "out"
DIFFS = (7, 8, 9)
GAP = 0.12   # inter-sentence silence, seconds

# ---------- text cleaning (mirrors scratchpad/ttsclean.py) ----------
PAREN_GUIDE = re.compile(r'\s*\(["“][^)]*["”]\)')
DIRECTIONS = {
    'emphasize', 'emphasized', 'read slowly', 'read quickly', 'read fast',
    'slowly', 'quickly', 'slow', 'pause', 'beat', 'read carefully',
    'editor', "editor's note", 'moderator note',
}
KEEP_START = re.compile(
    r'^(this|that|these|those|his|her|hers|him|he|she|it|its|they|their|them|'
    r'the|a|an|and|or|s|es|ed|ing|d|n|to|of|in)\b', re.I)
BRACKET = re.compile(r'(^|.)\[([^\]]{1,40})\]')

def _bracket(m):
    pre, content = m.group(1), m.group(2).strip()
    low = content.lower()
    if low in DIRECTIONS:
        return pre
    if pre and not pre.isspace():
        return pre + content
    if KEEP_START.match(low):
        return pre + content
    return pre.rstrip() if pre else pre

def clean(text: str) -> str:
    text = PAREN_GUIDE.sub('', text or '')
    text = BRACKET.sub(_bracket, text)
    text = text.replace('(*)', ' ')
    return re.sub(r'\s+', ' ', text).strip()

def sentences(t):
    return [p.strip() for p in re.split(r"(?<=[.!?])\s+(?=[\"'A-Z0-9(])", t) if p.strip()]

# ---------- worklist ----------
def worklist(conn):
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

def encode_opus(wav_f32, sr, path):
    """Pipe raw float32 PCM to ffmpeg -> Opus 24k mono .opus (ogg)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".opus.tmp")
    # -f ogg: the .tmp name has no muxer-recognized extension, so name the
    # container explicitly (Opus rides in Ogg).
    p = subprocess.run(
        ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
         "-f", "f32le", "-ar", str(sr), "-ac", "1", "-i", "pipe:0",
         "-c:a", "libopus", "-b:a", "24k", "-ac", "1", "-f", "ogg", str(tmp)],
        input=wav_f32.astype("<f4").tobytes(), capture_output=True)
    if p.returncode != 0:
        raise RuntimeError("ffmpeg: " + p.stderr.decode(errors="replace")[:300])
    tmp.rename(path)   # atomic: a half-written file never looks "done"

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0, help="stop after N new files (smoke test)")
    args = ap.parse_args()

    from chatterbox.tts import ChatterboxTTS
    print("loading Chatterbox...", flush=True)
    model = ChatterboxTTS.from_pretrained(device="cuda")
    sr = model.sr

    conn = sqlite3.connect(DB)
    items = worklist(conn)
    total = len(items)
    done0 = sum(1 for k, qid, _ in items if out_path(k, qid).exists())
    print(f"worklist: {total:,} items, {done0:,} already done, "
          f"{total - done0:,} to go", flush=True)

    made = 0
    t_start = time.time()
    audio_secs = 0.0
    for i, (kind, qid, text) in enumerate(items):
        path = out_path(kind, qid)
        if path.exists():
            continue
        if not text:
            continue
        try:
            chunks = []
            for sent in sentences(text):
                wav = model.generate(sent)
                chunks.append(wav.squeeze(0).cpu().numpy())
                chunks.append(np.zeros(int(sr * GAP), dtype=np.float32))
            if not chunks:
                continue
            full = np.concatenate(chunks)
            encode_opus(full, sr, path)
            made += 1
            audio_secs += len(full) / sr
        except Exception as e:
            print(f"  ERROR {kind}/{qid}: {e}", flush=True)
            continue

        if made % 25 == 0:
            el = time.time() - t_start
            rtf = audio_secs / el if el else 0
            rate = made / el * 3600 if el else 0
            remaining = (total - done0 - made)
            eta_h = remaining / rate * 1 if rate else 0
            print(f"[{time.strftime('%H:%M:%S')}] made {made:,} "
                  f"({done0 + made:,}/{total:,})  {rtf:.1f}x realtime  "
                  f"{rate:.0f}/hr  ETA {eta_h/24:.1f}d", flush=True)

        if args.limit and made >= args.limit:
            print(f"hit --limit {args.limit}", flush=True)
            break

    print(f"DONE this run: made {made:,} files in {(time.time()-t_start)/3600:.1f}h", flush=True)

if __name__ == "__main__":
    main()
