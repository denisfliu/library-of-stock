# American Literature overview — section authoring instructions

You are writing one fragment of the new `sections.txt` for the American
Literature overview page. Work from the repo root
`C:\Users\denis\code\library-of-stock`. On this machine run Python as `py`,
not `python`.

## Inputs

- Your assigned `section_XX_input.txt` file(s) in this directory. Columns:
  `frequency<TAB>answerline<TAB>match-status<TAB>parent<TAB>old_note`
  - `answerline` is the EXACT raw curated string — copy it verbatim
    (including any quotes/punctuation) wherever it appears in your output.
  - `parent` names the top-level entry this row should nest under (`-` = top
    level). Rows are already grouped: a parent row is followed by its children.
  - `old_note` is the note from the previous page version (`-` = none). Reuse
    the fact content when good, but tighten it to the style below.
  - Notes may carry a `[merge? ...]` hint — candidate same-entity variants.
- Style exemplar: read `output/_categories/opera/sections.txt` lines 1-70.
  Match its register exactly.
- To see actual question text for an answerline (REQUIRED for any entry whose
  note you cannot write confidently from the old note alone, and for
  verifying `[merge?]` hints):
  `PYTHONIOENCODING=utf-8 py lib/sweep/capture_questions.py american_literature --show "ANSWERLINE"`

## Output format (parsed by lib/sweep/author.py assemble — strict)

```
# Exact Section Header You Were Given
> One-sentence section blurb (only if instructed to write the blurb).
Raw Answer | note text
Raw Answer = Variant Raw Answer -> Canonical Display Name | note text
- Nested Raw Answer | note text
```

- `#` header: use EXACTLY the header string(s) assigned to you.
- `- ` nests an entry under the nearest preceding top-level entry (author's
  works, poems, characters). One level only.
- `= Variant` merges a true same-entity variant answerline into the entry
  (e.g. `Kurt Vonnegut = Kurt Vonnegut, Jr. = Kurt Vonnegut Jr.`). BOTH sides
  must be raw curated strings from your input. Only merge when the questions
  confirm they are the same answer — never merge merely-related answers
  (e.g. `Uncle Tom` the character is NOT a variant of `Uncle Tom's Cabin`;
  keep the character as a nested entry instead).
- `-> Canonical` sets the display name when the raw string is misspelled,
  uncapitalized, unpunctuated, or a variant-merge needs a clean title
  (`Cosi fan tutte -> Così fan tutte`). Optional otherwise.
- Every input answerline must appear EXACTLY ONCE in your fragment — either
  as a top-level entry, a nested entry, or absorbed as a `=` variant.
  None may be dropped; none may be invented.

## Note style (the part that takes judgment)

- 10-20 words. Relations + key works. No editorializing ("greatest",
  "beloved"), no full sentences needed, semicolons fine.
- An author note names their most-clued works; a work note gives its plot
  hook / famous line / key characters as the questions clue them.
- Ordering within a section: pedagogical, era/school flow — related entries
  adjacent (authored order is preserved on the page; frequency is only a
  badge). You may reorder rows freely within your section.
- Common-link entries: say what the questions actually span (the bucketing
  pass verified many of these — trust question evidence, not name vibes).
- Foreign authors/works: one clause on who they are + why they appear in
  American Literature questions if the questions show it.

## Process

1. Read the exemplar and your input file(s).
2. Consult questions for weak/ambiguous entries and `[merge?]` hints.
3. Write your fragment to the output path you were given.
4. Self-check before finishing: every input answerline present exactly once,
   verbatim; headers exact; every line matches the grammar above.

Your final message: entry count per header, which `[merge?]` hints you
accepted/rejected and why (one line each), entries you consulted questions
for, and anything you believe is misfiled in your section (do NOT move it
yourself — place it, flag it).
