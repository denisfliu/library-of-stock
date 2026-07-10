---
name: post-batch checklist
description: CRITICAL — always run post_batch.py + Sonnet crossref agent after every batch; never declare done without it
type: feedback
---

After all batch agents complete, ALWAYS run the full post-batch sequence before reporting "batch complete." The Sonnet crossref backfill is the most commonly skipped step — it causes pages to have no hyperlinks.

**Post-batch sequence:**
1. `python3 post_batch.py` — rebuilds crossref index AND prints the ready-to-use Sonnet agent prompt (reads completed topics from current_batch.json automatically)
2. Launch the Sonnet agent with the printed prompt (adds cross_refs, then rerenders + builds index)
3. After Sonnet finishes: `./build.sh`
4. VFA only: image pipeline (`lib/fix_images.py` → review → `lib/verify_images.py`)

**Why:** Skipping crossref backfill = no hyperlinks anywhere on new pages. This happened multiple times. `post_batch.py` was created specifically to make this mechanical and hard to skip.

**How to apply:** When the last agent finishes, immediately run `python3 post_batch.py` WITHOUT waiting for the user to ask. Do NOT say "batch complete" until the Sonnet agent has run and all renderers have finished. This applies to every batch including single-topic batches. Also update MEMORY.md if needed.
