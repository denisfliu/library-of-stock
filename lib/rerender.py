"""
rerender.py — Parse existing HTML guides and re-render them with the updated render.py template.

Extracts analysis dicts from the old HTML format and passes them through render_html().
Also saves the extracted analysis dicts as JSON for future re-rendering.
"""

import json
import re
from html import unescape
from pathlib import Path
from render import render_html


def extract_analysis_from_html(html: str) -> dict:
    """Parse the old-format HTML and extract a structured analysis dict."""

    # Extract topic from <title>Stock: TOPIC</title>
    m = re.search(r'<title>Stock:\s*(.+?)</title>', html)
    topic = unescape(m.group(1).strip()) if m else "Unknown"

    # Extract summary from <div class="summary">...</div>
    m = re.search(r'<div class="summary">(.*?)</div>', html, re.DOTALL)
    summary = unescape(m.group(1).strip()) if m else ""

    # Extract works from <details class="work" ...> blocks
    works = []
    work_blocks = re.findall(
        r'<details class="work"[^>]*>(.*?)</details>',
        html, re.DOTALL
    )

    for block in work_blocks:
        # Work name from <summary class="work-title">
        m = re.search(r'<summary class="work-title">(.*?)</summary>', block, re.DOTALL)
        work_name = unescape(m.group(1).strip()) if m else ""

        # Work description from <p class="work-desc">
        m = re.search(r'<p class="work-desc">(.*?)</p>', block, re.DOTALL)
        work_desc = m.group(1).strip() if m else ""

        # Extract images from <div class="work-images">
        images = []
        images_block = re.search(r'<div class="work-images">(.*?)</div>\s*(?=<div class="clue"|<table|$)', block, re.DOTALL)
        if images_block:
            # Find <figure> elements with <img> tags
            for fig in re.finditer(r'<figure(?:\s[^>]*)?>(.+?)</figure>', images_block.group(1), re.DOTALL):
                fig_content = fig.group(1)
                img_m = re.search(r'<img\s+src="([^"]*)"[^>]*>', fig_content)
                cap_m = re.search(r'<figcaption>(.*?)</figcaption>', fig_content, re.DOTALL)
                link_m = re.search(r'<a\s+href="([^"]*)"[^>]*><img', fig_content)

                img_data = {}
                if img_m:
                    img_data["url"] = unescape(img_m.group(1))
                else:
                    img_data["url"] = ""
                if cap_m:
                    img_data["caption"] = unescape(cap_m.group(1).strip())
                else:
                    img_data["caption"] = ""
                if link_m:
                    img_data["link"] = unescape(link_m.group(1))
                else:
                    img_data["link"] = ""
                images.append(img_data)

            # Find image-link figures (no embedded image)
            for fig in re.finditer(r'<figure class="image-link">\s*<a href="([^"]*)"[^>]*>View:\s*(.*?)</a>', images_block.group(1), re.DOTALL):
                images.append({
                    "url": "",
                    "link": unescape(fig.group(1)),
                    "caption": unescape(fig.group(2).strip()),
                })

        # Extract clues from <div class="clue"> blocks
        clues = []
        clue_blocks = re.findall(r'<div class="clue">(.*?)</div>\s*(?=<div class="clue">|</details>)', block, re.DOTALL)

        # More robust: find all clue divs
        if not clue_blocks:
            # Try splitting on clue boundaries
            clue_blocks = re.findall(r'<div class="clue">(.+?)(?=<div class="clue">|</details>)', block, re.DOTALL)

        for clue_block in clue_blocks:
            # Clue text
            m = re.search(r'<span class="clue-text">(.*?)</span>', clue_block, re.DOTALL)
            clue_text = unescape(m.group(1).strip()) if m else ""

            # Tendency badge
            m = re.search(r'<span class="badge badge-(\w+)">', clue_block)
            tendency = m.group(1) if m else "mid"

            # Frequency from "Appears ~Nx"
            m = re.search(r'Appears ~(\d+)x', clue_block)
            frequency = int(m.group(1)) if m else 1

            # Examples from <blockquote class="example">
            examples = []
            for ex_m in re.finditer(r'<blockquote class="example">(.*?)</blockquote>', clue_block, re.DOTALL):
                examples.append(unescape(ex_m.group(1).strip()))

            clues.append({
                "clue": clue_text,
                "frequency": frequency,
                "tendency": tendency,
                "examples": examples,
            })

        work_data = {
            "name": work_name,
            "description": work_desc,
            "clues": clues,
        }
        if images:
            work_data["images"] = images

        works.append(work_data)

    # Extract suggestions
    suggestions = []
    sugg_m = re.search(r'<section class="suggestions">.*?<ul>(.*?)</ul>', html, re.DOTALL)
    if sugg_m:
        for li in re.finditer(r'<li>(.*?)</li>', sugg_m.group(1), re.DOTALL):
            suggestions.append(unescape(li.group(1).strip()))

    # Extract links
    links = []
    links_m = re.search(r'<section class="links">.*?<ul>(.*?)</ul>', html, re.DOTALL)
    if links_m:
        for li in re.finditer(r'<a href="([^"]*)"[^>]*>(.*?)</a>', links_m.group(1), re.DOTALL):
            links.append({
                "url": unescape(li.group(1)),
                "text": unescape(li.group(2).strip()),
            })

    return {
        "topic": topic,
        "summary": summary,
        "works": works,
        "recursive_suggestions": suggestions,
        "links": links,
    }


def main():
    import sys
    force = "--force" in sys.argv
    output_dir = Path("output")

    # Re-render ONLY from analysis JSON — the JSON is the source of truth.
    # Never extract from HTML or overwrite the JSON.
    count = 0
    skipped_up_to_date = 0
    skipped_orphan = 0
    for json_path in sorted(output_dir.glob("*/analysis.json")):
        stock_path = json_path.parent / "stock.html"

        # Incremental: skip if HTML is newer than JSON (unless --force)
        if not force and stock_path.exists() and stock_path.stat().st_mtime >= json_path.stat().st_mtime:
            skipped_up_to_date += 1
            continue

        with open(json_path) as f:
            analysis = json.load(f)

        total_clues = sum(len(w.get("clues", [])) for w in analysis.get("works", []))
        total_images = sum(len(w.get("images", [])) for w in analysis.get("works", []))
        topic = analysis.get("topic", "?")
        print(f"  {topic}: {len(analysis.get('works', []))} works, {total_clues} clues, {total_images} images")

        render_html(analysis, stock_path)
        count += 1

    # Warn about orphaned HTML files with no JSON
    for html_path in sorted(output_dir.glob("*/stock.html")):
        json_path = html_path.parent / "analysis.json"
        if not json_path.exists():
            print(f"  WARNING: {html_path.parent.name}/stock.html has no analysis.json — skipped")
            skipped_orphan += 1

    parts = [f"Re-rendered {count} guides"]
    if skipped_up_to_date:
        parts.append(f"{skipped_up_to_date} up-to-date")
    if skipped_orphan:
        parts.append(f"{skipped_orphan} orphaned HTML")
    print(f"\nDone! {', '.join(parts)}.")


if __name__ == "__main__":
    main()
