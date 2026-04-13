---
name: first-pass
description: Run a first-pass analysis on a quizbowl topic — fetch clues, analyze, generate cards, and render.
arguments:
  - name: topic
    description: "Topic name (e.g., \"Smetana\", \"The Oxbow\")"
  - name: category
    description: "Optional category override. Auto-detected from queue if omitted."
---

# First Pass Analysis

You are creating a **new analysis from scratch** for the topic "$ARGUMENTS.topic".

## Step 1: Determine Category

If a category was provided ("$ARGUMENTS.category"), use it. Otherwise, check the queue:
```bash
python3 lib/queue/topic_queue.py summary
```
Match the topic to its category. Reference `categories.md` (project root) for valid category/subcategory names.

## Step 2: Derive Slug

Use the **full canonical name** of the person or topic — not a short name or last name alone.
`slug = full_canonical_name.lower().replace(" ", "_")`

- People with unique single names keep them: "Aristotle" -> `aristotle`, "Heraclitus" -> `heraclitus`
- Everyone else uses their full name: "Corot" -> `jean-baptiste-camille_corot`, "Smetana" -> `bedrich_smetana`
- Examples: "Samuel Beckett" -> `samuel_beckett` | "Bela Bartok" -> `bela_bartok` | "Bong Joon-ho" -> `bong_joon-ho`

The search term (Step 3) can still be the short name, but the slug and `topic` field must use the full name.

## Step 3: Fetch Clues

```bash
python3 lib/run.py "SEARCH TERM" "7,8,9,10" --outdir output/{slug}
```
Use the **minimally identifiable name** — the shortest form qbreader indexes on (usually last name). But set the `topic` field in the JSON to the **full proper name** from the answerline.

### Expand if sparse
If fewer than **10 total tossups + bonuses**:
```bash
python3 lib/run.py "SEARCH TERM" "5,6,7,8,9,10" --outdir output/{slug}
python3 lib/run.py "SEARCH TERM" "5,6,7,8,9,10" --mentions --outdir output/{slug}
```

## Step 4: Read Category Supplement

**Before analyzing clues**, read the appropriate category supplement skill:
- Literature -> `/literature`
- Fine Arts (VFA subcategory) -> `/vfa`
- Fine Arts (AFA subcategory) -> `/afa`
- Philosophy -> `/philosophy`
- Science -> `/science`

These contain category-specific sectioning, indicator, and processing rules that affect how you structure the analysis.

## Step 5: Analyze Clues

Read `output/{slug}/clues.txt` and all cache JSONs. Apply category supplement rules throughout.

### Filter irrelevant results
Scan all tossups and bonuses. Discard any clearly about a different topic (check answerline). Note how many discarded.

### Identify what the topic is (from clues only)
Brief summary based solely on how clues describe it.

### Identify key works / subtopics
**Systematically count references per work/subtopic across ALL clues.** Count every mention. Apply sectioning rules from CLAUDE.md and category supplement.

For creators: list major works from clues, group clues by work.
For non-creators: identify major themes, group by theme.

### Rank by frequency
Within each section, identify individual clues. Group same-clue-different-wording together. Count occurrences. Rank most to least common.

### Format the output
For each work/subtopic:
1. Work name, brief identification, `indicator` field (e.g., `"Play"`, `"Novel"`, `"Painting"`)
2. Clues ranked by frequency with: clear statement, count as number, 1-2 example quotes
3. Mark power vs. giveaway clues

## Step 6: Write analysis.json

Create `output/{slug}/analysis.json`.

Required fields: `topic`, `summary`, `works`, `comprehensive_summary`, `cards`, `category`, `subcategory`, `genre`, `year`, `continent`, `country`, `tags`, `links`, `recursive_suggestions`.

For `recursive_suggestions`: identify works/subtopics that deserve their own deep dive. Flag ambiguous names and recommend category filters.

Reference `output/emily_carr/analysis.json` for formatting if needed.

## Step 7: Generate Cards

Follow `/cards` skill rules to generate the `cards` array inline. Every clue with specific learnable content gets a card.

## Step 8: Self-Check (MANDATORY)

- [ ] `summary` filled (concise blurb — NOT empty)
- [ ] More than 1 work section if clues mention multiple works/ideas
- [ ] Every work mentioned 3+ times has its own section
- [ ] `indicator` set on every work; description is a mini-paragraph
- [ ] `comprehensive_summary` is real prose
- [ ] All metadata present: category, subcategory, genre, year, continent, country, tags

## Step 9: Render

```bash
python3 -c "from lib.render.render import render_html; import json; f=open('output/{slug}/analysis.json'); a=json.load(f); render_html(a, 'output/{slug}/stock.html')"
```

## Data Fetching Rules

- **Always** use `lib/run.py` to fetch clues — never write clues.txt manually. The API cache JSON is required for the questions page renderer.
- **Always** pass `--outdir output/{slug}` so cache files land in the right place.
- If 0 results: note "(no results)" and exit.
