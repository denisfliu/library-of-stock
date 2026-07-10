---
name: new-category
description: Onboarding checklist for starting a new qbreader category (or subcategory) in the pipeline.
---

# New Category Onboarding

Run through this checklist before queueing the first batch of a category that has never been processed. Each step is idempotent — safe to re-run for a category that's partially onboarded.

## Step 1: Taxonomy check

Confirm the category's exact names in `categories.md` (category, subcategories, alternate_subcategories). If the category isn't fully documented there, sample the live API and update it:
```bash
python -c "
import requests
from collections import Counter
r = requests.get('https://www.qbreader.org/api/random-tossup', params={'number': 100, 'minYear': 2012, 'categories': 'CATEGORY_NAME'}, timeout=30)
print(Counter((t['subcategory'], t.get('alternate_subcategory','')) for t in r.json()['tossups']))
"
```

## Step 2: Supplement skill

A supplement skill must exist at `.claude/skills/<category>/SKILL.md` covering: sectioning shapes, indicator vocabulary, card rules, and metadata specifics. Model it on `/history` (events), `/mythology` (figures+group), or `/social-science` (thinker-centric). If the category needs a `group` vocabulary (traditions, fields, schools), define the allowed values **in the supplement** and list them in `categories.md`.

## Step 3: Metadata decisions

Decide and write into the supplement:
- Does `year` make sense? Is `year_end` needed (periods/spans)?
- Is `coordinates` relevant (place-anchored topics)?
- What does `genre` hold, if anything (check alternate_subcategories)?
- What is the `group` vocabulary, if any?

## Step 4: Seed the queue

Pick 5-10 canonical high-frequency answers for a pilot (not 40 — the first batch always surfaces supplement gaps):
```bash
python lib/queues/topic_queue.py add-first "Topic Name" --category "CATEGORY_NAME"
```

## Step 5: Pilot one topic manually

Run `/first-pass` on ONE topic end-to-end before any batch. Review the rendered page: sectioning sensible? indicators right? metadata filled? cards non-circular? Fix the supplement based on what you see — this is the cheapest moment to correct it.

## Step 6: Index lens check

Check how the category browses on `index.html`: topics with no `year` fall to the end of timeline ordering. If the category is yearless (concepts, places, myths), confirm the `group` field is being set so the future cluster/map views can organize it — and note in CLAUDE.md's roadmap if the index needs a new lens for this category.

## Step 7: Pilot batch

Run a small `/batch` (the 5-10 pilot topics), then `post_batch.py`, card + crossref agents, `./build.sh`, and `/verify`. Audit with `python lib/queues/scan_redo.py` — shallow analyses on a fresh category usually mean the supplement's sectioning guidance needs sharpening, not that the agent failed.
