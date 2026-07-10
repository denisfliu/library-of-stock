# Stock Guide Project

Quizbowl study guide generator. Fetches clues from qbreader, analyzes them, generates Anki-style cards, and renders HTML study pages.

## Orientation (read this before exploring)

- `output/{slug}/analysis.json` is the **source of truth** for every topic. All HTML is generated from it — **never read or edit generated `.html` files** (there are ~2,500 of them); edit the JSON or the renderer, then run `./build.sh`.
- Renderers: `lib/render/render.py` (stock.html), `lib/render/render_cards.py` (cards.html), `lib/render/render_questions.py` (questions.html), `lib/build_index.py` (index.html). Each is a Python file emitting one big HTML template.
- Pipeline: `lib/pipeline/fetch.py` (qbreader API, cached) → `lib/pipeline/parse.py` (clue extraction) → `lib/run.py` (CLI wrapper producing `clues.txt`).
- Queues: `lib/queue/topic_queue.py` (global first/second-pass queues), `lib/queue/batch_worker.py` (per-batch claim/complete). State lives in `queue/*.json`.
- Cross-refs: `lib/crossref/crossref.py` rebuilds `output/topic_index.json`; `lib/crossref/backfill_crossrefs.py` adds mechanical links; the `/crossref` skill adds semantic ones.
- Agent workflows live in `.claude/skills/` (`batch`, `first-pass`, `second-pass`, `cards`, `crossref` + category supplements). `docs_backup/` is the pre-skills version, kept for reference only.
- `lib/pipeline/prompt_builder.py` predates the skills migration and reads from the deleted `docs/` directory — do not rely on it without fixing that.

## Common commands

```bash
./build.sh                                  # incremental render of everything + validate
./build.sh --force                          # full re-render
python lib/validate.py                     # health check on all analysis JSONs
python lib/queue/topic_queue.py summary    # queue counts by category
python lib/queue/batch_worker.py status    # current batch progress
python post_batch.py                       # after a batch: rebuild index + print agent prompts
```

## Universal Rules

### Analysis Quality
- **No outside knowledge for clue content.** Only describe what the clues say. Outside knowledge is OK for: hyperlinks, identifying referenced works/people for linking, and metadata fields (year, continent, country, tags).
- Any work/subtopic mentioned **3+ times** across all clues gets its own section — no exceptions.
- Any work with **specific plot/detail clues** gets its own section regardless of count.
- The `summary` field must be non-empty — a concise paragraph covering key identifiers, most famous works, and distinguishing facts.
- Work descriptions must be **mini-paragraphs**, not one-liners like "His most famous work."
- `comprehensive_summary` must be real prose synthesizing all facts from clues.
- Sentences may contain multiple clues — separate them during analysis.
- Giveaway clues (containing "For 10/ten points") are still clues.

### Metadata
- Reference `categories.md` (project root) for correct category, subcategory, and genre names.
- **"Visual Fine Arts"**, not "Visual Arts."
- `genre` is only set for:
  - Fine Arts > Other Fine Arts: specific type from categories.md (`Architecture`, `Film`, `Photography`, `Dance`, `Jazz`, `Musicals`, `Opera`, `Misc Arts`)
  - Science > Other Science: specific field (`Math`, `Astronomy`, `Computer Science`, `Earth Science`, `Engineering`, `Misc Science`)
  - Leave as `""` for all other subcategories.
- `year`: birth year for people, creation/publication year for works, start year for periods. Negative for BCE.
- `continent`: one of Africa, Asia, Europe, North America, Oceania, South America.
- `country`: country the topic is primarily associated with.
- `tags`: recognized movements/schools/styles only (e.g., `["Surrealism"]`). NOT broad geographic descriptors like "Japanese literature."

## Key Paths
- `output/{slug}/analysis.json` — per-topic analysis data
- `output/{slug}/stock.html` — rendered study page
- `output/topic_index.json` — master index of all topics/works
- `queue/` — all queue JSON files (never `lib/queue/`)
- `categories.md` — valid qbreader category/subcategory names
