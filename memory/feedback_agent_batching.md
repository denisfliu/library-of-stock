---
name: Agent batch size and quality
description: Keep agent batches to 10-15 topics max; separate analysis from image search; always include self-check step
type: feedback
---

Autonomous agents degrade significantly when given too many topics (60+ per agent). Later topics get shallow single-section analyses with no cards.

**Why:** Context window exhaustion. Each detailed analysis (read clues, group by work, count frequencies, write JSON, generate cards) consumes significant context. Visual arts topics are worse because image searches add overhead.

**How to apply:**
1. **10 topics per agent max for first pass, 5 for second pass** (fewer for big topics like Picasso/Beethoven: 5 first, 3 second)
2. **Card agents: 3–5 topics each** (default batch size 4, set via `CARD_BATCH_SIZE` in `post_batch.py`). `post_batch.py` now auto-chunks using `build_card_prompt_batch()`.
3. **Two-phase pipeline**: analysis agents first (no images), then a dedicated image agent. See `docs/batch_run.md` for details.
4. **Mandatory self-check step** in every agent prompt: verify multiple work sections, non-empty cards, metadata present
5. **Paste a concrete JSON example** in the prompt — don't just reference a file (agents may not read it carefully when rushed)
6. **Post-run audit**: check for shallow analyses (1 work section, 0 cards) and broken image URLs
