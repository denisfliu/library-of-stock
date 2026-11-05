"""build_reader.py — Generate reader.html (the question reader) at repo root.

The page is a static shell: all question data is fetched at view time from
the R2 data plane (catalog.json + topics.json at boot, set shards lazily)
via lib/js/qdata.js; the app logic lives in lib/js/reader.js. Colours come
from theme.theme_vars_css() (light + dark, qbsuite look).

Layout: a quiet top bar (view tabs, Wiki, Sync), a centred row of setting
pills whose popovers hold the existing control panels (bottom sheets on a
phone, via lib/js/mobile.js), and one centred question column. Optional
right column: the similar-clues panel, or the read-only session column.

Usage:
    python lib/render/build_reader.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from lib.common import ROOT
from lib.render.theme import (FONT_STACK, PALETTE, cache_buster, layout_switch_script,
                              sheet_css, theme_vars_css)


def js_v(name: str) -> str:
    """Cache-buster for a lib/js asset (Pages caches JS ~10 min; a fresh
    page must never run a stale script)."""
    return cache_buster(ROOT / "lib" / "js" / name)


def page_html() -> str:
    p = PALETTE
    return f"""<!DOCTYPE html>
<html lang="en" data-layout="desktop">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
{layout_switch_script()}
<title>Library of Stock — Reader</title>
<style>
{theme_vars_css()}
:root {{
  --bg: {p['bg']}; --raised: {p['bg_raised']}; --inset: {p['bg_input']}; --border: {p['border']};
  --text: {p['text']}; --bright: {p['text_bright']}; --muted: {p['text_muted']}; --faint: {p['text_faint']};
  --wiki: {p['link']}; --link: var(--c-link); --line2: var(--c-line2); --hover: var(--c-hover);
  --accent: var(--c-accent); --accent-dim: var(--c-selline);
  --good: var(--c-good); --bad: var(--c-bad); --warn: var(--c-warn);
  --pick: var(--c-pick); --pickline: var(--c-pickline);
  --sans: {FONT_STACK};
  --serif: 'Linux Libertine', Georgia, serif;
}}
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
html {{ background: var(--bg); }}
body {{
  font-family: var(--sans); background: var(--bg); color: var(--text);
  font-size: 15px; line-height: 1.5; min-height: 100vh; -webkit-font-smoothing: antialiased;
}}
a {{ color: var(--link); text-decoration: none; }}
a:hover {{ text-decoration: underline; }}
button {{ font-family: var(--sans); cursor: pointer; }}
:focus-visible {{ outline: 2px solid var(--link); outline-offset: 1px; }}

/* ---------- top bar ---------- */
.topbar {{
  display: flex; align-items: center; gap: 0.4rem 1.35rem; flex-wrap: wrap; position: relative;
  padding: 1.05rem 2rem; font-size: 14px; border-bottom: 1px solid var(--border);
}}
.topbar .home {{ color: var(--text); font-weight: 600; font-size: 15px; }}
.topbar .crumb {{ color: var(--muted); margin-left: -0.9rem; }}
.topbar .sp {{ flex-grow: 1; }}
.viewtabs {{ display: flex; align-items: center; gap: 0.2rem 1.35rem; }}
.viewtabs button, .viewtabs a.tab {{
  background: none; border: none; color: var(--muted); font-size: 14px; padding: 0.15rem 0;
  border-bottom: 2px solid transparent; border-radius: 0;
}}
.viewtabs button:hover, .viewtabs a.tab:hover {{ color: var(--text); text-decoration: none; }}
.viewtabs button.on {{ color: var(--text); border-bottom-color: var(--text); }}
.menubtn {{ display: none; background: none; border: none; color: var(--text); font-size: 14px; padding: 0.3rem 0.5rem; border-radius: 6px; }}
.menubtn:hover {{ background: var(--hover); }}

.wrap {{ max-width: 808px; margin: 0 auto; padding: 1.4rem 1.5rem 3.5rem; }}
.wrap[data-view="stats"], .wrap[data-view="history"], .wrap[data-view="missed"] {{ max-width: 1040px; }}
.wrap:has(#cluepanel.show), .wrap:has(#sessrail:not([hidden])) {{ max-width: 1220px; }}
.wrap:not([data-view="play"]) .pills {{ display: none; }}
/* With a side column up (session column, similar clues) the pills center
   over the question column, not the whole page: the side is 300px + the
   48px stage gap (main takes all the flex growth). From 1200px the column
   is wide enough for the pills on one line; the session column only shows
   from there (reader.js syncSession, RAIL_MQ). It carries the session
   score, so the tally line steps aside. */
@media (min-width: 1200px) {{
  .wrap:has(#cluepanel.show) .pills, .wrap:has(#sessrail:not([hidden])) .pills {{ margin-right: 348px; }}
}}
.wrap:has(#sessrail:not([hidden])) .sessline {{ display: none; }}

/* ---------- setting pills + popovers ---------- */
.pills {{
  display: flex; justify-content: center; align-items: center; gap: 8px; flex-wrap: wrap;
  scrollbar-width: none;
}}
.pills::-webkit-scrollbar {{ display: none; }}
.pill {{
  font-size: 14px; color: var(--text); background: none; border: 1px solid var(--border);
  border-radius: 99px; padding: 5px 13px; white-space: nowrap;
}}
.pill:hover, .pill.open {{ border-color: var(--link); }}
.pill .c {{ color: var(--muted); margin-left: 4px; }}
.sessline {{ font-size: 13px; color: var(--muted); margin-left: 6px; font-variant-numeric: tabular-nums;
  background: none; border: none; padding: 0; white-space: nowrap; }}
.sessline b {{ color: var(--text); }}
.sessline:empty {{ display: none; }}
/* A popover is a .los-sheet: a bottom sheet on a phone (mobile.js), an
   anchored dropdown under its pill on desktop (reader.js positions it). */
html[data-layout="desktop"] .pop {{
  position: absolute; right: auto; bottom: auto; width: 340px; max-width: calc(100vw - 24px);
  max-height: min(72vh, 620px); border: 1px solid var(--border); border-radius: 12px;
  box-shadow: 0 10px 34px rgba(0,0,0,0.16); padding-bottom: 0;
}}
html[data-layout="desktop"] #pop-set {{ width: 390px; }}
html[data-layout="desktop"] #pop-more {{ width: 360px; }}
html[data-layout="desktop"] .pop .los-sheet-handle {{ display: none; }}
html[data-layout="desktop"] .pop .los-sheet-body {{ padding: 0.95rem 1rem 0.6rem; }}
html[data-layout="desktop"] .los-backdrop {{ display: none !important; }}
html[data-layout="desktop"] body.los-sheet-open {{ overflow: auto; }}
.pop .panel {{ border: none; border-radius: 0; background: none; padding: 0; margin: 0 0 0.9rem; }}
html[data-layout="desktop"] #pop-speed, html[data-layout="desktop"] #pop-text, html[data-layout="desktop"] #pop-sent {{ width: 300px; }}
.pop .panel + .panel {{ border-top: 1px solid var(--border); padding-top: 0.85rem; }}

/* ---------- mobile layout (html[data-layout="mobile"], set by the head
   script from theme.layout_switch_script; MOBILE_MQ is the one breakpoint).
   Popovers become bottom sheets, the pills scroll sideways, the view tabs
   fold into a Menu, and the action buttons move to the fixed bottom bar
   #mbar (the timerbar node moves into it). ---------- */
#mbar, .taphint {{ display: none; }}
html[data-layout="mobile"] .topbar {{ padding: 0.8rem 1rem; }}
html[data-layout="mobile"] .menubtn {{ display: inline-block; }}
html[data-layout="mobile"] .viewtabs {{ display: none; }}
html[data-layout="mobile"] .topbar.menu-open .viewtabs {{
  display: flex; flex-direction: column; align-items: stretch; gap: 0;
  position: absolute; right: 0.75rem; top: calc(100% - 0.3rem); z-index: 80; min-width: 12rem;
  background: var(--bg); border: 1px solid var(--border); border-radius: 12px;
  box-shadow: 0 10px 30px rgba(0,0,0,0.18); padding: 0.35rem;
}}
html[data-layout="mobile"] .topbar.menu-open .viewtabs button,
html[data-layout="mobile"] .topbar.menu-open .viewtabs a.tab {{
  text-align: left; padding: 0.7rem 0.8rem; border: none; border-radius: 8px; min-height: 44px; font-size: 15px;
}}
html[data-layout="mobile"] .topbar.menu-open .viewtabs button.on {{ background: var(--pick); font-weight: 600; }}
html[data-layout="mobile"] .wrap {{ padding: 1rem 1rem calc(150px + env(safe-area-inset-bottom)); }}
html[data-layout="mobile"] .pills {{ justify-content: flex-start; flex-wrap: nowrap; overflow-x: auto; margin: 0 -1rem; padding: 0 1rem; }}
html[data-layout="mobile"] .pill {{ min-height: 38px; }}
html[data-layout="mobile"] .chip {{ padding: 0.4rem 0.9rem; font-size: 0.92rem; }}
html[data-layout="mobile"] .seg button {{ padding: 0.55rem 0.2rem; font-size: 0.9rem; }}
html[data-layout="mobile"] .qtext {{ min-height: 8rem; }}
html[data-layout="mobile"] kbd, html[data-layout="mobile"] .btn[data-kbd]::after {{ display: none; }}
/* Live-question run-out: while a question is live, reader.js unhides the
   spacer so the revealing text can be scrolled anywhere on screen. */
#qspacer {{ height: 70vh; height: 70svh; }}
html[data-layout="mobile"] .controls > #mainbtn, html[data-layout="mobile"] .controls .quietrow {{ display: none; }}
html[data-layout="mobile"] .kbdhint {{ display: none; }}
html[data-layout="mobile"] .taphint {{ display: block; }}
html[data-layout="mobile"] #mbar {{
  display: block; position: fixed; left: 0; right: 0; bottom: 0; z-index: 50;
  background: var(--bg); border-top: 1px solid var(--border);
  padding: 0 1rem env(safe-area-inset-bottom);
}}
#mbar-timer {{ display: flex; margin: 0 -1rem; }}
#mbar-timer .timerbar {{ position: static; border-radius: 0; width: 100%; height: 3px; }}
.mbar-main {{ padding-top: 0.6rem; }}
.mbar-btns {{ display: flex; justify-content: space-around; padding: 0.25rem 0 0.55rem; }}
.mbar-btns .btn {{ min-height: 44px; }}
.los-sheet-body .dtree .dw {{ min-height: 40px; }}
.los-sheet-body .dtree .twist {{ width: 24px; height: 24px; line-height: 24px; }}
/* Stats view on a narrow screen */
.tablewrap {{ overflow-x: auto; -webkit-overflow-scrolling: touch; max-width: 100%; }}
html[data-layout="mobile"] .bar {{ width: 56px; }}
html[data-layout="mobile"] table.acc td, html[data-layout="mobile"] table.acc th {{ padding-left: 0.35rem; padding-right: 0.35rem; }}
html[data-layout="mobile"] .facetlbl {{ width: 100%; }}
html[data-layout="mobile"] .d-only {{ display: none !important; }}
{sheet_css()}

/* ---------- control panels (live inside the popovers) ---------- */
.panel {{ background: var(--raised); border: 1px solid var(--border); border-radius: 8px; padding: 0.85rem 0.95rem; margin-bottom: 0.9rem; }}
.panel h2 {{
  font-size: 14px; font-weight: 600; color: var(--text); margin-bottom: 0.55rem;
  display: flex; align-items: baseline;
}}
.panel h2 .count {{ margin-left: auto; font-weight: 400; color: var(--muted); font-size: 13px; font-variant-numeric: tabular-nums; }}
.panel h2 .count b {{ color: var(--text); font-weight: 600; }}
.chips {{ display: flex; flex-wrap: wrap; gap: 0.3rem; }}
.chip {{
  border: 1px solid var(--border); background: var(--bg); color: var(--text);
  border-radius: 99px; padding: 0.16rem 0.65rem; font-size: 0.84rem; user-select: none;
}}
.chip:hover {{ border-color: var(--link); }}
.chip.on {{ background: var(--pick); border-color: var(--pickline); color: var(--bright); font-weight: 600; }}
.chip .n {{ color: var(--muted); font-weight: 400; font-size: 0.75rem; font-variant-numeric: tabular-nums; }}
.subhead {{ font-size: 0.78rem; color: var(--muted); margin: 0.7rem 0 0.35rem; }}
/* Category picker: qbreader's modal (outlined, colour-coded buttons; filled
   = on) plus a Group column, one block per unit in scope. The category
   colours are qbreader's own, the same in both themes. */
.cmodal {{ position: fixed; inset: 0; z-index: 95; background: rgba(0,0,0,.55); overflow-y: auto;
  padding: 1.75rem max(16px, env(safe-area-inset-right, 0px)) 1.75rem max(16px, env(safe-area-inset-left, 0px)); }}
.cbox {{ max-width: 1060px; margin: 0 auto; background: var(--bg); border: 1px solid var(--border); border-radius: 8px; }}
.chead {{ display: flex; flex-wrap: wrap; align-items: center; gap: .6rem; padding: .8rem 1rem; border-bottom: 1px solid var(--border); }}
.chead h2 {{ font-size: 17px; font-weight: 600; color: var(--bright); }}
.chead .tog {{ font-size: 13px; background: var(--link); color: var(--bg); border: 0; border-radius: 6px; padding: .25rem .65rem; }}
.chead .cnt {{ font-size: 13px; color: var(--muted); font-variant-numeric: tabular-nums; margin-left: auto; }}
.chead .x {{ font-size: 22px; line-height: 1; background: none; border: 0; color: var(--muted); padding: 0 .2rem; }}
.ccols {{ display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)) minmax(0, 1.35fr); gap: 1rem; padding: 1rem; }}
.ccols h3 {{ text-align: center; font-size: 15px; font-weight: 600; margin: 0 0 .4rem; color: var(--bright); }}
.chint {{ text-align: center; color: var(--muted); font-size: 13px; padding: .3rem 0; }}
.cb {{ display: block; width: 100%; margin: .25rem 0; padding: .3rem .5rem; font-size: 13.5px; text-align: center;
  background: transparent; border: 1px solid var(--k); color: var(--k); border-radius: 0; }}
.cb[aria-pressed="true"], .gb[aria-pressed="true"], .gall[aria-pressed="true"] {{ background: var(--k); color: #fff; }}
.k-lit {{ --k: #4f7cac; }} .k-hist {{ --k: #00a67c; }} .k-sci {{ --k: #d9483b; }} .k-arts {{ --k: #e8740c; }} .k-other {{ --k: #7d858e; }}
.gunit {{ margin-bottom: .7rem; }}
.guhead {{ display: flex; align-items: baseline; gap: .5rem; font-size: 12.5px; color: var(--muted); margin: .1rem 0 .25rem; }}
.guhead b {{ color: var(--text); font-weight: 600; }}
.gall {{ margin-left: auto; font-size: 12px; padding: .05rem .5rem; border: 1px solid var(--k); color: var(--k); background: transparent; }}
.gchips {{ display: flex; flex-wrap: wrap; gap: .25rem; }}
.gb {{ font-size: 12.5px; padding: .15rem .5rem; border: 1px solid var(--k); color: var(--k); background: transparent; text-align: left; }}
.cb:focus-visible, .gb:focus-visible, .gall:focus-visible, .chead button:focus-visible {{ outline: 2px solid var(--link); outline-offset: 2px; }}
html[data-layout="mobile"] .ccols {{ grid-template-columns: minmax(0, 1fr); }}
html[data-layout="mobile"] .cmodal {{ padding: 0; }}
html[data-layout="mobile"] .cbox {{ border-radius: 0; min-height: 100%; }}
/* Set picker + packet grid */
.pill.set {{ border-color: var(--link); }}
.pill.dim, .pill:disabled {{ color: var(--faint); border-style: dashed; cursor: default; }}
.pill.dim .c {{ display: none; }}
.setsearch {{ width: 100%; font: inherit; font-size: 14px; color: var(--text); background: var(--inset); border: 1px solid var(--border);
  border-radius: 8px; padding: .45rem .6rem; }}
.setsearch:focus {{ outline: none; border-color: var(--link); }}
.setlist {{ margin-top: .5rem; max-height: 250px; overflow-y: auto; border-top: 1px solid var(--border); }}
.setyear {{ font-size: 12px; color: var(--muted); padding: .5rem .2rem .2rem; font-variant-numeric: tabular-nums; }}
.setrow {{ display: grid; grid-template-columns: 1fr auto; gap: .1rem .8rem; width: 100%; text-align: left; background: none;
  border: 0; padding: .38rem .45rem; border-radius: 6px; color: var(--text); }}
.setrow:hover {{ background: var(--hover); }}
.setrow.on {{ background: var(--c-selbg); box-shadow: inset 0 0 0 1px var(--c-selline); }}
.setrow .nm {{ font-size: 14px; }}
.setrow .meta {{ color: var(--faint); font-size: 12px; grid-column: 1; }}
.setrow .prog {{ grid-row: 1 / span 2; grid-column: 2; align-self: center; text-align: right; font-size: 12px; color: var(--muted);
  font-variant-numeric: tabular-nums; line-height: 1.35; }}
.setrow .prog b {{ color: var(--text); font-weight: 600; }}
.prange {{ display: flex; align-items: center; gap: .45rem; margin-top: .8rem; font-size: 13px; color: var(--muted); }}
.prange label {{ margin-right: .2rem; }}
.pksel {{ font: inherit; font-size: 13px; color: var(--text); background: var(--inset); border: 1px solid var(--border);
  border-radius: 6px; padding: .2rem .35rem; font-variant-numeric: tabular-nums; }}
.setfoot {{ display: flex; justify-content: space-between; align-items: center; margin-top: .75rem; font-size: 12.5px; color: var(--muted); }}
.pmap {{ margin-top: .6rem; display: grid; gap: 3px; }}
.prow {{ display: grid; grid-template-columns: 1.6rem minmax(0, 1fr) 2.8rem; align-items: center; gap: .4rem; }}
.prow.out {{ opacity: .35; }}
.prow .pn, .prow .pc {{ font-size: 11px; color: var(--faint); font-variant-numeric: tabular-nums; }}
.prow .pn {{ text-align: right; }} .prow .pc {{ color: var(--muted); }}
.sq {{ display: flex; flex-wrap: wrap; gap: 2px; }}
.sq i, .plegend i {{ display: inline-block; width: 11px; height: 11px; border-radius: 2px; flex: none; }}
.pmap.big .sq {{ gap: 3px; }} .pmap.big .sq i {{ width: 18px; height: 18px; border-radius: 3px; }}
.pmap.big .prow {{ grid-template-columns: 1.8rem auto 3rem; justify-content: start; }}
.pmap.big .pn, .pmap.big .pc {{ font-size: 12.5px; }}
.rP {{ background: var(--accent); }} .rC {{ background: var(--good); }} .rW {{ background: var(--bad); }}
.rD {{ background: var(--faint); opacity: .55; }} .rH {{ background: var(--faint); opacity: .3; }}
.r0 {{ background: transparent; box-shadow: inset 0 0 0 1px var(--border); }}
.plegend {{ display: flex; flex-wrap: wrap; gap: .3rem .8rem; margin: .45rem 0 0 2rem; font-size: 11.5px; color: var(--muted); }}
.plegend span {{ display: inline-flex; align-items: center; gap: .3rem; }}
.pmap.big .plegend {{ font-size: 12.5px; margin-left: 2.2rem; }}
.setdone {{ text-align: center; padding: 2.4rem 0 1.2rem; }}
.setdone .t {{ font-size: 1.15rem; font-weight: 600; color: var(--text); }}
.setdone .s {{ color: var(--muted); margin-top: .35rem; font-variant-numeric: tabular-nums; }}
.setdone .row {{ display: flex; gap: .6rem; justify-content: center; flex-wrap: wrap; margin-top: 1.2rem; }}
.facetmore {{ align-self: center; }}
.linkbtn {{ background: none; border: none; color: var(--link); font-size: 0.82rem; padding: 0; }}
.linkbtn:hover {{ text-decoration: underline; }}

label.setting {{ display: block; font-size: 0.86rem; color: var(--muted); margin-bottom: 0.6rem; }}
label.drilltoggle {{ display: flex; align-items: center; gap: 0.5rem; color: var(--text); cursor: pointer; margin: 0.55rem 0 0.4rem; }}
label.drilltoggle input {{ accent-color: var(--link); width: 15px; height: 15px; }}
label.setting .val {{ color: var(--text); font-weight: 600; font-variant-numeric: tabular-nums; }}
input[type=range] {{ width: 100%; accent-color: var(--link); margin-top: 0.3rem; }}
.seg {{ display: flex; border: 1px solid var(--border); border-radius: 8px; overflow: hidden; margin-top: 0.3rem; }}
.seg button {{ flex: 1; background: var(--bg); border: none; color: var(--text); padding: 0.4rem 0.2rem; font-size: 0.84rem; border-left: 1px solid var(--border); }}
.seg button:first-child {{ border-left: none; }}
.seg button.on {{ background: var(--pick); color: var(--bright); font-weight: 600; }}
.seg input[type=number] {{ flex: 1; background: var(--bg); border: none; border-left: 1px solid var(--border); color: var(--text); padding: 0.4rem 0.4rem; font-size: 0.84rem; min-width: 0; text-align: center; font-family: var(--sans); }}
.seg input[type=number].on {{ background: var(--pick); color: var(--bright); font-weight: 600; }}
.seg input[type=number]:focus {{ outline: none; }}
.hint {{ font-size: 0.78rem; color: var(--muted); margin-top: 0.45rem; line-height: 1.45; }}
kbd {{
  font-family: ui-monospace, Consolas, monospace; font-size: 11px; color: var(--muted);
  border: 1px solid var(--border); border-radius: 4px; padding: 0 4px;
}}

/* ---------- stage: question column + optional side column ---------- */
.stage {{ display: flex; flex-wrap: wrap; gap: 48px; margin-top: 1.9rem; align-items: flex-start; }}
main {{ flex: 999 1 560px; min-width: 0; }}
#view-play {{ max-width: 760px; margin: 0 auto; }}
.side {{ flex: 1 1 300px; max-width: 360px; }}
.sidehead {{ display: flex; justify-content: space-between; align-items: baseline; gap: 0.5rem;
  padding-bottom: 8px; border-bottom: 1px solid var(--text); }}
.sidehead h3 {{ font-size: 15px; font-weight: 600; color: var(--text); margin: 0; }}
.quietbtn {{ background: none; border: none; color: var(--muted); font-size: 13px; padding: 2px 6px; border-radius: 6px; }}
.quietbtn:hover {{ color: var(--text); background: var(--hover); }}

/* Clue lookup: tappable sentences on finished questions + result column. */
.clue-s {{ cursor: pointer; border-radius: 3px; }}
.clue-s:hover, .clue-s.on {{ background: var(--hover); color: var(--text); text-decoration: underline;
  text-decoration-color: var(--muted); text-underline-offset: 3px; }}
#cluepanel {{ display: none; position: sticky; top: 1rem; max-height: calc(100vh - 2rem); overflow-y: auto; }}
#cluepanel.show {{ display: block; }}
.cluehead {{ position: sticky; top: 0; background: var(--bg); z-index: 1; }}
#cluequery {{ font-size: 13.5px; padding: 10px 0; color: var(--muted); border-bottom: 1px solid var(--border); }}
#cluequery:not(:empty)::before {{ content: '“'; }}
#cluequery:not(:empty)::after {{ content: '”'; }}
.clueitem {{ padding: 10px 8px; margin: 0 -8px; border-bottom: 1px solid var(--border); border-radius: 8px; }}
#cluebody .clueitem:hover {{ background: var(--hover); }}
.clueans {{ display: flex; align-items: baseline; gap: 8px; font-size: 13.5px; color: var(--text); font-weight: 600; }}
.clueans a {{ font-weight: normal; font-size: 12.5px; color: var(--link); }}
.cluepos {{ margin-left: auto; color: var(--muted); font-size: 12px; font-weight: normal; white-space: nowrap; text-align: right; }}
.cluetext {{ font-size: 13.5px; color: var(--text); margin-top: 3px; line-height: 1.5; }}
.cluenote {{ padding: 0.7rem 0; font-size: 0.82rem; color: var(--muted); }}
#cluefoot {{ font-size: 12.5px; color: var(--muted); padding-top: 10px; }}
html[data-layout="mobile"] #cluepanel {{
  position: fixed; left: 0; right: 0; bottom: 0; top: auto; z-index: 92; max-width: none;
  max-height: 64vh; background: var(--bg); border-radius: 16px 16px 0 0;
  box-shadow: 0 -8px 30px rgba(0,0,0,0.18); padding: 0 1rem calc(1.2rem + env(safe-area-inset-bottom));
}}
html[data-layout="mobile"] #cluepanel .cluehead {{ padding-top: 0.9rem; }}
html[data-layout="mobile"] #cluepanel .cluehead::before {{
  content: ''; display: block; width: 40px; height: 4px; border-radius: 4px;
  background: var(--border); margin: -0.35rem auto 0.6rem;
}}

/* Session column (read-only view of this session's LOG rows). */
.bigscore {{ display: flex; align-items: baseline; gap: 10px; padding: 16px 0 12px; }}
.bigscore .n {{ font-size: 40px; line-height: 1; font-weight: 600; letter-spacing: -0.02em; font-variant-numeric: tabular-nums; color: var(--text); }}
.bigscore .n small {{ color: var(--muted); font-size: 24px; font-weight: 400; }}
.bigscore .l {{ color: var(--muted); font-size: 14px; }}
.srow {{ display: grid; grid-template-columns: minmax(0, 1fr) 44px 20px; gap: 8px; align-items: center;
  min-height: 38px; padding: 0 8px; margin: 0 -8px; border-top: 1px solid var(--border); font-size: 14px; border-radius: 8px; }}
.srow:hover {{ background: var(--hover); }}
.srow.can {{ cursor: pointer; }}
.srow.on {{ background: var(--hover); }}
.srow .a {{ white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }}
.srow .at {{ text-align: right; color: var(--muted); font-size: 13px; font-variant-numeric: tabular-nums; }}
.srow .m {{ text-align: center; font-weight: 700; }}
.srow .m.x {{ color: var(--warn); }}
.srow.heard .a {{ color: var(--muted); }}
.srow .m.h {{ color: var(--faint); }}

/* ---------- question ---------- */
.qcard {{ position: relative; }}
.qmeta {{ display: flex; flex-wrap: wrap; align-items: baseline; font-size: 13px; color: var(--muted); }}
.qmeta #m-cat:empty + .diff {{ display: none; }}
.qmeta .diff:not(:empty)::before {{ content: '·'; margin: 0 0.35em; }}
.qmeta .status {{ margin-left: auto; padding-left: 0.8rem; font-variant-numeric: tabular-nums; }}
.status.reading, .status.buzzed {{ color: var(--muted); }}
.status.done-c {{ color: var(--good); font-weight: 600; }}
.status.done-w {{ color: var(--bad); font-weight: 600; }}
.status.dead {{ color: var(--muted); }}
.progline {{ position: relative; height: 2px; margin-top: 8px; background: var(--border); border-radius: 2px; overflow: hidden; }}
.qprog {{ position: absolute; inset: 0; }}
.qprog i {{ display: block; height: 100%; width: 0%; background: var(--link); border-radius: 2px; }}
.timerbar {{ position: absolute; inset: 0; background: transparent; overflow: hidden; }}
.timerbar i {{ display: block; height: 100%; background: var(--warn); width: 0%; }}

.qtext {{
  font-size: var(--qsize, 17px); line-height: 1.65; color: var(--text);
  margin-top: 14px; min-height: 9rem;
}}
.qtext .skipped {{ color: var(--muted); }}
.qtext .unheard {{ color: var(--muted); }}
.qtext .buzzmark {{
  display: inline-block; font-size: 10px; font-weight: 700; letter-spacing: 0.04em; line-height: 1.5;
  color: var(--bg); background: var(--link); border-radius: 4px; padding: 0 5px; margin: 0 4px;
  vertical-align: 0.2em; font-family: var(--sans);
}}
.qtext .buzzmark.ok {{ background: var(--good); }}
.qtext .buzzmark.neg {{ background: var(--bad); }}
.qtext .powermark {{ color: var(--accent); font-weight: 600; }}
.qtext .caret {{ display: inline-block; width: 2px; height: 1.1em; background: var(--link); vertical-align: -0.15em; margin-left: 3px; }}
.qtext .empty {{ padding: 2.5rem 0; }}
.skiptoggle {{
  font-family: var(--sans); display: inline-block; font-size: 0.78rem; color: var(--muted);
  background: none; border: 1px dashed var(--border); border-radius: 6px;
  padding: 0.12rem 0.6rem; margin-bottom: 0.55rem;
}}
.skiptoggle:hover {{ color: var(--text); border-color: var(--muted); }}
.taplookup {{ margin-top: 8px; font-size: 13px; }}

.pvsrc {{ font-size: 13px; color: var(--muted); margin-top: 8px; }}
.railempty {{ font-size: 13px; color: var(--muted); padding: 14px 0; line-height: 1.45; }}
/* Score-clue mode: inline per-gap pills for hidden clue runs, a warm tint
   on notation sentences, and highlighted note runs (the units the reveal
   pacing slows down for). */
.qtext .segtoggle {{ margin: 0.1rem 0.15rem; vertical-align: 0.12em; }}
.qtext .noterun {{ background: color-mix(in srgb, var(--accent) 16%, transparent); color: var(--bright); border-radius: 3px; padding: 0 0.12rem; }}
.qtext .scoresent {{ background: color-mix(in srgb, var(--accent) 7%, transparent); border-radius: 3px; box-shadow: 0 0 0 3px color-mix(in srgb, var(--accent) 7%, transparent); }}
.qtext .scoremark {{ color: var(--accent); font-size: 0.85em; user-select: none; }}

.distpanel {{ margin-top: 0.7rem; border-top: 1px solid var(--border); padding-top: 0.6rem; }}
.distpanel summary {{ cursor: pointer; color: var(--text); font-size: 0.88rem; font-weight: 600; }}
.disttoggle {{ display: flex; align-items: center; gap: 0.45rem; color: var(--text); cursor: pointer; margin: 0.5rem 0 0.3rem; }}
.disttoggle input {{ accent-color: var(--link); width: 15px; height: 15px; }}
.dtree {{ margin: 0.55rem 0 0; }}
.drow {{ position: relative; display: flex; align-items: center; gap: 0.3rem; padding: 0.22rem 0 0.3rem; }}
.drow .bar {{ position: absolute; left: 0; bottom: 1px; height: 2px; background: var(--c-selline); border-radius: 1px; pointer-events: none; border: none; width: auto; margin: 0; }}
.drow.lv0 .bar {{ background: var(--link); opacity: 0.75; }}
.twist {{ width: 16px; height: 16px; flex-shrink: 0; background: none; border: none; padding: 0;
  color: var(--faint); font-size: 0.62rem; line-height: 16px; cursor: pointer; transform: rotate(0deg); }}
.twist.open {{ transform: rotate(90deg); color: var(--muted); }}
.twist.leaf {{ visibility: hidden; cursor: default; }}
.dname {{ flex: 1; font-size: 0.82rem; color: var(--muted); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }}
.drow.lv0 .dname {{ color: var(--text); }}
.drow.zero .dname {{ color: var(--faint); }}
.dpct {{ width: 2.6rem; text-align: right; font-size: 0.74rem; color: var(--faint); font-variant-numeric: tabular-nums; flex-shrink: 0; }}
.drow.lv0 .dpct {{ color: var(--muted); }}
.dw {{ width: 3rem; flex-shrink: 0; background: var(--inset); border: 1px solid var(--border); color: var(--text);
  border-radius: 6px; padding: 0.15rem 0.35rem; font-size: 0.82rem; text-align: right; font-variant-numeric: tabular-nums; font-family: var(--sans); }}
.dw:focus {{ outline: none; border-color: var(--link); }}
.dw.untouched {{ color: var(--faint); }}
.dw:disabled {{ opacity: 0.4; }}
.dtree.disabled .bar {{ opacity: 0.25; }}
.dtree.disabled .evenrow {{ display: none; }}
.kids {{ margin-left: 14px; border-left: 1px solid var(--border); padding-left: 6px; }}
.evenrow {{ display: flex; justify-content: flex-end; padding: 0.05rem 0 0.25rem; }}
.evenrow .linkbtn {{ font-size: 0.74rem; color: var(--faint); }}
.evenrow .linkbtn:hover {{ color: var(--link); }}
.distfoot {{ display: flex; justify-content: space-between; align-items: baseline; margin-top: 0.55rem; }}
.disttotal {{ font-size: 0.76rem; color: var(--faint); font-variant-numeric: tabular-nums; }}

/* ---------- buttons ---------- */
.btn {{
  background: none; color: var(--link); border: 1px solid var(--border);
  border-radius: 8px; padding: 6px 14px; font-size: 14px; line-height: 1.4;
}}
.btn:hover:not(:disabled) {{ border-color: var(--link); }}
.btn.primary {{ border-color: var(--link); font-weight: 600; }}
.btn.primary:hover:not(:disabled) {{ background: var(--hover); }}
.btn:disabled {{ opacity: 0.4; cursor: default; }}
.btn.big {{ width: 100%; height: 56px; border-radius: 12px; font-size: 18px; font-weight: 600; border-width: 1.5px; border-color: var(--link); }}
.btn.quiet {{ border-color: transparent; color: var(--muted); }}
.btn.quiet:hover:not(:disabled) {{ color: var(--text); background: var(--hover); border-color: transparent; }}
.btn[data-kbd]:not([data-kbd=""])::after {{
  content: attr(data-kbd); font-family: ui-monospace, Consolas, monospace; font-size: 11px; font-weight: 400;
  border: 1px solid var(--border); border-radius: 4px; padding: 0 4px; color: var(--muted); margin-left: 6px;
  vertical-align: 0.1em;
}}
.controls {{ display: flex; flex-wrap: wrap; align-items: center; gap: 8px; margin-top: 18px; }}
.controls #mainbtn:not(.big) {{ min-height: 44px; padding: 0 22px; }}
.controls #mainbtn.big + .selfgrade + .quietrow {{ flex-basis: 100%; justify-content: center; }}
.quietrow {{ display: flex; gap: 4px; }}
.controls #mainbtn:not(.big) ~ .quietrow {{ margin-left: auto; }}
.controls #mainbtn:not(.big) ~ .quietrow #pausebtn, .controls #mainbtn:not(.big) ~ .quietrow #skipbtn {{ display: none; }}
.selfgrade {{ display: flex; gap: 8px; align-items: center; }}
.selfgrade .sg {{ min-height: 44px; color: var(--muted); }}
.selfgrade .sg.on {{ display: none; }}

.answerrow {{ display: none; margin-top: 16px; }}
.answerrow.show {{ display: block; }}
.answerrow input {{
  width: 100%; height: 46px; background: var(--inset); color: var(--text); border: 1px solid var(--link);
  border-radius: 10px; padding: 0 14px; font-size: 16px; font-family: var(--sans);
}}
.answerrow input:focus {{ outline: none; box-shadow: 0 0 0 3px var(--c-selbg); }}
.judge {{ display: none; margin-top: 14px; color: var(--text); }}
/* qbreader-style buzz lines: a coloured Buzz badge (green accepted, red
   rejected, yellow prompt, blue while answering), who, what they said. */
.bline {{ font-size: 15px; line-height: 1.55; margin: 2px 0; }}
.bbadge {{ display: inline-block; font-size: 11px; font-weight: 700; line-height: 1.6; border-radius: 4px;
  padding: 0 6px; vertical-align: 1px; background: var(--link); color: var(--bg); font-family: var(--sans); }}
.bbadge.ok {{ background: var(--good); }}
.bbadge.neg {{ background: var(--bad); }}
.bbadge.prompt {{ background: var(--warn); }}
.bbadge.none {{ background: var(--border); color: var(--text); }}
.bline b {{ font-weight: 600; color: var(--bright); }}
.bline .bnote {{ color: var(--muted); font-size: 14px; }}
.ansline {{ margin-bottom: 8px; font-size: 15px; }}
.ansline:has(.answerline:empty) {{ display: none; }}
.anslbl {{ font-weight: 700; letter-spacing: 0.02em; }}
.judge.show {{ display: block; }}
.answerline {{ font-size: 15px; color: inherit; }}
.answerline:empty {{ display: none; }}
.answerline b u, .answerline u b {{ color: inherit; }}
#j-guide {{ color: var(--link); font-size: 14px; margin-left: 6px; }}
#j-guide:empty {{ display: none; }}
.srcline {{ display: none; font-size: 13px; color: var(--muted); margin-top: 8px; }}
.judge.show:not(:has(.verdict.p)) + .srcline {{ display: block; }}

.wikibox {{ display: none; margin-top: 1.6rem; border-top: 1px solid var(--border); padding-top: 0.9rem; }}
.wikibox.show {{ display: block; }}
.wikibox h3 {{ font-size: 13px; font-weight: 600; color: var(--muted); margin-bottom: 0.35rem; }}
.wikibox .topiclink {{ font-size: 1rem; font-weight: 600; }}
.wikibox .tmeta {{ font-size: 0.82rem; color: var(--muted); margin-top: 0.1rem; }}
.wikibox .chips {{ margin-top: 0.5rem; }}
.empty {{ padding: 2.5rem 1.5rem; text-align: center; color: var(--muted); }}
.qdata-error {{ padding: 2.5rem 1.5rem; text-align: center; color: var(--muted); }}

/* ---------- stats view ---------- */
.statgrid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(140px, 1fr)); gap: 0.9rem; margin-bottom: 1.2rem; }}
.stat {{ background: var(--raised); border: 1px solid var(--border); border-radius: 10px; padding: 0.75rem 0.95rem; }}
.stat .k {{ font-size: 13px; color: var(--muted); }}
.stat .v {{ font-size: 1.65rem; font-weight: 600; color: var(--text); font-variant-numeric: tabular-nums; margin-top: 0.15rem; }}
.stat .v small {{ font-size: 0.85rem; color: var(--muted); font-weight: 400; }}
table.acc {{ width: 100%; border-collapse: collapse; font-size: 0.88rem; }}
table.acc th {{ text-align: left; font-size: 12.5px; color: var(--muted); font-weight: 600; padding: 0.35rem 0.5rem; border-bottom: 1px solid var(--text); }}
table.acc td {{ padding: 0.42rem 0.5rem; border-bottom: 1px solid var(--border); font-variant-numeric: tabular-nums; }}
table.acc td.name {{ color: var(--text); font-variant-numeric: normal; }}
table.acc td.name .sub {{ color: var(--faint); font-size: 0.78rem; }}
.bar {{ display: inline-block; width: 90px; height: 7px; background: var(--line2); border: 1px solid var(--border); border-radius: 4px; vertical-align: middle; margin-right: 0.5rem; overflow: hidden; }}
.bar i {{ display: block; height: 100%; }}
.pct {{ color: var(--muted); }}
.statnote {{ font-size: 0.82rem; color: var(--muted); margin: 0.8rem 0 1.4rem; }}
.sechead {{ font-size: 1.1rem; font-weight: 600; color: var(--text); margin: 1.6rem 0 0.6rem; border-bottom: 1px solid var(--border); padding-bottom: 0.3rem; }}
.playtag {{ font-size: 0.78rem; color: var(--link); cursor: pointer; }}
.playtag:hover {{ text-decoration: underline; }}
table.acc th.sorth {{ cursor: pointer; user-select: none; white-space: nowrap; }}
table.acc th.sorth:hover {{ color: var(--text); }}
.dimsel {{ display: flex; gap: 0.3rem; flex-wrap: wrap; margin-bottom: 0.6rem; }}
.dimbtn {{
    background: none; border: 1px solid var(--border); color: var(--text);
    border-radius: 99px; padding: 0.25rem 0.8rem; font-size: 0.84rem;
}}
.dimbtn:hover {{ border-color: var(--link); }}
.dimbtn.on {{ background: var(--pick); border-color: var(--pickline); color: var(--bright); font-weight: 600; }}
.scopebox {{ background: var(--raised); border: 1px solid var(--border); border-radius: 10px; padding: 0.7rem 0.9rem 0.55rem; margin-bottom: 1.1rem; }}
.facetrow {{ display: flex; align-items: baseline; gap: 0.45rem; flex-wrap: wrap; padding: 0.22rem 0; }}
.facetlbl {{ font-size: 12.5px; color: var(--muted); width: 92px; flex-shrink: 0; }}
.facetnote {{ font-size: 0.8rem; color: var(--faint); }}
.scopefoot {{ margin-top: 0.35rem; font-size: 0.8rem; color: var(--muted); }}
.scopefoot .linkbtn {{ margin-left: 0.7rem; }}
table.acc td.name .kpart {{ color: var(--faint); }}
.calibcv {{ width: 100%; max-width: 720px; height: auto; margin-bottom: 1.3rem; }}

/* progress-over-time chart (stats) */
.progwrap {{ position: relative; background: var(--raised); border: 1px solid var(--border); border-radius: 10px; padding: 0.55rem 0.6rem 0.4rem; max-width: 860px; }}
.progcv {{ display: block; width: 100%; height: 300px; }}
.ctlrow {{ display: flex; gap: 0.6rem 1.1rem; flex-wrap: wrap; align-items: center; margin-bottom: 0.6rem; }}
.ctlgrp {{ display: flex; gap: 0.3rem; align-items: center; }}
.ctllbl {{ font-size: 12.5px; color: var(--muted); margin-right: 0.15rem; }}
.wslider {{
    -webkit-appearance: none; appearance: none; width: 150px; height: 3px;
    background: var(--border); border-radius: 2px; outline: none;
}}
.wslider::-webkit-slider-thumb {{
    -webkit-appearance: none; appearance: none; width: 13px; height: 13px;
    border-radius: 50%; background: var(--link); border: 1px solid var(--bg); cursor: pointer;
}}
.wslider::-moz-range-thumb {{
    width: 13px; height: 13px; border-radius: 50%;
    background: var(--link); border: 1px solid var(--bg); cursor: pointer;
}}
.wslider:disabled {{ opacity: 0.4; }}
.wslider:disabled::-webkit-slider-thumb {{ background: var(--faint); cursor: default; }}
.wslider:disabled::-moz-range-thumb {{ background: var(--faint); cursor: default; }}
.wnum {{
    width: 52px; background: var(--inset); border: 1px solid var(--border); border-radius: 6px;
    color: var(--text); font-family: var(--sans); font-size: 0.8rem;
    padding: 0.2rem 0.3rem; text-align: right; font-variant-numeric: tabular-nums;
}}
.wnum:focus {{ border-color: var(--link); outline: none; }}
.proglegend {{ display: flex; gap: 0.5rem; flex-wrap: wrap; padding: 0.45rem 0.25rem 0; font-size: 0.8rem; color: var(--muted); }}
.legitem {{
    background: none; border: 1px solid transparent; border-radius: 6px; color: var(--muted);
    font-size: 0.8rem; padding: 0.1rem 0.4rem; display: inline-flex; align-items: center;
}}
.legitem:hover {{ color: var(--text); border-color: var(--border); }}
.legitem.off {{ opacity: 0.4; text-decoration: line-through; }}
.proglegend .sw {{ display: inline-block; width: 18px; height: 3px; border-radius: 2px; vertical-align: middle; margin-right: 0.35rem; }}
.proglegend .sw.dash {{ height: 0; border-top: 3px dashed; border-radius: 0; }}
.progtip {{
    position: absolute; pointer-events: none; background: var(--bg);
    border: 1px solid var(--border); border-radius: 8px; padding: 0.4rem 0.55rem;
    font-size: 0.78rem; color: var(--text); white-space: nowrap; opacity: 0;
    transition: opacity 0.08s; box-shadow: 0 3px 12px rgba(0,0,0,0.18); z-index: 5;
}}
.progtip .tth {{ color: var(--bright); font-weight: 600; margin-bottom: 0.15rem; }}
.progtip .ttr {{ display: flex; gap: 0.7rem; justify-content: space-between; font-variant-numeric: tabular-nums; }}
.progtip .ttr i {{ font-style: normal; color: var(--faint); }}
canvas.spark {{ width: 96px; height: 22px; vertical-align: middle; cursor: pointer; opacity: 0.85; }}
canvas.spark:hover {{ opacity: 1; }}
table.acc tr.pinned td {{ background: var(--c-raised2); }}
table.acc tr.pinned td.name::before {{
    content: ''; display: inline-block; width: 8px; height: 8px;
    border-radius: 2px; margin-right: 0.45rem; background: var(--pincol);
}}
html[data-layout="mobile"] .progcv {{ height: 220px; }}
html[data-layout="mobile"] .wslider {{ width: 110px; }}
html[data-layout="mobile"] .sparkcell, html[data-layout="mobile"] table.acc th.sparkhead {{ display: none; }}

.calib {{ display: flex; gap: 0.7rem; flex-wrap: wrap; margin-bottom: 1.2rem; }}
.calib-cell {{
    flex: 1; min-width: 110px; background: var(--raised); border: 1px solid var(--border);
    border-radius: 10px; padding: 0.6rem 0.8rem; text-align: center;
}}
.calib-cell .v {{ font-size: 1.5rem; font-variant-numeric: tabular-nums; margin: 0.15rem 0; }}
.calib-cell .k {{ font-size: 12px; color: var(--muted); }}

/* ---------- history view (searchable log of played questions) ---------- */
.histsearch input {{
  width: 100%; height: 44px; background: var(--inset); color: var(--text); border: 1px solid var(--border);
  border-radius: 10px; padding: 0 14px; font-size: 16px; font-family: var(--sans);
}}
.histsearch input:focus {{ outline: none; border-color: var(--link); }}
.histrow {{ border-bottom: 1px solid var(--border); }}
.histhead {{ display: flex; gap: 0.7rem; align-items: baseline; flex-wrap: wrap; padding: 0.6rem 0.5rem; cursor: pointer; border-radius: 8px; }}
.histhead:hover {{ background: var(--hover); }}
.hist-ans {{ font-size: 15px; font-weight: 600; color: var(--text); }}
.hist-meta {{ font-size: 0.8rem; color: var(--muted); }}
.hist-res {{ margin-left: auto; font-size: 0.8rem; font-weight: 600; font-variant-numeric: tabular-nums; white-space: nowrap; }}
.hist-res.c {{ color: var(--good); }} .hist-res.w {{ color: var(--bad); }} .hist-res.d {{ color: var(--muted); }}
.histbody {{ display: none; padding: 0.3rem 0.5rem 0.9rem; }}
.histbody.show {{ display: block; }}
.histbody .qfull {{ font-size: 15px; line-height: 1.65; color: var(--text); }}
.histbody .answerline {{ margin-top: 0.5rem; font-size: 15px; display: block; }}
#histmore {{ margin-top: 0.8rem; }}

/* ---------- missed clues report ---------- */
.mc {{ border: 1px solid var(--border); border-radius: 12px; margin-bottom: 0.8rem; overflow: hidden; }}
.mc-head {{ display: flex; align-items: center; gap: 0.55rem; padding: 0.6rem 0.8rem 0.5rem; flex-wrap: wrap; }}
.mc-depth {{ font-variant-numeric: tabular-nums; font-size: 0.86rem; font-weight: 600; min-width: 2.6rem; text-align: right; color: var(--text); }}
.mc-depth small {{ font-weight: 400; font-size: 0.68rem; color: var(--muted); }}
.mc-res {{ font-size: 0.72rem; padding: 0.05rem 0.45rem; border-radius: 99px; border: 1px solid; }}
.mc-res.dead {{ color: var(--muted); border-color: var(--border); }}
.mc-res.neg {{ color: var(--bad); border-color: var(--bad); }}
.mc-res.ok {{ color: var(--good); border-color: var(--good); }}
.mc-ans {{ font-weight: 600; color: var(--text); font-size: 0.94rem; }}
.mc-ans a {{ font-size: 0.78rem; font-weight: 400; margin-left: 0.3rem; }}
.mc-meta {{ margin-left: auto; font-size: 0.76rem; color: var(--muted); white-space: nowrap; }}
.mc-bar {{ height: 3px; background: var(--line2); position: relative; }}
.mc-bar i {{ position: absolute; left: 0; top: 0; bottom: 0; }}
.mc-bar i.neg {{ background: var(--bad); }}
.mc-bar i.ok {{ background: var(--good); }}
.mc-bar i.dead {{ background: var(--faint2, var(--border)); }}
.mc-q + .mc-q {{ border-top: 1px solid var(--border); }}
.mc-query {{ padding: 0.55rem 0.8rem 0.55rem; font-size: 0.86rem; color: var(--muted); border-bottom: 1px solid var(--line2); }}
.mc-query .lbl {{ font-size: 0.72rem; color: var(--faint); display: block; margin-bottom: 0.1rem; }}
.mc-sim {{ padding: 0.35rem 0.8rem 0.55rem; }}
.mc-sim .cluenote {{ padding: 0.35rem 0; }}
.mc-sim .clueitem {{ margin: 0; padding-left: 0; padding-right: 0; border-color: var(--line2); }}
.simtoggle {{ background: none; border: none; color: var(--link); font-size: 0.8rem; cursor: pointer; padding: 0.2rem 0; }}
.simlist {{ display: none; }}
.simlist.open {{ display: block; }}
@media (prefers-reduced-motion: reduce) {{ .timerbar i {{ transition: none !important; }} }}
/* Multiplayer rooms (reader.js "multiplayer rooms"): the scoreboard strip
   on the question card, the room popover, and guest mode, where the
   host's scope/difficulty/speed/sentence pills don't apply. */
.roombar {{ display: flex; flex-wrap: wrap; align-items: center; gap: 0.3rem 0.4rem; margin-bottom: 0.6rem;
  font-size: 0.84rem; font-variant-numeric: tabular-nums; }}
.roombar[hidden] {{ display: none; }}
.roombar .rcode {{ background: none; border: none; padding: 0; color: var(--muted); font-size: 0.78rem;
  letter-spacing: 0.04em; margin-right: 0.2rem; }}
.roombar .rcode:hover {{ color: var(--link); }}
.roombar .rp {{ border: 1px solid var(--border); border-radius: 99px; padding: 0.1rem 0.6rem; white-space: nowrap; }}
.roombar .rp b {{ font-weight: 600; margin-left: 0.15rem; }}
.roombar .rp.me {{ border-color: var(--pickline); background: var(--pick); color: var(--bright); }}
.roombar .rp.buzz {{ border-color: var(--accent); box-shadow: 0 0 0 2px var(--accent-dim); }}
.roombar .rp.out {{ opacity: 0.5; text-decoration: line-through; }}
.roombar .rp.off {{ border-style: dashed; color: var(--faint); }}
.roombar .rwarn {{ color: var(--warn); font-size: 0.78rem; }}
.rmrow {{ display: flex; gap: 0.4rem; margin-top: 0.6rem; }}
.rmrow input, #roompanel .setting input {{ flex: 1; min-width: 0; background: var(--bg); border: 1px solid var(--border);
  border-radius: 6px; color: var(--text); padding: 0.4rem 0.55rem; font-size: 0.9rem; font-family: var(--sans); }}
#roompanel .setting input {{ display: block; width: 100%; margin-top: 0.25rem; }}
#rm-code {{ text-transform: uppercase; letter-spacing: 0.12em; max-width: 7.5rem; text-align: center; }}
.rmrow input:focus, #roompanel .setting input:focus {{ outline: none; border-color: var(--link); }}
.rmcode {{ letter-spacing: 0.08em; margin-left: 0.35rem; color: var(--bright); }}
.rmerr:empty {{ display: none; }}
/* In a room everyone's controls edit the shared settings, except multibuzz
   (rooms use lockouts) and, for players, drill (it's built from the host's
   own history). */
body[data-room="host"] label:has(#multibuzz), body[data-room="host"] #multibuzzrow,
body[data-room="guest"] label:has(#multibuzz), body[data-room="guest"] #multibuzzrow,
body[data-room="guest"] label:has(#drill), body[data-room="guest"] #drillrow {{ display: none; }}
/* Room chat, under the question card. */
.chatpanel {{ margin-top: 1.2rem; border: 1px solid var(--border); border-radius: 12px; padding: 0.55rem 0.8rem 0.7rem; }}
.chatpanel[hidden] {{ display: none; }}
.chatlog {{ max-height: 9.5rem; overflow-y: auto; font-size: 0.86rem; line-height: 1.45; padding: 0.1rem 0 0.35rem; }}
.chatlog .cl {{ overflow-wrap: anywhere; }}
.chatlog .cl b {{ font-weight: 600; color: var(--bright); }}
.chatlog .cl.me b {{ color: var(--link); }}
.chatlog .cl.sys {{ color: var(--faint); font-size: 0.8rem; }}
#chatinput {{ width: 100%; background: var(--bg); border: 1px solid var(--border); border-radius: 6px; color: var(--text);
  padding: 0.4rem 0.55rem; font-size: 0.9rem; font-family: var(--sans); }}
#chatinput:focus {{ outline: none; border-color: var(--link); }}
.chatlog .bline {{ font-size: inherit; margin: 1px 0; }}
.chatlog .bline .bnote {{ font-size: inherit; }}
.chatlog .bbadge {{ font-size: 10px; }}
/* Previous questions: collapsed cards under the chat, newest first. */
.qhist {{ margin-top: 1.2rem; display: flex; flex-direction: column; gap: 8px; }}
.qhist:empty {{ display: none; }}
.qh {{ border: 1px solid var(--border); border-radius: 10px; overflow: hidden; }}
.qh-head {{ display: flex; align-items: baseline; gap: 12px; width: 100%; background: var(--raised); border: none;
  color: var(--text); padding: 9px 14px; text-align: left; font-size: 15px; font-family: var(--sans); }}
.qh-head:hover {{ background: var(--hover); }}
.qh-ans {{ flex: 1; min-width: 0; }}
.qh-meta {{ font-size: 12px; color: var(--muted); white-space: nowrap; }}
.qh-res {{ font-size: 12px; font-weight: 600; white-space: nowrap; color: var(--muted); }}
.qh-res.ok {{ color: var(--good); }}
.qh-res.neg {{ color: var(--bad); }}
.qh-body {{ display: none; padding: 2px 14px 12px; }}
.qh.open .qh-body {{ display: block; }}
.qh.open .qh-head {{ border-bottom: 1px solid var(--line2); }}
.qh .qtext {{ font-size: calc(var(--qsize, 17px) * 0.92); min-height: 0; margin-top: 10px; }}
.qh .ansline {{ margin-top: 10px; }}
.qh-foot {{ display: flex; gap: 6px 14px; flex-wrap: wrap; font-size: 13px; color: var(--muted); margin-top: 8px; }}
html[data-layout="mobile"] .qh-meta {{ display: none; }}
/* Score table above "This session": each player's powers/10s/negs/0s and points. */
.scorebox {{ margin-bottom: 18px; }}
.sbt {{ width: 100%; border-collapse: collapse; font-variant-numeric: tabular-nums; }}
.sbt th {{ font-size: 11px; font-weight: 600; color: var(--muted); text-align: center; padding: 0 4px 6px;
  border-bottom: 1px solid var(--line2); }}
.sbt th.nm {{ text-align: left; font-size: 15px; color: var(--text); padding-left: 0; }}
.sbt td {{ text-align: center; font-size: 15px; padding: 7px 4px; border-bottom: 1px solid var(--line2); color: var(--text); }}
.sbt td.nm {{ text-align: left; padding-left: 0; max-width: 120px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }}
.sbt th.pts, .sbt td.pts {{ text-align: right; padding-right: 0; }}
.sbt td.pts {{ font-weight: 700; font-size: 17px; }}
.sbt td.pw {{ color: var(--accent); font-weight: 600; }}
.sbt td.ng {{ color: var(--bad); font-weight: 600; }}
.sbt tr.me td.nm {{ font-weight: 600; color: var(--bright); }}
.sbt tr.off td {{ color: var(--faint); }}
.sbt tr.buzz td.nm {{ color: var(--link); font-weight: 700; }}
.sbt tr.buzz td.nm::after {{ content: ' · buzzed'; font-size: 11px; font-weight: 600; }}
.sbt tr.out td.nm {{ text-decoration: line-through; color: var(--muted); }}
/* With the score table showing, the strip above the question keeps only the
   room code and connection warnings; narrower pages (no table) keep the
   player chips. */
.wrap:has(#sessrail:not([hidden])) .roombar .rp {{ display: none; }}
.sbcel {{ font-size: 12px; color: var(--muted); margin-top: 6px; text-align: right; }}
/* Another player's answer as they type it, under the frozen question. */
.liveans {{ margin-top: 10px; font-size: 0.95rem; color: var(--text); background: var(--raised);
  border-radius: 10px; padding: 0.45rem 0.8rem; overflow-wrap: anywhere; }}
.liveans[hidden] {{ display: none; }}
.liveans b {{ font-weight: 600; margin-right: 0.3rem; }}
.liveans .dots {{ color: var(--faint); }}
</style>
</head>
<body>
<header class="topbar" id="topbar">
  <a class="home" href="index.html">Library of Stock</a><span class="crumb">/ Reader</span>
  <span class="sp"></span>
  <button class="menubtn" id="open-menu" aria-expanded="false" aria-controls="viewtabs">Menu</button>
  <nav class="viewtabs" id="viewtabs">
    <button id="tab-play" class="on">Reader</button>
    <button id="tab-stats">My stats</button>
    <button id="tab-missed">Missed clues</button>
    <button id="tab-history">History</button>
    <a class="tab" href="wiki.html">Wiki</a>
    <button id="pill-room" data-pop="room" aria-haspopup="dialog"><span id="pl-room">Multiplayer</span></button>
    <button id="open-sync" data-pop="sync" style="display:none">Sign in</button>
  </nav>
</header>

<div class="wrap" id="wrap" data-view="play">
  <div class="pills" id="pills">
    <button class="pill" id="pill-scope" aria-haspopup="dialog" aria-controls="catmodal"><span id="pl-scope">All categories</span><span class="c">&#9662;</span></button>
    <button class="pill" id="pill-set" data-pop="set" aria-haspopup="dialog"><span id="pl-set">Any set</span><span class="c">&#9662;</span></button>
    <button class="pill" id="pill-diff" data-pop="diff" aria-haspopup="dialog"><span id="pl-diff">Difficulty</span><span class="c">&#9662;</span></button>
    <button class="pill" id="pill-speed" data-pop="speed" aria-haspopup="dialog"><span id="pl-speed">380 wpm</span><span class="c">&#9662;</span></button>
    <button class="pill" id="pill-sent" data-pop="sent" aria-haspopup="dialog"><span id="pl-sent">Full question</span><span class="c">&#9662;</span></button>
    <button class="pill" id="pill-text" data-pop="text" aria-haspopup="dialog"><span id="pl-text">Text 17px</span><span class="c">&#9662;</span></button>
    <button class="pill" id="pill-more" data-pop="more" aria-haspopup="dialog">More<span class="c">&#9662;</span></button>
    <span class="sessline" id="sessline"></span>
  </div>

  <div class="stage">
  <main>
    <section id="view-play">
      <div class="qcard" id="qcard">
        <div class="roombar" id="roombar" hidden></div>
        <div class="qmeta">
          <span id="m-cat"></span><span class="diff" id="m-diff"></span>
          <span class="status" id="m-status"></span>
        </div>
        <div class="progline" aria-hidden="true">
          <div class="qprog"><i id="qprogfill"></i></div>
          <div class="timerbar"><i id="timerfill"></i></div>
        </div>
        <div class="qtext" id="qtext"></div>
        <div class="liveans" id="liveans" hidden aria-live="polite"></div>
        <div class="hint taplookup" id="taplookup" style="display:none">Tap any sentence to find similar clues from other questions.</div>
        <div class="answerrow" id="answerrow">
          <input id="answerinput" type="text" placeholder="Answer&hellip;" autocomplete="off" spellcheck="false" aria-label="Your answer">
        </div>
        <div class="judge" id="judge">
          <div class="ansline"><span class="anslbl">ANSWER:</span> <span class="answerline" id="answerline"></span> <a id="j-guide" href="#"></a></div>
          <div class="verdict" id="verdict"></div>
        </div>
        <div class="srcline" id="srcline"><span id="m-set"></span><span id="m-src"></span></div>
        <div class="controls">
          <button class="btn primary big" id="mainbtn" disabled>Start</button>
          <div class="selfgrade" id="selfgrade" style="display:none">
            <button class="btn sg" id="sg-right" title="Override the checker: count it correct">I was right</button>
            <button class="btn sg" id="sg-wrong" title="Override the checker: count it wrong">I was wrong</button>
          </div>
          <div class="quietrow">
            <button class="btn quiet" id="pausebtn" data-kbd="P" disabled>Pause</button>
            <button class="btn quiet" id="skipbtn" data-kbd="S" disabled title="Not counted in stats">Skip</button>
            <button class="btn quiet" id="prevbtn" data-kbd="K" disabled title="Review the previous question (k)">Previous</button>
          </div>
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
      </div>
      <section class="chatpanel" id="chatpanel" hidden aria-label="Room chat">
        <div class="chatlog" id="chatlog" aria-live="polite"></div>
        <input id="chatinput" type="text" maxlength="300" placeholder="Message the room (Enter)" autocomplete="off" aria-label="Message the room">
      </section>
      <section class="qhist" id="qhist" aria-label="Previous questions"></section>
      <div id="qspacer" hidden></div>
    </section>

    <section id="view-stats" style="display:none">
      <div class="statgrid" id="statgrid"></div>
      <div class="statnote" id="statnote"></div>
      <div id="statbody"></div>
    </section>

    <section id="view-missed" style="display:none">
      <div class="statnote" id="missednote"></div>
      <div id="missedlist"></div>
    </section>

    <section id="view-history" style="display:none">
      <div class="histsearch"><input id="histq" type="search" placeholder="Search answer, category, set&hellip;" autocomplete="off"></div>
      <div class="statnote" id="histnote"></div>
      <div id="histlist"></div>
    </section>
  </main>

  <aside class="side" id="cluepanel" aria-live="polite">
    <div class="cluehead">
      <div class="sidehead"><h3>Similar clues</h3><button class="quietbtn" id="clueclose" aria-label="Close similar clues">Close</button></div>
      <div id="cluequery"></div>
    </div>
    <div id="cluebody"></div>
    <div id="cluefoot"></div>
  </aside>

  <aside class="side" id="sessrail" hidden>
    <div class="scorebox" id="scorebox"></div>
    <div class="sidehead"><h3>This session</h3><button class="linkbtn" id="rail-stats">My stats</button></div>
    <div id="rail-list"></div>
  </aside>
  </div>
</div>

<div id="mbar">
  <div id="mbar-timer"></div>
  <div class="mbar-main"><button class="btn primary big" id="m-main" disabled>Start</button></div>
  <div class="mbar-btns">
    <button class="btn quiet" id="m-pause" disabled>Pause</button>
    <button class="btn quiet" id="m-skip" disabled>Skip</button>
    <button class="btn quiet" id="m-prev" disabled title="Previous question">Previous</button>
  </div>
</div>

<div class="cmodal" id="catmodal" hidden role="dialog" aria-modal="true" aria-labelledby="cattitle">
  <div class="cbox">
    <div class="chead"><h2 id="cattitle">Select Categories</h2>
      <button type="button" class="tog" id="cattoggle">Toggle all</button>
      <span class="cnt" id="catcount"></span>
      <button type="button" class="x" id="catclose" aria-label="Close">&times;</button></div>
    <div class="ccols">
      <div><h3>Category</h3><div id="c-cat"></div></div>
      <div><h3>Subcategory</h3><div id="c-sub"></div></div>
      <div><h3>Alternate Subcategory</h3><div id="c-alt"></div></div>
      <div class="gcol"><h3>Group</h3><div id="c-grp"></div></div>
    </div>
  </div>
</div>

<!-- Setting popovers: anchored dropdowns on desktop, bottom sheets on a
     phone. Each holds the reader's existing control panels, unchanged. -->
<div class="los-sheet pop" id="pop-set" role="dialog" aria-label="Set">
  <div class="los-sheet-handle"></div>
  <div class="los-sheet-body">
    <div class="panel">
      <h2>Set <button class="linkbtn" id="setany" style="margin-left:auto">Any set</button></h2>
      <input class="setsearch" id="setq" type="search" placeholder="Search sets" autocomplete="off" aria-label="Search sets">
      <div class="setlist" id="setlist"></div>
      <div id="setdetail" hidden>
        <div class="prange"><label for="pfrom">Packets</label><select class="pksel" id="pfrom"></select><span>to</span><select class="pksel" id="pto" aria-label="to packet"></select></div>
        <div id="setmap"></div>
        <div class="setfoot"><span id="setfoot"></span><button class="linkbtn" id="setstats">Stats for this set</button></div>
      </div>
    </div>
  </div>
</div>
<div class="los-sheet pop" id="pop-diff" role="dialog" aria-label="Difficulty">
  <div class="los-sheet-handle"></div>
  <div class="los-sheet-body">
    <div class="panel" id="panel-diff">
      <h2>Difficulty</h2>
      <div class="chips" id="f-diffs"></div>
      <div class="hint">Pick one or more levels. None picked means every level.</div>
    </div>
  </div>
</div>
<div class="los-sheet pop" id="pop-speed" role="dialog" aria-label="Reading speed">
  <div class="los-sheet-handle"></div>
  <div class="los-sheet-body">
    <div class="panel">
      <label class="setting">Speed: <span class="val" id="wpmval"></span> wpm
        <input type="range" id="wpm" min="120" max="700" step="10">
      </label>
    </div>
  </div>
</div>
<div class="los-sheet pop" id="pop-sent" role="dialog" aria-label="Sentences read">
  <div class="los-sheet-handle"></div>
  <div class="los-sheet-body">
    <div class="panel">
      <label class="setting" style="margin-bottom:0.25rem">Sentences read</label>
      <div class="seg" id="sentmode">
        <button data-n="0" class="on">Full question</button>
        <input type="number" id="sentn" min="1" max="99" inputmode="numeric" placeholder="last n" aria-label="read only the last n sentences">
        <button id="sentscore" title="read only sentences containing musical notation">&#9834; Score</button>
      </div>
      <label class="drilltoggle" id="scoregrow" style="display:none"><input type="checkbox" id="scoregive" checked> Also read the giveaway</label>
      <div class="hint" id="senthint">Type a number to read only the last n sentences.</div>
      <div class="hint" id="scorehint" style="display:none">Only sentences containing musical notation (note runs) are revealed; other clues collapse into tappable pills. The scope narrows to questions with notation, and read-aloud is unavailable in this mode.</div>
    </div>
  </div>
</div>
<div class="los-sheet pop" id="pop-text" role="dialog" aria-label="Text size">
  <div class="los-sheet-handle"></div>
  <div class="los-sheet-body">
    <div class="panel">
      <label class="setting">Text size: <span class="val" id="fsizeval"></span>
        <input type="range" id="fsize" min="13" max="28" step="1">
      </label>
    </div>
  </div>
</div>
<div class="los-sheet pop" id="pop-more" role="dialog" aria-label="More settings">
  <div class="los-sheet-handle"></div>
  <div class="los-sheet-body">
    <div class="panel" id="panel-reading">
      <h2>Reading</h2>
      <label class="setting drilltoggle" id="voicetoggle"><input type="checkbox" id="voice"> Read aloud (voice)</label>
      <div id="voicerow" style="display:none">
        <label class="setting">Voice speed: <span class="val" id="vrateval"></span>
          <input type="range" id="vrate" min="0.6" max="1.6" step="0.05">
        </label>
      </div>
      <label class="setting drilltoggle"><input type="checkbox" id="multibuzz"> Multiple buzzes</label>
      <div id="multibuzzrow" style="display:none">
        <div class="hint">Wrong answers resume the reading. The first neg still counts.</div>
      </div>
      <label class="setting drilltoggle"><input type="checkbox" id="drill"> Drill my weaknesses</label>
      <div id="drillrow" style="display:none">
        <label class="setting">Focus: <span class="val" id="focusval">balanced</span>
          <input type="range" id="focus" min="0" max="100" value="55">
        </label>
      </div>
      <details class="distpanel" id="distpanel">
        <summary>Category distribution</summary>
        <label class="setting disttoggle"><input type="checkbox" id="usedist" checked> Follow distribution</label>
        <label class="setting disttoggle"><input type="checkbox" id="exactdist"> Take turns exactly instead of at random</label>
        <div class="dtree" id="disttree"></div>
        <div class="distfoot">
          <button class="linkbtn" id="distreset">Reset to standard</button>
          <span class="disttotal" id="disttotal"></span>
        </div>
      </details>
      <div class="hint kbdhint"><kbd>Space</kbd> buzz &middot; <kbd>Enter</kbd> submit &middot; <kbd>N</kbd> next &middot; <kbd>K</kbd> show/hide the last question &middot; <kbd>S</kbd> skip &middot; <kbd>P</kbd> pause</div>
      <div class="hint taphint">Skip is never counted. Swipe the question left to skip or advance, right to go back.</div>
    </div>
    <div class="panel" id="panel-cluesearch">
      <h2>Clue search</h2>
      <div class="seg" id="csmode">
        <button data-m="cloud">Cloud</button>
        <button data-m="local">In browser</button>
      </div>
      <div class="hint">Cloud needs sign in. In browser runs the model on this device, 600 MB, downloads once.</div>
      <div class="hint" id="csprog" style="display:none"></div>
    </div>
  </div>
</div>
<div class="los-sheet pop" id="pop-room" role="dialog" aria-label="Multiplayer">
  <div class="los-sheet-handle"></div>
  <div class="los-sheet-body">
    <div class="panel" id="roompanel"></div>
  </div>
</div>
<div class="los-sheet pop" id="pop-sync" role="dialog" aria-label="Sync">
  <div class="los-sheet-handle"></div>
  <div class="los-sheet-body">
    <div class="panel" id="syncpanel" style="display:none">
      <h2>Sync</h2>
      <div id="syncbody"></div>
    </div>
  </div>
</div>

<script src="lib/js/qdata.js?v={js_v('qdata.js')}"></script>
<script src="lib/js/mobile.js?v={js_v('mobile.js')}"></script>
<script src="lib/js/answer_checker.js?v={js_v('answer_checker.js')}"></script>
<script src="lib/js/reveal_units.js?v={js_v('reveal_units.js')}"></script>
<script src="lib/js/clue_search.js?v={js_v('clue_search.js')}"></script>
<script src="lib/js/reader_room.js?v={js_v('reader_room.js')}"></script>
<script src="lib/js/reader.js?v={js_v('reader.js')}"></script>
<script src="lib/js/sync.js?v={js_v('sync.js')}"></script>
</body>
</html>
"""


def build() -> None:
    out_path = ROOT / "reader.html"
    out_path.write_text(page_html(), encoding="utf-8")
    print("Built reader.html")


if __name__ == "__main__":
    build()
