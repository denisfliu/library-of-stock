# Design: shared question store

**Status: proposal — for Denis review before any migration.** July 2026.
Roadmap item "Shared question store" (CLAUDE.md). Should land before the
~38-unit overview scale-out multiplies the duplication.

## Problem

Question text is stored in three independent shapes that don't know about
each other:

| shape | where | size today | keyed by |
|---|---|---|---|
| per-topic caches | `output/{slug}/{query}_d…_y….json` (committed) | **71 MB**, 25,737 question objects | query filename; fuzzy `find_cache_for_topic` fallback |
| sweep sets | `output/_sets/{set}/set.json` (committed) | 1.3 MB, 1,348 rows | packet/number; **no `_id` retained** |
| unit captures | `output/_categories/{unit}/questions.json` + `questions_data.js` (committed) | 1.6 MB | normalized answerline; **no `_id` retained** |

Measured on the current corpus (773 topics, 1 sweep set, 2 unit pages):

- Only **19,403 distinct qbreader `_id`s** back those 25,737 topic-cache
  objects — 25% duplicate copies *within topic caches alone*, before the
  set/unit copies. Every new overview unit and sweep set adds more copies
  of the same questions.
- Each topic-cache object stores the text **twice** (`question` +
  `question_sanitized`, ~12 MB each corpus-wide) plus `answer` +
  `answer_sanitized` (~8 MB combined).
- The set and unit shapes are **lossy**: they dropped `_id` at capture
  time, so today they can't be deduplicated, backlinked, or refreshed
  without refetching.
- `render_questions.find_cache_for_topic` does 5-tier fuzzy filename
  matching because the topic→cache relationship is encoded in filenames
  instead of data.

## Goals

1. One committed copy of each fetched question, keyed by qbreader `_id`;
   every artifact references into it.
2. CI keeps working: renderers must find everything in a fresh checkout.
3. Smaller git footprint (rough estimate: ~74 MB of question shapes →
   ~20 MB store + small ref files, by deduplicating and keeping one text
   variant).
4. Stable refs unlock features: "this question also appears on…"
   backlinks, per-question freshness (`updatedAt`), refetch-free rematch
   everywhere.

Non-goals: mirroring qbreader wholesale (only what we fetched); changing
the agent-facing `clues.txt` format (analysis agents never touch the
store); changing fetch caching in gitignored `cache/` (stays as a
network-avoidance layer only).

## Design

### Store layout

```
output/_questions/{set_slug}.json     # one shard per qbreader set
```

Sharded **by set** (decided, Denis, July 2026), not by id-prefix: a
tournament's questions land in one file, new fetches touch few shards,
diffs stay local, and sweep pages read exactly their shard. Shard file =
`{_id: doc}` map, keys sorted, written via `write_json_if_changed`
(no churn).

Question doc — qbreader fields minus redundancy:

```json
{
  "type": "tossup",
  "question": "…sanitized text…",
  "answer": "…sanitized answerline…",
  "category": "Literature", "subcategory": "World Literature",
  "alternate_subcategory": "",
  "set": "2022 ACF Winter", "packet": 3, "number": 7,
  "difficulty": 8, "updatedAt": "…"
}
```

Bonuses keep `leadin` + `parts[]` + `answers[]` in the same style.
**Open question (a):** keep only the sanitized variant (proposed — it's
what every renderer displays) or both raw+sanitized (doubles text weight).

### API — `lib/questions_store.py`

- `load_store(sets=None) -> dict[_id, doc]` — one dict, loaded once per
  build (build.py passes it alongside `analyses`).
- `upsert(docs)` — add/update by `_id`, routed to the right shard,
  `file_lock`-guarded so concurrent batch agents don't clobber shards.
  Existing docs are only rewritten when qbreader's `updatedAt` moved.

### Artifacts become refs

- **Topic**: `output/{slug}/questions_ref.json` —
  `[{query_string, params, tossups: [_id…], bonuses: [_id…]}]`, one entry
  per query (replaces N `{query}_d…json` files and the fuzzy filename
  matching; `analysis.cache_file` and validate's `STALE CACHE_FILE` check
  retire with it).
- **Sweep set**: `set.json` rows keep `answer_clean` + `match` but carry
  `_id` instead of `text`/`answer_raw`.
- **Unit capture**: `questions.json` maps answerline → `[_id…]`;
  `questions_data.js` is generated from the store at render time.

Writers that must start retaining `_id`: `lib/sweep/build_set.extract_questions`,
`lib/sweep/capture_questions.py`, `lib/pipeline/fetch.py` (already has it).

### Renderers

`render_questions`, `render_sweep`, `render_overview`/`capture` all render
by resolving `_id`s against the loaded store — same HTML output as today
(golden test pins this).

## Migration (each phase independently shippable, golden-test-gated)

- **A. Backfill**: script builds shards from existing topic caches (they
  carry `_id` + full docs). The lossy set/unit artifacts are refetched
  once instead of reverse-matched — today that's 1 set + 2 units, which is
  exactly why this should land **before** the scale-out.
- **B. Dual-read**: renderers prefer the store, fall back to legacy caches.
  Golden fixtures gain a store shard; snapshots must not change.
- **C. Cut over**: writers emit refs only; per-topic `{query}_*.json`
  files and embedded set/unit text are deleted. `find_cache_for_topic`
  and the raw-text fields go away. One-time ~50 MB drop in repo size
  (history keeps the old blobs unless we ever rewrite).

## Risks

- **Concurrent writers** during /batch fan-out: per-set sharding +
  `file_lock` keeps contention low; upsert is idempotent by `_id`.
- **qbreader edits**: `updatedAt`-gated upsert means text can drift
  between a topic's fetch and a later set fetch — acceptable; the store
  always holds the newest seen version.
- **Deploy artifact**: Pages rsync ships only html/mp3/`*_data.js`, so
  the store isn't published; question text still reaches pages embedded
  at render time. No deploy change needed.

## Decisions needed from Denis

1. (a) above — sanitized-only text, or keep raw too?
2. Shard-by-set OK? (alternative: 256 id-prefix shards — smaller diffs,
   but every page load touches many files and diffs scatter).
3. Green-light phase A+B now (no user-visible change), with phase C after
   the next batch runs cleanly?
