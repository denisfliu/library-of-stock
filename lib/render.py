"""
render.py — Generate HTML study guide from analysis data.

Takes a structured analysis dict and renders it as a self-contained HTML file.
"""

import json, re
from pathlib import Path
from html import escape


def _load_crossref_index():
    """Load the topic index for inline linking."""
    idx_path = Path(__file__).parent.parent / 'output' / 'topic_index.json'
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
            target = escape(ref.get('target_topic') or name)
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
    topic_index = _load_crossref_index()
    summary = _linkify(analysis.get("summary", ""), cross_refs, self_topic)
    works = analysis.get("works", [])
    suggestions = analysis.get("recursive_suggestions", [])
    links = analysis.get("links", [])

    # Nav links
    topic_key = str(output_path.stem).replace("_stock", "")
    questions_file = f"{topic_key}_questions.html"
    cards_file = f"{topic_key}_cards.html"
    has_cards = bool(analysis.get("cards"))
    cards_secondary = f'<a href="{cards_file}">Make cards</a>' if has_cards else ""
    nav_html = (
        f'<div class="nav-bar">'
        f'<div class="nav-links">'
        f'<a href="../index.html" class="nav-home">&larr; Home</a>'
        f'<div class="nav-overflow-wrap">'
        f'<button class="nav-overflow-btn" title="More">&#9776;</button>'
        f'<div class="nav-secondary">'
        f'<a href="{questions_file}">View source questions</a>'
        f'{cards_secondary}'
        f'</div>'
        f'</div>'
        f'</div>'
        f'<div class="nav-search"></div>'
        f'</div>'
    )

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

            examples = clue.get("examples", [])
            ex_html = ""
            if examples:
                tooltip_text = " | ".join(escape(ex) for ex in examples[:3])
                ex_html = f'<span class="ex-icon" title="Examples">&#x1f4ac;<span class="ex-tooltip">{tooltip_text}</span></span>'

            clues_html += f"""
            <tr class="clue-row">
                <td class="clue-freq">{freq}x</td>
                <td class="clue-body">
                    <span class="clue-text">{escape(clue.get("clue", ""))}</span>
                    <span class="badge {badge_class}">{tendency}</span>{ex_html}
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
        work_name_lower = work_name_raw.lower()
        for ref in cross_refs:
            ref_name = ref.get('name', '')
            if ref.get('exists') and ref_name and ref_name.lower() in work_name_lower:
                slug = ref.get('target_slug', '')
                href = f"{slug}_stock.html"
                # If the ref points to a work (not the topic itself), add anchor
                target_work = ref.get('target_work')
                if target_work:
                    anchor = re.sub(r'[^a-z0-9]+', '-', target_work.lower()).strip('-')
                    href += f"#{anchor}"
                work_link_btn = f' <a href="{href}" class="work-link-btn" title="Go to {escape(ref.get("target_topic", ""))}">&rarr;</a>'
                break
        # If no cross_ref match, check topic index directly for section names like
        # "Robert Henri (leader)" or "George Bellows" that have their own pages.
        if not work_link_btn and topic_index:
            for indexed_name, entry in topic_index.items():
                # Only match primary topic names (not aliases) and skip self
                if (entry.get('type') == 'topic'
                        and indexed_name == entry.get('topic')
                        and indexed_name.lower() != self_topic.lower()):
                    iname_lower = indexed_name.lower()
                    # Match if work name equals or starts with the indexed name
                    # (handles "Robert Henri (leader)", "Into the Woods (1987)", etc.)
                    if (work_name_lower == iname_lower
                            or work_name_lower.startswith(iname_lower + ' ')
                            or work_name_lower.startswith(iname_lower + '(')):
                        slug = entry.get('slug', '')
                        work_link_btn = f' <a href="{slug}_stock.html" class="work-link-btn" title="Go to {escape(indexed_name)}">&rarr;</a>'
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
    font-size: 0.82rem;
}}
.clue-row td {{
    padding: 0.15rem 0.4rem;
    border-top: 1px solid #2a2f37;
    vertical-align: middle;
}}
.clue-freq {{
    width: 2rem;
    text-align: center;
    color: #9aa0a7;
    font-size: 0.75rem;
    font-weight: bold;
    white-space: nowrap;
}}
.clue-body {{
    line-height: 1.35;
}}
.clue-text {{
    color: #c8ccd1;
}}
.badge {{
    font-size: 0.6rem;
    padding: 0.05rem 0.3rem;
    border-radius: 3px;
    text-transform: uppercase;
    font-weight: bold;
    white-space: nowrap;
    margin-left: 0.25rem;
    vertical-align: middle;
}}
.badge-power {{ background: #3b1c1c; color: #f08080; border: 1px solid #6b2a2a; }}
.badge-giveaway {{ background: #1c3327; color: #6bcf8e; border: 1px solid #2a6b42; }}
.badge-mid {{ background: #332b1a; color: #e0b860; border: 1px solid #6b5a2a; }}
.ex-icon {{
    display: inline-block;
    width: 1.1rem;
    text-align: center;
    font-size: 0.72rem;
    color: #555;
    cursor: pointer;
    margin-left: 0.25rem;
    vertical-align: middle;
    position: relative;
}}
.ex-icon:hover {{ color: #6b9eff; }}
.ex-icon .ex-tooltip {{
    display: none;
    position: absolute;
    bottom: 1.5rem;
    left: 50%;
    transform: translateX(-50%);
    background: #1a1f25;
    border: 1px solid #3a3f47;
    border-radius: 4px;
    padding: 0.4rem 0.6rem;
    font-size: 0.75rem;
    color: #9aa0a7;
    font-style: italic;
    font-weight: normal;
    white-space: normal;
    width: max-content;
    max-width: 350px;
    z-index: 10;
    box-shadow: 0 2px 8px rgba(0,0,0,0.4);
    text-align: left;
    line-height: 1.3;
}}
.ex-icon:hover .ex-tooltip {{ display: block; }}
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
    display: flex;
    justify-content: space-between;
    align-items: center;
    flex-wrap: wrap;
    gap: 0.3rem;
}}
.nav-bar a {{
    color: #6b9eff;
    text-decoration: none;
}}
.nav-bar a:hover {{
    text-decoration: underline;
}}
.nav-links {{
    display: flex;
    gap: 0.3rem;
    align-items: center;
}}
.nav-overflow-wrap {{
    position: relative;
    display: flex;
    align-items: center;
}}
.nav-secondary {{
    display: flex;
    align-items: center;
    gap: 0.5rem;
}}
.nav-secondary a::before {{
    content: '·';
    margin-right: 0.5rem;
    color: #555;
}}
.nav-overflow-btn {{
    display: none;
    background: #1a1f25;
    border: 1px solid #3a3f47;
    border-radius: 3px;
    color: #9aa0a7;
    font-size: 1rem;
    cursor: pointer;
    padding: 0.2rem 0.5rem;
    line-height: 1;
}}
.nav-overflow-btn:hover {{
    background: #262d37;
    color: #c8ccd1;
    border-color: #6b9eff;
}}
@media (max-width: 600px) {{
    .nav-overflow-btn {{
        display: inline-flex;
        align-items: center;
        min-height: 36px;
        margin-left: 0.4rem;
    }}
    .nav-secondary {{
        display: none;
        position: absolute;
        top: calc(100% + 4px);
        left: 0;
        flex-direction: column;
        align-items: flex-start;
        background: #1a1f25;
        border: 1px solid #3a3f47;
        border-radius: 4px;
        padding: 0.4rem 0;
        z-index: 100;
        min-width: 180px;
        box-shadow: 0 4px 12px rgba(0,0,0,0.5);
        gap: 0;
    }}
    .nav-overflow-wrap.open .nav-secondary {{
        display: flex;
    }}
    .nav-secondary a {{
        padding: 0.5rem 0.8rem;
        width: 100%;
        box-sizing: border-box;
    }}
    .nav-secondary a::before {{
        display: none;
    }}
    .nav-secondary a:hover {{
        background: #262d37;
        text-decoration: none;
    }}
    .search-nav-input {{
        width: 110px;
    }}
    .search-nav-input:focus {{
        width: 150px;
    }}
    .search-nav-random,
    .search-nav-prev,
    .search-nav-next {{
        min-height: 36px;
        padding: 0.4rem 0.6rem;
    }}
}}
/* search nav */
.search-nav {{ display: inline-block; }}
.search-nav-row {{
    display: flex;
    gap: 0.3rem;
    align-items: center;
}}
.search-nav-input-wrap {{
    position: relative;
}}
.search-nav-input {{
    width: 160px;
    padding: 0.25rem 0.5rem;
    font-size: 0.8rem;
    background: #15191e;
    color: #c8ccd1;
    border: 1px solid #3a3f47;
    border-radius: 3px;
    outline: none;
    font-family: inherit;
}}
.search-nav-input:focus {{
    border-color: #6b9eff;
    width: 220px;
}}
.search-nav-input::placeholder {{ color: #555; }}
.search-nav-dropdown {{
    display: none;
    position: absolute;
    top: 100%;
    right: 0;
    margin-top: 0.2rem;
    background: #1a1f25;
    border: 1px solid #3a3f47;
    border-radius: 4px;
    min-width: 280px;
    max-height: 350px;
    overflow-y: auto;
    z-index: 200;
    box-shadow: 0 4px 12px rgba(0,0,0,0.5);
}}
.search-nav-dropdown.open {{ display: block; }}
.search-nav-result {{
    display: flex;
    justify-content: space-between;
    align-items: baseline;
    padding: 0.4rem 0.6rem;
    color: #c8ccd1;
    text-decoration: none;
    font-size: 0.85rem;
    border-bottom: 1px solid #2a2f37;
}}
.search-nav-result:last-child {{ border-bottom: none; }}
.search-nav-result:hover, .search-nav-result.active {{
    background: #262d37;
}}
.search-nav-result-name {{
    color: #6b9eff;
}}
.search-nav-result-cat {{
    font-size: 0.72rem;
    color: #808790;
    margin-left: 0.5rem;
    white-space: nowrap;
}}
.search-nav-empty {{
    padding: 0.6rem;
    color: #555;
    font-size: 0.82rem;
    font-style: italic;
}}
.search-nav-random {{
    background: #1a1f25;
    border: 1px solid #3a3f47;
    border-radius: 3px;
    color: #9aa0a7;
    font-size: 0.85rem;
    cursor: pointer;
    padding: 0.2rem 0.4rem;
    line-height: 1;
}}
.search-nav-random:hover {{
    background: #262d37;
    color: #c8ccd1;
    border-color: #6b9eff;
}}
.search-nav-prev, .search-nav-next {{
    background: #1a1f25;
    border: 1px solid #3a3f47;
    border-radius: 3px;
    color: #9aa0a7;
    font-size: 0.85rem;
    cursor: pointer;
    padding: 0.2rem 0.5rem;
    line-height: 1;
    text-decoration: none;
    font-weight: bold;
}}
.search-nav-prev:hover, .search-nav-next:hover {{
    background: #262d37;
    color: #6b9eff;
    border-color: #6b9eff;
    text-decoration: none;
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
<script src="../output/guides_data.js"></script>
<script src="../lib/js/search_nav.js"></script>
<script>initSearchNav('.nav-search', {{ prefix: '../', currentSlug: '{topic_key}' }});</script>
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
