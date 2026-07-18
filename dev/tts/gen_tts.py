"""gen_tts.py — Chatterbox TTS generation for the reader, run on MSL (4090).

Reads the qbreader mirror, synthesizes every diff 7-9 tossup and bonus with
Chatterbox, encodes to Opus 24k mono, and writes to
  out/{tossups,bonuses}/{qid[:2]}/{qid}.opus
plus a per-question sidecar {qid}.json with per-chunk [start_s, end_s]
audio offsets and the chunk texts (synthesis is chunk-by-chunk, so offsets
are exact — this is what maps a buzz's audio time to a text position).
Sharded by the ObjectId's first 2 hex chars (256 buckets) to stay well under
HF's per-folder file limit. Resumable: existing files are skipped, so it can
be killed and relaunched freely.

Text cleaning (ttsclean) strips pronunciation guides ("kun-doo-REE") / SUR [sir]
and moderator directions [emphasize]/[read slowly]/[pause], keeps editorial
insertions (hat[ing]->hating), and expands title abbreviations (Mrs.->Missus,
Dr.->Doctor, St.->Saint) so they read correctly and don't trip the sentence
splitter. Bonuses are read verbatim: leadin + parts, no "for 10 points each".

Chunk 0 (the question's audible start) passes through the ttsverify ASR gate
(whisper-tiny): a mangled first word (Chatterbox's attack-clip) or a runaway is
re-rolled, and the final retry escalates to *priming* (synthesize with a
sacrificial word, cut it off at the ASR word boundary) which reliably absorbs a
stubborn attack-clip. Chunks 1+ get only the cheap duration-runaway check — whisper
on every chunk saturates the GPU and cancels the two-stream speedup; the post-run
whisperX pass is the exhaustive mid-question clip net.

Usage (under tmux):
  gen_tts.py                       # local: this machine's full worklist, skip-existing
  gen_tts.py --queue               # fleet: claim from the queue this machine hosts
  gen_tts.py --queue --queue-host msl   # fleet: claim from the queue on MSL (over ssh)
  gen_tts.py --limit 20            # smoke test
(--shard i/n still exists for static splitting, but the queue is the way to span
 machines — each has its own GPU, unlike two streams sharing one.)
"""
import argparse
import json
import socket
import sqlite3
import subprocess
import sys
import time
from pathlib import Path

import numpy as np
import torch

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ttsverify            # ASR gate (shared with verify_tts.py)
import ttsqueue             # cross-machine work queue (claim/complete)
from ttscorpus import DB, OUT, worklist, chunk_text, out_path

GAP = 0.12          # inter-sentence silence, seconds
RETRIES = 3         # regenerate a chunk this many times if it runs away

# Chatterbox sampling params (settled July 2026 by A/B): default voice, no
# reference clip (cloning sounded worse). exaggeration 0.5 read best; the
# lower temperature + higher repetition_penalty cut runaway-glitch odds.
PARAMS = dict(exaggeration=0.5, cfg_weight=0.5, temperature=0.7, repetition_penalty=1.3)

def write_sidecar(opus_path, spans, texts):
    """{qid}.json: per-chunk [start_s, end_s] audio offsets + the chunk texts.
    Written before the .opus lands — the .opus is the resume key, so a present
    .opus must always imply a present sidecar."""
    sc = opus_path.with_suffix(".json")
    sc.parent.mkdir(parents=True, exist_ok=True)
    tmp = sc.with_suffix(".json.tmp")
    tmp.write_text(json.dumps({"v": 1, "chunks": spans, "texts": texts},
                              separators=(",", ":"), ensure_ascii=False),
                   encoding="utf-8")
    tmp.rename(sc)

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
    ap.add_argument("--shard", default="", metavar="i/n",
                    help="process a disjoint slice for parallel streams, e.g. 0/2 and 1/2")
    ap.add_argument("--queue", action="store_true",
                    help="cross-machine mode: claim work from the shared queue")
    ap.add_argument("--queue-host", default="",
                    help="ssh host of the queue DB (empty = this machine hosts it)")
    ap.add_argument("--worker", default="",
                    help="worker id recorded in the queue (default: hostname)")
    ap.add_argument("--queue-batch", type=int, default=100,
                    help="items claimed per round in queue mode")
    args = ap.parse_args()

    shard_i = shard_n = None
    if args.shard:
        shard_i, shard_n = (int(x) for x in args.shard.split("/"))

    from chatterbox.tts import ChatterboxTTS
    print("loading Chatterbox + whisper-tiny...", flush=True)
    model = ChatterboxTTS.from_pretrained(device="cuda")
    sr = model.sr
    wm = ttsverify.load_whisper()

    def gen_chunk(chunk, use_asr):
        """Generate a chunk, re-rolling on failure (Chatterbox's attack-clip/babble
        is stochastic, so a fresh take usually lands clean).

        use_asr=True (chunk 0 only — the question's audible start, and where the
        reported "beginning cutoff" lives): full ttsverify gate (first word +
        duration); the FINAL attempt escalates to *priming* (prepend a sacrificial
        word, cut it off at the ASR word boundary) to absorb a stubborn attack-clip.
        Gating only chunk 0 keeps whisper off the GPU for the other ~80% of chunks —
        it saturates the GPU and cancels the two-stream speedup otherwise. Exhaustive
        mid-question clip detection is the post-run whisperX pass's job.

        use_asr=False (chunks 1+): cheap duration-runaway check only, no whisper —
        keep the shortest of RETRIES takes if all run long (the babble signature)."""
        exp = len(chunk) / 15.0            # ~150 wpm
        tol = exp * 1.8 + 2.0
        best, bestscore = None, -1e9
        for attempt in range(RETRIES):
            primed = use_asr and attempt == RETRIES - 1
            gtext = (ttsverify.PRIME + chunk) if primed else chunk
            w = model.generate(gtext, **PARAMS).squeeze(0).cpu().numpy()
            if primed:
                cut = ttsverify.cut_prime(w, sr, wm)
                if cut is None:            # priming word not found -> discard attempt
                    continue
                w = cut
            if use_asr:
                ok, score = ttsverify.verify_chunk(w, sr, chunk, wm, tol)
            else:
                ok, score = (len(w) / sr <= tol), -len(w) / sr   # duration only; shortest wins
            if ok:
                return w
            if score > bestscore:
                best, bestscore = w, score
        return best if best is not None else w

    def synth(kind, qid, text):
        """Synthesize one item to out/. Returns audio seconds on success, 0.0 if
        skipped (already exists / empty text), or None on error — the caller must
        NOT mark a None item done, so a crashed item re-queues instead of vanishing."""
        path = out_path(kind, qid)
        if path.exists() or not text:
            return 0.0
        try:
            gap = np.zeros(int(sr * GAP), dtype=np.float32)
            parts, spans, texts = [], [], []
            pos = 0   # cumulative samples, gaps included
            for idx, ch in enumerate(chunk_text(text)):
                w = gen_chunk(ch, use_asr=(idx == 0))
                spans.append([round(pos / sr, 3), round((pos + len(w)) / sr, 3)])
                texts.append(ch)
                parts.append(w)
                parts.append(gap)
                pos += len(w) + len(gap)
            if not parts:
                return 0.0
            full = np.concatenate(parts)
            write_sidecar(path, spans, texts)
            encode_opus(full, sr, path)
            return len(full) / sr
        except Exception as e:
            print(f"  ERROR {kind}/{qid}: {e}", flush=True)
            return None

    conn = sqlite3.connect(DB)
    textmap = {qid: (kind, text) for kind, qid, text in worklist(conn)}
    made = 0
    t_start = time.time()
    audio_secs = 0.0

    def progress(seen, total=None):
        el = time.time() - t_start
        rtf = audio_secs / el if el else 0
        rate = made / el * 3600 if el else 0
        tail = f"  ETA {(total - seen) / rate / 24:.1f}d" if (total and rate) else ""
        print(f"[{time.strftime('%H:%M:%S')}] made {made:,}"
              + (f" ({seen:,}/{total:,})" if total else "")
              + f"  {rtf:.1f}x realtime  {rate:.0f}/hr{tail}", flush=True)

    if args.queue:
        # Cross-machine mode: claim batches from the shared queue on --queue-host
        # (empty = this machine hosts the queue). Each qid is served to exactly one
        # worker; text is resolved from this machine's local mirror.
        worker = args.worker or socket.gethostname()
        qc = ttsqueue.Client(host=args.queue_host)
        print(f"queue mode: worker={worker!r} host={args.queue_host or 'local'} "
              f"batch={args.queue_batch}", flush=True)
        while True:
            batch = qc.claim(worker, args.queue_batch)
            if not batch:
                print("queue drained", flush=True)
                break
            done = []
            for kind, qid in batch:
                entry = textmap.get(qid)
                secs = synth(kind, qid, entry[1]) if entry else 0.0
                if secs is not None:              # made or skipped -> done; error re-queues
                    done.append((kind, qid))
                if secs:
                    made += 1
                    audio_secs += secs
                    if made % 25 == 0:
                        progress(qc.stats().get("done", 0), sum(qc.stats().values()) or None)
            qc.complete(done)
            if args.limit and made >= args.limit:
                print(f"hit --limit {args.limit}", flush=True)
                break
    else:
        # Local mode: iterate this machine's full worklist (optionally a static
        # --shard slice) and skip-existing. No coordination.
        items = worklist(conn)
        if shard_n:
            items = items[shard_i::shard_n]
            print(f"shard {shard_i}/{shard_n}: {len(items):,} items", flush=True)
        total = len(items)
        done0 = sum(1 for k, qid, _ in items if out_path(k, qid).exists())
        print(f"worklist: {total:,} items, {done0:,} already done, "
              f"{total - done0:,} to go", flush=True)
        for kind, qid, text in items:
            secs = synth(kind, qid, text)
            if secs:
                made += 1
                audio_secs += secs
                if made % 25 == 0:
                    progress(done0 + made, total)
            if args.limit and made >= args.limit:
                print(f"hit --limit {args.limit}", flush=True)
                break

    print(f"DONE this run: made {made:,} files in {(time.time()-t_start)/3600:.1f}h", flush=True)

if __name__ == "__main__":
    main()
