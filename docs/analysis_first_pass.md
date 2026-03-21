# First Pass Analysis

You are creating a **new analysis from scratch**.

## Step 1: Expand Search if Sparse

After the initial answerline fetch, check if the results are sparse — fewer than **10 total tossups + bonuses**. If so, run two additional queries:

1. **Expand difficulty range** — re-fetch answerline results with difficulties 5-10 instead of 7-10:
   ```bash
   python3 lib/run.py "SEARCH TERM" "5,6,7,8,9,10"
   ```

2. **Text mentions** — fetch questions where the topic appears in the clue text but is NOT the answer:
   ```bash
   python3 lib/run.py "SEARCH TERM" "5,6,7,8,9,10" --mentions
   ```

Incorporate all results into your analysis. Text mention clues provide contextual information — how other topics reference this one — and should be clearly labeled as such in the analysis.

## Step 2: Suggest Recursive Searches

Identify works or subtopics that deserve their own deep dive. For example, if "The Moldau" comes up 10 times with varied clues, it deserves its own answerline search.

Save suggestions in the `"recursive_suggestions"` field of the analysis JSON. These will be used for second pass enrichment later.

When suggesting, flag any topic names that are likely ambiguous and recommend a category filter. For example, suggest `"Indiana" with category "Literature"` rather than just `"Indiana"` if the unfiltered search would be dominated by Indiana the US state.
