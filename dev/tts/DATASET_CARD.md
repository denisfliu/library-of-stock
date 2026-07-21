---
pretty_name: qb-audio
language:
  - en
license: other
license_name: community-question-content
license_link: https://www.qbreader.org/
tags:
  - audio
  - text-to-speech
  - quizbowl
  - trivia
---

# qb-audio — read-aloud audio for quizbowl questions

TTS read-aloud recordings of quizbowl questions from
[qbreader](https://www.qbreader.org/), one Opus file per tossup / bonus.
Built so any quizbowl app can add listening practice over plain HTTP — no
install, no API key. **Generation is in progress (July 2026); the dataset
grows as the run proceeds.**

## Layout

- `tossups/{qid[-2:]}/{qid}.opus`, `bonuses/{qid[-2:]}/{qid}.opus` — audio,
  Opus 24 kHz mono. `qid` is the question's qbreader `_id`; files shard by
  its last two hex characters.
- `tossups/{qid[-2:]}/{qid}.json`, `bonuses/...` — chunk-offset sidecar:
  `{"v": 1, "chunks": [[start_s, end_s], ...], "texts": ["chunk text", ...]}`.
  Synthesis is per-chunk, so cumulative chunk durations map audio time to
  text position (for buzz points, reveal pacing).
- `audio_index.json` — manifest: `{"tossups": [qid, ...], "bonuses": [qid,
  ...]}`, the questions that have audio. Fetch this first and restrict your
  queue to it.

The spoken text is a cleaned form of the question text (pronunciation
guides applied, markup and moderator directives stripped) — the sidecar
`texts` are exactly what the audio says.

## How it was made

Synthesized with [Chatterbox TTS](https://github.com/resemble-ai/chatterbox)
(MIT, Resemble AI) on a single RTX 4090, with an ASR verification gate
(OpenAI [Whisper](https://github.com/openai/whisper), MIT) that re-rolls
clipped or runaway generations. Pipeline code is open source under the
[qbsuite](https://github.com/qbsuite) org (MIT).

## Credits and licensing

- **Question text** was written by the packet authors and editors of the
  respective tournaments and reaches this dataset via
  [qbreader](https://www.qbreader.org/), which distributes the community
  question archive. The audio is a synthesized reading of that text;
  rights in the underlying questions remain with their authors.
- The dataset is shared for study and practice in line with quizbowl
  community norms, the same basis on which the text archive circulates. It
  is not licensed for uses beyond that (the `other` license tag above
  reflects this — there is no blanket open-content license to grant).
- **Audio synthesis**: Chatterbox TTS (MIT © Resemble AI). QA: Whisper
  (MIT © OpenAI).

If you are an author or editor of included questions and want your
material removed, open an issue on any [qbsuite](https://github.com/qbsuite)
repo or use the dataset's community tab and it will be taken down.
