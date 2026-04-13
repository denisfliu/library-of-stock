---
name: cards
description: Generate or audit Anki cards for a topic's analysis.json.
arguments:
  - name: topic
    description: "Topic name or slug (e.g., \"Smetana\", \"emily_carr\")"
---

# Card Generation

Generate or regenerate the `cards` array for "$ARGUMENTS.topic".

## Step 1: Read Analysis

Read `output/{slug}/analysis.json`. Study all work sections, clues, and any existing cards.

Determine the category and read the appropriate supplement skill for indicator guidance:
- Literature -> `/literature`
- Fine Arts (VFA) -> `/vfa`
- Fine Arts (AFA) -> `/afa`
- Philosophy -> `/philosophy`
- Science -> `/science`

## Step 2: Generate Cards

### Card format

Each card object has:
- **`type`**: MUST be `"basic"` or `"image"` — never the indicator value, never a work type
- **`indicator`**: the type indicator for the front (e.g., `"Play"`, `"Novel"`, `"Composer"`, `"Painting"`)
- **`front`**: for basic cards, the full text including indicator (e.g., `"Play: the protagonist tricks..."`). For image cards, always `""`
- **`back`**: the card back text
- **`work`**: the EXACT `name` of the work section this card belongs to (character-for-character match). The renderer uses this to attach images — missing or wrong `work` = no image on card back
- **`frequency`**: number of times this clue appeared (integer). Never text labels
- **`tags`**: ALWAYS `[]` — user adds tags interactively

### Basic cards

For each clue with specific, learnable content:
- **Front**: `Indicator: self-contained clue, lowercase start after colon` (unless first word is a proper noun)
- **Back**: `Work Name (Creator)` for work-specific clues, or just `Creator Name` for general/biographical facts. The back should be what the indicator names — if indicator is `Photograph:`, back is the photograph

### Indicator rules

Use the **broadest label that still uniquely identifies the type**:
- Works: `Novel:`, `Play:`, `Poem:`, `Opera:`, `Symphony:`, `Painting:`, `Sculpture:`, `Film:`, `Short Story:`, `Work:` (generic fallback)
- Creators: `Author:`, `Composer:`, `Artist:`, `Playwright:`, `Philosopher:`
- Other: `Concept:`, `Event:`, `Place:`
- Prefer broad: `Work:` over `Short Story:`, `Artist:` over `Sculptor:`, `Author:` over `Novelist:`
- Only get specific when broad would be ambiguous (e.g., `Photograph:` if could be mistaken for painting, `Opera:` to distinguish from play)
### What NOT to card

- Pure identifier clues ("this Czech composer of X") — giveaways, not learnable
- Too vague without context
- Circular (front just restates the back)
- Duplicates of existing cards

### Card quality rules

- **Each card tests ONE fact.** Two facts joined by semicolons, "and", or separate clauses = split into two cards. Always.
- **Never leak the answer on the front.** If back is "Work (Creator)", do not mention creator on front.
- **Front must teach something specific** — a fact that helps identify the answer in a quizbowl question.

### Examples

- `Play: the protagonist tricks the Duke into kissing a poisoned skull` -> `The Revenger's Tragedy (Thomas Middleton)`
- `Painting: a white church completely surrounded by greenery, controversially renamed in 2018` -> `Indian Church / Church at Yuquot Village (Emily Carr)`
- `Composer: went deaf in 1874; depicted this with a sustained high E in a string quartet` -> `Bedrich Smetana`

## Step 3: Write Back

Replace ONLY the `cards` field in `output/{slug}/analysis.json`. Do not modify any other field.

## Step 4: Render

```bash
python3 lib/render/render_cards.py
```
