# Batch Guide Generation

How to launch agents to bulk-generate stock guides. Read this fully before starting.

## Quick Start

Tell the controller (Claude Code conversation):

> Start a batch with N first pass agents and M second pass agents.

The controller will:
1. Create `queue/current_batch.json` from the global queues
2. Launch N+M agents that pull from the shared batch queue
3. Monitor agents, relaunch when one finishes (if queue not empty)
4. After all done, launch a Sonnet agent for cross-ref backfill
5. Run final renders

## Batch Rules

### Sizing
- **10 topics per agent maximum.** Larger batches cause context exhaustion — later topics get shallow analysis.
- For **big topics** (20+ tossups like Picasso, Beethoven, Shakespeare): limit to **5 per agent**.

### Two-Phase Pipeline (VFA only)
- **Phase 1**: Analysis agents — fetch, analyze, render. **No image searching.**
- **Phase 2**: Run `python3 lib/fix_images.py` **once, sequentially** after all analysis agents finish. Then LLM reviews `cache/pending_images.json`.

Non-VFA categories (Literature, Philosophy, Science) don't need Phase 2.

### Required Reading for Agents
Every agent must read these before starting:
1. **`docs/analysis_instructions.md`** — core protocol (steps, JSON format, card rules, cross-refs)
2. **Category supplement** — category-specific sectioning, indicators, and rules:
   - Literature: `docs/analysis_literature.md`
   - Visual Fine Arts: `docs/analysis_vfa.md`
   - Philosophy: `docs/analysis_philosophy.md`
   - Science: `docs/analysis_science.md`

## First Pass Agent Prompt Template

Each agent is assigned a category and only pops topics from that category. The controller specifies the category when launching the agent.

```
You are a stock guide generation agent for [CATEGORY] topics. Process topics from the shared batch queue. Do NOT ask for confirmation.

## INSTRUCTIONS
Read `docs/analysis_instructions.md` (core protocol) and `docs/analysis_[CATEGORY].md` (category supplement).

## LOOP: Pop and process topics (up to 10)

### Step 0: Pop next topic
Run: python3 lib/batch_worker.py pop first --category "[CATEGORY]"
If output is "EMPTY", you are done — exit.
Parse the JSON output to get the topic name and metadata.

### Step 1: Fetch clues
Use the minimally identifiable search term (usually last name or common name):
python3 lib/run.py "SEARCH TERM" "7,8,9,10"
Example: search "Falconet" not "Étienne Maurice Falconet"

### Step 2: Read clues and create analysis JSON
Read output/{slug}_clues.txt. Create output/{slug}_analysis.json.
IMPORTANT: Set "topic" to the FULL proper name (from the answerline), not the search term.

### Step 3: Self-check (MANDATORY)
- [ ] More than 1 work section (if data mentions multiple works/ideas)
- [ ] Cards array is non-empty
- [ ] Every work/concept mentioned 3+ times has its own section
- [ ] Indicator field set on every work
- [ ] Description is a mini-paragraph (not a terse phrase)
- [ ] comprehensive_summary is real prose (multiple sentences)
- [ ] Metadata present: category, subcategory, year, continent, country, tags
- [ ] Each card tests ONE fact

### Step 4: Render
python3 -c "from render import render_html; import json; f=open('output/{slug}_analysis.json'); a=json.load(f); render_html(a, 'output/{slug}_stock.html')"
python3 render_cards.py

### Step 5: Mark complete
python3 lib/batch_worker.py complete "FULL TOPIC NAME"
echo "FULL TOPIC NAME" >> csvs/completed.txt
python3 lib/topic_queue.py remove-first "FULL TOPIC NAME"

Then go back to Step 0 and pop the next topic. Stop after 10 topics or when queue is empty.
```

## IMPORTANT RULES (include in all agent prompts)
- Do NOT search for images. Images are handled separately after analysis.
- Do NOT use WebSearch for images or construct Wikimedia URLs.
- Process ALL steps for each topic before popping the next.
- If 0 results, mark complete with "(no results)" and move on.
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
# 1. Rebuild cross-ref index
python3 lib/crossref.py

# 2. Cross-reference backfill (use Sonnet agent — cheaper, equally effective)
# Launch ONE Sonnet agent with all newly created + modified topics:
# Agent(model="sonnet", prompt="Read docs/crossref_backfill.md. Add cross_refs to these topics: [list]")
# This replaces per-topic cross-ref work that Opus agents used to do.

# 3. Final render
python3 rerender.py
python3 render_cards.py
python3 render_questions.py
python3 build_index.py

# 3. For VFA topics only — image pipeline
python3 lib/fix_images.py                    # sequential, respects rate limits
# Then review cache/pending_images.json      # LLM approves/rejects ambiguous images
python3 lib/verify_images.py                 # verify all URLs return 200

# 4. Quality audit
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

## Controller Workflow

### 1. Check queues
```bash
python3 lib/topic_queue.py summary
```

### 2. Initialize batch
```bash
# Pull from global queues into the shared batch queue
python3 lib/batch_worker.py init "batch-name" --first 40 --second 10 --category Literature
```
This pops items from the global queues and creates `queue/current_batch.json`.
Use `--category` to scope to one category, or omit for mixed batches.

### 3. Launch agents
Launch N agents per category. Each agent pops from the shared batch queue filtered by its category and pass type. When an agent finishes (10 topics or queue empty), launch a replacement if the queue still has items.

### 4. Monitor
Open `progress.html` (via `./serve.sh`) — auto-refreshes every 5s showing queued/in-progress/completed.

### 5. After all agents complete
Run Sonnet cross-ref backfill, then final renders (see "After All Agents Complete" section).

## Second Pass Agent Prompt Template

Each second pass agent is also assigned a category.

```
You are a second-pass enrichment agent for [CATEGORY] topics. Do NOT ask for confirmation.

## INSTRUCTIONS
Read `docs/second_pass.md` (enrichment protocol), `docs/analysis_instructions.md` (core rules),
and `docs/analysis_[CATEGORY].md` (category supplement).

## LOOP: Pop and process topics (up to 10)

### Step 0: Pop next topic
Run: python3 lib/batch_worker.py pop second --category "[CATEGORY]"
If output is "EMPTY", you are done — exit.
Parse the JSON output to get the topic name and slug.

### Step 1-6: Follow docs/second_pass.md
1. Load existing analysis JSON
2. If sparse, run: python3 lib/run.py "TOPIC" "5,6,7,8,9,10" --mentions
3. For each major work, run: python3 lib/run.py "WORK NAME" "7,8,9,10"
4. Merge new clues into existing analysis (preserve all existing data)
5. Mark complete: python3 lib/batch_worker.py complete "TOPIC"
6. Remove from queue: python3 lib/topic_queue.py remove-second "TOPIC"
7. Render

Then go back to Step 0. Stop after 10 topics or when queue is empty.
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
