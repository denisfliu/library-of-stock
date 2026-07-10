---
name: social-science
description: Category supplement for Social Science — thinker-centric sectioning, genre from alternate_subcategory, and experiment card rules.
---

# Social Science Category Supplement

## Sectioning for Social Science Topics

Social Science is mostly **thinker-centric** — the literature works model fits. For a thinker, organize by:

- **Major works** — each book/paper mentioned 3+ times gets its own section
- **Theories and concepts** — named ideas that span works (e.g., "Cognitive Dissonance", "Comparative Advantage") get their own sections, philosophy-style
- **Experiments** — landmark experiments (Milgram obedience, Stanford prison, Bobo doll, Asch conformity) **get their own sections**, with both **method clues** (setup, procedure, participants) and **findings clues** (results, interpretations, criticisms)
- "Other Works" for minor pieces; "General / Biographical" for identifiers

For a concept/experiment topic itself, section by originator, method, findings, and later responses/replications.

## Indicators

- `Economist:`, `Psychologist:`, `Sociologist:`, `Anthropologist:`, `Linguist:` — match the field; fall back to `Thinker:` if unclear
- `Theory:`, `Concept:` for named ideas
- `Experiment:` for studies
- `Work:` for books and papers

## Cards

- `Work: argument and contents described` -> `Work Title (Author)`
- `Experiment: method or findings described` -> `Experiment Name (Researcher)`
- `Theory: the claim described` -> `Theory Name (Thinker)`
- `Economist: biographical or idea clue` -> `Thinker Name`
- Never leak the answer on the front — theory names often contain the thinker's name (Nash equilibrium); scrub accordingly.

## Metadata

- `genre`: set to the qbreader **alternate_subcategory** — one of `Psychology`, `Anthropology`, `Economics`, `Linguistics`, `Sociology`, `Other Social Science`. This mirrors how Other Science uses `genre`.
- `year`: **birth year** for thinkers; publication year for a standalone work; the year conducted for a standalone experiment.
- `tags`: recognized schools only (e.g., `["Behaviorism"]`, `["Chicago School"]`, `["Structuralism"]`).

## Universal Reminders

- **No outside knowledge for clue content** — describe only what the clues say; outside knowledge is OK for hyperlinks and metadata (years, `genre`).

## Common Pitfalls

- Thinkers straddle categories — Freud and Marx appear in Philosophy, Adam Smith in Philosophy or History. Include only questions categorized as Social Science.
- Experiments are often clued for the researcher AND as their own answerline — check which one the question wants.
- Work descriptions must be mini-paragraphs synthesizing the clues, not one-liners like "His most famous study."
