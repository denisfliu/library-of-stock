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
- `ttsclean.py` — text cleaning. Strips pronunciation guides (`("kun-doo-REE")`
  and `SUR [sir]`) and moderator directions (`[emphasize]`/`[read slowly]`/
  `[pause]`); KEEPS editorial brackets (`hat[ing]`->hating, `[this concept]`,
  `"[his]"`). Bonuses read verbatim (leadin + parts), no injected "for 10
  points each" — the writer includes it if they want it. **This logic must be
  ported into the real pipeline when the reader consumes the audio.**
- `gen_tts.py` — the generator (runs on MSL under tmux session `tts`). Reads
  the mirror, synthesizes, encodes to Opus via ffmpeg, writes
  `out/{tossups,bonuses}/{qid[:2]}/{qid}.opus`. Sharded by ObjectId prefix
  (256 buckets) for HF's <10k-files-per-folder rule. Skip-existing = resumable.
- `upload_hf.py` — CommitScheduler uploader (second tmux session). Reads a
  write token from `~/los_tts/.hf_token` (chmod 600, never on the cmdline),
  creates the dataset repo, commits new `*.opus` every 10 min. Idempotent.

## MSL layout
- Workdir `~/los_tts/` : `qbreader.sqlite` (mirror copy), `gen_tts.py`,
  `upload_hf.py`, `out/`, `gen.log`, `.hf_token`.
- Venv `~/venvs/chatterbox-tts/` (miniforge-python venv; torch 2.6.0+cu124,
  `setuptools<80` so perth's `pkg_resources` import works).
- tmux: `tts` (generator), and an uploader session once the token exists.
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
2. Optional: per-question sentence-offset manifest for sentence-accurate buzz
   depth (generate sentence-by-sentence, record cumulative durations).
3. New sets from `sync.py` won't have audio until a re-run; they simply won't
   appear in audio-mode scope until then (the manifest gates them out).
4. Extend `DIFFS` in gen_tts.py to cover more difficulties later if wanted.
