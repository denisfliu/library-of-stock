"""
render_score_review.py — Generate a consolidated review page for all score clues.

Usage:
    python3 lib/render_score_review.py
    # Output: dev/score_clues_review.html
"""

import hashlib
import json
from html import escape
from pathlib import Path

OUTPUT_DIR = Path("output")
DEV_DIR = Path("dev")
OUT_FILE = DEV_DIR / "score_clues_review.html"


def collect_clues():
    """Collect all score clues with ABC notation, deduplicating by abc content."""
    seen_abc = set()
    clues = []
    for f in sorted(OUTPUT_DIR.glob("*/analysis.json")):
        data = json.load(open(f))
        topic = data.get("topic", "")
        slug = f.parent.name
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
            mtime = hashlib.md5(mp3_abs.read_bytes()).hexdigest()[:8] if mp3_abs and mp3_abs.exists() else 0
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
<script src="https://cdn.jsdelivr.net/npm/abcjs@6.4.4/dist/abcjs-basic-min.js"></script>
<style>
* {{ box-sizing: border-box; margin: 0; padding: 0; }}
body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; background: #f4f4f6; color: #1a1a2e; }}
header {{ background: #1a1a2e; color: #fff; padding: 1.2rem 2rem; display: flex; align-items: center; gap: 2rem; }}
header h1 {{ font-size: 1.3rem; font-weight: 600; }}
.back {{ font-size: 0.8rem; }}
.back a {{ color: rgba(255,255,255,0.6); text-decoration: none; }}
.back a:hover {{ color: #fff; }}
.stats {{ font-size: 0.85rem; opacity: 0.7; }}
.controls {{ margin-left: auto; display: flex; gap: 0.5rem; }}
.controls button {{ padding: 0.35rem 0.8rem; border: 1px solid rgba(255,255,255,0.3); background: transparent; color: #fff; border-radius: 4px; cursor: pointer; font-size: 0.8rem; }}
.controls button.active {{ background: #fff; color: #1a1a2e; }}
main {{ max-width: 1000px; margin: 1.5rem auto; padding: 0 1rem; display: flex; flex-direction: column; gap: 1rem; }}
.clue-card {{ background: #fff; border-radius: 8px; box-shadow: 0 1px 4px rgba(0,0,0,0.08); overflow: hidden; }}
.clue-card[hidden] {{ display: none; }}
.clue-header {{ display: flex; align-items: flex-start; justify-content: space-between; padding: 0.9rem 1.2rem 0.5rem; border-bottom: 1px solid #eee; }}
.clue-title {{ display: flex; flex-direction: column; gap: 0.2rem; }}
.topic-link {{ font-weight: 700; font-size: 1rem; color: #1a1a2e; text-decoration: none; }}
.topic-link:hover {{ text-decoration: underline; }}
.work-name {{ font-size: 0.85rem; color: #666; }}
.badge {{ font-size: 0.7rem; font-weight: 600; padding: 0.2rem 0.6rem; border-radius: 20px; white-space: nowrap; }}
.badge.review {{ background: #fff3cd; color: #856404; }}
.badge.ok {{ background: #d1e7dd; color: #0a3622; }}
.clue-body {{ display: grid; grid-template-columns: 1fr 1fr; gap: 1rem; padding: 0.8rem 1.2rem; }}
.notation svg {{ max-width: 100%; height: auto; }}
.clue-meta {{ display: flex; flex-direction: column; gap: 0.6rem; justify-content: center; }}
.description {{ font-size: 0.9rem; font-weight: 500; }}
.source-text {{ font-size: 0.82rem; color: #555; font-style: italic; line-height: 1.4; }}
audio {{ width: 100%; margin-top: 0.3rem; }}
.no-audio {{ font-size: 0.8rem; color: #999; }}
.abc-raw {{ padding: 0.5rem 1.2rem 0.8rem; border-top: 1px solid #eee; }}
.abc-raw code {{ font-size: 0.72rem; color: #888; white-space: pre-wrap; word-break: break-all; }}
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


if __name__ == "__main__":
    DEV_DIR.mkdir(exist_ok=True)
    clues = collect_clues()
    html = render(clues)
    OUT_FILE.write_text(html, encoding="utf-8")
    print(f"Written {OUT_FILE} ({len(clues)} unique clues)")
