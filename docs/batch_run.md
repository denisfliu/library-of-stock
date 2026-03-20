# Batch Guide Generation

How to launch agents to bulk-generate stock guides. Read this fully before starting.

## Quick Start

Give Claude Code a topic list and say:

> Launch batch agents for these topics following `docs/batch_run.md`. Category: [Literature/Fine Arts/Philosophy/Science]. Difficulties: 7,8,9,10.

Then provide the list (inline or as a file path).

## Batch Rules

### Sizing
- **10 topics per agent maximum.** Larger batches cause context exhaustion — later topics get shallow analysis.
- For **big topics** (20+ tossups like Picasso, Beethoven, Shakespeare): limit to **5 per agent**.

### Two-Phase Pipeline (VFA only)
- **Phase 1**: Analysis agents — fetch, analyze, render. **No image searching.**
- **Phase 2**: Run `python3 lib/fix_images.py` **once, sequentially** after all analysis agents finish. Then LLM reviews `cache/pending_images.json`.

Non-VFA categories (Literature, Philosophy, Science) don't need Phase 2.

### Category-Specific Instructions
Each agent must be told which category supplement to read:
- Literature: `docs/analysis_literature.md`
- Visual Fine Arts: `docs/analysis_vfa.md`
- Philosophy: `docs/analysis_philosophy.md`
- Science: `docs/analysis_science.md`

## Agent Prompt Template

Copy and customize this for each agent:

```
You are a stock guide generation agent. Process each topic autonomously. Do NOT ask for confirmation.

## YOUR BATCH
[list topics here, with known works/notes]

## INSTRUCTIONS
Read `docs/analysis_instructions.md` (core protocol) and `docs/analysis_[category].md` (category supplement).

## PIPELINE FOR EACH TOPIC

### Step 1: Fetch clues
python3 lib/run.py "TOPIC NAME" "7,8,9,10"

### Step 2: Read clues and create analysis JSON
Read output/{slug}_clues.txt. Create output/{slug}_analysis.json.

Key JSON structure:
{
  "topic": "Name",
  "summary": "...",
  "works": [
    {
      "name": "Work or Concept Name",
      "indicator": "Novel/Painting/Philosopher/Concept/Work",
      "description": "Mini-paragraph explaining this section with context and connections.",
      "clues": [
        {"clue": "...", "frequency": N, "tendency": "power/mid/giveaway", "examples": ["..."]}
      ]
    }
  ],
  "comprehensive_summary": "Multi-paragraph prose summary of everything the clues tell us.",
  "recursive_suggestions": [],
  "links": [{"text": "...", "url": "https://en.wikipedia.org/..."}],
  "category": "...", "subcategory": "...",
  "year": BIRTH_YEAR, "continent": "...", "country": "...",
  "tags": ["movement1"],
  "cards": [
    {"type": "basic", "indicator": "...", "front": "Indicator: clue", "back": "Answer", "work": "...", "frequency": N, "tags": []}
  ]
}

### Step 3: Self-check (MANDATORY)
After writing each JSON, verify ALL of these:
- [ ] More than 1 work section (if data mentions multiple works/ideas)
- [ ] Cards array is non-empty
- [ ] Every work/concept mentioned 3+ times has its own section
- [ ] Indicator field set on every work
- [ ] Description is a mini-paragraph (not a terse phrase)
- [ ] comprehensive_summary is real prose (multiple sentences)
- [ ] Metadata present: category, subcategory, year, continent, country, tags
If any check fails, fix before moving on.

### Step 4: Render
python3 -c "
from render import render_html
import json
with open('output/{slug}_analysis.json') as f:
    analysis = json.load(f)
render_html(analysis, 'output/{slug}_stock.html')
"
python3 render_cards.py
python3 build_index.py

### Step 5: Track
echo "TOPIC NAME" >> csvs/completed.txt

## IMPORTANT RULES
- Do NOT search for images. Images are handled separately after analysis.
- Do NOT use WebSearch for images or construct Wikimedia URLs.
- Process ALL steps for each topic before moving to the next.
- If 0 results, log as "NAME (no results)" in completed.txt and move on.
```

## Card Rules (include in prompt or reference)

- Indicator before colon: `Novel:`, `Painting:`, `Philosopher:`, `Concept:`, `Work:`, `Author:`, `Artist:`
- Back: `Work (Creator)` for work-specific, just `Creator` for general facts
- For philosophy: also use `Concept: description` → `Concept Name (Philosopher)`
- Never leak the answer on the front
- Skip pure identifier giveaways with no learnable content
- Tags: always empty `[]`
- Each card should test ONE fact (split semicolons into separate cards)

## After All Agents Complete

```bash
# 1. Final render
python3 rerender.py
python3 render_cards.py
python3 render_questions.py
python3 build_index.py

# 2. For VFA topics only — image pipeline
python3 lib/fix_images.py                    # sequential, respects rate limits
# Then review cache/pending_images.json      # LLM approves/rejects ambiguous images
python3 lib/verify_images.py                 # verify all URLs return 200

# 3. Quality audit
python3 -c "
import json
from pathlib import Path
for f in sorted(Path('output').glob('*_analysis.json')):
    with open(f) as fh:
        data = json.load(fh)
    works = len(data.get('works', []))
    cards = len(data.get('cards', []))
    desc_ok = all(len(w.get('description','')) > 50 for w in data.get('works',[]) if 'General' not in w.get('name',''))
    if works <= 1 or cards == 0 or not desc_ok:
        print(f'NEEDS REVIEW: {data.get(\"topic\",\"?\")} ({works}w, {cards}c, desc={desc_ok})')
"
```

## Pitfalls from Previous Runs

These mistakes were made before — do NOT repeat them:

1. **Shallow analyses**: Agents with 60+ topics crammed everything into single sections with no cards. **Fix**: 10 topics max per agent.
2. **Guessed image URLs**: Agents constructed Wikimedia URLs that were 404s or showed the wrong artist's painting. **Fix**: No image searching during analysis. Use `lib/fix_images.py` after.
3. **Rate limiting**: Parallel agents all hitting Wikimedia caused hours-long blocks. **Fix**: Image search is always sequential, never in parallel agents.
4. **Terse descriptions**: Agents wrote one-line descriptions like "His most famous work." **Fix**: Self-check requires mini-paragraph descriptions.
5. **Multi-clue cards**: Cards with 3+ semicolons packing multiple facts. **Fix**: Self-check — each card should test one fact.
6. **Missing question pages**: Agents forgot to run `render_questions.py`. **Fix**: Included in post-run checklist.
7. **Wrong category for VFA**: Some agents tagged subcategory as "Visual Arts" instead of "Visual Fine Arts". **Fix**: Reference `docs/categories.md`.

## Permissions

Ensure `.claude/settings.local.json` allows:
```json
{
  "permissions": {
    "allow": ["Bash(*)", "Edit", "Write"]
  }
}
```
