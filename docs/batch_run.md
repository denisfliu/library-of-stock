# Batch Guide Generation

How to launch agents to bulk-generate stock guides. Read this fully before starting.

## Quick Start

Tell the controller (Claude Code conversation):

> Start a batch with N first pass agents and M second pass agents.

The controller will:
1. Create `queue/current_batch.json` from the global queues
2. Build agent prompts using `lib/prompt_builder.py`
3. Launch N+M agents with assembled prompts
4. Monitor agents, relaunch when one finishes (if queue not empty)
5. After all done, run `python3 post_batch.py` (rebuilds index, runs deterministic backfill, prints Sonnet prompt)
6. Launch the Sonnet crossref agent with the printed prompt
7. Run `./build.sh`

## Building Agent Prompts

Agent prompts are assembled programmatically from building blocks in `docs/`:

| Block | Content |
|---|---|
| `analysis_core.md` | Universal rules: filtering, sectioning, ranking, formatting, summary, metadata, constraints |
| `analysis_first_pass.md` | First-pass-specific: recursive search suggestions |
| `analysis_second_pass.md` | Second-pass-specific: load existing, fetch additional data, merge rules |
| `analysis_cards.md` | Card generation rules and quality standards |

Category supplements (in `docs/`): `analysis_literature.md`, `analysis_vfa.md`, `analysis_philosophy.md`, `analysis_science.md`

### Concatenation order

```
First-pass:  analysis_core → analysis_first_pass → category_supplement → analysis_cards
Second-pass: analysis_core → analysis_second_pass → category_supplement → analysis_cards
```

### Generate a prompt

```bash
python3 lib/prompt_builder.py first --category Literature
python3 lib/prompt_builder.py second --category Philosophy
python3 lib/prompt_builder.py first --category "Fine Arts" --max-topics 5
```

The builder reads blocks, concatenates in order, renumbers steps sequentially, and wraps in the agent loop template. The full protocol text is inlined into the prompt — agents never need to read doc files.

## Batch Rules

### Sizing
- **First pass: 10 topics per agent maximum.** Larger batches cause context exhaustion — later topics get shallow analysis.
- **Second pass: 5 topics per agent maximum.** Enrichment is more context-intensive.
- For **big topics** (20+ tossups like Picasso, Beethoven, Shakespeare): limit to **5 per agent** (first pass) or **3 per agent** (second pass).

### Two-Phase Pipeline (VFA only)
- **Phase 1**: Analysis agents — fetch, analyze, render. **No image searching.**
- **Phase 2**: Run `python3 lib/fix_images.py` **once, sequentially** after all analysis agents finish. Then LLM reviews `cache/pending_images.json`.

Non-VFA categories (Literature, Philosophy, Science) don't need Phase 2.

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
Generate the prompt and launch agents:
```bash
python3 lib/prompt_builder.py first --category Literature
# Copy output as the agent prompt
```
Each agent pops from the shared batch queue filtered by its category and pass type.
When an agent finishes (max topics or queue empty), launch a replacement if the queue still has items.

### 4. Monitor
Open `progress.html` (via `./serve.sh`) — auto-refreshes every 5s showing queued/in-progress/completed.

### 5. After all agents complete

```bash
# 1. Run post_batch.py — rebuilds cross-ref index AND prints the Sonnet agent prompt
python3 post_batch.py

# 2. Launch the Sonnet crossref backfill agent using the prompt post_batch.py printed.
#    The agent adds cross_refs to all completed topics, then runs ./build.sh.

# 3. After the Sonnet agent finishes, run all renderers:
./build.sh

# 4. For VFA topics only — image pipeline
python3 lib/fix_images.py                    # sequential, respects rate limits
# Then review cache/pending_images.json      # LLM approves/rejects ambiguous images
python3 lib/verify_images.py                 # verify all URLs return 200

# 5. Quality audit
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

1. **Shallow analyses**: Agents with 60+ queries crammed everything into single sections with no cards. **Fix**: 10/5 items to query max per agent (1st pass / 2nd pass).
2. **Guessed image URLs**: Agents constructed Wikimedia URLs that were 404s or showed the wrong artist's painting. **Fix**: No image searching during analysis. Use `lib/fix_images.py` after.
3. **Rate limiting**: Parallel agents all hitting Wikimedia caused hours-long blocks. **Fix**: Image search is always sequential, never in parallel agents.
4. **Terse descriptions**: Agents wrote one-line descriptions like "His most famous work." **Fix**: Self-check requires mini-paragraph descriptions.
5. **Multi-clue cards**: Cards with 3+ semicolons packing multiple facts. **Fix**: Self-check — each card tests one fact.
6. **Missing question pages**: Agents forgot to render. **Fix**: Always run `./build.sh` after the batch — it covers all four renderers.
7. **Wrong category for VFA**: Some agents tagged subcategory as "Visual Arts" instead of "Visual Fine Arts". **Fix**: Reference `docs/categories.md`.
8. **Empty summary field**: Agents wrote comprehensive_summary but left the "summary" field empty, causing blank blurbs on the page. **Fix**: "summary" is now in the required fields list and self-check.
9. **Forgot cross-ref backfill**: Controller skipped the Sonnet cross-ref step after agents finished. **Fix**: Run `python3 post_batch.py` immediately when the last agent finishes — it automates index rebuild + deterministic backfill and prints the Sonnet prompt. Don't report "done" until all steps complete.
10. **verify_images.py runs multiple times**: The script silently backgrounds itself when not in a TTY, so the Bash tool returns immediately with a background job ID. **Fix**: Run it once, then wait for the background task notification — do NOT re-run if the shell returns immediately. Check the task output file when notified.

## Permissions

Ensure `.claude/settings.local.json` allows:
```json
{
  "permissions": {
    "allow": ["Bash(*)", "Edit", "Write"]
  }
}
```
