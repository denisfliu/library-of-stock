# Cross-Reference Backfill Protocol

For agents adding hyperlinks to existing pages. This is a mechanical task — use Sonnet.

## Deterministic Script (run first)

Before doing any LLM-based backfill, run the deterministic script which handles mechanical name matches automatically:

```bash
python3 lib/crossref/backfill_crossrefs.py          # adds cross_refs to any topic missing them
python3 lib/crossref/backfill_crossrefs.py --dry-run  # preview without writing
```

This script only touches topics with no `cross_refs` key yet. It's conservative: only matches canonical multi-word names from the index, skips ambiguous short titles. Run it first — then use the Sonnet agent only for richer semantic links it might miss (e.g., a work's title alluding to another author, cross-category connections).

## What You Do

For each assigned topic:
1. Read `output/{slug}/analysis.json`
2. Read `output/topic_index.json` (the master index of all topics/works)
3. Scan the summary, comprehensive_summary, and work descriptions for mentions of other indexed topics
4. Add a `cross_refs` array to the JSON

## How to Find Cross-References

Scan all text fields (summary, comprehensive_summary, work descriptions, clue text) for:
- **Names of other people** who have pages (check topic_index.json)
- **Names of works** that have their own pages or are sections in other pages
- **Movements/schools** that have pages (e.g., "Hudson River School", "Ashcan School")

## Cross-Ref Format

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

**Field names**: use `slug`, `topic`, `work` — these match what `topic_index.json` returns directly. Do NOT use `target_slug`, `target_topic`, `target_work` (old format, still supported by renderer but deprecated).

## Priority Rules

1. **Own page** → `type: "topic"`, link to their page (e.g., Robert Henri has `output/robert_henri/stock.html`)
2. **Section in another page** → `type: "work"`, link to that page's section (e.g., John Sloan is a section in Ashcan School)
3. **No page but notable** → `type: "topic"`, `exists: false` (red link for future page)

To check: look up the name in `output/topic_index.json`. If found with `type: "topic"` → rule 1. If found with `type: "work"` → rule 2. If not found but clearly a notable person/work → rule 3.

**Section anchors**: When `target_work` is set, the renderer appends `#section-anchor` to the URL (e.g., `../ashcan_school/stock.html#john-sloan`).

## How the Renderer Uses Cross-Refs

**Inline links**: The renderer scans summary, comprehensive_summary, and work descriptions for the `name` field of each cross-ref. The first occurrence of each name gets turned into a link:
- Blue link (exists: true) → clickable `<a>` tag pointing to the target page
- Red link (exists: false) → red `<span>` with tooltip "No page yet: ..."

**Section anchors**: When `target_work` is set, the renderer appends `#section-anchor` to the URL (e.g., `ashcan_school_stock.html#john-sloan`), scrolling to that section within the target page.

**Section header buttons**: If a work section name matches a cross-ref that has a page (e.g., Ashcan School has a "Robert Henri (leader)" section and Robert Henri has his own page), a → button appears on the section header linking to that page.

**Only first occurrence**: Each name is only linked once per page to avoid visual clutter.

## What NOT to Do

- Don't modify any field except `cross_refs`
- Don't add refs for generic terms ("painting", "novel", "philosophy")
- Don't add refs for the topic itself
- Don't add duplicate refs (same topic + work)
- Don't set `topic` to `null` — use the name string instead if no page exists
- Don't set `slug` to `null` — use empty string `""` if no page exists
- **Always populate `slug` when `exists: true`** — copy it directly from the index entry

## Pipeline

```bash
# For each topic in your batch:

# 1. Read the analysis JSON and topic index
# 2. Add cross_refs array
# 3. Save the JSON

# No need to render — post_batch.py runs ./build.sh after the agent finishes.
```

## Lookup Helper

```python
import json
with open('output/topic_index.json') as f:
    index = json.load(f)

# Check if a name has a page
def lookup(name):
    return index.get(name)  # Returns entry dict or None

# Example:
lookup("Robert Henri")  # {"slug": "robert_henri", "topic": "Robert Henri", "type": "topic", ...}
lookup("John Sloan")    # {"slug": "ashcan_school", "topic": "Ashcan School", "type": "work", "work": "John Sloan", ...}
lookup("Winslow Homer") # None (no page)
```
