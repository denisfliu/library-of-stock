"""Searchable browser over the corpus of binary cards (corpus_cards.py output).

Styled like the Library of Stock study pages: each binary card is a
clue-table row (count + placement track under it, clue text, hover for
another phrasing), grouped by answerline. One page covers every scope
built (the whole corpus): search by answer, key phrase or clue text;
filter like qbreader (category -> subcategory -> alternate subcategory,
difficulties, years, tossups / bonuses) and by how many tiers confirm a card.

Data is sharded so the page stays light:
    data/index.json   qbreader's taxonomy, then one row per answerline:
                      name, category / subcategory / alternate, parent,
                      key phrases (for instant search) and two ints per
                      card (gcode: tiers, difficulties, type; ymask: set
                      years), so filter counts never need the card text;
    data/cards_N.json card text, ~1.5 MB per shard, fetched on demand.

Usage: python dev/binary/browse.py [--standalone]   -> out/browse/
       (--standalone drops the links to other site pages, for sharing
        the folder on its own)
       python dev/binary/browse.py --upload         -> binaries.html + R2
       (publish on the site: upload the data, then commit binaries.html)
"""
import argparse
import gzip
import hashlib
import json
import os
import re
import subprocess
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from common import BASE_OUT, ROOT
from keys import SCOPES
from lib.render.theme import base_css, site_nav, site_nav_css

SHARD_BYTES = 1_500_000
# --site: the page goes to the repo root (binaries.html, deployed with the
# wiki and reader); its data to the site's R2 bucket, in a content-hashed
# folder (the data comes from the local corpus, so CI can't rebuild it).
R2_BASE = "https://pub-b5f94e8d4cc648abb0e35b7ca4444c65.r2.dev"   # = lib/js/qdata.js QDATA_BASE
R2_BUCKET = "library-of-stock-data"                                 # = lib/mirror/publish.py
R2_PREFIX = "binaries"
YEAR0 = 2000                       # year bitmask: bit (year - YEAR0), earlier years clamp to bit 0
YEAR1 = YEAR0 + 30                 # 31 bits stay positive in JS bitwise ops


def gcode(c):
    """One int per card for the filters: tiers (bits 0-2), difficulties
    0-10 (bits 3-13, 0 = unknown), question type (bits 14-15: tossup, bonus)."""
    g = c["t"]
    for d in c["d"]:
        g |= 1 << (3 + d)
    return g | c.get("ty", 3) << 14


def ymask(c):
    m = 0
    for y in c.get("y", []):
        m |= 1 << (min(max(y, YEAR0), YEAR1) - YEAR0)
    return m


def taxonomy():
    """qbreader's category tree, in qbreader's order."""
    from qbmirror import query
    return dict(cats=query.CATEGORIES, subs=query.CATEGORY_TO_SUBCATEGORY,
                alts=query.CATEGORY_TO_ALTERNATE_SUBCATEGORIES)


def render(nav, title, data_base):
    return (PAGE.replace("/*BASE_CSS*/", base_css(max_width="1000px", body_padding="1.4rem 16px 4rem")
                         + site_nav_css())
            .replace("<!--NAV-->", nav).replace("/*TITLE*/", title)
            .replace("/*DATA*/", json.dumps(data_base))
            .replace("�", "&#xFFFD;"))


def version(data: Path) -> str:
    """Content hash of the data files: the R2 folder name, so a published
    page and its data never mix across rebuilds (and cache forever)."""
    h = hashlib.sha256()
    for f in sorted(data.glob("*.json")):
        h.update(f.name.encode())
        h.update(f.read_bytes())
    return h.hexdigest()[:12]


def upload(data: Path, bucket=R2_BUCKET, workers=6):
    """Pre-gzipped, like lib/mirror/publish.py (r2.dev does no edge compression)."""
    prefix = f"{R2_PREFIX}/{version(data)}"
    gz_dir = data.parent / "gz"
    gz_dir.mkdir(exist_ok=True)

    def put(f):
        gz = gz_dir / f.name
        gz.write_bytes(gzip.compress(f.read_bytes(), 6, mtime=0))
        proc = subprocess.run(["npx", "wrangler", "r2", "object", "put", f"{bucket}/{prefix}/{f.name}",
                               "--file", str(gz), "--content-type", "application/json",
                               "--content-encoding", "gzip",
                               "--cache-control", "public, max-age=31536000, immutable", "--remote"],
                              capture_output=True, text=True, encoding="utf-8", shell=(os.name == "nt"))
        gz.unlink(missing_ok=True)
        return f.name, proc.returncode, proc.stderr.strip()[-300:]

    with ThreadPoolExecutor(workers) as pool:
        bad = [(n, err) for n, rc, err in pool.map(put, sorted(data.glob("*.json"))) if rc]
    for n, err in bad:
        print(f"FAILED {n}: {err}")
    print(f"uploaded r2://{bucket}/{prefix}/" if not bad else f"{len(bad)} uploads failed")
    return not bad


def build(out_dir: Path, standalone: bool, site: bool = False):
    rows = []
    for scope in SCOPES:
        p = BASE_OUT / f"corpus_cards_{scope}.json"
        if p.exists():
            rows += json.load(open(p, encoding="utf-8"))["answerlines"]
    # An answerline with no usable name (an empty answer string in the
    # source) can't be shown or searched.
    rows = [r for r in rows if (r["answer"] + r["key"]).replace("�", "").strip(" \"'")]
    # One answerline can live in both scopes (Emily Dickinson: 174 literature
    # cards, 1 music card): merge by id, keeping the bigger one's metadata.
    merged = {}
    for r in rows:
        m = merged.get(r["id"])
        if m is None:
            merged[r["id"]] = r
            continue
        big, small = (m, r) if len(m["cards"]) >= len(r["cards"]) else (r, m)
        seen = {c["f"] for c in big["cards"]}
        merged[r["id"]] = dict(big, cards=big["cards"] + [c for c in small["cards"] if c["f"] not in seen])
    rows = list(merged.values())
    rows.sort(key=lambda r: -len(r["cards"]))
    # Works under their creator, characters under their work (or straight
    # under the creator: Macbeth), biggest first. A person with a parent is
    # a character: keys.ParentRule never climbs real people.
    kids = {}
    cat_of = {r["id"]: r["cat"] for r in rows}
    for r in rows:
        if r["kind"] not in ("work", "person"):     # "B minor", "toccata" are not works
            continue
        for p in r.get("parent_id", [])[:1]:
            # Same category only: Odets's Golden Boy (Joe Bonaparte, literature)
            # is not a Napoleon (history) work.
            if cat_of.get(p) == r["cat"]:
                kids.setdefault(p, []).append(r["id"])
    ids = {r["id"] for r in rows}
    data = out_dir / "data"
    data.mkdir(parents=True, exist_ok=True)
    for old in data.glob("cards_*.json"):
        old.unlink()
    index, shard, size, n_shard = [], {}, 0, 0
    for r in rows:
        # broken source encodings; the "(*)" power marker; mid-sentence "for 10 points"
        def clean(t):
            t = re.sub(r"\s*\(\*\)\s*", " ", t.replace("�", ""))
            t = re.sub(r",?\s*\b(?:for (?:10|ten) points|FTP)\b,?\s*", " ", t, flags=re.I)
            return re.sub(r"\s+", " ", t).strip()
        cards = [dict(f=clean(c["f"][:420]), t=c["t"], q=c["q"], p=c["p"], g=gcode(c), y=ymask(c), w=c.get("w", 0), u=c.get("u", ""), k=c["k"],
                      x=clean(c["x"][:300])) for c in r["cards"]]
        shard[str(r["id"])] = cards
        size += len(json.dumps(cards, ensure_ascii=False).encode())
        name = r["answer"].replace("�", "").strip(" \"'") and r["answer"].replace("�", "") or r["key"]
        index.append(dict(i=r["id"], a=name, c=r["cat"], s=r["sub"], l=r.get("alt"),
                          par=r["parent"][:1], sh=n_shard, p=int(r["kind"] == "person"),
                          ch=[k for k in kids.get(r["id"], []) if k in ids][:80],
                          kp=" | ".join(sorted({k for c in r["cards"] for k in c["k"]}))[:600],
                          g=[gcode(c) for c in r["cards"]], y=[ymask(c) for c in r["cards"]]))
        if size >= SHARD_BYTES:
            json.dump(shard, open(data / f"cards_{n_shard}.json", "w", encoding="utf-8"), ensure_ascii=False)
            shard, size, n_shard = {}, 0, n_shard + 1
    if shard:
        json.dump(shard, open(data / f"cards_{n_shard}.json", "w", encoding="utf-8"), ensure_ascii=False)
        n_shard += 1
    json.dump(dict(shards=n_shard, year0=YEAR0, tax=taxonomy(), answerlines=index), open(data / "index.json", "w", encoding="utf-8"),
              ensure_ascii=False, separators=(",", ":"))
    if site:
        page = render(site_nav("", "binaries"), "Binaries — Library of Stock", f"{R2_BASE}/{R2_PREFIX}/{version(data)}/")
        (ROOT / "binaries.html").write_text(page, encoding="utf-8")
    nav = ('<nav class="site-nav"><span class="site-home">Library of Stock</span>'
           '<span class="here">Binaries</span><span class="site-sp"></span></nav>') if standalone         else site_nav("", "binaries")
    (out_dir / "index.html").write_text(render(nav, "Binary Clue Browser", "data/"), encoding="utf-8")
    n_cards = sum(len(r["cards"]) for r in rows)
    print(f"{len(index):,} answerlines, {n_cards:,} cards, {n_shard} shards -> {out_dir}")


PAGE = r"""<meta charset="utf-8">
<title>/*TITLE*/</title>
<style>
[hidden] { display: none !important; }
/*BASE_CSS*/
.site-nav .site-home { color: var(--c-text); font-weight: 600; }
.site-nav .here { color: var(--c-text); }
h1 { margin-bottom: .9rem; }
.controls { display: grid; gap: .6rem; margin-bottom: 1rem; }
.search { width: 100%; font: inherit; font-size: 15px; padding: .55rem .8rem; border-radius: 10px;
          border: 1px solid var(--c-border); background: var(--c-input); color: var(--c-text); }
.search:focus { outline: 2px solid var(--c-selline); outline-offset: 0; }
.row { display: flex; flex-wrap: wrap; gap: .4rem .9rem; align-items: center; font-size: 13px; color: var(--c-muted); }
.seg { display: inline-flex; border: 1px solid var(--c-border); border-radius: 99px; overflow: hidden; }
.seg button { font: inherit; font-size: 13px; background: var(--c-bg); color: var(--c-text); border: 0;
              padding: .18rem .65rem; cursor: pointer; border-left: 1px solid var(--c-border); }
.seg button:first-child { border-left: 0; }
.seg button[aria-pressed="true"] { background: var(--c-selbg); color: var(--c-bright); }
.seg button:focus-visible, .al-head:focus-visible, .more:focus-visible { outline: 2px solid var(--c-link); outline-offset: 2px; }
select { font: inherit; font-size: 13px; background: var(--c-bg); color: var(--c-text); border: 1px solid var(--c-border);
         border-radius: 8px; padding: .15rem .4rem; }
.status { font-size: 13px; color: var(--c-muted); margin: .2rem 0 .8rem; font-variant-numeric: tabular-nums; }
.al { border-top: 1px solid var(--c-border); }
.al-head { display: flex; flex-wrap: wrap; gap: .2rem .7rem; align-items: baseline; width: 100%; text-align: left;
           background: none; border: 0; color: inherit; font: inherit; padding: .4rem .2rem; cursor: pointer; }
.al-head:hover { background: var(--c-hover); }
.al-name { font-weight: 600; font-size: 14px; color: var(--c-bright); }
.al-par { font-size: 13px; color: var(--c-muted); }
.al-par a { color: var(--c-link); cursor: pointer; }
.al-cat { font-size: 12px; color: var(--c-faint); }
.al-n { margin-left: auto; font-size: 12px; color: var(--c-muted); font-variant-numeric: tabular-nums; }
.al-n b { color: var(--c-text); font-weight: 600; }
.al-body { padding: 0 0 .6rem; }
.loading { font-size: 13px; color: var(--c-muted); padding: .4rem .3rem; }
/* clue rows: the study-page clue table */
.clue-table { width: 100%; border-collapse: collapse; font-size: 12.5px; line-height: 1.4; }
.clue-row td { padding: .12rem .35rem; border-top: 1px solid var(--c-line2); vertical-align: baseline; }
.clue-row:hover td { background: var(--c-hover); }
.clue-freq { width: 1%; text-align: right; color: var(--c-muted); font-size: 12px; white-space: nowrap;
             font-variant-numeric: tabular-nums; padding-right: .6rem !important; }
.freq-n { display: inline-block; min-width: 2.1em; text-align: right; }
/* count and placement share one line, so the clue text sets the row height */
.freq-tools { display: inline-block; width: 24px; margin-left: 5px; vertical-align: middle; line-height: 0; }
.place { display: inline-block; position: relative; vertical-align: middle; width: 24px; height: 3px;
         border-radius: 2px; background: var(--c-border); }
.place-dot { position: absolute; top: 50%; width: 7px; height: 7px; border-radius: 50%;
             transform: translate(-50%, -50%); background: var(--c-muted); }
.place-early .place-dot { background: var(--c-warn); }
.place-late .place-dot { background: var(--c-good); }
.clue-body { min-width: 0; overflow-wrap: anywhere; }
.clue-text { color: var(--c-text); }
mark { background: var(--c-hl); color: var(--c-text); border-radius: 3px; padding: 0 .1rem; }
mark.key { background: var(--c-selbg); }
.bin { color: var(--c-text); }
.bin.is-key { color: var(--c-bright); font-weight: 500; }
.bin.hit { background: var(--c-hl); border-radius: 3px; }
.bin.title { font-style: italic; }                 /* a work, as quizbowl writes titles */
.bin.ent { font-variant: small-caps; letter-spacing: .02em; }   /* a character */
.work-link { cursor: pointer; }
.work-link:hover { color: var(--c-link); }
.go { color: var(--c-muted); padding: 0 .2rem; cursor: pointer; }
.go:hover { color: var(--c-link); text-decoration: none; }
.clue-row.sub .clue-body, tr.sub .all-rows { padding-left: 1.3rem; }
.clue-row.sub .clue-body { position: relative; }
.clue-row.sub .clue-body::before { content: ""; position: absolute; left: .55rem; top: .2rem; bottom: .2rem;
                                   border-left: 1px solid var(--c-border); }
.clue-row.sub .bin.is-key { font-weight: 400; color: var(--c-text); }
.alt { display: none; font-size: 12px; color: var(--c-muted); margin-top: .1rem; }
.alt p + p { margin-top: .2rem; }
.tier { width: 2.2rem; text-align: right; white-space: nowrap; }
.dots { display: inline-flex; gap: 3px; vertical-align: middle; }
.dots i { width: 5px; height: 5px; border-radius: 50%; background: var(--c-border); }
.dots i.on { background: var(--c-faint); }
.all-rows { font: inherit; font-size: 12px; color: var(--c-link); background: none; border: 0; padding: .15rem 0; cursor: pointer; }
.grp + .grp { margin-top: .35rem; }
.grp-h { display: flex; align-items: baseline; gap: .5rem; font-size: 12px; color: var(--c-muted); padding: .35rem .35rem .1rem; }
.grp-h a { color: var(--c-text); font-weight: 600; cursor: pointer; }
.grp-h a:hover { color: var(--c-link); }
.grp-n { font-variant-numeric: tabular-nums; }
.all-rows:focus-visible { outline: 2px solid var(--c-link); outline-offset: 2px; }
.clue-row.open .alt { display: block; }
.clue-row.has-alt { cursor: pointer; }
.more { display: block; margin: 1rem auto 0; font: inherit; font-size: 14px; padding: .4rem 1rem; border-radius: 99px;
        border: 1px solid var(--c-border); background: var(--c-bg); color: var(--c-text); cursor: pointer; }
.empty { color: var(--c-muted); padding: 1.5rem 0; }
/* filters */
.cat-btn, .clear { font: inherit; font-size: 13px; background: var(--c-bg); color: var(--c-text); border: 1px solid var(--c-border);
                   border-radius: 8px; padding: .15rem .6rem; cursor: pointer; }
.clear { border: 0; color: var(--c-link); padding: .15rem .2rem; }
.cat-sum { color: var(--c-text); min-width: 0; overflow-wrap: anywhere; }
.chips { display: flex; flex-wrap: wrap; gap: .3rem; }
.chips button { font: inherit; font-size: 12.5px; background: var(--c-bg); color: var(--c-text); border: 1px solid var(--c-border);
                border-radius: 99px; padding: .1rem .55rem; cursor: pointer; }
.chips button[aria-pressed="true"] { background: var(--c-selbg); color: var(--c-bright); border-color: var(--c-selline); }
.chips button:focus-visible, .cat-btn:focus-visible, .clear:focus-visible { outline: 2px solid var(--c-link); outline-offset: 2px; }
/* category picker: qbreader's modal (three columns of outlined, color-coded buttons) */
.modal { position: fixed; inset: 0; z-index: 50; background: rgba(0, 0, 0, .55); overflow-y: auto; padding: 1.75rem 16px; }
.modal-box { max-width: 800px; margin: 0 auto; background: var(--c-bg); border: 1px solid var(--c-border); border-radius: 8px; }
.modal-head { display: flex; align-items: center; gap: .6rem; padding: .8rem 1rem; border-bottom: 1px solid var(--c-border); }
.modal-head h2 { font-size: 17px; font-weight: 600; margin: 0; color: var(--c-bright); }
.modal-head .tog { font: inherit; font-size: 13px; background: #375a7f; color: #fff; border: 0; border-radius: 6px; padding: .25rem .65rem; cursor: pointer; }
.modal-head .x { margin-left: auto; font: inherit; font-size: 22px; line-height: 1; background: none; border: 0; color: var(--c-muted); cursor: pointer; }
.modal-cols { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 1rem; padding: 1rem; }
.modal-cols h3 { text-align: center; font-size: 15px; font-weight: 600; margin: 0 0 .4rem; color: var(--c-bright); }
.modal-cols .hint { text-align: center; color: var(--c-muted); font-size: 13px; margin: 0; }
.cb { display: block; width: 100%; margin: .25rem 0; padding: .3rem .5rem; font: inherit; font-size: 13.5px; cursor: pointer;
      background: transparent; border: 1px solid var(--k); color: var(--k); border-radius: 0; }
.cb[aria-pressed="true"] { background: var(--k); color: #fff; }
.cb:focus-visible, .modal-head button:focus-visible { outline: 2px solid var(--c-link); outline-offset: 2px; }
.k-lit { --k: #4f7cac; } .k-hist { --k: #00bc8c; } .k-sci { --k: #e74c3c; } .k-arts { --k: #fd7e14; } .k-other { --k: #8a9199; }
.diffs button { min-width: 2rem; padding: .1rem .4rem; font-variant-numeric: tabular-nums; }
.yr { width: 4.6rem; font: inherit; font-size: 13px; background: var(--c-input); color: var(--c-text);
      border: 1px solid var(--c-border); border-radius: 8px; padding: .12rem .4rem; }
@media (max-width: 575px) { .modal-cols { grid-template-columns: minmax(0, 1fr); } }

</style>

<!--NAV-->
<h1>Binaries</h1>

<div class="controls">
  <input id="q" class="search" type="search" placeholder="Bartók, Grand Inquisitor, cockroach…" autocomplete="off" aria-label="Search binaries">
  <div class="row">
    <button type="button" class="cat-btn" id="cat-btn" aria-haspopup="dialog">Categories</button>
    <span class="cat-sum" id="cat-sum">all</span>
    <button type="button" class="clear" id="cat-clear" hidden>clear</button>
  </div>
  <div class="modal" id="cat-modal" hidden role="dialog" aria-modal="true" aria-labelledby="cat-title">
    <div class="modal-box">
      <div class="modal-head"><h2 id="cat-title">Select Categories</h2>
        <button type="button" class="tog" id="toggle-all">Toggle all</button>
        <button type="button" class="x" id="cat-close" aria-label="Close">&times;</button></div>
      <div class="modal-cols">
        <div><h3>Category</h3><div id="f-cat"></div></div>
        <div><h3>Subcategory</h3><div id="f-sub"></div></div>
        <div><h3>Alternate Subcategory</h3><div id="f-alt"></div></div>
      </div>
    </div>
  </div>
  <div class="row">
    <span>Difficulty</span>
    <div class="chips diffs" id="f-diff" role="group" aria-label="Difficulties"></div>
  </div>
  <div class="row">
    <span>Years</span>
    <input class="yr" id="y-min" type="number" inputmode="numeric" aria-label="Minimum year">
    <span>–</span>
    <input class="yr" id="y-max" type="number" inputmode="numeric" aria-label="Maximum year">
    <span>Type</span>
    <div class="seg" id="f-type" role="group" aria-label="Question type">
      <button type="button" data-v="3" aria-pressed="true">both</button>
      <button type="button" data-v="1" aria-pressed="false">tossups</button>
      <button type="button" data-v="2" aria-pressed="false">bonuses</button>
    </div>
  </div>
  <div class="row">
    <span>Tiers</span>
    <div class="seg" id="f-conf" role="group" aria-label="Confirmation">
      <button type="button" data-v="any" aria-pressed="true">any</button>
      <button type="button" data-v="multi" aria-pressed="false">2+</button>
      <button type="button" data-v="key" aria-pressed="false">key</button>
    </div>
    <span>Sort</span>
    <div class="seg" id="f-sort" role="group" aria-label="Sort">
      <button type="button" data-v="n" aria-pressed="true">cards</button>
      <button type="button" data-v="az" aria-pressed="false">A–Z</button>
    </div>
  </div>
</div>
<div class="status" id="status" aria-live="polite">Loading…</div>
<div id="list"></div>
<button type="button" class="more" id="more" hidden>More</button>

<script>
(function () {
  "use strict";
  var DATA = /*DATA*/;
  var IDX = [], NSH = 0, SHARDS = {}, PENDING = {}, PAGE = 50;
  // cats / subs / alts: selected names (qbreader semantics: picking a
  // category picks all its subcategories and alternates; unpicking one of
  // those narrows the category).
  var S = { q: "", cats: {}, subs: {}, alts: {}, diffs: 0, ymin: 0, ymax: 0, type: 3, conf: "any", sort: "n",
            limit: PAGE, open: {}, allg: {} };
  var TAX = null, Y0 = 2000, YMASK = 0, SUBCAT = {}, ALTCAT = {};
  var $ = function (id) { return document.getElementById(id); };

  function esc(s) { return String(s).replace(/[&<>"]/g, function (c) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]; }); }
  function fold(s) { return String(s).normalize("NFKD").replace(/[̀-ͯ]/g, "").toLowerCase().replace(/[^\w\s]/g, " ").replace(/\s+/g, " ").trim(); }
  function bits(t) { return (t & 1) + ((t >> 1) & 1) + ((t >> 2) & 1); }
  // A card (g: tiers bits 0-2, difficulties 0-10 bits 3-13, tossup/bonus
  // bits 14-15; y: set-year bitmask) passes the filters?
  function passG(g, y) {
    var t = g & 7;
    if (S.diffs && !((g >> 3) & S.diffs)) return false;
    if (!((g >> 14) & S.type)) return false;
    if (YMASK && !(y & YMASK)) return false;
    if (S.conf === "multi" && bits(t) < 2) return false;
    if (S.conf === "key" && !(t & 1)) return false;
    return true;
  }
  // An entity row (a character with its own answerline) passes when any of
  // that answerline's cards do.
  function passAl(a) { for (var j = 0; j < a.g.length; j++) if (passG(a.g[j], a.y[j])) return true; return false; }
  function passCard(c) { return c.al && c.g == null ? passAl(c.al) : passG(c.g, c.y); }
  function setYears() {
    var lo = S.ymin || Y0, hi = S.ymax || Y0 + 30, m = 0;
    if (!S.ymin && !S.ymax) { YMASK = 0; return; }
    for (var y = Math.max(lo, Y0); y <= Math.min(hi, Y0 + 30); y++) m |= 1 << (y - Y0);
    YMASK = m || 1 << 31;              // empty range: bit 31, which no card has
  }
  function any(o) { for (var k in o) return true; return false; }
  // The answerline's place in the taxonomy passes the category filters?
  // (Off-taxonomy subcategories and answerlines without an alternate pass,
  // as qbreader's own search lets them.)
  function passTax(a) {
    if (!any(S.cats)) return true;
    if (!S.cats[a.c]) return false;
    if (a.s && a.s !== a.c && SUBCAT[a.s] === a.c && !S.subs[a.s]) return false;
    if (a.l && ALTCAT[a.l] === a.c && !S.alts[a.l]) return false;
    return true;
  }

  function shard(n) {
    if (SHARDS[n]) return Promise.resolve(SHARDS[n]);
    if (!PENDING[n]) PENDING[n] = fetch(DATA + "cards_" + n + ".json").then(function (r) { return r.json(); })
      .then(function (d) { SHARDS[n] = d; return d; });
    return PENDING[n];
  }
  var allLoading = null;
  function loadAll() {
    if (allLoading) return allLoading;
    var done = 0, ps = [];
    for (var i = 0; i < NSH; i++) ps.push(shard(i).then(function () { done++; if (S.q) setStatus(null, done); }));
    allLoading = Promise.all(ps);
    return allLoading;
  }

  // Search: answer names + key phrases instantly; clue text once shards load.
  function textHits(a, qf) {
    var d = SHARDS[a.sh]; if (!d) return null;
    var cards = d[a.i] || [], hit = [];
    for (var j = 0; j < cards.length; j++) if ((" " + fold(cards[j].f + " " + cards[j].x)).indexOf(" " + qf) >= 0) hit.push(j);
    return hit;
  }
  function results() {
    var qf = fold(S.q), out = [];
    for (var i = 0; i < IDX.length; i++) {
      var a = IDX[i];
      if (!passTax(a)) continue;
      var n = 0; for (var j = 0; j < a.g.length; j++) if (passG(a.g[j], a.y[j])) n++;
      if (!n) continue;
      var why = "";
      if (qf) {
        // Word-start matches: "odin" finds Odin, not Borodin.
        var at = function (s) { return (" " + s).indexOf(" " + qf) >= 0; };
        if (at(a.af) || (a.par.length && at(fold(a.par[0])))) why = "name";
        else if (at(a.kf)) why = "key";
        else { var h = textHits(a, qf); if (h && h.length) why = "text"; else continue; }
      }
      a._why = why;
      out.push({ a: a, n: n, why: why });
    }
    // A-Z on the folded name: leading quotes and punctuation don't count.
    if (S.sort === "az") out.sort(function (x, y) { return (x.a.af || "~").localeCompare(y.a.af || "~"); });
    else out.sort(function (x, y) { return (x.why === "name" ? 0 : 1) - (y.why === "name" ? 0 : 1) || y.n - x.n; });
    return out;
  }

  function setStatus(res, loaded) {
    var el = $("status");
    if (!res) { if (S.q && allLoading && loaded < NSH) el.textContent = "Searching… " + loaded + "/" + NSH; return; }
    var cards = 0; res.forEach(function (r) { cards += r.n; });
    var tail = S.q && Object.keys(SHARDS).length < NSH ? " · searching…" : "";
    el.textContent = res.length.toLocaleString() + " answerlines · " + cards.toLocaleString() + " cards" + tail;
  }

  function placeBar(p) {
    if (p < 0) return "";
    var zone = p >= 85 ? "late" : p <= 35 ? "early" : "mid";
    return '<span class="place place-' + zone + '" title="' + p + '% through tossup"><span class="place-dot" style="left:' + p + '%"></span></span>';
  }
  function keyRe(k) {
    return new RegExp("\\b(" + k.split(" ").map(function (w) { return w.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"); }).join("[\\W_]+") + ")\\b", "i");
  }
  function highlight(text, keys) {
    var t = esc(text);
    keys.slice().sort(function (a, b) { return b.length - a.length; }).forEach(function (k) {
      t = t.replace(keyRe(k), '<mark class="key">$1</mark>');
    });
    return t;
  }
  var SHOW = 8, SHOW_SUB = 3;
  function hitOf(c, qf) { return qf && (" " + fold(c.f + " " + c.x)).indexOf(" " + qf) >= 0; }
  // A row is one binary: the key phrase (a title in italics); tap shows it
  // in a clue. sub: a clue nested under its work. go: the work's own
  // answerline, linked.
  function rowHtml(c, qf, sub, go) {
    var detail = c.x ? "<p>" + highlight(c.x, c.k) + "</p>" : "";
    var n = bits(c.t), tiers = ["key", "sentence", "clause"].filter(function (t, i) { return c.t & (1 << i); }).join(", ");
    var dots = '<span class="dots" title="' + tiers + '">' + [0, 1, 2].map(function (i) { return '<i' + (i < n ? ' class="on"' : "") + "></i>"; }).join("") + "</span>";
    return '<tr class="clue-row' + (sub ? " sub" : "") + (detail ? " has-alt" : "") + '"' + (detail ? ' tabindex="0"' : "") + '>' +
      '<td class="clue-freq"><span class="freq-n">' + (c.q || "") + '</span><span class="freq-tools">' + placeBar(c.p) + "</span></td>" +
      '<td class="clue-body"><span class="bin is-key' + (c.w ? " title" : "") + (c.al ? " ent" : "") + (hitOf(c, qf) ? " hit" : "") + '">' + esc(c.f) + "</span>" +
      ((go = go || (c.al && c.al.a)) ? ' <a class="go" data-go="' + esc(go) + '" title="Open ' + esc(go) + '">›</a>' : "") +
      (detail ? '<div class="alt">' + detail + "</div>" : "") + "</td><td class=\"tier\">" + dots + "</td></tr>";
  }
  function moreRow(rest, gid, sub) {
    return rest > 0 ? '<tr' + (sub ? ' class="sub"' : "") + '><td></td><td colspan="2"><button type="button" class="all-rows" data-g="' + gid + '">+' + rest + "</button></td></tr>" : "";
  }
  // Items passing the filters, search hits first, cut to n unless expanded.
  // (A work passes, and hits, through its own row or any nested clue.)
  function workPass(g) { return (g.head && passCard(g.head)) || g.cards.some(passCard); }
  function workHit(g, qf) { return (g.head && hitOf(g.head, qf)) || g.cards.some(function (c) { return hitOf(c, qf); }); }
  function pick(items, qf, gid, n, works) {
    var pass = works ? workPass : passCard, hit = works ? workHit : hitOf;
    var order = items.filter(pass);
    if (qf) order.sort(function (x, y) { return (hit(x, qf) ? 0 : 1) - (hit(y, qf) ? 0 : 1); });
    var shown = S.allg[gid] ? order : order.slice(0, n);
    return { shown: shown, rest: order.length - shown.length };
  }
  function rowsHtml(cards, qf, gid) {
    var p = pick(cards, qf, gid, SHOW);
    return '<table class="clue-table"><tbody>' + p.shown.map(function (c) { return rowHtml(c, qf); }).join("") +
      moreRow(p.rest, gid) + "</tbody></table>";
  }
  // Works: each work's own row (its title binary, or just its name), the
  // clues that point to it nested beneath.
  function worksHtml(works, qf, gid) {
    var p = pick(works, qf, gid, SHOW, true);
    var rows = p.shown.map(function (g) {
      var head = g.head && passCard(g.head) ? rowHtml(g.head, qf, false, g.id ? g.name : "") :
        '<tr class="clue-row"><td class="clue-freq"></td><td class="clue-body"><a class="bin is-key title work-link" data-go="' + esc(g.name) + '">' +
        esc(g.name) + '</a></td><td class="tier"></td></tr>';
      var sub = pick(g.cards, qf, gid + ":" + g.key, SHOW_SUB);
      return head + sub.shown.map(function (c) { return rowHtml(c, qf, true); }).join("") + moreRow(sub.rest, gid + ":" + g.key, true);
    }).join("");
    return '<table class="clue-table"><tbody>' + rows + moreRow(p.rest, gid) + "</tbody></table>";
  }

  // Rows reorder / highlight only when the clue text or a key matched,
  // not when the search simply named the answerline.
  function rowQ(a) { return a._why === "text" || a._why === "key" ? fold(S.q) : ""; }
  // Work name as it appears in clue text: folded, leading article dropped.
  function workKey(name) { return fold(name).replace(/^(the|a|an) /, ""); }
  // One work under several spellings ("Brandenburg Concertos" / "Concerti").
  function workId(name) {
    var t = workKey(name).split(" "), w = t[t.length - 1];
    t[t.length - 1] = w.length > 4 && /i$/.test(w) ? w.slice(0, -1) + "o" : /os$/.test(w) ? w.slice(0, -1) : /[^s]s$/.test(w) ? w.slice(0, -1) : w;
    return t.join(" ");
  }
  var rank = function (x, y) { return y.q - x.q || bits(y.t) - bits(x.t); };
  function fillBody(el, a, qf) {
    var al = function (ids) { return (ids || []).map(function (id) { return BYID[id]; }).filter(Boolean); };
    var kids = al(a.ch).filter(function (k) { return !k.p; }), chars = al(a.ch).filter(function (k) { return k.p; });
    var need = [a.sh].concat(kids.map(function (k) { return k.sh; }));
    Promise.all(need.map(shard)).then(function () {
      var own = (SHARDS[a.sh][a.i] || []).slice().sort(rank);
      // Works: the answerline's child works (own decks of clues pointing to
      // them) and its own title binaries ("Space Oddity" -> Bowie), merged
      // by name.
      var works = [], byWid = {};
      var work = function (name, id) {
        name = name.replace(/^["“'‘]+|["”'’]+$/g, "");      // '"White Nights"' -> White Nights
        var wid = workId(name), g = byWid[wid];
        if (!g) { g = byWid[wid] = { key: wid, id: id, name: name, wk: workKey(name), head: null, cards: [] }; works.push(g); }
        if (id && !g.id) g.id = id;
        return g;
      };
      kids.forEach(function (k) {
        var g = work(k.a, k.i), seen = {};
        g.cards.forEach(function (c) { seen[c.f] = 1; });
        (SHARDS[k.sh][k.i] || []).forEach(function (c) { if (!seen[c.f]) g.cards.push(c); });
        g.chars = (g.chars || []).concat(al(k.ch).filter(function (x) { return x.p; }));
      });
      own.forEach(function (c) {
        if (!c.w) return;
        var g = work(c.f, null);
        if (!g.head || c.q > g.head.q) g.head = c;
      });
      // A clue goes under the work its evidence points into, else the work
      // it names, else the one work its example names (if exactly one),
      // else straight to the answerline.
      var clues = [];
      var names = function (t, g) { return g.wk.length >= 4 && t.indexOf(" " + g.wk + " ") >= 0; };
      own.forEach(function (c) {
        if (c.w) return;
        if (works.some(function (g) { return workKey(c.f) === g.wk; })) return;   // the work's own row shows it
        var fk = " " + fold(c.f) + " ", xk = " " + fold(c.x) + " ";
        // the work the key's own evidence points into (keys.py "under")
        var g = c.u ? byWid[workId(c.u.replace(/^["“'‘]+|["”'’]+$/g, ""))] : null;
        g = g || works.find(function (g) { return names(fk, g); });
        if (!g) {
          var hits = works.filter(function (g) { return names(xk, g); });
          if (hits.length === 1) g = hits[0];
        }
        (g ? g.cards : clues).push(c);
      });
      // Characters (answerlines of their own) mark the binary that names
      // them (Raskolnikov in "Rodion Romanovich Raskolnikov"), or get a row
      // of their own: under their work, or among the clues.
      var entities = function (lists, cs, home) {
        cs.forEach(function (ch) {
          var nm = " " + ch.af + " ", c = null;
          lists.some(function (l) {
            return (c = l.find(function (c) { var f = fold(c.f); return !c.al && f.length >= 4 && nm.indexOf(" " + f + " ") >= 0; }));
          });
          if (c) c.al = ch;
          else home.push({ f: ch.a, q: 0, t: 0, p: -1, k: [], x: "", al: ch });
        });
      };
      works.forEach(function (g) { entities([g.cards], g.chars || [], g.cards); });
      entities([clues].concat(works.map(function (g) { return g.cards; })), chars, clues);
      // Same phrase twice in one deck (creator and work both own it): once.
      var seenF = {}, once = function (c) { var f = fold(c.f); if (seenF[f]) return false; seenF[f] = 1; return true; };
      works.forEach(function (g) { if (g.head) once(g.head); });
      works.forEach(function (g) { g.cards = g.cards.filter(once).sort(rank); });
      clues = clues.filter(once);
      var weight = function (g) { return (g.head ? g.head.q : 0) + g.cards.filter(passCard).reduce(function (s, c) { return s + c.q; }, 0); };
      works.sort(function (x, y) { return weight(y) - weight(x); });
      var nWorks = works.filter(workPass).length, nClues = clues.filter(passCard).length;
      var html = "";
      if (nWorks) html += '<div class="grp"><div class="grp-h"><span>Works</span><span class="grp-n">' + nWorks + "</span></div>" +
        worksHtml(works, qf, a.i + ":works") + "</div>";
      if (nClues) html += '<div class="grp">' + (nWorks ? '<div class="grp-h"><span>Clues</span><span class="grp-n">' + nClues + "</span></div>" : "") +
        rowsHtml(clues, qf, a.i + ":clues") + "</div>";
      el.innerHTML = html;
    });
  }
  function render() {
    var res = results(), qf = fold(S.q), list = $("list");
    setStatus(res);
    if (!res.length) { list.innerHTML = '<p class="empty">No matches.</p>'; $("more").hidden = true; return; }
    var html = res.slice(0, S.limit).map(function (r) {
      var a = r.a, open = S.open[a.i] || r.why === "text" || res.length <= 3;
      var par = a.par.length ? ' <span class="al-par">→ <a data-go="' + esc(a.par[0]) + '">' + esc(a.par[0]) + "</a></span>" : "";
      return '<div class="al" data-i="' + a.i + '"><button type="button" class="al-head" aria-expanded="' + (open ? "true" : "false") + '">' +
        '<span class="al-name">' + esc(a.a) + "</span>" + par + '<span class="al-cat">' + esc(a.c) + (a.s && a.s !== a.c ? " · " + esc(a.s) : "") + (a.l ? " · " + esc(a.l) : "") + "</span>" +
        '<span class="al-n"><b>' + r.n + "</b> card" + (r.n === 1 ? "" : "s") + "</span></button>" +
        '<div class="al-body"' + (open ? "" : " hidden") + '><div class="loading">Loading…</div></div></div>';
    }).join("");
    list.innerHTML = html;
    list.querySelectorAll(".al").forEach(function (el) {
      var body = el.querySelector(".al-body");
      if (!body.hidden) fillBody(body, BYID[el.dataset.i], rowQ(BYID[el.dataset.i]));
    });
    $("more").hidden = res.length <= S.limit;
  }
  var BYID = {};

  $("list").addEventListener("click", function (ev) {
    var go = ev.target.closest("[data-go]");
    if (go) { ev.stopPropagation(); $("q").value = go.dataset.go; S.q = go.dataset.go; S.limit = PAGE; render(); return; }
    var allBtn = ev.target.closest(".all-rows");
    if (allBtn) { S.allg[allBtn.dataset.g] = 1; var al = allBtn.closest(".al"); fillBody(al.querySelector(".al-body"), BYID[al.dataset.i], rowQ(BYID[al.dataset.i])); return; }
    var row = ev.target.closest(".clue-row.has-alt");
    if (row) { row.classList.toggle("open"); return; }
    var head = ev.target.closest(".al-head");
    if (!head) return;
    var el = head.parentNode, body = el.querySelector(".al-body"), a = BYID[el.dataset.i];
    var opening = body.hidden;
    body.hidden = !opening; head.setAttribute("aria-expanded", String(opening));
    if (opening) { S.open[a.i] = 1; fillBody(body, a, rowQ(a)); } else delete S.open[a.i];
  });
  $("list").addEventListener("keydown", function (ev) {
    if ((ev.key === "Enter" || ev.key === " ") && ev.target.classList.contains("has-alt")) { ev.preventDefault(); ev.target.classList.toggle("open"); }
  });
  function seg(id, key, cast) {
    $(id).addEventListener("click", function (ev) {
      var b = ev.target.closest("button"); if (!b) return;
      S[key] = cast ? cast(b.dataset.v) : b.dataset.v; S.limit = PAGE;
      $(id).querySelectorAll("button").forEach(function (x) { x.setAttribute("aria-pressed", String(x === b)); });
      render();
    });
  }
  seg("f-type", "type", Number); seg("f-conf", "conf"); seg("f-sort", "sort");
  $("more").addEventListener("click", function () { S.limit += PAGE; render(); });
  var tq = null;
  $("q").addEventListener("input", function () {
    clearTimeout(tq); var v = this.value;
    tq = setTimeout(function () {
      S.q = v.trim(); S.limit = PAGE; render();
      if (fold(S.q).length >= 3) loadAll().then(function () { if (S.q) render(); });
    }, 200);
  });

  // Category panel: qbreader's three lists. Subcategories and alternates
  // show for the chosen categories (all of them when none is chosen).
  // Categories: qbreader's modal. Subcategories and alternates appear for
  // the picked categories, already picked; click one to drop it.
  var KCLASS = { Literature: "k-lit", History: "k-hist", Science: "k-sci", "Fine Arts": "k-arts" };
  function cb(kind, v, c) {
    return '<button type="button" class="cb ' + (KCLASS[c] || "k-other") + '" data-k="' + kind + '" data-v="' + esc(v) +
      '" aria-pressed="' + (S[kind][v] ? "true" : "false") + '">' + esc(v) + "</button>";
  }
  function fillCats() {
    var on = TAX.cats.filter(function (c) { return S.cats[c]; }), subs = [], alts = [];
    $("f-cat").innerHTML = TAX.cats.map(function (c) { return cb("cats", c, c); }).join("");
    on.forEach(function (c) {
      (TAX.subs[c] || []).forEach(function (s) { if (s !== c) subs.push(cb("subs", s, c)); });
      (TAX.alts[c] || []).forEach(function (l) { alts.push(cb("alts", l, c)); });
    });
    $("f-sub").innerHTML = subs.join("") || '<p class="hint">You must select categories before you can select subcategories.</p>';
    $("f-alt").innerHTML = alts.join("");
    // Summary: "Literature (no Poetry) · History"
    var parts = on.map(function (c) {
      var off = (TAX.subs[c] || []).filter(function (s) { return s !== c && !S.subs[s]; })
        .concat((TAX.alts[c] || []).filter(function (l) { return !S.alts[l]; }));
      return c + (off.length ? " (no " + off.join(", ") + ")" : "");
    });
    $("cat-sum").textContent = parts.length ? parts.join(" · ") : "all";
    $("cat-clear").hidden = !parts.length;
  }
  function setCat(c, on) {
    var put = function (set, v) { if (on) set[v] = 1; else delete set[v]; };
    put(S.cats, c);
    (TAX.subs[c] || []).forEach(function (s) { put(S.subs, s); });
    (TAX.alts[c] || []).forEach(function (l) { put(S.alts, l); });
  }
  function catsChanged() { S.limit = PAGE; fillCats(); render(); }
  function openModal(open) { $("cat-modal").hidden = !open; (open ? $("cat-close") : $("cat-btn")).focus(); }
  $("cat-btn").addEventListener("click", function () { openModal(true); });
  $("cat-close").addEventListener("click", function () { openModal(false); });
  $("cat-modal").addEventListener("click", function (ev) {
    if (ev.target === this) { openModal(false); return; }
    var b = ev.target.closest(".cb"); if (!b) return;
    var k = b.dataset.k, v = b.dataset.v;
    if (k === "cats") setCat(v, !S.cats[v]);
    else if (S[k][v]) delete S[k][v]; else S[k][v] = 1;
    catsChanged();
  });
  $("toggle-all").addEventListener("click", function () {
    var all = TAX.cats.every(function (c) { return S.cats[c]; });
    TAX.cats.forEach(function (c) { setCat(c, !all); });
    catsChanged();
  });
  document.addEventListener("keydown", function (ev) { if (ev.key === "Escape" && !$("cat-modal").hidden) openModal(false); });
  $("cat-clear").addEventListener("click", function () { S.cats = {}; S.subs = {}; S.alts = {}; catsChanged(); });

  // Difficulty: qbreader's levels 0-10, any number of them.
  var LEVELS = ["pop culture", "middle school", "easy high school", "regular high school", "hard high school", "national high school",
                "easy college", "medium college", "regular college", "hard college", "open"];
  $("f-diff").innerHTML = LEVELS.map(function (t, i) {
    return '<button type="button" data-v="' + i + '" aria-pressed="false" title="' + t + '">' + i + "</button>";
  }).join("");
  $("f-diff").addEventListener("click", function (ev) {
    var b = ev.target.closest("button"); if (!b) return;
    S.diffs ^= 1 << Number(b.dataset.v);
    b.setAttribute("aria-pressed", String(!!(S.diffs & (1 << Number(b.dataset.v)))));
    S.limit = PAGE; render();
  });
  ["y-min", "y-max"].forEach(function (id) {
    $(id).addEventListener("change", function () {
      var v = parseInt(this.value, 10);
      S[id === "y-min" ? "ymin" : "ymax"] = isFinite(v) ? v : 0;
      setYears(); S.limit = PAGE; render();
    });
  });

  fetch(DATA + "index.json").then(function (r) { return r.json(); }).then(function (d) {
    NSH = d.shards; IDX = d.answerlines; TAX = d.tax; Y0 = d.year0;
    TAX.cats.forEach(function (c) {
      (TAX.subs[c] || []).forEach(function (s) { SUBCAT[s] = c; });
      (TAX.alts[c] || []).forEach(function (l) { ALTCAT[l] = c; });
    });
    var ymax = Y0;
    IDX.forEach(function (a) {
      a.af = fold(a.a); a.kf = fold(a.kp); BYID[a.i] = a;
      a.y.forEach(function (m) { while (m >>> (ymax - Y0 + 1)) ymax++; });
    });
    $("y-min").placeholder = Y0; $("y-max").placeholder = ymax;
    $("y-min").min = $("y-max").min = Y0; $("y-min").max = $("y-max").max = ymax;
    fillCats(); render();
  }).catch(function () { $("status").textContent = "Index failed to load."; });
})();
</script>
"""


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--standalone", action="store_true")
    ap.add_argument("--site", action="store_true", help="also write the site page (repo root binaries.html)")
    ap.add_argument("--upload", action="store_true", help="upload the data to R2 (implies --site)")
    a = ap.parse_args()
    build(BASE_OUT / "browse", a.standalone, a.site or a.upload)
    if a.upload and not upload(BASE_OUT / "browse" / "data"):
        raise SystemExit(1)
