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


def render_questions_html(cache_data: dict, output_path: str | Path,
                          topic_display: str = "", stock_link: str = "") -> Path:
    """
    Render cached API data into an HTML page showing all tossups and bonuses.
    """
    output_path = Path(output_path)
    query = cache_data.get("query_string", "Unknown")
    topic = topic_display or query

    tossups = cache_data.get("answer_matches", {}).get("tossups", [])
    bonuses = cache_data.get("answer_matches", {}).get("bonuses", [])

    # Build tossup HTML
    tossups_html = ""
    for i, t in enumerate(tossups, 1):
        set_name = t.get("set", {}).get("name", "")
        year = t.get("set", {}).get("year", "")
        diff = t.get("difficulty", "")
        cat = t.get("category", "")
        question = t.get("question", "")
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
        </div>
        """

    # Build bonus HTML
    bonuses_html = ""
    for i, b in enumerate(bonuses, 1):
        set_name = b.get("set", {}).get("name", "")
        year = b.get("set", {}).get("year", "")
        diff = b.get("difficulty", "")
        cat = b.get("category", "")
        leadin = b.get("leadin", "")
        parts = b.get("parts", [])
        answers = b.get("answers", [])

        parts_html = ""
        for j, (part, ans) in enumerate(zip(parts, answers)):
            parts_html += f"""
            <div class="b-part">
                <div class="b-part-text">[10] {part}</div>
                <div class="q-answer">ANSWER: {ans}</div>
            </div>
            """

        bonuses_html += f"""
        <div class="question">
            <div class="q-header">
                <span class="q-num">B{i}</span>
                <span class="q-source">{escape(str(set_name))} ({year})</span>
                <span class="q-meta">Diff {diff} &middot; {escape(str(cat))}</span>
            </div>
            <div class="q-text">{leadin}</div>
            {parts_html}
        </div>
        """

    back_link = ""
    if stock_link:
        back_link = f'<div class="back-link"><a href="../index.html">&larr; Home</a> · <a href="{escape(stock_link)}">Study guide</a></div>'

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
    text-decoration: none;
}}
.back-link:hover {{ text-decoration: underline; }}
.stats {{
    font-size: 0.85rem;
    color: #808790;
    margin-bottom: 1.2rem;
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
.q-num {{
    font-weight: bold;
    color: #6b9eff;
    min-width: 2rem;
}}
.q-source {{
    color: #c8ccd1;
}}
.q-meta {{
    color: #808790;
    margin-left: auto;
}}
.q-text {{
    padding: 0.6rem 0.8rem;
    font-size: 0.9rem;
    line-height: 1.6;
}}
.q-text b {{
    color: #e0e0e0;
}}
.q-answer {{
    padding: 0.4rem 0.8rem;
    font-size: 0.85rem;
    border-top: 1px solid #2a2f37;
    color: #9aa0a7;
}}
.q-answer b, .q-answer u {{
    color: #6bcf8e;
}}
.b-part {{
    border-top: 1px solid #2a2f37;
}}
.b-part-text {{
    padding: 0.5rem 0.8rem;
    font-size: 0.9rem;
    line-height: 1.6;
}}
</style>
</head>
<body>
{back_link}
<h1>Questions: {escape(topic)}</h1>
<div class="stats">{len(tossups)} tossups &middot; {len(bonuses)} bonuses</div>

<h2>Tossups</h2>
{tossups_html}

<h2>Bonuses</h2>
{bonuses_html}
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


def build_all():
    """Generate question pages for all topics that have both cache and analysis data."""
    output_dir = Path("output")
    count = 0
    for analysis_file in sorted(output_dir.glob("*_analysis.json")):
        topic_key = analysis_file.stem.replace("_analysis", "")

        # Load topic display name
        with open(analysis_file) as f:
            analysis = json.load(f)
        topic_display = analysis.get("topic", topic_key.replace("_", " ").title())

        # Find cache file (pass full topic name for better slug matching)
        cache_file = find_cache_for_topic(topic_key, topic_name=topic_display)
        if not cache_file:
            print(f"  Skipping {topic_key}: no cache file found")
            continue

        with open(cache_file) as f:
            cache_data = json.load(f)

        stock_link = f"{topic_key}_stock.html"
        questions_path = output_dir / f"{topic_key}_questions.html"
        render_questions_html(cache_data, questions_path,
                              topic_display=topic_display,
                              stock_link=stock_link)
        print(f"  {topic_display}: {len(cache_data.get('answer_matches', {}).get('tossups', []))}T "
              f"{len(cache_data.get('answer_matches', {}).get('bonuses', []))}B "
              f"-> {questions_path}")
        count += 1
    print(f"Built {count} question pages")


if __name__ == "__main__":
    if len(sys.argv) == 3:
        cache_path = sys.argv[1]
        output_path = sys.argv[2]
        with open(cache_path) as f:
            data = json.load(f)
        render_questions_html(data, output_path)
        print(f"Rendered to {output_path}")
    else:
        build_all()
