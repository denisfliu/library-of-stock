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

# Colour tokens. Every page includes THEME_VARS_CSS (base_css does it for
# you; pages with their own <style> call theme_vars_css()). PALETTE maps
# the historical names to those CSS variables, so f-string CSS written
# against PALETTE follows the light/dark switch automatically. The look is
# shared with qbsuite (qb-td): warm off-white light mode, soft charcoal
# dark mode, chosen by prefers-color-scheme (html[data-theme] overrides).
THEME_LIGHT = {
    'bg': '#fafaf8', 'raised': '#f1f1ec', 'input': '#ffffff', 'border': '#e4e4e7',
    'line2': '#ececea', 'hover': '#efefea', 'link': '#1d4ed8', 'text': '#1a1a1a',
    'bright': '#111111', 'muted': '#52525b', 'faint': '#71717a', 'faint2': '#a1a1aa',
    'accent': '#a16207', 'good': '#15803d', 'bad': '#b91c1c', 'warn': '#b4410e',
    'selbg': '#e8eefc', 'selline': '#9db5ef', 'pick': '#e4e4df', 'pickline': '#c9c9c2',
    'winbg': '#dcefe0', 'winfg': '#14532d', 'hl': '#fdf1c7', 'raised2': '#f6f6f2',
}
THEME_DARK = {
    'bg': '#232326', 'raised': '#2b2b2f', 'input': '#1e1e21', 'border': '#36363c',
    'line2': '#303036', 'hover': '#303036', 'link': '#8fb0f5', 'text': '#e4e4e7',
    'bright': '#f4f4f5', 'muted': '#a1a1aa', 'faint': '#8a8a93', 'faint2': '#6b6b73',
    'accent': '#e0b25a', 'good': '#6fc58d', 'bad': '#f08a8a', 'warn': '#e7a177',
    'selbg': '#2a3448', 'selline': '#4a5f8a', 'pick': '#38383f', 'pickline': '#4d4d55',
    'winbg': '#2a4032', 'winfg': '#cfeeda', 'hl': '#4a4126', 'raised2': '#27272b',
}


def _vars(d):
    return ' '.join(f'--c-{k}: {v};' for k, v in d.items())


def theme_vars_css() -> str:
    """Colour variables for both themes. Include once per page."""
    return (
        f":root {{ color-scheme: light; {_vars(THEME_LIGHT)} }}\n"
        "@media (prefers-color-scheme: dark) {\n"
        f"  :root:not([data-theme=\"light\"]) {{ color-scheme: dark; {_vars(THEME_DARK)} }}\n"
        "}\n"
        f":root[data-theme=\"dark\"] {{ color-scheme: dark; {_vars(THEME_DARK)} }}\n"
    )


PALETTE = {
    'bg': 'var(--c-bg)',
    'bg_raised': 'var(--c-raised)',
    'bg_input': 'var(--c-input)',
    'border': 'var(--c-border)',
    'link': 'var(--c-link)',
    'text': 'var(--c-text)',
    'text_bright': 'var(--c-bright)',
    'text_muted': 'var(--c-muted)',
    'text_faint': 'var(--c-faint)',
}

FONT_STACK = "ui-sans-serif, system-ui, -apple-system, 'Segoe UI', sans-serif"


def base_css(max_width='960px', body_padding='1.5rem 1.5rem',
             type_scale=True, h1_size='1.75rem',
             h1_pad='0.25rem', h1_margin='0.5rem',
             global_links=True) -> str:
    """Shared page-header CSS: reset, body, links, h1.

    Parameters cover the deliberate per-page differences (page width,
    heading size); everything else — palette, font stacks, reset, link
    style (plain, underline on hover) — is defined once here. Colors
    come from PALETTE.
    """
    p = PALETTE
    type_rules = "\n    line-height: 1.55;\n    font-size: 15px;" if type_scale else ""
    if global_links:
        links = (f"a {{ color: {p['link']}; text-decoration: none; }}\n"
                 "a:hover { text-decoration: underline; }\n")
    else:
        links = ""
    return f"""{theme_vars_css()}* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{
    font-family: {FONT_STACK};
    -webkit-font-smoothing: antialiased;
    background: {p['bg']};
    color: {p['text']};
    max-width: {max_width};
    margin: 0 auto;
    padding: {body_padding};{type_rules}
}}
{links}h1 {{
    font-family: {FONT_STACK};
    font-size: {h1_size};
    font-weight: 600;
    letter-spacing: -0.01em;
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
{site_nav_css()}"""


def site_nav_css() -> str:
    """The shared Library of Stock top bar (markup from site_nav())."""
    p = PALETTE
    return f"""
/* --- site nav (theme.site_nav) --- */
.site-nav {{
    display: flex; align-items: center; gap: 0.35rem 1.2rem; flex-wrap: wrap;
    font-size: 14px; padding-bottom: 0.85rem; margin-bottom: 1.6rem;
    border-bottom: 1px solid {p['border']};
}}
.site-nav a {{ color: {p['text_muted']}; text-decoration: none; }}
.site-nav a:hover {{ color: {p['text']}; text-decoration: none; }}
.site-nav a.site-home {{ color: {p['text']}; font-weight: 600; }}
.site-nav a.here {{ color: {p['text']}; }}
.site-nav .site-sp {{ flex-grow: 1; }}
html[data-layout="mobile"] .site-nav {{ gap: 0.3rem 0.9rem; }}
"""


def site_nav(root: str, active: str = '', right: str = '') -> str:
    """Shared top bar: Library of Stock · Wiki · Reader · Search, then
    `right` (page tools such as the guide search box + Random). `root` is
    the relative path to the site root ('' at the top level, '../../' on
    output/<slug>/ pages)."""
    def link(key, href, label):
        cls = ' class="here"' if key == active else ''
        return f'<a{cls} href="{href}">{label}</a>'
    return (
        '<nav class="site-nav">'
        f'<a class="site-home" href="{root}index.html">Library of Stock</a>'
        + link('wiki', f'{root}wiki.html', 'Wiki')
        + link('reader', f'{root}reader.html', 'Reader')
        + link('search', 'https://qbsuite.github.io/qb-semantic-search/app/', 'Search')
        + '<span class="site-sp"></span>' + right + '</nav>'
    )


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
    border: 1px solid {p['border']}; border-radius: 8px;
    outline: none; font-family: inherit;
}}
.search-nav-input:focus {{ border-color: {p['link']}; width: 220px; }}
.search-nav-input::placeholder {{ color: var(--c-faint2); }}
.search-nav-dropdown {{
    display: none; position: absolute; top: 100%; right: 0;
    margin-top: 0.2rem; background: {p['bg_raised']};
    border: 1px solid {p['border']}; border-radius: 4px;
    min-width: 280px; max-height: 350px; overflow-y: auto;
    z-index: {z_index}; box-shadow: 0 8px 24px rgba(0,0,0,0.14);
}}
.search-nav-dropdown.open {{ display: block; }}
.search-nav-result {{
    display: flex; justify-content: space-between; align-items: baseline;
    padding: 0.4rem 0.6rem; color: {p['text']}; text-decoration: none;
    font-size: 0.85rem; border-bottom: 1px solid var(--c-line2);
}}
.search-nav-result:last-child {{ border-bottom: none; }}
.search-nav-result:hover, .search-nav-result.active {{ background: var(--c-hover); }}
.search-nav-result-name {{ color: {p['link']}; }}
.search-nav-result-cat {{
    font-size: 0.72rem; color: {p['text_faint']};
    margin-left: 0.5rem; white-space: nowrap;
}}
.search-nav-empty {{ padding: 0.6rem; color: var(--c-faint2); font-size: 0.82rem; font-style: italic; }}
.search-nav-random {{
    background: none; border: 1px solid {p['border']}; border-radius: 8px;
    color: {p['text_muted']}; font-size: 0.85rem; cursor: pointer;
    padding: 0.3rem 0.55rem; line-height: 1;
}}
.search-nav-random:hover {{ background: var(--c-hover); color: {p['text']}; border-color: {p['link']}; }}
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
    background: rgba(0,0,0,0.32);
}}
.los-backdrop.open {{ display: block; }}
.los-sheet {{
    position: fixed; left: 0; right: 0; bottom: 0; z-index: 91;
    background: {p['bg']};
    border-top: 1px solid {p['border']};
    border-radius: 16px 16px 0 0;
    max-height: 85vh; max-height: 85dvh;
    display: none; flex-direction: column;
    padding-bottom: env(safe-area-inset-bottom);
    box-shadow: 0 -8px 30px rgba(0,0,0,0.18);
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


def cache_buster(path: Path) -> str:
    """Short content hash for cache-busting asset URLs ('0' if missing).

    Pages that reference mutable assets (JS, audio) must append ?v={hash}:
    GitHub Pages caches assets for ~10 minutes, so a fresh HTML page can
    otherwise run a stale script."""
    path = Path(path)
    if not path.exists():
        return '0'
    return hashlib.md5(path.read_bytes()).hexdigest()[:8]


def mp3_cache_buster(mp3_path: Path) -> str:
    return cache_buster(mp3_path)
