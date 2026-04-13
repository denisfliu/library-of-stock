---
name: afa
description: Category supplement for Auditory Fine Arts — sectioning, indicators, score clues, and AFA-specific card rules.
---

# Auditory Fine Arts Category Supplement

## Topic Types

AFA topics come in four forms — adjust sectioning accordingly:

**Composer (person):** Organize by major works, each getting its own section. Add `"General / Biographical"` for career-level clues (nationality, teachers, dedications, hearing loss, etc.) and `"Other Works"` for infrequently clued pieces.

**Individual work:** Organize by movement or section (`"First Movement (Allegro con brio)"`, `"Adagio"`, `"Finale"`, etc.). Add a top-level section named after the work itself for whole-work clues (premiere, dedication, key, form).

**Genre or period:** Organize by key representative works or composers, with a section per major figure/work.

**Performing ensemble:** Organize by repertoire, premieres, and commissions.

## Indicators

Choose the most specific applicable indicator:

- `Symphony`, `Concerto`, `Sonata`, `String Quartet`, `Opera`, `Oratorio`, `Cantata`, `Requiem`
- `Tone Poem`, `Overture`, `Suite`, `Prelude`, `Etude`, `Nocturne`, `Ballade`
- `Ballet`, `Mass`, `Motet`, `Lied`, `Art Song`, `Song Cycle`
- `Composer`, `Conductor`, `Performer` — for general/biographical sections
- `Movement` — when the section is a single named movement of a larger work

## Metadata

```json
{
  "category": "Fine Arts",
  "subcategory": "Auditory Fine Arts",
  "genre": "Classical"
}
```

Use `"genre"` to distinguish within AFA: `"Classical"`, `"Opera"`, `"Jazz"`, `"Folk"`, `"Contemporary"`, `"Baroque"`, `"Romantic"`.

## Score Clues

Score clues capture a musical excerpt as ABC notation for audio study cards.

### When to write a score clue

**Only write ABC notation when the question text names specific pitches or rhythms explicitly** — enough that a musician could notate from the description:

- "opens with the ascending notes F, B-flat, F" -> can notate
- "dotted eighth F, sixteenth D-flat, low half note A-flat over a pedal" -> can notate
- "opens with a Mannheim rocket in the low strings" -> verbal only, no ABC
- "a lyrical oboe theme in the second movement" -> verbal only, no ABC

If the clue is not pitch-explicit, include it as a regular text clue. Do NOT force ABC notation.

### ABC notation rules

- **2-4 bars maximum** — enough to be recognizable
- Always use `K:C` (no key signature) — use explicit accidentals (`_B` for B-flat, `^F` for F-sharp)
- Uppercase (`C`-`B`) = middle octave; lowercase (`c`-`b`) = one octave higher
- Note lengths with `L:1/4`: `C` = quarter, `C2` = half, `C4` = whole, `C/2` = eighth
- Add `%%MIDI program N` to set instrument. Common: Trumpet=56, Horn=60, Trombone=57, Violin=40, Flute=73, Oboe=68, Clarinet=71, Piano=0
- Always set `needs_review: true`

### `score_clues` field format

Add a top-level `"score_clues"` array. The `"work"` field must exactly match the work section's `"name"` — character for character.

```json
"score_clues": [
  {
    "work": "Fanfare for the Common Man",
    "indicator": "high",
    "description": "Opening brass gesture after percussion intro",
    "source_text": "trumpets playing the ascending notes F, B-flat, F",
    "abc": "X:1\nT:Fanfare opening\n%%MIDI program 56\nM:4/4\nL:1/4\nK:C\n|F2 _B2|f4||",
    "needs_review": true
  }
]
```

Set `"abc": null` and `"needs_review": false` for verbal-only clues stored for reference but not renderable.

## Cards

### Basic cards

**The `"type"` field must be `"basic"` — never the indicator value.** AFA has many indicator words (`Fanfare`, `Symphony`, `Concerto`) that look like types but are not.

- `Work: opens with four repeated notes in C minor` -> `Symphony No. 5 (Beethoven)`
- `Composer: went deaf in 1874; depicted this with a sustained high E in a string quartet` -> `Bedrich Smetana`
- `Opera: the heroine stabs herself with Scarpia's own knife` -> `Tosca (Puccini)`

### Audio cards

**Do not create audio cards manually.** They are auto-generated at build time from `score_clues` entries with a resolved `mp3` path.

### What NOT to card

- Pitch-explicit clues already captured as score clues — avoid duplicating as both text and audio
- Clues that simply name the composer without a testable fact
- Tempo markings or key signatures in isolation unless specifically clued
