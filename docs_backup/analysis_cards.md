# Anki Card Generation

After analysis, generate a default set of Anki cards from the clues. Store them in the `"cards"` field of the analysis JSON as a list of card objects.

## Step 1: Generate Cards

### Card format

Each card object has:
- **`type`**: MUST be `"basic"` or `"image"` — never the indicator value, never a work type like "Fanfare" or "Symphony"
- **`indicator`**: the type indicator for the front (e.g., `"Play"`, `"Novel"`, `"Composer"`, `"Painting"`)
- **`front`**: for `"basic"` cards, the full card front text including indicator (e.g., `"Play: the protagonist tricks..."`). For `"image"` cards, always `""` — the image is the front.
- **`back`**: the card back text
- **`work`**: the EXACT `name` of the work section this card belongs to (must match character-for-character). The renderer uses this to automatically attach the work's image to the card — missing or wrong `work` = no image on card back.
- **`frequency`**: the number of times this clue appeared across all questions (integer, e.g. `3`). Never use text labels like "common" or "rare".
- **`tags`**: ALWAYS set to empty list `[]` — do NOT copy from topic-level tags or work names. The user adds card tags interactively in the card editor.

### Basic cards (work-based clues)

For each clue that has specific, learnable content (not just "this Czech composer" identifiers), generate a basic card:

- **Front**: `Indicator: self-contained clue, lowercase start after colon`
- **Back**: `Work Name (Creator)` when the card is about a specific work, or just `Creator Name` when the card is a general fact about the person (collaborations, biographical info, etc.). The back should be the thing the indicator names — if the indicator is `Photograph:`, the back is the photograph, not the photographer.

The **indicator** tells the reader what type of thing they're trying to identify. Use the **broadest label that still uniquely identifies the type** — don't over-specify. Match the indicator to what the clue is actually about, not the creator's general medium. Think about what the thing *is*, not what the person *does*.
- Works: `Novel:`, `Play:`, `Poem:`, `Opera:`, `Symphony:`, `Painting:`, `Sculpture:`, `Film:`, `Short Story:` etc.
- Creators: `Author:`, `Composer:`, `Artist:`, `Playwright:`, `Philosopher:` etc.
- Other: `Work:` (generic fallback), `Concept:`, `Event:`, `Place:` etc.
- Prefer broad: `Work:` over `Short Story:`, `Artist:` over `Sculptor:`, `Author:` over `Novelist:`
- Only get specific when the broad label would be ambiguous or misleading — e.g., use `Photograph:` if the work could be mistaken for a painting, `Opera:` to distinguish from a play

The clue text should be a clean, self-contained statement — not a raw quote from a question. Rewrite if needed for clarity, but preserve the factual content. Preserve proper noun capitalization; only lowercase common words at the start (e.g., "the protagonist" not "The protagonist", but "Vindice" stays capitalized).

Each card object includes an `"indicator"` field storing which indicator was used.

### Examples

- Front: `Play: the protagonist tricks the Duke into kissing a poisoned skull, which eats away at his lips`
  Back: `The Revenger's Tragedy (Thomas Middleton)`
- Front: `Play: bed trick with Diaphanta on wedding night; De Flores starts fire to murder Diaphanta`
  Back: `The Changeling (with William Rowley) (Thomas Middleton)` — keep full work name including collaborators
- Front: `Painting: a white church completely surrounded by greenery, controversially renamed in 2018`
  Back: `Indian Church / Church at Yuquot Village (Emily Carr)`
- Front: `Composer: went deaf in 1874; depicted this with a sustained high E in a string quartet`
  Back: `Bedrich Smetana`

### What NOT to card

- Pure identifier clues ("this Czech composer of X") — these are giveaways, not learnable facts
- Clues that are too vague without context
- Clues that essentially restate the answer — if the front is just describing what the back says, it's circular
- Duplicate information already covered by another card

### Card quality rules

- **Each card tests ONE fact.** This is the most important rule. If a front contains two independent facts joined by semicolons, "and", or separate clauses, split them into separate cards. Two facts = two cards, always. A card with "X; also Y" is wrong — make one card for X and one for Y.
- **Never leak the answer on the front.** If the back is "Work (Creator)", do not mention the creator's name on the front. Rewrite to remove it — e.g., "Lawren Harris called this work its artist's best work" not "Lawren Harris called it Carr's best work."
- **Use general indicators**: `Artist:` (not `Painter:` or `Sculptor:`), `Author:` (not `Novelist:`), etc.
- **The front must teach something specific.** Every card front should contain a fact that, once memorized, helps you identify the answer in a quizbowl question.
