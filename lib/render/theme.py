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


def nav_bar_css() -> str:
    """Top nav-bar row shared by stock, overview, and sweep pages.
    Markup: <div class="nav-bar"><div class="nav-links">...</div>...</div>.
    Page-specific extensions (overflow menu on stock pages) stay local."""
    p = PALETTE
    return f"""
/* --- nav bar (theme.nav_bar_css) --- */
.nav-bar {{
    margin-bottom: 0.8rem;
    font-size: 0.85rem;
    display: flex;
    justify-content: space-between;
    align-items: center;
    flex-wrap: wrap;
    gap: 0.3rem;
}}
.nav-bar a {{ color: {p['link']}; text-decoration: none; }}
.nav-bar a:hover {{ text-decoration: underline; }}
.nav-links {{ display: flex; gap: 0.3rem; align-items: center; }}
"""


def search_nav_css(z_index: int = 200) -> str:
    """Search box + dropdown + random button (pairs with lib/js/search_nav.js).
    z_index must clear the page's own stacking contexts (sweep passes 1200
    to sit above the Leaflet map panes)."""
    p = PALETTE
    return f"""
/* --- search nav (theme.search_nav_css) --- */
.search-nav {{ display: inline-block; }}
.search-nav-row {{ display: flex; gap: 0.3rem; align-items: center; }}
.search-nav-input-wrap {{ position: relative; }}
.search-nav-input {{
    width: 160px; padding: 0.25rem 0.5rem; font-size: 0.8rem;
    background: {p['bg_input']}; color: {p['text']};
    border: 1px solid {p['border']}; border-radius: 3px;
    outline: none; font-family: inherit;
}}
.search-nav-input:focus {{ border-color: {p['link']}; width: 220px; }}
.search-nav-input::placeholder {{ color: #555; }}
.search-nav-dropdown {{
    display: none; position: absolute; top: 100%; right: 0;
    margin-top: 0.2rem; background: {p['bg_raised']};
    border: 1px solid {p['border']}; border-radius: 4px;
    min-width: 280px; max-height: 350px; overflow-y: auto;
    z-index: {z_index}; box-shadow: 0 4px 12px rgba(0,0,0,0.5);
}}
.search-nav-dropdown.open {{ display: block; }}
.search-nav-result {{
    display: flex; justify-content: space-between; align-items: baseline;
    padding: 0.4rem 0.6rem; color: {p['text']}; text-decoration: none;
    font-size: 0.85rem; border-bottom: 1px solid #2a2f37;
}}
.search-nav-result:last-child {{ border-bottom: none; }}
.search-nav-result:hover, .search-nav-result.active {{ background: #262d37; }}
.search-nav-result-name {{ color: {p['link']}; }}
.search-nav-result-cat {{
    font-size: 0.72rem; color: {p['text_faint']};
    margin-left: 0.5rem; white-space: nowrap;
}}
.search-nav-empty {{ padding: 0.6rem; color: #555; font-size: 0.82rem; font-style: italic; }}
.search-nav-random {{
    background: {p['bg_raised']}; border: 1px solid {p['border']}; border-radius: 3px;
    color: {p['text_muted']}; font-size: 0.85rem; cursor: pointer;
    padding: 0.2rem 0.4rem; line-height: 1;
}}
.search-nav-random:hover {{ background: #262d37; color: {p['text']}; border-color: {p['link']}; }}
"""


# --- Mobile layout mode -------------------------------------------------
#
# Pages carry two genuinely distinct layouts selected at runtime: a tiny
# inline head script (layout_switch_script) sets data-layout="mobile" or
# "desktop" on <html>, and both CSS (html[data-layout="mobile"] ...) and
# JS (lib/js/mobile.js, page scripts listening for the 'loslayout' event)
# key off that one attribute. The breakpoint expression below is the only
# place the mobile/desktop boundary is defined. The static markup default
# is data-layout="desktop" (no-JS fallback).

MOBILE_MQ = '(max-width: 700px), ((pointer: coarse) and (max-width: 1024px))'


def layout_switch_script() -> str:
    """Inline <head> script that keeps html[data-layout] in sync with
    MOBILE_MQ and fires a 'loslayout' CustomEvent on every change
    (including the initial application, which runs before body paint)."""
    return f"""<script>
(function () {{
  var mq = window.matchMedia('{MOBILE_MQ}');
  function apply() {{
    var mode = mq.matches ? 'mobile' : 'desktop';
    if (document.documentElement.dataset.layout === mode) return;
    document.documentElement.dataset.layout = mode;
    window.dispatchEvent(new CustomEvent('loslayout', {{ detail: mode }}));
  }}
  if (mq.addEventListener) mq.addEventListener('change', apply);
  else mq.addListener(apply);
  apply();
}})();
</script>"""


def mobile_core_css() -> str:
    """Baseline mobile rules shared by every page: mode-scoped visibility
    utilities, comfortable touch targets, and a horizontal-scroll wrapper
    for tables that cannot stack."""
    return """
/* --- mobile core (theme.mobile_core_css) --- */
.m-only { display: none !important; }
html[data-layout="mobile"] .m-only { display: revert !important; }
html[data-layout="mobile"] .d-only { display: none !important; }
html[data-layout="mobile"] body { padding-left: 0.9rem; padding-right: 0.9rem; }
html[data-layout="mobile"] button,
html[data-layout="mobile"] select,
html[data-layout="mobile"] input[type="checkbox"] + label {
    min-height: 40px;
}
html[data-layout="mobile"] input[type="text"],
html[data-layout="mobile"] input[type="search"],
html[data-layout="mobile"] input[type="number"] {
    font-size: 16px; /* prevents iOS focus zoom */
}
.tablewrap { overflow-x: auto; -webkit-overflow-scrolling: touch; max-width: 100%; }
html[data-layout="mobile"] img { max-width: 100%; height: auto; }
"""


def sheet_css() -> str:
    """Bottom-sheet component styles (element behavior in lib/js/mobile.js).
    Markup: <div class="los-backdrop"></div> plus
    <div class="los-sheet"><div class="los-sheet-handle"></div><div class="los-sheet-body">...</div></div>."""
    p = PALETTE
    return f"""
/* --- bottom sheet (theme.sheet_css) --- */
.los-backdrop {{
    display: none; position: fixed; inset: 0; z-index: 90;
    background: rgba(0,0,0,0.55);
}}
.los-backdrop.open {{ display: block; }}
.los-sheet {{
    position: fixed; left: 0; right: 0; bottom: 0; z-index: 91;
    background: {p['bg_raised']};
    border-top: 1px solid {p['border']};
    border-radius: 14px 14px 0 0;
    max-height: 85vh; max-height: 85dvh;
    display: none; flex-direction: column;
    padding-bottom: env(safe-area-inset-bottom);
    box-shadow: 0 -8px 30px rgba(0,0,0,0.45);
}}
.los-sheet.open {{ display: flex; }}
.los-sheet-handle {{
    flex: none; padding: 0.55rem 0 0.35rem; cursor: grab; touch-action: none;
}}
.los-sheet-handle::before {{
    content: ""; display: block; width: 42px; height: 4px; margin: 0 auto;
    border-radius: 2px; background: {p['text_faint']};
}}
.los-sheet-body {{
    overflow-y: auto; -webkit-overflow-scrolling: touch;
    padding: 0 1rem 1rem; overscroll-behavior: contain;
}}
body.los-sheet-open {{ overflow: hidden; }}
"""


def table_cards_css(table_class: str) -> str:
    """Mobile table-to-card-list transform for a given table class: header
    row hidden, each row a bordered block, each cell a stacked line labeled
    by its data-label attribute (cells without one get no label)."""
    p = PALETTE
    t = f'html[data-layout="mobile"] table.{table_class}'
    return f"""
/* --- table->cards for .{table_class} (theme.table_cards_css) --- */
{t} {{ display: block; border: none; }}
{t} thead {{ display: none; }}
{t} tbody {{ display: block; }}
{t} tr {{
    display: block; border: 1px solid {p['border']}; border-radius: 6px;
    margin-bottom: 0.6rem; padding: 0.55rem 0.7rem; background: {p['bg_raised']};
}}
{t} td {{
    display: block; border: none; padding: 0.25rem 0; width: auto;
    max-width: none; min-width: 0; white-space: normal;
}}
{t} td:empty {{ display: none; }}
{t} td[data-label]::before {{
    content: attr(data-label);
    display: block; font-size: 0.68rem; text-transform: uppercase;
    letter-spacing: 0.06em; color: {p['text_faint']}; margin-bottom: 0.1rem;
}}
"""


def mp3_cache_buster(mp3_path: Path) -> str:
    """Short content hash for cache-busting audio URLs ('0' if missing)."""
    mp3_path = Path(mp3_path)
    if not mp3_path.exists():
        return '0'
    return hashlib.md5(mp3_path.read_bytes()).hexdigest()[:8]
