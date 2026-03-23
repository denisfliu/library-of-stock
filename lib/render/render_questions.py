"""
render_questions.py — Generate HTML page displaying raw tossups and bonuses
for a topic from cached API data.

Usage:
    python render_questions.py <cache_file> <output_file>
    python render_questions.py cache/smetana_d7_8_9_10_y2012.json output/smetana_questions.html
"""

import json
import re
import sys
from html import escape
from pathlib import Path


def _sanitize(name: str) -> str:
    """Same normalization fetch.py uses for cache filenames."""
    return re.sub(r'[^\w\-]', '_', name.strip().lower())


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
    """Wrap all case-insensitive occurrences of query in <mark> tags."""
    if not query:
        return text
    return re.sub(
        r'(' + re.escape(query) + r')',
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
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{
    font-family: -apple-system, 'Segoe UI', Roboto, 'Helvetica Neue', sans-serif;
    background: #101418;
    color: #c8ccd1;
    max-width: 960px;
    margin: 0 auto;
    padding: 1.5rem 1.5rem;
    line-height: 1.5;
    font-size: 14px;
}}
a {{ color: #6b9eff; }}
a:hover {{ text-decoration: underline; }}
h1 {{
    font-family: 'Linux Libertine', Georgia, serif;
    font-size: 1.8rem;
    font-weight: normal;
    border-bottom: 1px solid #3a3f47;
    padding-bottom: 0.25rem;
    margin-bottom: 0.5rem;
    color: #e0e0e0;
}}
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
    with open(output_path, "w") as f:
        f.write(html)
    return output_path


def find_cache_for_topic(topic_key: str, topic_name: str = "") -> Path | None:
    """Find the cache file matching a topic key (from analysis filename).

    Agents often search by last name (e.g. 'kafka' for Franz Kafka), so the
    cache file slug won't match the full-name analysis slug.  Strategy:

    1. Exact prefix match on topic_key.
    2. If topic_name provided, apply fetch.py's _sanitize() to get the
       canonical cache slug (handles dots, special chars) and try that.
    3. Try each word component from last to first as a prefix — catches the
       common last-name-search pattern.
    4. Try adjacent word pairs from the end — catches compound names
       like "du Maurier" → prefix "du_maurier".
    5. Substring fallback.
    """
    cache_dir = Path("cache")

    name_lower = topic_name.lower() if topic_name else ""

    def _first_non_mention(pattern: str) -> Path | None:
        for f in sorted(cache_dir.glob(pattern)):
            if "_mentions" not in f.name:
                return f
        return None

    def _validated(pattern: str) -> Path | None:
        """Like _first_non_mention but also checks that the cache's
        query_string is actually a word in the topic name.  This prevents
        e.g. 'smith_d7...' (about Adam Smith) from being served to a
        different topic whose only match is the surname 'Smith'."""
        for f in sorted(cache_dir.glob(pattern)):
            if "_mentions" in f.name:
                continue
            if not name_lower:
                return f  # no topic_name to validate against, accept blindly
            try:
                qs = json.load(open(f)).get("query_string", "").lower()
            except Exception:
                continue
            if qs and qs in name_lower:
                return f
        return None

    # 1. Exact prefix match (always trusted — no validation needed)
    result = _first_non_mention(f"{topic_key}_*.json")
    if result:
        return result

    # 2. Sanitized topic_name (matches fetch.py's cache key convention)
    if topic_name:
        sanitized = _sanitize(topic_name)
        if sanitized != topic_key:
            result = _first_non_mention(f"{sanitized}_*.json")
            if result:
                return result

    # 3. Each word component from last to first (min 3 chars) — validated.
    # Use components from both the topic_key and the sanitized topic_name so
    # that apostrophes/special chars in names like "O'Connor" resolve correctly
    # (analysis slug: flannery_oconnor, sanitized: flannery_o_connor → 'connor').
    sanitized_name = _sanitize(topic_name) if topic_name else topic_key
    all_components = dict.fromkeys(
        p for source in (topic_key, sanitized_name)
        for p in source.replace(".", "").split("_")
        if len(p) >= 3
    )
    for part in reversed(list(all_components)):
        result = _validated(f"{part}_*.json")
        if result:
            return result

    # 4. Adjacent word pairs from the end — validated (compound last names).
    # Use sanitized name so O'Connor → ['o', 'connor'] → pair 'o_connor'.
    for source_key in dict.fromkeys([sanitized_name, topic_key.replace(".", "")]):
        raw_parts = [p for p in source_key.split("_") if p]
        for i in range(len(raw_parts) - 1, 0, -1):
            pair = "_".join(raw_parts[i - 1:i + 1])
            result = _validated(f"{pair}_*.json")
            if result:
                return result

    # 5. Substring fallback
    for f in sorted(cache_dir.glob("*.json")):
        if "_mentions" not in f.name and topic_key in f.name:
            return f
    return None


def build_all(force: bool = False):
    """Generate question pages for all topics that have both cache and analysis data."""
    output_dir = Path("output")
    count = 0
    skipped = 0
    for analysis_file in sorted(output_dir.glob("*/analysis.json")):
        topic_key = analysis_file.parent.name

        # Load topic display name
        with open(analysis_file) as f:
            analysis = json.load(f)
        topic_display = analysis.get("topic", topic_key.replace("_", " ").title())

        # Collect all cache files in the topic directory
        # Sort: non-mentions first (alphabetically), then mentions
        all_jsons = [f for f in analysis_file.parent.glob("*.json")
                     if f.name != "analysis.json"]
        non_mentions = sorted(f for f in all_jsons if "_mentions" not in f.name)
        mentions = sorted(f for f in all_jsons if "_mentions" in f.name)
        cache_files = non_mentions + mentions

        # If nothing in topic dir, fall back to fuzzy match in cache/
        if not cache_files:
            fallback = find_cache_for_topic(topic_key, topic_name=topic_display)
            if fallback:
                cache_files = [fallback]

        if not cache_files:
            # Check recorded cache_file as last resort
            recorded = analysis.get("cache_file")
            if recorded:
                candidate = analysis_file.parent / recorded
                if not candidate.exists():
                    candidate = Path("cache") / recorded
                if candidate.exists():
                    cache_files = [candidate]
            if not cache_files:
                print(f"  Skipping {topic_key}: no cache file found")
                continue

        questions_path = analysis_file.parent / "questions.html"

        # Incremental: skip if questions.html is newer than all cache files and analysis
        if not force and questions_path.exists():
            html_mtime = questions_path.stat().st_mtime
            if (html_mtime >= analysis_file.stat().st_mtime
                    and all(html_mtime >= cf.stat().st_mtime for cf in cache_files)):
                skipped += 1
                continue

        sources = []
        is_mentions_flags = []
        for cf in cache_files:
            with open(cf) as f:
                sources.append(json.load(f))
            is_mentions_flags.append("_mentions" in cf.name)

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
    print(f"Built {count} question pages" + (f" ({skipped} up-to-date)" if skipped else ""))


if __name__ == "__main__":
    force = "--force" in sys.argv
    remaining = [a for a in sys.argv[1:] if a != "--force"]
    if len(remaining) == 2:
        cache_path = remaining[0]
        output_path = sys.argv[2]
        with open(cache_path) as f:
            data = json.load(f)
        render_questions_html(data, output_path)
        print(f"Rendered to {output_path}")
    else:
        build_all(force=force)
