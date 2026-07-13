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
- **Tightly-coupled thin entities** (paired rituals, paired reform sects) that individually miss the 3+ threshold: combine into one joint section ("Samayika and Pratikraman") rather than fragmenting into one-clue sections
- **Figure classes vs. individuals** (Tirthankaras, Sikh Gurus, prophets): give the class its own section for class-level facts; individuals get their own sections when they clear 3+ mentions or carry specific clues — cross-link between them

## Indicators

- `Text:` for scriptures and religious writings
- `Figure:` for founders, prophets, saints
- `Practice:` for rituals and observances
- `Holiday:` for festivals and holy days
- `Doctrine:` for named beliefs and theological concepts
- `Denomination:` for branches, sects, and schools
- `Religion:` for the General/Giveaway section when the topic IS a religion
- Mantras/prayers/hymns: `Text:` when they have fixed quotable content, `Practice:` when clued through their performance
- Adherent-community clues (merchants, diaspora, demographics): fold into General unless heavy enough for their own section

## Cards

- `Text: contents and context described` -> `Text Name (religion)`
- `Practice: what is done and when` -> `Practice Name`
- `Doctrine: the belief described` -> `Doctrine Name (religion)`
- `Holiday: observances described` -> `Holiday Name`
- Never leak the answer on the front — scrub the topic name and transparent synonyms from clue text.

## Metadata

- `group` (optional, NEW): the religion — "Buddhism", "Islam", "Judaism", "Christianity", "Hinduism", "Sikhism", etc.
- `year`: only when well-defined — a founder's birth year or a text's composition/publication date. When the topic is a religion itself, use the most recent human founder's traditional birth year (Jainism → Mahavira, -599); omit if there is no meaningful founder date. Omit for practices, holidays, and most doctrines. Negative for BCE.
- `continent`/`country`: where the topic originated or is primarily associated.
- `tags`: recognized movements/schools only (e.g., `["Zen"]`, `["Hasidism"]`) — not the religion itself, which belongs in `group`.

## Universal Reminders

- **No outside knowledge for clue content** — describe only what the clues say; outside knowledge is OK for hyperlinks and metadata (years, `group`).
- Text/section descriptions are **mini-paragraphs**, not one-liners like "Its most sacred text."

## Common Pitfalls

- Figures shared across traditions (Abraham, Moses, Jesus) are clued differently by each — check the answerline and which tradition's clues dominate.
- Religion vs. Mythology is a fuzzy boundary at qbreader (Hindu deities appear in both) — trust the question's category field.
- Text titles have many transliterations (Quran/Koran, Daodejing/Tao Te Ching) — normalize when matching answerlines.
