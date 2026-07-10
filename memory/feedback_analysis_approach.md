---
name: feedback_analysis_approach
description: How to approach quizbowl stock knowledge analysis — pipeline, constraints, and user preferences
type: feedback
---

When the user asks to analyze a quizbowl topic (e.g., "stock Smetana", "analyze Beethoven"):

1. Run `python3 lib/run.py "<topic>" "<difficulties>"` via Bash to fetch + parse clues.
   - Default difficulties: "7,8,9,10" (user's usual range, but ask if not specified)
   - Default min_year: 2012 (hardcoded)
   - Only fetches first 25 results per search type (1 page)

2. Read the output file from `output/<topic>_clues.txt`.

3. Analyze the clues following the protocol in `docs/analysis_core.md` (+ pass-specific and category supplements assembled by `lib/prompt_builder.py`).

4. Generate HTML output using `lib/render.py`. Save analysis JSON to `output/`. Then run `./build.sh`.

5. After initial answerline analysis, suggest recursive searches into important works/subtopics — ask for user confirmation before fetching.

6. For visual topics, use `lib/images.py` to find Wikimedia Commons images to embed.

**Why:** User wants a tight workflow where they give a topic and get a study guide. I (Claude) am the LLM in the pipeline — no separate API calls needed. User is on Claude Max.

**How to apply:** When the user gives a topic name, immediately start the pipeline. Don't ask unnecessary questions — just run it. Power marks track whether a clue is in the power region (useful metadata) but are NOT used for importance ranking.
