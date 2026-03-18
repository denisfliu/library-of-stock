"""
build_index.py — Generate a static index.html for GitHub Pages.

Scans output/ for *_stock.html files and creates an index page
with search/filter. Run this before committing new guides.

Usage:
    python build_index.py
"""

import json
from datetime import datetime
from pathlib import Path

OUTPUT_DIR = Path("output")

INDEX_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Stock Knowledge Guides</title>
<style>
* { margin: 0; padding: 0; box-sizing: border-box; }
body {
    font-family: -apple-system, 'Segoe UI', Roboto, sans-serif;
    background: #101418;
    color: #c8ccd1;
    max-width: 700px;
    margin: 0 auto;
    padding: 2rem 1.5rem;
}
h1 {
    font-family: 'Linux Libertine', Georgia, serif;
    font-weight: normal;
    font-size: 1.6rem;
    color: #e0e0e0;
    border-bottom: 1px solid #3a3f47;
    padding-bottom: 0.3rem;
    margin-bottom: 1rem;
}
.search {
    width: 100%;
    padding: 0.5rem 0.8rem;
    font-size: 0.95rem;
    background: #1a1f25;
    color: #c8ccd1;
    border: 1px solid #3a3f47;
    border-radius: 4px;
    margin-bottom: 1rem;
    outline: none;
}
.search:focus { border-color: #6b9eff; }
.search::placeholder { color: #666; }
.guide-list { list-style: none; }
.guide-item {
    border: 1px solid #3a3f47;
    background: #1a1f25;
    margin-bottom: 0.5rem;
    border-radius: 4px;
    overflow: hidden;
}
.guide-item a {
    display: block;
    padding: 0.6rem 0.8rem;
    color: #6b9eff;
    text-decoration: none;
    font-size: 0.95rem;
}
.guide-item a:hover { background: #262d37; }
.guide-meta {
    font-size: 0.78rem;
    color: #808790;
    margin-top: 0.15rem;
}
.empty {
    color: #666;
    font-style: italic;
    padding: 1rem 0;
}
.count {
    font-size: 0.82rem;
    color: #808790;
    margin-bottom: 0.8rem;
}
</style>
</head>
<body>
<h1>Stock Knowledge Guides</h1>
<input class="search" type="text" placeholder="Search guides..." autofocus>
<div class="count"></div>
<ul class="guide-list"></ul>
<script>
const guides = GUIDE_DATA;
const list = document.querySelector('.guide-list');
const search = document.querySelector('.search');
const count = document.querySelector('.count');

function render(filter) {
    const q = (filter || '').toLowerCase();
    const filtered = guides.filter(g => g.name.toLowerCase().includes(q));
    count.textContent = filtered.length + ' guide' + (filtered.length !== 1 ? 's' : '');
    if (filtered.length === 0) {
        list.innerHTML = '<li class="empty">No guides found.</li>';
        return;
    }
    list.innerHTML = filtered.map(g => `
        <li class="guide-item">
            <a href="${g.path}">
                ${g.name}
                <div class="guide-meta">${g.works} works &middot; ${g.modified}</div>
            </a>
        </li>
    `).join('');
}

search.addEventListener('input', e => render(e.target.value));
render('');
</script>
</body>
</html>"""


def build():
    guides = []
    for f in sorted(OUTPUT_DIR.glob("*_stock.html")):
        name = f.stem.replace("_stock", "").replace("_", " ").title()

        # Count works from analysis JSON if available
        analysis_json = f.with_name(f.stem.replace("_stock", "_analysis") + ".json")
        works_count = "?"
        if analysis_json.exists():
            try:
                with open(analysis_json) as af:
                    data = json.load(af)
                    works_count = str(len(data.get("works", [])))
            except Exception:
                pass

        mtime = datetime.fromtimestamp(f.stat().st_mtime).strftime("%Y-%m-%d")
        guides.append({
            "name": name,
            "path": f"output/{f.name}",
            "works": works_count,
            "modified": mtime,
        })

    html = INDEX_TEMPLATE.replace("GUIDE_DATA", json.dumps(guides))
    out_path = Path("index.html")
    with open(out_path, "w") as f:
        f.write(html)

    print(f"Built index.html with {len(guides)} guides")
    for g in guides:
        print(f"  {g['name']} ({g['works']} works)")


if __name__ == "__main__":
    build()
