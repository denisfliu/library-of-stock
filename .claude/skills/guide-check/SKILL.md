---
name: guide-check
description: Pipeline v2 — independent faithfulness check of a finished /analyze guide. Fresh-context agent reads evidence.txt (every clue entry and card beside the source sentences it cites), fixes unsupported, mis-attributed, or over-cited content, re-finalizes.
---

**Arguments:** `slug` (or an outdir path).

# Guide check (pipeline v2)

You did not write this guide. Your job is to catch what its author couldn't see: claims the cited questions don't support. Work only from the evidence; never from your own knowledge of the topic.

## Step 1: Read

- `output/{slug}/evidence.txt` (written by `finalize.py`) shows each section's entries `E#` with their cited source sentences, then each card `K#` with its sources.
- Also read `analysis.json`'s `summary`, `comprehensive_summary` and section `description`s.

## Step 2: Check every entry and card

For each `E#`, check for these problems:
1. **Unsupported:** the statement says something none of its cited sentences say. Outside knowledge counts, even when it's true. Names, numbers and dates must match the evidence.
2. **Over-cited:** a cited cluster or phrasing doesn't actually state this fact (it's about a different movement, work or person). This inflates frequency. Narrow `src` to the phrasings that do, written as `C12:2`.
3. **Mis-filed:** the evidence shows the fact belongs to a different work or section.
4. **Two facts:** the entry bundles facts that should be separate entries.
9. **Not identifying:** the entry wouldn't single out this section's answer for someone who knows the topic. It's a property shared by many answers ("has five movements", "dates from 1943", "uses folk tunes", "Hungarian composer"), or a meta line ("identifier lines asking for the work").
   - **Fix:** fold the fact into an identifying entry that its source sentence pairs it with, or remove the entry. When removing, delete its cards, move the fact into the section description if it's useful context, and add its now-uncited clusters to `uncited` with the reason "not identifying".
   - **Keep:** distinctive facts even when they're single-question, and the one identification entry that names the topic's actual works.

For each `K#`, check for these problems:
5. **Wrong answer:** the back isn't what the front's indicator asks for, or the front's fact belongs to a different work.
6. **Leak:** the front contains the answer or an obvious giveaway of it.
7. **Not self-contained:** the front relies on context the card doesn't give, like "that cat" or "the aforementioned work".

For the prose fields:
8. Any sentence in `summary`, `comprehensive_summary` or a `description` that no entry supports. Rewrite it or cut it.

## Step 3: Fix in place

1. Edit `analysis.json` and `cards.json` directly.
2. Run `python lib/pipeline/finalize.py output/{slug}` until it shows 0 errors. It recomputes frequency after you narrow a `src`.
3. Re-render as in `/analyze` Step 8.

Don't restructure sections or rewrite correct content for style. This pass is about faithfulness, not taste.

## Report

Report counts by problem type (1–9) with one example each, and the before → after `finalize` summary line.

## Sharded mode (large guides)

When `evidence.txt` is over about 100 KB (big canon topics), the orchestrator runs several checkers in parallel, each on a range of sections such as `S1–S2`. In this mode you **do not edit the JSON**:

1. Check only your sections' entries, the cards whose `[work]` is one of your sections, and the prose for your sections. The shard that holds S1 also checks `summary` and `comprehensive_summary`.
2. Write your fixes as edit ops to `output/{slug}/checks/shard_N.json`, using the op format in `lib/pipeline/apply_checks.py`'s docstring.
3. Address sections as `S#`, entries by their `E#` number and cards by their `K#` number, all exactly as `evidence.txt` numbers them.
4. For type 9 removals, also emit `{"op": "uncite", "id": "C123", "reason": "not identifying"}` for each cluster that no remaining entry cites.
5. When all shards are done, the orchestrator runs `python lib/pipeline/apply_checks.py output/{slug}`, then `finalize.py`, then renders.
