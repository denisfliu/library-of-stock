---
name: crossref
description: Run cross-reference backfill — add hyperlinks between related topics.
arguments:
  - name: topics
    description: "Optional: comma-separated topic names or slugs to process. If omitted, processes all topics missing cross_refs."
---

# Cross-Reference Backfill

Add cross-references (hyperlinks between related topics) to analysis JSON files.

## Step 1: Run Deterministic Script First

```bash
python3 lib/crossref/backfill_crossrefs.py
```
This handles mechanical name matches automatically — only touches topics with no `cross_refs` key yet. Conservative: only matches canonical multi-word names from the index.

## Step 2: LLM-Based Enrichment

For each topic (either the specified topics or all that need richer links):

### Read data
1. Read `output/{slug}/analysis.json`
2. Read `output/topic_index.json` (master index of all topics/works)

### Find cross-references
Scan all text fields (summary, comprehensive_summary, work descriptions, clue text) for:
- **Names of other people** who have pages (check topic_index.json)
- **Names of works** that have their own pages or are sections in other pages
- **Movements/schools** that have pages (e.g., "Hudson River School", "Ashcan School")

### Cross-ref format
```json
{
  "cross_refs": [
    {
      "name": "Robert Henri",
      "topic": "Robert Henri",
      "slug": "robert_henri",
      "work": null,
      "type": "topic",
      "exists": true
    },
    {
      "name": "John Sloan",
      "topic": "Ashcan School",
      "slug": "ashcan_school",
      "work": "John Sloan",
      "type": "work",
      "exists": true
    },
    {
      "name": "Winslow Homer",
      "topic": "Winslow Homer",
      "slug": "",
      "work": null,
      "type": "topic",
      "exists": false
    }
  ]
}
```

Use field names `slug`, `topic`, `work` — these match topic_index.json directly.

### Priority rules
1. **Own page** -> `type: "topic"`, link to their page
2. **Section in another page** -> `type: "work"`, link to that page's section
3. **No page but notable** -> `type: "topic"`, `exists: false` (red link)

Look up names in `output/topic_index.json`: found with `type: "topic"` -> rule 1; found with `type: "work"` -> rule 2; not found but notable -> rule 3.

### Write back
Add/update only the `cross_refs` array in the JSON. Do not modify any other field.

## Lookup Helper

```python
import json
with open('output/topic_index.json') as f:
    index = json.load(f)

def lookup(name):
    return index.get(name)  # Returns entry dict or None
```

## What NOT to Do

- Don't modify any field except `cross_refs`
- Don't add refs for generic terms ("painting", "novel", "philosophy")
- Don't add refs for the topic itself
- Don't add duplicate refs (same topic + work)
- Don't set `topic` to `null` — use the name string
- Don't set `slug` to `null` — use empty string `""` if no page exists
- **Always populate `slug` when `exists: true`** — copy directly from the index entry
