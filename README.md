# Stock Knowledge Tool

A quizbowl study tool that pulls clues from the [qbreader](https://www.qbreader.org/) database and generates structured, frequency-ranked study guides as HTML files. Vibe coded in ~2 hours, mostly using for myself.

## How It Works

1. **Fetch** — queries the qbreader API for all tossups/bonuses where a topic appears as an answerline
2. **Parse** — extracts individual clue sentences with metadata (power, giveaway, source)
3. **Analyze** — Claude reads the clues and groups them by work/subtopic, ranks by frequency, tags power vs. giveaway
4. **Render** — generates a self-contained HTML study guide with collapsible sections, embedded images (for visual topics), and Wikipedia links

## Quick Start

### Browse existing guides

Open `index.html` in a browser, or run a local server:

```bash
python -m http.server
# Opens at http://localhost:8000
```

### Generate a new guide (with Claude Code)

Paste this prompt into Claude Code:

```
I want to study [TOPIC]. Run `python3 lib/run.py "[TOPIC]" "[DIFFICULTIES]"` to fetch clues
(add "[CATEGORY]" as 4th arg if the topic name is ambiguous),
then read the output file and analyze it following docs/analysis_instructions.md.
Generate the HTML study guide using render.py and save the analysis JSON.
After the initial analysis, suggest recursive searches into important works/subtopics.
```

**Example prompts:**

```
I want to study Smetana. Run `python3 lib/run.py "Smetana" "7,8,9,10"` to fetch clues,
then read the output and analyze following docs/analysis_instructions.md.
Generate the HTML with render.py, save analysis JSON, and suggest deep dives.
```

```
I want to study "The Great Gatsby". Run `python3 lib/run.py "The Great Gatsby" "7,8,9,10"`
and analyze the clues. This is a literary work so organize by themes/characters.
```

```
I want to study the novel Indiana. Run `python3 lib/run.py "Indiana" "7,8,9,10" 2012 "Literature"`
and analyze the clues. Use the Literature category filter since "Indiana" also matches the US state.
```

```
I want to study Caravaggio. Run `python3 lib/run.py "Caravaggio" "7,8,9,10"` and analyze.
This is a visual artist so look up painting images from Wikimedia Commons using lib/images.py.
```

### Parameters

- **Difficulties**: 1-10 scale. Example:
  - `7,8,9,10` — college competitive (default recommendation)
- **Min year**: defaults to 2012 (older questions suck)
- **Category**: optional filter to restrict results to a qbreader category. Useful when a topic name is ambiguous (e.g., "Indiana" the novel vs. the state). Example:
  - `python3 lib/run.py "Indiana" "7,8,9,10" 2012 "Literature"`
  - Multiple categories: `"Literature,Fine Arts"`
  - Available categories: Literature, Fine Arts, History, Science, Religion, Mythology, Philosophy, Social Science, Geography, Current Events, Trash

## File Structure

```
stock/
├── render.py             # HTML study guide generator (tweak CSS here)
├── render_cards.py       # Card editor page generator
├── render_questions.py   # Source question page generator
├── rerender.py           # Re-render all stock guides from saved analysis JSON
├── build_index.py        # Index page generator (list + map views)
├── lib/                  # Pipeline internals (Claude runs these)
│   ├── fetch.py      # qbreader API data collection
│   ├── parse.py      # Clue extraction from raw data
│   ├── images.py     # Wikimedia Commons image lookup
│   └── run.py        # Combined fetch + parse runner
├── docs/
│   └── analysis_instructions.md   # How Claude should analyze clues
├── cache/            # Cached API responses (auto-generated, gitignored)
├── output/           # Generated guides and analysis data (gitignored)
│   ├── *_stock.html      # Study guides (open in browser)
│   └── *_analysis.json   # Saved analysis data for re-rendering
└── memory/           # Claude Code persistent memory (gitignored)
```

## Example Renders

### Thomas Cole (visual arts, with embedded paintings)
![Thomas Cole guide showing Course of Empire with embedded Wikimedia images, compact clue table with frequency counts and power/giveaway badges](output/thomas_cole_stock.html)

- 6 tossups, 15 bonuses analyzed
- 8 work sections including Course of Empire, The Oxbow, Voyage of Life
- Embedded paintings from Wikimedia Commons

### Kobo Abe (literature)

- 6 tossups, 15 bonuses analyzed
- 10 work sections from Woman in the Dunes to Kangaroo Notebook
- Recursive search into Woman in the Dunes added additional clues

### Smetana (music)

- 6 tossups, 11 bonuses at difficulty 7-10
- Works: Ma vlast, From My Life, The Bartered Bride, plus minor works and operas
- Clues ranked by frequency with example quotes from actual questions

## Workflow Tips

- **Start with answerline clues** — these are the richest (entire question is about your topic)
- **Recursive searches** — after initial analysis, search for major works as their own answerlines
- **Ambiguous topics** — use the category filter when a topic name collides with a more common answerline (e.g., "Indiana" the novel vs. the US state, "Sand" the material vs. George Sand). Even with category filtering, some irrelevant results may slip through — see the analysis instructions for how to handle these during analysis.
- **Text mentions** — for rare topics, also fetch text mentions: `fetch_text_mentions()` in lib/fetch.py
- **Visual topics** — use `lib/images.py` to find Wikimedia Commons images to embed
- **Re-render** — if you change the CSS in render.py, run `python rerender.py` to update all guides
- **Full rebuild** — after generating new guides, run all renderers:
  ```bash
  python3 rerender.py          # stock guide HTML pages
  python3 render_cards.py      # card editor HTML pages
  python3 render_questions.py  # source question HTML pages
  python3 build_index.py       # index page
  ```
