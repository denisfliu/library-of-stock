"""theme.py — Shared assets for the HTML renderers.

Single source of truth for the abcjs CDN tag, the mp3 cache-buster, and
the dark-theme palette. The per-page CSS blocks still live in each
renderer (they differ deliberately in layout); when changing colors,
change them here and reference PALETTE in new CSS.
"""
import hashlib
from pathlib import Path

# One abcjs version everywhere. render.py, render_cards.py, and
# render_score_review.py must all use this tag.
ABCJS_SCRIPT_TAG = '<script src="https://cdn.jsdelivr.net/npm/abcjs@6.4.4/dist/abcjs-basic-min.js"></script>'

# Dark theme palette (matches the CSS embedded in the renderers).
PALETTE = {
    'bg': '#101418',
    'bg_raised': '#1a1f25',
    'bg_input': '#15191e',
    'border': '#3a3f47',
    'link': '#6b9eff',
    'text': '#c8ccd1',
    'text_bright': '#e0e0e0',
    'text_muted': '#9aa0a7',
    'text_faint': '#808790',
}


def mp3_cache_buster(mp3_path: Path) -> str:
    """Short content hash for cache-busting audio URLs ('0' if missing)."""
    mp3_path = Path(mp3_path)
    if not mp3_path.exists():
        return '0'
    return hashlib.md5(mp3_path.read_bytes()).hexdigest()[:8]
