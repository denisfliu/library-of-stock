# QB tools suite — open-source plan (July 2026)

Status: **planned, not started** (except where marked). The intent: a new
independent GitHub org housing a suite of quizbowl tools extracted from this
repo, useful to the community and to us. `library-of-stock` stays the site,
but becomes a **consumer of the extracted packages** — code moves out and is
imported back, one source of truth, no copy drift.

## Decisions (settled)

- **New independent org** (name TBD — candidates: `openqb`, `qbkit`,
  `quizbowl-tools`). Positioned as a companion ecosystem to qbreader;
  contribute upstream opportunistically.
- **Extract-and-depend**, not copy-fork: each extraction refactors this repo
  to import the published package.
- **First public deliverable: qb-audio** (dataset spec + generation pipeline
  + JS playback client).
- **Moderator v1 is living-room only, no server**: one device reads a whole
  set aloud, keeps score, and — as the end goal — *listens* for buzzes and
  spoken answers (mic barge-in + STT). Online rooms come later, so the game
  engine must be transport-agnostic from day one (see rooms.md for the
  Durable Object design it will slot into).

## Repo map (three repos for v1)

| Repo | Contents | Extracted from |
|---|---|---|
| `qb-core` | The contracts + shared engines: question ID + `qid[-2:]` sharding scheme, answerline normalization, taxonomy ordinals, TTS text cleaning, the answer checker (vendored from qbreader, credited), and the reveal/pacing engine. Python + JS packages sharing golden test vectors. | `sweep/answerlines.py`, `mirror/publish.norm_ans`, reader.js `normAns` + reveal clock, `mirror/query.py` ordinals, `dev/tts/ttsclean.py`, `lib/js/answer_checker.js`, `tests/answer_checker/` (seed vectors) |
| `qb-audio` | Dataset spec (layout, manifest, chunk-offset sidecar schema, cleaning contract), generation pipeline (any-TTS-backend, mirror as one input adapter), JS playback client (manifest gate, LRU prefetch, audio-clock→text-position via sidecars). | `dev/tts/`, audio parts of `lib/js/reader.js` |
| `qb-moderator` | The game tool (below). | new + rooms.md design |

There is deliberately **no `qb-reader` repo**: the durable, reused-everywhere
pieces of the reader are the answer checker and the reveal/pacing engine, and
those are exactly qb-core's job — behavior that must be byte-identical across
the site reader, the moderator, and the future room server, enforced by
shared test vectors. The rest of reader.js is site UI nobody needs as a
library; the site's reader becomes qb-core's reference consumer.

**Later additions** (roadmap; code stays in this repo until extracted):
- `qb-mirror` — importer / sync / query engine as a PyPI package + CLI
  (`lib/mirror/`; R2 publisher stays site-side). Cleanest extraction, but
  nothing in v1 blocks on it being public.
- `qb-search` — embedder, IVF-binary index builder, self-hostable Worker
  (`lib/embed/`, `sync/worker.js` /search). Different audience (data/infra
  self-hosters) and stack than the v1 repos; extract once those settle.

## Why qb-core exists

The suite is held together by cross-language contracts that currently live
in duplicate/triplicate (normAns ×3, taxonomy ordinals ×3, ttsclean "must be
ported"). Open-sourcing makes them public interfaces; qb-core writes them
down once with shared **golden test vectors** — fixed input→expected-output
pairs stored as data and asserted by both the Python and JS test suites, so
the two implementations can't drift — plus thin py/js implementations. This
also pays down the "unify the answerline normalizers" roadmap item instead
of tripling the drift surface.

## qb-moderator v1 (living room, voice-driven)

Architecture rule: **game engine ≠ transport ≠ input**.

- **Engine** (pure state machine, no I/O): set iteration (tossup/bonus
  cycle via mirror set structure), buzz arbitration + lockouts, power/neg
  scoring from buzz position, bonus flow, score log. Runs identically in a
  browser tab today and inside a Durable Object later.
- **Input adapters**, in build order:
  1. hotkeys (one key per player/team) — v0, proves the engine;
  2. phones as buzzers (local network / room code) — shares the eventual
     online protocol;
  3. **voice barge-in** — the goal: mic open while audio plays
     (`getUserMedia` with `echoCancellation: true` against the device's own
     output), VAD/transient or keyword spotting for the buzz, STT for the
     answer (Web Speech first, whisper-WASM/WebGPU upgrade path), verdict
     from the answer checker, spoken score feedback.
- **Buzz flow**: a detected buzz pauses playback *immediately* (the `<audio>`
  element pauses instantly; for voice barge-in, the buzz timestamp is the
  detection time, not when STT finishes). Wrong answer → that player/team is
  locked out and reading resumes from the pause point (optionally rewound a
  few words for context); correct → score and move on; all locked out or
  time up → dead, reveal.
- **Buzz position** comes from the audio clock mapped through the
  chunk-offset sidecars (below) — that's what makes powers, prompts, and
  protests adjudicable. Platform: web app (PWA); everything above works in
  the browser and shares code with qb-reader and the future room client.

## Chunk-offset sidecars — DONE in gen_tts.py (July 18, 2026)

Synthesis is per-*chunk* (`chunk_text` merges tiny fragments, splits long
sentences at clauses), so cumulative per-chunk durations are exact and free
to record at generation time. This is the load-bearing artifact for the
whole moderator concept (audio time T → text position), promoted from
"optional" (dev/tts TODO #2) to a required part of the dataset spec.

- `gen_tts.py` now emits a per-question sidecar `{qid}.json` next to each
  `.opus`: `{"v": 1, "chunks": [[start_s, end_s], ...], "texts": [...]}`.
  The chunk *texts* are included because chunk boundaries aren't
  reproducible client-side — they're what lets a client map an offset back
  into the question text. Same shard folder (~940 files/folder, under HF's
  10k limit); sidecar written before the `.opus` lands so skip-existing
  resume can never produce audio without offsets. `upload_hf.py` ships them.
- **Deploy**: copy the updated `gen_tts.py` + `upload_hf.py` to MSL and
  bounce the tmux sessions (skip-existing makes restarts free). Reader
  keeps its proportional `currentTime/duration` approximation as fallback
  until it's taught to fetch sidecars.
- **Post-run batch alignment (decided July 18)**: after generation
  completes, force-align the ENTIRE dataset in one batch on the 4090 —
  alignment-only mode against the known transcript (whisperX align /
  wav2vec2 CTC; text is deterministic from the mirror via clean+chunk, no
  ASR), roughly a day of GPU for ~900 h of audio. This (a) yields
  **word-level** timestamps everywhere, written as sidecar v2 (word spans
  alongside the chunk spans); (b) covers files generated before the sidecar
  change, so nothing is deleted/regenerated for offsets' sake; (c) doubles
  as a QA sweep — files that align badly against their true text are the
  runaway/babble glitches, and become a regen worklist. The gen-time chunk
  sidecars remain the anchors: aligning within known chunk spans is more
  robust than whole-file alignment, and word timings outside their chunk
  are a detectable error.

## Sequencing

1. **Now, this repo**: ~~chunk-offset emission into `gen_tts.py`~~ done
   July 18, 2026 — deploy to MSL (see above). Pick org name, create org.
2. **qb-core** — contracts + checker + reveal engine; unblocks everything;
   normalizer unification lands here and the site switches to it.
3. **qb-audio** — dataset spec doc, pipeline repo, JS client; site reader
   consumes the client package.
4. **qb-moderator** — engine + hotkey v0 → phone buzzers → voice.
5. **Later**: `qb-mirror`, then `qb-search`.

## Data / licensing note

The mirror and audio dataset redistribute qbreader-hosted, tournament-
authored question content. qbreader distributes official backups, so
community norms appear fine, but make it a deliberate stance: tools *build
from* qbreader backups (user runs the import), we avoid redistributing the
raw DB ourselves; the derived audio dataset gets a README note crediting
qbreader + tournament authors. Code license: MIT across the org (matches
qbreader and Chatterbox).
