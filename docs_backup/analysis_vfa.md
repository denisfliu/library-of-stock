# Visual Fine Arts Analysis Guide

Supplement to `analysis_instructions.md`. Read the core instructions first.

## Sectioning for Visual Artists

Organize by **individual works or work groups** (series, chapel cycles, etc.):
- Major paintings/sculptures each get their own section
- Series can be grouped (e.g., "Thirty-Six Views of Mount Fuji" as one section)
- "Other Works" for infrequently clued pieces
- "General / Biographical" for common identifiers

Every work section needs an `indicator` field: `Painting`, `Sculpture`, `Fresco`, `Print`, `Engraving`, `Mural`, `Installation`, `Building`, `Architect`.

For movements (Ashcan School, YBA, etc.): use `Movement` indicator and organize by key members/exhibitions.

For **architect topics** (Bramante, Aalto, Wren, etc.):
- Use `Building:` for architectural works that are physical structures — churches, museums, palaces, courtyards, staircases, etc. Never use a more specific type (`Church:`, `Cathedral:`) and never use `Architecture:` (the genre name) as an indicator.
- Use `Location:` for non-building works — urban plans, parks, master plans, landscapes, or other designed spaces that are not themselves structures (e.g., Central Park, Battery Park City).
- Use `Architect:` for general/biographical sections about the person.
- Image cards: for every work with a non-empty `images` array, generate an image card (`"type": "image"`).

## Cards

- `Painting: clue` → `Work Name (Artist)` for work-specific clues
- `Artist: clue` → `Artist Name` for general/biographical
- `Movement: clue` → `Movement Name` for schools/movements
- Image recognition cards for works with embedded images

## Images

### Agent image step

After writing `analysis.json`, run the image finder scoped to your topic:
```bash
python3 lib/images/fix_images.py --slug {slug}
```
The file lock in `images.py` serializes concurrent agents automatically — no rate limiting risk even when multiple VFA agents run in parallel. Run this **before** rendering so the HTML includes any found images.

**After `fix_images.py` finishes**, check each visual work section. For any work still missing an image (`"images": []`), add a Wikipedia link object:
```json
{"url": "", "link": "https://en.wikipedia.org/wiki/Work_Title", "caption": "Work Title"}
```
The link must point to the specific work's article, not the artist's general page. Use `Artist_Name#Section` only if no dedicated article exists. Most 20th/21st century works are copyrighted and won't be on Commons — always add a Wikipedia link for these.

Post-batch `fix_images.py` (without `--slug`) catches any remaining stragglers and handles pending LLM review.

### Core rule

**Agents do NOT manually construct or guess Wikimedia URLs.** All image lookups go through `fix_images.py` which uses the verified API search pipeline.

### Image pipeline

1. Run `python3 lib/images/fix_images.py` — searches Commons for all missing visual works
2. Review `cache/pending_images.json` — LLM approves or rejects ambiguous matches
3. For works that remain imageless (copyrighted, not on Commons), manually add Wikipedia links
4. Run `python3 lib/images/verify_images.py` to confirm all URLs return HTTP 200

### How `lib/images/images.py` works

**Never construct or guess Wikimedia URLs.** All image URLs go through:

```python
from lib.images import find_image, set_work_image

url = find_image("The Great Wave off Kanagawa", "Hokusai")  # verified URL or None
if url:
    set_work_image(analysis_data, work_name, url)
```

**Three-way filename validation:**
- **Auto-pass**: artist name in filename → accepted
- **Auto-fail**: different artist named, or generic junk → rejected
- **Pending**: ambiguous → saved to `cache/pending_images.json` for LLM review

### Rate limiting

`lib/images/images.py` uses a **file lock** (`cache/.images.lock`) to ensure only one process accesses the Wikimedia API at a time. Multiple agents or scripts can safely call `find_image()` concurrently — they'll queue automatically.

Rules:
1. Never search for images inside parallel agents
2. All operations go through `lib/images/images.py` (2s delays, `Retry-After` support)
3. Persistent cache (`cache/image_urls.json`) — repeated runs are free
4. Agents must NOT use WebSearch, manual Commons lookups, or construct URLs
5. User-Agent must comply with Wikimedia policy: `BotName/version (URL; email)`

### Copyrighted works

For works not on Commons (most 20th/21st century art): `{"url": "", "link": "https://en.wikipedia.org/wiki/...", "caption": "Work Name"}`

**Links must point to the specific work's article**, not the artist's general page. Use `Artist#Section` only if no dedicated article exists.

### Lessons learned

1. Agents guessed URLs → wrong images (404s, wrong artist). **Fix:** API search + verify
2. Wrong-artist images passed undetected (Rossetti's St. George for Altdorfer, Ortelius map for Richter's Atlas, Titian's Danae for Klimt). **Fix:** Three-way validation + LLM review
3. Parallel agents caused hours-long rate limiting. **Fix:** Sequential image search only
4. Cache remembered failures, blocking re-searches. **Fix:** Clear not-found entries when retrying

## Common Pitfalls

- Many artists share subjects (Crucifixion, Annunciation, Saint George) — always verify the image is the right artist's version
- 20th/21st century works are almost always copyrighted — use Wikipedia links
- For architects (Alberti), use `Architect` for person cards, `Building` for physical structures, and `Location` for non-building designed spaces (parks, urban plans). Never use `Architecture:` as an indicator.
- Some VFA topics cross into literature (William Blake poems, Rossetti sonnets) — use appropriate indicators for each work type
