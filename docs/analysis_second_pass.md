# Second Pass Enrichment

You are **enriching an existing analysis** with additional data. The analysis JSON already exists — your job is to deepen it.

## Step 1: Load Existing Analysis

Read `output/{slug}/analysis.json`. Note:
- How many work sections exist
- How many cards exist
- Which works have thin clue coverage
- What the comprehensive summary covers

## Step 2: Fetch Additional Data

**Text mentions** — if the page is sparse (<10 original tossups+bonuses or <4 work sections), fetch questions where the topic appears in clue text but is NOT the answer. For sparse topics, also expand to difficulties 5-6:
```bash
python3 lib/run.py "TOPIC" "5,6,7,8,9,10" --mentions --outdir output/{slug}
```

**Subitem answerline queries** — for each major work listed in the analysis (skip "General / Biographical", "Other Works"), query it directly. For sparse topics, expand to difficulties 5-6 here too. Strip dates and parentheticals from work names before querying. For example:
- "The Course of Empire (1833–1836)" → query "The Course of Empire"
- "Vltava / The Moldau" → query "The Moldau" (use the more specific/English name)

If a query returns 0 results, skip it. Don't query works that already have rich clue coverage (5+ clues) unless you suspect there's much more data.

## Step 3: Merge Into Existing Analysis

Read ALL new clue files and merge following these rules:

**Preserve everything existing:**
- Never remove work sections, clues, cards, cross-refs, or metadata
- Never reduce frequency counts
- Never overwrite descriptions with shorter versions

**Add new data:**
- Add new clue entries to appropriate work sections
- If subitem queries reveal enough new material about a work, expand its description
- If text mentions reveal works/themes not previously covered, add new work sections (only if 3+ mentions)
- Generate cards for new clues (append to cards array)
- Rewrite `comprehensive_summary` to incorporate all information

**Fix the summary blurb:**
- Check the `"summary"` field (the blurb at top of the page)
- If empty or missing, write one: concise paragraph covering key identifiers (nationality, role, most famous works, notable associations, distinguishing facts)
- If it exists but is low quality (too vague, factually wrong, or doesn't match the clue data), rewrite it

**Track the enrichment:**
```json
{
  "second_pass": {
    "date": "YYYY-MM-DD",
    "text_mentions_queried": true,
    "subitem_queries": ["Work A", "Work B"],
    "new_clues_added": 12
  }
}
```

## What NOT to Do

- Don't re-derive existing clues from scratch — add to them
- Don't search for images — that's handled by `lib/images/fix_images.py` separately
