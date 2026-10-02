"""build_home.py — Generate index.html, the portal homepage.

The site has three main destinations: the wiki (wiki.html, built by
lib/build_index.py), the reader (reader.html), and semantic search
(the qb-semantic-search app at qbsuite.github.io/qb-semantic-search/app/). This page is the
front door linking them (three icon tiles), plus quick links to authored
overview pages and sweep sets. Stats are computed from the corpus at build
time; the reader question count is static (the mirror isn't available in CI).

Usage:
    python lib/render/build_home.py
"""
import json
import sys
from html import escape
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from lib.common import ROOT, CATEGORIES_DIR, SETS_DIR, resolve_analyses
from lib.render.theme import FONT_STACK, layout_switch_script, theme_vars_css
from lib.units import UNITS_BY_SLUG

SEARCH_URL = "https://qbsuite.github.io/qb-semantic-search/app/"

# Inline stroke icons for the three tiles (book / headphones / magnifier).
_SVG = ('<svg class="ic" width="30" height="30" viewBox="0 0 24 24" fill="none" '
        'stroke="currentColor" stroke-width="1.6" stroke-linecap="round" '
        'stroke-linejoin="round" aria-hidden="true">{}</svg>')
ICON_BOOK = _SVG.format('<path d="M4 5.5A2.5 2.5 0 0 1 6.5 3H20v15H6.5A2.5 2.5 0 0 0 4 20.5z"/>'
                        '<path d="M4 20.5A2.5 2.5 0 0 0 6.5 23H20v-5"/>')
ICON_HEADPHONES = _SVG.format('<path d="M4 14v-2a8 8 0 0 1 16 0v2"/>'
                              '<rect x="3" y="14" width="4" height="7" rx="1.5"/>'
                              '<rect x="17" y="14" width="4" height="7" rx="1.5"/>')
ICON_SEARCH = _SVG.format('<circle cx="11" cy="11" r="7"/><path d="M20 20l-3.5-3.5"/>')

TEMPLATE = """<!DOCTYPE html>
<html lang="en" data-layout="desktop">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
LAYOUT_SWITCH
<title>Library of Stock</title>
<style>
THEME_VARS
* { margin: 0; padding: 0; box-sizing: border-box; }
html { background: var(--c-bg); }
body {
  font-family: FONT_STACK; -webkit-font-smoothing: antialiased;
  background: var(--c-bg); color: var(--c-text);
  font-size: 15px; line-height: 1.5; min-height: 100vh;
}
a { color: var(--c-link); text-decoration: none; }
a:hover { text-decoration: underline; }
.wrap { max-width: 760px; margin: 0 auto; padding: 88px 24px 64px; }
.masthead { text-align: center; }
.masthead h1 {
  font-size: 34px; font-weight: 700; letter-spacing: -0.02em; color: var(--c-bright);
}
.masthead .tagline { margin-top: 6px; color: var(--c-muted); font-size: 16px; }
.statline {
  margin-top: 10px; font-size: 13px; color: var(--c-muted);
  font-variant-numeric: tabular-nums;
}
.statline span + span::before { content: ' \\00b7  '; white-space: pre; }

.tiles {
  display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 16px;
  margin: 40px auto 0; max-width: 600px;
}
a.tile {
  display: flex; flex-direction: column; align-items: center; justify-content: center;
  gap: 10px; height: 132px; border: 1px solid var(--c-border); border-radius: 14px;
  color: var(--c-text);
}
a.tile:hover { text-decoration: none; background: var(--c-hover); border-color: var(--c-link); }
a.tile .ic { color: var(--c-muted); }
a.tile:hover .ic, a.tile:hover .nm { color: var(--c-link); }
a.tile .nm { font-size: 18px; font-weight: 600; }

.sec-head {
  display: flex; justify-content: space-between; align-items: baseline; gap: 12px;
  margin-top: 64px; padding-bottom: 8px;
}
.sec-head h2, h2.sec { font-size: 15px; font-weight: 600; color: var(--c-muted); }
.sec-head .note { font-size: 13px; color: var(--c-muted); }
h2.sec { margin-top: 40px; padding-bottom: 8px; }
.ov-cols {
  border-top: 1px solid var(--c-border); padding-top: 12px;
  column-width: 180px; column-gap: 24px; font-size: 14px;
}
.ov-cols > div { padding: 3px 0; break-inside: avoid; }
.reviewed {
  margin-left: 6px; font-size: 12px; color: var(--c-muted);
  border: 1px solid var(--c-border); border-radius: 99px; padding: 0 7px;
  white-space: nowrap;
}
.rows { border-top: 1px solid var(--c-border); }
.rows > div { border-bottom: 1px solid var(--c-border); }
.rows .item { padding: 12px 10px; margin: 0 -10px; border-radius: 8px; }
.rows .item:hover { background: var(--c-hover); }
.rows .item a { font-weight: 600; }
.soon { color: var(--c-faint); font-size: 14px; }
footer { margin-top: 48px; font-size: 14px; color: var(--c-muted); text-align: center; }
footer a { color: var(--c-muted); text-decoration: underline; }

html[data-layout="mobile"] .wrap { padding: 40px 16px 48px; }
html[data-layout="mobile"] .masthead h1 { font-size: 28px; }
html[data-layout="mobile"] .tiles { gap: 10px; margin-top: 28px; }
html[data-layout="mobile"] a.tile { height: 104px; }
html[data-layout="mobile"] a.tile .nm { font-size: 16px; }
html[data-layout="mobile"] .sec-head { margin-top: 44px; }
html[data-layout="mobile"] .ov-cols { column-width: 150px; column-gap: 16px; }
html[data-layout="mobile"] .ov-cols > div { padding: 5px 0; }
</style>
</head>
<body>
<div class="wrap">
<header class="masthead">
  <h1>Library of Stock</h1>
  <div class="tagline">Quizbowl study guides, a question reader, and clue search</div>
  <div class="statline">STATLINE</div>
</header>

<nav class="tiles" aria-label="Sections">
  <a class="tile" href="wiki.html" title="Study guides for GUIDE_COUNT topics, category overviews, timeline and location views">ICON_BOOK<span class="nm">Wiki</span></a>
  <a class="tile" href="reader.html" title="Get questions read to you, buzz, and learn where you're weak">ICON_HEADPHONES<span class="nm">Reader</span></a>
  <a class="tile" href="SEARCH_URL" title="Find clues by meaning, not keywords, across the whole corpus">ICON_SEARCH<span class="nm">Search</span></a>
</nav>

<div class="sec-head">
  <h2>Category overviews</h2>
  <span class="note">AI drafts unless marked reviewed</span>
</div>
<div class="ov-cols">
  OVERVIEW_LINKS
</div>

<h2 class="sec">Tournament sweeps</h2>
<div class="rows">
  SWEEP_LINKS
</div>

<footer>
  Questions mirrored from <a href="https://www.qbreader.org">qbreader</a> &middot; noncommercial study use
</footer>
</div>
</body>
</html>
"""


def _set_display_name(set_dir: Path, sets_index: dict) -> str:
    """Human name for a sweep set: set.json's set_name (or legacy name),
    then the sets.json registry, then a prettified slug."""
    slug = set_dir.name
    try:
        data = json.loads((set_dir / "set.json").read_text(encoding="utf-8"))
        name = data.get("set_name") or data.get("name")
        if name:
            return name
    except (OSError, json.JSONDecodeError):
        pass
    if sets_index.get(slug):
        return sets_index[slug]
    words = slug.replace("_", " ").split()
    return " ".join(w.upper() if (w.isalpha() and len(w) <= 3) else w.capitalize()
                    for w in words)


def build(analyses=None) -> None:
    analyses = resolve_analyses(analyses)
    guide_count = len(analyses)

    overview_links = []
    draft_count = 0
    for ov_path in sorted(CATEGORIES_DIR.glob("*/overview.json")):
        try:
            ov = json.loads(ov_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        slug = ov_path.parent.name
        unit = UNITS_BY_SLUG.get(slug)
        title = unit.title if unit else slug.replace("_", " ").title()
        # Inverted marker: drafts are the norm, so only reviewed overviews
        # get a pill; the draft state stays in the link's title tooltip.
        if ov.get("draft"):
            draft_count += 1
            attr, mark = ' title="AI draft, not yet reviewed"', ""
        else:
            attr = ' title="Reviewed"'
            mark = ' <span class="reviewed" title="Reviewed by a human">reviewed</span>'
        overview_links.append(
            f'<div><a href="output/_categories/{escape(slug)}/overview.html"{attr}>'
            f'{escape(title)}</a>{mark}</div>'
        )
    n_overviews = len(overview_links)
    if not overview_links:
        overview_links.append('<span class="soon">none yet</span>')

    sets_index = {}
    try:
        for e in json.loads((SETS_DIR / "sets.json").read_text(encoding="utf-8")):
            sets_index[e.get("set_slug")] = e.get("set_name")
    except (OSError, json.JSONDecodeError, AttributeError, TypeError):
        pass

    sweep_links = []
    for set_path in sorted(SETS_DIR.glob("*/set.json")):
        name = _set_display_name(set_path.parent, sets_index)
        sweep_links.append(
            f'<div><div class="item"><a href="output/_sets/{escape(set_path.parent.name)}/sweep.html">'
            f'{escape(name)}</a></div></div>'
        )
    n_sweeps = len(sweep_links)
    if not sweep_links:
        sweep_links.append('<div><div class="item"><span class="soon">none yet</span></div></div>')

    stats = [
        f"<span>{guide_count} study guides</span>",
        f"<span>{n_overviews} category overviews</span>",
        f"<span>{n_sweeps} tournament sweep{'' if n_sweeps == 1 else 's'}</span>",
        "<span>187k+ questions in the reader</span>",
    ]

    html = (TEMPLATE
            .replace("LAYOUT_SWITCH", layout_switch_script())
            .replace("THEME_VARS", theme_vars_css())
            .replace("FONT_STACK", FONT_STACK)
            .replace("STATLINE", "".join(stats))
            .replace("GUIDE_COUNT", str(guide_count))
            .replace("ICON_BOOK", ICON_BOOK)
            .replace("ICON_HEADPHONES", ICON_HEADPHONES)
            .replace("ICON_SEARCH", ICON_SEARCH)
            .replace("SEARCH_URL", SEARCH_URL)
            .replace("OVERVIEW_LINKS", "\n  ".join(overview_links))
            .replace("SWEEP_LINKS", "\n  ".join(sweep_links)))
    (ROOT / "index.html").write_text(html, encoding="utf-8")
    print(f"Built index.html (portal): {guide_count} guides, "
          f"{n_overviews} overviews ({draft_count} drafts), {n_sweeps} sweeps")


if __name__ == "__main__":
    build()
