"""render_overview.py — Render a unit overview page from overview.json.

Overview pages are the wikipedia-style survey of one category unit
(subcategory or genre): an encyclopedia intro, a TOC, curated thematic
sections whose entries are frequency-ranked answerlines with context
blurbs, and a collapsed appendix of lower-frequency answerlines.

Links resolve at render time through TopicMatcher, so entries flip from
plain text ("no page yet") to blue links automatically as topic pages are
created.

overview.json schema: see .claude/skills/overview/SKILL.md and the
category-pages plan. Renderer expects:
    {unit, title, category, subcategory, genre, intro: [str],
     freq_source: {fetched, difficulties, min_year, threshold,
                   appendix_threshold, ...},
     sections: [{name, blurb?, entries: [{topic, answerline, frequency, note,
                                          variants?: [{answerline, frequency}],
                                          works?: [entry]}]}],
     unplaced: [entry],
     appendix: [{answer, frequency}]}

Entry frequency is the merged total across answerline variants; the
variants list preserves the raw strings for refresh diffing. `works`
nests answerlines that belong under a parent topic (Leaves of Grass
under Walt Whitman) one level deep. Entries render in authored order —
frequency is a badge, not the sort key.

Entries with captured questions (output/_categories/{unit}/questions.json
refs) get an expandable panel; the panel text is fetched at view time
from unit_questions/{unit}.json on the R2 data plane (lib/js/qdata.js).
"""
import json
import sys as _sys
from html import escape
from pathlib import Path as _Path

_sys.path.insert(0, str(_Path(__file__).resolve().parent.parent.parent))
from lib.common import anchor_slug
from lib.render.theme import (LEAFLET_TAGS, base_css, layout_switch_script,
                              mobile_core_css, search_nav_css, site_nav,
                              site_nav_css)
from lib.sweep.answerlines import normalize

UNPLACED_TITLE = 'Uncategorized'

# Soundbites of the unit currently being rendered:
# normalize(answerline) -> [{label, file, url}] from soundbites.json
# (Wikimedia Commons recordings — NOT the synthesized score-clue MP3s,
# which stay on topic pages for score-identification study.)
_soundbites: dict[str, list] = {}

# Question-panel counts of the unit currently being rendered:
# normalize(answerline) -> ref count from questions.json. Buttons render
# visible with these counts; the text itself is fetched at view time
# from unit_questions/{unit}.json on R2 (lib/js/qdata.js).
_question_counts: dict[str, int] = {}


def _flatten(entries: list[dict]):
    for e in entries:
        yield e
        yield from e.get('works', [])


def _entry_html(entry: dict, matcher, category: str, nested: bool = False) -> str:
    name = entry.get('topic') or entry.get('answerline', '')
    m = matcher.match(name, category=category)
    if not m.slug:
        m = matcher.match(entry.get('answerline', ''), category=category)
    freq = entry.get('frequency', 0)
    if m.slug:
        name_html = (f'<a class="entry-name" '
                     f'href="../../{m.slug}/stock.html">{escape(name)}</a>')
    else:
        name_html = (f'<span class="entry-name no-page" '
                     f'title="No page yet">{escape(name)}</span>')
    note = entry.get('note', '')
    note_html = f' <span class="entry-note">{escape(note)}</span>' if note else ''
    qkey = normalize(entry.get('answerline', '') or name)
    n_q = _question_counts.get(qkey, 0)
    qbtn = (f' <button class="q-toggle" data-qkey="{escape(qkey)}" '
            f'style="display:none">questions</button>' if not n_q else
            f' <button class="q-toggle" data-qkey="{escape(qkey)}">'
            f'{n_q} q</button>')
    clips = _soundbites.get(qkey, [])
    clip_btn = clip_panel = ''
    if clips:
        rows = ''
        for c in clips:
            file_page = ('https://commons.wikimedia.org/wiki/'
                         + c.get('file', '').replace(' ', '_'))
            rows += (f'<div class="clip-row">'
                     f'<span class="clip-label">{escape(c.get("label", ""))}'
                     f' <a class="clip-attr" href="{escape(file_page)}" '
                     f'target="_blank" title="Wikimedia Commons">&#9432;</a></span>'
                     f'<audio controls preload="none" '
                     f'src="{escape(c["url"])}"></audio></div>')
        clip_btn = (f' <button class="clip-toggle" '
                    f'title="Play recordings">&#9834; {len(clips)}</button>')
        clip_panel = f'<div class="clip-panel" style="display:none">{rows}</div>'
    works = entry.get('works', [])
    works_html = ''
    if works:
        inner = ''.join(_entry_html(w, matcher, category, nested=True)
                        for w in works)
        works_html = f'<ul class="entry-sublist">{inner}</ul>'
    cls = 'entry sub-entry' if nested else 'entry'
    # One hairline row (frequency column + name/note/chips); the panels
    # and nested works sit beneath it inside the same <li>.
    return (f'<li class="{cls}" id="e-{escape(qkey.replace(" ", "-"))}">'
            f'<div class="entry-row">'
            f'<span class="freq-badge" title="{freq} questions">{freq}&times;</span>'
            f'<span class="entry-body">{name_html}{note_html}{qbtn}{clip_btn}</span>'
            f'</div>'
            f'<div class="q-panel" style="display:none"></div>'
            f'{clip_panel}'
            f'{works_html}</li>')


def _ranges(nums) -> str:
    """[5, 7, 8, 9, 10] -> '5, 7&ndash;10' (runs of 3+ collapse)."""
    try:
        vals = sorted({int(n) for n in nums})
    except (TypeError, ValueError):
        return ', '.join(escape(str(n)) for n in nums)
    out, i = [], 0
    while i < len(vals):
        j = i
        while j + 1 < len(vals) and vals[j + 1] == vals[j] + 1:
            j += 1
        if j - i >= 2:
            out.append(f'{vals[i]}&ndash;{vals[j]}')
        else:
            out.extend(str(v) for v in vals[i:j + 1])
        i = j + 1
    return ', '.join(out)


def _coverage(entries: list[dict], matcher, category: str) -> tuple[int, int]:
    have = total = 0
    for e in _flatten(entries):
        total += 1
        m = matcher.match(e.get('topic') or e.get('answerline', ''),
                          category=category)
        if not m.slug:
            m = matcher.match(e.get('answerline', ''), category=category)
        if m.slug:
            have += 1
    return have, total


def render_overview(overview: dict, matcher, out_path: str | _Path) -> dict:
    """Render the page and return coverage stats
    {unit, title, have, total} for index aggregation."""
    global _soundbites, _question_counts
    out_path = _Path(out_path)
    sb_path = out_path.parent / 'soundbites.json'
    _soundbites = {}
    if sb_path.exists():
        with open(sb_path, encoding='utf-8') as f:
            _soundbites = json.load(f)
    q_path = out_path.parent / 'questions.json'
    _question_counts = {}
    if q_path.exists():
        with open(q_path, encoding='utf-8') as f:
            _question_counts = {k: len(v) for k, v in json.load(f).items() if v}
    unit_slug_json = json.dumps(overview.get('unit', out_path.parent.name))
    title = escape(overview.get('title', overview.get('unit', 'Unknown')))
    category = escape(overview.get('category', ''))
    fs = overview.get('freq_source', {})

    sections = list(overview.get('sections', []))
    if overview.get('unplaced'):
        sections.append({'name': UNPLACED_TITLE, 'blurb': '',
                         'entries': overview['unplaced']})

    raw_category = overview.get('category', '')
    all_entries = [e for s in sections for e in s.get('entries', [])]
    have, total = _coverage(all_entries, matcher, raw_category)

    # Map items: every entry that resolves to a topic page. Country and
    # year are joined client-side from GUIDES_DATA; pins are grouped
    # (colored) by section and scroll to the entry on click.
    map_items = []
    for s in sections:
        for e in _flatten(s.get('entries', [])):
            name = e.get('topic') or e.get('answerline', '')
            m = matcher.match(name, category=raw_category)
            if not m.slug:
                m = matcher.match(e.get('answerline', ''),
                                  category=raw_category)
            if m.slug:
                qkey = normalize(e.get('answerline', '') or name)
                map_items.append({'name': name, 'slug': m.slug,
                                  'section': s['name'],
                                  'anchor': 'e-' + qkey.replace(' ', '-')})
    map_items_json = (json.dumps(map_items, ensure_ascii=False)
                      .replace('</', '<\\/'))

    # TOC
    def _count(s):
        return sum(1 for _ in _flatten(s.get('entries', [])))

    toc_items = ''.join(
        f'<li><a href="#{anchor_slug(s["name"])}">{escape(s["name"])}</a>'
        f'<span class="toc-count">{_count(s)}</span></li>'
        for s in sections if s.get('entries'))

    # Sections (authored order preserved — frequency is a badge only).
    # The legend line sits under the first section, where a reader first
    # meets the blue-vs-plain distinction.
    sections_html = ''
    legend_done = False
    for s in sections:
        entries = s.get('entries', [])
        if not entries:
            continue
        blurb = s.get('blurb', '')
        blurb_html = (f'<p class="section-blurb">{escape(blurb)}</p>'
                      if blurb else '')
        items = ''.join(_entry_html(e, matcher, raw_category) for e in entries)
        n = _count(s)
        legend = ''
        if not legend_done:
            legend = ('<div class="legend">Blue names have a study page; '
                      'red ones don’t yet.</div>')
            legend_done = True
        sections_html += (
            f'<section class="unit-section">'
            f'<div class="section-head">'
            f'<h2 id="{anchor_slug(s["name"])}">{escape(s["name"])}</h2>'
            f'<span class="section-count">{n} answerline{"" if n == 1 else "s"}'
            f'</span></div>'
            f'{blurb_html}<ul class="entry-list">{items}</ul>{legend}</section>')

    # Appendix (mechanical, collapsed)
    appendix = overview.get('appendix', [])
    appendix_html = ''
    if appendix:
        rows = ''
        for e in sorted(appendix, key=lambda e: -e.get('frequency', 0)):
            m = matcher.match(e.get('answer', ''), category=raw_category)
            if m.slug:
                cell = (f'<a href="../../{m.slug}/stock.html">'
                        f'{escape(e.get("answer", ""))}</a>')
            else:
                cell = f'<span class="no-page">{escape(e.get("answer", ""))}</span>'
            rows += (f'<span class="appendix-item">'
                     f'<span class="freq-badge">{e.get("frequency", 0)}&times;</span> '
                     f'{cell}</span>')
        appendix_html = (
            f'<details class="appendix"><summary>Appendix: '
            f'{len(appendix)} more answerlines '
            f'<span class="appendix-range">(frequency '
            f'{fs.get("appendix_threshold", "?")}&ndash;'
            f'{fs.get("threshold", "?")})</span></summary>'
            f'<div class="appendix-grid">{rows}</div></details>')

    # Intro: the first paragraph shows; the rest sit behind a toggle.
    intro_paras = overview.get('intro', [])
    intro_html = ''.join(f'<p>{escape(p)}</p>' for p in intro_paras[:1])
    if len(intro_paras) > 1:
        n_more = len(intro_paras) - 1
        more_label = (f'Read the full introduction ({n_more} more '
                      f'paragraph{"" if n_more == 1 else "s"})')
        intro_html += (
            '<div class="intro-more" id="intro-more" hidden>'
            + ''.join(f'<p>{escape(p)}</p>' for p in intro_paras[1:])
            + '</div>'
            f'<button class="intro-toggle linkbtn" id="intro-toggle" '
            f'aria-expanded="false" aria-controls="intro-more" '
            f'data-more="{escape(more_label)}">{escape(more_label)}</button>')
    diffs = fs.get('difficulties', [])
    diffs_str = _ranges(diffs) if diffs else 'all'
    pct = round(100 * have / total) if total else 0

    nav_html = site_nav('../../../', 'wiki', '<div class="nav-search"></div>')

    draft_html = ''
    if overview.get('draft'):
        draft_html = (
            '<div class="draft-banner"><b>AI draft.</b> '
            'Answerlines are machine-collected; notes are AI-written '
            'and unreviewed.</div>')

    html = f"""<!DOCTYPE html>
<html lang="en" data-layout="desktop">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
{layout_switch_script()}
{LEAFLET_TAGS}
<title>{title} — Overview</title>
<style>
{base_css(max_width='820px', body_padding='22px 24px 64px', h1_size='28px',
          h1_pad='0', h1_margin='0')}
{site_nav_css()}
.breadcrumb {{
    font-size: 14px;
    color: var(--c-muted);
    margin-top: 0.4rem;
}}
h1 {{ margin-top: 2px; }}
.coverage-bar {{
    display: flex;
    gap: 6px 18px;
    flex-wrap: wrap;
    align-items: baseline;
    margin-top: 8px;
    font-size: 13px;
    color: var(--c-muted);
    font-variant-numeric: tabular-nums;
}}
.coverage-bar b {{ color: var(--c-text); font-weight: 600; }}
.linkbtn {{
    font: inherit;
    background: none;
    border: none;
    padding: 0;
    color: var(--c-link);
    cursor: pointer;
}}
.linkbtn:hover {{ text-decoration: underline; }}
.map-toggle {{ font-size: 13px; }}
.map-toggle.on {{ font-weight: 600; }}
.draft-banner {{
    background: var(--c-hl);
    border-radius: 8px;
    color: var(--c-text);
    font-size: 13.5px;
    padding: 0.5rem 0.8rem;
    margin: 16px 0 0;
}}
.draft-banner b {{ color: var(--c-accent); font-weight: 600; }}
.intro {{ margin-top: 20px; }}
.intro p {{
    font-size: 16px;
    line-height: 1.6;
    margin-bottom: 0.75rem;
    color: var(--c-text);
}}
.intro p:last-child, .intro > p:first-child {{ margin-bottom: 0; }}
.intro-more {{ margin-top: 0.75rem; }}
.intro-toggle {{ font-size: 14px; margin-top: 6px; }}
.map-box {{ border: 1px solid var(--c-border); border-radius: 8px 8px 0 0; margin-top: 16px; }}
.map-note {{
    color: var(--c-faint);
    font-size: 13px;
    margin: 0.4rem 0 0;
}}
.leaflet-container {{ background: var(--c-bg); font-family: inherit; }}
.leaflet-popup-content-wrapper, .leaflet-popup-tip {{
    background: var(--c-raised); color: var(--c-text);
    border: 1px solid var(--c-border);
}}
.leaflet-popup-content a {{ color: var(--c-link); text-decoration: none; }}
.toc-title {{
    margin: 32px 0 0;
    padding-bottom: 8px;
    font-size: 15px;
    font-weight: 600;
    color: var(--c-muted);
}}
.toc ol {{
    margin: 0;
    padding: 10px 0 0 22px;
    border-top: 1px solid var(--c-border);
    columns: 2 280px;
    column-gap: 32px;
    font-size: 14px;
}}
.toc li {{ padding: 2px 0; break-inside: avoid; }}
.toc li::marker {{ color: var(--c-muted); }}
.toc-count {{
    color: var(--c-muted);
    font-variant-numeric: tabular-nums;
    margin-left: 0.35rem;
}}
.unit-section {{ margin-top: 44px; }}
.section-head {{
    display: flex;
    justify-content: space-between;
    align-items: baseline;
    gap: 12px;
    padding-bottom: 10px;
    border-bottom: 1px solid var(--c-text);
}}
.section-head h2 {{
    font-size: 17px;
    font-weight: 600;
    color: var(--c-bright);
    scroll-margin-top: 1rem;
}}
.section-count {{ font-size: 13px; color: var(--c-muted); white-space: nowrap; }}
.section-blurb {{
    margin: 12px 0 8px;
    color: var(--c-muted);
    font-size: 14.5px;
    line-height: 1.5;
}}
.entry-list, .entry-sublist {{ list-style: none; margin: 0; padding: 0; }}
.entry-row {{
    display: flex;
    align-items: baseline;
    gap: 12px;
    padding: 8px 10px;
    margin: 0 -10px;
    border-top: 1px solid var(--c-border);
    border-radius: 8px;
}}
.entry-row:hover {{ background: var(--c-hover); }}
.entry-list > .entry:first-child > .entry-row {{ border-top-color: transparent; }}
.section-blurb + .entry-list > .entry:first-child > .entry-row {{ border-top-color: var(--c-border); }}
.sub-entry > .entry-row {{ padding-left: 46px; }}
.sub-entry .sub-entry > .entry-row {{ padding-left: 82px; }}
.freq-badge {{
    flex: 0 0 30px;
    text-align: right;
    color: var(--c-muted);
    font-size: 13px;
    font-variant-numeric: tabular-nums;
    white-space: nowrap;
}}
.entry-body {{ flex: 1 1 auto; min-width: 0; font-size: 14.5px; line-height: 1.5; }}
.entry-name {{ font-weight: 600; }}
a.entry-name {{ color: var(--c-link); text-decoration: none; }}
a.entry-name:hover {{ text-decoration: underline; }}
.no-page {{ color: var(--c-bad); cursor: default; }}
.entry-note {{ color: var(--c-muted); }}
.q-toggle, .clip-toggle {{
    font: inherit;
    font-size: 12px;
    color: var(--c-muted);
    background: none;
    border: none;
    border-radius: 6px;
    padding: 0 4px;
    margin-left: 4px;
    cursor: pointer;
    font-variant-numeric: tabular-nums;
    white-space: nowrap;
}}
.q-toggle:hover, .clip-toggle:hover {{ color: var(--c-link); text-decoration: underline; }}
.q-toggle.open, .clip-toggle.open {{
    color: var(--c-text); font-weight: 600;
    background: var(--c-pick);
}}
.q-panel, .clip-panel {{
    margin: 2px 0 8px 42px;
    border: 1px solid var(--c-border);
    border-radius: 8px;
    background: var(--c-raised2);
    padding: 0.4rem 0.8rem;
    font-size: 13.5px;
}}
.sub-entry > .q-panel, .sub-entry > .clip-panel {{ margin-left: 78px; }}
.q-panel {{ max-height: 320px; overflow-y: auto; }}
.q-item {{
    padding: 0.45rem 0;
    border-top: 1px solid var(--c-line2);
    line-height: 1.5;
    color: var(--c-text);
}}
.q-item:first-child {{ border-top: none; }}
.q-item-meta {{
    font-size: 12px;
    color: var(--c-faint);
    margin-bottom: 0.1rem;
}}
.q-item-meta b {{ color: var(--c-muted); font-weight: 600; }}
.qdata-error a {{ color: var(--c-link); }}
.clip-row {{
    display: flex;
    align-items: center;
    gap: 0.7rem;
    padding: 0.2rem 0;
}}
.clip-label {{
    color: var(--c-muted);
    font-size: 13px;
    min-width: 10rem;
}}
.clip-row audio {{ height: 28px; }}
.clip-attr {{
    color: var(--c-faint);
    text-decoration: none;
    font-size: 12px;
    margin-left: 0.2rem;
}}
.clip-attr:hover {{ color: var(--c-link); text-decoration: none; }}
.legend {{ margin-top: 10px; font-size: 13px; color: var(--c-muted); }}
.appendix {{ margin-top: 44px; }}
.appendix summary {{
    cursor: pointer;
    padding-bottom: 10px;
    border-bottom: 1px solid var(--c-text);
    font-size: 17px;
    font-weight: 600;
    color: var(--c-bright);
    user-select: none;
}}
.appendix-range {{ font-size: 13px; font-weight: 400; color: var(--c-muted); }}
.appendix summary:hover .appendix-range {{ color: var(--c-text); }}
.appendix-grid {{
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(240px, 1fr));
    gap: 0.15rem 1rem;
    padding: 0.7rem 0 0;
    font-size: 13.5px;
}}
.appendix-item {{ white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }}
.appendix-item .freq-badge {{ display: inline-block; min-width: 30px; margin-right: 0.3rem; }}
.appendix-item a {{ color: var(--c-link); text-decoration: none; }}
.appendix-item a:hover {{ text-decoration: underline; }}
{search_nav_css()}
{mobile_core_css()}
html[data-layout="mobile"] body {{ padding-top: 16px; }}
html[data-layout="mobile"] h1 {{ font-size: 24px; }}
html[data-layout="mobile"] .sub-entry > .entry-row {{ padding-left: 28px; }}
html[data-layout="mobile"] .sub-entry .sub-entry > .entry-row {{ padding-left: 46px; }}
html[data-layout="mobile"] .q-panel, html[data-layout="mobile"] .clip-panel,
html[data-layout="mobile"] .sub-entry > .q-panel,
html[data-layout="mobile"] .sub-entry > .clip-panel {{ margin-left: 0; }}
html[data-layout="mobile"] .q-toggle, html[data-layout="mobile"] .clip-toggle {{
    font-size: 13px; padding: 0.2rem 0.5rem; min-height: 32px;
    border: 1px solid var(--c-border); margin-top: 2px;
}}
html[data-layout="mobile"] .linkbtn {{ min-height: 0; padding: 0.35rem 0; }}
html[data-layout="mobile"] .clip-label {{ min-width: 0; }}
html[data-layout="mobile"] .clip-row {{ flex-wrap: wrap; }}
html[data-layout="mobile"] .search-nav-dropdown {{
    min-width: 0; width: min(320px, calc(100vw - 1.5rem));
}}
</style>
</head>
<body>
{nav_html}
<div class="breadcrumb">{category}</div>
<h1>{title}</h1>
<div class="coverage-bar">
<span><b>{total:,}</b> core answerlines (frequency &ge; {fs.get('threshold', '?')})</span>
<span><b>{have:,}</b> with study pages ({pct}%)</span>
<span>difficulties {diffs_str} &middot; {fs.get('min_year', '?')}&ndash;present</span>
<span>frequency data {escape(str(fs.get('fetched', '?')))}</span>
<button class="map-toggle linkbtn" id="map-toggle" aria-expanded="false">Map</button>
</div>
{draft_html}
<div id="map-wrap" style="display:none">
    <div class="map-box" id="map-box"></div>
    <div class="map-note" id="map-note"></div>
</div>
<div class="intro">{intro_html}</div>
<nav class="toc">
<h2 class="toc-title">Contents</h2>
<ol>{toc_items}</ol>
</nav>
{sections_html}
{appendix_html}
<script src="../../guides_data.js"></script>
<script src="../../../lib/js/search_nav.js"></script>
<script src="../../../lib/js/map_view.js"></script>
<script>initSearchNav('.nav-search', {{ prefix: '../../../' }});</script>
<script>
// Intro: first paragraph visible, the rest behind a toggle.
(function () {{
    const btn = document.getElementById('intro-toggle');
    const more = document.getElementById('intro-more');
    if (!btn || !more) return;
    btn.addEventListener('click', () => {{
        const open = more.hidden;
        more.hidden = !open;
        btn.setAttribute('aria-expanded', String(open));
        btn.textContent = open ? 'Show less' : btn.dataset.more;
    }});
}})();
</script>
<script>
const MAP_ITEMS = {map_items_json};
let mapCtl = null;
document.getElementById('map-toggle').addEventListener('click', function () {{
    const wrap = document.getElementById('map-wrap');
    const show = wrap.style.display === 'none';
    wrap.style.display = show ? '' : 'none';
    this.classList.toggle('on', show);
    this.setAttribute('aria-expanded', String(show));
    this.textContent = show ? 'Hide map' : 'Map';
    if (show && !mapCtl) {{
        const items = MAP_ITEMS.map(it => ({{
            name: it.name,
            country: guideCountry(it.slug),
            year: guideYear(it.slug),
            group: it.section,
            anchor: it.anchor,
        }}));
        mapCtl = initMapView(document.getElementById('map-box'), items, {{
            onUnlocated: (u) => {{
                document.getElementById('map-note').textContent =
                    u.length ? `${{u.length}} topics have no location metadata` : '';
            }},
        }});
    }} else if (show && mapCtl) {{
        setTimeout(() => mapCtl.map.invalidateSize(), 0);
    }}
}});
</script>
<script>
// Soundbite panels (Wikimedia Commons recordings from soundbites.json).
// Each entry's own panels are direct children of its <li>.
document.querySelectorAll('.clip-toggle').forEach(btn => {{
    const panel = btn.closest('.entry').querySelector(':scope > .clip-panel');
    if (!panel) return;
    btn.addEventListener('click', () => {{
        const open = panel.style.display !== 'none';
        panel.style.display = open ? 'none' : '';
        btn.classList.toggle('open', !open);
    }});
}});
</script>
<script src="../../../lib/js/qdata.js"></script>
<script>
// Question panels: buttons carry build-time ref counts; the text is
// fetched once per page from the unit's R2 artifact on first open.
const UNIT_SLUG = {unit_slug_json};
{{
    const escQ = s => String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
    const panelBody = qs => qs.map(q => `
                    <div class="q-item">
                        <div class="q-item-meta"><b>${{escQ(q.set)}}</b> · ${{q.type}} · diff ${{q.diff}}</div>
                        ${{escQ(q.text)}}
                    </div>`).join('');
    document.querySelectorAll('.q-toggle').forEach(btn => {{
        if (btn.style.display === 'none') return;
        const panel = btn.closest('.entry').querySelector(':scope > .q-panel');
        btn.addEventListener('click', () => {{
            const open = panel.style.display !== 'none';
            panel.style.display = open ? 'none' : '';
            btn.classList.toggle('open', !open);
            if (!open && !panel.innerHTML) {{
                panel.innerHTML = '<div class="q-item">Loading…</div>';
                qdataFetch('unit_questions/' + UNIT_SLUG + '.json').then(data => {{
                    const qs = data[btn.dataset.qkey];
                    panel.innerHTML = (qs && qs.length) ? panelBody(qs)
                        : '<div class="q-item">No questions available.</div>';
                    if (qs && qs.length) btn.textContent = qs.length + ' q';
                }}).catch(err => {{
                    panel.innerHTML = '';
                    panel.appendChild(Object.assign(document.createElement('div'),
                        {{className: 'q-item', innerHTML: qdataErrorHtml(err)}}));
                }});
            }}
        }});
    }});
}}
</script>
</body>
</html>"""

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(html, encoding='utf-8')
    return {'unit': overview.get('unit', out_path.parent.name),
            'title': overview.get('title', ''), 'have': have, 'total': total}
