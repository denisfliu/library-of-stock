# Visual Fine Arts Analysis Guide

Supplement to `analysis_instructions.md`. Read the core instructions first.

## Sectioning for Visual Artists

Organize by **individual works or work groups** (series, chapel cycles, etc.):
- Major paintings/sculptures each get their own section
- Series can be grouped (e.g., "Thirty-Six Views of Mount Fuji" as one section)
- "Other Works" for infrequently clued pieces
- "General / Biographical" for common identifiers

Every work section needs an `indicator` field: `Painting`, `Sculpture`, `Fresco`, `Print`, `Engraving`, `Mural`, `Installation`.

For movements (Ashcan School, YBA, etc.): use `Movement` indicator and organize by key members/exhibitions.

## Cards

- `Painting: clue` → `Work Name (Artist)` for work-specific clues
- `Artist: clue` → `Artist Name` for general/biographical
- `Movement: clue` → `Movement Name` for schools/movements
- Image recognition cards for works with embedded images

## Images

### Core rule

**Agents do NOT search for images during analysis.** Images are handled as a separate, sequential step after all analysis is complete. This prevents Wikimedia rate limiting.

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
- For architects (Alberti), use `Architect` or `Theorist` indicator, not `Painting`
- Some VFA topics cross into literature (William Blake poems, Rossetti sonnets) — use appropriate indicators for each work type
