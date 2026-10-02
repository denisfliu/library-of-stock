"""
build_index.py — Generate wiki.html (the wiki browse page) for GitHub Pages.

Scans output/*/stock.html and creates an index page with search and
category filtering. Run this before committing new guides.

Usage:
    python lib/build_index.py
"""

import json
import sys
from datetime import datetime
from html import escape
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from lib.common import ROOT, OUTPUT_DIR, QUEUE_DIR, CATEGORIES_DIR, SETS_DIR, resolve_analyses
from lib.render.theme import (base_css, layout_switch_script, mobile_core_css,
                              site_nav, site_nav_css)

# Disclosure chevron for the expandable overview rows (rotates when open).
CHEVRON = ('<svg class="ov-arrow" width="14" height="14" viewBox="0 0 24 24" fill="none" '
           'stroke="currentColor" stroke-width="2" stroke-linecap="round" '
           'stroke-linejoin="round" aria-hidden="true"><path d="M6 9l6 6 6-6"/></svg>')

# Right side of the shared site nav: the Dev menu (dev dashboards + the
# queue panel toggle) and the Random page button.
NAV_TOOLS = """<div id="dev-menu">
  <button class="nav-btn muted" onclick="var p=document.getElementById('dev-panel');p.style.display=p.style.display==='flex'?'none':'flex'">Dev<span class="d-only"> &#9662;</span></button>
  <div id="dev-panel">
    <a class="dev-item" href="dev/score_clues_review.html">Score clue reviews</a>
    <button class="dev-item" onclick="var p=document.getElementById('queue-panel');p.style.display=p.style.display==='block'?'none':'block';document.getElementById('dev-panel').style.display='none'">Queue <span class="dev-count">QUEUE_TOTAL</span></button>
    <a class="dev-item" href="dev/progress.html">Progress</a>
    <a class="dev-item" href="dev/stats.html">Stats</a>
    <a class="dev-item" href="dev/changelog.html">Changelog</a>
    <a class="dev-item" href="dev/crossrefs.html">Cross-refs</a>
  </div>
</div>
<button class="nav-btn nav-random" title="Random page" aria-label="Random page" onclick="const g=guides[Math.floor(Math.random()*guides.length)];if(g)window.location.href=g.path;"><svg class="m-only" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M16 3h5v5"/><path d="M4 20L21 3"/><path d="M21 16v5h-5"/><path d="M15 15l6 6"/><path d="M4 4l5 5"/></svg><span class="d-only">Random</span></button>"""

INDEX_TEMPLATE = """<!DOCTYPE html>
<html lang="en" data-layout="desktop">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
LAYOUT_SWITCH
<title>Wiki — Library of Stock</title>
<style>
BASE_CSS
NAV_CSS
body { font-size: 15px; line-height: 1.5; }
a { color: var(--c-link); text-decoration: none; }
.site-nav { margin-bottom: 0; padding-bottom: 14px; }
h1 { margin-top: 36px; }
.nav-btn {
    font: inherit; font-size: 14px; color: var(--c-link); background: none;
    border: 1px solid var(--c-border); border-radius: 8px; padding: 5px 12px;
    cursor: pointer; white-space: nowrap; line-height: 1.4;
}
.nav-btn:hover { border-color: var(--c-link); }
.nav-btn.muted { color: var(--c-muted); }
#dev-menu { position: relative; }
#dev-panel {
    display: none; position: absolute; right: 0; top: calc(100% + 6px);
    background: var(--c-bg); border: 1px solid var(--c-border); border-radius: 10px;
    padding: 0.35rem; flex-direction: column; gap: 0.1rem; z-index: 100; min-width: 180px;
    box-shadow: 0 8px 24px rgba(0,0,0,0.14);
}
.dev-item {
    display: block; width: 100%; text-align: left; font: inherit; font-size: 14px;
    color: var(--c-text); background: none; border: none; border-radius: 8px;
    padding: 0.35rem 0.6rem; cursor: pointer; white-space: nowrap; text-decoration: none;
}
.dev-item:hover { background: var(--c-hover); text-decoration: none; }
.dev-count {
    color: var(--c-muted); border: 1px solid var(--c-border); border-radius: 99px;
    padding: 0 0.4rem; font-size: 12px; margin-left: 0.3rem;
}
#queue-panel {
    display: none; border: 1px solid var(--c-border); border-radius: 10px;
    padding: 0.8rem 1rem; margin-top: 1rem; font-size: 0.85rem;
    max-height: 50vh; overflow-y: auto;
}
.queue-cols { display: flex; gap: 1.5rem; }
.queue-cols > div { flex: 1; min-width: 0; }
.queue-cols h3 { font-size: 0.85rem; font-weight: 600; color: var(--c-text); margin-bottom: 0.4rem; }
.queue-cols ul { list-style: none; max-height: 30vh; overflow-y: auto; color: var(--c-muted); }
.queue-cols li { padding: 0.2rem 0; border-bottom: 1px solid var(--c-border); }
.queue-cols li a { color: var(--c-muted); }
.queue-cols li a:hover { color: var(--c-link); }
.queue-cols li.q-empty { color: var(--c-faint2); font-style: italic; border-bottom: none; }

/* --- view tabs --- */
.view-toggle {
    display: flex; gap: 26px; margin-top: 14px;
    border-bottom: 1px solid var(--c-border);
}
.view-btn {
    font: inherit; font-size: 15px; color: var(--c-muted); background: none;
    border: none; border-radius: 0; padding: 0 0 10px; cursor: pointer;
}
.view-btn:hover { color: var(--c-text); }
.view-btn.active {
    color: var(--c-text); font-weight: 600; box-shadow: inset 0 -2px 0 var(--c-link);
}
.view-intro {
    color: var(--c-muted); line-height: 1.55; margin-top: 18px; max-width: 620px;
}
.empty { color: var(--c-faint); font-style: italic; padding: 1rem 0; }

/* --- overviews tab --- */
.ov-section-head {
    font-size: 15px; font-weight: 600; color: var(--c-muted);
    margin-top: 32px; padding-bottom: 8px;
}
.ov-sweep .ov-section-head { margin-top: 40px; }
.ov-list { border-top: 1px solid var(--c-border); }
.ov-card { border-bottom: 1px solid var(--c-border); display: block; }
.ov-card > summary, .ov-card-link, .ov-subgroup > summary, .sweep-row {
    display: flex; align-items: baseline; gap: 12px;
    padding: 12px 10px; margin: 0 -10px; border-radius: 8px;
    cursor: pointer; list-style: none; color: var(--c-text); text-decoration: none;
}
.ov-card > summary::-webkit-details-marker,
.ov-subgroup > summary::-webkit-details-marker { display: none; }
.ov-card > summary:hover, .ov-card-link:hover, .ov-subgroup > summary:hover,
.sweep-row:hover { background: var(--c-hover); text-decoration: none; }
.ov-cat-name, .sweep-name { font-weight: 600; flex: 0 0 180px; }
.ov-card > summary:hover .ov-cat-name, .ov-card-link:hover .ov-cat-name,
.sweep-row:hover .sweep-name { color: var(--c-link); }
.ov-cat-meta, .sweep-meta {
    flex-grow: 1; color: var(--c-muted); font-size: 14px;
    font-variant-numeric: tabular-nums;
}
.ov-arrow { color: var(--c-muted); transition: transform 0.15s; flex-shrink: 0; }
svg.ov-arrow { align-self: center; }
.ov-card[open] > summary .ov-arrow,
.ov-subgroup[open] > summary .ov-arrow { transform: rotate(180deg); }
.ov-sublist { display: flex; flex-direction: column; padding: 0 0 10px; }
.ov-sub {
    display: flex; align-items: baseline; gap: 12px;
    padding: 6px 10px 6px 30px; margin: 0 -10px; border-radius: 8px;
    color: var(--c-link); text-decoration: none;
}
.ov-sub:hover { background: var(--c-hover); text-decoration: none; }
.ov-sub-name { flex: 0 0 240px; font-size: 14px; }
.ov-sub-meta { font-size: 13px; color: var(--c-muted); font-variant-numeric: tabular-nums; }
.ov-subgroup > summary { padding: 6px 10px 6px 30px; }
.ov-subgroup > summary .ov-sub-name { color: var(--c-text); font-weight: 600; }
.ov-subgroup > summary .ov-arrow { margin-left: auto; }
.ov-sublist-nested { padding: 0 0 4px; }
.ov-sublist-nested .ov-sub { padding-left: 50px; }
.ov-sublist-nested .ov-sub-name { flex-basis: 220px; }
.ov-draft {
    font-size: 11px; color: var(--c-muted); border: 1px solid var(--c-border);
    border-radius: 99px; padding: 0 6px; margin-left: 6px; vertical-align: 1px;
}
.explore-cov { font-variant-numeric: tabular-nums; }

/* --- pills + dropdowns (Category / Tags / Sort / Country) --- */
.search {
    display: block; width: 100%; height: 44px; padding: 0 14px; margin-top: 20px;
    font: inherit; font-size: 15px; color: var(--c-text); background: var(--c-bg);
    border: 1px solid var(--c-border); border-radius: 8px; outline: none;
}
.search:focus { border-color: var(--c-link); }
.search::placeholder { color: var(--c-faint2); }
.control-bar {
    display: flex; align-items: center; gap: 8px; flex-wrap: wrap; margin-top: 12px;
}
.control-bar .sp { flex-grow: 1; }
.count-line { font-size: 13px; color: var(--c-muted); font-variant-numeric: tabular-nums; }
.dropdown-wrap { position: relative; display: inline-block; }
.dropdown-btn {
    font: inherit; font-size: 14px; color: var(--c-text); background: none;
    border: 1px solid var(--c-border); border-radius: 99px; padding: 5px 13px;
    cursor: pointer; white-space: nowrap; line-height: 1.4;
}
.dropdown-btn::after { content: ' \\25BE'; color: var(--c-muted); }
.dropdown-btn:hover { border-color: var(--c-link); }
.dropdown-btn.active {
    background: var(--c-selbg); color: var(--c-link); border-color: var(--c-selline);
}
.dropdown-panel {
    display: none; position: absolute; top: 100%; left: 0; margin-top: 0.35rem;
    background: var(--c-bg); border: 1px solid var(--c-border); border-radius: 10px;
    min-width: 240px; z-index: 100; box-shadow: 0 8px 24px rgba(0,0,0,0.14);
    overflow: hidden;
}
.dropdown-panel.right { left: auto; right: 0; min-width: 190px; }
.dropdown-panel.open { display: block; }
.dropdown-search {
    width: 100%; padding: 0.5rem 0.7rem; font: inherit; font-size: 14px;
    background: var(--c-bg); color: var(--c-text); border: none;
    border-bottom: 1px solid var(--c-border); outline: none;
}
.dropdown-search::placeholder { color: var(--c-faint2); }
.dropdown-list { max-height: 280px; overflow-y: auto; list-style: none; padding: 0.25rem 0; }
.dropdown-list label {
    display: flex; align-items: center; gap: 0.45rem; padding: 0.3rem 0.7rem;
    font-size: 14px; color: var(--c-text); cursor: pointer;
}
.dropdown-list label:hover { background: var(--c-hover); }
.dropdown-list label.cat-header { font-weight: 600; padding-top: 0.45rem; }
.dropdown-list label.sub-item { padding-left: 1.6rem; }
.dropdown-list label.sub-sub-item { padding-left: 3.2rem; }
.dropdown-list input[type="checkbox"] { accent-color: var(--c-link); flex-shrink: 0; }
.dropdown-list .item-count {
    color: var(--c-muted); margin-left: auto; font-size: 13px;
    font-variant-numeric: tabular-nums;
}
.menu-item, .filter-btn {
    display: flex; justify-content: space-between; gap: 1rem; width: 100%;
    text-align: left; font: inherit; font-size: 14px; color: var(--c-text);
    background: none; border: none; padding: 0.35rem 0.8rem; cursor: pointer;
}
.menu-item:hover, .filter-btn:hover { background: var(--c-hover); }
.menu-item.active, .filter-btn.active { color: var(--c-link); font-weight: 600; }
.menu-item .n { color: var(--c-muted); font-weight: 400; font-variant-numeric: tabular-nums; }
.menu-head {
    font-size: 12px; font-weight: 600; color: var(--c-muted);
    padding: 0.5rem 0.8rem 0.15rem;
}

/* --- pages tab: sortable table --- */
.guide-table { width: 100%; border-collapse: collapse; margin-top: 14px; table-layout: fixed; }
.guide-table th.c-cat { width: 190px; }
.guide-table th.c-year { width: 92px; }
.guide-table th.c-place { width: 150px; }
.guide-table th.c-topics { width: 64px; }
.guide-table th {
    font-weight: 500; font-size: 13px; color: var(--c-muted); text-align: left;
    padding: 8px 10px 8px 0; border-bottom: 1px solid var(--c-text);
    cursor: pointer; user-select: none; white-space: nowrap;
}
.guide-table th:hover, .guide-table th.sorted { color: var(--c-text); }
.guide-table th .arr { margin-left: 3px; }
.guide-table td {
    padding: 9px 10px 9px 0; border-bottom: 1px solid var(--c-border);
    font-size: 14px; vertical-align: baseline;
}
.guide-table th:last-child, .guide-table td:last-child { padding-right: 4px; }
.guide-table .num { text-align: right; font-variant-numeric: tabular-nums; white-space: nowrap; }
.guide-table td.c-cat, .guide-table td.c-place { color: var(--c-muted); }
.guide-item { cursor: pointer; }
.guide-item:hover td { background: var(--c-hover); }
.g-name { font-weight: 600; }
.g-mmeta { display: none; }
.guide-tags {
    margin-top: 1px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
    font-size: 12px; color: var(--c-faint);
}
.guide-tag { color: var(--c-muted); cursor: pointer; margin-right: 0.7rem; }
.guide-tag:hover { color: var(--c-link); text-decoration: underline; }
.guide-tag.active { color: var(--c-link); font-weight: 600; }

/* --- location tab: continent list + timeline --- */
.loc-split { display: flex; gap: 40px; margin-top: 24px; align-items: flex-start; }
.loc-side { flex: 0 0 230px; display: flex; flex-direction: column; font-size: 14px; }
.loc-item, .loc-ctry, .loc-more {
    display: flex; justify-content: space-between; gap: 0.6rem; width: 100%;
    text-align: left; font: inherit; background: none; border: none; cursor: pointer;
    border-radius: 8px;
}
.loc-item { padding: 7px 10px; font-size: 14px; color: var(--c-text); }
.loc-item .n, .loc-ctry .n { color: var(--c-muted); font-weight: 400; font-variant-numeric: tabular-nums; }
.loc-item:hover, .loc-ctry:hover { background: var(--c-hover); }
.loc-item.active { background: var(--c-hover); font-weight: 600; }
.loc-countries {
    display: flex; flex-direction: column; padding: 2px 0 8px 18px;
    border-bottom: 1px solid var(--c-border); margin-bottom: 4px;
}
.loc-ctry { padding: 3px 10px; font-size: 13.5px; color: var(--c-muted); }
.loc-ctry.active { background: var(--c-hover); color: var(--c-text); font-weight: 600; }
.loc-more { padding: 3px 10px; font-size: 13px; color: var(--c-link); }
.loc-more:hover { text-decoration: underline; }
.loc-mtabs, .loc-mctry { display: none; }
.map-timeline { flex: 1 1 420px; min-width: 0; }
.timeline-header {
    display: flex; align-items: baseline; gap: 12px;
    padding-bottom: 8px; border-bottom: 1px solid var(--c-text);
}
.timeline-header h2 { font-size: 17px; font-weight: 600; color: var(--c-bright); }
.timeline-sub { margin-left: auto; font-size: 13px; color: var(--c-muted); text-align: right; }
.timeline-close {
    font: inherit; font-size: 13px; color: var(--c-link); background: none;
    border: none; cursor: pointer; padding: 0; white-space: nowrap;
}
.timeline-close:hover { text-decoration: underline; }
.tl-row { border-bottom: 1px solid var(--c-border); }
.timeline-entry {
    display: grid; grid-template-columns: 82px minmax(0, 1fr) auto; gap: 0 12px;
    align-items: baseline; padding: 8px 10px; margin: 0 -10px;
    border-radius: 8px; font-size: 14px;
}
.timeline-entry:hover { background: var(--c-hover); }
.timeline-year { color: var(--c-muted); text-align: right; font-variant-numeric: tabular-nums; white-space: nowrap; }
.timeline-link { font-weight: 600; }
.timeline-link:hover { text-decoration: underline; }
.timeline-cat { color: var(--c-muted); font-size: 13px; text-align: right; }
MOBILE_CSS
/* --- mobile --- */
html[data-layout="mobile"] body { padding-top: 16px; padding-bottom: 48px; }
html[data-layout="mobile"] h1 { font-size: 24px; margin-top: 22px; }
html[data-layout="mobile"] .nav-btn { min-height: 34px; padding: 4px; border-color: transparent; }
html[data-layout="mobile"] .nav-random { display: inline-flex; align-items: center; }
html[data-layout="mobile"] .site-nav { gap: 0.3rem 0.7rem; }
html[data-layout="mobile"] #dev-menu, html[data-layout="mobile"] .nav-random { margin-left: -0.3rem; }
html[data-layout="mobile"] .control-bar .sp { display: none; }
html[data-layout="mobile"] #sort-wrap { order: 2; }
html[data-layout="mobile"] .count-line { order: 3; margin-left: auto; }
html[data-layout="mobile"] .view-btn { min-height: 36px; }
html[data-layout="mobile"] .queue-cols { flex-direction: column; gap: 0.8rem; }
html[data-layout="mobile"] .ov-cat-name, html[data-layout="mobile"] .sweep-name { flex-basis: 130px; }
html[data-layout="mobile"] .ov-sub { flex-direction: column; gap: 0; padding-left: 22px; }
html[data-layout="mobile"] .ov-sublist-nested .ov-sub { padding-left: 38px; }
html[data-layout="mobile"] .ov-subgroup > summary { padding-left: 22px; }
html[data-layout="mobile"] .ov-sub-name { flex-basis: auto; }
html[data-layout="mobile"] .dropdown-btn { min-height: 36px; }
/* category / tag / sort / country panels become fixed centered sheets */
html[data-layout="mobile"] .dropdown-panel {
    position: fixed; left: 0.6rem; right: 0.6rem; top: 18vh;
    min-width: 0; max-height: 60vh; overflow-y: auto; z-index: 250;
}
html[data-layout="mobile"] .menu-item,
html[data-layout="mobile"] .filter-btn { padding: 0.6rem 0.9rem; }
/* pages table -> two-line rows */
html[data-layout="mobile"] .guide-table thead { display: none; }
html[data-layout="mobile"] .guide-table { margin-top: 10px; border-top: 1px solid var(--c-text); table-layout: auto; }
html[data-layout="mobile"] .guide-table, html[data-layout="mobile"] .guide-table tbody { display: block; }
html[data-layout="mobile"] .guide-table tr {
    display: grid; grid-template-columns: minmax(0, 1fr) auto; gap: 0 10px;
    align-items: baseline; padding: 10px 0; border-bottom: 1px solid var(--c-border);
}
html[data-layout="mobile"] .guide-table td { display: block; padding: 0; border: none; }
html[data-layout="mobile"] .guide-table td.c-cat,
html[data-layout="mobile"] .guide-table td.c-place,
html[data-layout="mobile"] .guide-table td.c-topics { display: none; }
html[data-layout="mobile"] .guide-table td.c-year { font-size: 13px; color: var(--c-muted); }
html[data-layout="mobile"] .guide-table td.empty { grid-column: 1 / -1; padding: 0.5rem 0; }
html[data-layout="mobile"] .g-mmeta { display: block; font-size: 13px; color: var(--c-muted); }
html[data-layout="mobile"] .guide-item:hover td { background: none; }
/* location: continents as a scrolling tab row + Country pill */
html[data-layout="mobile"] .loc-side { display: none; }
html[data-layout="mobile"] .loc-split { margin-top: 18px; }
html[data-layout="mobile"] .loc-mtabs {
    display: flex; gap: 20px; overflow-x: auto; margin: 16px -0.9rem 0;
    padding: 0 0.9rem; border-bottom: 1px solid var(--c-border); scrollbar-width: none;
}
html[data-layout="mobile"] .loc-mtabs::-webkit-scrollbar { display: none; }
html[data-layout="mobile"] .loc-mtabs .view-btn { font-size: 14px; white-space: nowrap; flex-shrink: 0; }
.loc-mtabs .view-btn .n { font-weight: 400; color: var(--c-muted); font-size: 13px; margin-left: 4px; }
html[data-layout="mobile"] .loc-mctry { display: flex; gap: 8px; margin-top: 12px; }
html[data-layout="mobile"] .timeline-entry { grid-template-columns: 72px minmax(0, 1fr); }
html[data-layout="mobile"] .timeline-cat { grid-column: 2; text-align: left; }
html[data-layout="mobile"] .timeline-header { flex-wrap: wrap; }
</style>
</head>
<body>
NAV_MARKUP
<div id="queue-panel">
  <div class="queue-cols">
    <div>
      <h3>First pass (FIRST_COUNT)</h3>
      <ul>FIRST_PASS_LIST</ul>
    </div>
    <div>
      <h3>Second pass (SECOND_COUNT)</h3>
      <ul>SECOND_PASS_LIST</ul>
    </div>
    <div>
      <h3>Redo first pass (REDO_COUNT)</h3>
      <ul>REDO_PASS_LIST</ul>
    </div>
  </div>
</div>
<h1>Wiki</h1>
<div class="view-toggle" role="tablist">
    <button class="view-btn active" data-view="overviews">Overviews</button>
    <button class="view-btn" data-view="list">Pages</button>
    <button class="view-btn" data-view="location">Location</button>
</div>
<div id="overviews-view">
<p class="view-intro">Browse by category. Each overview maps a subcategory's canon (the answerlines that recur, grouped by era and school) and links to the study page for every topic that has one.</p>
OVERVIEWS_SECTION
</div>
<div id="list-view" style="display:none;">
<input class="search" type="search" placeholder="Search GUIDE_COUNT pages" aria-label="Search pages" autocomplete="off">
<div class="control-bar">
    <div class="dropdown-wrap" id="cat-wrap">
        <button class="dropdown-btn" id="cat-btn">Category: All</button>
        <div class="dropdown-panel" id="cat-panel">
            <input class="dropdown-search" id="cat-search" type="text" placeholder="Search categories...">
            <div class="dropdown-list" id="cat-list"></div>
        </div>
    </div>
    <div class="dropdown-wrap" id="tag-wrap">
        <button class="dropdown-btn" id="tag-btn">Tags: All</button>
        <div class="dropdown-panel" id="tag-panel">
            <input class="dropdown-search" id="tag-search" type="text" placeholder="Search tags...">
            <div class="dropdown-list" id="tag-list"></div>
        </div>
    </div>
    <span class="sp"></span>
    <span class="count-line"><span class="count"></span><span class="d-only"> &middot; click a column to sort</span></span>
    <div class="dropdown-wrap" id="sort-wrap">
        <button class="dropdown-btn" id="sort-btn">Sort: A&ndash;Z</button>
        <div class="dropdown-panel right" id="sort-panel">
            <div class="dropdown-list">
                <button class="filter-btn active" data-sort="alpha">A&ndash;Z</button>
                <button class="filter-btn" data-sort="year">Chronological</button>
                <button class="filter-btn" data-sort="continent">Continent</button>
                <button class="filter-btn" data-sort="created">Date added</button>
                <button class="filter-btn" data-sort="category">Category</button>
                <button class="filter-btn" data-sort="topics">Most topics</button>
            </div>
        </div>
    </div>
</div>
<table class="guide-table">
<thead><tr>
    <th data-sort="alpha">Name<span class="arr"></span></th>
    <th data-sort="category" class="c-cat">Category<span class="arr"></span></th>
    <th data-sort="year" class="num c-year">Year<span class="arr"></span></th>
    <th data-sort="continent" class="c-place">Place<span class="arr"></span></th>
    <th data-sort="topics" class="num c-topics">Topics<span class="arr"></span></th>
</tr></thead>
<tbody class="guide-list"></tbody>
</table>
</div>
<div id="continent-view" style="display:none;">
    <p class="view-intro" id="loc-intro"></p>
    <div class="loc-mtabs" id="loc-mtabs"></div>
    <div class="loc-mctry">
        <div class="dropdown-wrap" id="loc-ctry-wrap">
            <button class="dropdown-btn" id="loc-ctry-btn">Country: All</button>
            <div class="dropdown-panel" id="loc-ctry-panel">
                <div class="dropdown-list" id="loc-ctry-list"></div>
            </div>
        </div>
    </div>
    <div class="loc-split">
        <aside class="loc-side map-grid" id="map-grid"></aside>
        <div id="map-timeline" class="map-timeline">
            <div class="timeline-header">
                <h2 id="timeline-title"></h2>
                <span class="timeline-sub" id="timeline-sub"></span>
                <button class="timeline-close" onclick="closeTimeline()" title="Back to all locations">Show all</button>
            </div>
            <div id="timeline-entries" class="timeline-entries"></div>
        </div>
    </div>
</div>
<script>
const guides = GUIDE_DATA;
const list = document.querySelector('.guide-list');
const search = document.querySelector('.search');
const countEl = document.querySelector('.count');

// --- State ---
let selectedCats = new Set();     // category, subcategory, or genre strings
let selectedTags = new Set();
let activeSort = 'alpha';
let sortDir = 1;                  // 1 = natural order, -1 = reversed (column re-click)

// --- Helpers ---
const escHtml = s => String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
const categories = [...new Set(guides.map(g => g.category).filter(Boolean))].sort();
const allTags = [...new Set(guides.flatMap(g => g.tags || []))].sort();
const fmtYear = y => y ? (y < 0 ? Math.abs(y) + ' BCE' : String(y)) : '';

// Row clicks: tag chips toggle the tag filter (event delegation; inline
// onclick breaks on quotes in tag names); anywhere else opens the page.
list.addEventListener('click', e => {
    const tagEl = e.target.closest('.guide-tag');
    if (tagEl) {
        e.preventDefault();
        e.stopPropagation();
        const t = tagEl.dataset.tag;
        if (selectedTags.has(t)) selectedTags.delete(t); else selectedTags.add(t);
        updateTagBtn();
        buildTagList('');
        update();
        return;
    }
    if (e.target.closest('a')) return;
    const row = e.target.closest('tr[data-href]');
    if (row) window.location.href = row.dataset.href;
});

function setupDropdown(wrapId, btnId, panelId, searchId) {
    const wrap = document.getElementById(wrapId);
    const btn = document.getElementById(btnId);
    const panel = document.getElementById(panelId);
    const searchInput = searchId ? document.getElementById(searchId) : null;
    btn.onclick = (e) => {
        e.stopPropagation();
        // close other panels
        document.querySelectorAll('.dropdown-panel.open').forEach(p => {
            if (p !== panel) p.classList.remove('open');
        });
        panel.classList.toggle('open');
        if (searchInput && panel.classList.contains('open')) {
            searchInput.value = '';
            setTimeout(() => searchInput.focus(), 0);
        }
    };
    if (searchInput) searchInput.addEventListener('click', e => e.stopPropagation());
    return { wrap, btn, panel, searchInput };
}

const catDD = setupDropdown('cat-wrap', 'cat-btn', 'cat-panel', 'cat-search');
const tagDD = setupDropdown('tag-wrap', 'tag-btn', 'tag-panel', 'tag-search');
const sortDD = setupDropdown('sort-wrap', 'sort-btn', 'sort-panel', null);
const ctryDD = setupDropdown('loc-ctry-wrap', 'loc-ctry-btn', 'loc-ctry-panel', null);

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
        const genreMatches = subcats.some(sub =>
            [...new Set(guides.filter(g => g.category === cat && g.subcategory === sub).map(g => g.genre).filter(Boolean))]
                .some(gn => gn.toLowerCase().includes(q)));
        if (!catMatches && !subMatches && !genreMatches) return;

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
                subcats.forEach(s => {
                    selectedCats.add(s);
                    const genres = [...new Set(guides.filter(g => g.category === cat && g.subcategory === s).map(g => g.genre).filter(Boolean))];
                    genres.forEach(gn => selectedCats.add(gn));
                });
            } else {
                selectedCats.delete(cat);
                subcats.forEach(s => {
                    selectedCats.delete(s);
                    const genres = [...new Set(guides.filter(g => g.category === cat && g.subcategory === s).map(g => g.genre).filter(Boolean))];
                    genres.forEach(gn => selectedCats.delete(gn));
                });
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
                if (q && !sub.toLowerCase().includes(q) && !catMatches && !genreMatches) return;
                const genres = [...new Set(guides.filter(g => g.category === cat && g.subcategory === sub).map(g => g.genre).filter(Boolean))].sort();
                const subCount = guides.filter(g => g.subcategory === sub).length;
                const subLabel = document.createElement('label');
                subLabel.className = 'sub-item';
                const subCb = document.createElement('input');
                subCb.type = 'checkbox';
                subCb.checked = selectedCats.has(sub);
                subCb.onchange = () => {
                    if (subCb.checked) {
                        selectedCats.add(sub);
                        genres.forEach(gn => selectedCats.add(gn));
                    } else {
                        selectedCats.delete(sub);
                        selectedCats.delete(cat);
                        genres.forEach(gn => selectedCats.delete(gn));
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
                sspan.appendChild(document.createTextNode(''));
                subLabel.appendChild(sspan);
                el.appendChild(subLabel);

                // Genres (third level) under this subcategory
                if (genres.length > 0) {
                    genres.forEach(gn => {
                        if (q && !gn.toLowerCase().includes(q) && !catMatches && !sub.toLowerCase().includes(q)) return;
                        const gnCount = guides.filter(g => g.genre === gn).length;
                        const gnLabel = document.createElement('label');
                        gnLabel.className = 'sub-sub-item';
                        const gnCb = document.createElement('input');
                        gnCb.type = 'checkbox';
                        gnCb.checked = selectedCats.has(gn);
                        gnCb.onchange = () => {
                            if (gnCb.checked) {
                                selectedCats.add(gn);
                            } else {
                                selectedCats.delete(gn);
                                selectedCats.delete(sub);
                                selectedCats.delete(cat);
                            }
                            updateCatBtn();
                            buildCatList(filter);
                            buildTagList(document.getElementById('tag-search').value);
                            update();
                        };
                        gnLabel.appendChild(gnCb);
                        gnLabel.appendChild(document.createTextNode(gn));
                        const gnspan = document.createElement('span');
                        gnspan.className = 'item-count';
                        gnspan.textContent = gnCount;
                        gnLabel.appendChild(gnspan);
                        el.appendChild(gnLabel);
                    });
                }
            });
        }
    });
}

function updateCatBtn() {
    if (selectedCats.size === 0) {
        catDD.btn.textContent = 'Category: All';
        catDD.btn.classList.remove('active');
    } else {
        catDD.btn.textContent = 'Category: ' + selectedCats.size + ' selected';
        catDD.btn.classList.add('active');
    }
}

catDD.searchInput.addEventListener('input', e => buildCatList(e.target.value));
buildCatList('');

// --- Tag dropdown (checkboxes, flat but context-aware) ---
function getVisibleGuides() {
    if (selectedCats.size === 0) return guides;
    return guides.filter(g => selectedCats.has(g.category) || selectedCats.has(g.subcategory) || selectedCats.has(g.genre));
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
        tagDD.btn.textContent = 'Tags: All';
        tagDD.btn.classList.remove('active');
    } else {
        tagDD.btn.textContent = 'Tags: ' + selectedTags.size + ' selected';
        tagDD.btn.classList.add('active');
    }
}

tagDD.searchInput.addEventListener('input', e => buildTagList(e.target.value));
buildTagList('');

// --- Helpers ---
function normalize(s) {
    return s.normalize('NFD').replace(/[\\u0300-\\u036f]/g, '').toLowerCase();
}

// --- Render ---
function render() {
    const q = normalize(search.value || '');
    let filtered = guides.filter(g => {
        const matchesText = normalize(g.name).includes(q);
        const matchesCat = selectedCats.size === 0 || selectedCats.has(g.category) || selectedCats.has(g.subcategory) || selectedCats.has(g.genre);
        const matchesTag = selectedTags.size === 0 || (g.tags && g.tags.some(t => selectedTags.has(t)));
        return matchesText && matchesCat && matchesTag;
    });
    const fn = sortFns[activeSort] || sortFns.alpha;
    filtered.sort((a, b) => {
        // Undated pages stay at the end of a chronological sort either way.
        if (activeSort === 'year' && !a.year !== !b.year) return a.year ? -1 : 1;
        return sortDir * fn(a, b);
    });
    countEl.textContent = filtered.length + ' page' + (filtered.length !== 1 ? 's' : '');
    if (filtered.length === 0) {
        list.innerHTML = '<tr><td class="empty" colspan="5">No pages found.</td></tr>';
        return;
    }
    list.innerHTML = filtered.map(g => {
        const subLabel = g.subcategory || g.category || '?';
        const place = g.country || g.continent || '';
        const placeTitle = (g.country && g.continent) ? g.continent + ' \\u00b7 ' + g.country : (g.continent || '');
        const mmeta = [subLabel, place, g.works + ' topics'].filter(Boolean).map(escHtml).join(' &middot; ');
        const tagsHtml = (g.tags || []).map(t => {
            const isActive = selectedTags.has(t);
            return `<span class="guide-tag${isActive ? ' active' : ''}" data-tag="${escHtml(t)}" title="Filter by ${escHtml(t)}">${escHtml(t)}</span>`;
        }).join('');
        return `
        <tr class="guide-item" data-href="${escHtml(g.path)}">
            <td class="c-name"><a class="g-name" href="${escHtml(g.path)}">${escHtml(g.name)}</a>
                <div class="g-mmeta">${mmeta}</div>${tagsHtml ? `<div class="guide-tags">${tagsHtml}</div>` : ''}</td>
            <td class="c-cat">${escHtml(subLabel)}</td>
            <td class="c-year num">${fmtYear(g.year)}</td>
            <td class="c-place" title="${escHtml(placeTitle)}">${escHtml(place)}</td>
            <td class="c-topics num">${escHtml(g.works)}</td>
        </tr>`;
    }).join('');
}

// --- Sorting ---
const sortFns = {
    alpha: (a, b) => a.name.localeCompare(b.name),
    year: (a, b) => (a.year || 9999) - (b.year || 9999),
    continent: (a, b) => (a.continent || 'ZZZ').localeCompare(b.continent || 'ZZZ') || a.name.localeCompare(b.name),
    created: (a, b) => b.modified.localeCompare(a.modified),
    category: (a, b) => (a.subcategory || a.category || 'ZZZ').localeCompare(b.subcategory || b.category || 'ZZZ') || a.name.localeCompare(b.name),
    topics: (a, b) => ((parseInt(b.works) || 0) - (parseInt(a.works) || 0)) || a.name.localeCompare(b.name),
};
const sortLabels = { alpha: 'A\\u2013Z', year: 'Chronological', continent: 'Continent',
    created: 'Date added', category: 'Category', topics: 'Most topics' };

function updateSortUI() {
    document.querySelectorAll('.filter-btn[data-sort]').forEach(b =>
        b.classList.toggle('active', b.dataset.sort === activeSort));
    document.querySelectorAll('.guide-table th[data-sort]').forEach(th => {
        const on = th.dataset.sort === activeSort;
        th.classList.toggle('sorted', on);
        th.querySelector('.arr').textContent = on ? (sortDir > 0 ? '\\u25BE' : '\\u25B4') : '';
    });
    sortDD.btn.textContent = 'Sort: ' + sortLabels[activeSort] + (sortDir < 0 ? ' (reversed)' : '');
}

function setSort(key, toggle) {
    if (toggle && key === activeSort) sortDir = -sortDir;
    else { activeSort = key; sortDir = 1; }
    updateSortUI();
    render();
}

document.querySelectorAll('.filter-btn[data-sort]').forEach(btn => {
    btn.addEventListener('click', () => {
        setSort(btn.dataset.sort, false);
        sortDD.panel.classList.remove('open');
    });
});
document.querySelectorAll('.guide-table th[data-sort]').forEach(th => {
    th.addEventListener('click', () => setSort(th.dataset.sort, true));
});

let currentView = 'overviews';
function isLocationActive() {
    return currentView === 'location';
}
function update() {
    render();
    if (isLocationActive()) buildLocationView();
}
search.addEventListener('input', () => update());
updateSortUI();
render();

// --- View toggle ---
document.querySelectorAll('.view-toggle .view-btn').forEach(btn => {
    btn.addEventListener('click', () => {
        document.querySelectorAll('.view-toggle .view-btn').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        currentView = btn.dataset.view;
        document.getElementById('overviews-view').style.display = currentView === 'overviews' ? '' : 'none';
        document.getElementById('list-view').style.display = currentView === 'list' ? '' : 'none';
        document.getElementById('continent-view').style.display = currentView === 'location' ? '' : 'none';
        if (currentView === 'list' && document.documentElement.dataset.layout !== 'mobile') search.focus();
        if (currentView === 'location') buildLocationView();
    });
});

// --- Location view ---
// Left: All + continents (the selected one expands to its countries);
// right: the selection's pages, oldest first. On mobile the continent list
// becomes a scrolling tab row and the countries a Country pill.
let locCont = 'All', locCountry = null, locShowAll = false;
const LOC_TOP = 8;

function getFilteredGuides() {
    const q = (search.value || '').toLowerCase();
    return guides.filter(g => {
        const matchesText = g.name.toLowerCase().includes(q);
        const matchesCat = selectedCats.size === 0 || selectedCats.has(g.category) || selectedCats.has(g.subcategory) || selectedCats.has(g.genre);
        const matchesTag = selectedTags.size === 0 || (g.tags && g.tags.some(t => selectedTags.has(t)));
        return matchesText && matchesCat && matchesTag;
    });
}

function selectLoc(cont, country) {
    if (cont !== locCont) locShowAll = false;
    locCont = cont;
    locCountry = country;
    buildLocationView();
}

function locButton(cls, label, n, active, onclick) {
    const b = document.createElement('button');
    b.className = cls + (active ? ' active' : '');
    b.innerHTML = escHtml(label) + '<span class="n">' + n + '</span>';
    b.onclick = onclick;
    return b;
}

function buildLocationView() {
    const grid = document.getElementById('map-grid');
    const mtabs = document.getElementById('loc-mtabs');
    const ctryList = document.getElementById('loc-ctry-list');
    const panel = document.getElementById('map-timeline');
    grid.innerHTML = '';
    mtabs.innerHTML = '';
    ctryList.innerHTML = '';

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

    document.getElementById('loc-intro').textContent = filtered.length + ' page'
        + (filtered.length === 1 ? '' : 's')
        + ' by where they are from. Pick a continent or country to see its pages in date order.';

    if (sortedContinents.length === 0) {
        grid.innerHTML = '<div class="empty">No pages match current filters.</div>';
        panel.style.display = 'none';
        ctryDD.btn.textContent = 'Country: All';
        return;
    }
    panel.style.display = '';

    // Drop a selection the current filters no longer contain.
    if (locCont !== 'All' && !byContinent[locCont]) { locCont = 'All'; locCountry = null; }
    if (locCountry && !(byContinent[locCont] || {})[locCountry]) locCountry = null;

    const contTotal = c => Object.values(byContinent[c]).reduce((s, arr) => s + arr.length, 0);
    const countriesOf = c => Object.entries(byContinent[c]).sort((a, b) => b[1].length - a[1].length);

    // Desktop: continent list; the selected continent expands to its countries.
    grid.appendChild(locButton('loc-item', 'All', filtered.length, locCont === 'All', () => selectLoc('All', null)));
    sortedContinents.forEach(cont => {
        grid.appendChild(locButton('loc-item', cont, contTotal(cont),
            locCont === cont && !locCountry, () => selectLoc(cont, null)));
        if (cont !== locCont) return;
        const box = document.createElement('div');
        box.className = 'loc-countries';
        const countries = countriesOf(cont);
        const shown = (locShowAll || countries.length <= LOC_TOP) ? countries
            : countries.filter(([c], i) => i < LOC_TOP || c === locCountry);
        shown.forEach(([country, cg]) => {
            box.appendChild(locButton('loc-ctry', country, cg.length, locCountry === country,
                () => selectLoc(cont, country)));
        });
        if (countries.length > LOC_TOP) {
            const more = document.createElement('button');
            more.className = 'loc-more';
            more.textContent = locShowAll ? 'Show fewer'
                : (countries.length - shown.length) + ' more countr' + (countries.length - shown.length === 1 ? 'y' : 'ies');
            more.onclick = () => { locShowAll = !locShowAll; buildLocationView(); };
            box.appendChild(more);
        }
        grid.appendChild(box);
    });

    // Mobile: continent tab row.
    const tab = (label, n, active, onclick) => locButton('view-btn', label, n, active, onclick);
    mtabs.appendChild(tab('All', filtered.length, locCont === 'All', () => selectLoc('All', null)));
    sortedContinents.forEach(cont => {
        mtabs.appendChild(tab(cont, contTotal(cont), locCont === cont, () => selectLoc(cont, null)));
    });
    const activeTab = mtabs.querySelector('.active');
    if (activeTab && activeTab.scrollIntoView && document.documentElement.dataset.layout === 'mobile') {
        mtabs.scrollLeft = Math.max(0, activeTab.offsetLeft - 16);
    }

    // Mobile: Country pill (countries of the selected continent; all
    // continents grouped when "All" is selected).
    const pick = (cont, country) => { ctryDD.panel.classList.remove('open'); selectLoc(cont, country); };
    const scope = locCont === 'All' ? sortedContinents : [locCont];
    const nCountries = scope.reduce((s, c) => s + Object.keys(byContinent[c]).length, 0);
    ctryList.appendChild(locButton('menu-item', 'All countries', nCountries, !locCountry,
        () => pick(locCont, null)));
    scope.forEach(cont => {
        if (scope.length > 1) {
            const h = document.createElement('div');
            h.className = 'menu-head';
            h.textContent = cont;
            ctryList.appendChild(h);
        }
        countriesOf(cont).forEach(([country, cg]) => {
            ctryList.appendChild(locButton('menu-item', country, cg.length,
                locCont === cont && locCountry === country, () => pick(cont, country)));
        });
    });
    ctryDD.btn.textContent = 'Country: ' + (locCountry || ('All ' + nCountries));
    ctryDD.btn.classList.toggle('active', !!locCountry);

    // Timeline for the selection.
    if (locCountry) showTimeline(locCountry, byContinent[locCont][locCountry]);
    else if (locCont === 'All') showTimeline('All', filtered);
    else showTimeline(locCont, Object.values(byContinent[locCont]).flat());
    document.querySelector('.timeline-close').style.display =
        (locCont === 'All' && !locCountry) ? 'none' : '';
}

function showTimeline(label, guideList) {
    const panel = document.getElementById('map-timeline');
    const title = document.getElementById('timeline-title');
    const entries = document.getElementById('timeline-entries');

    title.textContent = label === 'All' ? 'All locations' : label;
    document.getElementById('timeline-sub').textContent = guideList.length + ' page'
        + (guideList.length === 1 ? '' : 's') + ', oldest first';
    panel.style.display = '';

    // Sort by year
    const sorted = [...guideList].sort((a, b) => (a.year || 9999) - (b.year || 9999));

    entries.innerHTML = sorted.map(g => {
        const yearStr = g.year ? (g.year < 0 ? Math.abs(g.year) + ' BCE' : g.year) : '?';
        const catLabel = g.subcategory || g.category || '';
        const countryLabel = g.country ? (catLabel ? ' &middot; ' : '') + escHtml(g.country) : '';
        return `<div class="tl-row"><div class="timeline-entry">
            <span class="timeline-year">${yearStr}</span>
            <a href="${escHtml(g.path)}" class="timeline-link">${escHtml(g.name)}</a>
            <span class="timeline-cat">${escHtml(catLabel)}${countryLabel}</span>
        </div></div>`;
    }).join('');
}

// "Show all": clear the continent/country selection back to every location.
function closeTimeline() {
    selectLoc('All', null);
}
</script>
</body>
</html>"""




def build(analyses=None):
    by_slug = {slug: data for slug, _path, data in resolve_analyses(analyses)}
    guides = []
    for f in sorted(OUTPUT_DIR.glob("*/stock.html")):
        # Slug is the parent directory name
        slug = f.parent.name
        name = slug.replace("_", " ").title()

        works_count = "?"
        category = ""
        subcategory = ""
        genre = ""
        year = None
        continent = ""
        country = ""
        tags = []
        data = by_slug.get(slug)
        if data is not None:
            works_count = str(sum(1 for w in data.get("works", [])
                if not any(x in w.get("name", "") for x in
                ["General", "Biographical", "Other Works", "Other "])))
            category = data.get("category", "")
            subcategory = data.get("subcategory", "")
            genre = data.get("genre", "")
            year = data.get("year")
            continent = data.get("continent", "")
            country = data.get("country", "")
            tags = data.get("tags", [])
            if data.get("topic"):
                name = data["topic"]

        mtime = datetime.fromtimestamp(f.stat().st_mtime).strftime("%Y-%m-%d")
        guide = {
            "name": name,
            "path": f"output/{slug}/stock.html",
            "works": works_count,
            "category": category,
            "subcategory": subcategory,
            "genre": genre,
            "modified": mtime,
            "continent": continent,
            "country": country,
            "tags": tags,
        }
        if year is not None:
            guide["year"] = year
        guides.append(guide)

    # Queue data for index page
    def _load_queue(name):
        path = QUEUE_DIR / name
        if not path.exists():
            return []
        return json.loads(path.read_text(encoding='utf-8')).get("queue", [])

    queue_first = _load_queue("queue_first_pass.json")
    queue_second = _load_queue("queue_second_pass.json")
    queue_redo = _load_queue("queue_redo_first.json")
    first_count = len(queue_first)
    second_count = len(queue_second)
    redo_count = len(queue_redo)
    total_count = first_count + second_count + redo_count
    empty_li = '<li class="q-empty">Empty</li>'
    first_list = "".join(f'<li>{escape(item["topic"])}</li>' for item in queue_first) or empty_li

    def _second_li(item):
        slug = item.get("slug", "")
        topic = escape(item["topic"])
        if slug:
            return f'<li><a href="output/{slug}/stock.html">{topic}</a></li>'
        return f'<li>{topic}</li>'
    second_list = "".join(_second_li(item) for item in queue_second) or empty_li

    tier_colors = {"definite": "var(--c-bad)", "likely": "var(--c-warn)", "maybe": "var(--c-faint)"}
    def _redo_li(item):
        slug = item.get("slug", "")
        topic = escape(item["topic"])
        tier = item.get("tier", "maybe")
        color = tier_colors.get(tier, "var(--c-faint)")
        stats = f'{item.get("works_before","?")}w / {item.get("questions_available","?")}Q'
        badge = f'<span style="color:{color};font-size:0.72rem;margin-left:0.3rem">[{tier}]</span>'
        detail = f'<span style="color:var(--c-faint2);font-size:0.72rem;margin-left:0.3rem">({stats})</span>'
        if slug:
            return f'<li><a href="output/{slug}/stock.html">{topic}</a>{badge}{detail}</li>'
        return f'<li>{topic}{badge}{detail}</li>'
    redo_list = "".join(_redo_li(item) for item in queue_redo) or empty_li

    # Overviews view: main-category cards that open to their subcategory
    # overview pages, plus a sweep-sets block. Rendered server-side —
    # everything is known at build time and <details> gives native
    # accordion behavior with no JS.
    from lib.units import UNITS, unit_for_guide

    CATEGORY_ORDER = ['Literature', 'History', 'Science', 'Fine Arts',
                      'Social Science', 'Philosophy', 'Religion',
                      'Mythology', 'Geography']

    def _overviews_section() -> str:
        stats_path = CATEGORIES_DIR / 'stats.json'
        stats = (json.loads(stats_path.read_text(encoding='utf-8'))
                 if stats_path.exists() else {})

        # Page counts per unit, from the guides bucketed by their canonical unit.
        page_counts = {}
        for g in guides:
            u = unit_for_guide(g.get('category', ''), g.get('subcategory', ''),
                               g.get('genre', ''))
            if u:
                page_counts[u.slug] = page_counts.get(u.slug, 0) + 1

        # Group units by main category (only those with an overview page).
        by_cat = {}
        for u in UNITS:
            ov_path = CATEGORIES_DIR / u.slug / 'overview.json'
            if not ov_path.exists():
                continue
            draft = False
            try:
                draft = bool(json.loads(ov_path.read_text(encoding='utf-8'))
                             .get('draft'))
            except (OSError, json.JSONDecodeError):
                pass
            s = stats.get(u.slug, {})
            by_cat.setdefault(u.category, []).append({
                'slug': u.slug, 'title': u.title,
                'subcategory': u.subcategory, 'genre': u.genre,
                'have': s.get('have', 0), 'total': s.get('total', 0),
                'pages': page_counts.get(u.slug, 0), 'draft': draft,
            })

        def _cov(have, total):
            return f'{round(100 * have / total)}%' if total else '—'

        def _unit_row(us) -> str:
            draft = ('<span class="ov-draft" title="AI draft — pending review">'
                     'draft</span>' if us['draft'] else '')
            return (
                f'<a class="ov-sub" href="output/_categories/{us["slug"]}/overview.html">'
                f'<span class="ov-sub-name">{escape(us["title"])}{draft}</span>'
                f'<span class="ov-sub-meta">{us["pages"]} page'
                f'{"" if us["pages"] == 1 else "s"} · {_cov(us["have"], us["total"])} covered'
                f'</span></a>')

        def _umbrella_group(sub, gunits) -> str:
            # An umbrella subcategory (Other Science, Other Fine Arts) — its
            # genre units nest one level deeper, revealed on click.
            pages = sum(u['pages'] for u in gunits)
            rows = ''.join(_unit_row(u) for u in sorted(gunits, key=lambda u: u['title']))
            return (
                f'<details class="ov-subgroup">'
                f'<summary>'
                f'<span class="ov-sub-name">{escape(sub)}</span>'
                f'<span class="ov-sub-meta">{len(gunits)} areas · {pages} page'
                f'{"" if pages == 1 else "s"}</span>'
                f'{CHEVRON}</summary>'
                f'<div class="ov-sublist ov-sublist-nested">{rows}</div></details>')

        def _category_body(cat, units) -> str:
            # Group a category's units by subcategory; a subcategory with
            # several genre units (Other Science) becomes a nested group,
            # everything else is a direct row. Direct rows first, umbrellas
            # last.
            subs = {}
            for u in units:
                subs.setdefault(u['subcategory'], []).append(u)
            directs, umbrellas = [], []
            for sub, gunits in subs.items():
                if sub == cat or (len(gunits) == 1 and not gunits[0]['genre']):
                    directs.extend(gunits)          # flat rows (Biology, Social Science genres)
                else:
                    umbrellas.append((sub, gunits))  # Other Science / Other Fine Arts
            directs.sort(key=lambda u: u['title'])
            umbrellas.sort(key=lambda x: x[0])
            return (''.join(_unit_row(u) for u in directs)
                    + ''.join(_umbrella_group(sub, g) for sub, g in umbrellas))

        cards = ''
        ordered = ([c for c in CATEGORY_ORDER if c in by_cat]
                   + [c for c in by_cat if c not in CATEGORY_ORDER])
        for cat in ordered:
            units = sorted(by_cat[cat], key=lambda u: u['title'])
            n_pages = sum(u['pages'] for u in units)
            sub_label = (f'{len(units)} overviews'
                         if len(units) > 1 else '1 area')
            head = (f'<span class="ov-cat-name">{escape(cat)}</span>'
                    f'<span class="ov-cat-meta">{sub_label} · '
                    f'{n_pages} pages</span>')
            if len(units) == 1:
                u = units[0]
                cards += (
                    f'<div class="ov-card"><a class="ov-card-link" '
                    f'href="output/_categories/{u["slug"]}/overview.html">'
                    f'{head}<span class="ov-arrow" aria-hidden="true">&rarr;</span></a></div>')
            else:
                cards += (
                    f'<details class="ov-card">'
                    f'<summary>{head}{CHEVRON}</summary>'
                    f'<div class="ov-sublist">{_category_body(cat, units)}</div></details>')

        # Sweep sets block.
        sweep_html = ''
        sets_path = SETS_DIR / 'sets.json'
        if sets_path.exists():
            set_links = []
            for e in json.loads(sets_path.read_text(encoding='utf-8')):
                tot = e.get('total', 0)
                pct = f'{round(100 * e.get("linked", 0) / tot)}%' if tot else '—'
                set_links.append(
                    f'<div class="ov-card"><a class="sweep-row" href="output/_sets/{e["set_slug"]}/sweep.html">'
                    f'<span class="sweep-name">{escape(e["set_name"])}</span>'
                    f'<span class="sweep-meta"><span class="explore-cov">{pct}</span>'
                    f' of answerlines have a study page</span>'
                    f'<span class="ov-arrow" aria-hidden="true">&rarr;</span></a></div>')
            if set_links:
                sweep_html = (
                    '<div class="ov-sweep"><h2 class="ov-section-head">Tournament sweeps</h2>'
                    '<div class="ov-list">' + ''.join(set_links) + '</div></div>')

        return ('<h2 class="ov-section-head">Categories</h2>'
                f'<div class="ov-list">{cards}</div>{sweep_html}')

    # Write shared guides data file for search_nav.js
    guides_js_path = OUTPUT_DIR / "guides_data.js"
    with open(guides_js_path, "w", encoding='utf-8') as gf:
        gf.write("const GUIDES_DATA = ")
        json.dump(guides, gf, ensure_ascii=False)
        gf.write(";\n")

    html = INDEX_TEMPLATE.replace("LAYOUT_SWITCH", layout_switch_script())
    html = html.replace("MOBILE_CSS", mobile_core_css())
    html = html.replace("BASE_CSS", base_css(
        max_width='860px', body_padding='22px 24px 64px',
        type_scale=False, h1_size='28px', h1_pad='0',
        h1_margin='0', global_links=False))
    html = html.replace("NAV_CSS", site_nav_css())
    html = html.replace("NAV_MARKUP", site_nav('', 'wiki', NAV_TOOLS))
    html = html.replace("OVERVIEWS_SECTION", _overviews_section())
    html = html.replace("GUIDE_COUNT", str(len(guides)))
    html = html.replace("GUIDE_DATA", json.dumps(guides))
    html = html.replace("QUEUE_TOTAL", str(total_count))
    html = html.replace("FIRST_COUNT", str(first_count))
    html = html.replace("SECOND_COUNT", str(second_count))
    html = html.replace("REDO_COUNT", str(redo_count))
    html = html.replace("FIRST_PASS_LIST", first_list)
    html = html.replace("SECOND_PASS_LIST", second_list)
    html = html.replace("REDO_PASS_LIST", redo_list)

    out_path = ROOT / "wiki.html"
    with open(out_path, "w", encoding='utf-8') as f:
        f.write(html)

    # Summary
    cat_counts = {}
    for g in guides:
        c = g["category"] or "Unknown"
        cat_counts[c] = cat_counts.get(c, 0) + 1

    print(f"Built wiki.html with {len(guides)} guides")
    for cat, cnt in sorted(cat_counts.items()):
        print(f"  {cat}: {cnt}")



if __name__ == "__main__":
    build()
