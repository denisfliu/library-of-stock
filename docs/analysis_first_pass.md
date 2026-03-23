# First Pass Analysis

You are creating a **new analysis from scratch**.

## Slug and Directory

Two distinct identifiers exist for every topic:

- **Slug** — the canonical directory name, derived from the full proper topic name (e.g., `samuel_beckett`, `étienne_maurice_falconet`, `béla_bartók`). This is `topic_full_name.lower().replace(" ", "_")`. The slug names the `output/{slug}/` directory, the page URL, and the `currentSlug` in the JavaScript.
- **Search term** — the short query used with `run.py` (e.g., `"Beckett"`, `"Falconet"`). This is separate from the slug.

**Always derive the slug from the full proper name before fetching**, and pass it as `--outdir`:
```bash
# Full name from batch queue: "Samuel Beckett"  →  slug: samuel_beckett
python3 lib/run.py "Beckett" "7,8,9,10" --outdir output/samuel_beckett
```
This saves `output/samuel_beckett/clues.txt` — the clue file, cache files, and analysis all live in the canonical directory from the start.

If you don't yet know the full proper name (e.g., the batch entry is just a last name), run the fetch without `--outdir` first, read the answerline from the clue file to learn the full name, then move the output into the correctly-named directory.

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
