# Core Analysis Protocol

When analyzing clues for a quizbowl topic, follow this protocol. **Only use information from the clues themselves** — do not inject outside knowledge except for hyperlinks.

## Search Query vs. Page Title

When fetching clues, use the **minimally identifiable name** — the shortest form that qbreader indexes on. But set the `topic` field in the analysis JSON to the **full proper name**.

Examples:
- Search: `"Falconet"` → topic: `"Étienne Maurice Falconet"`
- Search: `"Schelling"` → topic: `"Friedrich Wilhelm Joseph Schelling"`
- Search: `"Smetana"` → topic: `"Bedřich Smetana"`
- Search: `"Hokusai"` → topic: `"Hokusai"` (already minimal)
- Search: `"The Oxbow"` → topic stays as work title

The answerline in the clue results usually tells you the full name (e.g., "Arthur **Schopenhauer**"). Use that for the topic field. When in doubt, match Wikipedia's article title.

## Step 1: Filter Out Irrelevant Results

Some topic names are ambiguous — "Indiana" could be the George Sand novel or the US state; "Sand" could be the material or the author. Even with category filtering at fetch time, the results may contain questions about the wrong topic.

Before analyzing, scan all returned tossups and bonuses and **discard any that are clearly about a different topic.** Check the answerline and question content — if a question is about "Indiana (the state)" when you're studying the novel, skip it entirely. Note how many results you discarded so the user knows.

## Step 2: Identify What the Topic Is (from clues only)

Write a brief summary of what the topic is, based solely on how the clues describe it. For example, if the clues say "this Czech composer of Ma vlast," then the summary is "Czech composer, associated with Ma vlast." Do not add biographical details that don't appear in the clues.

## Step 3: Identify Key Works / Subtopics

**Before grouping, systematically count references per work/subtopic across ALL tossup and bonus clues.** Count every mention — whether it appears as a giveaway identifier ("this author of X"), a specific plot clue, or a bonus part answer. Use these counts to decide what gets its own section.

**Sectioning rules:**
- Any work/subtopic mentioned **3+ times** across all clues gets its own section. No exceptions.
- Any work/subtopic that has **specific plot/detail clues** (not just used as a name-drop identifier) gets its own section, regardless of count.
- Only lump into "Other Works" if a work appears 1-2 times AND only as a passing identifier with no specific detail clues.

For creators (composers, authors, artists, etc.):
- List the major works that appear in the clues
- Group clues by work

For non-creators (concepts, events, places, scientific topics, etc.):
- Identify the major themes or aspects clued
- Group clues by theme

## Step 4: Rank by Frequency

Within each work/subtopic, identify the individual clues. Note:
- A single sentence may contain multiple clues (e.g., "this piece opens with two harps and uses the motif B-flat, E-flat, D, B-flat" = two clues: instrumentation + motif)
- Different questions may word the same clue differently — group these together
- Count how many times each clue appears across different questions
- Rank from most common to least common

## Step 5: Format the Output

For each work/subtopic, provide:
1. **Work name**, brief identification (from clues), and **`indicator`** field — the card type indicator for this work (e.g., `"Play"`, `"Novel"`, `"Painting"`). For general/biographical sections, use the creator type (e.g., `"Playwright"`, `"Composer"`). This is stored on the work object in the JSON and used during card generation.
2. **Clues ranked by frequency**, each with:
   - A clear statement of what the clue is
   - How many times it appeared as a **number** (e.g. "appears 4 times") — never use text labels like "very common", "common", "rare"
   - 1-2 example quotes from actual questions showing how it's worded
3. Mark which clues tend to appear in power (early/hard) vs. giveaway (late/easy)

## Step 6: Write a Comprehensive Summary

After completing the clue-by-clue analysis, write a prose summary that synthesizes all the facts accumulated from the clues into a readable reference. This is different from the brief topic identification in Step 2 — it should be a thorough, paragraph-form account of everything the clues tell us.

For a creator, this might cover: biographical details, major works and their plots/content, key relationships and associations, and how the topic connects to other frequently clued subjects. For a concept or event, cover all aspects and angles that appeared across the clues.

Write this as if someone who knows nothing about the topic will read it to get a complete picture of what quizbowl expects them to know. Use only facts from the clues. Store this in the `"comprehensive_summary"` field of the analysis JSON.

## Metadata Fields

The analysis JSON must include these fields for the index page:

- **`category`** and **`subcategory`**: pulled automatically from qbreader API data (see `docs/categories.md`)
- **`genre`**: the most specific type within the subcategory, when applicable. Required for:
  - Fine Arts > Other Fine Arts: set to the specific type from `docs/categories.md`: `"Architecture"`, `"Film"`, `"Photography"`, `"Dance"`, `"Jazz"`, `"Musicals"`, `"Opera"`, or `"Misc Arts"`
  - Science > Other Science: set to the specific field from `docs/categories.md`: `"Math"`, `"Astronomy"`, `"Computer Science"`, `"Earth Science"`, `"Engineering"`, or `"Misc Science"`
  - Leave as `""` for all other subcategories (Visual Fine Arts, Auditory Fine Arts, Biology, Chemistry, Physics, etc.)
- **`year`**: birth year for people, creation/publication year for works, start year for periods/movements. Use negative numbers for BCE. This is outside knowledge — OK to use here.
- **`continent`**: where the topic is primarily associated with. One of: Africa, Asia, Europe, North America, Oceania, South America. This is outside knowledge — OK to use here.
- **`country`**: country the topic is primarily associated with (e.g., "France", "Japan", "England"). This is outside knowledge — OK to use here.
- **`tags`**: list of notable movements, schools, or styles (e.g., `["Hudson River School", "Romanticism"]` for Thomas Cole, `["Surrealism", "Absurdism"]` for Kobo Abe). Only include specific, recognized movements — NOT broad geographic descriptors like "Japanese literature" or "American landscape." These are used for cross-topic filtering in the index. This is outside knowledge — OK to use here.

## Constraints

- **No outside knowledge for clue content.** Only describe what the clues say.
- **Outside knowledge OK for:** hyperlinks, identifying what a referenced work/person is for linking purposes, and metadata fields (year, continent) above.
- **Sentences may contain multiple clues** — separate them during analysis.
- **Giveaway clues** (containing "For 10/ten points") are still clues — they tell you what the most common/easy identification is.
