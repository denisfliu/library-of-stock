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

# One Leaflet version everywhere. Any page mounting the shared map view
# (lib/js/map_view.js) must include these tags before it.
LEAFLET_TAGS = (
    '<link rel="stylesheet" '
    'href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css">\n'
    '<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>'
)

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


def base_css(max_width='960px', body_padding='1.5rem 1.5rem',
             type_scale=True, h1_size='1.8rem',
             h1_pad='0.25rem', h1_margin='0.5rem',
             global_links=True) -> str:
    """Shared page-header CSS: reset, body, links, h1.

    Parameters cover the deliberate per-page differences (page width,
    heading size); everything else — palette, font stacks, reset, link
    style (plain, underline on hover) — is defined once here. Colors
    come from PALETTE.
    """
    p = PALETTE
    type_rules = "\n    line-height: 1.5;\n    font-size: 14px;" if type_scale else ""
    if global_links:
        links = (f"a {{ color: {p['link']}; text-decoration: none; }}\n"
                 "a:hover { text-decoration: underline; }\n")
    else:
        links = ""
    return f"""* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{
    font-family: -apple-system, 'Segoe UI', Roboto, 'Helvetica Neue', sans-serif;
    background: {p['bg']};
    color: {p['text']};
    max-width: {max_width};
    margin: 0 auto;
    padding: {body_padding};{type_rules}
}}
{links}h1 {{
    font-family: 'Linux Libertine', Georgia, serif;
    font-size: {h1_size};
    font-weight: normal;
    border-bottom: 1px solid {p['border']};
    padding-bottom: {h1_pad};
    margin-bottom: {h1_margin};
    color: {p['text_bright']};
}}"""


def mp3_cache_buster(mp3_path: Path) -> str:
    """Short content hash for cache-busting audio URLs ('0' if missing)."""
    mp3_path = Path(mp3_path)
    if not mp3_path.exists():
        return '0'
    return hashlib.md5(mp3_path.read_bytes()).hexdigest()[:8]
