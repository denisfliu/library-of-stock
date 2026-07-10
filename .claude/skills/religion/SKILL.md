---
name: religion
description: Category supplement for Religion — text/figure/practice sectioning, the group religion field, and doctrine card rules.
---

# Religion Category Supplement

## Sectioning for Religion Topics

Organize by the distinct kinds of things clued:

- **Texts and scriptures** — each named text mentioned 3+ times gets its own section (e.g., a specific sutra, book, or epistle)
- **Figures** — founders, prophets, saints, reformers
- **Practices and rituals** — prayers, pilgrimages, dietary laws, rites
- **Holidays and festivals** — each significant holiday with specific clues
- **Doctrines** — named beliefs, creeds, theological concepts
- **Denominations and schools** — branches, sects, movements within the religion
- "General / Giveaway Identifiers" for the standard closers

## Indicators

- `Text:` for scriptures and religious writings
- `Figure:` for founders, prophets, saints
- `Practice:` for rituals and observances
- `Holiday:` for festivals and holy days
- `Doctrine:` for named beliefs and theological concepts
- `Denomination:` for branches, sects, and schools

## Cards

- `Text: contents and context described` -> `Text Name (religion)`
- `Practice: what is done and when` -> `Practice Name`
- `Doctrine: the belief described` -> `Doctrine Name (religion)`
- `Holiday: observances described` -> `Holiday Name`
- Never leak the answer on the front — scrub the topic name and transparent synonyms from clue text.

## Metadata

- `group` (optional, NEW): the religion — "Buddhism", "Islam", "Judaism", "Christianity", "Hinduism", "Sikhism", etc.
- `year`: only when well-defined — a founder's birth year or a text's composition/publication date. Omit for practices, holidays, and most doctrines. Negative for BCE.
- `continent`/`country`: where the topic originated or is primarily associated.
- `tags`: recognized movements/schools only (e.g., `["Zen"]`, `["Hasidism"]`) — not the religion itself, which belongs in `group`.

## Universal Reminders

- **No outside knowledge for clue content** — describe only what the clues say; outside knowledge is OK for hyperlinks and metadata (years, `group`).
- Text/section descriptions are **mini-paragraphs**, not one-liners like "Its most sacred text."

## Common Pitfalls

- Figures shared across traditions (Abraham, Moses, Jesus) are clued differently by each — check the answerline and which tradition's clues dominate.
- Religion vs. Mythology is a fuzzy boundary at qbreader (Hindu deities appear in both) — trust the question's category field.
- Text titles have many transliterations (Quran/Koran, Daodejing/Tao Te Ching) — normalize when matching answerlines.
