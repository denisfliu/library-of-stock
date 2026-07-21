"""render_overview.py — Render a unit overview page from overview.json.

Overview pages are the wikipedia-style survey of one category unit
(subcategory or genre): an encyclopedia intro, a TOC, curated thematic
sections whose entries are frequency-ranked answerlines with context
blurbs, and a collapsed appendix of lower-frequency answerlines.

Links resolve at render time through TopicMatcher, so entries flip from
red ("no page yet") to blue automatically as topic pages are created.

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
                              mobile_core_css, nav_bar_css, search_nav_css)
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
    return (f'<li class="{cls}" id="e-{escape(qkey.replace(" ", "-"))}">'
            f'<span class="freq-badge" title="{freq} questions">{freq}&times;</span> '
            f'{name_html}{note_html}{qbtn}{clip_btn}'
            f'<div class="q-panel" style="display:none"></div>'
            f'{clip_panel}'
            f'{works_html}</li>')


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
    toc_items = ''.join(
        f'<li><a href="#{anchor_slug(s["name"])}">{escape(s["name"])}</a>'
        f'<span class="toc-count">{sum(1 for _ in _flatten(s.get("entries", [])))}</span></li>'
        for s in sections if s.get('entries'))

    # Sections (authored order preserved — frequency is a badge only)
    sections_html = ''
    for s in sections:
        entries = s.get('entries', [])
        if not entries:
            continue
        blurb = s.get('blurb', '')
        blurb_html = (f'<p class="section-blurb">{escape(blurb)}</p>'
                      if blurb else '')
        items = ''.join(_entry_html(e, matcher, raw_category) for e in entries)
        sections_html += (
            f'<section class="unit-section">'
            f'<h2 id="{anchor_slug(s["name"])}">{escape(s["name"])}</h2>'
            f'{blurb_html}<ul class="entry-list">{items}</ul></section>')

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
            f'(frequency {fs.get("appendix_threshold", "?")}&ndash;'
            f'{fs.get("threshold", "?")})</summary>'
            f'<div class="appendix-grid">{rows}</div></details>')

    intro_html = ''.join(f'<p>{escape(p)}</p>' for p in overview.get('intro', []))
    diffs = fs.get('difficulties', [])
    diffs_str = ','.join(str(d) for d in diffs) if diffs else 'all'
    pct = round(100 * have / total) if total else 0

    nav_html = (
        '<div class="nav-bar">'
        '<div class="nav-links">'
        '<a href="../../../wiki.html" class="nav-home">&larr; Wiki</a>'
        '</div>'
        '<div class="nav-search"></div>'
        '</div>')

    draft_html = ''
    if overview.get('draft'):
        draft_html = (
            '<div class="draft-banner">&#9888;&#65039; <b>AI draft</b>. '
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
{base_css(max_width='860px')}
.breadcrumb {{
    font-size: 0.8rem;
    color: #808790;
    margin-bottom: 0.2rem;
}}
.intro p {{
    font-size: 0.95rem;
    line-height: 1.65;
    margin-bottom: 0.7rem;
    color: #c8ccd1;
}}
.draft-banner {{
    background: #2a2410;
    border: 1px solid #8a6a2f;
    border-radius: 4px;
    color: #e8b04a;
    font-size: 0.85rem;
    padding: 0.5rem 0.9rem;
    margin: 0.7rem 0;
}}
.draft-banner b {{ color: #f0c46a; }}
.coverage-bar {{
    background: #1a1f25;
    border: 1px solid #3a3f47;
    padding: 0.5rem 0.9rem;
    margin: 0.9rem 0;
    font-size: 0.82rem;
    color: #9aa0a7;
    display: flex;
    gap: 1.2rem;
    flex-wrap: wrap;
}}
.coverage-bar b {{ color: #e0e0e0; }}
.toc {{
    display: inline-block;
    background: #1a1f25;
    border: 1px solid #3a3f47;
    padding: 0.6rem 1rem;
    margin-bottom: 1.2rem;
    font-size: 0.88rem;
}}
.toc-title {{
    font-weight: bold;
    color: #e0e0e0;
    margin-bottom: 0.3rem;
}}
.toc ol {{ margin-left: 1.4rem; }}
.toc li {{ margin-bottom: 0.1rem; }}
.toc-count {{
    color: #808790;
    font-size: 0.75rem;
    margin-left: 0.4rem;
}}
.unit-section h2 {{
    font-family: 'Linux Libertine', Georgia, serif;
    font-size: 1.35rem;
    font-weight: normal;
    border-bottom: 1px solid #3a3f47;
    padding-bottom: 0.15rem;
    margin: 1.4rem 0 0.5rem;
    color: #e0e0e0;
}}
.section-blurb {{
    font-size: 0.88rem;
    color: #9aa0a7;
    font-style: italic;
    margin-bottom: 0.5rem;
    line-height: 1.5;
}}
.entry-sublist {{
    list-style: none;
    margin: 0.1rem 0 0.15rem 2.6rem;
    border-left: 1px solid #2a2f37;
    padding-left: 0.7rem;
}}
.sub-entry {{
    border-top: none !important;
    padding: 0.12rem 0;
    font-size: 0.85rem;
}}
.q-toggle {{
    background: none;
    border: 1px solid #2a2f37;
    border-radius: 3px;
    color: #808790;
    font-size: 0.68rem;
    padding: 0.02rem 0.4rem;
    margin-left: 0.4rem;
    cursor: pointer;
    vertical-align: middle;
}}
.q-toggle:hover {{ color: #6b9eff; border-color: #6b9eff; }}
.q-toggle.open {{ color: #6b9eff; border-color: #2a4060; background: #1a2535; }}
.qdata-error a {{ color: #6b9eff; }}
.q-panel {{
    margin: 0.3rem 0 0.4rem 2.6rem;
    border: 1px solid #2a2f37;
    background: #15191e;
    padding: 0.5rem 0.7rem;
    font-size: 0.8rem;
    max-height: 320px;
    overflow-y: auto;
}}
.q-item {{
    padding: 0.35rem 0;
    border-top: 1px solid #22272e;
    line-height: 1.45;
    color: #9aa0a7;
}}
.q-item:first-child {{ border-top: none; }}
.q-item-meta {{
    font-size: 0.7rem;
    color: #555;
    margin-bottom: 0.1rem;
}}
.q-item-meta b {{ color: #808790; }}
.clip-toggle {{
    background: none;
    border: 1px solid #2a2f37;
    border-radius: 3px;
    color: #808790;
    font-size: 0.68rem;
    padding: 0.02rem 0.4rem;
    margin-left: 0.3rem;
    cursor: pointer;
    vertical-align: middle;
}}
.clip-toggle:hover {{ color: #e0b860; border-color: #e0b860; }}
.clip-toggle.open {{ color: #e0b860; border-color: #6b5a2a; background: #1f1c12; }}
.clip-panel {{
    margin: 0.3rem 0 0.4rem 2.6rem;
    border: 1px solid #2a2f37;
    background: #15191e;
    padding: 0.4rem 0.7rem;
}}
.clip-row {{
    display: flex;
    align-items: center;
    gap: 0.7rem;
    padding: 0.2rem 0;
}}
.clip-label {{
    color: #9aa0a7;
    font-size: 0.78rem;
    min-width: 10rem;
}}
.clip-row audio {{ height: 26px; }}
.clip-attr {{
    color: #555;
    text-decoration: none;
    font-size: 0.75rem;
    margin-left: 0.2rem;
}}
.clip-attr:hover {{ color: #6b9eff; }}
.map-toggle {{
    background: #1a1f25;
    border: 1px solid #3a3f47;
    border-radius: 3px;
    color: #9aa0a7;
    font-size: 0.78rem;
    padding: 0.1rem 0.6rem;
    cursor: pointer;
    margin-left: auto;
}}
.map-toggle:hover, .map-toggle.on {{ color: #6b9eff; border-color: #6b9eff; }}
.map-box {{ border: 1px solid #3a3f47; margin-bottom: 0.3rem; }}
.map-note {{
    color: #555;
    font-size: 0.78rem;
    font-style: italic;
    margin-bottom: 0.9rem;
}}
.leaflet-container {{ background: #101418; }}
.leaflet-popup-content-wrapper, .leaflet-popup-tip {{
    background: #1a1f25; color: #c8ccd1;
    border: 1px solid #3a3f47;
}}
.leaflet-popup-content a {{ color: #6b9eff; text-decoration: none; }}
.entry-list {{
    list-style: none;
    margin: 0;
}}
.entry {{
    padding: 0.28rem 0;
    border-top: 1px solid #22272e;
    font-size: 0.9rem;
    line-height: 1.5;
}}
.entry:first-child {{ border-top: none; }}
.freq-badge {{
    display: inline-block;
    min-width: 2.1rem;
    text-align: right;
    color: #808790;
    font-size: 0.72rem;
    font-weight: bold;
    white-space: nowrap;
}}
.entry-name {{
    font-weight: bold;
}}
a.entry-name {{
    color: #6b9eff;
    text-decoration: none;
    border-bottom: 1px dotted #6b9eff;
}}
a.entry-name:hover {{ text-decoration: none; border-bottom-style: solid; }}
.no-page {{
    color: #cc6666;
    border-bottom: 1px dotted #cc6666;
    cursor: default;
}}
.entry-note {{
    color: #9aa0a7;
}}
.appendix {{
    margin-top: 1.6rem;
    border: 1px solid #3a3f47;
    background: #1a1f25;
}}
.appendix summary {{
    cursor: pointer;
    padding: 0.5rem 0.9rem;
    color: #9aa0a7;
    font-size: 0.85rem;
    user-select: none;
}}
.appendix summary:hover {{ color: #c8ccd1; }}
.appendix-grid {{
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(240px, 1fr));
    gap: 0.15rem 1rem;
    padding: 0.6rem 0.9rem 0.8rem;
    font-size: 0.8rem;
}}
.appendix-item {{ white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }}
.appendix-item a {{ color: #6b9eff; text-decoration: none; }}
.appendix-item a:hover {{ text-decoration: underline; }}
{nav_bar_css()}
{search_nav_css()}
{mobile_core_css()}
html[data-layout="mobile"] .toc {{ display: block; }}
html[data-layout="mobile"] .entry-sublist {{ margin-left: 1.2rem; }}
html[data-layout="mobile"] .q-panel, html[data-layout="mobile"] .clip-panel {{ margin-left: 0; }}
html[data-layout="mobile"] .q-toggle, html[data-layout="mobile"] .clip-toggle {{
    font-size: 0.78rem; padding: 0.2rem 0.6rem; min-height: 32px;
}}
html[data-layout="mobile"] .clip-label {{ min-width: 0; }}
html[data-layout="mobile"] .clip-row {{ flex-wrap: wrap; }}
html[data-layout="mobile"] .search-nav-dropdown {{
    min-width: 0; width: min(320px, calc(100vw - 1.5rem));
}}
html[data-layout="mobile"] .coverage-bar {{ gap: 0.4rem 1.2rem; }}
</style>
</head>
<body>
<div class="breadcrumb">{category}</div>
<h1>{title}</h1>
{nav_html}
{draft_html}
<div class="intro">{intro_html}</div>
<div class="coverage-bar">
<span><b>{total}</b> core answerlines (frequency &ge; {fs.get('threshold', '?')})</span>
<span><b>{have}</b> with study pages ({pct}%)</span>
<span>difficulties {diffs_str}, {fs.get('min_year', '?')}&ndash;present</span>
<span>frequency data {escape(str(fs.get('fetched', '?')))}</span>
<button class="map-toggle" id="map-toggle">Map</button>
</div>
<div id="map-wrap" style="display:none">
    <div class="map-box" id="map-box"></div>
    <div class="map-note" id="map-note"></div>
</div>
<div class="toc">
<div class="toc-title">Contents</div>
<ol>{toc_items}</ol>
</div>
{sections_html}
{appendix_html}
<script src="../../guides_data.js"></script>
<script src="../../../lib/js/search_nav.js"></script>
<script src="../../../lib/js/map_view.js"></script>
<script>initSearchNav('.nav-search', {{ prefix: '../../../' }});</script>
<script>
const MAP_ITEMS = {map_items_json};
let mapCtl = null;
document.getElementById('map-toggle').addEventListener('click', function () {{
    const wrap = document.getElementById('map-wrap');
    const show = wrap.style.display === 'none';
    wrap.style.display = show ? '' : 'none';
    this.classList.toggle('on', show);
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
// Score-clip panels (soundbites from matched topics' score_clues).
document.querySelectorAll('.clip-toggle').forEach(btn => {{
    const panel = btn.parentElement.querySelector('.clip-panel');
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
        const panel = btn.parentElement.querySelector('.q-panel');
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
