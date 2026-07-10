---
name: Image pipeline lessons
description: Critical rules for finding/verifying VFA images — learned from the image debacle where agents produced hundreds of wrong images
type: feedback
---

Never construct or guess Wikimedia URLs. All images must go through `lib/images.py` → `find_image()`.

**Why:** Agents previously guessed URLs that were 404s or showed the wrong artist's version of a painting (Cesare Rossetti's St. George for Altdorfer, Titian's Danae for Klimt, Ortelius world map for Richter's Atlas, anime for Carrington, concert photos for Siqueiros).

**How to apply:**
- Agents NEVER search for images during analysis — only after, via `fix_images.py`
- Image search is always sequential, never in parallel agents (causes Wikimedia rate limiting that lasts hours)
- After `fix_images.py`, review `cache/pending_images.json` — approve/reject ambiguous matches
- For copyrighted works (most 20th/21st century), add Wikipedia links instead
- If rate-limited, respect `Retry-After` header; don't retry aggressively
- See `docs/analysis_vfa.md` "Image pipeline" section for full protocol
