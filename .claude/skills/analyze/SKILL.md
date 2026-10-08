---
name: analyze
description: Pipeline v2 — build a topic's study guide in one pass: gather every relevant clue, write sections/clues/cards that cite digest cluster ids, finalize (computed counts + coverage check), render. Replaces /first-pass + /second-pass.
---

**Arguments** (free-form after the skill name):
- `topic` — full canonical name (e.g., "Béla Bartók", "Carolee Schneemann")
- `aliases` — optional extra search terms (surname, alternate spellings)
- `outdir` — optional; default `output/{slug}`

# Analyze a topic (pipeline v2)

You do the judgment; scripts do everything countable. You never estimate a
frequency, never decide power/giveaway, never run extra fetches, and never
copy example quotes by hand. You cite digest cluster ids and `finalize.py`
computes the rest exactly.

## Step 1: Gather (one command, no follow-up fetches)

Slug: full canonical name, lowercased, spaces → `_` (keep diacritics, as in `béla_bartók`).

```bash
python lib/pipeline/gather.py "FULL NAME" --alias SURNAME --outdir output/{slug}
```

- `--alias` is repeatable. Add the surname when it's distinctive, plus any alternate spellings or transliterations.
- **Ambiguous surname?** (Morris, Bach, Wood, Hall, and so on): don't alias it. If the full name is too rare, alias the surname with `--category "Fine Arts"` (or the topic's category) to gate it.
- Defaults: difficulty 5–10, all years, answerline and text-mention searches merged. This covers what first pass + second pass + subitem queries used to cover, without the junk subitem hits.

The command writes three files:
- `digest.txt`: what you read.
- `clusters.json`: the evidence `finalize.py` counts from.
- `questions_ref.json`: refs for the questions page.

## Step 2: Read the category supplement

`/afa`, `/vfa`, `/literature`, `/philosophy`, `/science`, `/history`, `/religion`, `/mythology`, `/geography` or `/social-science`. Use it for indicators, metadata and category quirks. Its *fetch* steps don't apply; gather already did them.

## Step 3: Read the whole digest

Each line is `[Cid | Nq | dX-Y | years | flags] representative sentence` (phrasing 1), followed by up to three `~k` lines showing other phrasings. Nq is the number of distinct questions; the flags are PWR (power), GIVE (giveaway/ask line), B (bonus part) and L (bonus leadin).

The digest has three tiers:
1. **ANSWER IS THE TOPIC.** Clues about the topic itself. For a creator, this tier also holds most of the clues about their works. `-- theme --` blocks are machine-suggested groupings, so re-sort freely.
2. **ANSWER IS ONE OF THE TOPIC'S WORKS / SUBTOPICS.** Questions answered by a work, or by a concept the topic is clued through (a technique, an instrument, a commissioner). Some groups are noise; ignore those.
3. **PASSING MENTIONS.** Only the sentences that name the topic, taken from questions on other answers. These are the topic's relationships to other people and works.

If the digest is over about 120 KB, read it in chunks. Otherwise read it all before writing anything.

## Step 4: Plan sections

- **Creators:** one section per work or work-group. Add `General / Biographical`, and `Other Works` for works with only 1–2 thin clues.
- **Non-creators:** one section per theme, as the supplement says.
- **Section threshold:** a work or subtopic in **3+ distinct questions** gets its own section. In a **sparse topic** (under ~15 questions in tiers 1–2; passing mentions don't count), a work with **2+ distinct facts** gets its own section even from one question.
- **Tier-3 placement:**
  - Relationship facts go in a `Connections` section with the topic's own indicator, e.g. `Composer`. These are teachers, collaborators, influence, and works by others that feature or cite the topic.
  - Trivia-style ask lines ("this city where Schneemann performed Interior Scroll") go with the work or biography they're about.
  - A work by someone else that the topic took part in (Robert Morris's *Site*) gets its own section only if it's in 2+ questions. Otherwise it goes in `Connections`.
- **Style or technique concepts** that pass the threshold (Bartók's "night music", the "Bartók pizzicato") get their own section with indicator `Style` or `Technique`.

## Step 5: Write `output/{slug}/analysis.json`

The schema is below. Fields marked *(computed)* are written by `finalize.py`, so leave them out.

```json
{
  "topic": "Béla Bartók",
  "summary": "2-4 sentence blurb: key identifiers, most famous works, distinguishing facts",
  "comprehensive_summary": "several paragraphs of real prose synthesizing every section",
  "category": "Fine Arts", "subcategory": "Auditory Fine Arts", "genre": "Contemporary",
  "year": 1881, "continent": "Europe", "country": "Hungary", "tags": [],
  "links": [{"text": "Béla Bartók — Wikipedia", "url": "https://en.wikipedia.org/wiki/B%C3%A9la_Bart%C3%B3k"}],
  "recursive_suggestions": ["Concerto for Orchestra — own answerline in 13 questions"],
  "works": [
    {"name": "Concerto for Orchestra", "indicator": "Concerto",
     "description": "mini-paragraph: what it is plus its most-clued features",
     "images": [],
     "clues": [
       {"clue": "Fourth movement 'Intermezzo interrotto' parodies the invasion theme of Shostakovich's Leningrad Symphony",
        "src": ["C14", "C88"],
        "frequency": 0, "tendency": "power|mid|giveaway", "examples": []}
     ]}
  ],
  "uncited": {"C412": "noise: tossup on a different Hungarian composer"}
}
```

In that example, `frequency`, `tendency` and `examples` are *(computed)*. So are `build`, and `placement` (`{avg, n}`: where the clue usually falls in its tossups, 0 = opening line, 1 = giveaway). The page draws `placement` as a small bar on each clue.

**Precedence:** the category supplement's `genre`, indicator and `images` rules win over the generic ones in CLAUDE.md. For example, AFA always sets `genre`.

**AFA:** `score_clues` still apply, as in `/afa`. Write them for pitch-explicit clues only. A score-clue work keeps its text clue entry but gets no text card.

Rules for clue entries:

- **One fact per entry.** Split multi-fact sentences. Several entries may cite the same cluster, even across sections, as long as each cited phrasing really states that entry's fact.
- **`src` is required.** Cite `C12` when every phrasing in the cluster states the fact. When a cluster mixes facts (its `~k` lines say different things), cite only the phrasings that state this fact, as `C12:1`, `C12:3`. Over-citing inflates frequency. It lists every cluster that states this fact, so merge paraphrases that the clustering split.
- **Leave `frequency`, `tendency` and `examples` out.** `finalize.py` writes them.
- **Clue text:** state the fact plainly, in the clue's own terms. No outside knowledge.
- **Every entry must identify its answer.** A clue entry is something a player could buzz on, so it has to point to this section's answer and not to other plausible ones.
  - **The test:** someone who knows the topic hears only this entry and the indicator ("Concerto: …"). Could they name this work, and not one of the topic's other works or another composer's piece of the same kind?
  - **Fails:** "It has five movements", "Dates from 1943", "Uses Hungarian folk tunes", "Its finale includes folk themes", "Commissioned after his leukemia diagnosis", "Hungarian composer". These are properties shared by many answers.
  - **Passes:** "Fourth movement 'Intermezzo interrotto' parodies the invasion theme of Shostakovich's Leningrad Symphony", "Two bassoons a minor sixth apart begin the 'Game of Pairs'".
  - **When a weak fact only appears alongside an identifying one** ("this five-movement work with a 'Game of Pairs'"), fold it into the identifying entry or leave it out.
  - **Where a non-identifying fact goes:** it can stay as context in the section `description`. Its clusters go in `uncited` with the reason "not identifying".
  - **General / Biographical sections:** the same test applies to the person. "Hungarian composer" fails. "Recorded Hungarian folk songs on an Edison phonograph with Zoltán Kodály" passes.
- **Conflicting clues** (e.g. "Max Tenney" vs "James Tenney"): state the majority version and add `"note": "one clue says Max Tenney"`.
- **Identifier/ask lines** ("name this Hungarian composer of X and Y"): a list of the topic's famous works does identify it, so keep one identification entry per section that states the actual works or features named. Never write a meta entry such as "Identifier lines asking for the work". Don't make cards from identification entries.
- **`uncited`:** a top-level `{"C123": "reason"}` map for clusters you deliberately leave out: noise groups, quiz-mechanics sentences, off-topic hits. `finalize.py` errors on any uncited cluster that appears in 2+ questions unless it's excused here.
- **Prose fields:** `summary` (a concise blurb), `comprehensive_summary` (real prose that synthesizes the clues), section `description` (a mini-paragraph). Give full canonical names on first mention, because the cross-ref linker depends on them. Never write `cross_refs`.
- **Metadata:** `category`, `subcategory`, `genre`, `year`, `continent`, `country`, `tags`, `links` and `recursive_suggestions`, as before.

## Step 6: Write `output/{slug}/cards.json`

Card rules are the same as `/cards`, plus `src`:

```json
{"type": "basic", "indicator": "Concerto", "work": "Concerto for Orchestra",
 "front": "Concerto: its fourth movement parodies the invasion theme of Shostakovich's Leningrad Symphony",
 "back": "Concerto for Orchestra (Béla Bartók)", "src": ["C14", "C88"], "tags": []}
```

- **Coverage:** every clue entry with specific, learnable content gets a card, singletons included. On a sparse topic almost every entry is a hard, single-question clue, and those are exactly the cards advanced players need. Skip only identifier lines, vague clues and score-clue entries. Expect cards ≈ 70–100% of clue entries.
- **Several facts in one entry:** if an entry still holds two facts, split the entry. Don't put two facts on one card.
- **Front:** one fact per card. Never include a word of the answer's title.
- **`work`:** must match the section name character for character.
- **Leave out:** card `frequency` (computed). Don't make cards from pure identifier lines.

## Step 7: Finalize — loop until clean

```bash
python lib/pipeline/finalize.py output/{slug}
```

1. Fix every `ERROR` and re-run.
2. Then deal with each `WARN`: either fix it, or leave it because it's a judgment call (say a singleton that adds nothing). Don't chase zero warnings mechanically.

The report's first line (sections, entries, cards, coverage) is your self-check. The per-section question counts are what the 3+ question rule refers to. Coverage under 90% on a topic with 20+ questions means you skipped material.

## Step 8: Render

```bash
python -c "from lib.render.render import render_html; import json; a=json.load(open('output/{slug}/analysis.json')); render_html(a, 'output/{slug}/stock.html')"
```

VFA topics: run `python lib/images/fix_images.py --slug {slug}` before rendering (see `/vfa`).

## Report back

Report:
- sections, clue entries, cards, coverage
- the `uncited` count and its main reasons
- any data errors you noted
- anything in the digest that misled you (bad grouping, a misfiled tier). This feeds `gather.py` fixes.

## Then: independent check

After you finish, a **separate, fresh-context agent** runs `/guide-check` on the guide. It reads `evidence.txt` and fixes unsupported, over-cited and mis-filed content. Don't run it yourself, because the point is a second reader.
