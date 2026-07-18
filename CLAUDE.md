# Stock Guide Project

Quizbowl study guide generator. Fetches clues from qbreader, analyzes them, generates Anki-style cards, and renders HTML study pages.

## Orientation (read this before exploring)

- `output/{slug}/analysis.json` is the **source of truth** for every topic. All HTML is generated from it — **never read or edit generated `.html` files** (there are ~2,500 of them); edit the JSON or the renderer, then run `./build.sh`.
- Renderers: `lib/render/render.py` (stock.html), `lib/render/render_cards.py` (cards.html), `lib/render/render_questions.py` (questions.html), `lib/build_index.py` (index.html). Each is a Python file emitting one big HTML template.
- Pipeline: `lib/pipeline/fetch.py` (reads the local qbreader mirror) → `lib/pipeline/parse.py` (clue extraction) → `lib/run.py` (CLI wrapper producing `clues.txt`).
- **qbreader mirror** (`mirror/qbreader.sqlite`, gitignored, ~860 MB): the ENTIRE qbreader database, local. All fetch.py queries run against it offline — the live API is used only by `lib/mirror/sync.py` to pull newly added sets. Seed/re-seed from official backups via `lib/mirror/import_backup.py`. Design + freshness model: `docs/mirror.md`.
- Queues: `lib/queues/topic_queue.py` (global first/second-pass queues), `lib/queues/batch_worker.py` (per-batch claim/complete). State lives in `queue/*.json`.
- Cross-refs: `lib/crossref/crossref.py` rebuilds `output/topic_index.json`; `lib/crossref/relink.py` re-derives mechanical links for ALL topics (tiered `lib/crossref/linker.py`; ambiguous surfaces queue in `dev/crossref_candidates.json`); the `/crossref` skill only ADJUDICATES those into `output/crossref_overrides.json`; `lib/crossref/infer.py` builds question-text co-mention `related.json` (the Related strip). Refs carry `source` provenance. Methodology: `docs/crossref.md`.
- Agent workflows are skills in `.claude/skills/<name>/SKILL.md`: `/batch`, `/first-pass`, `/second-pass`, `/cards`, `/crossref`, plus category supplements (`/literature`, `/vfa`, `/afa`, `/philosophy`, `/science`). These are the single source of truth for agent instructions.
- `lib/common.py` provides `ROOT`/`OUTPUT_DIR`/`QUEUE_DIR`/`CATEGORIES_DIR`/`SETS_DIR`/`OVERRIDES_FILE`, UTF-8 stdio, and `file_lock`. Every entry script imports it — new scripts should too.
- **Unit overview pages** (`output/_categories/{unit}/`, one per `lib/units.py` unit): agent-authored `sections.txt` + `intro.txt` are assembled into `overview.json` by `lib/sweep/author.py` (scaffold/assemble; format documented in its docstring — `> ` blurbs, `- ` nesting, `=` variant merge, `->` canonical topic). `lib/sweep/capture_questions.py` captures the unit's full question set → per-entry expandable question panels; `soundbites.json` (curated via `lib/audio/soundbites.py`, Wikimedia Commons recordings) powers ♪ audio players. Rendered by `lib/render/build_overviews.py`. Notes style: 10-20 words, relations + key works, no editorializing; consult questions.json for ambiguous/common-link answerlines.
- **Sweep sets** (`output/_sets/{set_slug}/`): `lib/sweep/build_set.py "2022 ACF Winter"` fetches a whole tournament, matches every tossup/bonus-part answerline via `lib/sweep/matcher.py` (override → exact → alias tiers, category-gated; overrides in `output/answerline_overrides.json`, keys from `lib/sweep/answerlines.normalize`), writes `set.json` + reviewable `report.json`, renders interactive `sweep.html`. `--all --rematch-only` re-matches without network (red links self-heal to blue as topics get pages).
- **Shared map** (`lib/js/map_view.js`): any page mounts it (theme.LEAFLET_TAGS + `initMapView`); one pin per location (country centroids), click → panel grouped by category / year-sorted, facet chips for group + era filtering. Live on overview + sweep pages.
- `lib/units.py` is the canonical unit registry (40 units) + `SUBCATEGORY_ALIASES` drift map; classify guides via `unit_for_guide()`, never raw subcategory strings.

## Common commands

```bash
./build.sh                                  # incremental render of everything + validate
./build.sh --force                          # full re-render
python lib/validate.py                     # health check on all analysis JSONs
python lib/queues/topic_queue.py summary    # queue counts by category
python lib/queues/batch_worker.py status    # current batch progress
python post_batch.py                       # after a batch: rebuild index + print agent prompts
python lib/sweep/freq.py UNIT               # frequency table + match status for a unit
python lib/sweep/author.py scaffold UNIT    # prep/refresh overview authoring (re-entrant)
python lib/sweep/author.py assemble UNIT    # sections.txt + intro.txt -> overview.json
python lib/sweep/capture_questions.py UNIT  # capture unit's questions for the page
python lib/render/build_overviews.py        # render overview pages (--force, --unit)
python lib/sweep/build_set.py --list-sets   # find exact qbreader set names
python lib/mirror/sync.py                   # pull new sets from qbreader into the mirror
python lib/mirror/publish.py --upload       # export + upload reader data artifacts to R2
python lib/crossref/relink.py               # re-derive mechanical cross_refs (+ candidates queue)
python lib/crossref/infer.py                # related-topics from question co-mentions (mirror)
python lib/audio/soundbites.py search "..." # find Commons audio for soundbites.json
python lib/embed/embed_corpus.py tossups|bonuses|topics  # (re)embed into mirror/embeddings.sqlite (resumable)
python lib/embed/build_search_index.py      # stage online clue-search index for R2 (--eval-only to check recall)
python tests/golden/run_golden.py           # golden render test (--update to rebless)
node tests/answer_checker/run_tests.js      # reader answer-judging tests
node tests/reader_facets/run_tests.js       # reader facet-filtering tests
node tests/reader_audio/run_tests.js        # reader read-aloud queue restriction
```

## Deferred improvements (roadmap for future sessions)

- **July 2026 audit cleanup — remaining items** (junk removal, cache plumbing, one-shot relocation to `dev/oneshots/`, and nav/search-nav CSS hoisting into `theme.py` are done): (1) unify the answerline normalizers (`sweep/answerlines.normalize` vs `mirror/publish.norm_ans`, both mirroring reader.js `normAns`) and the era-bucket thresholds (`sweep/wikidata.py` / `sweep/answerline_kb.py` / `reader.js`); (2) extract the embedded client JS in `build_index.py` and `render_cards.py` into `lib/js/` files; (3) add a single local test runner wrapping the three suites; (4) consider renaming `lib/questions_store.py` (now just live refs helpers) to stop signaling the retired store.
- **Template consolidation**: the renderers embed large HTML/CSS strings; shared CSS lives in `lib/render/theme.py`. Long-term, move page templates to Jinja2 files.
- **`getCardImages` is triplicated** — `lib/render/render_cards.py` (Python `_synthesize_image_cards`), its embedded JS, and `lib/js/anki_export.js`. Any card-image schema change needs all three.
- **Broaden the golden render test**: `tests/golden/` (run in CI before every deploy) covers stock/cards/questions/overview/sweep/topic_index. Not yet covered: `index.html` (embeds stock.html mtimes — needs date normalization) and the dev dashboards.
- **Wikimedia batching**: `lib/images/` fetches thumbnails one filename at a time; the Commons API accepts pipe-joined `titles=`.
- ~~Shared question store~~: built July 2026, then **retired later that month** — question text now lives only in the mirror; committed refs (`questions_ref.json`, sweep row ids, unit `{answerline: [{id, part}]}`) resolve at publish time. History: `docs/question_store.md`.
- ~~Full qbreader mirror~~: **done July 2026** — `mirror/qbreader.sqlite` + `lib/mirror/` (importer, sync, local query engine, R2 publisher); fetch.py is mirror-backed, API used only for new-set sync. Site pages fetch question text from R2 at view time. See `docs/mirror.md`.
- ~~Custom question reader~~: **live July 2026** — `reader.html` (`lib/render/build_reader.py` + `lib/js/reader.js`), R2 data plane, OAuth sync (`sync/`).
- **Reader online rooms** (multiplayer): tabled; full design assessment in `docs/rooms.md` (Durable Object per room on the existing sync Worker, deterministic clock protocol, reusable answer checker).
- **Map v2**: real `coordinates` metadata — pins currently sit at country centroids (`lib/js/map_view.js`; country click-panel and category/era facets exist). With real coords, add city-level spread and pass `coords` per item (component already supports it).
- **AFA soundbites**: extend the Commons soundbites (done for opera) to Auditory Fine Arts when that unit is authored. First add API pacing to `lib/audio/soundbites.py` searches (mirror `lib/images/` `API_DELAY`) — a curation agent burst got 429-throttled by Wikimedia in July 2026.
- **Score-clue synthesis quality**: the ABC→MP3 synthesizations behind `score_clues` are correct when they faithfully transcribe the specific clued passage, but many currently don't (56 clips across 35 topics; the 56 `[NEEDS_ABC_REVIEW]` validate warnings are related) — audit/fix the transcriptions. Once trustworthy, they're ALSO worth surfacing on AFA overview pages attached to work entries (they demonstrate the actual clued passage), alongside — not instead of — the Commons famous-excerpt soundbites (`lib/audio/soundbites.py`).
- **Next-button ordering**: currently chronological-by-year within subcategory; science/philosophy concepts have no year. When yearless topics grow, switch to tag-based clustering so related concepts are adjacent.
- **Digest clustering for single-answerline figures**: `clues_digest.txt` groups by answerline, which works for creators (works = answerlines) but degenerates for History figures where every clue shares one answerline — the July 2026 Andrew Jackson pilot had to hand-cluster ~60 flat `[1x]` sentences from clues.txt. Consider a fact-level clustering pass in the digest for such topics.

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
- `output/{slug}/questions_ref.json` — qbreader `_id` refs backing the topic's questions.html
- `mirror/qbreader.sqlite` — full local qbreader mirror (gitignored; all question text; see `docs/mirror.md`)
- `output/{slug}/stock.html` — rendered study page
- `output/topic_index.json` — master index of all topics/works
- `queue/` — all queue JSON files (never `lib/queues/`)
- `categories.md` — valid qbreader category/subcategory names
