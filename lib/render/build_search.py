"""build_search.py — generate search.html, the semantic search page.

The third top-level page (wiki, reader, search): free-text semantic
search over every embedded tossup sentence and bonus part, with
qbreader.org/db's filter set. All logic lives in lib/js/semsearch.js;
this template supplies the shell and window.SEM_CFG — the canonical
taxonomy lists from qbmirror.query in list order, which IS the
ordinal contract shared with build_search_index.py and the Worker.

The sync Worker URL is read from lib/js/sync.js at build time so the
two pages can never disagree about the backend.

Usage: python lib/render/build_search.py
"""
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from lib.common import ROOT
from qbmirror.query import (ALTERNATE_SUBCATEGORY_TO_CATEGORY,
                              CATEGORY_TO_ALTERNATE_SUBCATEGORIES,
                              CATEGORY_TO_SUBCATEGORY, CATEGORIES,
                              SUBCATEGORIES, ALTERNATE_SUBCATEGORIES,
                              SUBCATEGORY_TO_CATEGORY)
from lib.render.theme import (base_css, layout_switch_script, mobile_core_css,
                              nav_bar_css)

OUT_PATH = ROOT / "search.html"

# qbreader's difficulty scale, for chip tooltips (0 = unrated).
DIFF_NAMES = [
    "Unrated", "Middle School", "Easy High School", "Regular High School",
    "Hard High School", "National High School", "Easy College",
    "Medium College", "Hard College", "Nationals College", "Open",
]


def _sync_base() -> str:
    src = (ROOT / "lib" / "js" / "sync.js").read_text(encoding="utf-8")
    m = re.search(r"const SYNC_BASE = '([^']*)'", src)
    if not m:
        raise SystemExit("SYNC_BASE not found in lib/js/sync.js")
    return m.group(1)


def render() -> str:
    cfg = {
        "syncBase": _sync_base(),
        "cats": CATEGORIES,
        "subs": SUBCATEGORIES,
        "alts": ALTERNATE_SUBCATEGORIES,
        "catToSubs": CATEGORY_TO_SUBCATEGORY,
        "catToAlts": CATEGORY_TO_ALTERNATE_SUBCATEGORIES,
        "subToCat": SUBCATEGORY_TO_CATEGORY,
        "altToCat": ALTERNATE_SUBCATEGORY_TO_CATEGORY,
        "diffNames": DIFF_NAMES,
    }
    return f"""<!DOCTYPE html>
<html lang="en" data-layout="desktop">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
{layout_switch_script()}
<title>Semantic Search — Library of Stock</title>
<style>
{base_css(max_width='860px')}
{nav_bar_css()}
.tagline {{ color: #9aa0a7; font-size: 0.85rem; margin-bottom: 1rem; }}
.qrow {{ display: flex; gap: 0.5rem; margin-bottom: 0.8rem; }}
.qrow input[type="text"] {{
    flex: 1; padding: 0.5rem 0.7rem; font-size: 0.95rem;
    background: #15191e; color: #c8ccd1;
    border: 1px solid #3a3f47; border-radius: 4px; outline: none;
    font-family: inherit;
}}
.qrow input[type="text"]:focus {{ border-color: #6b9eff; }}
.qrow button {{
    background: #1a1f25; border: 1px solid #3a3f47; border-radius: 4px;
    color: #c8ccd1; font-size: 0.9rem; cursor: pointer; padding: 0.5rem 1rem;
}}
.qrow button:hover {{ background: #262d37; border-color: #6b9eff; }}
.filters {{
    background: #1a1f25; border: 1px solid #3a3f47; border-radius: 6px;
    padding: 0.7rem 0.9rem; margin-bottom: 1rem; font-size: 0.85rem;
}}
.frow {{ display: flex; gap: 0.6rem; align-items: baseline; margin: 0.35rem 0; flex-wrap: wrap; }}
.frow-label {{ color: #808790; font-size: 0.75rem; text-transform: uppercase;
               letter-spacing: 0.05em; min-width: 6.5rem; }}
.fchips {{ display: flex; gap: 0.3rem; flex-wrap: wrap; }}
.fchip {{
    background: #15191e; border: 1px solid #3a3f47; border-radius: 12px;
    color: #9aa0a7; font-size: 0.8rem; cursor: pointer; padding: 0.15rem 0.6rem;
}}
.fchip:hover {{ border-color: #6b9eff; }}
.fchip[aria-pressed="true"] {{
    background: #24354f; border-color: #6b9eff; color: #cfe0ff;
}}
.frow input[type="number"], .frow input[type="text"] {{
    background: #15191e; color: #c8ccd1; border: 1px solid #3a3f47;
    border-radius: 3px; padding: 0.2rem 0.4rem; font-size: 0.82rem;
    font-family: inherit; outline: none; width: 6rem;
}}
.frow select {{
    background: #15191e; color: #c8ccd1; border: 1px solid #3a3f47;
    border-radius: 3px; padding: 0.2rem 0.3rem; font-size: 0.82rem;
    font-family: inherit;
}}
.frow .grow {{ flex: 1; }}
.fmeta {{ display: flex; justify-content: space-between; align-items: center;
          margin-top: 0.4rem; color: #808790; font-size: 0.78rem; }}
.linkbtn {{ background: none; border: none; color: #6b9eff; cursor: pointer;
            font-size: inherit; padding: 0; font-family: inherit; }}
.linkbtn:hover {{ text-decoration: underline; }}
.note {{ color: #9aa0a7; font-size: 0.85rem; font-style: italic; padding: 0.6rem 0; }}
.hit {{
    background: #1a1f25; border: 1px solid #3a3f47; border-radius: 6px;
    padding: 0.6rem 0.9rem; margin-bottom: 0.7rem; font-size: 0.88rem;
    line-height: 1.55;
}}
.hit-head {{ display: flex; gap: 0.7rem; align-items: baseline;
             margin-bottom: 0.35rem; }}
.hit-score {{ color: #6b9eff; font-size: 0.78rem; font-variant-numeric: tabular-nums; }}
.hit-badge {{ color: #808790; font-size: 0.78rem; }}
.hit-body p {{ margin-bottom: 0.35rem; }}
.hit-body mark {{ background: #3d4c2a; color: #dfe8c8; padding: 0 0.15rem;
                  border-radius: 2px; }}
.hit-body .ans {{ color: #9aa0a7; font-size: 0.82rem; }}
.hit-body .bpart {{ margin-left: 0.8rem; }}
{mobile_core_css()}
html[data-layout="mobile"] .frow-label {{ min-width: 100%; }}
</style>
</head>
<body>
<div class="nav-bar">
    <div class="nav-links">
        <a href="index.html">Library of Stock</a> &middot;
        <a href="wiki.html">Wiki</a> &middot;
        <a href="reader.html">Reader</a>
    </div>
    <span id="whoami" style="color:#808790;font-size:0.8rem"></span>
    <button type="button" class="linkbtn" id="csmode2" style="margin-left:0.7rem"></button>
</div>
<h1>Semantic Search</h1>
<div class="tagline">Every tossup sentence and bonus part ever asked,
ranked by semantic similarity.</div>

<div class="qrow">
    <input type="text" id="q" placeholder="e.g. a painter who cut off his ear"
           autocomplete="off" autofocus>
    <button type="button" id="gobtn">Search</button>
</div>

<div class="filters">
    <div class="frow"><span class="frow-label">Categories</span>
        <div class="fchips" id="cats"></div></div>
    <div class="frow" id="subrow" style="display:none">
        <span class="frow-label">Subcategories</span>
        <div class="fchips" id="subs"></div></div>
    <div class="frow" id="altrow" style="display:none">
        <span class="frow-label">Alt. subcats</span>
        <div class="fchips" id="alts"></div></div>
    <div class="frow"><span class="frow-label">Difficulties</span>
        <div class="fchips" id="diffs"></div></div>
    <div class="frow"><span class="frow-label">More</span>
        <select id="qtype">
            <option value="all">Tossups + bonuses</option>
            <option value="tossup">Tossups only</option>
            <option value="bonus">Bonuses only</option>
        </select>
        <label>year <input type="number" id="ymin" placeholder="min"></label>
        <label>&ndash; <input type="number" id="ymax" placeholder="max"></label>
        <input type="text" id="setname" class="grow" placeholder="set name contains&hellip;">
    </div>
    <div class="fmeta">
        <span>Filters mirror <a href="https://www.qbreader.org/db">qbreader/db</a>;
        empty = everything.</span>
        <button type="button" class="linkbtn" id="clearbtn">clear filters</button>
    </div>
</div>

<div id="results"></div>

<script>window.SEM_CFG = {json.dumps(cfg)};</script>
<script src="lib/js/qdata.js"></script>
<script src="lib/js/clue_search.js"></script>
<script src="lib/js/semsearch.js"></script>
</body>
</html>
"""


def build() -> None:
    OUT_PATH.write_text(render(), encoding="utf-8")
    print(f"search.html written -> {OUT_PATH}")


if __name__ == "__main__":
    build()
