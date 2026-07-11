"""
render_questions.py — Generate HTML pages of raw tossups and bonuses.

Each topic's page renders from output/{slug}/questions_ref.json — ordered
qbreader _id lists per query — resolved against the shared question store
(lib/questions_store.py, output/_questions/).

Usage:
    python lib/render/render_questions.py [--force]      # all topics
    python lib/render/render_questions.py <cache_file> <output_file>
"""

import json
import re
import sys
from html import escape
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from lib.common import resolve_analyses
from lib.render.theme import base_css


def _tab_label(cache_data: dict, is_mentions: bool) -> str:
    """Short human-readable label for a cache file tab."""
    query = cache_data.get("query_string", "?")
    diffs = cache_data.get("difficulties") or []
    if diffs:
        label = f"{query} (d{min(diffs)}–{max(diffs)})"
    else:
        label = query
    if is_mentions:
        label += " mentions"
    return label


def _highlight_query(text: str, query: str) -> str:
    """Wrap all case-insensitive occurrences of query in <mark> tags.

    ``text`` is qbreader's HTML question text (it carries <b>/<i> power
    markup by design, so it must NOT be escaped here). The lookahead
    keeps matches out of tag internals, mirroring render.py's _linkify.
    """
    if not query:
        return text
    return re.sub(
        r'(' + re.escape(query) + r')(?![^<]*>)',
        r'<mark>\1</mark>',
        text,
        flags=re.IGNORECASE,
    )


def _questions_html_for_cache(cache_data: dict, tab_idx: int, is_mentions: bool = False) -> str:
    """Render tossups + bonuses for one cache source into HTML."""
    # Mentions files store results under 'text_mentions'; answer files use 'answer_matches'
    matches = cache_data.get("answer_matches") or cache_data.get("text_mentions") or {}
    tossups = matches.get("tossups", [])
    bonuses = matches.get("bonuses", [])
    query = cache_data.get("query_string", "") if is_mentions else ""

    tossups_html = ""
    for i, t in enumerate(tossups, 1):
        set_name = t.get("set", {}).get("name", "")
        year = t.get("set", {}).get("year", "")
        diff = t.get("difficulty", "")
        cat = t.get("category", "")
        question = _highlight_query(t.get("question", ""), query)
        answer = t.get("answer", "")
        tossups_html += f"""
        <div class="question">
            <div class="q-header">
                <span class="q-num">T{i}</span>
                <span class="q-source">{escape(str(set_name))} ({year})</span>
                <span class="q-meta">Diff {diff} &middot; {escape(str(cat))}</span>
            </div>
            <div class="q-text">{question}</div>
            <div class="q-answer">ANSWER: {answer}</div>
        </div>"""

    bonuses_html = ""
    for i, b in enumerate(bonuses, 1):
        set_name = b.get("set", {}).get("name", "")
        year = b.get("set", {}).get("year", "")
        diff = b.get("difficulty", "")
        cat = b.get("category", "")
        leadin = _highlight_query(b.get("leadin", ""), query)
        parts = b.get("parts", [])
        answers = b.get("answers", [])
        parts_html = ""
        for part, ans in zip(parts, answers):
            part = _highlight_query(part, query)
            parts_html += f"""
            <div class="b-part">
                <div class="b-part-text">[10] {part}</div>
                <div class="q-answer">ANSWER: {ans}</div>
            </div>"""
        bonuses_html += f"""
        <div class="question">
            <div class="q-header">
                <span class="q-num">B{i}</span>
                <span class="q-source">{escape(str(set_name))} ({year})</span>
                <span class="q-meta">Diff {diff} &middot; {escape(str(cat))}</span>
            </div>
            <div class="q-text">{leadin}</div>
            {parts_html}
        </div>"""

    stats = f"{len(tossups)} tossup{'s' if len(tossups) != 1 else ''} &middot; {len(bonuses)} bonus{'es' if len(bonuses) != 1 else ''}"
    empty_msg = '<p style="color:#808790;font-style:italic;padding:0.5rem 0;">No questions.</p>'

    return f"""
<div class="tab-stats">{stats}</div>
<h2>Tossups</h2>
{tossups_html or empty_msg}
<h2>Bonuses</h2>
{bonuses_html or empty_msg}"""


def render_questions_html(cache_sources: "list[dict] | dict", output_path: str | Path,
                          topic_display: str = "", stock_link: str = "",
                          is_mentions: "list[bool] | None" = None) -> Path:
    """
    Render cached API data into an HTML page with one tab per cache source.
    cache_sources: list of cache dicts (one per query), or a single dict for back-compat.
    is_mentions: parallel list of bools indicating which sources are mention searches.
    """
    output_path = Path(output_path)

    # Back-compat: accept a single dict
    if isinstance(cache_sources, dict):
        cache_sources = [cache_sources]
        is_mentions = [False]
    if is_mentions is None:
        is_mentions = [False] * len(cache_sources)

    topic = topic_display or cache_sources[0].get("query_string", "Unknown")

    back_link = ""
    if stock_link:
        back_link = f'<div class="back-link"><a href="../../index.html">&larr; Home</a> · <a href="{escape(stock_link)}">Study guide</a></div>'

    # Build tab headers and panels
    tabs_html = ""
    panels_html = ""
    for i, (data, mentions) in enumerate(zip(cache_sources, is_mentions)):
        label = escape(_tab_label(data, mentions))
        active_cls = " active" if i == 0 else ""
        tabs_html += f'<button class="tab-btn{active_cls}" onclick="showTab({i})">{label}</button>\n'
        display = "block" if i == 0 else "none"
        panels_html += f'<div class="tab-panel" id="tab-{i}" style="display:{display}">{_questions_html_for_cache(data, i, is_mentions=mentions)}</div>\n'

    single = len(cache_sources) == 1

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
<script>
function showTab(i) {{
    document.querySelectorAll('.tab-panel').forEach((p, j) => p.style.display = j === i ? 'block' : 'none');
    document.querySelectorAll('.tab-btn').forEach((b, j) => b.classList.toggle('active', j === i));
}}
</script>
</body>
</html>"""

    output_path.parent.mkdir(exist_ok=True)
    with open(output_path, "w", encoding='utf-8') as f:
        f.write(html)
    return output_path


def build_all(force: bool = False, analyses=None, store=None):
    """Generate question pages for every topic with a questions_ref.json.

    Refs hold ordered qbreader _id lists per query; the text lives once in
    output/_questions/ (lib/questions_store.py). Note the incremental check
    keys off the ref + analysis mtimes only — a store-shard refresh that
    changes question text needs --force to propagate.
    """
    count = 0
    skipped = 0
    missing_ids = 0
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

        if store is None:
            from lib.questions_store import load_store
            store = load_store()

        with open(ref_path, encoding='utf-8') as f:
            refs = json.load(f)

        sources = []
        is_mentions_flags = []
        for entry in refs:
            docs = {}
            for kind in ("tossups", "bonuses"):
                ids = entry.get(kind, [])
                docs[kind] = [store[i] for i in ids if i in store]
                missing_ids += sum(1 for i in ids if i not in store)
            key = "text_mentions" if entry.get("mentions") else "answer_matches"
            sources.append({
                "query_string": entry.get("query_string", ""),
                "difficulties": entry.get("difficulties"),
                "min_year": entry.get("min_year"),
                key: docs,
            })
            is_mentions_flags.append(bool(entry.get("mentions")))

        stock_link = "stock.html"
        render_questions_html(sources, questions_path,
                              topic_display=topic_display,
                              stock_link=stock_link,
                              is_mentions=is_mentions_flags)
        def _counts(s):
            m = s.get("answer_matches") or s.get("text_mentions") or {}
            return len(m.get("tossups", [])), len(m.get("bonuses", []))
        total_t = sum(_counts(s)[0] for s in sources)
        total_b = sum(_counts(s)[1] for s in sources)
        print(f"  {topic_display}: {len(sources)} source(s), {total_t}T {total_b}B -> {questions_path}")
        count += 1
    if missing_ids:
        print(f"  WARNING: {missing_ids} referenced question ids missing "
              f"from output/_questions/", file=sys.stderr)
    print(f"Built {count} question pages" + (f" ({skipped} up-to-date)" if skipped else ""))


if __name__ == "__main__":
    force = "--force" in sys.argv
    remaining = [a for a in sys.argv[1:] if a != "--force"]
    if len(remaining) == 2:
        cache_path = remaining[0]
        output_path = sys.argv[2]
        with open(cache_path, encoding='utf-8') as f:
            data = json.load(f)
        render_questions_html(data, output_path)
        print(f"Rendered to {output_path}")
    else:
        build_all(force=force)
