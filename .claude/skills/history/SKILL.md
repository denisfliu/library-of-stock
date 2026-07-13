---
name: history
description: Category supplement for History — event/period/figure sectioning, year_end for spans, and battle/treaty/ruler card rules.
---

# History Category Supplement

## Sectioning for History Topics

History topics come in three main shapes — section accordingly:

- **Events** (battles, treaties, revolutions, assassinations) — each named event mentioned 3+ times gets its own section
- **Periods/eras** (dynasties, reigns, movements) — section by phase or by the major events within the period
- **Figures** (rulers, generals, politicians) — section by their **major acts and events**, not by "works": key battles fought, laws passed, treaties signed, scandals, downfall
- For a **war topic**: section by campaigns/battles, causes, key figures/commanders, and aftermath/peace settlement
- Always include "General / Giveaway Identifiers"
- **Causally-linked event chains** (e.g. Bank War → Specie Circular → Panic of 1837): split into separate sections only when each link is independently clued or has its own answerline presence; otherwise keep the chain as one section
- **Spouses/relatives with their own answerline**: give them a section on the figure's page when they're clued only through the figure; they warrant a standalone topic only with independent question presence
- A **Legacy / Memory & Cultural Depictions** section is normal for major figures (eponymous places, currency, statues, songs, plays)

## Indicators

- `Battle:`, `Treaty:`, `War:`, `Event:` for discrete happenings
- `Ruler:`, `Leader:`, `Figure:` for people
- `Dynasty:`, `Empire:`, `Period:` for spans
- `Law:`, `Document:` for legislation and primary documents
- `Institution:` for named organizations (banks, parliaments, companies)
- `Case:` for court cases
- Legacy/cultural-depiction sections: `Event:` for commemorations, `Work:` for named artworks/songs/plays about the figure

## Cards

The back is **the thing the indicator names**:
- `Battle: description of the engagement` -> `Battle Name (war, if applicable)`
- `Treaty: terms and signatories described` -> `Treaty Name`
- `Ruler: deeds described` -> `Ruler Name`
- `Event: what happened` -> `Event Name`
- On a figure's page, the back within an event/institution/law section is **the named entity** (the act, bank, treaty, case) — the figure's name is the back only in biographical/giveaway sections
- Never leak the answer on the front — strip the topic's name and obvious derivatives from the clue text

## Metadata

- `year`: event start year, or a person's **birth** year (Andrew Jackson → 1767, NOT 1829 when his presidency began). Negative for BCE.
- `year_end` (optional, NEW): end year for anything with duration — periods, wars, empires, dynasties, movements. Omit for point events and people.
- `tags`: recognized movements/dynasties only (e.g., `["Tudor"]`, `["Reconstruction"]`) — NOT broad labels like "European history."
- Subcategories: American History, Ancient History, European History, World History, Other History. `genre` stays `""`.

## Universal Reminders

- **No outside knowledge for clue content** — describe only what the clues say; outside knowledge is OK for hyperlinks and metadata (years, countries).
- Section descriptions are **mini-paragraphs**, not one-liners like "His most famous battle."

## Common Pitfalls

- **Don't mix in Literature or Mythology clues about the same figure.** Julius Caesar the historical general is a History topic; clues about Shakespeare's play or his deification are Lit/Myth — check the question's category and answerline context.
- The same battle may be clued for the war, the commander, or the location — only include questions where the topic IS the answer.
- Regnal numbers and shared names (multiple King Charleses, two Roosevelts) make answerline checking essential.
