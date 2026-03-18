"""
build_index.py — Generate a static index.html for GitHub Pages.

Scans output/ for *_stock.html files and creates an index page
with search and category filtering. Run this before committing new guides.

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
    margin-bottom: 0.8rem;
    outline: none;
}
.search:focus { border-color: #6b9eff; }
.search::placeholder { color: #666; }
.filters {
    display: flex;
    flex-wrap: wrap;
    gap: 0.4rem;
    margin-bottom: 0.8rem;
}
.filter-btn {
    padding: 0.25rem 0.6rem;
    font-size: 0.78rem;
    background: #1a1f25;
    color: #9aa0a7;
    border: 1px solid #3a3f47;
    border-radius: 3px;
    cursor: pointer;
    font-family: inherit;
}
.filter-btn:hover {
    background: #262d37;
    color: #c8ccd1;
}
.filter-btn.active {
    background: #2a3545;
    color: #6b9eff;
    border-color: #6b9eff;
}
.guide-list { list-style: none; }
.guide-item {
    border: 1px solid #3a3f47;
    background: #1a1f25;
    margin-bottom: 0.5rem;
    border-radius: 4px;
    overflow: hidden;
}
.guide-item a {
    display: flex;
    justify-content: space-between;
    align-items: baseline;
    padding: 0.6rem 0.8rem;
    color: #6b9eff;
    text-decoration: none;
    font-size: 0.95rem;
}
.guide-item a:hover { background: #262d37; }
.guide-info {
    flex: 1;
}
.guide-meta {
    font-size: 0.78rem;
    color: #808790;
    margin-top: 0.15rem;
}
.guide-cat {
    font-size: 0.72rem;
    color: #808790;
    border: 1px solid #3a3f47;
    border-radius: 3px;
    padding: 0.1rem 0.4rem;
    white-space: nowrap;
    flex-shrink: 0;
    margin-left: 0.5rem;
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
<div class="filters" id="cat-filters"></div>
<div class="filters" id="subcat-filters"></div>
<div class="count"></div>
<ul class="guide-list"></ul>
<script>
const guides = GUIDE_DATA;
const list = document.querySelector('.guide-list');
const search = document.querySelector('.search');
const count = document.querySelector('.count');
const catFiltersEl = document.getElementById('cat-filters');
const subcatFiltersEl = document.getElementById('subcat-filters');

let activeCategory = null;
let activeSubcategory = null;

// Build category filter buttons
const categories = [...new Set(guides.map(g => g.category).filter(Boolean))].sort();

function buildCatButtons() {
    catFiltersEl.innerHTML = '';
    const allBtn = document.createElement('button');
    allBtn.className = 'filter-btn' + (activeCategory === null ? ' active' : '');
    allBtn.textContent = 'All';
    allBtn.onclick = () => { activeCategory = null; activeSubcategory = null; buildCatButtons(); buildSubcatButtons(); render(); };
    catFiltersEl.appendChild(allBtn);

    categories.forEach(cat => {
        const btn = document.createElement('button');
        btn.className = 'filter-btn' + (cat === activeCategory ? ' active' : '');
        btn.textContent = cat;
        const catCount = guides.filter(g => g.category === cat).length;
        btn.textContent = cat + ' (' + catCount + ')';
        btn.onclick = () => {
            activeCategory = activeCategory === cat ? null : cat;
            activeSubcategory = null;
            buildCatButtons();
            buildSubcatButtons();
            render();
        };
        catFiltersEl.appendChild(btn);
    });
}

function buildSubcatButtons() {
    subcatFiltersEl.innerHTML = '';
    if (!activeCategory) return;

    const subcats = [...new Set(
        guides.filter(g => g.category === activeCategory)
              .map(g => g.subcategory)
              .filter(Boolean)
    )].sort();

    if (subcats.length <= 1) return;

    const allBtn = document.createElement('button');
    allBtn.className = 'filter-btn' + (activeSubcategory === null ? ' active' : '');
    allBtn.textContent = 'All ' + activeCategory;
    allBtn.onclick = () => { activeSubcategory = null; buildSubcatButtons(); render(); };
    subcatFiltersEl.appendChild(allBtn);

    subcats.forEach(sub => {
        const btn = document.createElement('button');
        const subCount = guides.filter(g => g.category === activeCategory && g.subcategory === sub).length;
        btn.className = 'filter-btn' + (sub === activeSubcategory ? ' active' : '');
        btn.textContent = sub.replace(activeCategory + ' - ', '').replace('Other ', 'Other') + ' (' + subCount + ')';
        btn.onclick = () => {
            activeSubcategory = activeSubcategory === sub ? null : sub;
            buildSubcatButtons();
            render();
        };
        subcatFiltersEl.appendChild(btn);
    });
}

function render() {
    const q = (search.value || '').toLowerCase();
    const filtered = guides.filter(g => {
        const matchesText = g.name.toLowerCase().includes(q);
        const matchesCat = !activeCategory || g.category === activeCategory;
        const matchesSub = !activeSubcategory || g.subcategory === activeSubcategory;
        return matchesText && matchesCat && matchesSub;
    });
    count.textContent = filtered.length + ' guide' + (filtered.length !== 1 ? 's' : '');
    if (filtered.length === 0) {
        list.innerHTML = '<li class="empty">No guides found.</li>';
        return;
    }
    list.innerHTML = filtered.map(g => {
        const subLabel = g.subcategory || g.category || '?';
        return `
        <li class="guide-item">
            <a href="${g.path}">
                <div class="guide-info">
                    ${g.name}
                    <div class="guide-meta">${g.works} works &middot; ${g.modified}</div>
                </div>
                <span class="guide-cat">${subLabel}</span>
            </a>
        </li>`;
    }).join('');
}

search.addEventListener('input', () => render());
buildCatButtons();
render();
</script>
</body>
</html>"""


def build():
    guides = []
    for f in sorted(OUTPUT_DIR.glob("*_stock.html")):
        # Default name from filename, but prefer topic from analysis JSON
        name = f.stem.replace("_stock", "").replace("_", " ").title()

        # Load metadata from analysis JSON
        analysis_json = f.with_name(f.stem.replace("_stock", "_analysis") + ".json")
        works_count = "?"
        category = ""
        subcategory = ""
        if analysis_json.exists():
            try:
                with open(analysis_json) as af:
                    data = json.load(af)
                    works_count = str(len(data.get("works", [])))
                    category = data.get("category", "")
                    subcategory = data.get("subcategory", "")
                    if data.get("topic"):
                        name = data["topic"]
            except Exception:
                pass

        mtime = datetime.fromtimestamp(f.stat().st_mtime).strftime("%Y-%m-%d")
        guides.append({
            "name": name,
            "path": f"output/{f.name}",
            "works": works_count,
            "category": category,
            "subcategory": subcategory,
            "modified": mtime,
        })

    html = INDEX_TEMPLATE.replace("GUIDE_DATA", json.dumps(guides))
    out_path = Path("index.html")
    with open(out_path, "w") as f:
        f.write(html)

    # Summary
    cat_counts = {}
    for g in guides:
        c = g["category"] or "Unknown"
        cat_counts[c] = cat_counts.get(c, 0) + 1

    print(f"Built index.html with {len(guides)} guides")
    for cat, cnt in sorted(cat_counts.items()):
        print(f"  {cat}: {cnt}")


if __name__ == "__main__":
    build()
