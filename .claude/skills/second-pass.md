---
name: second-pass
description: Enrich an existing analysis with additional data — fetch more clues, merge, audit cards, and re-render.
arguments:
  - name: topic
    description: "Topic name (e.g., \"Smetana\", \"Emily Carr\")"
  - name: category
    description: "Optional category override. Auto-detected from existing analysis if omitted."
---

# Second Pass Enrichment

You are **enriching an existing analysis** for "$ARGUMENTS.topic". The analysis JSON already exists — your job is to deepen it.

## Step 1: Load Existing Analysis

Read `output/{slug}/analysis.json`. Note:
- How many work sections exist
- How many cards exist
- Which works have thin clue coverage
- What the comprehensive summary covers
- The category/subcategory (for auto-detection)

## Step 2: Read Category Supplement

**Before fetching or analyzing**, read the appropriate category supplement skill:
- Literature -> `/literature`
- Fine Arts (VFA subcategory) -> `/vfa`
- Fine Arts (AFA subcategory) -> `/afa`
- Philosophy -> `/philosophy`
- Science -> `/science`

Reference `categories.md` (project root) for valid category/subcategory names.

## Step 3: Fetch Additional Data

**Text mentions** — if the page is sparse (<10 original tossups+bonuses or <4 work sections):
```bash
python3 lib/run.py "TOPIC" "5,6,7,8,9,10" --mentions --outdir output/{slug}
```

**Subitem answerline queries** — for each major work listed in the analysis (skip "General / Biographical", "Other Works"), query it directly. Strip dates and parentheticals before querying:
- "The Course of Empire (1833-1836)" -> "The Course of Empire"
- "Vltava / The Moldau" -> "The Moldau"

```bash
python3 lib/run.py "WORK NAME" "7,8,9,10" --outdir output/{slug}
```
For sparse topics, expand to difficulties 5-6. Skip works with 5+ clues already. If 0 results, skip.

## Step 4: Merge Into Existing Analysis

Read ALL new clue files and merge following these rules:

**Preserve everything existing:**
- Never remove work sections, clues, cards, cross-refs, or metadata
- Never reduce frequency counts
- Never overwrite descriptions with shorter versions

**Add new data:**
- Add new clue entries to appropriate work sections
- If subitem queries reveal enough new material, expand descriptions
- If text mentions reveal works/themes not previously covered, add new sections (only if 3+ mentions)
- Rewrite `comprehensive_summary` to incorporate all information

**Fix the summary blurb:**
- Check `"summary"` — if empty, missing, or low quality, write/rewrite it

**Track enrichment:**
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

## Step 5: Card Audit (MANDATORY)

Before appending new cards, audit **existing** cards for quality violations and fix in place:

1. **Wrong indicators** — genre/category name as indicator instead of proper type? Fix both `indicator` field and `front` text.
2. **Multi-fact fronts** — semicolon bundling two facts? Split into two cards.
3. **Missing image cards** — work section with non-empty `images` array but no `"type": "image"` card? Add one.
4. **Missing `work` field** — every card must have `work` matching the section `name` character-for-character.
5. **Image card fronts** — every `"type": "image"` card must have `"front": ""`.
6. **Uppercase clue starts** — clue text after `Indicator: ` must start lowercase unless proper noun.

Do NOT remove or rewrite cards that are substantively correct — only fix structural violations.

## Step 6: Generate New Cards

Generate cards for any new clues added during this pass. Append to existing `cards` array. Follow `/cards` skill rules.

## Step 7: Self-Check (MANDATORY)

- [ ] All existing work sections preserved; no frequency counts reduced
- [ ] New clues added to appropriate sections
- [ ] `comprehensive_summary` rewritten to include new info
- [ ] `summary` blurb filled and high quality
- [ ] `second_pass` tracking field added

## Step 8: Render

```bash
python3 -c "from lib.render.render import render_html; import json; f=open('output/{slug}/analysis.json'); a=json.load(f); render_html(a, 'output/{slug}/stock.html')"
```

## Data Fetching Rules

- **Always** use `lib/run.py` to fetch clues — never write clues.txt manually.
- **Always** pass `--outdir output/{slug}` for every `lib/run.py` call — never let subitem results land in their own top-level directories.
- Never delete orphan cache directories — move their files into the correct parent directory.

## What NOT to Do

- Don't re-derive existing clues from scratch — add to them
- Don't run image steps unless the category supplement says to
