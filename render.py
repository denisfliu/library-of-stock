"""
render.py — Generate HTML study guide from analysis data.

Takes a structured analysis dict and renders it as a self-contained HTML file.
"""

import json, re
from pathlib import Path
from html import escape


def _load_crossref_index():
    """Load the topic index for inline linking."""
    idx_path = Path(__file__).parent / 'output' / 'topic_index.json'
    if idx_path.exists():
        with open(idx_path) as f:
            return json.load(f)
    return {}


def _linkify(text, cross_refs, self_topic, escaped=True):
    """Replace cross-ref names in text with hyperlinks.

    Blue links for existing pages, red spans for future pages.
    Only replaces names listed in cross_refs (LLM-curated, not regex guessing).
    """
    if not cross_refs:
        return escape(text) if escaped else text

    if escaped:
        text = escape(text)

    # Sort by name length descending so longer matches take priority
    refs_sorted = sorted(cross_refs, key=lambda r: len(r.get('name', '')), reverse=True)

    replaced = set()  # track what we've already linked (only link first occurrence)
    for ref in refs_sorted:
        name = ref.get('name', '')
        if not name or name in replaced:
            continue

        # Escape the name for HTML context
        name_escaped = escape(name) if escaped else name

        # Match whole word (case-insensitive)
        pattern = r'(?<![/>])(\b' + re.escape(name_escaped) + r'\b)(?![^<]*>)'

        if ref.get('exists'):
            slug = ref.get('target_slug', '')
            href = f"{slug}_stock.html"
            # If linking to a specific work within a page, add anchor
            target_work = ref.get('target_work')
            if target_work:
                anchor = re.sub(r'[^a-z0-9]+', '-', target_work.lower()).strip('-')
                href += f"#{anchor}"
            replacement = f'<a href="{href}" class="crossref-inline">{name_escaped}</a>'
        else:
            target = escape(ref.get('target_topic', name))
            replacement = f'<span class="crossref-inline-red" title="No page yet: {target}">{name_escaped}</span>'

        new_text, count = re.subn(pattern, replacement, text, count=1, flags=re.IGNORECASE)
        if count > 0:
            text = new_text
            replaced.add(name)

    return text


def render_html(analysis: dict, output_path: str | Path) -> Path:
    """
    Render an analysis dict to a self-contained HTML file.

    Expected analysis structure:
    {
        "topic": "Smetana",
        "summary": "...",
        "works": [
            {
                "name": "Ma vlast",
                "description": "...",
                "clues": [
                    {
                        "clue": "Two flutes represent the river",
                        "frequency": 5,
                        "tendency": "giveaway",  # or "power" or "mid"
                        "examples": ["Two flutes play swirling...", "..."],
                    },
                    ...
                ],
            },
            ...
        ],
        "recursive_suggestions": ["The Moldau", "From My Life", ...],
        "comprehensive_summary": "Paragraph(s) synthesizing all facts from the clues...",
        "links": [{"text": "...", "url": "..."}, ...],
    }
    """
    output_path = Path(output_path)
    topic = escape(analysis.get("topic", "Unknown"))
    cross_refs = analysis.get("cross_refs", [])
    self_topic = analysis.get("topic", "")
    summary = _linkify(analysis.get("summary", ""), cross_refs, self_topic)
    works = analysis.get("works", [])
    suggestions = analysis.get("recursive_suggestions", [])
    links = analysis.get("links", [])

    # Nav links
    topic_key = str(output_path.stem).replace("_stock", "")
    questions_file = f"{topic_key}_questions.html"
    cards_file = f"{topic_key}_cards.html"
    has_cards = bool(analysis.get("cards"))
    cards_link = f' · <a href="{cards_file}">Make cards</a>' if has_cards else ""
    nav_html = f'<div class="nav-bar"><a href="../index.html">← Home</a> · <a href="{questions_file}">View source questions</a>{cards_link}</div>'

    works_html = ""
    for i, work in enumerate(works):
        clues_html = ""
        for clue in work.get("clues", []):
            freq = clue.get("frequency", 1)
            tendency = clue.get("tendency", "mid")
            badge_class = {
                "power": "badge-power",
                "giveaway": "badge-giveaway",
                "mid": "badge-mid",
            }.get(tendency, "badge-mid")

            examples_items = ""
            for ex in clue.get("examples", []):
                examples_items += f'<li>{escape(ex)}</li>'

            clues_html += f"""
            <tr class="clue-row">
                <td class="clue-freq">{freq}x</td>
                <td class="clue-body">
                    <span class="clue-text">{escape(clue.get("clue", ""))}</span>
                    <span class="badge {badge_class}">{tendency}</span>
                    <details class="examples"><summary>examples</summary><ul>{examples_items}</ul></details>
                </td>
            </tr>
            """

        # description allows raw HTML (for image links, etc.)
        # Apply cross-ref linking (escaped=False since desc may contain HTML)
        desc = _linkify(work.get("description", ""), cross_refs, self_topic, escaped=False)

        # Render images if provided
        images_html = ""
        if work.get("images"):
            figures = ""
            for img in work["images"]:
                caption = escape(img.get("caption", ""))
                src = escape(img["url"])
                link = img.get("link", "")
                if src:
                    # Embedded image, optionally wrapped in a link
                    img_tag = f'<img src="{src}" alt="{caption}" loading="lazy">'
                    if link:
                        img_tag = f'<a href="{escape(link)}" target="_blank">{img_tag}</a>'
                    figures += f"""
                    <figure>
                        {img_tag}
                        <figcaption>{caption}</figcaption>
                    </figure>
                    """
                elif link:
                    # No embeddable image — show a styled link instead
                    figures += f"""
                    <figure class="image-link">
                        <a href="{escape(link)}" target="_blank">View: {caption}</a>
                    </figure>
                    """
            images_html = f'<div class="work-images">{figures}</div>'

        clues_table = f'<table class="clue-table">{clues_html}</table>' if clues_html else ""

        # Check if this work/section links to another topic's page
        work_link_btn = ""
        work_name_raw = work.get("name", "")
        for ref in cross_refs:
            ref_name = ref.get('name', '')
            if ref.get('exists') and ref_name and ref_name.lower() in work_name_raw.lower():
                slug = ref.get('target_slug', '')
                href = f"{slug}_stock.html"
                # If the ref points to a work (not the topic itself), add anchor
                target_work = ref.get('target_work')
                if target_work:
                    anchor = re.sub(r'[^a-z0-9]+', '-', target_work.lower()).strip('-')
                    href += f"#{anchor}"
                work_link_btn = f' <a href="{href}" class="work-link-btn" title="Go to {escape(ref.get("target_topic", ""))}">&rarr;</a>'
                break

        # Generate anchor ID from work name
        anchor_id = re.sub(r'[^a-z0-9]+', '-', work_name_raw.lower()).strip('-')

        works_html += f"""
        <details class="work" id="{anchor_id}" open>
            <summary class="work-title">{escape(work_name_raw)}{work_link_btn}</summary>
            <p class="work-desc">{desc}</p>
            {images_html}
            {clues_table}
        </details>
        """

    suggestions_html = ""
    if suggestions:
        items = "".join(f"<li>{escape(s)}</li>" for s in suggestions)
        suggestions_html = f"""
        <h3>Suggested Deep Dives</h3>
        <ul>{items}</ul>
        """

    comp_summary = analysis.get("comprehensive_summary", "")
    comp_summary_html = ""
    if comp_summary:
        # Support multiple paragraphs separated by newlines
        paragraphs = [p.strip() for p in comp_summary.split("\n\n") if p.strip()]
        body = "".join(f"<p>{_linkify(p, cross_refs, self_topic)}</p>" for p in paragraphs)
        comp_summary_html = f"""
        <section class="comp-summary">
            <h2>Summary of Facts</h2>
            {body}
        </section>
        """

    # cross_refs are used for inline linking only (no separate section)

    links_html = ""
    if links or suggestions:
        link_items = ""
        if links:
            link_items = "".join(
                f'<li><a href="{escape(l["url"])}" target="_blank">{escape(l["text"])}</a></li>'
                for l in links
            )
        links_html = f"""
        <section class="links">
            <h2>Further Reading</h2>
            {'<ul>' + link_items + '</ul>' if link_items else ''}
            {suggestions_html}
        </section>
        """

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Stock: {topic}</title>
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
.summary {{
    background: #1a1f25;
    border: 1px solid #3a3f47;
    padding: 0.6rem 1rem;
    margin-bottom: 1.2rem;
    font-size: 0.92rem;
    color: #9aa0a7;
}}
.work {{
    border: 1px solid #3a3f47;
    margin-bottom: 1rem;
    background: #1a1f25;
}}
.work-title {{
    font-size: 1rem;
    font-weight: bold;
    cursor: pointer;
    padding: 0.4rem 0.8rem;
    background: #1f252d;
    border-bottom: 1px solid #3a3f47;
    user-select: none;
    list-style: none;
    color: #e0e0e0;
}}
.work-title::-webkit-details-marker {{ display: none; }}
.work-title::before {{
    content: '\u25b6';
    font-size: 0.65rem;
    margin-right: 0.5rem;
    display: inline-block;
    transition: transform 0.15s;
    color: #9aa0a7;
}}
.work[open] > .work-title::before {{
    transform: rotate(90deg);
}}
.work-title:hover {{
    background: #262d37;
}}
.work-link-btn {{
    float: right;
    padding: 0.1rem 0.5rem;
    font-size: 0.8rem;
    color: #6b9eff;
    border: 1px solid #2a4060;
    border-radius: 3px;
    text-decoration: none;
    background: #1a2535;
    margin-left: 0.5rem;
}}
.work-link-btn:hover {{
    background: #223050;
    text-decoration: none;
}}
.work-desc {{
    padding: 0.3rem 0.8rem;
    color: #9aa0a7;
    font-size: 0.85rem;
    border-bottom: 1px solid #2a2f37;
}}
.work-desc a {{ color: #6b9eff; text-decoration: none; }}
.work-desc a:hover {{ text-decoration: underline; }}
.work-images {{
    display: flex;
    flex-wrap: wrap;
    gap: 0.8rem;
    padding: 0.5rem 0.8rem;
    border-bottom: 1px solid #2a2f37;
}}
.work-images img {{
    max-width: 250px;
    max-height: 280px;
    border: 1px solid #3a3f47;
    object-fit: contain;
    background: #15191e;
}}
.work-images figure {{ margin: 0; }}
.work-images figcaption {{
    font-size: 0.75rem;
    color: #9aa0a7;
    margin-top: 0.2rem;
    text-align: center;
}}
.work-images .image-link {{
    display: flex;
    align-items: center;
    justify-content: center;
    min-width: 120px;
    min-height: 60px;
    background: #15191e;
    border: 1px dashed #3a3f47;
    padding: 0.5rem;
}}
.work-images .image-link a {{
    color: #6b9eff;
    font-size: 0.82rem;
}}
/* clue table */
.clue-table {{
    width: 100%;
    border-collapse: collapse;
    font-size: 0.88rem;
}}
.clue-row td {{
    padding: 0.25rem 0.5rem;
    border-top: 1px solid #2a2f37;
    vertical-align: top;
}}
.clue-freq {{
    width: 2.5rem;
    text-align: center;
    color: #9aa0a7;
    font-weight: bold;
    white-space: nowrap;
}}
.clue-body {{
    line-height: 1.45;
}}
.clue-text {{
    font-weight: 600;
    color: #d4d8dd;
}}
.badge {{
    font-size: 0.65rem;
    padding: 0.1rem 0.35rem;
    border-radius: 3px;
    text-transform: uppercase;
    font-weight: bold;
    white-space: nowrap;
    margin-left: 0.3rem;
    vertical-align: middle;
}}
.badge-power {{ background: #3b1c1c; color: #f08080; border: 1px solid #6b2a2a; }}
.badge-giveaway {{ background: #1c3327; color: #6bcf8e; border: 1px solid #2a6b42; }}
.badge-mid {{ background: #332b1a; color: #e0b860; border: 1px solid #6b5a2a; }}
.examples {{
    margin-top: 0.15rem;
}}
.examples summary {{
    font-size: 0.78rem;
    color: #6b9eff;
    cursor: pointer;
    display: inline;
}}
.examples summary:hover {{ text-decoration: underline; }}
.examples ul {{
    margin: 0.2rem 0 0.2rem 1.2rem;
    padding: 0;
    font-size: 0.82rem;
    color: #808790;
    font-style: italic;
}}
.examples li {{
    margin-bottom: 0.1rem;
}}
.suggestions, .links {{
    margin-top: 1.2rem;
}}
.suggestions h2, .links h2 {{
    font-family: 'Linux Libertine', Georgia, serif;
    font-size: 1.2rem;
    font-weight: normal;
    border-bottom: 1px solid #3a3f47;
    padding-bottom: 0.15rem;
    margin-bottom: 0.4rem;
    color: #e0e0e0;
}}
.suggestions ul, .links ul {{
    margin: 0 0 0 1.5rem;
    padding: 0;
    font-size: 0.88rem;
}}
.suggestions li, .links li {{
    margin-bottom: 0.15rem;
}}
.links a {{ color: #6b9eff; text-decoration: none; }}
.links a:hover {{ text-decoration: underline; }}
.crossref-inline {{
    color: #6b9eff;
    text-decoration: none;
    border-bottom: 1px dotted #6b9eff;
}}
.crossref-inline:hover {{
    text-decoration: none;
    border-bottom: 1px solid #6b9eff;
}}
.crossref-inline-red {{
    color: #cc6666;
    border-bottom: 1px dotted #cc6666;
    cursor: default;
}}
.comp-summary {{
    margin-top: 1.2rem;
    background: #1a1f25;
    border: 1px solid #3a3f47;
    padding: 0.8rem 1rem;
}}
.comp-summary h2 {{
    font-family: 'Linux Libertine', Georgia, serif;
    font-size: 1.2rem;
    font-weight: normal;
    border-bottom: 1px solid #3a3f47;
    padding-bottom: 0.15rem;
    margin-bottom: 0.5rem;
    color: #e0e0e0;
}}
.comp-summary p {{
    font-size: 0.88rem;
    color: #c8ccd1;
    margin-bottom: 0.5rem;
    line-height: 1.6;
}}
.comp-summary p:last-child {{
    margin-bottom: 0;
}}
.nav-bar {{
    margin-bottom: 0.8rem;
    font-size: 0.85rem;
}}
.nav-bar a {{
    color: #6b9eff;
    text-decoration: none;
}}
.nav-bar a:hover {{
    text-decoration: underline;
}}
</style>
</head>
<body>
<h1>{topic}</h1>
{nav_html}
<div class="summary">{summary}</div>
{works_html}
{comp_summary_html}
{links_html}
</body>
</html>"""

    output_path.parent.mkdir(exist_ok=True)
    with open(output_path, "w") as f:
        f.write(html)

    return output_path


if __name__ == "__main__":
    # Demo with sample data
    sample = {
        "topic": "Smetana",
        "summary": "Czech nationalist composer, known for the tone poem cycle Ma vlast (containing The Moldau) and the opera The Bartered Bride. Notably went deaf in 1874.",
        "works": [
            {
                "name": "Ma vlast (My Country)",
                "description": "Cycle of six symphonic/tone poems depicting Bohemia",
                "clues": [
                    {
                        "clue": "Two flutes play swirling/undulating figures representing a river",
                        "frequency": 4,
                        "tendency": "mid",
                        "examples": [
                            "Two flutes play swirling figures to represent a river in a set of six tone poems",
                            "two flutes play undulating E minor sixteenth note figures to represent waters",
                        ],
                    },
                ],
            },
        ],
        "recursive_suggestions": ["The Moldau", "From My Life (String Quartet No. 1)"],
        "links": [
            {"text": "Smetana - Wikipedia", "url": "https://en.wikipedia.org/wiki/Bed%C5%99ich_Smetana"},
        ],
    }
    path = render_html(sample, "output/smetana_demo.html")
    print(f"Demo rendered to {path}")
