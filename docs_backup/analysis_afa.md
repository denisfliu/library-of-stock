# Auditory Fine Arts Analysis Guide

Supplement to `analysis_core.md`. Read the core instructions first.

## Topic Types

AFA topics come in four forms — adjust sectioning accordingly:

**Composer (person):** Organize by major works, each getting its own section. Add `"General / Biographical"` for career-level clues (nationality, teachers, dedications, hearing loss, etc.) and `"Other Works"` for infrequently clued pieces.

**Individual work:** Organize by movement or section (`"First Movement (Allegro con brio)"`, `"Adagio"`, `"Finale"`, etc.). Add a top-level section named after the work itself (e.g. `"Fanfare for the Common Man"`) for whole-work clues (premiere, dedication, key, form).

**Genre or period:** Organize by key representative works or composers, with a section per major figure/work.

**Performing ensemble:** Organize by repertoire, premieres, and commissions.

## Indicators

Choose the most specific applicable indicator:

- `Symphony`, `Concerto`, `Sonata`, `String Quartet`, `Opera`, `Oratorio`, `Cantata`, `Requiem`
- `Tone Poem`, `Overture`, `Suite`, `Prelude`, `Étude`, `Nocturne`, `Ballade`
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

Use `"genre"` to distinguish subcategories within AFA:
`"Classical"`, `"Opera"`, `"Jazz"`, `"Folk"`, `"Contemporary"`, `"Baroque"`, `"Romantic"`.

## Score Clues

Score clues are the audio equivalent of image clues: they capture a musical excerpt as ABC notation so a listener can recognize it, and generate an audio card for study.

### When to write a score clue

**Only write ABC notation when the question text names specific pitches or rhythms explicitly** — enough that a musician could notate it from the description alone:

✅ `"opens with the ascending notes F, B-flat, F"` → can notate
✅ `"dotted eighth F, sixteenth D-flat, low half note A-flat over a pedal"` → can notate
✅ `"four timpani strikes on D before the soloist enters"` → can notate
❌ `"opens with a Mannheim rocket in the low strings"` → verbal only
❌ `"a lyrical oboe theme in the second movement"` → verbal only
❌ `"a passage of surprising harmonic ambiguity"` → verbal only

If the clue is not pitch-explicit, include it as a regular text clue in the work section. Do **not** force ABC notation.

### ABC notation rules

- Write **2–4 bars maximum** — enough to be recognizable, not a transcription
- Always use `K:C` (no key signature) — use explicit accidentals (`_B` for B-flat, `^F` for F-sharp) to avoid parser ambiguity
- Uppercase letters (`C`–`B`) = middle octave; lowercase (`c`–`b`) = one octave higher. Ascending sequences must reach the right octave: "ascending F, B-flat, F" → `F _B f` (F4, Bb4, F5), not `F _B F` (which stays in the same octave)
- Note lengths with `L:1/4`: `C` = quarter, `C2` = half, `C4` = whole, `C/2` = eighth
- Add `%%MIDI program N` to set the instrument. Common: Trumpet=56, Horn=60, Trombone=57, Violin=40, Flute=73, Oboe=68, Clarinet=71, Piano=0 (default). Use the instrument named in the clue
- Always set `needs_review: true`

### `score_clues` field format

Add a top-level `"score_clues"` array to the analysis JSON. One entry per extractable musical excerpt:

**Critical:** The `"work"` field must be an exact copy of the `"name"` field of the corresponding work section in the analysis JSON — character for character. If they don't match, the clip will not render on the study page.

```json
"score_clues": [
  {
    "work": "Fanfare for the Common Man",
    "indicator": "high",
    "description": "Opening brass gesture after percussion intro",
    "source_text": "trumpets playing the ascending notes F, B-flat, F",
    "abc": "X:1\nT:Fanfare opening\n%%MIDI program 56\nM:4/4\nL:1/4\nK:C\n|F2 _B2|f4||",
    "needs_review": true
  },
  {
    "work": "Symphony No. 5 – First Movement",
    "indicator": "high",
    "description": "Oboe cadenza at the recapitulation",
    "source_text": "first oboe plays an unexpected adagio cadenza on a half cadence ending with a fermata on G",
    "abc": null,
    "needs_review": false
  }
]
```

Set `"abc": null` and `"needs_review": false` for verbal-only clues stored in `score_clues` for reference but not renderable as notation.

Only include a `score_clues` entry for excerpts that appear in actual question text. Do not invent or recall from general musical knowledge — base it on what the questions describe.

## Cards

### Basic cards

Follow the same rules as all other categories. **The `"type"` field must be `"basic"` — never the indicator value.** AFA has many indicator words (`Fanfare`, `Symphony`, `Concerto`) that look like types but are not. The indicator goes in `"indicator"`, not `"type"`.

For AFA:

- `Work: opens with four repeated notes in C minor` → `Symphony No. 5 (Beethoven)`
- `Composer: went deaf in 1874; depicted this with a sustained high E in a string quartet` → `Bedřich Smetana`
- `Opera: the heroine stabs herself with Scarpia's own knife after he reneges on the bargain` → `Tosca (Puccini)`
- `Work: opens with the slurred sostenuto 4/4 melody over a dominant pedal that is respelled in C-sharp minor in the middle section` → `Raindrop Prelude (Chopin)`

### Audio cards

**Do not create audio cards manually.** They are auto-generated at build time from `score_clues` entries that have a resolved `mp3` path (after `lib/render/render_audio.py` runs). The front of an audio card is the `description` field; the back is the work and composer name.

### What NOT to card

- Pitch-explicit clues that are already captured as score clues — avoid duplicating the same fact as both a text card and an audio card
- Clues that simply name the composer without a testable fact ("this Austrian composer")
- Tempo markings or key signatures in isolation unless they are clued specifically in questions

