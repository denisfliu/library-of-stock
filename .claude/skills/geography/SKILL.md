---
name: geography
description: Category supplement for Geography — physical/human/history-at-place sectioning, the coordinates field, and place card rules.
---

# Geography Category Supplement

## Sectioning for Places

Organize a place (country, city, river, mountain range, region) by:

- **Physical features** — rivers, mountains, lakes, deserts, climate; each named feature mentioned 3+ times gets its own section
- **Human geography** — cities, economy, industries, peoples, languages
- **History at the place** — events clued through the place (battles fought there, explorers, founding); keep these as geography clues about the place, not history topics
- **Neighboring and contained features** — borders, tributaries, islands within, what the place is part of
- "General / Giveaway Identifiers" for the standard closers

## Indicators

- `River:`, `Mountain:`, `Lake:`, `Desert:`, `Island:` for physical features
- `City:` for settlements
- `Region:` for larger areas, provinces, and countries
- `Landmark:` for specific sites and structures

## Cards

- `River: course, tributaries, cities on its banks described` -> `River Name`
- `City: features and location described` -> `City Name (country)`
- `Mountain: range, height context, notable facts` -> `Mountain Name`
- Never leak the answer on the front — place names embed in demonyms and derived names (the "Amazonian" basin on an Amazon card); scrub them.

## Metadata

- `coordinates` (optional, NEW): `[lat, lon]` in decimal degrees (e.g., `[-3.4653, -62.2159]`). Outside knowledge is OK for coordinates, just as it is for years. Use a representative point: the feature's center, a river's mouth, a city's center.
- `country` and `continent`: **required**. For features spanning several countries, pick the most-associated one.
- `year`: usually omitted; only for things with a founding date that clues actually engage with.
- `tags`: leave empty unless a genuinely recognized classification applies — no broad descriptors like "African geography."

## Universal Reminders

- **No outside knowledge for clue content** — describe only what the clues say; outside knowledge is OK for hyperlinks and metadata (coordinates, country, continent).
- Feature/section descriptions are **mini-paragraphs**, not one-liners like "Its longest river."

## Common Pitfalls

- Same-named places abound (Georgia, Paris, Tripoli) — check the answerline and clue context to keep the right one.
- A river clued as the site of a battle may be a History question; only include questions categorized as Geography with the place as the answer.
- Physical features vs. named political units (the island of Ireland vs. the Republic of Ireland) are distinct answerlines.
