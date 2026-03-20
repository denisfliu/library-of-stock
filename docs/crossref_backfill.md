# Cross-Reference Backfill Protocol

For agents adding hyperlinks to existing pages. This is a mechanical task — use Sonnet.

## What You Do

For each assigned topic:
1. Read `output/{slug}_analysis.json`
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
      "target_topic": "Robert Henri",
      "target_slug": "robert_henri",
      "target_work": null,
      "type": "topic",
      "exists": true
    },
    {
      "name": "John Sloan",
      "target_topic": "Ashcan School",
      "target_slug": "ashcan_school",
      "target_work": "John Sloan",
      "type": "work",
      "exists": true
    },
    {
      "name": "Winslow Homer",
      "target_topic": "Winslow Homer",
      "target_slug": "",
      "target_work": null,
      "type": "topic",
      "exists": false
    }
  ]
}
```

## Priority Rules

1. **Own page** → `type: "topic"`, link to their page (e.g., Robert Henri has `robert_henri_stock.html`)
2. **Section in another page** → `type: "work"`, link to that page's section (e.g., John Sloan is a section in Ashcan School)
3. **No page but notable** → `type: "topic"`, `exists: false` (red link for future page)

To check: look up the name in `output/topic_index.json`. If found with `type: "topic"` → rule 1. If found with `type: "work"` → rule 2. If not found but clearly a notable person/work → rule 3.

## What NOT to Do

- Don't modify any field except `cross_refs`
- Don't add refs for generic terms ("painting", "novel", "philosophy")
- Don't add refs for the topic itself
- Don't add duplicate refs (same target_topic + target_work)

## Pipeline

```bash
# For each topic in your batch:

# 1. Read the analysis JSON and topic index
# 2. Add cross_refs array
# 3. Save the JSON

# After all topics:
python3 rerender.py
python3 build_index.py
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
