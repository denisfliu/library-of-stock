# Stock Knowledge Analysis Instructions

When analyzing clues for a quizbowl topic, follow this protocol. **Only use information from the clues themselves** — do not inject outside knowledge except for hyperlinks and images.

## Step 0: Filter Out Irrelevant Results

Some topic names are ambiguous — "Indiana" could be the George Sand novel or the US state; "Sand" could be the material or the author. Even with category filtering at fetch time, the results may contain questions about the wrong topic.

Before analyzing, scan all returned tossups and bonuses and **discard any that are clearly about a different topic.** Check the answerline and question content — if a question is about "Indiana (the state)" when you're studying the novel, skip it entirely. Note how many results you discarded so the user knows.

## Step 1: Identify What the Topic Is (from clues only)

Write a brief summary of what the topic is, based solely on how the clues describe it. For example, if the clues say "this Czech composer of Ma vlast," then the summary is "Czech composer, associated with Ma vlast." Do not add biographical details that don't appear in the clues.

## Step 2: Identify Key Works / Subtopics

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

## Step 3: Rank by Frequency

Within each work/subtopic, identify the individual clues. Note:
- A single sentence may contain multiple clues (e.g., "this piece opens with two harps and uses the motif B-flat, E-flat, D, B-flat" = two clues: instrumentation + motif)
- Different questions may word the same clue differently — group these together
- Count how many times each clue appears across different questions
- Rank from most common to least common

## Step 4: Format the Output

For each work/subtopic, provide:
1. **Work name**, brief identification (from clues), and **`indicator`** field — the card type indicator for this work (e.g., `"Play"`, `"Novel"`, `"Painting"`). For general/biographical sections, use the creator type (e.g., `"Playwright"`, `"Composer"`). This is stored on the work object in the JSON and used during card generation.
2. **Clues ranked by frequency**, each with:
   - A clear statement of what the clue is
   - How many times it appeared (approximate)
   - 1-2 example quotes from actual questions showing how it's worded
3. Mark which clues tend to appear in power (early/hard) vs. giveaway (late/easy)

## Step 5: Write a Comprehensive Summary

After completing the clue-by-clue analysis, write a prose summary that synthesizes all the facts accumulated from the clues into a readable reference. This is different from the brief topic identification in Step 1 — it should be a thorough, paragraph-form account of everything the clues tell us.

For a creator, this might cover: biographical details, major works and their plots/content, key relationships and associations, and how the topic connects to other frequently clued subjects. For a concept or event, cover all aspects and angles that appeared across the clues.

Write this as if someone who knows nothing about the topic will read it to get a complete picture of what quizbowl expects them to know. Use only facts from the clues. Store this in the `"comprehensive_summary"` field of the analysis JSON.

## Step 6: Suggest Recursive Searches

After analysis, identify works or subtopics that deserve their own deep dive. For example, if "The Moldau" comes up 10 times with varied clues, suggest searching for it as its own answerline. Present these as suggestions for user confirmation.

When suggesting recursive searches, flag any topic names that are likely ambiguous and recommend a category filter. For example, suggest `"Indiana" ... "Literature"` rather than just `"Indiana"` if the unfiltered search would be dominated by Indiana the US state.

## Output Format

The final output should be an HTML file with:
- Collapsible sections for each work/subtopic
- Clue frequency indicators (visual, like bars or counts)
- Example quotes styled distinctly (blockquote or similar)
- Power vs. giveaway indicators
- A comprehensive prose summary of all accumulated facts (above the reference links)
- Hyperlinks to relevant Wikipedia articles for further reading
- Space for images (paintings, scores) where relevant — these can be added later
- Clean, readable typography suitable for studying

## Metadata Fields

The analysis JSON must include these fields for the index page:

- **`category`** and **`subcategory`**: pulled automatically from qbreader API data (see `docs/categories.md`)
- **`year`**: birth year for people, creation/publication year for works, start year for periods/movements. Use negative numbers for BCE. This is outside knowledge — OK to use here.
- **`continent`**: where the topic is primarily associated with. One of: Africa, Asia, Europe, North America, Oceania, South America. This is outside knowledge — OK to use here.
- **`country`**: country the topic is primarily associated with (e.g., "France", "Japan", "England"). This is outside knowledge — OK to use here.
- **`tags`**: list of notable movements, schools, or styles (e.g., `["Hudson River School", "Romanticism"]` for Thomas Cole, `["Surrealism", "Absurdism"]` for Kobo Abe). Only include specific, recognized movements — NOT broad geographic descriptors like "Japanese literature" or "American landscape." These are used for cross-topic filtering in the index. This is outside knowledge — OK to use here.

## Step 7: Generate Anki Cards

After analysis, generate a default set of Anki cards from the clues. Store them in the `"cards"` field of the analysis JSON as a list of card objects.

### Card format

Each card object has:
- **`type`**: `"basic"` or `"image"` (or `"cloze"` in the future)
- **`indicator`**: the type indicator for the front (e.g., `"Play"`, `"Novel"`, `"Composer"`, `"Painting"`)
- **`front`**: the full card front text including indicator (e.g., `"Play: the protagonist tricks..."`)
- **`back`**: the card back text
- **`work`**: which work/subtopic the card is from
- **`frequency`**: the approximate frequency of the underlying clue
- **`image_url`**: (optional) URL of an image for the back (basic) or front (image cards)
- **`tags`**: empty list by default `[]` — user adds tags interactively in the card editor

### Basic cards (work-based clues)

For each clue that has specific, learnable content (not just "this Czech composer" identifiers), generate a basic card:

- **Front**: `Indicator: self-contained clue, lowercase start after colon`
- **Back**: `Work Name (Creator)` when the card is about a specific work, or just `Creator Name` when the card is a general fact about the person (collaborations, biographical info, etc.). Only use the `Work (Creator)` format when it makes sense — i.e., the clue is specifically about that work.

The **indicator** is the type of thing being tested. Choose the most specific applicable one:
- Works: `Novel:`, `Play:`, `Poem:`, `Opera:`, `Symphony:`, `Painting:`, `Sculpture:`, `Film:`, `Short Story:` etc.
- Creators: `Author:`, `Composer:`, `Painter:`, `Playwright:`, `Philosopher:` etc.
- Other: `Work:` (generic fallback), `Concept:`, `Event:`, `Place:` etc.

The clue text should be a clean, self-contained statement — not a raw quote from a question. Rewrite if needed for clarity, but preserve the factual content. Preserve proper noun capitalization; only lowercase common words at the start (e.g., "the protagonist" not "The protagonist", but "Vindice" stays capitalized).

Each card object includes an `"indicator"` field storing which indicator was used.

Examples:
- Front: `Play: the protagonist tricks the Duke into kissing a poisoned skull, which eats away at his lips`
  Back: `The Revenger's Tragedy (Thomas Middleton)`
- Front: `Play: bed trick with Diaphanta on wedding night; De Flores starts fire to murder Diaphanta`
  Back: `The Changeling (with William Rowley) (Thomas Middleton)` — keep full work name including collaborators
- Front: `Painting: a white church completely surrounded by greenery, controversially renamed in 2018`
  Back: `Indian Church / Church at Yuquot Village (Emily Carr)`
- Front: `Composer: went deaf in 1874; depicted this with a sustained high E in a string quartet`
  Back: `Bedrich Smetana`

### Image cards (visual arts only)

For topics with embedded images, generate an extra card per image:
- **Front**: the image (stored as `image_url`)
- **Back**: `"Work Name (Artist)"`

### What NOT to card

- Pure identifier clues ("this Czech composer of X") — these are giveaways, not learnable facts
- Clues that are too vague without context
- Clues that essentially restate the answer — if the front is just describing what the back says, it's circular
- Duplicate information already covered by another card

### Card quality rules

- **Never leak the answer on the front.** If the back is "Work (Creator)", do not mention the creator's name on the front. Rewrite to remove it — e.g., "Lawren Harris called this work its artist's best work" not "Lawren Harris called it Carr's best work." Another example:  "totem poles in the wilderness" when the work of art is Totem Pole Paintings (Emily Carr)
- **Use general indicators**: `Artist:` (not `Painter:` or `Sculptor:`), `Author:` (not `Novelist:`), etc.
- **The front must teach something specific.** Every card front should contain a fact that, once memorized, helps you identify the answer in a quizbowl question.

## Image Verification (Visual Arts)

When adding images for paintings/sculptures/artworks, **never guess Wikimedia URLs**. Always use the API:

1. **Search** for the correct filename via `commons.wikimedia.org/w/api.php` with `action=query&list=search&srsearch=QUERY&srnamespace=6`
2. **Get the thumbnail URL** via `en.wikipedia.org/w/api.php` with `action=query&titles=File:FILENAME&prop=imageinfo&iiprop=url&iiurlwidth=500`
3. **Verify** the URL returns HTTP 200 before saving it
4. For **copyrighted works** not on Commons (modern/contemporary art), use a link-only image: `{"url": "", "link": "https://museum-page...", "caption": "Work Name (Year)"}` — this renders as a "View" link instead of an embedded image

## Constraints

- **No outside knowledge for clue content.** Only describe what the clues say.
- **Outside knowledge OK for:** hyperlinks, images, identifying what a referenced work/person is for linking purposes, and metadata fields (year, continent) above.
- **Sentences may contain multiple clues** — separate them during analysis.
- **Giveaway clues** (containing "For 10/ten points") are still clues — they tell you what the most common/easy identification is.
