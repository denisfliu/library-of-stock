# Cross-refs v2: methodology

**Since July 2026.** Principle: *agents assert identities, machines
resolve links*. Analysis agents write prose using full canonical names
(first mention); a deterministic linker turns names into links; the only
LLM involvement is one-time adjudication of genuinely ambiguous
surfaces, whose decisions persist forever.

## Ref schema (analysis.json `cross_refs[]`)

`{name, type, exists, slug, topic, work, source}` — `name` is the
surface string in prose (drives inline linking in render.py); `type`
`"topic"`/`"work"`; `exists:false` = red link with `slug:""`; `source`
is provenance:

| source | written by | regenerated? |
|---|---|---|
| `backfill` | linker auto tier (relink.py) | yes, every relink |
| `override` | linker applying an adjudicated decision | yes, every relink |
| `agent` | LLM/human judgment (incl. all red links) | never touched by machines |

## The linker (`lib/crossref/linker.py`)

Single matching engine (replaces the old triplicated heuristics). Two
tiers, built from the analyses themselves so alias collisions are
visible:

- **auto** — canonical names (a topic's full name; work names of 2+
  words): linked outright, guarded by `SKIP_TERMS`, `MIN_LEN`, and a
  longer-name adjacency check (a single word touching another
  capitalized word is a chunk of some longer proper name — "Carmen"
  inside "Carmen Maria Machado").
- **gated** — ambiguous surfaces (last-name aliases, one-word titles,
  parenthetical/slash variants): **never auto-linked** — this tier is
  where the old system's wrong-person errors lived. A gated hit either
  resolves through an override or becomes a candidate for adjudication.

## Overrides (`output/crossref_overrides.json`, committed)

`per_topic[slug][surface]` and `global[category-or-"*"][surface]` map a
surface to a target `{slug, topic, type, work, exists}` or `null`
(never link). Precedence: per-topic > category > `*`. The `*` seeds are
hand-picked always-ambiguous surfaces (bare `Thomas`/`House`/...).

## The loop

```
per pass/batch (post_batch.py):
  lib/crossref/crossref.py         # rebuild topic_index.json
  lib/crossref/relink.py           # re-derive machine refs for ALL topics
       -> dev/crossref_candidates.json   (open ambiguity, grouped by surface)
  /crossref agent (only if candidates exist):
       adjudicates surfaces -> writes overrides -> reruns relink
```

relink runs over every topic each time (old pages gain links to new
pages), preserves `source:"agent"` refs verbatim, and is idempotent.
Local-only — it mutates analysis.json, so it never runs in CI.
`lib/validate.py` enforces hygiene: `[CROSSREF DANGLING / RED WITH SLUG
/ SELF / DUPE / NO SLUG / BAD SOURCE]`.

## Pass-agent rule (the zero-agent half)

First/second-pass prose (summary, comprehensive_summary, work
descriptions) refers to other people/works by **full canonical name on
first mention** — that lands in the auto tier for free; bare last names
would just queue adjudication work.

## Related topics (mirror inference)

`lib/crossref/infer.py` (local, needs the mirror) scans each topic's
question text (resolved from `questions_ref.json` ids) with the auto
tier only, building a bidirectional co-mention graph. Top-scored
neighbors not already cross-ref'd land in `output/{slug}/related.json`
(machine-owned file, cards.json precedent) and render as the "Related
topics" strip on stock.html; the graph also ships in the R2 topics.json
overlay.
