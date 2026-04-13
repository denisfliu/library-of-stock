# Batch Guide Generation

How to launch agents to bulk-generate stock guides. Read this fully before starting.

## Quick Start

Tell the controller (Claude Code conversation):

> Start a batch with N parallel agents for first pass / second pass.

The controller will:
1. Create `queue/current_batch.json` from the global queues
2. Build agent prompts using `lib/pipeline/prompt_builder.py`
3. Launch N agents, each processing one topic and exiting
4. Relaunch agents as they finish until the queue is empty
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
python3 lib/pipeline/prompt_builder.py first --category Literature
python3 lib/pipeline/prompt_builder.py second --category Philosophy
python3 lib/pipeline/prompt_builder.py first --category "Fine Arts" --max-topics 5
```

The builder reads blocks, concatenates in order, renumbers steps sequentially, and wraps in the agent loop template. The full protocol text is inlined into the prompt — agents never need to read doc files.

## Batch Rules

### Sizing
- **One topic per agent.** Each agent pops one topic, processes it fully, and exits.
- Launch as many parallel agents as topics you want to process simultaneously.
- This eliminates context accumulation (later topics getting shallow analysis) and reduces API cost.

### Two-Phase Pipeline (VFA only)
- **Phase 1**: Analysis agents — fetch, analyze, run `fix_images.py --slug {slug}`, render. The file lock serializes image lookups across parallel agents automatically.
- **Phase 2**: After all agents finish, run `python3 lib/images/fix_images.py` once to catch stragglers (works that went pending or were added late). Then LLM reviews `cache/pending_images.json`.

Known failures are cached — `fix_images.py` skips them by default. Use `--retry` to re-try them.

Non-VFA categories (Literature, Philosophy, Science) don't need Phase 2.

## Queue File Locations

All queue data files live in `queue/` at the project root — **never** in `lib/queue/`:

| File | Purpose |
|---|---|
| `queue/queue_first_pass.json` | Global first-pass backlog |
| `queue/queue_second_pass.json` | Global second-pass backlog |
| `queue/current_batch.json` | Active batch state (read by progress page) |

`lib/queue/` contains only Python source files (no `.json`). The scripts use `ROOT = Path(__file__).parent.parent.parent` to reach the project root.

## Controller Workflow

### 1. Check queues
```bash
python3 lib/queue/topic_queue.py summary
```

### 2. Initialize batch
```bash
# Pull from global queues into the shared batch queue
python3 lib/queue/batch_worker.py init "batch-name" --first 40 --second 10 --category Literature
```
This pops items from the global queues and creates `queue/current_batch.json`.
Use `--category` to scope to one category, or omit for mixed batches.

### 3. Launch agents
Generate the prompt and launch agents:
```bash
python3 lib/pipeline/prompt_builder.py first --category Literature
# Copy output as the agent prompt
```
Each agent pops from the shared batch queue filtered by its category and pass type.
When an agent finishes (max topics or queue empty), launch a replacement if the queue still has items.

### 4. Monitor
Open `progress.html` (via `./serve.sh`) — auto-refreshes every 5s showing queued/in-progress/completed.

### 5. After all agents complete

```bash
# 1. Run post_batch.py — rebuilds cross-ref index and prints two agent prompts
python3 post_batch.py

# 2. Launch ALL agents printed by post_batch.py IN PARALLEL:
#    - Card agents (step 3/4): each generates cards for 3-5 topics
#    - Sonnet crossref agent (step 4/4): adds cross_refs to all completed topics
#    Launch them all at the same time — they write to different fields and don't conflict.

# 3. After BOTH agents finish, run all renderers:
./build.sh

# 4. For VFA topics only — image pipeline
python3 lib/images/fix_images.py             # sequential, respects rate limits
# Then review cache/pending_images.json      # LLM approves/rejects ambiguous images
python3 lib/images/verify_images.py          # verify all URLs return 200

# 5. Quality audit
python3 -c "
import json
from pathlib import Path
for f in sorted(Path('output').glob('*/analysis.json')):
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

1. **Shallow analyses**: Agents with 60+ queries crammed everything into single sections with no cards. **Fix**: One topic per agent.
2. **Guessed image URLs**: Agents constructed Wikimedia URLs that were 404s or showed the wrong artist's painting. **Fix**: Always use `fix_images.py --slug {slug}` — never construct URLs manually.
3. **Rate limiting**: Parallel agents all hitting Wikimedia caused hours-long blocks. **Fix**: The file lock in `images.py` serializes all API calls automatically — always go through `fix_images.py`, never call the Wikimedia API directly.
4. **Terse descriptions**: Agents wrote one-line descriptions like "His most famous work." **Fix**: Self-check requires mini-paragraph descriptions.
5. **Multi-clue cards**: Cards with 3+ semicolons packing multiple facts. **Fix**: Self-check — each card tests one fact.
6. **Missing question pages**: Agents forgot to render. **Fix**: Always run `./build.sh` after the batch — it covers all four renderers.
7. **Wrong category for VFA**: Some agents tagged subcategory as "Visual Arts" instead of "Visual Fine Arts". **Fix**: Reference `docs/categories.md`.
8. **Empty summary field**: Agents wrote comprehensive_summary but left the "summary" field empty, causing blank blurbs on the page. **Fix**: "summary" is now in the required fields list and self-check.
9. **Forgot post-batch agents**: Controller skipped the card agent or Sonnet crossref step after analysis agents finished. **Fix**: Run `python3 post_batch.py` immediately when the last analysis agent finishes — it prints both the card agent prompt and the Sonnet crossref prompt. Launch both in parallel. Don't report "done" until all steps complete.
10. **verify_images.py runs multiple times**: The script silently backgrounds itself when not in a TTY, so the Bash tool returns immediately with a background job ID. **Fix**: Run it once, then wait for the background task notification — do NOT re-run if the shell returns immediately. Check the task output file when notified.
11. **Queue JSON written to `lib/queue/` instead of `queue/`**: After the `lib/` refactor, `ROOT` in the queue scripts briefly pointed to `lib/` instead of the project root, silently writing data to `lib/queue/*.json` while the real files (and the progress page) lived in `queue/`. **Fix**: Scripts now use `.parent.parent.parent` for ROOT. Queue data belongs exclusively in `queue/` — there should be no `.json` files in `lib/queue/`.
12. **Subitem query results scattered into top-level `output/` dirs**: Second-pass agents ran `python3 lib/run.py "Work Name" "7,8,9,10"` without `--outdir`, creating `output/guernica/`, `output/mona_lisa/`, etc. as orphan directories alongside real topic dirs. **Fix**: Always pass `--outdir output/{slug}` for every `lib/run.py` call so cache files land inside the parent topic's folder. If orphan dirs already exist: **move** their files into the correct parent directory — never delete them, as the cache JSONs are needed by the questions page renderer.

## Permissions

Ensure `.claude/settings.local.json` allows:
```json
{
  "permissions": {
    "allow": ["Bash(*)", "Edit", "Write"]
  }
}
```
