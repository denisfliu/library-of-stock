---
name: vfa
description: Category supplement for Visual Fine Arts — sectioning, indicators, image handling, and architect rules.
---

# Visual Fine Arts Category Supplement

## Sectioning for Visual Artists

Organize by **individual works or work groups** (series, chapel cycles, etc.):
- Major paintings/sculptures each get their own section
- Series can be grouped (e.g., "Thirty-Six Views of Mount Fuji" as one section)
- "Other Works" for infrequently clued pieces
- "General / Biographical" for common identifiers

Every work section needs an `indicator` field: `Painting`, `Sculpture`, `Fresco`, `Print`, `Engraving`, `Mural`, `Installation`, `Building`, `Architect`.

For movements (Ashcan School, YBA, etc.): use `Movement` indicator and organize by key members/exhibitions.

### Architect topics (Bramante, Aalto, Wren, etc.)
- `Building:` for physical structures — churches, museums, palaces, courtyards, staircases, etc. Never use `Church:`, `Cathedral:`, or `Architecture:` as an indicator.
- `Location:` for non-building works — urban plans, parks, master plans, landscapes, designed spaces that are not structures (e.g., Central Park, Battery Park City).
- `Architect:` for general/biographical sections.
- Image cards: for every work with a non-empty `images` array, generate an image card (`"type": "image"`).

## Cards

- `Painting: clue` -> `Work Name (Artist)` for work-specific clues
- `Artist: clue` -> `Artist Name` for general/biographical
- `Movement: clue` -> `Movement Name` for schools/movements
- Image recognition cards for works with embedded images

## Images

### Agent image step

After writing `analysis.json`, run the image finder scoped to your topic:
```bash
python3 lib/images/fix_images.py --slug {slug}
```
The file lock serializes concurrent agents automatically — no rate limiting risk. Run this **before** rendering so the HTML includes any found images.

**After `fix_images.py` finishes**, check each visual work section. For any work still missing an image (`"images": []`), add a Wikipedia link object:
```json
{"url": "", "link": "https://en.wikipedia.org/wiki/Work_Title", "caption": "Work Title"}
```
The link must point to the specific work's article, not the artist's general page. Most 20th/21st century works are copyrighted and won't be on Commons — always add a Wikipedia link for these.

### Core rule

**Never manually construct or guess Wikimedia URLs.** All image lookups go through `fix_images.py` which uses the verified API search pipeline.

### Image pipeline (post-batch)

1. Run `python3 lib/images/fix_images.py` — searches Commons for all missing visual works
2. Review `cache/pending_images.json` — approve or reject ambiguous matches
3. For works that remain imageless (copyrighted), manually add Wikipedia links
4. Run `python3 lib/images/verify_images.py` to confirm all URLs return HTTP 200

### Rate limiting

`lib/images/images.py` uses a **file lock** (`cache/.images.lock`) to serialize API access. Rules:
1. All operations go through `lib/images/images.py` (2s delays, `Retry-After` support)
2. Persistent cache (`cache/image_urls.json`) — repeated runs are free
3. Agents must NOT use WebSearch, manual Commons lookups, or construct URLs

### Copyrighted works

For works not on Commons (most 20th/21st century art): `{"url": "", "link": "https://en.wikipedia.org/wiki/...", "caption": "Work Name"}`
Links must point to the specific work's article, not the artist's general page.

## Common Pitfalls

- Many artists share subjects (Crucifixion, Annunciation, Saint George) — verify the image is the right artist's version
- 20th/21st century works are almost always copyrighted — use Wikipedia links
- For architects: `Architect` for person cards, `Building` for structures, `Location` for non-building spaces. Never `Architecture:`
- Some VFA topics cross into literature (William Blake poems, Rossetti sonnets) — use appropriate indicators for each work type
