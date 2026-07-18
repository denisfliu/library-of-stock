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
  verified). Reader will fetch `tossups|bonuses/{qid[:2]}/{qid}.opus`.

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
  Opus via ffmpeg, writes `out/{tossups,bonuses}/{qid[:2]}/{qid}.opus` (sharded
  by ObjectId prefix, 256 buckets) plus a `{qid}.json` sidecar: `{"v":1,
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
- `upload_hf.py` — CommitScheduler uploader (second tmux session). Reads a
  write token from `~/los_tts/.hf_token` (chmod 600, never on the cmdline),
  creates the dataset repo, commits new `*.opus` + `*.json` sidecars every
  10 min. Idempotent.

## MSL layout
- Workdir `~/los_tts/` : `qbreader.sqlite` (mirror copy), `gen_tts.py`,
  `upload_hf.py`, `out/`, `gen.log`, `.hf_token`.
- Venv `~/venvs/chatterbox-tts/` (miniforge-python venv; torch 2.6.0+cu124,
  `setuptools<80` so perth's `pkg_resources` import works).
- tmux: `tts` (generator), `upload` (uploader). Launch:
  `tmux new-session -d -s tts "~/venvs/chatterbox-tts/bin/python gen_tts.py >> gen.log 2>&1"`
  `tmux new-session -d -s upload "bash -c \"ulimit -n 65536 && ~/venvs/chatterbox-tts/bin/python upload_hf.py >> upload.log 2>&1\""`
  — the uploader NEEDS the raised fd limit: a fresh CommitScheduler's first
  push re-scans the whole out/ folder and blows past the default 1024 open
  files once the corpus is a few thousand files (hit July 18, 2026).
- Monitor: `ssh msl 'grep "made" ~/los_tts/gen.log | tail -1'`.

## Reader integration — DONE (July 17, 2026)
The reader (`lib/js/reader.js`) plays this audio when "Read aloud" is on:
- Base `https://huggingface.co/datasets/uild42/qb-audio/resolve/main`;
  plays `tossups/{qid[:2]}/{qid}.opus` via a shared `<audio>` element.
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
