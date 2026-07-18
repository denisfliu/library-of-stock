"""A/B bench for the phoneme-attack-clipping mitigation + verification-gate
timing. Runs on MSL alongside the production generator (VRAM allows it).

Subcommands:
  bench      - generate baseline vs primed takes for test texts, save wavs +
               metrics.jsonl into ~/los_tts/ab3/
  scan       - sample existing sidecar-bearing opus files, whisper the start of
               every chunk, report first-word clip rate + per-chunk ASR cost
  throughput - generate a fixed chunk in a loop for N seconds (second-stream
               contention probe; compare production gen.log rate during window)
"""
import json, re, subprocess, sys, time, wave
from pathlib import Path
import numpy as np

WORK = Path.home() / "los_tts"
AB = WORK / "ab3"
PARAMS = dict(exaggeration=0.5, cfg_weight=0.5, temperature=0.7, repetition_penalty=1.3)
PRIME = "Okay."          # sacrificial priming sentence, clipped out afterwards

TEXTS = [
    ("grignard",  "Grignard reagents add twice to esters to form tertiary alcohols."),
    ("phthalic",  "Phthalic anhydride condenses with resorcinol to form fluorescein."),
    ("openletter","An open letter written to this leader described atrocities in the Congo Free State."),
    ("euler",     "Euler introduced the gamma function to extend factorials."),
    ("for10",     "For 10 points, name this element with atomic number 79."),
    ("tchaik",    "Tchaikovsky's sixth symphony premiered days before his death."),
    ("governess", "She wrote about a governess at Thornfield Hall."),
    ("dalloway",  "This novel opens as Mrs. Dalloway says she will buy the flowers herself."),
]
# abbreviation-expansion A/B rides along (2 takes each)
ABBREV = [
    ("abbrev_raw",      "The party is hosted by Mr. Ramsay and Mrs. Ramsay at St. Ives."),
    ("abbrev_expanded", "The party is hosted by Mister Ramsay and Missus Ramsay at Saint Ives."),
]

def save_wav(path, w, sr):
    path.parent.mkdir(parents=True, exist_ok=True)
    x = np.clip(w, -1, 1)
    with wave.open(str(path), "wb") as f:
        f.setnchannels(1); f.setsampwidth(2); f.setframerate(sr)
        f.writeframes((x * 32767).astype("<i2").tobytes())

def to16k(w, sr):
    n16 = int(len(w) * 16000 / sr)
    return np.interp(np.arange(n16) * (sr / 16000), np.arange(len(w)), w).astype(np.float32)

def rms_frames(w, sr, frame_ms=10):
    n = int(sr * frame_ms / 1000)
    m = len(w) // n
    return np.sqrt(np.mean(w[: m * n].reshape(m, n) ** 2, axis=1)), n

def energy_cut(w, sr, speech_thr=0.02, sil_thr=0.008, min_sil_ms=100, keep_ms=80):
    """Cut point after the priming word: first >=min_sil silence run that
    follows the first speech burst; keep keep_ms of lead-in silence."""
    env, n = rms_frames(w, sr)
    sp = np.nonzero(env > speech_thr)[0]
    if not len(sp):
        return None
    i = sp[0]
    need = max(1, min_sil_ms // 10)
    run = 0
    for j in range(i + 1, min(len(env), i + 250)):   # search within 2.5 s
        if env[j] < sil_thr:
            run += 1
        else:
            if run >= need:                          # silence run ended at j
                return max(0, j * n - int(sr * keep_ms / 1000))
            run = 0
    return None

def transcribe(wm, w, sr, max_s=None):
    x = to16k(w if max_s is None else w[: int(sr * max_s)], sr)
    segs, _ = wm.transcribe(x, language="en", beam_size=1, word_timestamps=True)
    words = [wd for s in segs for wd in s.words]
    return [(wd.word.strip(), wd.start, wd.end) for wd in words]

def norm(word):
    return re.sub(r"[^a-z0-9']", "", word.lower())

def load_models():
    from chatterbox.tts import ChatterboxTTS
    from faster_whisper import WhisperModel
    print("loading chatterbox + whisper-tiny...", flush=True)
    tts = ChatterboxTTS.from_pretrained(device="cuda")
    wm = WhisperModel("tiny", device="cuda", compute_type="float16")
    return tts, wm

def bench():
    tts, wm = load_models()
    sr = tts.sr
    out = []
    jobs = [(k, t, "baseline", 3) for k, t in TEXTS] + \
           [(k, t, "primed", 3) for k, t in TEXTS] + \
           [(k, t, "baseline", 2) for k, t in ABBREV]
    for key, text, arm, takes in jobs:
        gen_text = (PRIME + " " + text) if arm == "primed" else text
        for take in range(takes):
            t0 = time.time()
            w = tts.generate(gen_text, **PARAMS).squeeze(0).cpu().numpy()
            gen_s = time.time() - t0
            t0 = time.time()
            words = transcribe(wm, w, sr)
            asr_s = time.time() - t0
            rec = dict(key=key, arm=arm, take=take, text=text, gen_s=round(gen_s, 2),
                       audio_s=round(len(w) / sr, 2), asr_s=round(asr_s, 3),
                       words=[(t, round(a, 2), round(b, 2)) for t, a, b in words[:12]])
            name = f"{key}__{arm}_t{take}"
            save_wav(AB / f"{name}.wav", w, sr)
            if arm == "primed":
                ec = energy_cut(w, sr)
                # ASR cut: end of the priming word -> keep 80 ms before next word
                ac = None
                if words and norm(words[0][0]) == norm(PRIME):
                    nxt = words[1][1] if len(words) > 1 else words[0][2]
                    ac = int(max(words[0][2], nxt - 0.08) * sr)
                rec["cut_energy_s"] = round(ec / sr, 3) if ec else None
                rec["cut_asr_s"] = round(ac / sr, 3) if ac else None
                cut = ec if ec is not None else ac
                if cut is not None:
                    save_wav(AB / f"{name}_cut.wav", w[cut:], sr)
                    rec["cut_first_words"] = [t for t, _, _ in transcribe(wm, w[cut:], sr, max_s=3)][:4]
            out.append(rec)
            print(json.dumps(rec, ensure_ascii=False), flush=True)
    (AB / "metrics.jsonl").write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in out))

def decode_opus(p, sr=24000):
    r = subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-i", str(p),
                        "-f", "f32le", "-ac", "1", "-ar", str(sr), "pipe:1"], capture_output=True)
    if r.returncode != 0:
        raise RuntimeError(r.stderr.decode()[:200])
    return np.frombuffer(r.stdout, dtype="<f4")

def scan(n_files=150):
    from faster_whisper import WhisperModel
    wm = WhisperModel("tiny", device="cuda", compute_type="float16")
    sr = 24000
    files = sorted(WORK.glob("out/*/*/*.json"))
    step = max(1, len(files) // n_files)
    files = files[::step][:n_files]
    n_chunks = miss = 0
    t_asr = 0.0
    misses = []
    for sc in files:
        op = sc.with_suffix(".opus")
        if not op.exists():
            continue
        meta = json.loads(sc.read_text())
        w = decode_opus(op, sr)
        for i, (a, b) in enumerate(meta["chunks"]):
            seg = w[int(a * sr): int(a * sr) + int(3.0 * sr)]
            t0 = time.time()
            words = transcribe(wm, seg, sr)
            t_asr += time.time() - t0
            n_chunks += 1
            want = [norm(x) for x in meta["texts"][i].split()[:2]]
            got = [norm(t) for t, _, _ in words[:3]]
            ok = bool(got) and (got[0] == want[0] or (len(got) > 1 and got[1] == want[0])
                                or want[0].startswith(got[0]) or got[0].endswith(want[0]))
            if not ok:
                miss += 1
                misses.append(dict(f=str(op.name), chunk=i, want=meta["texts"][i][:40], got=got[:3]))
        if n_chunks and n_chunks % 200 < len(meta["chunks"]):
            print(f"...{n_chunks} chunks, {miss} first-word misses", flush=True)
    print(f"\nSCAN: {len(files)} files, {n_chunks} chunks, {miss} first-word misses "
          f"({miss / max(1, n_chunks) * 100:.1f}%), asr {t_asr / max(1, n_chunks) * 1000:.0f} ms/chunk", flush=True)
    (AB / "scan_misses.jsonl").parent.mkdir(exist_ok=True)
    (AB / "scan_misses.jsonl").write_text("\n".join(json.dumps(m) for m in misses))

def throughput(seconds=300):
    from chatterbox.tts import ChatterboxTTS
    tts = ChatterboxTTS.from_pretrained(device="cuda")
    text = "An open letter written to this leader described atrocities in the Congo Free State."
    t0 = time.time(); n = 0; audio = 0.0
    while time.time() - t0 < seconds:
        w = tts.generate(text, **PARAMS).squeeze(0).cpu().numpy()
        n += 1; audio += len(w) / tts.sr
    el = time.time() - t0
    print(f"THROUGHPUT: {n} chunks in {el:.0f}s = {audio / el:.2f}x realtime this stream", flush=True)

if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "bench"
    if cmd == "bench": bench()
    elif cmd == "scan": scan(int(sys.argv[2]) if len(sys.argv) > 2 else 150)
    elif cmd == "throughput": throughput(int(sys.argv[2]) if len(sys.argv) > 2 else 300)
