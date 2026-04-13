# First Pass Analysis

You are creating a **new analysis from scratch**.

## Unknown Full Name

If the batch entry only has a short name and you don't yet know the full proper name, run the initial fetch without `--outdir`, read the answerline from the clue file to get the full name, then move the output into `output/{slug}/`.

## Step 1: Suggest Recursive Searches

After analysis, identify works or subtopics that deserve their own deep dive. For example, if "The Moldau" comes up 10 times with varied clues, it deserves its own answerline search.

Save suggestions in `"recursive_suggestions"` in the analysis JSON. Flag ambiguous topic names and recommend a category filter (e.g., `"Indiana" with category "Literature"` rather than just `"Indiana"`).
