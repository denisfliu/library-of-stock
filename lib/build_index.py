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
.control-bar {
    display: flex;
    flex-wrap: wrap;
    gap: 0.8rem;
    margin-bottom: 1rem;
    align-items: flex-start;
}
.control-group {
    display: flex;
    align-items: center;
    gap: 0.4rem;
    flex-wrap: wrap;
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
.sort-label {
    font-size: 0.78rem;
    color: #808790;
}
.dropdown-wrap {
    position: relative;
    display: inline-block;
}
.dropdown-btn {
    padding: 0.25rem 0.6rem;
    font-size: 0.78rem;
    background: #1a1f25;
    color: #9aa0a7;
    border: 1px solid #3a3f47;
    border-radius: 3px;
    cursor: pointer;
    font-family: inherit;
}
.dropdown-btn:hover {
    background: #262d37;
    color: #c8ccd1;
}
.dropdown-btn.active {
    background: #2a3545;
    color: #6b9eff;
    border-color: #6b9eff;
}
.dropdown-panel {
    display: none;
    position: absolute;
    top: 100%;
    left: 0;
    margin-top: 0.3rem;
    background: #1a1f25;
    border: 1px solid #3a3f47;
    border-radius: 4px;
    min-width: 240px;
    z-index: 100;
    box-shadow: 0 4px 12px rgba(0,0,0,0.4);
}
.dropdown-panel.open {
    display: block;
}
.dropdown-search {
    width: 100%;
    padding: 0.4rem 0.6rem;
    font-size: 0.82rem;
    background: #15191e;
    color: #c8ccd1;
    border: none;
    border-bottom: 1px solid #3a3f47;
    outline: none;
    font-family: inherit;
}
.dropdown-search::placeholder {{ color: #555; }}
.dropdown-list {
    max-height: 250px;
    overflow-y: auto;
    list-style: none;
}
.dropdown-list label {
    display: flex;
    align-items: center;
    gap: 0.4rem;
    padding: 0.25rem 0.6rem;
    font-size: 0.82rem;
    color: #9aa0a7;
    cursor: pointer;
}
.dropdown-list label:hover {
    background: #262d37;
    color: #c8ccd1;
}
.dropdown-list label.cat-header {
    font-weight: 600;
    color: #c8ccd1;
    padding-top: 0.4rem;
}
.dropdown-list label.sub-item {
    padding-left: 1.6rem;
}
.dropdown-list input[type="checkbox"] {
    accent-color: #6b9eff;
    flex-shrink: 0;
}
.dropdown-list .item-count {
    color: #555;
    margin-left: auto;
    font-size: 0.75rem;
}
.guide-tags {
    display: flex;
    flex-wrap: wrap;
    gap: 0.25rem;
    margin-top: 0.2rem;
}
.guide-tag {
    font-size: 0.68rem;
    color: #808790;
    background: #15191e;
    border: 1px solid #2a2f37;
    border-radius: 8px;
    padding: 0.05rem 0.4rem;
    cursor: pointer;
}
.guide-tag:hover {
    color: #6b9eff;
    border-color: #6b9eff;
}
.guide-tag.active {
    color: #6b9eff;
    border-color: #6b9eff;
    background: #2a3545;
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
.view-toggle {
    display: flex;
    gap: 0.3rem;
    margin-bottom: 1rem;
}
.view-btn {
    padding: 0.3rem 0.8rem;
    font-size: 0.82rem;
    background: #1a1f25;
    color: #9aa0a7;
    border: 1px solid #3a3f47;
    border-radius: 3px;
    cursor: pointer;
    font-family: inherit;
}
.view-btn:hover { background: #262d37; color: #c8ccd1; }
.view-btn.active { background: #2a3545; color: #6b9eff; border-color: #6b9eff; }
.map-grid {
    display: flex;
    flex-direction: column;
    gap: 1.5rem;
}
.continent-section h3 {
    font-family: 'Linux Libertine', Georgia, serif;
    font-weight: normal;
    font-size: 1.1rem;
    color: #e0e0e0;
    border-bottom: 1px solid #2a2f37;
    padding-bottom: 0.2rem;
    margin-bottom: 0.6rem;
}
.country-bubbles {
    display: flex;
    flex-wrap: wrap;
    gap: 0.4rem;
}
.country-bubble {
    padding: 0.3rem 0.7rem;
    font-size: 0.82rem;
    background: #1a1f25;
    color: #9aa0a7;
    border: 1px solid #3a3f47;
    border-radius: 16px;
    cursor: pointer;
    font-family: inherit;
    transition: all 0.15s;
}
.country-bubble:hover {
    background: #2a3545;
    color: #6b9eff;
    border-color: #6b9eff;
}
.country-bubble.active {
    background: #2a3545;
    color: #6b9eff;
    border-color: #6b9eff;
}
.country-bubble .bubble-count {
    font-size: 0.72rem;
    color: #555;
    margin-left: 0.2rem;
}
.map-timeline {
    margin-top: 1.5rem;
    border: 1px solid #3a3f47;
    border-radius: 4px;
    background: #1a1f25;
    overflow: hidden;
}
.timeline-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 0.6rem 0.8rem;
    border-bottom: 1px solid #3a3f47;
    background: #15191e;
}
.timeline-header h2 {
    font-family: 'Linux Libertine', Georgia, serif;
    font-weight: normal;
    font-size: 1rem;
    color: #e0e0e0;
}
.timeline-close {
    background: none;
    border: none;
    color: #808790;
    font-size: 1.2rem;
    cursor: pointer;
    padding: 0 0.3rem;
}
.timeline-close:hover { color: #c8ccd1; }
.timeline-entries {
    max-height: 400px;
    overflow-y: auto;
}
.timeline-entry {
    display: flex;
    align-items: baseline;
    gap: 0.6rem;
    padding: 0.5rem 0.8rem;
    border-bottom: 1px solid #2a2f37;
}
.timeline-entry:last-child { border-bottom: none; }
.timeline-entry:hover { background: #262d37; }
.timeline-year {
    font-size: 0.78rem;
    color: #808790;
    min-width: 3.5rem;
    text-align: right;
    flex-shrink: 0;
}
.timeline-dot {
    width: 6px;
    height: 6px;
    border-radius: 50%;
    background: #6b9eff;
    flex-shrink: 0;
    margin-top: 0.35rem;
}
.timeline-link {
    color: #6b9eff;
    text-decoration: none;
    font-size: 0.9rem;
}
.timeline-link:hover { text-decoration: underline; }
.timeline-cat {
    font-size: 0.68rem;
    color: #808790;
    border: 1px solid #3a3f47;
    border-radius: 3px;
    padding: 0.05rem 0.3rem;
    margin-left: auto;
    white-space: nowrap;
    flex-shrink: 0;
}
</style>
</head>
<body>
<div style="display:flex;justify-content:space-between;align-items:baseline;">
<h1>Stock Knowledge Guides</h1>
<div style="display:flex;gap:0.5rem;">
<a href="progress.html" style="background:#1a1f25;color:#9aa0a7;border:1px solid #3a3f47;border-radius:4px;padding:0.25rem 0.6rem;font-size:0.78rem;text-decoration:none;white-space:nowrap;">Progress</a>
<button style="background:#1a1f25;color:#9aa0a7;border:1px solid #3a3f47;border-radius:4px;padding:0.25rem 0.6rem;font-size:0.78rem;cursor:pointer;white-space:nowrap;" onclick="document.getElementById('queue-panel').style.display=document.getElementById('queue-panel').style.display==='none'?'block':'none'">Queue <span style="background:#2a3040;color:#6b9eff;border-radius:8px;padding:0.1rem 0.4rem;font-size:0.72rem;margin-left:0.3rem;">QUEUE_TOTAL</span></button>
<button style="background:#1a1f25;color:#9aa0a7;border:1px solid #3a3f47;border-radius:4px;padding:0.25rem 0.6rem;font-size:0.85rem;cursor:pointer;line-height:1;" title="Random guide" onclick="const g=guides[Math.floor(Math.random()*guides.length)];if(g)window.location.href=g.path;">&#x1f3b2;</button>
</div>
</div>
<div id="queue-panel" style="display:none;background:#15191e;border:1px solid #2a2f37;border-radius:4px;padding:0.8rem 1rem;margin-bottom:0.8rem;font-size:0.82rem;max-height:50vh;overflow-y:auto;">
  <div style="display:flex;gap:1.5rem;">
    <div style="flex:1;">
      <h3 style="font-size:0.85rem;color:#e0e0e0;margin-bottom:0.4rem;">First Pass (FIRST_COUNT)</h3>
      <ul style="list-style:none;max-height:30vh;overflow-y:auto;color:#9aa0a7;">FIRST_PASS_LIST</ul>
    </div>
    <div style="flex:1;">
      <h3 style="font-size:0.85rem;color:#e0e0e0;margin-bottom:0.4rem;">Second Pass (SECOND_COUNT)</h3>
      <ul style="list-style:none;max-height:30vh;overflow-y:auto;color:#9aa0a7;">SECOND_PASS_LIST</ul>
    </div>
  </div>
</div>
<div class="view-toggle">
    <button class="view-btn active" data-view="list">All</button>
    <button class="view-btn" data-view="location">Location</button>
</div>
<input class="search" type="text" placeholder="Search guides..." autofocus>
<div class="control-bar">
    <div class="control-group">
        <span class="sort-label">Category:</span>
        <div class="dropdown-wrap" id="cat-wrap">
            <button class="dropdown-btn" id="cat-btn">All</button>
            <div class="dropdown-panel" id="cat-panel">
                <input class="dropdown-search" id="cat-search" type="text" placeholder="Search categories...">
                <div class="dropdown-list" id="cat-list"></div>
            </div>
        </div>
    </div>
</div>
<div class="control-bar">
    <div class="control-group">
        <span class="sort-label">Tags:</span>
        <div class="dropdown-wrap" id="tag-wrap">
            <button class="dropdown-btn" id="tag-btn">All</button>
            <div class="dropdown-panel" id="tag-panel">
                <input class="dropdown-search" id="tag-search" type="text" placeholder="Search tags...">
                <div class="dropdown-list" id="tag-list"></div>
            </div>
        </div>
    </div>
</div>
<div id="list-view">
<div class="control-bar">
    <div class="control-group">
        <span class="sort-label">Sort:</span>
        <button class="filter-btn active" data-sort="alpha">A-Z</button>
        <button class="filter-btn" data-sort="year">Chronological</button>
        <button class="filter-btn" data-sort="continent">Continent</button>
        <button class="filter-btn" data-sort="created">Date added</button>
    </div>
</div>
<div class="count"></div>
<ul class="guide-list"></ul>
</div>
<div id="continent-view" style="display:none;">
    <div class="map-container">
        <div class="map-grid" id="map-grid"></div>
    </div>
    <div id="map-timeline" class="map-timeline" style="display:none;">
        <div class="timeline-header">
            <h2 id="timeline-title"></h2>
            <button class="timeline-close" onclick="closeTimeline()">&times;</button>
        </div>
        <div id="timeline-entries" class="timeline-entries"></div>
    </div>
</div>
<script>
const guides = GUIDE_DATA;
const list = document.querySelector('.guide-list');
const search = document.querySelector('.search');
const countEl = document.querySelector('.count');

// --- State ---
let selectedCats = new Set();     // category or subcategory strings
let selectedTags = new Set();
let activeSort = 'alpha';

// --- Helpers ---
const categories = [...new Set(guides.map(g => g.category).filter(Boolean))].sort();
const allTags = [...new Set(guides.flatMap(g => g.tags || []))].sort();

function setupDropdown(wrapId, btnId, panelId, searchId) {
    const wrap = document.getElementById(wrapId);
    const btn = document.getElementById(btnId);
    const panel = document.getElementById(panelId);
    const searchInput = document.getElementById(searchId);
    btn.onclick = (e) => {
        e.stopPropagation();
        // close other panels
        document.querySelectorAll('.dropdown-panel.open').forEach(p => {
            if (p !== panel) p.classList.remove('open');
        });
        panel.classList.toggle('open');
        if (panel.classList.contains('open')) {
            searchInput.value = '';
            setTimeout(() => searchInput.focus(), 0);
        }
    };
    searchInput.addEventListener('click', e => e.stopPropagation());
    return { wrap, btn, panel, searchInput };
}

const catDD = setupDropdown('cat-wrap', 'cat-btn', 'cat-panel', 'cat-search');
const tagDD = setupDropdown('tag-wrap', 'tag-btn', 'tag-panel', 'tag-search');

document.addEventListener('click', () => {
    document.querySelectorAll('.dropdown-panel.open').forEach(p => p.classList.remove('open'));
});

// prevent dropdown clicks from closing
document.querySelectorAll('.dropdown-panel').forEach(p => {
    p.addEventListener('click', e => e.stopPropagation());
});

// --- Category dropdown (checkboxes, hierarchical) ---
function buildCatList(filter) {
    const q = (filter || '').toLowerCase();
    const el = document.getElementById('cat-list');
    el.innerHTML = '';

    categories.forEach(cat => {
        const subcats = [...new Set(guides.filter(g => g.category === cat).map(g => g.subcategory).filter(Boolean))].sort();
        const catMatches = cat.toLowerCase().includes(q);
        const subMatches = subcats.some(s => s.toLowerCase().includes(q));
        if (!catMatches && !subMatches) return;

        // Category header with checkbox
        const catCount = guides.filter(g => g.category === cat).length;
        const catLabel = document.createElement('label');
        catLabel.className = 'cat-header';
        const catCb = document.createElement('input');
        catCb.type = 'checkbox';
        catCb.checked = selectedCats.has(cat);
        catCb.onchange = () => {
            if (catCb.checked) {
                selectedCats.add(cat);
                // also select all visible subcats
                subcats.forEach(s => selectedCats.add(s));
            } else {
                selectedCats.delete(cat);
                subcats.forEach(s => selectedCats.delete(s));
            }
            updateCatBtn();
            buildCatList(filter);
            buildTagList(document.getElementById('tag-search').value);
            update();
        };
        catLabel.appendChild(catCb);
        catLabel.appendChild(document.createTextNode(cat));
        const span = document.createElement('span');
        span.className = 'item-count';
        span.textContent = catCount;
        catLabel.appendChild(span);
        el.appendChild(catLabel);

        // Subcategories
        if (subcats.length > 1) {
            subcats.forEach(sub => {
                if (q && !sub.toLowerCase().includes(q) && !catMatches) return;
                const subCount = guides.filter(g => g.subcategory === sub).length;
                const subLabel = document.createElement('label');
                subLabel.className = 'sub-item';
                const subCb = document.createElement('input');
                subCb.type = 'checkbox';
                subCb.checked = selectedCats.has(sub);
                subCb.onchange = () => {
                    if (subCb.checked) {
                        selectedCats.add(sub);
                    } else {
                        selectedCats.delete(sub);
                        selectedCats.delete(cat); // uncheck parent
                    }
                    updateCatBtn();
                    buildCatList(filter);
                    buildTagList(document.getElementById('tag-search').value);
                    update();
                };
                subLabel.appendChild(subCb);
                subLabel.appendChild(document.createTextNode(sub));
                const sspan = document.createElement('span');
                sspan.className = 'item-count';
                sspan.textContent = subCount;
                subLabel.appendChild(sspan);
                el.appendChild(subLabel);
            });
        }
    });
}

function updateCatBtn() {
    if (selectedCats.size === 0) {
        catDD.btn.textContent = 'All';
        catDD.btn.classList.remove('active');
    } else {
        catDD.btn.textContent = selectedCats.size + ' selected';
        catDD.btn.classList.add('active');
    }
}

catDD.searchInput.addEventListener('input', e => buildCatList(e.target.value));
buildCatList('');

// --- Tag dropdown (checkboxes, flat but context-aware) ---
function getVisibleGuides() {
    if (selectedCats.size === 0) return guides;
    return guides.filter(g => selectedCats.has(g.category) || selectedCats.has(g.subcategory));
}

function buildTagList(filter) {
    const q = (filter || '').toLowerCase();
    const el = document.getElementById('tag-list');
    el.innerHTML = '';

    const visible = getVisibleGuides();
    const visibleTags = [...new Set(visible.flatMap(g => g.tags || []))].sort();
    const filtered = visibleTags.filter(t => t.toLowerCase().includes(q));

    // Remove tags that are no longer visible
    selectedTags.forEach(t => {
        if (!visibleTags.includes(t)) selectedTags.delete(t);
    });

    filtered.forEach(tag => {
        const tagCount = visible.filter(g => (g.tags || []).includes(tag)).length;
        const label = document.createElement('label');
        const cb = document.createElement('input');
        cb.type = 'checkbox';
        cb.checked = selectedTags.has(tag);
        cb.onchange = () => {
            if (cb.checked) selectedTags.add(tag);
            else selectedTags.delete(tag);
            updateTagBtn();
            update();
        };
        label.appendChild(cb);
        label.appendChild(document.createTextNode(tag));
        const span = document.createElement('span');
        span.className = 'item-count';
        span.textContent = tagCount;
        label.appendChild(span);
        el.appendChild(label);
    });
}

function updateTagBtn() {
    if (selectedTags.size === 0) {
        tagDD.btn.textContent = 'All';
        tagDD.btn.classList.remove('active');
    } else {
        tagDD.btn.textContent = selectedTags.size + ' selected';
        tagDD.btn.classList.add('active');
    }
}

tagDD.searchInput.addEventListener('input', e => buildTagList(e.target.value));
buildTagList('');

// --- Helpers ---
function normalize(s) {
    return s.normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase();
}

// --- Render ---
function render() {
    const q = normalize(search.value || '');
    let filtered = guides.filter(g => {
        const matchesText = normalize(g.name).includes(q);
        const matchesCat = selectedCats.size === 0 || selectedCats.has(g.category) || selectedCats.has(g.subcategory);
        const matchesTag = selectedTags.size === 0 || (g.tags && g.tags.some(t => selectedTags.has(t)));
        return matchesText && matchesCat && matchesTag;
    });
    filtered.sort(sortFns[activeSort] || sortFns.alpha);
    countEl.textContent = filtered.length + ' guide' + (filtered.length !== 1 ? 's' : '');
    if (filtered.length === 0) {
        list.innerHTML = '<li class="empty">No guides found.</li>';
        return;
    }
    list.innerHTML = filtered.map(g => {
        const subLabel = g.subcategory || g.category || '?';
        let meta = g.works + ' topics';
        if (g.year) meta += ' &middot; ' + (g.year < 0 ? Math.abs(g.year) + ' BCE' : g.year);
        if (g.country && g.continent) meta += ' &middot; ' + g.continent + ' &middot; ' + g.country;
        else if (g.continent) meta += ' &middot; ' + g.continent;
        const tagsHtml = (g.tags || []).map(t => {
            const isActive = selectedTags.has(t);
            return `<span class="guide-tag${isActive ? ' active' : ''}" onclick="event.preventDefault();event.stopPropagation();if(selectedTags.has('${t}'))selectedTags.delete('${t}');else selectedTags.add('${t}');updateTagBtn();buildTagList('');update();">${t}</span>`;
        }).join('');
        return `
        <li class="guide-item">
            <a href="${g.path}">
                <div class="guide-info">
                    ${g.name}
                    <div class="guide-meta">${meta}</div>
                    <div class="guide-tags">${tagsHtml}</div>
                </div>
                <span class="guide-cat">${subLabel}</span>
            </a>
        </li>`;
    }).join('');
}

// --- Sorting ---
const sortFns = {
    alpha: (a, b) => a.name.localeCompare(b.name),
    year: (a, b) => (a.year || 9999) - (b.year || 9999),
    continent: (a, b) => (a.continent || 'ZZZ').localeCompare(b.continent || 'ZZZ') || a.name.localeCompare(b.name),
    created: (a, b) => b.modified.localeCompare(a.modified),
};

document.querySelectorAll('.filter-btn[data-sort]').forEach(btn => {
    btn.addEventListener('click', () => {
        activeSort = btn.dataset.sort;
        document.querySelectorAll('.filter-btn[data-sort]').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        render();
    });
});

let currentView = 'list';
function isLocationActive() {
    return currentView === 'location';
}
function update() {
    render();
    if (isLocationActive()) buildLocationView();
}
search.addEventListener('input', () => update());
render();

// --- View toggle ---
document.querySelectorAll('.view-btn').forEach(btn => {
    btn.addEventListener('click', () => {
        document.querySelectorAll('.view-btn').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        currentView = btn.dataset.view;
        document.getElementById('list-view').style.display = currentView === 'list' ? '' : 'none';
        document.getElementById('continent-view').style.display = currentView === 'location' ? '' : 'none';
        if (currentView === 'location') buildLocationView();
    });
});

// --- Map view ---
function getFilteredGuides() {
    const q = (search.value || '').toLowerCase();
    return guides.filter(g => {
        const matchesText = g.name.toLowerCase().includes(q);
        const matchesCat = selectedCats.size === 0 || selectedCats.has(g.category) || selectedCats.has(g.subcategory);
        const matchesTag = selectedTags.size === 0 || (g.tags && g.tags.some(t => selectedTags.has(t)));
        return matchesText && matchesCat && matchesTag;
    });
}

function buildLocationView() {
    const grid = document.getElementById('map-grid');
    grid.innerHTML = '';
    closeTimeline();

    const filtered = getFilteredGuides();
    const continentOrder = ['Europe', 'North America', 'Asia', 'South America', 'Africa', 'Oceania'];
    const byContinent = {};
    filtered.forEach(g => {
        const cont = g.continent || 'Other';
        if (!byContinent[cont]) byContinent[cont] = {};
        const country = g.country || 'Unknown';
        if (!byContinent[cont][country]) byContinent[cont][country] = [];
        byContinent[cont][country].push(g);
    });

    const sortedContinents = Object.keys(byContinent).sort((a, b) => {
        const ai = continentOrder.indexOf(a); const bi = continentOrder.indexOf(b);
        return (ai === -1 ? 99 : ai) - (bi === -1 ? 99 : bi);
    });

    if (sortedContinents.length === 0) {
        grid.innerHTML = '<div class="empty">No guides match current filters.</div>';
        return;
    }

    // Top-level buttons: All + each continent
    const topBar = document.createElement('div');
    topBar.className = 'country-bubbles';
    topBar.style.marginBottom = '1rem';

    const allBtn = document.createElement('button');
    allBtn.className = 'country-bubble';
    allBtn.innerHTML = 'All <span class="bubble-count">' + filtered.length + '</span>';
    allBtn.onclick = () => {
        document.querySelectorAll('.country-bubble.active').forEach(b => b.classList.remove('active'));
        allBtn.classList.add('active');
        showTimeline('All', filtered);
    };
    topBar.appendChild(allBtn);

    sortedContinents.forEach(cont => {
        const total = Object.values(byContinent[cont]).reduce((s, arr) => s + arr.length, 0);
        const btn = document.createElement('button');
        btn.className = 'country-bubble';
        btn.innerHTML = cont + ' <span class="bubble-count">' + total + '</span>';
        btn.onclick = () => {
            document.querySelectorAll('.country-bubble.active').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            const allInContinent = Object.values(byContinent[cont]).flat();
            showTimeline(cont, allInContinent);
        };
        topBar.appendChild(btn);
    });
    grid.appendChild(topBar);

    // Auto-select All
    allBtn.classList.add('active');
    showTimeline('All', filtered);

    // Per-continent sections with country bubbles
    sortedContinents.forEach(cont => {
        const section = document.createElement('div');
        section.className = 'continent-section';
        const h3 = document.createElement('h3');
        const total = Object.values(byContinent[cont]).reduce((s, arr) => s + arr.length, 0);
        h3.textContent = cont + ' (' + total + ')';
        section.appendChild(h3);

        const bubbles = document.createElement('div');
        bubbles.className = 'country-bubbles';
        const countries = Object.entries(byContinent[cont]).sort((a, b) => b[1].length - a[1].length);
        countries.forEach(([country, countryGuides]) => {
            const bubble = document.createElement('button');
            bubble.className = 'country-bubble';
            bubble.innerHTML = country + ' <span class="bubble-count">' + countryGuides.length + '</span>';
            bubble.onclick = () => {
                document.querySelectorAll('.country-bubble.active').forEach(b => b.classList.remove('active'));
                bubble.classList.add('active');
                showTimeline(country, countryGuides);
            };
            bubbles.appendChild(bubble);
        });
        section.appendChild(bubbles);
        grid.appendChild(section);
    });
}

function showTimeline(label, guideList) {
    const panel = document.getElementById('map-timeline');
    const title = document.getElementById('timeline-title');
    const entries = document.getElementById('timeline-entries');

    title.textContent = label;
    panel.style.display = '';

    // Sort by year
    const sorted = [...guideList].sort((a, b) => (a.year || 9999) - (b.year || 9999));

    entries.innerHTML = sorted.map(g => {
        const yearStr = g.year ? (g.year < 0 ? Math.abs(g.year) + ' BCE' : g.year) : '?';
        const catLabel = g.subcategory || g.category || '';
        const countryLabel = g.country ? ' &middot; ' + g.country : '';
        return `<div class="timeline-entry">
            <span class="timeline-year">${yearStr}</span>
            <span class="timeline-dot"></span>
            <a href="${g.path}" class="timeline-link">${g.name}</a>
            <span class="timeline-cat">${catLabel}${countryLabel}</span>
        </div>`;
    }).join('');
}

function closeTimeline() {
    document.getElementById('map-timeline').style.display = 'none';
    document.querySelectorAll('.country-bubble.active').forEach(b => b.classList.remove('active'));
}
</script>
</body>
</html>"""




def build():
    guides = []
    for f in sorted(OUTPUT_DIR.glob("*_stock.html")):
        # Default name from filename, but prefer topic from analysis JSON
        # Use removesuffix to only strip the trailing _stock, not _stock inside names like Stockton
        slug = f.stem.removesuffix("_stock") if f.stem.endswith("_stock") else f.stem
        name = slug.replace("_", " ").title()

        # Load metadata from analysis JSON
        analysis_json = f.with_name(slug + "_analysis.json")
        works_count = "?"
        category = ""
        subcategory = ""
        year = None
        continent = ""
        country = ""
        tags = []
        if analysis_json.exists():
            try:
                with open(analysis_json) as af:
                    data = json.load(af)
                    works_count = str(sum(1 for w in data.get("works", [])
                        if not any(x in w.get("name", "") for x in
                        ["General", "Biographical", "Other Works", "Other "])))
                    category = data.get("category", "")
                    subcategory = data.get("subcategory", "")
                    year = data.get("year")
                    continent = data.get("continent", "")
                    country = data.get("country", "")
                    tags = data.get("tags", [])
                    if data.get("topic"):
                        name = data["topic"]
            except Exception:
                pass

        mtime = datetime.fromtimestamp(f.stat().st_mtime).strftime("%Y-%m-%d")
        guide = {
            "name": name,
            "path": f"output/{f.name}",
            "works": works_count,
            "category": category,
            "subcategory": subcategory,
            "modified": mtime,
            "continent": continent,
            "country": country,
            "tags": tags,
        }
        if year is not None:
            guide["year"] = year
        guides.append(guide)

    # Queue data for index page
    queue_first = json.loads(Path("queue/queue_first_pass.json").read_text()) if Path("queue/queue_first_pass.json").exists() else {"queue": []}
    queue_second = json.loads(Path("queue/queue_second_pass.json").read_text()) if Path("queue/queue_second_pass.json").exists() else {"queue": []}
    first_count = len(queue_first["queue"])
    second_count = len(queue_second["queue"])
    total_count = first_count + second_count
    first_list = "".join(f'<li style="padding:0.2rem 0;border-bottom:1px solid #1a1f25">{item["topic"]}</li>' for item in queue_first["queue"]) or '<li style="color:#555;font-style:italic">Empty</li>'
    second_list = "".join(f'<li style="padding:0.2rem 0;border-bottom:1px solid #1a1f25">{item["topic"]}</li>' for item in queue_second["queue"]) or '<li style="color:#555;font-style:italic">Empty</li>'

    # Write shared guides data file for search_nav.js
    guides_js_path = OUTPUT_DIR / "guides_data.js"
    with open(guides_js_path, "w") as gf:
        gf.write("const GUIDES_DATA = ")
        json.dump(guides, gf, ensure_ascii=False)
        gf.write(";\n")

    html = INDEX_TEMPLATE.replace("GUIDE_DATA", json.dumps(guides))
    html = html.replace("QUEUE_TOTAL", str(total_count))
    html = html.replace("FIRST_COUNT", str(first_count))
    html = html.replace("SECOND_COUNT", str(second_count))
    html = html.replace("FIRST_PASS_LIST", first_list)
    html = html.replace("SECOND_PASS_LIST", second_list)

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
