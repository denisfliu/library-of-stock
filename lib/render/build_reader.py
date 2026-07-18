"""build_reader.py — Generate reader.html (the question reader) at repo root.

The page is a static shell: all question data is fetched at view time from
the R2 data plane (catalog.json + topics.json at boot, set shards lazily)
via lib/js/qdata.js; the app logic lives in lib/js/reader.js. Palette
matches theme.PALETTE; the question text is set in the site serif.

Usage:
    python lib/render/build_reader.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from lib.common import ROOT
from lib.render.theme import PALETTE, layout_switch_script, sheet_css


def page_html() -> str:
    p = PALETTE
    accent = '#e8b04a'
    accent_dim = '#8a6a2f'
    good = '#5dbb7a'
    bad = '#e0655f'
    return f"""<!DOCTYPE html>
<html lang="en" data-layout="desktop">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
{layout_switch_script()}
<title>Library of Stock — Reader</title>
<style>
:root {{
  color-scheme: dark;
  --bg: {p['bg']}; --raised: {p['bg_raised']}; --inset: {p['bg_input']}; --border: {p['border']};
  --text: {p['text']}; --bright: {p['text_bright']}; --muted: {p['text_muted']}; --faint: {p['text_faint']};
  --wiki: {p['link']}; --accent: {accent}; --accent-dim: {accent_dim};
  --good: {good}; --bad: {bad};
  --sans: -apple-system, 'Segoe UI', Roboto, 'Helvetica Neue', sans-serif;
  --serif: 'Linux Libertine', Georgia, serif;
}}
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
html {{ background: var(--bg); }}
body {{
  font-family: var(--sans); background: var(--bg); color: var(--text);
  font-size: 14px; line-height: 1.5; min-height: 100vh;
}}
a {{ color: var(--wiki); text-decoration: none; }}
a:hover {{ text-decoration: underline; }}
button {{ font-family: var(--sans); cursor: pointer; }}
:focus-visible {{ outline: 2px solid var(--accent); outline-offset: 1px; }}

header {{
  display: flex; align-items: baseline; gap: 1rem; flex-wrap: wrap;
  max-width: 1200px; margin: 0 auto; padding: 1.1rem 1.5rem 0.6rem;
  border-bottom: 1px solid var(--border);
}}
header h1 {{
  font-family: var(--serif); font-weight: normal; font-size: 1.45rem; color: var(--bright);
}}
header h1 .lede {{ color: var(--faint); }}
.viewtabs {{ display: flex; gap: 0.25rem; margin-left: auto; }}
.viewtabs button, .viewtabs a.tab {{
  background: none; border: 1px solid transparent; color: var(--muted);
  padding: 0.3rem 0.85rem; font-size: 0.88rem; border-radius: 3px;
}}
.viewtabs button.on {{ color: var(--bright); border-color: var(--border); background: var(--raised); }}
.viewtabs button:hover, .viewtabs a.tab:hover {{ color: var(--bright); text-decoration: none; }}
.viewtabs a.tab {{ color: var(--wiki); }}

.wrap {{ max-width: 1200px; margin: 0 auto; padding: 1.1rem 1.5rem 3rem; display: flex; gap: 1.4rem; align-items: flex-start; }}
.taphint {{ display: none; }}

/* ---------- mobile layout (html[data-layout="mobile"], set by the head
   script from theme.layout_switch_script; MOBILE_MQ is the one breakpoint).
   The rail panels are reparented into bottom sheets by reader.js
   (initMobile), the desktop .controls row is replaced by the fixed bottom
   action bar #mbar, and the timerbar node moves into the bar. ---------- */
.mchrome, #mbar {{ display: none; }}
html[data-layout="mobile"] .wrap {{
  flex-direction: column; gap: 1rem;
  padding: 0.75rem 0.8rem calc(86px + env(safe-area-inset-bottom));
}}
html[data-layout="mobile"] header {{ padding: 0.75rem 0.9rem 0.5rem; gap: 0.6rem; }}
html[data-layout="mobile"] header h1 {{ font-size: 1.2rem; }}
html[data-layout="mobile"] main {{ width: 100%; }}
html[data-layout="mobile"] aside {{ display: none; }}
html[data-layout="mobile"] .mchrome {{
  display: flex; gap: 0.5rem; max-width: 1200px; margin: 0 auto;
  padding: 0.55rem 0.9rem 0;
}}
.mchrome button {{
  flex: 1; background: var(--raised); border: 1px solid var(--border);
  color: var(--bright); border-radius: 20px; padding: 0.5rem 0.9rem;
  font-size: 0.9rem; display: flex; align-items: center; justify-content: center; gap: 0.4rem;
}}
.mchrome .mbadge {{
  background: var(--accent-dim); border: 1px solid var(--accent); color: #fff;
  border-radius: 10px; font-size: 0.74rem; padding: 0 0.45rem;
  font-variant-numeric: tabular-nums;
}}
html[data-layout="mobile"] .btn {{ padding: 0.65rem 1.25rem; font-size: 1rem; }}
html[data-layout="mobile"] .chip {{ padding: 0.4rem 0.9rem; font-size: 0.92rem; }}
html[data-layout="mobile"] .seg button {{ padding: 0.55rem 0.2rem; font-size: 0.9rem; }}
html[data-layout="mobile"] .qtext {{ font-size: 1.06rem; line-height: 1.7; padding: 0.95rem 1rem 1.05rem; min-height: 8.5rem; }}
html[data-layout="mobile"] .controls {{ display: none; }}
html[data-layout="mobile"] .kbdhint {{ display: none; }}
html[data-layout="mobile"] .taphint {{ display: block; }}
html[data-layout="mobile"] #mbar {{
  display: block; position: fixed; left: 0; right: 0; bottom: 0; z-index: 50;
  background: var(--raised); border-top: 1px solid var(--border);
  padding-bottom: env(safe-area-inset-bottom);
}}
#mbar-timer {{ display: flex; }}
#mbar-timer .timerbar {{ border-radius: 0; min-width: 0; width: 100%; }}
.mbar-btns {{ display: flex; gap: 0.5rem; padding: 0.55rem 0.7rem 0.6rem; }}
.mbar-btns .btn {{ min-height: 48px; }}
#m-main {{ flex: 1; font-weight: 600; }}
/* Rail panels lose their card chrome once inside a sheet body. */
.los-sheet-body .panel {{ border: none; background: none; padding: 0.4rem 0 0; margin: 0; }}
.los-sheet-body .distgrid input {{ min-height: 40px; }}
/* Stats view on a narrow screen */
.tablewrap {{ overflow-x: auto; -webkit-overflow-scrolling: touch; max-width: 100%; }}
html[data-layout="mobile"] .bar {{ width: 56px; }}
html[data-layout="mobile"] table.acc td, html[data-layout="mobile"] table.acc th {{ padding-left: 0.35rem; padding-right: 0.35rem; }}
html[data-layout="mobile"] .scopesel {{ flex: 1; min-width: 0; }}
{sheet_css()}

/* ---------- filter rail ---------- */
aside {{ width: 300px; flex: none; position: sticky; top: 0.8rem; }}
.panel {{ background: var(--raised); border: 1px solid var(--border); border-radius: 4px; padding: 0.85rem 0.95rem; margin-bottom: 0.9rem; }}
.panel h2 {{
  font-size: 0.72rem; font-weight: 600; letter-spacing: 0.09em; text-transform: uppercase;
  color: var(--faint); margin-bottom: 0.6rem; display: flex; align-items: baseline;
}}
.panel h2 .count {{ margin-left: auto; font-weight: 400; letter-spacing: 0; text-transform: none; color: var(--muted); font-variant-numeric: tabular-nums; }}
.chips {{ display: flex; flex-wrap: wrap; gap: 0.3rem; }}
.chip {{
  border: 1px solid var(--border); background: var(--inset); color: var(--muted);
  border-radius: 20px; padding: 0.14rem 0.65rem; font-size: 0.82rem; user-select: none;
}}
.chip:hover {{ color: var(--bright); border-color: var(--faint); }}
.chip.on {{ background: var(--accent-dim); border-color: var(--accent); color: #fff; }}
.chip .n {{ opacity: 0.65; font-size: 0.74rem; font-variant-numeric: tabular-nums; }}
.subhead {{ font-size: 0.75rem; color: var(--faint); margin: 0.65rem 0 0.35rem; }}
.clearrow {{ margin-top: 0.6rem; }}
.linkbtn {{ background: none; border: none; color: var(--wiki); font-size: 0.8rem; padding: 0; }}
.linkbtn:hover {{ text-decoration: underline; }}

label.setting {{ display: block; font-size: 0.82rem; color: var(--muted); margin-bottom: 0.55rem; }}
label.drilltoggle {{ display: flex; align-items: center; gap: 0.45rem; color: var(--bright); cursor: pointer; margin: 0.6rem 0 0.4rem; }}
label.drilltoggle input {{ accent-color: var(--accent); width: 15px; height: 15px; }}
label.setting .val {{ color: var(--bright); font-variant-numeric: tabular-nums; }}
input[type=range] {{ width: 100%; accent-color: var(--accent); margin-top: 0.2rem; }}
.seg {{ display: flex; border: 1px solid var(--border); border-radius: 3px; overflow: hidden; margin-top: 0.25rem; }}
.seg button {{ flex: 1; background: var(--inset); border: none; color: var(--muted); padding: 0.32rem 0.2rem; font-size: 0.8rem; border-left: 1px solid var(--border); }}
.seg button:first-child {{ border-left: none; }}
.seg button.on {{ background: var(--accent-dim); color: #fff; }}
.seg input[type=number] {{ flex: 1; background: var(--inset); border: none; border-left: 1px solid var(--border); color: var(--muted); padding: 0.32rem 0.4rem; font-size: 0.8rem; min-width: 0; text-align: center; }}
.seg input[type=number].on {{ background: var(--accent-dim); color: #fff; }}
.seg input[type=number]:focus {{ outline: none; color: var(--bright); }}
.hint {{ font-size: 0.75rem; color: var(--faint); margin-top: 0.45rem; line-height: 1.45; }}
/* Clue lookup: tappable sentences on finished questions + result panel. */
.clue-s {{ cursor: pointer; border-radius: 3px; }}
.clue-s:hover {{ background: var(--inset); box-shadow: 0 0 0 2px var(--inset); }}
#cluepanel {{ display: none; position: fixed; right: 1rem; bottom: 1rem; width: 24rem;
  max-width: calc(100vw - 2rem); max-height: 60vh; overflow-y: auto;
  background: var(--raised); border: 1px solid var(--border); border-radius: 6px;
  box-shadow: 0 6px 24px rgba(0,0,0,0.45); z-index: 60; }}
#cluepanel.show {{ display: block; }}
.cluehead {{ display: flex; align-items: baseline; gap: 0.5rem; padding: 0.6rem 0.8rem 0.4rem;
  border-bottom: 1px solid var(--border); position: sticky; top: 0; background: var(--raised); }}
.cluehead h3 {{ font-size: 0.85rem; margin: 0; color: var(--bright); white-space: nowrap; }}
#cluequery {{ font-size: 0.72rem; color: var(--faint); font-style: italic; flex: 1;
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }}
#clueclose {{ background: none; border: none; color: var(--muted); font-size: 1.05rem; cursor: pointer; }}
.clueitem {{ padding: 0.5rem 0.8rem; border-bottom: 1px solid var(--border); }}
.clueitem:last-child {{ border-bottom: none; }}
.clueans {{ font-size: 0.8rem; color: var(--bright); font-weight: 600; }}
.clueans a {{ font-weight: normal; font-size: 0.72rem; color: var(--wiki); }}
.cluepos {{ float: right; color: var(--faint); font-size: 0.7rem; font-weight: normal; }}
.cluetext {{ font-size: 0.78rem; color: var(--muted); margin-top: 0.15rem; line-height: 1.45; }}
.cluenote {{ padding: 0.7rem 0.8rem; font-size: 0.78rem; color: var(--muted); }}
html[data-layout="mobile"] #cluepanel {{ left: 0; right: 0; bottom: 0; width: auto;
  max-width: none; border-radius: 12px 12px 0 0; max-height: 55vh; }}
kbd {{
  font-family: Consolas, monospace; font-size: 0.72rem; color: var(--bright);
  background: var(--inset); border: 1px solid var(--border); border-bottom-width: 2px;
  border-radius: 3px; padding: 0 0.32rem;
}}

/* ---------- stage ---------- */
main {{ flex: 1; min-width: 0; }}
.qcard {{ background: var(--raised); border: 1px solid var(--border); border-radius: 4px; overflow: hidden; }}
.qmeta {{
  display: flex; gap: 0.9rem; flex-wrap: wrap; align-items: baseline;
  padding: 0.55rem 1.1rem; border-bottom: 1px solid var(--border);
  font-size: 0.78rem; color: var(--faint); background: var(--inset);
}}
.qmeta .set {{ color: var(--muted); }}
.qmeta .diff {{ font-variant-numeric: tabular-nums; }}
.qmeta .status {{ margin-left: auto; font-weight: 600; letter-spacing: 0.05em; text-transform: uppercase; font-size: 0.72rem; }}
.status.reading {{ color: var(--accent); }}
.status.buzzed {{ color: var(--accent); }}
.status.done-c {{ color: var(--good); }}
.status.done-w {{ color: var(--bad); }}
.status.dead {{ color: var(--faint); }}

.qtext {{
  font-family: var(--serif); font-size: 1.14rem; line-height: 1.78; color: var(--bright);
  padding: 1.15rem 1.3rem 1.25rem; min-height: 11.5rem;
}}
.qtext .skipped {{ color: var(--faint); }}
.qtext .unread {{ color: var(--faint); opacity: 0.55; }}
.qtext .buzzmark {{ color: var(--accent); font-weight: bold; padding: 0 0.1rem; }}
.qtext .powermark {{ color: var(--accent); }}
.skiptoggle {{
  font-family: var(--sans); display: inline-block; font-size: 0.76rem; color: var(--muted);
  background: var(--inset); border: 1px dashed var(--border); border-radius: 3px;
  padding: 0.12rem 0.6rem; margin-bottom: 0.55rem;
}}
.skiptoggle:hover {{ color: var(--bright); border-color: var(--faint); }}
.reviewbar {{
  display: flex; align-items: center; gap: 0.6rem; flex-wrap: wrap;
  font-size: 0.8rem; color: var(--accent); background: var(--accent-dim);
  border: 1px solid var(--accent); border-radius: 5px;
  padding: 0.4rem 0.7rem; margin-bottom: 0.7rem;
}}
.reviewbar .rlbl {{ color: #fff; font-weight: 600; }}
.reviewbar button {{
  font-family: var(--sans); font-size: 0.78rem; color: #fff; background: transparent;
  border: 1px solid rgba(255,255,255,0.4); border-radius: 4px; padding: 0.15rem 0.55rem;
}}
.reviewbar button:hover:not(:disabled) {{ background: rgba(255,255,255,0.15); }}
.reviewbar button:disabled {{ opacity: 0.4; cursor: default; }}
.reviewbar .rspacer {{ flex: 1; }}
.distpanel {{ margin-top: 0.7rem; border-top: 1px solid var(--border); padding-top: 0.6rem; }}
.distpanel summary {{ cursor: pointer; color: var(--bright); font-size: 0.86rem; font-weight: 600; }}
.disttoggle {{ display: flex; align-items: center; gap: 0.45rem; color: var(--bright); cursor: pointer; margin: 0.5rem 0 0.3rem; }}
.disttoggle input {{ accent-color: var(--accent); width: 15px; height: 15px; }}
.distgrid {{ display: grid; grid-template-columns: 1fr auto; gap: 0.2rem 0.6rem; align-items: center; margin: 0.5rem 0; }}
.distgrid label {{ font-size: 0.8rem; color: var(--muted); }}
.distgrid input {{ width: 3.4rem; background: var(--inset); border: 1px solid var(--border); color: var(--bright); border-radius: 4px; padding: 0.15rem 0.35rem; font-size: 0.8rem; text-align: right; }}
.distgrid input:disabled {{ opacity: 0.4; }}

.controls {{ display: flex; gap: 0.6rem; align-items: center; padding: 0.75rem 1.1rem; border-top: 1px solid var(--border); flex-wrap: wrap; }}
.btn {{
  background: var(--inset); color: var(--bright); border: 1px solid var(--border);
  border-radius: 3px; padding: 0.42rem 1.1rem; font-size: 0.88rem;
}}
.btn:hover {{ border-color: var(--faint); }}
.btn.primary {{ background: var(--accent-dim); border-color: var(--accent); color: #fff; font-weight: 600; }}
.btn.primary:hover {{ background: #9d7a38; }}
.btn:disabled {{ opacity: 0.4; cursor: default; }}
.timerbar {{ flex: 1; height: 3px; background: var(--border); border-radius: 2px; overflow: hidden; min-width: 80px; }}
.timerbar i {{ display: block; height: 100%; background: var(--accent); width: 0%; }}

.answerrow {{ display: none; padding: 0.75rem 1.1rem; border-top: 1px solid var(--border); }}
.answerrow.show {{ display: block; }}
.answerrow input {{
  width: 100%; background: var(--inset); color: var(--bright); border: 1px solid var(--accent);
  border-radius: 3px; padding: 0.5rem 0.8rem; font-size: 16px; font-family: var(--sans);
}}
.judge {{ display: none; padding: 0.9rem 1.1rem; border-top: 1px solid var(--border); }}
.judge.show {{ display: block; }}
.verdict {{ font-size: 0.95rem; margin-bottom: 0.35rem; }}
.verdict.c {{ color: var(--good); }} .verdict.w {{ color: var(--bad); }} .verdict.p {{ color: var(--accent); }}
.answerline {{ font-family: var(--serif); font-size: 1.05rem; color: var(--bright); }}
.answerline b u, .answerline u b {{ color: #fff; }}
.selfgrade {{ margin-top: 0.6rem; display: flex; gap: 0.5rem; align-items: center; }}
.sglbl {{ font-size: 0.78rem; color: var(--faint); }}
#sg-right.on {{ background: rgba(93, 187, 122, 0.18); border-color: var(--good); color: var(--good); font-weight: 600; }}
#sg-wrong.on {{ background: rgba(224, 101, 95, 0.18); border-color: var(--bad); color: var(--bad); font-weight: 600; }}

.wikibox {{ display: none; margin-top: 0.9rem; background: var(--raised); border: 1px solid var(--border); border-left: 3px solid var(--wiki); border-radius: 4px; padding: 0.85rem 1rem; }}
.wikibox.show {{ display: block; }}
.wikibox h3 {{ font-size: 0.72rem; font-weight: 600; letter-spacing: 0.09em; text-transform: uppercase; color: var(--faint); margin-bottom: 0.45rem; }}
.wikibox .topiclink {{ font-family: var(--serif); font-size: 1.08rem; }}
.wikibox .tmeta {{ font-size: 0.8rem; color: var(--muted); margin-top: 0.15rem; }}
.wikibox .chips {{ margin-top: 0.55rem; }}
.empty {{ padding: 2.5rem 1.5rem; text-align: center; color: var(--muted); }}
.qdata-error {{ padding: 2.5rem 1.5rem; text-align: center; color: var(--muted); }}

/* ---------- stats view ---------- */
.statgrid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(140px, 1fr)); gap: 0.9rem; margin-bottom: 1.2rem; }}
.stat {{ background: var(--raised); border: 1px solid var(--border); border-radius: 4px; padding: 0.75rem 0.95rem; }}
.stat .k {{ font-size: 0.72rem; letter-spacing: 0.08em; text-transform: uppercase; color: var(--faint); }}
.stat .v {{ font-size: 1.65rem; color: var(--bright); font-variant-numeric: tabular-nums; margin-top: 0.15rem; }}
.stat .v small {{ font-size: 0.85rem; color: var(--muted); }}
table.acc {{ width: 100%; border-collapse: collapse; font-size: 0.86rem; }}
table.acc th {{ text-align: left; font-size: 0.72rem; letter-spacing: 0.08em; text-transform: uppercase; color: var(--faint); font-weight: 600; padding: 0.35rem 0.5rem; border-bottom: 1px solid var(--border); }}
table.acc td {{ padding: 0.42rem 0.5rem; border-bottom: 1px solid var(--inset); font-variant-numeric: tabular-nums; }}
table.acc td.name {{ color: var(--bright); font-variant-numeric: normal; }}
table.acc td.name .sub {{ color: var(--faint); font-size: 0.78rem; }}
.bar {{ display: inline-block; width: 90px; height: 7px; background: var(--inset); border: 1px solid var(--border); border-radius: 4px; vertical-align: middle; margin-right: 0.5rem; overflow: hidden; }}
.bar i {{ display: block; height: 100%; }}
.pct {{ color: var(--muted); }}
.statnote {{ font-size: 0.78rem; color: var(--faint); margin: 0.8rem 0 1.4rem; }}
.sechead {{ font-family: var(--serif); font-size: 1.15rem; color: var(--bright); margin: 1.5rem 0 0.6rem; border-bottom: 1px solid var(--border); padding-bottom: 0.25rem; font-weight: normal; }}
.playtag {{ font-size: 0.76rem; color: var(--wiki); cursor: pointer; }}
.playtag:hover {{ text-decoration: underline; }}
table.acc th.sorth {{ cursor: pointer; user-select: none; white-space: nowrap; }}
table.acc th.sorth:hover {{ color: var(--bright); }}
.dimsel {{ display: flex; gap: 0.3rem; flex-wrap: wrap; margin-bottom: 0.6rem; }}
.dimbtn {{
    background: var(--inset); border: 1px solid var(--border); color: var(--muted);
    border-radius: 3px; padding: 0.3rem 0.8rem; font-size: 0.82rem;
}}
.dimbtn:hover {{ color: var(--bright); border-color: var(--faint); }}
.dimbtn.on {{ background: var(--accent-dim); border-color: var(--accent); color: #fff; }}
.scoperow {{ display: flex; flex-wrap: wrap; align-items: center; gap: 0.4rem; margin-bottom: 1.1rem; }}
.scopelbl {{ font-size: 0.72rem; letter-spacing: 0.08em; text-transform: uppercase; color: var(--faint); margin-right: 0.15rem; }}
.scopesel {{ background: var(--inset); color: var(--bright); border: 1px solid var(--border); border-radius: 3px; padding: 0.3rem 0.5rem; font-family: var(--sans); font-size: 0.82rem; }}
.scopesel:hover {{ border-color: var(--faint); }}
.calibcv {{ width: 100%; max-width: 720px; height: auto; margin-bottom: 1.3rem; }}
.calib {{ display: flex; gap: 0.7rem; flex-wrap: wrap; margin-bottom: 1.2rem; }}
.calib-cell {{
    flex: 1; min-width: 110px; background: var(--raised); border: 1px solid var(--border);
    border-radius: 4px; padding: 0.6rem 0.8rem; text-align: center;
}}
.calib-cell .v {{ font-size: 1.5rem; font-variant-numeric: tabular-nums; margin: 0.15rem 0; }}
.calib-cell .k {{ font-size: 0.7rem; color: var(--faint); text-transform: uppercase; letter-spacing: 0.05em; }}
@media (prefers-reduced-motion: reduce) {{ .timerbar i {{ transition: none !important; }} }}
</style>
</head>
<body>
<header>
  <h1><a href="index.html" style="color:inherit">Library of Stock</a> <span class="lede">/ Reader</span></h1>
  <nav class="viewtabs">
    <button id="tab-play" class="on">Reader</button>
    <button id="tab-stats">My stats</button>
    <a class="tab" href="wiki.html">Wiki &nearr;</a>
  </nav>
</header>

<div class="mchrome">
  <button id="open-scope">Scope <span class="mbadge" id="scopebadge" style="display:none"></span></button>
  <button id="open-reading">Reading &amp; settings</button>
</div>

<div class="wrap">
  <aside id="rail">
    <div class="panel" id="panel-scope">
      <h2>Scope <span class="count" id="scopecount"></span></h2>
      <div class="subhead">Category</div>
      <div class="chips" id="f-cats"></div>
      <div class="subhead" id="subs-head" style="display:none">Subcategory</div>
      <div class="chips" id="f-subs"></div>
      <div class="subhead" id="subsub-head" style="display:none">Subtype</div>
      <div class="chips" id="f-subsub"></div>
      <div class="subhead" id="tags-head" style="display:none">Focus &mdash; movements &amp; schools <span style="text-transform:none;letter-spacing:0">(from the wiki)</span></div>
      <div class="chips" id="f-tags"></div>
      <div class="subhead" id="eras-head" style="display:none">Era</div>
      <div class="chips" id="f-eras"></div>
      <div class="subhead" id="groups-head" style="display:none">Group <span style="text-transform:none;letter-spacing:0">(overview sections)</span></div>
      <div class="chips" id="f-groups"></div>
      <div class="subhead">Difficulty</div>
      <div class="chips" id="f-diffs"></div>
      <div class="clearrow"><button class="linkbtn" id="clearfilters">Reset scope</button></div>
    </div>
    <div class="panel" id="panel-reading">
      <h2>Reading</h2>
      <label class="setting">Speed &mdash; <span class="val" id="wpmval"></span> wpm
        <input type="range" id="wpm" min="120" max="700" step="10">
      </label>
      <label class="setting" style="margin-bottom:0.25rem">Sentences read</label>
      <div class="seg" id="sentmode">
        <button data-n="0" class="on">Full</button>
        <input type="number" id="sentn" min="1" max="99" inputmode="numeric" placeholder="last n" aria-label="read only the last n sentences">
      </div>
      <div class="hint">Type how many final sentences to read (blank = full question) to drill giveaways and stock clues; earlier sentences stay hidden until you ask.</div>
      <label class="setting drilltoggle" id="voicetoggle"><input type="checkbox" id="voice"> Read aloud (voice)</label>
      <div id="voicerow" style="display:none">
        <label class="setting">Voice speed &mdash; <span class="val" id="vrateval"></span>
          <input type="range" id="vrate" min="0.6" max="1.6" step="0.05">
        </label>
        <div class="hint">A recorded voice reads the question &mdash; its text stays hidden until the question is over, like a real moderator. The scope narrows to questions that have audio (being added over time). The wpm slider above only affects text reveal.</div>
      </div>
      <label class="setting drilltoggle"><input type="checkbox" id="multibuzz"> Multiple buzzes</label>
      <div id="multibuzzrow" style="display:none">
        <div class="hint">A wrong answer doesn&rsquo;t end the question &mdash; reading resumes from your buzz and you can buzz again until it runs out. Your first wrong buzz still counts as a neg in stats.</div>
      </div>
      <label class="setting drilltoggle"><input type="checkbox" id="drill"> Drill my weaknesses</label>
      <div id="drillrow" style="display:none">
        <label class="setting">Focus &mdash; <span class="val" id="focusval">balanced</span>
          <input type="range" id="focus" min="0" max="100" value="55">
        </label>
        <div class="hint">Weights the queue toward your weak groups &amp; answers (from My stats), with spaced review of misses. Broad = variety; Targeted = hammer weaknesses.</div>
      </div>
      <details class="distpanel" id="distpanel">
        <summary>Category distribution</summary>
        <label class="setting disttoggle"><input type="checkbox" id="usedist" checked> Follow distribution</label>
        <div class="hint">Sample categories in a standard quizbowl mix (like qbreader) instead of raw corpus frequency. Set a weight to 0 to exclude a category; edit any weight to taste.</div>
        <div class="distgrid" id="distgrid"></div>
        <button class="linkbtn" id="distreset">Reset to standard</button>
      </details>
      <div class="hint kbdhint"><kbd>Space</kbd> buzz &middot; <kbd>Enter</kbd> submit &middot; <kbd>N</kbd> next &middot; <kbd>K</kbd> previous &middot; <kbd>S</kbd> skip &middot; <kbd>P</kbd> pause</div>
      <div class="hint taphint">Tap the question text to buzz; tap it again after the reveal for the next question. Skip is never counted.</div>
      <div class="hint">Note-run clues (&ldquo;E, G, B-flat&hellip;&rdquo;) read at a slower pace automatically.</div>
    </div>
    <div class="panel" id="syncpanel" style="display:none">
      <h2>Sync</h2>
      <div id="syncbody"></div>
    </div>
  </aside>

  <main>
    <section id="view-play">
      <div class="qcard" id="qcard">
        <div class="qmeta">
          <span class="set" id="m-set"></span>
          <span class="diff" id="m-diff"></span>
          <span id="m-cat"></span>
          <span class="status" id="m-status"></span>
        </div>
        <div class="reviewbar" id="reviewbar" style="display:none"></div>
        <div class="qtext" id="qtext"></div>
        <div class="answerrow" id="answerrow">
          <input id="answerinput" type="text" placeholder="Answer&hellip;" autocomplete="off" spellcheck="false">
        </div>
        <div class="judge" id="judge">
          <div class="verdict" id="verdict"></div>
          <div class="answerline" id="answerline"></div>
          <div class="selfgrade" id="selfgrade" style="display:none">
            <span class="sglbl">Override:</span>
            <button class="btn sg" id="sg-right">Correct</button>
            <button class="btn sg" id="sg-wrong">Incorrect</button>
          </div>
        </div>
        <div class="controls">
          <button class="btn primary" id="mainbtn">Start</button>
          <button class="btn" id="pausebtn" disabled>Pause</button>
          <button class="btn" id="skipbtn" disabled title="Throw this question away — not counted in stats">Skip</button>
          <button class="btn" id="prevbtn" disabled title="Review the previous question (k)">&#9664; Prev</button>
          <div class="timerbar" aria-hidden="true"><i id="timerfill"></i></div>
        </div>
      </div>
      <div class="wikibox" id="wikibox">
        <div id="w-topicblock">
          <h3>From the wiki</h3>
          <div><a class="topiclink" id="w-topic" href="#"></a></div>
          <div class="tmeta" id="w-meta"></div>
          <div class="chips" id="w-tags"></div>
          <div class="chips" id="w-rel" style="margin-top:0.4rem"></div>
        </div>
        <div id="w-practiceblock" style="display:none;margin-top:0.7rem">
          <h3>Practice more</h3>
          <div class="chips" id="w-practice"></div>
        </div>
      </div>
    </section>

    <section id="view-stats" style="display:none">
      <div class="statgrid" id="statgrid"></div>
      <div class="statnote" id="statnote"></div>
      <div id="statbody"></div>
    </section>
  </main>
</div>

<div id="mbar">
  <div id="mbar-timer"></div>
  <div class="mbar-btns">
    <button class="btn" id="m-prev" disabled title="Previous question">&#9664;</button>
    <button class="btn" id="m-pause" disabled>Pause</button>
    <button class="btn" id="m-skip" disabled>Skip</button>
    <button class="btn primary" id="m-main">Start</button>
  </div>
</div>

<div class="los-sheet" id="sheet-scope" role="dialog" aria-label="Scope">
  <div class="los-sheet-handle"></div>
  <div class="los-sheet-body" id="sheet-scope-body"></div>
</div>
<div class="los-sheet" id="sheet-reading" role="dialog" aria-label="Reading settings">
  <div class="los-sheet-handle"></div>
  <div class="los-sheet-body" id="sheet-reading-body"></div>
</div>

<script src="lib/js/qdata.js"></script>
<div id="cluepanel" aria-live="polite">
  <div class="cluehead"><h3>Similar clues</h3><span id="cluequery"></span>
    <button id="clueclose" aria-label="close">&times;</button></div>
  <div id="cluebody"></div>
</div>

<script src="lib/js/mobile.js"></script>
<script src="lib/js/answer_checker.js"></script>
<script src="lib/js/reader.js"></script>
<script src="lib/js/sync.js"></script>
</body>
</html>
"""


def build() -> None:
    out_path = ROOT / "reader.html"
    out_path.write_text(page_html(), encoding="utf-8")
    print("Built reader.html")


if __name__ == "__main__":
    build()
