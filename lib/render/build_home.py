"""build_home.py — Generate index.html, the three-door portal homepage.

The site has three main destinations: the wiki (wiki.html, built by
lib/build_index.py), the reader (reader.html), and semantic search
(search.html, built by lib/render/build_search.py). This page is the
front door linking them, plus quick links to authored overview pages and
sweep sets. Stats are computed from the corpus at build time; question-corpus
figures live in door copy only (the mirror isn't available in CI).

Usage:
    python lib/render/build_home.py
"""
import json
import sys
from html import escape
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from lib.common import ROOT, CATEGORIES_DIR, SETS_DIR, resolve_analyses
from lib.render.theme import PALETTE, layout_switch_script
from lib.units import UNITS_BY_SLUG

# CSS custom properties for the neutral palette, sourced from theme.PALETTE
# so the portal can't drift from the wiki/reader. (--accent is a semantic
# color not yet in PALETTE and stays inline in the template.)
_PALETTE_VARS = (
    f"--bg: {PALETTE['bg']}; --raised: {PALETTE['bg_raised']}; "
    f"--inset: {PALETTE['bg_input']}; --border: {PALETTE['border']};\n"
    f"  --text: {PALETTE['text']}; --bright: {PALETTE['text_bright']}; "
    f"--muted: {PALETTE['text_muted']}; --faint: {PALETTE['text_faint']};\n"
    f"  --wiki: {PALETTE['link']};"
)

TEMPLATE = """<!DOCTYPE html>
<html lang="en" data-layout="desktop">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
LAYOUT_SWITCH
<title>Library of Stock</title>
<style>
:root {
  color-scheme: dark;
  PALETTE_VARS
  --accent: #e8b04a;
  --search: #79c0a5;
  --sans: -apple-system, 'Segoe UI', Roboto, 'Helvetica Neue', sans-serif;
  --serif: 'Linux Libertine', Georgia, serif;
}
* { margin: 0; padding: 0; box-sizing: border-box; }
html { background: var(--bg); }
body {
  font-family: var(--sans); background: var(--bg); color: var(--text);
  font-size: 15px; line-height: 1.55; min-height: 100vh;
  display: flex; flex-direction: column; align-items: center;
  padding: 0 1.2rem 3rem;
}
a { text-decoration: none; }
.masthead { text-align: center; margin: 3.2rem 0 0.4rem; }
.masthead h1 {
  font-family: var(--serif); font-weight: normal; font-size: 2.5rem; color: var(--bright);
  letter-spacing: 0.01em;
}
.masthead .tagline { color: var(--muted); font-size: 0.95rem; margin-top: 0.35rem; }
.statline {
  display: flex; gap: 1.6rem; justify-content: center; flex-wrap: wrap;
  color: var(--faint); font-size: 0.8rem; margin: 1.1rem 0 2.2rem;
  font-variant-numeric: tabular-nums;
}
.statline b { color: var(--muted); font-weight: 600; }

.doors { display: flex; gap: 1.2rem; width: 100%; max-width: 860px; }
html[data-layout="mobile"] .doors { flex-direction: column; }
html[data-layout="mobile"] .masthead { margin-top: 1.8rem; }
html[data-layout="mobile"] .masthead h1 { font-size: 2rem; }
html[data-layout="mobile"] .statline { gap: 0.7rem 1.4rem; }
html[data-layout="mobile"] .door .go { padding: 0.6rem 1.3rem; }
html[data-layout="mobile"] .quick a { padding: 0.25rem 0; }
.door {
  flex: 1; display: block; background: var(--raised); border: 1px solid var(--border);
  border-radius: 6px; padding: 1.5rem 1.5rem 1.35rem; color: var(--text);
  transition: border-color 0.15s;
}
.door:hover { border-color: var(--faint); }
.door .eyebrow {
  font-size: 0.7rem; font-weight: 600; letter-spacing: 0.12em; text-transform: uppercase;
  margin-bottom: 0.55rem;
}
.door.wiki .eyebrow { color: var(--wiki); }
.door.reader .eyebrow { color: var(--accent); }
.door.search .eyebrow { color: var(--search); }
.door h2 { font-family: var(--serif); font-weight: normal; font-size: 1.7rem; color: var(--bright); }
.door p { color: var(--muted); font-size: 0.9rem; margin-top: 0.5rem; }
.door ul { list-style: none; margin-top: 0.9rem; }
.door li { font-size: 0.85rem; color: var(--text); padding: 0.22rem 0; }
.door li::before { content: '·'; margin-right: 0.5rem; }
.door.wiki li::before { color: var(--wiki); }
.door.reader li::before { color: var(--accent); }
.door.search li::before { color: var(--search); }
.door .go {
  display: inline-block; margin-top: 1.1rem; font-size: 0.88rem; font-weight: 600;
  border: 1px solid var(--border); border-radius: 3px; padding: 0.4rem 1.05rem;
}
.door.wiki .go { color: var(--wiki); }
.door.reader .go { color: var(--accent); }
.door.search .go { color: var(--search); }
.door:hover .go { border-color: var(--faint); }

.below {
  width: 100%; max-width: 860px; margin-top: 1.2rem;
  display: flex; gap: 1.2rem; flex-wrap: wrap;
}
.quick {
  flex: 1; min-width: 240px; background: var(--inset); border: 1px solid var(--border);
  border-radius: 6px; padding: 0.9rem 1.1rem;
}
.quick h3 {
  font-size: 0.7rem; font-weight: 600; letter-spacing: 0.12em; text-transform: uppercase;
  color: var(--faint); margin-bottom: 0.5rem;
}
.quick a { display: inline-block; color: var(--wiki); font-size: 0.85rem; margin: 0.12rem 0.9rem 0.12rem 0; }
.quick a:hover { text-decoration: underline; }
.quick .draft-mark { color: var(--accent); font-size: 0.7rem; vertical-align: super; }
.quick .soon { color: var(--faint); font-size: 0.85rem; margin: 0.12rem 0.9rem 0.12rem 0; }
footer { margin-top: 2.4rem; color: var(--faint); font-size: 0.75rem; text-align: center; }
footer a { color: var(--muted); }
</style>
</head>
<body>
<div class="masthead">
  <h1>Library of Stock</h1>
  <div class="tagline">A quizbowl study companion &mdash; read the canon, then get read the questions.</div>
</div>
<div class="statline">STATLINE</div>

<div class="doors">
  <a class="door wiki" href="wiki.html">
    <div class="eyebrow">Study</div>
    <h2>Wiki</h2>
    <p>Every topic the canon asks about, analyzed from real clues.</p>
    <ul>
      <li>Search all GUIDE_COUNT guides</li>
      <li>Category overviews with question panels &amp; soundbites</li>
      <li>Timeline and map views</li>
      <li>Anki-style cards per topic</li>
    </ul>
    <span class="go">Open the wiki &rarr;</span>
  </a>
  <a class="door reader" href="reader.html">
    <div class="eyebrow">Practice</div>
    <h2>Reader</h2>
    <p>Get questions read to you, buzz, and learn where you're weak.</p>
    <ul>
      <li>187,000+ tossups, filtered by category, movement &amp; era</li>
      <li>Last-<i>n</i>-sentences mode for giveaway drilling</li>
      <li>Accuracy &amp; buzz-depth stats, weakest-first</li>
      <li>Every reveal links back to the wiki</li>
    </ul>
    <span class="go">Start reading &rarr;</span>
  </a>
  <a class="door search" href="search.html">
    <div class="eyebrow">Look up</div>
    <h2>Search</h2>
    <p>Find clues by meaning, not keywords, across the whole corpus.</p>
    <ul>
      <li>Semantic search over 1.7M clue sentences</li>
      <li>qbreader-style filters: category, difficulty, year, set</li>
      <li>Matched sentence highlighted in its question</li>
      <li>Shareable search URLs</li>
    </ul>
    <span class="go">Search the corpus &rarr;</span>
  </a>
</div>

<div class="below">
  <div class="quick">
    <h3>Category overviews</h3>
    OVERVIEW_LINKS
  </div>
  <div class="quick">
    <h3>Tournament sweeps</h3>
    SWEEP_LINKS
  </div>
</div>

<footer>
  Questions mirrored from <a href="https://www.qbreader.org">qbreader</a> &middot; noncommercial study use
</footer>
</body>
</html>
"""


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
        draft = ov.get("draft")
        if draft:
            draft_count += 1
        mark = ' <span class="draft-mark" title="AI draft — pending review">draft</span>' if draft else ""
        overview_links.append(
            f'<a href="output/_categories/{escape(slug)}/overview.html">{escape(title)}</a>{mark}'
        )
    if not overview_links:
        overview_links.append('<span class="soon">none yet</span>')

    sweep_links = []
    for set_path in sorted(SETS_DIR.glob("*/set.json")):
        try:
            name = json.loads(set_path.read_text(encoding="utf-8")).get("name", set_path.parent.name)
        except (OSError, json.JSONDecodeError):
            name = set_path.parent.name
        sweep_links.append(
            f'<a href="output/_sets/{escape(set_path.parent.name)}/sweep.html">{escape(name)}</a>'
        )
    if not sweep_links:
        sweep_links.append('<span class="soon">none yet</span>')

    stats = [
        f"<span><b>{guide_count}</b> study guides</span>",
        f"<span><b>{len(overview_links)}</b> category overviews</span>",
        f"<span><b>{len(sweep_links)}</b> tournament sweeps</span>",
        "<span><b>187k+</b> questions in the reader</span>",
    ]

    html = (TEMPLATE
            .replace("LAYOUT_SWITCH", layout_switch_script())
            .replace("PALETTE_VARS", _PALETTE_VARS)
            .replace("STATLINE", "\n  ".join(stats))
            .replace("GUIDE_COUNT", str(guide_count))
            .replace("OVERVIEW_LINKS", "\n    ".join(overview_links))
            .replace("SWEEP_LINKS", "\n    ".join(sweep_links)))
    (ROOT / "index.html").write_text(html, encoding="utf-8")
    print(f"Built index.html (portal): {guide_count} guides, "
          f"{len(overview_links)} overviews ({draft_count} drafts), {len(sweep_links)} sweeps")


if __name__ == "__main__":
    build()
