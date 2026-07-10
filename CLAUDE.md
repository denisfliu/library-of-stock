# Stock Guide Project

Quizbowl study guide generator. Fetches clues from qbreader, analyzes them, generates Anki-style cards, and renders HTML study pages.

## Orientation (read this before exploring)

- `output/{slug}/analysis.json` is the **source of truth** for every topic. All HTML is generated from it — **never read or edit generated `.html` files** (there are ~2,500 of them); edit the JSON or the renderer, then run `./build.sh`.
- Renderers: `lib/render/render.py` (stock.html), `lib/render/render_cards.py` (cards.html), `lib/render/render_questions.py` (questions.html), `lib/build_index.py` (index.html). Each is a Python file emitting one big HTML template.
- Pipeline: `lib/pipeline/fetch.py` (qbreader API, cached) → `lib/pipeline/parse.py` (clue extraction) → `lib/run.py` (CLI wrapper producing `clues.txt`).
- Queues: `lib/queues/topic_queue.py` (global first/second-pass queues), `lib/queues/batch_worker.py` (per-batch claim/complete). State lives in `queue/*.json`.
- Cross-refs: `lib/crossref/crossref.py` rebuilds `output/topic_index.json`; `lib/crossref/backfill_crossrefs.py` adds mechanical links; the `/crossref` skill adds semantic ones.
- Agent workflows are skills in `.claude/skills/<name>/SKILL.md`: `/batch`, `/first-pass`, `/second-pass`, `/cards`, `/crossref`, plus category supplements (`/literature`, `/vfa`, `/afa`, `/philosophy`, `/science`). These are the single source of truth for agent instructions.
- `lib/common.py` provides `ROOT`/`OUTPUT_DIR`/`QUEUE_DIR`/etc., UTF-8 stdio, and `file_lock`. Every entry script imports it — new scripts should too.

## Common commands

```bash
./build.sh                                  # incremental render of everything + validate
./build.sh --force                          # full re-render
python lib/validate.py                     # health check on all analysis JSONs
python lib/queues/topic_queue.py summary    # queue counts by category
python lib/queues/batch_worker.py status    # current batch progress
python post_batch.py                       # after a batch: rebuild index + print agent prompts
```

## Deferred improvements (roadmap for future sessions)

- **Template consolidation**: the renderers embed large HTML/CSS strings; shared CSS lives in `lib/render/theme.py`. Long-term, move page templates to Jinja2 files.
- **`getCardImages` is triplicated** — `lib/render/render_cards.py` (Python `_synthesize_image_cards`), its embedded JS, and `lib/js/anki_export.js`. Any card-image schema change needs all three.
- **Tests + CI**: zero tests exist. Start with a golden-file render test (render a fixture topic, diff against a committed snapshot) and a GitHub Action running `./build.sh && python lib/validate.py --strict`.
- **Single-load `build.py` orchestrator**: `build.sh` runs ~10 processes that each re-parse all analysis JSONs (~4x redundant parsing). Worth doing when the corpus outgrows the current ~23s forced build.
- **Wikimedia batching**: `lib/images/` fetches thumbnails one filename at a time; the Commons API accepts pipe-joined `titles=`.
- **qbreader pagination**: `fetch.py` retrieves only the first 25 results per query — big topics (Beethoven, Shakespeare) silently lose clues. Add pagination or raise `maxReturnLength`.
- **Next-button ordering**: currently chronological-by-year within subcategory; science/philosophy concepts have no year. When yearless topics grow, switch to tag-based clustering so related concepts are adjacent.

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
  - Social Science: alternate_subcategory (`Psychology`, `Anthropology`, `Economics`, `Linguistics`, `Sociology`, `Other Social Science`)
  - Leave as `""` for all other subcategories.
- `year`: birth year for people, creation/publication year for works, start year for periods. Negative for BCE.
- `year_end` (optional): end year for periods, wars, empires, movements — renders as a timeline span. Omit for people and single works.
- `coordinates` (optional): `[lat, lon]` decimal degrees for Geography and place-anchored topics (buildings, monuments). Outside knowledge OK, like `year`.
- `group` (optional): one clustering value per topic where the category supplement defines a vocabulary — science field ("Organic Chemistry"), mythology tradition ("Greek"), religion ("Buddhism"), philosophy school ("German Idealism").
- `continent`: one of Africa, Asia, Europe, North America, Oceania, South America.
- `country`: country the topic is primarily associated with.
- `tags`: recognized movements/schools/styles only (e.g., `["Surrealism"]`). NOT broad geographic descriptors like "Japanese literature." Don't duplicate the `group` value.

## Key Paths
- `output/{slug}/analysis.json` — per-topic analysis data
- `output/{slug}/cards.json` — the topic's Anki cards (separate file; card agents write ONLY this)
- `output/{slug}/stock.html` — rendered study page
- `output/topic_index.json` — master index of all topics/works
- `queue/` — all queue JSON files (never `lib/queues/`)
- `categories.md` — valid qbreader category/subcategory names
