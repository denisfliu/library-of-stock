"""
render_questions.py — Generate HTML pages of raw tossups and bonuses.

Each topic's page is built from output/{slug}/questions_ref.json (ordered
qbreader _id lists per query) but ships WITHOUT question text: the page
fetches topic_questions/{slug}.json from the R2 data plane at view time
(lib/js/qdata.js; artifacts published by lib/mirror/publish.py) and
renders the cards client-side. Tab labels and counts come from the refs,
so the chrome is complete before the fetch resolves.

Usage:
    python lib/render/render_questions.py [--force]      # all topics
"""

import json
import sys
from html import escape
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from lib.common import resolve_analyses
from lib.render.theme import (base_css, layout_switch_script, mobile_core_css,
                              site_nav, site_nav_css)


def _tab_label(entry: dict) -> str:
    """Short human-readable label for a query tab (from its ref entry)."""
    query = entry.get("query_string", "?")
    diffs = entry.get("difficulties") or []
    if diffs:
        label = f"{query} (d{min(diffs)}–{max(diffs)})"
    else:
        label = query
    if entry.get("mentions"):
        label += " mentions"
    return label


# Client-side renderer: mirrors the DOM the old build-time renderer
# produced (.question/.q-header/.q-text/.q-answer, bonus .b-part rows;
# raw qbreader markup inserted unescaped by design; <mark> highlighting
# on mentions tabs, kept out of tag internals by the lookahead).
_PAGE_JS = """
const esc = s => String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');

function highlight(text, query) {
    if (!query) return text;
    const re = new RegExp('(' + query.replace(/[.*+?^${}()|[\\]\\\\]/g, '\\\\$&') + ')(?![^<]*>)', 'gi');
    return String(text).replace(re, '<mark>$1</mark>');
}

function header(prefix, i, q) {
    const set = (q.set || {});
    return `
            <div class="q-header">
                <span class="q-num">${prefix}${i}</span>
                <span class="q-source">${esc(set.name || '')} (${set.year ?? ''})</span>
                <span class="q-meta">difficulty ${q.difficulty ?? ''} &middot; ${esc(q.category || '')}</span>
            </div>`;
}

const ANS = '<span class="q-ans-label">ANSWER</span>';

function panelHtml(entry) {
    const query = entry.mentions ? entry.query_string : '';
    const tossups = entry.tossups.map((t, i) => `
        <div class="question">${header('T', i + 1, t)}
            <div class="q-text">${highlight(t.question || '', query)}</div>
            <div class="q-answer">${ANS}${t.answer || ''}</div>
        </div>`).join('');
    const bonuses = entry.bonuses.map((b, i) => {
        const parts = (b.parts || []).map((part, j) => `
            <div class="b-part">
                <div class="b-part-text"><span class="b-ten">[10]</span> ${highlight(part, query)}</div>
                <div class="q-answer">${ANS}${(b.answers || [])[j] || ''}</div>
            </div>`).join('');
        return `
        <div class="question">${header('B', i + 1, b)}
            <div class="q-text">${highlight(b.leadin || '', query)}</div>
            ${parts}
        </div>`;
    }).join('');
    const nt = entry.tossups.length, nb = entry.bonuses.length;
    const stats = `${nt} tossup${nt !== 1 ? 's' : ''} &middot; ${nb} bonus${nb !== 1 ? 'es' : ''}`;
    const empty = '<p class="q-empty">No questions.</p>';
    // Tossups / Bonuses are underline sub-tabs (counts in the labels);
    // the h2s stay for structure/screen readers.
    return `
<div class="sub-tabs" role="tablist">
<button class="sub-btn active" data-k="t" role="tab">Tossups<span class="c">${nt}</span></button>
<button class="sub-btn" data-k="b" role="tab">Bonuses<span class="c">${nb}</span></button>
<span class="tab-stats">${stats}</span>
</div>
<div class="sub-panel" data-k="t">
<h2>Tossups</h2>
${tossups || empty}
</div>
<div class="sub-panel" data-k="b" style="display:none">
<h2>Bonuses</h2>
${bonuses || empty}
</div>`;
}

document.addEventListener('click', e => {
    const btn = e.target.closest && e.target.closest('.sub-btn');
    if (!btn) return;
    const panel = btn.closest('.tab-panel');
    panel.querySelectorAll('.sub-btn').forEach(b => b.classList.toggle('active', b === btn));
    panel.querySelectorAll('.sub-panel').forEach(p => p.style.display = p.dataset.k === btn.dataset.k ? 'block' : 'none');
});

qdataFetch('topic_questions/' + TOPIC_SLUG + '.json').then(entries => {
    entries.forEach((entry, i) => {
        const panel = document.getElementById('tab-' + i);
        if (panel) panel.innerHTML = panelHtml(entry);
    });
}).catch(err => {
    document.querySelectorAll('.tab-panel').forEach(p => {
        p.innerHTML = qdataErrorHtml(err);
    });
});

function showTab(i) {
    document.querySelectorAll('.tab-panel').forEach((p, j) => p.style.display = j === i ? 'block' : 'none');
    document.querySelectorAll('.tab-btn').forEach((b, j) => b.classList.toggle('active', j === i));
}
"""


def render_questions_html(refs: list[dict], output_path: str | Path,
                          topic_slug: str, topic_display: str = "",
                          stock_link: str = "") -> Path:
    """Render the questions page chrome for one topic; text arrives at
    view time from topic_questions/{slug}.json."""
    output_path = Path(output_path)
    topic = topic_display or (refs[0].get("query_string", "Unknown") if refs
                              else "Unknown")

    # Breadcrumb back to the study guide (Wiki lives in the shared site nav).
    back_link = ""
    if stock_link:
        back_link = (f'<div class="back-link"><a href="{escape(stock_link)}">{escape(topic)}</a>'
                     f' <span class="crumb-muted">&middot; study guide</span></div>')
    cards_link = ""
    if (output_path.parent / "cards.json").exists():
        cards_link = '<a class="head-link" href="cards.html">Make cards</a>'
    labels = [_tab_label(e) for e in refs]
    subline = ("Questions matched by " + ", ".join(escape(l) for l in labels)) if labels else ""

    tabs_html = ""
    panels_html = ""
    for i, entry in enumerate(refs):
        label = escape(_tab_label(entry))
        active_cls = " active" if i == 0 else ""
        tabs_html += f'<button class="tab-btn{active_cls}" onclick="showTab({i})">{label}</button>\n'
        display = "block" if i == 0 else "none"
        panels_html += (f'<div class="tab-panel" id="tab-{i}" '
                        f'style="display:{display}">'
                        f'<p class="q-loading">Loading questions…</p></div>\n')

    single = len(refs) == 1

    html = f"""<!DOCTYPE html>
<html lang="en" data-layout="desktop">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
{layout_switch_script()}
<title>Questions: {escape(topic)}</title>
<style>
{base_css(max_width='868px')}
{site_nav_css()}
.back-link {{
    margin-top: 2rem;
    font-size: 14px;
}}
.crumb-muted {{ color: var(--c-muted); }}
.page-head {{
    display: flex;
    align-items: baseline;
    gap: 0.5rem 1.1rem;
    flex-wrap: wrap;
    margin-top: 2px;
}}
.page-head h1 {{ font-size: 28px; margin: 0; padding: 0; flex: 1 1 auto; }}
.head-link {{ font-size: 14px; }}
.subline {{ margin-top: 4px; font-size: 13px; color: var(--c-muted); }}
.tab-bar, .sub-tabs {{
    display: flex;
    align-items: flex-end;
    gap: 0.4rem 1.6rem;
    flex-wrap: wrap;
    border-bottom: 1px solid var(--c-border);
}}
.tab-bar {{
    display: {'none' if single else 'flex'};
    margin-top: 1.1rem;
}}
.sub-tabs {{ margin-top: 1.1rem; }}
.tab-btn, .sub-btn {{
    background: none;
    border: none;
    border-radius: 0;
    padding: 0 0 0.6rem;
    margin-bottom: -1px;
    font: inherit;
    font-size: 15px;
    color: var(--c-muted);
    cursor: pointer;
}}
.tab-btn {{ font-size: 14px; }}
.tab-btn:hover, .sub-btn:hover {{ color: var(--c-text); }}
.tab-btn.active, .sub-btn.active {{
    color: var(--c-text);
    font-weight: 600;
    box-shadow: inset 0 -2px 0 var(--c-link);
}}
.sub-btn .c {{ font-weight: 400; color: var(--c-muted); font-size: 13px; margin-left: 0.3rem; }}
.tab-stats {{
    margin-left: auto;
    padding-bottom: 0.6rem;
    font-size: 13px;
    color: var(--c-muted);
}}
.q-loading, .qdata-error, .q-empty {{
    color: var(--c-muted);
    font-style: italic;
    padding: 1.2rem 0;
    font-size: 14px;
}}
.qdata-error a {{ color: var(--c-link); }}
.sub-panel h2 {{
    position: absolute; width: 1px; height: 1px; overflow: hidden;
    clip: rect(0 0 0 0); white-space: nowrap;
}}
.question {{
    padding: 1.35rem 0;
    border-bottom: 1px solid var(--c-border);
}}
.q-header {{
    display: flex;
    align-items: baseline;
    gap: 0.75rem;
    flex-wrap: wrap;
    font-size: 13px;
    color: var(--c-muted);
}}
.q-num {{ font-weight: 600; color: var(--c-text); }}
.q-meta {{ margin-left: auto; }}
.q-text, .b-part-text {{ margin-top: 0.5rem; font-size: 15.5px; line-height: 1.65; }}
.q-text:empty {{ display: none; }}
.q-text b, .b-part-text b {{ color: var(--c-bright); }}
.q-answer {{ margin-top: 0.6rem; font-size: 15px; line-height: 1.6; color: var(--c-text); }}
.q-ans-label {{
    color: var(--c-muted); font-size: 12px; font-weight: 600;
    letter-spacing: 0.04em; margin-right: 0.4rem;
}}
.b-part {{ margin-top: 0.9rem; }}
.b-ten {{ color: var(--c-muted); font-size: 13px; }}
mark {{ background: var(--c-hl); color: inherit; border-radius: 2px; padding: 0 2px; }}
{mobile_core_css()}
html[data-layout="mobile"] .tab-btn, html[data-layout="mobile"] .sub-btn {{ min-height: 40px; display: inline-flex; align-items: flex-end; }}
html[data-layout="mobile"] .page-head h1 {{ font-size: 24px; }}
html[data-layout="mobile"] .q-meta {{ margin-left: 0; }}
html[data-layout="mobile"] .tab-stats {{ display: none; }}
</style>
</head>
<body>
{site_nav('../../', 'wiki')}
{back_link}
<div class="page-head"><h1>Source questions</h1>{cards_link}</div>
<div class="subline">{subline}</div>
<div class="tab-bar">
{tabs_html}</div>
{panels_html}
<script src="../../lib/js/qdata.js"></script>
<script>
const TOPIC_SLUG = {json.dumps(topic_slug)};
{_PAGE_JS}</script>
</body>
</html>"""

    output_path.parent.mkdir(exist_ok=True)
    with open(output_path, "w", encoding='utf-8') as f:
        f.write(html)
    return output_path


def build_all(force: bool = False, analyses=None):
    """Generate question pages for every topic with a questions_ref.json.

    Pages carry only the refs-derived chrome; question text is fetched at
    view time from the R2 data plane, so a text refresh needs a publish,
    not a rebuild.
    """
    count = 0
    skipped = 0
    for topic_key, analysis_file, analysis in resolve_analyses(analyses):
        topic_display = analysis.get("topic", topic_key.replace("_", " ").title())

        ref_path = analysis_file.parent / "questions_ref.json"
        if not ref_path.exists():
            print(f"  Skipping {topic_key}: no questions_ref.json")
            continue

        questions_path = analysis_file.parent / "questions.html"
        if not force and questions_path.exists():
            html_mtime = questions_path.stat().st_mtime
            if (html_mtime >= analysis_file.stat().st_mtime
                    and html_mtime >= ref_path.stat().st_mtime):
                skipped += 1
                continue

        with open(ref_path, encoding='utf-8') as f:
            refs = json.load(f)

        render_questions_html(refs, questions_path,
                              topic_slug=topic_key,
                              topic_display=topic_display,
                              stock_link="stock.html")
        total_t = sum(len(e.get("tossups", [])) for e in refs)
        total_b = sum(len(e.get("bonuses", [])) for e in refs)
        print(f"  {topic_display}: {len(refs)} source(s), {total_t}T {total_b}B -> {questions_path}")
        count += 1
    print(f"Built {count} question pages" + (f" ({skipped} up-to-date)" if skipped else ""))


if __name__ == "__main__":
    build_all(force="--force" in sys.argv)
