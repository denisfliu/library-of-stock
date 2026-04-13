---
name: batch
description: Full autopilot batch run — init queues, spawn analysis agents, post-batch, crossref, cards, build.
arguments:
  - name: agents
    description: "Number of parallel agents to run (default: 3)"
  - name: category
    description: "Optional: scope to one category (e.g., \"Literature\", \"Fine Arts\")"
  - name: count
    description: "Optional: number of topics to pull from queue"
---

# Batch Guide Generation

Full autopilot. Run all steps without confirmation between stages.

## Step 1: Check Queues

```bash
python3 lib/queue/topic_queue.py summary
```

Determine which topics are queued for first pass vs. second pass. A batch can include a mix of both.

## Step 2: Initialize Batch

```bash
python3 lib/queue/batch_worker.py init "batch-$(date +%Y%m%d)" --first N --second M --category CATEGORY
```
Adjust `--first` and `--second` counts based on the queue summary and `$ARGUMENTS.count`. This pops items from the global queues into `queue/current_batch.json`.

## Step 3: Spawn Analysis Agents

For each agent slot (up to $ARGUMENTS.agents parallel), spawn a sub-agent using the Agent tool. Each agent processes **one topic** then exits.

**For each topic**, determine whether it's a first-pass or second-pass item (from the batch queue), then instruct the agent to follow the corresponding skill:

### First-pass agent prompt
Instruct the agent to follow the `/first-pass` skill protocol:
1. Pop one topic: `python3 lib/queue/batch_worker.py pop first --category "{category}"`
2. Derive slug
3. Fetch clues with `lib/run.py`
4. Read the appropriate category supplement skill (`/literature`, `/vfa`, `/afa`, `/philosophy`, `/science`) before analyzing
5. Analyze clues following the core protocol from `/first-pass`
6. Write analysis.json with all required fields
7. Generate cards following `/cards` skill rules
8. Run self-check
9. Render
10. Mark complete: `python3 lib/queue/batch_worker.py complete "TOPIC"` and `python3 lib/queue/topic_queue.py remove-first "TOPIC"`

### Second-pass agent prompt
Instruct the agent to follow the `/second-pass` skill protocol:
1. Pop one topic: `python3 lib/queue/batch_worker.py pop second --category "{category}"`
2. Load existing analysis.json
3. Read the appropriate category supplement skill before fetching/analyzing
4. Fetch additional data (text mentions, subitem queries)
5. Merge into existing analysis following `/second-pass` rules
6. Audit existing cards, generate new cards
7. Run self-check
8. Render
9. Mark complete: `python3 lib/queue/batch_worker.py complete "TOPIC"` and `python3 lib/queue/topic_queue.py remove-second "TOPIC"`

### One topic per agent
Each agent pops one topic, processes it fully, and exits. This eliminates context accumulation and reduces cost.

When an agent finishes, check the queue. If topics remain, spawn a replacement. Continue until the queue is empty.

## Step 4: Monitor

Open `progress.html` (via `./serve.sh`) — auto-refreshes every 5s.

## Step 5: Post-Batch

After ALL analysis agents complete:

```bash
python3 post_batch.py
```
This rebuilds the cross-ref index and prints agent prompts for the next steps.

## Step 6: Launch Card + Crossref Agents IN PARALLEL

Launch ALL of these at the same time — they write to different fields and don't conflict:

1. **Card agents**: Spawn agents following `/cards` skill. Each agent handles 3-5 topics — read analysis.json, generate cards, write back.
2. **Crossref agent** (use Sonnet): Spawn an agent following `/crossref` skill — deterministic backfill first, then LLM-based enrichment.

## Step 7: Build

After BOTH card and crossref agents finish:

```bash
./build.sh
```

## Step 8: VFA Image Pipeline (VFA batches only)

```bash
python3 lib/images/fix_images.py
```
Then review `cache/pending_images.json`. Then:
```bash
python3 lib/images/verify_images.py
```
Run verify_images.py **once** — it may background itself. Wait for completion notification, do NOT re-run.

## Step 9: Quality Audit

```bash
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

## Pitfalls (Do NOT Repeat)

1. **Shallow analyses**: Agents cramming everything into single sections. Fix: one topic per agent.
2. **Guessed image URLs**: 404s or wrong artist. Fix: always use `fix_images.py`.
3. **Rate limiting**: Parallel Wikimedia hits. Fix: file lock serializes automatically.
4. **Terse descriptions**: One-line descriptions. Fix: self-check requires mini-paragraphs.
5. **Multi-clue cards**: 3+ semicolons packing multiple facts. Fix: one fact per card.
6. **Missing pages**: Forgot to render. Fix: `./build.sh` covers all renderers.
7. **Wrong VFA category**: "Visual Arts" instead of "Visual Fine Arts". Fix: reference `categories.md`.
8. **Empty summary**: Left `summary` blank. Fix: required field + self-check.
9. **Forgot post-batch agents**: Skipped cards or crossref. Fix: run `post_batch.py` immediately, launch both agents.
10. **verify_images.py re-runs**: Backgrounds itself silently. Fix: run once, wait for notification.
11. **Queue JSON in wrong dir**: Written to `lib/queue/` instead of `queue/`. Fix: queue data exclusively in `queue/`.
12. **Orphan subitem dirs**: `lib/run.py` without `--outdir`. Fix: always pass `--outdir output/{slug}`.

## Permissions

Ensure `.claude/settings.local.json` allows:
```json
{
  "permissions": {
    "allow": ["Bash(*)", "Edit", "Write"]
  }
}
```
