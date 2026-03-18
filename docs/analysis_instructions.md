# Stock Knowledge Analysis Instructions

When analyzing clues for a quizbowl topic, follow this protocol. **Only use information from the clues themselves** — do not inject outside knowledge except for hyperlinks and images.

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
1. **Work name** and brief identification (from clues)
2. **Clues ranked by frequency**, each with:
   - A clear statement of what the clue is
   - How many times it appeared (approximate)
   - 1-2 example quotes from actual questions showing how it's worded
3. Mark which clues tend to appear in power (early/hard) vs. giveaway (late/easy)

## Step 5: Suggest Recursive Searches

After analysis, identify works or subtopics that deserve their own deep dive. For example, if "The Moldau" comes up 10 times with varied clues, suggest searching for it as its own answerline. Present these as suggestions for user confirmation.

## Output Format

The final output should be an HTML file with:
- Collapsible sections for each work/subtopic
- Clue frequency indicators (visual, like bars or counts)
- Example quotes styled distinctly (blockquote or similar)
- Power vs. giveaway indicators
- Hyperlinks to relevant Wikipedia articles for further reading
- Space for images (paintings, scores) where relevant — these can be added later
- Clean, readable typography suitable for studying

## Constraints

- **No outside knowledge for clue content.** Only describe what the clues say.
- **Outside knowledge OK for:** hyperlinks, images, identifying what a referenced work/person is for linking purposes.
- **Sentences may contain multiple clues** — separate them during analysis.
- **Giveaway clues** (containing "For 10/ten points") are still clues — they tell you what the most common/easy identification is.
