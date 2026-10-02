"""
render_score_review.py — Generate a consolidated review page for all score clues.

Usage:
    python lib/render_score_review.py
    # Output: dev/score_clues_review.html
"""

import json
import sys
from html import escape
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from lib.common import OUTPUT_DIR, DEV_DIR, resolve_analyses
from lib.render.theme import (ABCJS_SCRIPT_TAG, FONT_STACK, mp3_cache_buster,
                              theme_vars_css)
OUT_FILE = DEV_DIR / "score_clues_review.html"


def collect_clues(analyses=None):
    """Collect all score clues with ABC notation, deduplicating by abc content."""
    seen_abc = set()
    clues = []
    for slug, _path, data in resolve_analyses(analyses):
        topic = data.get("topic", "")
        for i, c in enumerate(data.get("score_clues", [])):
            abc = c.get("abc")
            if not abc:
                continue
            key = abc.strip()
            if key in seen_abc:
                continue
            seen_abc.add(key)
            mp3 = c.get("mp3", "")
            # mp3 is relative to topic dir (e.g. "audio/0.mp3")
            # dev/ pages need: ../output/{slug}/audio/0.mp3
            mp3_abs = OUTPUT_DIR / slug / mp3 if mp3 else None
            # Empty string when the file is missing so the `if c["mp3_v"]`
            # check below skips emitting a broken <audio> element.
            mtime = mp3_cache_buster(mp3_abs) if mp3_abs and mp3_abs.exists() else ''
            mp3_rel = f"../output/{slug}/{mp3}" if mp3 else ""
            clues.append({
                "topic": topic,
                "slug": slug,
                "index": i,
                "work": c.get("work", ""),
                "description": c.get("description", ""),
                "source_text": c.get("source_text", ""),
                "abc": abc,
                "mp3": mp3_rel,
                "mp3_v": mtime,
                "needs_review": c.get("needs_review", False),
            })
    return clues


def render(clues):
    cards_html = []
    for idx, c in enumerate(clues):
        mp3_src = ""
        if c["mp3"] and c["mp3_v"]:
            mp3_src = f"{escape(c['mp3'])}?v={c['mp3_v']}"
        elif c["mp3"]:
            mp3_src = escape(c["mp3"])

        audio_html = (
            f'<audio controls preload="none" src="{mp3_src}"></audio>'
            if mp3_src else
            '<span class="no-audio">no MP3</span>'
        )

        badge = '<span class="badge review">needs review</span>' if c["needs_review"] else '<span class="badge ok">reviewed</span>'
        abc_id = f"abc-{idx}"
        abc_escaped = escape(c["abc"])

        cards_html.append(f"""
<div class="clue-card" id="clue-{idx}" data-needs-review="{str(c['needs_review']).lower()}">
  <div class="clue-header">
    <div class="clue-title">
      <a href="../output/{escape(c['slug'])}/stock.html" class="topic-link">{escape(c['topic'])}</a>
      <span class="work-name">{escape(c['work'])}</span>
    </div>
    {badge}
  </div>
  <div class="clue-body">
    <div class="notation" id="{abc_id}"></div>
    <div class="clue-meta">
      <div class="description">{escape(c['description'])}</div>
      <div class="source-text">"{escape(c['source_text'])}"</div>
      {audio_html}
    </div>
  </div>
  <div class="abc-raw"><code>{abc_escaped}</code></div>
</div>""")

    clues_json = json.dumps([{
        "idx": i,
        "abc": c["abc"],
        "abcId": f"abc-{i}",
    } for i, c in enumerate(clues)], ensure_ascii=False)

    total = len(clues)
    needs_review = sum(1 for c in clues if c["needs_review"])

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Score Clues Review</title>
{ABCJS_SCRIPT_TAG}
<style>
{theme_vars_css()}
* {{ box-sizing: border-box; margin: 0; padding: 0; }}
body {{ font-family: {FONT_STACK}; -webkit-font-smoothing: antialiased; background: var(--c-bg); color: var(--c-text); }}
header {{ max-width: 1000px; margin: 0 auto; padding: 1.4rem 1rem 0.9rem; display: flex; align-items: baseline; gap: 0.6rem 1.6rem; flex-wrap: wrap; border-bottom: 1px solid var(--c-border); }}
header h1 {{ font-size: 1.4rem; font-weight: 600; color: var(--c-bright); }}
.back {{ font-size: 0.85rem; }}
.back a {{ color: var(--c-muted); text-decoration: none; }}
.back a:hover {{ color: var(--c-text); }}
.stats {{ font-size: 0.85rem; color: var(--c-muted); }}
.controls {{ margin-left: auto; display: flex; gap: 0.4rem; }}
.controls button {{ font: inherit; padding: 0.25rem 0.8rem; border: 1px solid var(--c-border); background: none; color: var(--c-text); border-radius: 99px; cursor: pointer; font-size: 0.8rem; }}
.controls button:hover {{ border-color: var(--c-link); }}
.controls button.active {{ background: var(--c-pick); border-color: var(--c-pickline); font-weight: 600; }}
main {{ max-width: 1000px; margin: 1.5rem auto; padding: 0 1rem; display: flex; flex-direction: column; gap: 1rem; }}
.clue-card {{ background: var(--c-raised2); border: 1px solid var(--c-border); border-radius: 8px; overflow: hidden; }}
.clue-card[hidden] {{ display: none; }}
.clue-header {{ display: flex; align-items: flex-start; justify-content: space-between; padding: 0.9rem 1.2rem 0.5rem; border-bottom: 1px solid var(--c-line2); }}
.clue-title {{ display: flex; flex-direction: column; gap: 0.2rem; }}
.topic-link {{ font-weight: 600; font-size: 1rem; color: var(--c-link); text-decoration: none; }}
.topic-link:hover {{ text-decoration: underline; }}
.work-name {{ font-size: 0.85rem; color: var(--c-muted); }}
.badge {{ font-size: 0.7rem; font-weight: 600; padding: 0.2rem 0.6rem; border-radius: 99px; white-space: nowrap; }}
.badge.review {{ background: var(--c-hl); color: var(--c-accent); }}
.badge.ok {{ background: var(--c-winbg); color: var(--c-winfg); }}
.clue-body {{ display: grid; grid-template-columns: 1fr 1fr; gap: 1rem; padding: 0.8rem 1.2rem; }}
.notation svg {{ max-width: 100%; height: auto; color: var(--c-text); }}
/* abcjs draws in black; follow the theme's text colour instead. */
.notation svg [fill]:not([fill="none"]) {{ fill: var(--c-text); }}
.notation svg [stroke]:not([stroke="none"]) {{ stroke: var(--c-text); }}
.clue-meta {{ display: flex; flex-direction: column; gap: 0.6rem; justify-content: center; }}
.description {{ font-size: 0.9rem; font-weight: 500; }}
.source-text {{ font-size: 0.82rem; color: var(--c-muted); line-height: 1.4; }}
audio {{ width: 100%; margin-top: 0.3rem; }}
.no-audio {{ font-size: 0.8rem; color: var(--c-faint); }}
.abc-raw {{ padding: 0.5rem 1.2rem 0.8rem; border-top: 1px solid var(--c-line2); }}
.abc-raw code {{ font-size: 0.72rem; color: var(--c-faint); white-space: pre-wrap; word-break: break-all; }}
</style>
</head>
<body>
<header>
  <div class="back"><a href="../index.html">← Home</a></div>
  <h1>Score Clues Review</h1>
  <div class="stats">{total} clues &nbsp;·&nbsp; {needs_review} need review</div>
  <div class="controls">
    <button id="btn-all" class="active" onclick="filter('all')">All</button>
    <button id="btn-review" onclick="filter('review')">Needs Review</button>
    <button id="btn-ok" onclick="filter('ok')">Reviewed</button>
  </div>
</header>
<main id="main">
{''.join(cards_html)}
</main>
<script>
const CLUES = {clues_json};

function filter(mode) {{
  document.querySelectorAll('.clue-card').forEach(el => {{
    const nr = el.dataset.needsReview === 'true';
    el.hidden = (mode === 'review' && !nr) || (mode === 'ok' && nr);
  }});
  document.querySelectorAll('.controls button').forEach(b => b.classList.remove('active'));
  document.getElementById('btn-' + mode).classList.add('active');
}}

// Render ABC notation
CLUES.forEach(c => {{
  const el = document.getElementById(c.abcId);
  if (el) ABCJS.renderAbc(c.abcId, c.abc, {{ responsive: 'resize', staffwidth: 380, paddingleft: 0, paddingright: 0 }});
}});
</script>
</body>
</html>"""


def main(analyses=None):
    DEV_DIR.mkdir(exist_ok=True)
    clues = collect_clues(analyses)
    html = render(clues)
    OUT_FILE.write_text(html, encoding="utf-8")
    print(f"Written {OUT_FILE} ({len(clues)} unique clues)")


if __name__ == "__main__":
    main()
