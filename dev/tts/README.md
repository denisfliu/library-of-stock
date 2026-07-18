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
  `[this concept]`, `"[his]"`). Self-test: `python ttsclean.py` (21 cases).
  Bonuses read verbatim, no injected "for 10 points each".
- `gen_tts.py` — the generator (runs on MSL under tmux session `tts`). Reads
  the mirror, cleans (imports ttsclean), **chunks** (merges tiny fragments like
  the "H." from "W. H. Auden", splits >200-char sentences at clauses — both are
  glitch magnets), synthesizes each chunk with a **runaway validator** (if a
  chunk's duration far exceeds what its text warrants — the babble/repetition
  signature — regenerate, up to 3x, keep shortest), encodes to Opus via ffmpeg,
  writes `out/{tossups,bonuses}/{qid[:2]}/{qid}.opus` (sharded by ObjectId
  prefix, 256 buckets) plus a `{qid}.json` sidecar: `{"v":1, "chunks":
  [[start_s,end_s],...], "texts":[...]}` — exact per-chunk audio offsets +
  chunk texts (audio time → text position; the moderator tool's buzz-position
  source). The sidecar is written before the `.opus` lands, so a present
  `.opus` always implies a present sidecar. Skip-existing = resumable. Sampling params in `PARAMS`
  (settled by A/B: default voice — cloning sounded worse — exaggeration 0.5,
  temperature 0.7, repetition_penalty 1.3).
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
