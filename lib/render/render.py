"""
render.py — Generate HTML study guide from analysis data.

Takes a structured analysis dict and renders it as a self-contained HTML file.
"""

import json, re, sys
from pathlib import Path
from html import escape

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from lib.common import TOPIC_INDEX_FILE, anchor_slug
from lib.render.theme import (ABCJS_SCRIPT_TAG, base_css, layout_switch_script,
                              mobile_core_css, mp3_cache_buster, nav_bar_css,
                              search_nav_css, site_nav)


def _load_crossref_index():
    """Load the topic index for inline linking."""
    if TOPIC_INDEX_FILE.exists():
        with open(TOPIC_INDEX_FILE, encoding='utf-8') as f:
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
            slug = ref.get('slug', '')
            href = f"../{slug}/stock.html"
            # If linking to a specific work within a page, add anchor
            target_work = ref.get('work')
            if target_work:
                anchor = anchor_slug(target_work)
                href += f"#{anchor}"
            replacement = f'<a href="{href}" class="crossref-inline">{name_escaped}</a>'
        else:
            target = escape(ref.get('topic') or name)
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
    topic_key = output_path.parent.name
    questions_file = "questions.html"
    cards_file = "cards.html"
    has_cards = (output_path.parent / "cards.json").exists()
    cards_secondary = f'<a href="{cards_file}">Make cards</a>' if has_cards else ""
    # Shared site bar on top (guide search + random land in .nav-search,
    # filled by lib/js/search_nav.js); the page actions sit on the h1 line.
    # .nav-overflow-* is the mobile overflow menu (toggled by search_nav.js);
    # .page-pn receives search_nav's prev/next links (moved by the page script).
    nav_html = site_nav('../../', 'wiki', '<div class="nav-search"></div>')
    overflow_icon = ('<svg width="16" height="16" viewBox="0 0 16 16" aria-hidden="true">'
                     '<path d="M2 4h12M2 8h12M2 12h12" stroke="currentColor" '
                     'stroke-width="1.6" stroke-linecap="round"/></svg>')
    head_html = (
        f'<div class="page-head">'
        f'<h1>{topic}</h1>'
        f'<div class="nav-links page-actions">'
        f'<div class="nav-overflow-wrap">'
        f'<button class="nav-overflow-btn" title="More" aria-label="More">{overflow_icon}</button>'
        f'<div class="nav-secondary">'
        f'<a href="{questions_file}">View source questions</a>'
        f'{cards_secondary}'
        f'</div>'
        f'</div>'
        f'<span class="page-pn"></span>'
        f'</div>'
        f'</div>'
    )

    # Build score_clues lookup: work_name → list of clues with abc/mp3
    score_clips_by_work: dict[str, list] = {}
    for sc in analysis.get("score_clues", []):
        if sc.get("abc") or sc.get("mp3"):
            score_clips_by_work.setdefault(sc["work"], []).append(sc)

    has_score_clips = bool(score_clips_by_work)

    def _score_clip_html(clip: dict) -> str:
        """Render a single score clip as an inline block."""
        # html.escape preserves newlines, so dataset.abc yields real ABC
        # line breaks (same as the JSON path in render_cards.py).
        abc_attr = escape(clip.get("abc", ""))
        mp3 = clip.get("mp3", "")
        review_badge = ' <span class="review-badge" title="ABC needs review">⚠</span>' if clip.get("needs_review") else ""
        audio_el = ""
        if mp3:
            mp3_path = output_path.parent / mp3
            mp3_src = f"{escape(mp3)}?v={mp3_cache_buster(mp3_path)}"
            audio_el = f'<audio controls preload="none" src="{mp3_src}" style="height:24px;vertical-align:middle;margin-left:0.4rem;"></audio>'
        return (f'<div class="score-clip" data-abc="{abc_attr}">'
                f'<div class="score-clip-header">'
                f'<span class="score-clip-label">Score clip{review_badge}</span>{audio_el}'
                f'</div>'
                f'<div class="score-notation"></div>'
                f'</div>')

    works_html = ""
    for i, work in enumerate(works):
        # Pre-match score clips to clue indices by source_text word overlap
        work_name = work.get("name", "")
        work_clips = []
        for clip_work, clips in score_clips_by_work.items():
            if clip_work == work_name or clip_work in work_name or work_name.startswith(clip_work):
                work_clips.extend(clips)
        clue_list = work.get("clues", [])
        clip_for_clue: dict[int, list] = {}  # clue_idx → [clips]
        unmatched_clips = []
        for clip in work_clips:
            src_words = {w for w in re.sub(r'[^\w\s]', ' ', clip.get("source_text", "").lower()).split() if len(w) > 2}
            best_idx, best_overlap = -1, 0
            for ci, clue in enumerate(clue_list):
                clue_words = {w for w in re.sub(r'[^\w\s]', ' ', clue.get("clue", "").lower()).split() if len(w) > 2}
                overlap = len(src_words & clue_words)
                if overlap > best_overlap:
                    best_overlap, best_idx = overlap, ci
            if best_overlap >= 2:
                clip_for_clue.setdefault(best_idx, []).append(clip)
            else:
                unmatched_clips.append(clip)

        clues_html = ""
        for ci, clue in enumerate(clue_list):
            freq = clue.get("frequency", 1)
            # Old schema uses string frequencies ("very common", "common")
            freq_display = f"{freq}\u00d7" if isinstance(freq, int) else str(freq)
            # Old schema uses "power" bool; new schema uses "tendency" string
            if "tendency" in clue:
                tendency = clue["tendency"]
            elif clue.get("power"):
                tendency = "power"
            else:
                tendency = "mid"
            badge_class = {
                "power": "badge-power",
                "giveaway": "badge-giveaway",
                "mid": "badge-mid",
            }.get(tendency, "badge-mid")
            # Old schema uses "text" key; new schema uses "clue"
            clue_text = clue.get("clue") or clue.get("text", "")

            examples = clue.get("examples", [])
            ex_html = ""
            if examples:
                tooltip_text = " | ".join(escape(ex) for ex in examples[:3])
                ex_label = "example" if len(examples) == 1 else "examples"
                ex_html = (f'<span class="ex-icon" tabindex="0" role="button" title="Examples">'
                           f'{ex_label}<span class="ex-tooltip">{tooltip_text}</span></span>')

            inline_clips = "".join(_score_clip_html(c) for c in clip_for_clue.get(ci, []))
            clues_html += f"""
            <tr class="clue-row">
                <td class="clue-freq">{freq_display}</td>
                <td class="clue-body">
                    <span class="clue-text">{escape(clue_text)}</span>{inline_clips}
                </td>
                <td class="clue-ex">{ex_html}</td>
                <td class="clue-tag"><span class="badge {badge_class}">{tendency}</span></td>
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

        # Unmatched clips → spanning rows at top of table
        unmatched_rows = "".join(
            f'<tr class="clip-row"><td colspan="4">{_score_clip_html(c)}</td></tr>'
            for c in unmatched_clips
        )
        clues_table = f'<table class="clue-table">{unmatched_rows}{clues_html}</table>' if (clues_html or unmatched_rows) else ""

        # Check if this work/section links to another topic's page
        work_link_btn = ""
        work_name_raw = work.get("name", "")
        work_name_lower = work_name_raw.lower()
        for ref in cross_refs:
            ref_name = ref.get('name', '')
            if ref.get('exists') and ref_name and ref_name.lower() in work_name_lower:
                slug = ref.get('slug', '')
                href = f"../{slug}/stock.html"
                # If the ref points to a work (not the topic itself), add anchor
                target_work = ref.get('work')
                if target_work:
                    anchor = anchor_slug(target_work)
                    href += f"#{anchor}"
                work_link_btn = f' <a href="{href}" class="work-link-btn" title="Go to {escape(ref.get("topic", ""))}">&rarr;</a>'
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
                        work_link_btn = f' <a href="../{slug}/stock.html" class="work-link-btn" title="Go to {escape(indexed_name)}">&rarr;</a>'
                        break

        # Generate anchor ID from work name
        anchor_id = anchor_slug(work_name_raw)

        n_clues = len(clue_list)
        count_label = f"{n_clues} clue" + ("" if n_clues == 1 else "s") if n_clues else ""
        works_html += f"""
        <details class="work" id="{anchor_id}" open>
            <summary class="work-title"><span class="work-name">{escape(work_name_raw)}{work_link_btn}</span><span class="work-count">{count_label}</span></summary>
            <p class="work-desc">{desc}</p>
            {images_html}
            {clues_table}
        </details>
        """

    suggestions_html = ""
    if suggestions:
        items = "".join(f"<li>{escape(s)}</li>" for s in suggestions)
        suggestions_html = f"""
        <h3>Suggested deep dives</h3>
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
            <h2>Summary of facts</h2>
            {body}
        </section>
        """

    # cross_refs are used for inline linking only (no separate section).
    # Mirror-inferred neighbors (lib/crossref/infer.py) get the Related
    # strip instead — topics co-mentioned in this topic's source
    # questions that aren't already linked in the prose.
    related_html = ""
    related_path = Path(output_path).parent / "related.json"
    if related_path.exists():
        try:
            related = json.loads(related_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            related = []
        if related:
            def chip_title(r):
                if r.get("source") == "embedding":
                    return f'similar topic (cosine {r["score"]})'
                return f'co-mentioned {r["score"]}× in source questions'
            chips = "".join(
                f'<a class="related-chip" href="../{r["slug"]}/stock.html" '
                f'title="{chip_title(r)}">'
                f'{escape(r.get("topic", r["slug"]))}</a>'
                for r in related)
            related_html = f"""
        <section class="related">
            <h2>Related topics</h2>
            <div class="related-chips">{chips}</div>
        </section>
        """

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
            <h2>Further reading</h2>
            {'<ul>' + link_items + '</ul>' if link_items else ''}
            {suggestions_html}
        </section>
        """

    abcjs_script = ABCJS_SCRIPT_TAG if has_score_clips else ""

    html = f"""<!DOCTYPE html>
<html lang="en" data-layout="desktop">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
{layout_switch_script()}
{abcjs_script}
<title>Stock: {topic}</title>
<style>
{base_css(max_width='868px')}
/* page head: h1 + page actions on one line */
.page-head {{
    display: flex;
    align-items: baseline;
    gap: 0.5rem 1rem;
    flex-wrap: wrap;
    margin-top: 2.2rem;
}}
.page-head h1 {{
    font-size: 28px;
    margin: 0;
    padding: 0;
    flex: 1 1 auto;
}}
.page-head .page-actions {{
    display: flex;
    align-items: baseline;
    gap: 1.1rem;
    font-size: 14px;
    flex-wrap: wrap;
}}
.page-actions a {{ color: var(--c-link); text-decoration: none; }}
.page-actions a:hover {{ text-decoration: underline; }}
.page-pn {{ display: flex; gap: 1.1rem; }}
.page-pn a.search-nav-prev, .page-pn a.search-nav-next {{
    color: var(--c-muted);
    font-weight: normal;
    font-size: 14px;
    background: none;
    border: none;
    padding: 0;
    white-space: nowrap;
}}
.page-pn a.search-nav-prev:hover, .page-pn a.search-nav-next:hover {{
    color: var(--c-text);
    background: none;
    text-decoration: underline;
}}
.summary {{
    margin: 1rem 0 0;
    font-size: 16px;
    line-height: 1.6;
    color: var(--c-text);
}}
/* sections: heading over a rule, collapsible via <details> */
.work {{
    margin-top: 2.5rem;
}}
.work-title {{
    display: flex;
    align-items: baseline;
    justify-content: space-between;
    gap: 0.75rem;
    padding-bottom: 0.6rem;
    border-bottom: 1px solid var(--c-text);
    font-size: 17px;
    font-weight: 600;
    cursor: pointer;
    user-select: none;
    list-style: none;
    color: var(--c-bright);
}}
.work-title::-webkit-details-marker {{ display: none; }}
.work-name {{ min-width: 0; flex: 1 1 auto; }}
.work-count {{
    flex: none;
    font-size: 13px;
    font-weight: normal;
    color: var(--c-muted);
    white-space: nowrap;
}}
/* collapse chevron (CSS-drawn) after the count */
.work-title::after {{
    content: '';
    flex: none;
    align-self: center;
    width: 6px;
    height: 6px;
    margin: 0 2px 0 -2px;
    border-right: 1.5px solid var(--c-faint);
    border-bottom: 1.5px solid var(--c-faint);
    transform: translateY(-2px) rotate(45deg);
    transition: transform 0.15s;
}}
.work:not([open]) > .work-title::after {{
    transform: rotate(-45deg);
}}
.work-title:hover::after {{ border-color: var(--c-text); }}
.work:not([open]) > .work-title {{ color: var(--c-muted); border-bottom-color: var(--c-border); }}
.work-link-btn {{
    margin-left: 0.5rem;
    font-size: 14px;
    font-weight: normal;
    color: var(--c-link);
    text-decoration: none;
}}
.work-link-btn:hover {{ text-decoration: underline; }}
.work-desc {{
    margin: 0.75rem 0 0.5rem;
    color: var(--c-muted);
    font-size: 14.5px;
    line-height: 1.6;
}}
.work-desc a {{ color: var(--c-link); text-decoration: none; }}
.work-desc a:hover {{ text-decoration: underline; }}
.work-images {{
    display: flex;
    flex-wrap: wrap;
    gap: 1rem;
    margin: 0.75rem 0;
}}
.work-images img {{
    max-width: 250px;
    max-height: 280px;
    border-radius: 6px;
    object-fit: contain;
    background: var(--c-raised);
}}
.work-images figure {{ margin: 0; }}
.work-images figcaption {{
    font-size: 12.5px;
    color: var(--c-muted);
    margin-top: 0.3rem;
}}
.work-images .image-link {{
    display: flex;
    align-items: center;
    min-height: 2rem;
    font-size: 14px;
}}
.work-images .image-link a {{ color: var(--c-link); }}
/* clue rows: hairlines, freq column, text, example, tag */
.clue-table {{
    width: 100%;
    border-collapse: collapse;
    font-size: 15px;
}}
.clue-row td, .clip-row td {{
    padding: 0.5rem 0.35rem;
    border-top: 1px solid var(--c-border);
    vertical-align: baseline;
}}
.clue-row:hover td {{ background: var(--c-hover); }}
.clue-row td:first-child {{ border-radius: 8px 0 0 8px; }}
.clue-row td:last-child {{ border-radius: 0 8px 8px 0; }}
.clue-freq {{
    width: 2.4rem;
    text-align: right;
    color: var(--c-muted);
    font-size: 13px;
    white-space: nowrap;
    font-variant-numeric: tabular-nums;
    padding-right: 0.6rem !important;
}}
.clue-body {{
    line-height: 1.5;
}}
.clue-text {{
    color: var(--c-text);
}}
.clue-ex {{ width: 1%; white-space: nowrap; text-align: right; }}
.clue-tag {{ width: 1%; white-space: nowrap; text-align: right; }}
.badge {{
    display: inline-block;
    font-size: 12px;
    line-height: 1.5;
    padding: 0 0.45rem;
    border-radius: 99px;
    white-space: nowrap;
}}
.badge-giveaway {{ background: var(--c-winbg); color: var(--c-winfg); font-weight: 600; }}
.badge-mid {{ color: var(--c-muted); box-shadow: inset 0 0 0 1px var(--c-border); }}
.badge-power {{ color: var(--c-warn); box-shadow: inset 0 0 0 1px var(--c-warn); }}
/* "example(s)" affordance: shows on row hover/focus on desktop; the
   tooltip carries up to three source sentences. */
.ex-icon {{
    position: relative;
    display: inline-block;
    font-size: 13px;
    color: var(--c-link);
    cursor: pointer;
    opacity: 0;
    outline: none;
}}
.clue-row:hover .ex-icon, .ex-icon:focus, .ex-icon.open {{ opacity: 1; }}
.ex-icon:hover, .ex-icon:focus-visible {{ text-decoration: underline; }}
.ex-icon .ex-tooltip {{
    display: none;
    position: absolute;
    bottom: calc(100% + 6px);
    right: 0;
    background: var(--c-input);
    border: 1px solid var(--c-border);
    border-radius: 8px;
    padding: 0.55rem 0.75rem;
    font-size: 13px;
    color: var(--c-text);
    font-style: italic;
    font-weight: normal;
    white-space: normal;
    width: max-content;
    max-width: 380px;
    z-index: 10;
    box-shadow: 0 6px 20px rgba(0,0,0,0.14);
    text-align: left;
    line-height: 1.45;
    cursor: default;
}}
.ex-icon:hover .ex-tooltip, .ex-icon:focus .ex-tooltip, .ex-icon.open .ex-tooltip {{ display: block; }}
/* trailing sections share the heading-over-rule look */
.comp-summary, .related, .links {{ margin-top: 2.5rem; }}
.comp-summary h2, .related h2, .links h2, .links h3 {{
    font-size: 17px;
    font-weight: 600;
    padding-bottom: 0.6rem;
    margin-bottom: 0.75rem;
    border-bottom: 1px solid var(--c-text);
    color: var(--c-bright);
}}
.links h3 {{ margin-top: 1.5rem; }}
.links ul {{
    margin: 0 0 0 1.25rem;
    padding: 0;
    font-size: 15px;
}}
.links li {{ margin-bottom: 0.25rem; }}
.links a {{ color: var(--c-link); text-decoration: none; }}
.links a:hover {{ text-decoration: underline; }}
.crossref-inline {{
    color: var(--c-link);
    text-decoration: none;
}}
.crossref-inline:hover {{ text-decoration: underline; }}
.crossref-inline-red {{
    color: var(--c-bad);
    border-bottom: 1px dotted var(--c-bad);
    cursor: default;
}}
.related-chips {{ display: flex; flex-wrap: wrap; gap: 0.4rem; }}
.related-chip {{
    border: 1px solid var(--c-border);
    border-radius: 99px;
    color: var(--c-text);
    font-size: 13.5px;
    padding: 0.2rem 0.75rem;
    text-decoration: none;
    white-space: nowrap;
}}
.related-chip:hover {{ border-color: var(--c-link); color: var(--c-link); background: var(--c-hover); text-decoration: none; }}
.comp-summary p {{
    font-size: 15px;
    color: var(--c-text);
    margin-bottom: 0.75rem;
    line-height: 1.65;
}}
.comp-summary p:last-child {{ margin-bottom: 0; }}
{nav_bar_css()}
.site-nav .nav-search {{ display: flex; align-items: center; }}
.nav-overflow-wrap {{
    position: relative;
    display: flex;
    align-items: baseline;
}}
.nav-secondary {{
    display: flex;
    align-items: baseline;
    gap: 1.1rem;
}}
.nav-overflow-btn {{
    display: none;
    background: none;
    border: 1px solid var(--c-border);
    border-radius: 8px;
    color: var(--c-muted);
    cursor: pointer;
    padding: 0.3rem 0.5rem;
    line-height: 0;
}}
.nav-overflow-btn:hover {{
    background: var(--c-hover);
    color: var(--c-text);
}}
/* Mobile layout — keyed on html[data-layout="mobile"], set by the head
   script from theme.layout_switch_script (MOBILE_MQ is the one breakpoint). */
html[data-layout="mobile"] .page-head {{ margin-top: 1.2rem; align-items: center; }}
html[data-layout="mobile"] .page-head h1 {{ font-size: 24px; flex-basis: 100%; }}
html[data-layout="mobile"] .page-actions {{ align-items: center; width: 100%; }}
html[data-layout="mobile"] .page-pn {{ margin-left: auto; }}
html[data-layout="mobile"] .page-pn a {{ display: inline-flex; align-items: center; min-height: 40px; }}
html[data-layout="mobile"] .nav-overflow-wrap {{ align-items: center; }}
html[data-layout="mobile"] .nav-overflow-btn {{
    display: inline-flex;
    align-items: center;
    min-height: 40px;
    min-width: 40px;
    justify-content: center;
}}
html[data-layout="mobile"] .nav-secondary {{
    display: none;
    position: absolute;
    top: calc(100% + 4px);
    left: 0;
    flex-direction: column;
    align-items: flex-start;
    background: var(--c-input);
    border: 1px solid var(--c-border);
    border-radius: 8px;
    padding: 0.35rem 0;
    z-index: 100;
    min-width: 200px;
    box-shadow: 0 8px 24px rgba(0,0,0,0.16);
    gap: 0;
}}
html[data-layout="mobile"] .nav-overflow-wrap.open .nav-secondary {{
    display: flex;
}}
html[data-layout="mobile"] .nav-secondary a {{
    padding: 0.6rem 0.9rem;
    width: 100%;
    box-sizing: border-box;
}}
html[data-layout="mobile"] .nav-secondary a:hover {{
    background: var(--c-hover);
    text-decoration: none;
}}
html[data-layout="mobile"] .search-nav-input {{
    width: 130px;
}}
html[data-layout="mobile"] .search-nav-input:focus {{
    width: 170px;
}}
html[data-layout="mobile"] .search-nav-random {{
    min-height: 40px;
    padding: 0.4rem 0.7rem;
}}
html[data-layout="mobile"] .search-nav-dropdown {{
    min-width: 0;
    width: min(320px, calc(100vw - 1.5rem));
}}
/* Clue rows on phones: freq + text on the first line, then the example
   link and tag on a second line. Hover has no meaning on touch, so the
   example link is always visible and a tap toggles .open
   (lib/js/mobile.js losTapTooltips); the tooltip becomes a small fixed
   panel at the bottom of the viewport — anchored tooltips clip on narrow
   screens. */
html[data-layout="mobile"] .clue-table, html[data-layout="mobile"] .clue-table tbody {{ display: block; }}
html[data-layout="mobile"] .clue-row {{
    display: grid;
    grid-template-columns: 2.2rem minmax(0, 1fr) auto;
    column-gap: 0.5rem;
    border-top: 1px solid var(--c-border);
    padding: 0.55rem 0;
}}
html[data-layout="mobile"] .clue-row td {{ border: none; padding: 0; background: none; }}
html[data-layout="mobile"] .clue-row:hover td {{ background: none; }}
html[data-layout="mobile"] .clue-freq {{ grid-row: 1; grid-column: 1; padding-right: 0 !important; width: auto; }}
html[data-layout="mobile"] .clue-body {{ grid-row: 1; grid-column: 2 / -1; }}
html[data-layout="mobile"] .clue-ex {{ grid-row: 2; grid-column: 2; text-align: left; width: auto; align-self: center; }}
html[data-layout="mobile"] .clue-tag {{ grid-row: 2; grid-column: 3; width: auto; align-self: center; }}
html[data-layout="mobile"] .clue-ex:empty + .clue-tag {{ padding: 0.3rem 0 0; }}
html[data-layout="mobile"] .clip-row {{ display: block; }}
html[data-layout="mobile"] .clip-row td {{ display: block; padding: 0.4rem 0; }}
html[data-layout="mobile"] .ex-icon {{
    opacity: 1;
    min-height: 32px;
    display: inline-flex;
    align-items: center;
}}
html[data-layout="mobile"] .ex-icon:hover:not(.open) .ex-tooltip,
html[data-layout="mobile"] .ex-icon:focus:not(.open) .ex-tooltip {{ display: none; }}
html[data-layout="mobile"] .ex-icon.open .ex-tooltip {{
    display: block;
    position: fixed;
    left: 0.7rem;
    right: 0.7rem;
    bottom: 0.7rem;
    top: auto;
    transform: none;
    width: auto;
    max-width: none;
    max-height: 45vh;
    overflow-y: auto;
    padding: 0.75rem 0.95rem;
    font-size: 14px;
    z-index: 300;
    box-shadow: 0 -4px 20px rgba(0,0,0,0.25);
}}
html[data-layout="mobile"] .work-images img {{
    max-width: 100%;
}}
html[data-layout="mobile"] .related-chip {{
    padding: 0.4rem 0.85rem;
    font-size: 14px;
}}
{search_nav_css()}
.search-nav-random {{ font-size: 14px; padding: 0.3rem 0.75rem; color: var(--c-link); }}
.search-nav-input {{ font-size: 14px; padding: 0.3rem 0.6rem; }}
.search-nav-prev, .search-nav-next {{
    color: var(--c-muted);
    text-decoration: none;
}}
.score-clip {{
    margin: 0.5rem 0 0.25rem;
    background: var(--c-raised);
    border-radius: 8px;
    padding: 0.55rem 0.75rem;
}}
.score-clip-header {{
    display: flex;
    align-items: center;
    gap: 0.7rem;
    margin-bottom: 0.35rem;
    flex-wrap: wrap;
}}
.score-clip-label {{
    font-size: 13px;
    color: var(--c-muted);
}}
.review-badge {{
    font-size: 12px;
    color: var(--c-warn);
}}
.score-notation svg {{
    max-width: 100%;
}}
.score-notation .abcjs-staff path {{
    fill: var(--c-text);
    stroke: var(--c-text);
}}
{mobile_core_css()}
</style>
</head>
<body>
{nav_html}
{head_html}
<div class="summary">{summary}</div>
{works_html}
{comp_summary_html}
{related_html}
{links_html}
<script src="../../output/guides_data.js"></script>
<script src="../../lib/js/mobile.js"></script>
<script src="../../lib/js/search_nav.js"></script>
<script>initSearchNav('.nav-search', {{ prefix: '../../', currentSlug: '{topic_key}' }});
losTapTooltips('.ex-icon');
(function () {{
    // Page-level restyle of the shared search_nav widget: prev/next move to
    // the page actions on the h1 line (titles kept), Random gets a text label.
    var pn = document.querySelector('.page-pn');
    var prev = document.querySelector('.nav-search .search-nav-prev');
    var next = document.querySelector('.nav-search .search-nav-next');
    if (pn && prev) {{ prev.textContent = '\u2190 Previous'; pn.appendChild(prev); }}
    if (pn && next) {{ next.textContent = 'Next \u2192'; pn.appendChild(next); }}
    var rnd = document.querySelector('.nav-search .search-nav-random');
    if (rnd) rnd.textContent = 'Random';
}})();</script>
{f'''<script>
// Render ABC notation for all score clips
document.querySelectorAll('.score-clip').forEach(function(clip) {{
    var abc = clip.dataset.abc;
    var el = clip.querySelector('.score-notation');
    if (abc && el && typeof ABCJS !== 'undefined') {{
        ABCJS.renderAbc(el, abc, {{ responsive: 'resize', staffwidth: 340, scale: 0.85,
            paddingright: 0, paddingleft: 0, stafflineThickness: 1.5,
            foregroundColor: 'var(--c-text)' }});
    }}
}});


</script>''' if has_score_clips else ''}
</body>
</html>"""

    output_path.parent.mkdir(exist_ok=True)
    with open(output_path, "w", encoding='utf-8') as f:
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
