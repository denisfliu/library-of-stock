---
name: crossref
description: Adjudicate ambiguous cross-ref surfaces — resolve dev/crossref_candidates.json into output/crossref_overrides.json, then relink.
---

**Arguments** (passed free-form after the skill name):
- `surfaces` — Optional: comma-separated surface strings to adjudicate. If omitted, process the whole candidates file.

# Cross-Reference Adjudication

You do NOT free-generate cross_refs and you do NOT edit analysis.json.
The deterministic linker (`lib/crossref/relink.py`) already created every
unambiguous link. Your job: judge the ambiguous leftovers it queued, and
record each decision in the overrides file so it is never asked again.
Methodology background: `docs/crossref.md`.

## Step 1: Read the queue

`dev/crossref_candidates.json` — `surfaces` maps each ambiguous surface
string to its `instances`: `{slug, topic, category, snippet, targets}`.
`targets` are the index entries that surface *could* mean. Surfaces are
sorted by instance count, most frequent first — work in that order.

## Step 2: Decide each surface

For each instance, the question is: **in this topic's snippet, what does
the surface actually refer to?** Read the topic's `analysis.json` when
the snippet alone is not enough. Possible verdicts:

1. **One of the listed targets** — the text means that topic/work.
2. **A red link** — the text means a notable person/work that has no
   page and is none of the targets (e.g. "Duffy" meaning Bruce Duffy
   when only Carol Ann Duffy has a page). Resolution:
   `{"topic": "Bruce Duffy", "type": "topic", "exists": false, "slug": ""}`.
3. **null** — generic/unlinkable use ("the house", a character name, a
   common word). When in doubt, null: a missing link is invisible, a
   wrong link is a defect.

**Scope of the decision:**
- Applies to just this topic → `per_topic[slug][surface]`.
- Same verdict clearly holds for every instance in a category (e.g.
  "Beethoven" in Fine Arts always means Ludwig van Beethoven) →
  `global[category][surface]`. Use `global["*"]` only for surfaces that
  are junk everywhere.
- Mixed instances → per-topic entries for each; no global rule.

## Step 3: Write the overrides

Merge into `output/crossref_overrides.json` (do not clobber existing
entries). Resolution objects use index fields:
`{"slug", "topic", "type", "work", "exists"}` — copy `slug` exactly from
the chosen target; `work` only for `type:"work"`; red links have
`exists:false, slug:""`; `null` means never link.

## Step 4: Apply

```bash
python lib/crossref/relink.py
python lib/validate.py
```

relink converts your decisions into `source:"override"` refs and removes
the surfaces from the candidates file. Validate must not report new
`[CROSSREF ...]` issues.

## What NOT to do

- Don't edit `analysis.json` or any file except
  `output/crossref_overrides.json`.
- Don't guess: if you can't tell what a surface means from the snippet +
  analysis, use `null`.
- Don't write a global rule from a single instance unless the surface is
  intrinsically unambiguous (a unique famous surname like "Beethoven").
- Don't run render scripts — the controller builds after you finish.
