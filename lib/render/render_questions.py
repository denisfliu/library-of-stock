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
from lib.render.theme import base_css


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
                <span class="q-meta">Diff ${q.difficulty ?? ''} &middot; ${esc(q.category || '')}</span>
            </div>`;
}

function panelHtml(entry) {
    const query = entry.mentions ? entry.query_string : '';
    const tossups = entry.tossups.map((t, i) => `
        <div class="question">${header('T', i + 1, t)}
            <div class="q-text">${highlight(t.question || '', query)}</div>
            <div class="q-answer">ANSWER: ${t.answer || ''}</div>
        </div>`).join('');
    const bonuses = entry.bonuses.map((b, i) => {
        const parts = (b.parts || []).map((part, j) => `
            <div class="b-part">
                <div class="b-part-text">[10] ${highlight(part, query)}</div>
                <div class="q-answer">ANSWER: ${(b.answers || [])[j] || ''}</div>
            </div>`).join('');
        return `
        <div class="question">${header('B', i + 1, b)}
            <div class="q-text">${highlight(b.leadin || '', query)}</div>
            ${parts}
        </div>`;
    }).join('');
    const nt = entry.tossups.length, nb = entry.bonuses.length;
    const stats = `${nt} tossup${nt !== 1 ? 's' : ''} &middot; ${nb} bonus${nb !== 1 ? 'es' : ''}`;
    const empty = '<p style="color:#808790;font-style:italic;padding:0.5rem 0;">No questions.</p>';
    return `
<div class="tab-stats">${stats}</div>
<h2>Tossups</h2>
${tossups || empty}
<h2>Bonuses</h2>
${bonuses || empty}`;
}

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

    back_link = ""
    if stock_link:
        back_link = f'<div class="back-link"><a href="../../index.html">&larr; Home</a> · <a href="{escape(stock_link)}">Study guide</a></div>'

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
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Questions: {escape(topic)}</title>
<style>
{base_css()}
.back-link {{
    display: inline-block;
    margin-bottom: 1rem;
    font-size: 0.88rem;
}}
.tab-bar {{
    display: {'none' if single else 'flex'};
    gap: 0.25rem;
    flex-wrap: wrap;
    margin: 0.8rem 0 0.2rem;
    border-bottom: 1px solid #3a3f47;
    padding-bottom: 0;
}}
.tab-btn {{
    background: none;
    border: 1px solid transparent;
    border-bottom: none;
    padding: 0.3rem 0.75rem;
    font-size: 0.82rem;
    color: #808790;
    cursor: pointer;
    border-radius: 3px 3px 0 0;
    margin-bottom: -1px;
}}
.tab-btn:hover {{ color: #c8ccd1; }}
.tab-btn.active {{
    color: #6b9eff;
    border-color: #3a3f47;
    border-bottom-color: #101418;
    background: #101418;
}}
.tab-stats {{
    font-size: 0.85rem;
    color: #808790;
    margin: 0.6rem 0 1rem;
}}
.q-loading, .qdata-error {{
    color: #808790;
    font-style: italic;
    padding: 0.8rem 0;
    font-size: 0.9rem;
}}
.qdata-error a {{ color: #6b9eff; }}
h2 {{
    font-family: 'Linux Libertine', Georgia, serif;
    font-size: 1.3rem;
    font-weight: normal;
    border-bottom: 1px solid #3a3f47;
    padding-bottom: 0.15rem;
    margin-bottom: 0.8rem;
    margin-top: 1.5rem;
    color: #e0e0e0;
}}
.question {{
    background: #1a1f25;
    border: 1px solid #3a3f47;
    margin-bottom: 0.8rem;
    padding: 0;
    border-radius: 4px;
    overflow: hidden;
}}
.q-header {{
    display: flex;
    align-items: center;
    gap: 0.6rem;
    padding: 0.35rem 0.8rem;
    background: #1f252d;
    border-bottom: 1px solid #3a3f47;
    font-size: 0.82rem;
}}
.q-num {{ font-weight: bold; color: #6b9eff; min-width: 2rem; }}
.q-source {{ color: #c8ccd1; }}
.q-meta {{ color: #808790; margin-left: auto; }}
.q-text {{ padding: 0.6rem 0.8rem; font-size: 0.9rem; line-height: 1.6; }}
.q-text b {{ color: #e0e0e0; }}
.q-answer {{ padding: 0.4rem 0.8rem; font-size: 0.85rem; border-top: 1px solid #2a2f37; color: #9aa0a7; }}
.q-answer b, .q-answer u {{ color: #6bcf8e; }}
.b-part {{ border-top: 1px solid #2a2f37; }}
.b-part-text {{ padding: 0.5rem 0.8rem; font-size: 0.9rem; line-height: 1.6; }}
mark {{ background: #5a4a00; color: #ffd54f; border-radius: 2px; padding: 0 2px; }}
</style>
</head>
<body>
{back_link}
<h1>Questions: {escape(topic)}</h1>
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
