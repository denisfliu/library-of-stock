# Library of Stock

A quizbowl study tool built on a full local mirror of the [qbreader](https://www.qbreader.org/) database. Claude agents analyze every clue ever written about a topic and produce structured, frequency-ranked study guides; renderers turn those analyses into a static site with a wiki, unit overview pages, tournament sweep pages, and an interactive question reader with cross-device sync.

The published site: <https://denisfliu.github.io/library-of-stock/>

## How It Works

1. **Fetch** — `lib/pipeline/fetch.py` queries the local qbreader mirror (`mirror/qbreader.sqlite`, gitignored, ~860 MB) for all tossups/bonuses where a topic appears as the answerline. The live qbreader API is used only by `lib/mirror/sync.py` to pull newly added sets. See `docs/mirror.md`.
2. **Parse** — `lib/pipeline/parse.py` extracts individual clue sentences with metadata (power mark, giveaway, source set/year).
3. **Analyze** — a Claude agent reads the clues, groups them by work/subtopic, ranks by frequency, and writes `output/{slug}/analysis.json`, plus Anki cards in `cards.json`. Agent instructions live in `.claude/skills/` and CLAUDE.md.
4. **Render** — `./build.sh` (a thin wrapper around `build.py`, a single-process orchestrator) regenerates every page from the JSON and runs validation.

`analysis.json` is the source of truth for every topic. All HTML is regenerable from it at any time — never edit generated `.html` files.

## The Site

Three entry pages, all generated:

- **`index.html`** — portal homepage (`lib/render/build_home.py`).
- **`wiki.html`** — master study-guide index with search (`lib/build_index.py`). Links into per-topic pages, unit overview pages (`output/_categories/`), and tournament sweep pages (`output/_sets/`).
- **`reader.html`** — question reader (`lib/render/build_reader.py` + `lib/js/reader.js`): plays real tossups with buzz/judge scoring, spaced-repetition mastery tracking, facet filtering, stats, voice reading, and semantic clue search. Question text loads at view time from R2; optional GitHub-OAuth cross-device sync runs on a Cloudflare Worker + D1 (`sync/` — see `sync/README.md`).

All pages support a runtime mobile layout mode and share theming from `lib/render/theme.py` and scripts from `lib/js/`.

## Repository Layout

```
library-of-stock/
├── build.sh / build.py       # Build everything + validate (build.sh wraps build.py)
├── post_batch.py             # Post-batch automation: crossref rebuild + agent prompts
├── index.html / wiki.html / reader.html   # Generated entry pages (gitignored)
├── categories.md             # Valid qbreader category/subcategory/genre names
├── CLAUDE.md                 # Agent instructions (analysis quality + metadata rules)
├── docs/                     # Design docs: mirror, crossref, question store (history), rooms
│
├── .claude/skills/           # Agent workflows (the primary way work gets done)
│   ├── batch|first-pass|second-pass|cards|crossref|verify|new-category/
│   └── literature|vfa|afa|philosophy|science|history|geography|
│       mythology|religion|social-science/       # category supplements
│
├── lib/
│   ├── common.py             # Shared paths, UTF-8 stdio, portable file locking
│   ├── run.py                # Fetch + parse runner (CLI used by agents and manually)
│   ├── units.py              # Canonical 40-unit registry + subcategory alias map
│   ├── build_index.py        # Generates wiki.html
│   ├── rerender.py           # Re-render all stock.html from analysis.json
│   ├── validate.py           # Post-build health checks
│   ├── questions_store.py    # Live refs helpers (questions_ref.json); store itself retired
│   ├── pipeline/             # fetch.py (mirror-backed), parse.py, digest.py
│   ├── mirror/               # qbreader SQLite mirror: importer, sync, queries, R2 publish
│   ├── queues/               # topic_queue.py, batch_worker.py, scan_redo.py
│   ├── render/               # Page renderers: render.py (stock), render_cards.py,
│   │                         #   render_questions.py, render_overview.py, render_sweep.py,
│   │                         #   build_overviews.py, build_reader.py, build_home.py,
│   │                         #   render_audio.py (ABC→MP3), render_score_review.py, theme.py
│   ├── crossref/             # crossref.py (topic index), linker.py + relink.py
│   │                         #   (mechanical links), infer.py (related-topics from mirror)
│   ├── sweep/                # Tournament sets (build_set.py, matcher.py, answerlines.py),
│   │                         #   overview authoring (author.py, capture_questions.py),
│   │                         #   answerline KB (answerline_kb.py, wikidata.py), freq/gaps tools
│   ├── embed/                # Qwen3 embedding pipeline: embed_corpus.py, cluster.py,
│   │                         #   build_search_index.py (powers reader clue search + inference)
│   ├── images/               # Wikimedia Commons image lookup + fixers
│   ├── audio/                # soundbites.py — Commons audio curation for overview pages
│   └── js/                   # Shared browser JS: reader.js, answer_checker.js, sync.js,
│                             #   qdata.js (R2 question fetch), map_view.js, mobile.js,
│                             #   search_nav.js, anki_export.js
│
├── sync/                     # Cloudflare Worker + D1: OAuth login, reader sync, search API
├── tests/                    # golden render test (Python), answer_checker + reader_facets (Node)
├── dev/                      # Dev dashboards (committed) + their data builders
├── queue/                    # Queue state (first pass, second pass, redo, current batch)
├── output/                   # Generated content — one directory per topic (see below)
├── mirror/                   # qbreader.sqlite + embeddings.sqlite (gitignored)
└── cache/                    # cache/sets/: live-API sync resume cache (gitignored)
```

### Per-topic output layout

```
output/{slug}/
├── analysis.json        # Source of truth: summary, works, clues, metadata, cross_refs
├── cards.json           # Anki cards (own file so card agents can't clobber the analysis)
├── questions_ref.json   # qbreader _id refs backing questions.html (text resolved from mirror/R2)
├── related.json         # Related-topics strip (mirror co-mention inference)
├── clues.txt            # Formatted clue text fed to the analysis agent
├── stock.html           # Study guide page          (generated)
├── cards.html           # Card editor page          (generated)
├── questions.html       # Source question viewer    (generated)
└── audio/               # Generated MP3s for score clues (music topics only)
```

Shared output: `output/topic_index.json` (master cross-reference index), `output/_categories/{unit}/` (unit overview pages), `output/_sets/{set_slug}/` (tournament sweep pages), `output/_answerlines/` (per-answerline metadata KB), `output/crossref_overrides.json` + `output/answerline_overrides.json` (adjudicated overrides).

Slugs are the full canonical name, lowercased, spaces → underscores (e.g. `samuel_beckett`, `bedrich_smetana`).

## Data Planes

- **Committed JSON** — analyses, cards, refs, overviews, overrides. The repo is the database of record for everything agent-authored.
- **qbreader mirror** (`mirror/qbreader.sqlite`, gitignored) — the entire qbreader question corpus, local. Seed from an official backup with `lib/mirror/import_backup.py`; keep fresh with `python lib/mirror/sync.py`. Design: `docs/mirror.md`.
- **R2** — `python lib/mirror/publish.py --upload` exports question-text artifacts (per-topic, per-unit, per-set) plus the semantic-search index to Cloudflare R2; site pages fetch them at view time (`lib/js/qdata.js` holds the base URL).
- **D1** (via `sync/` Worker) — per-user reader state for cross-device sync, behind GitHub OAuth.

## Workflows

Work is driven by Claude Code skills in `.claude/skills/`. The typical flows:

### Batch run (main workflow)

```bash
# 1. Check what's queued
python lib/queues/topic_queue.py summary

# 2. Initialize a batch (pops from global queues into queue/current_batch.json)
python lib/queues/batch_worker.py init "my-batch" --first 40 --second 10 --category Literature

# 3. Run the /batch skill (or launch analysis agents following /first-pass and /second-pass)

# 4. When agents finish:
python post_batch.py    # rebuilds topic index, runs deterministic crossref relink + inference,
                        # prints card-agent and crossref-agent prompts

# 5. After those agents finish:
./build.sh              # render everything + validate
```

`build.sh` runs `build.py`, which loads the analysis corpus once and runs every stage in one process: crossref index rebuild → stock/cards/questions/audio/score-review renders → dev dashboards → sweep rematch → overview pages → wiki index → reader → portal → `validate.py`. Default is incremental (mtime-based); pass `--force` to re-render everything.

### Single topic (manual)

```bash
# Fetch and parse clues (reads the local mirror; no network)
python lib/run.py "Smetana" "7,8,9,10" --outdir output/bedrich_smetana

# Analyze with the /first-pass skill, then rebuild:
./build.sh
```

**`lib/run.py` flags:** positional args are `topic`, `difficulties`, `min_year` (default 2012), `category`. `--mentions` fetches questions where the topic appears in the text but isn't the answer. `--outdir` targets the canonical slug directory (always use it).

### Queue management

```bash
python lib/queues/topic_queue.py add-first "Frida Kahlo" --category "Fine Arts"
python lib/queues/topic_queue.py add-second "Thomas Cole" --reason "sparse"
python lib/queues/topic_queue.py list | summary | status
python lib/queues/scan_redo.py            # find shallow analyses worth redoing
```

### Overviews and sweep sets

```bash
python lib/sweep/build_set.py "2022 ACF Winter"   # build a tournament sweep page
python lib/sweep/build_set.py --list-sets          # find exact qbreader set names
python lib/sweep/freq.py UNIT                      # frequency table + match status for a unit
python lib/sweep/author.py scaffold UNIT           # prep overview authoring (re-entrant)
python lib/sweep/author.py assemble UNIT           # sections.txt + intro.txt -> overview.json
```

See CLAUDE.md for the full command reference (crossref, embeddings, soundbites, publishing).

## Testing

Three suites, all run in CI before every deploy:

```bash
python tests/golden/run_golden.py        # golden render test: frozen corpus through the real
                                         #   renderers, diffed against tests/golden/expected/
                                         #   (--update to rebless after intended changes)
node tests/answer_checker/run_tests.js   # reader answer-judging logic
node tests/reader_facets/run_tests.js    # reader facet filtering
```

## Browsing

Open `index.html` directly in a browser, or serve the repo root with any static file server (e.g. `python -m http.server 8000`). Pages inline their CSS (shared scripts load from `lib/js/`; abcjs/sql.js/JSZip/Leaflet come from CDNs). Question text is fetched at view time from the public R2 bucket, so question panels and the reader need internet access even locally.

Generated files (`index.html`, `wiki.html`, `reader.html`, `output/**/*.html`, `dev/*_data.json`, `dev/score_clues_review.html`) are **not committed** — on a fresh clone, run `./build.sh` once to produce them.

## Deployment

Every push to `main` triggers `.github/workflows/deploy.yml`: it runs the three test suites, then `./build.sh` (with `validate.py` as a gate), and publishes the rendered site to GitHub Pages. Only `analysis.json`/`cards.json` and other source data get committed; the HTML is built in CI.

MP3 audio clips stay committed (they need fluidsynth + a soundfont to regenerate, which CI doesn't install); `render_audio.py` skips them gracefully during the CI build. The R2 artifacts are published separately via `lib/mirror/publish.py --upload`; the sync Worker deploys from `sync/` with wrangler.

## Requirements

- Python 3.10+ with `requests`, `genanki`, and `filelock` (`pip install -r requirements.txt`)
- Audio rendering only: `music21`, `fluidsynth`, `ffmpeg`, and a GM soundfont
- Embedding pipeline only (`lib/embed/`): `torch` and `sentence-transformers` (local Qwen3-Embedding-0.6B)
- Cross-platform: file locking uses `filelock` and all I/O is explicit UTF-8, so Windows, macOS, and Linux all work
