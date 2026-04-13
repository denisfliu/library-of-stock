# Stock Guide Project

Quizbowl study guide generator. Fetches clues from qbreader, analyzes them, generates Anki-style cards, and renders HTML study pages.

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
