# Reader voice audio — Chatterbox TTS generation pipeline

Pre-generates spoken audio for the reader (a nicer voice than the browser's
Web Speech API). Runs on **MSL** (RTX 4090) because Chatterbox is ~4.7x
realtime there vs ~1.7x on the laptop 4070.

## Decision trail (July 2026)
- Compared Web Speech (bad), Kokoro-82M (~20x realtime, fine), and Chatterbox
  (Resemble AI, MIT). Denis picked **Chatterbox** — clearly better voice.
  A/B samples: `dev/tts_samples/ab.html` (+ `v2.html`).
- Voice: Chatterbox default speaker (female; the one in the approved samples).
- Format: **Opus 24kbps mono in Ogg** (Denis's pick). ~123 KB/question.
- Scope (first run): **difficulty 7-9 tossups + bonuses = 119,901 items**,
  ~14.7 GB, ETA ~12.5 days single-stream on the 4090. Resumable, so it can be
  extended to more difficulties later by editing `DIFFS` in `gen_tts.py`.
- Hosting: **Hugging Face public dataset** `<user>/qb-audio`
  (R2 free tier is only 10 GB and already ~1 GB used; HF gives effectively
  unlimited public-dataset storage with a CDN + CORS + Range support, all
  verified). Reader will fetch `tossups|bonuses/{qid[-2:]}/{qid}.opus`.

## Files
- `ttsclean.py` — **single source of truth** for text cleaning (gen_tts imports
  `clean`). Strips, in either `()` or `[]`: pronunciation guides (quoted
  `("kun-doo-REE")`, and bare `(green-YARR)`/`SUR [sir]` via a hyphen +
  all-caps-stress heuristic — ~2.5k bare-paren guides were leaking before),
  moderator directions (`[emphasize]`, `(read slowly)`), and **moderator
  notes** (bracketed `[Note to moderator: ...]` and bare `Note to moderator:
  ...` prefixes). KEEPS: **player/reader notes** (`[Note to players: ...]` —
  info the answerer needs), real parentheticals (`(II)`, `(1710)`,
  `(After Fragonard)`, `(log n)`), and editorial brackets (`hat[ing]`->hating,
  `[this concept]`, `"[his]"`). Also **expands title abbreviations** for spoken
  output (`Mrs.`->Missus, `Mr.`->Mister, `Dr.`->Doctor, `St. X`->Saint X,
  `Mt.`->Mount, `Jr./Sr.`->Junior/Senior, `Op./No. N`->Opus/Number N,
  `vs.`->versus) — this fixes pronunciation AND removes the trailing period that
  otherwise splits a name like "Mrs. Dalloway" into two chunks across the gap.
  Self-test: `python ttsclean.py` (29 cases). Bonuses read verbatim.
- `ttsverify.py` — **ASR gate**, shared by gen_tts (inline) and verify_tts
  (backfill). whisper-tiny transcribes each synthesized chunk (~58 ms/chunk vs
  ~1 s to generate — a ~5% tax) and a chunk PASSES unless there's strong defect
  evidence: nothing heard, a content word replaced by a function word, or an
  unrelated word (far edit distance relative to length). **Deliberately
  conservative** — free ASR can't tell a legitimate Chatterbox pronunciation
  (Euler->"Oiler", Grignard->"Grinyard") from a clip by spelling, so it errs
  toward keeping and leans on priming-retry + the post-run whisperX pass for the
  rest. `cut_prime` removes a priming word at the ASR word boundary. Self-test:
  `python ttsverify.py` (12 first-word calibration cases). Calibrated on a
  150-file/859-chunk output scan (July 2026).
- `gen_tts.py` — the generator (runs on MSL, **two parallel streams** under tmux
  sessions `tts0`/`tts1` via `--shard 0/2` and `--shard 1/2` — disjoint slices,
  ~43% more throughput; the 4090 is ~80% utilized by one stream so a 2nd adds
  sub-linearly, a 3rd wouldn't). Reads the mirror, cleans (ttsclean), **chunks**
  (merges tiny fragments like the "H." from "W. H. Auden", protects abbreviation
  /initial periods from the splitter, splits >200-char sentences at clauses —
  short chunks babble, long ones run away), synthesizes **chunk 0** through the
  **ttsverify gate**: re-roll on a failed first-word/duration check, and the
  final retry escalates to priming (prepend a sacrificial word, cut it off) to
  fix a stubborn attack-clip; keep the best-scoring take if all fail. **Chunks 1+
  get only the cheap duration-runaway check** — whisper on every chunk saturates
  the GPU (89%) and cancels the two-stream speedup (measured: 4.8x combined with
  full gating vs ~6.9x ungated); the post-run whisperX pass is the exhaustive
  mid-question clip net. Encodes to
  Opus via ffmpeg, writes `out/{tossups,bonuses}/{qid[-2:]}/{qid}.opus` (sharded
  by the LAST two hex chars — the ObjectId counter, uniform across 256 buckets;
  the timestamp *prefix* is `62` for every qbreader id, which funneled all files
  into one folder and hit HF's hard 10k-files-per-directory limit on July 19,
  2026 — re-sharded + re-uploaded that day) plus a `{qid}.json` sidecar: `{"v":1,
  "chunks": [[start_s,end_s],...], "texts":[...]}` — exact per-chunk audio
  offsets + chunk texts (audio time → text position; the moderator tool's
  buzz-position source). The sidecar is written before the `.opus` lands, so a
  present `.opus` always implies a present sidecar. Skip-existing = resumable.
  Sampling params in `PARAMS` (settled by A/B: default voice — cloning sounded
  worse — exaggeration 0.5, temperature 0.7, repetition_penalty 1.3).
- `verify_tts.py` — **backfill QA** over already-generated files (MSL). Flags a
  file for regeneration if (1) its clean+chunk text changed under the current
  ttsclean/chunker (e.g. abbreviation expansion — deterministic, no ASR), or
  (2) a chunk fails the ttsverify gate. `--apply` deletes the `.opus`+`.json` so
  gen_tts's resume regenerates it; default is a `--dry-run` report. Also the
  reusable post-run QA tool. A/B bench that settled all this: `msl_ab3.py`
  (baseline-vs-primed, clip-rate scan, throughput probe) + `dev/tts_samples/tuning3/`.
- `ttscorpus.py` — **torch-free** corpus helpers (worklist, chunk splitting,
  `out/` path layout) shared by gen_tts, verify_tts, and ttsqueue. Kept free of
  torch so a queue claim over SSH doesn't pay a multi-second model import.
- `ttsqueue.py` — **cross-machine work queue** (SQLite `~/los_tts/tts_queue.db`
  on the host machine). One Chatterbox stream saturates a GPU, so the way to go
  faster is more *machines*, each its own GPU, drawing from one queue.
  `init` seeds from the mirror (marking existing `out/` done); `claim`/`complete`
  are atomic (BEGIN IMMEDIATE + busy timeout) with a 1 h lease so a crashed
  worker's items re-serve. Transport is **SSH, not an HTTP port** (MSL is behind
  the Stanford firewall): a remote worker runs `ssh msl python ttsqueue.py claim`,
  batched (~100 items/round) so the round-trip is negligible. `Client(host)`
  wraps local-vs-ssh for gen_tts. Self-test (atomicity/lease/drain): the queue
  logic is exercised by a synthetic-DB test (see commit).
- `upload_hf.py` — CommitScheduler uploader (second tmux session). Reads a
  write token from `~/los_tts/.hf_token` (chmod 600, never on the cmdline),
  creates the dataset repo, commits new `*.opus` + `*.json` sidecars every
  10 min. Idempotent.

## MSL layout
- Workdir `~/los_tts/` : `qbreader.sqlite` (mirror copy), `gen_tts.py`,
  `ttscorpus.py`, `ttsqueue.py`, `ttsclean.py`, `ttsverify.py`, `upload_hf.py`,
  `out/`, `tts_queue.db`, `gen.log`, `.hf_token`.
- Venv `~/venvs/chatterbox-tts/` (miniforge-python venv; torch 2.6.0+cu124,
  `setuptools<80` so perth's `pkg_resources` import works; plus `faster-whisper`
  for the ASR gate).
- MSL hosts the queue and runs one worker. tmux: `tts` (generator), `upload`
  (uploader), `sweep` (maintenance). Launch:
  `~/venvs/chatterbox-tts/bin/python ttsqueue.py init`   # once, seeds the queue
  `tmux new-session -d -s tts "~/venvs/chatterbox-tts/bin/python gen_tts.py --queue --worker msl >> gen.log 2>&1"`
  `tmux new-session -d -s upload "bash -c \"ulimit -n 65536 && ~/venvs/chatterbox-tts/bin/python upload_hf.py >> upload.log 2>&1\""`
  `tmux new-session -d -s sweep "bash ~/los_tts/maintain.sh >> sweep.log 2>&1"`
  — the uploader NEEDS the raised fd limit: a fresh CommitScheduler's first
  push re-scans the whole out/ folder and blows past the default 1024 open
  files once the corpus is a few thousand files (hit July 18, 2026).
- `maintain.sh` (the `sweep` session): every 30 min runs `ttsqueue.py reconcile`
  (requeues items a stopped worker marked done but never synced), and every 4 h
  also runs `verify_tts.py --no-asr --requeue` (requeues stale-text files). This
  guarantees the end-of-run sweep happens on its own and keeps the fleet
  self-healing as workers come and go.
- Monitor: `ssh msl 'grep "made" ~/los_tts/gen.log | tail -1'`;
  queue: `ssh msl '~/venvs/chatterbox-tts/bin/python ~/los_tts/tts_queue... stats'`
  (`ttsqueue.py stats`).

## Adding a worker on another machine (fleet)
An extra machine draws from MSL's queue over SSH and **does NOT run its own
uploader** — `upload_hf` builds the manifest from the *local* out/, so a second
uploader would clobber MSL's manifest and conflict on the dataset's git history.
Instead the worker ships its files to MSL with `push_out.py`, and MSL's single
uploader owns HF + the union manifest.
  1. Copy `qbreader.sqlite` + the `tts*.py` scripts to `~/los_tts/` (a hardlink to
     an existing mirror copy avoids duplicating 860 MB).
  2. Env: chatterbox-tts + faster-whisper + ffmpeg + **`setuptools<80`** (else
     perth's watermarker silently becomes None -> `TypeError` at model load) and
     the **CUDA** torch build (`pip install torch --index-url .../cu124`; the
     chatterbox dep pulls the CPU build by default).
  3. Launch the worker AND the sync loop. If you invoke the env's python directly
     (not `conda run`), put the env's `Library\bin` on PATH first or ffmpeg isn't
     found (`WinError 2` at encode):
       `gen_tts.py --queue --queue-host msl --worker <name>`
       `push_out.py --host msl`
     `--queue-host msl` routes claim/complete over `ssh msl` (needs passwordless
     ssh, or adjust `REMOTE_PY`/`REMOTE_SCRIPT` in ttsqueue.py). Each qid is served
     once fleet-wide. On **Windows** use `worker_ctl.ps1 start|stop|status`
     (`powershell -ExecutionPolicy Bypass -File worker_ctl.ps1 <cmd>`) — it sets
     the PATH, launches worker+push_out detached, and tracks PIDs; disable AC sleep
     while running (`powercfg -change -standby-timeout-ac 0`).
  4. **Fluid pause/resume**: just stop to pause, start to resume — nothing is lost.
     Claims are small (batch 30) and completions flush every 5, so an abrupt stop
     leaves at most a few items un-acked; those plus the unstarted rest of the
     batch re-serve after the 30-min lease, and MSL's `sweep` loop reconciles
     anything completed-but-unsynced. Worst case is re-doing a handful of items.
  5. **Reconcile / end-of-run**: MSL's `sweep` loop already runs `ttsqueue.py
     reconcile` every 30 min (resets to 'todo' any 'done' qid whose `.opus` isn't
     in MSL's out/) and the text-sweep every 4 h — so gaps self-heal without
     intervention. To force it: `ttsqueue.py reconcile` + `verify_tts.py --no-asr
     --requeue` on MSL.

## Reader integration — DONE (July 17, 2026)
The reader (`lib/js/reader.js`) plays this audio when "Read aloud" is on:
- Base `https://huggingface.co/datasets/uild42/qb-audio/resolve/main`;
  plays `tossups/{qid[-2:]}/{qid}.opus` via a shared `<audio>` element.
- Loads `audio_index.json` and RESTRICTS the queue to questions that have
  audio (`audioMode()`/`hasAudio()` gate in `rowInScope`) — so scope/facets/
  queue only show playable questions. Before the manifest loads, nothing is
  filtered (queue never collapses mid-load). Empty manifest -> zero in scope.
- Buzz depth from the audio clock (`currentTime/duration` -> reveal-unit idx);
  text hidden until resolve; native pause/resume; speed slider = playbackRate
  (pitch-preserved), live mid-question. A file error/404 degrades to text
  reveal for that one question.
- Next question's audio is blob-prefetched during the current one's playback
  (`prefetchAudio`/`audioSrcFor`, LRU-capped) so only the first question of a
  session pays HF's ~0.5 s resolve→CDN latency; the rest start instantly.
- Regression test `tests/reader_audio/run_tests.js` (in CI) covers the gate.
- CORS+Range verified from the GitHub Pages origin; `<audio>` playback needs
  no CORS, only the manifest `fetch()` does (present on the resolve URL).

## Still TODO
1. Port `ttsclean.clean` into `lib/` (shared source of truth for re-gen).
2. ~~Per-question offset manifest~~ — **done July 18, 2026**: `{qid}.json`
   chunk-offset sidecars (see gen_tts above). Reader still uses the
   proportional `currentTime/duration` approximation until it's taught to
   fetch sidecars.
3. **Post-run batch alignment** (decided July 18): after the run, force-align
   the whole dataset on the 4090 (whisperX align-only against the known
   clean+chunk transcript; ~a day of GPU) → word-level sidecar v2, covers
   pre-sidecar files, and flags badly-aligning (runaway/babble) files as a
   regen worklist. Chunk sidecars serve as alignment anchors + validation.
4. New sets from `sync.py` won't have audio until a re-run; they simply won't
   appear in audio-mode scope until then (the manifest gates them out).
5. Extend `DIFFS` in gen_tts.py to cover more difficulties later if wanted.
