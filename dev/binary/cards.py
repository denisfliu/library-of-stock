"""One card view per topic: key phrases + sentence binaries + clause binaries.

For each of the topic's answerlines (topic.py's discovery):
  1. clause-tier binaries are the base cards (finest unit: one fact);
  2. a sentence-tier binary that shares a sentence with a clause card
     confirms it (tier "sentence" added); one that overlaps no clause
     card becomes its own card;
  3. a Tier A key phrase owned by the answerline (or by one of its works)
     attaches to the card whose sentences contain it, becoming its short
     form; keys that match no card become key-only cards;
  4. cards rank by how many tiers agree, then by questions.

Writes out/cards_{slug}.json and out/cards_{slug}.html.

Usage: python dev/binary/cards.py bela_bartok [--scope music]
       (slug of an existing topic.py run in BOTH out/ and out/clauses_{scope}/)
"""
import argparse
import html
import json
import re
from collections import defaultdict

from common import BASE_OUT, fold, load
from lib.render.theme import theme_vars_css

GOOD = ("binary", "binary-key")
KEY_FIT = 0.5      # a key joins a card only if its phrase is in the front or half its sentences


def display_answer(raw):
    """Main answer with bracketed / parenthesised material removed (not
    truncated): "Bela (Viktor Janos) Bartok [accept ...]" -> "Bela Bartok"."""
    a = re.sub(r"<[^>]*>", " ", raw or "")
    a = re.sub(r"[\[\(][^\]\)]*[\]\)]", " ", a)
    a = re.split(r"[\[\(]", a)[0]
    return re.sub(r"\s+", " ", a).strip() or raw


def build(slug, scope):
    sent = json.load(open(BASE_OUT / f"topic_{slug}.json", encoding="utf-8"))
    clause = json.load(open(BASE_OUT / f"clauses_{scope}" / f"topic_{slug}.json", encoding="utf-8"))
    keys = json.load(open(BASE_OUT / f"keys_{scope}.json", encoding="utf-8"))["keys"]
    U = load("units.pkl")
    L = load("labels.pkl")
    key_label = {k: i for i, k in enumerate(L["keys"])}
    s_by = {a["answerline"]: a for a in sent}
    c_by = {a["answerline"]: a for a in clause}
    order = [a["answerline"] for a in sent] + [a["answerline"] for a in clause
                                                 if a["answerline"] not in s_by]
    keys_by_owner = defaultdict(list)
    for k in keys:
        keys_by_owner[k["owner"]].append(k)
    out = []
    for al in order:
        s_facts = [f for f in s_by.get(al, {}).get("facts", []) if f["status"] in GOOD]
        c_facts = [f for f in c_by.get(al, {}).get("facts", []) if f["status"] in GOOD]
        cards = []
        for f in c_facts:
            cards.append(dict(front=f["rep"], tiers=["clause"], questions=max(f["questions"], f["support"]),
                              sentences=set(f["sentences"]), position=f["position"],
                              examples=f["examples"], keys=[]))
        for f in s_facts:
            hit = [c for c in cards if c["sentences"] & set(f["sentences"])]
            if hit:
                for c in hit:
                    if "sentence" not in c["tiers"]:
                        c["tiers"].append("sentence")
                    c["questions"] = max(c["questions"], f["questions"], f["support"])
            else:
                cards.append(dict(front=f["rep"], tiers=["sentence"],
                                  questions=max(f["questions"], f["support"]),
                                  sentences=set(f["sentences"]), position=f["position"],
                                  examples=f["examples"], keys=[]))
        sent_text = {}
        for c in cards:
            for sid in c["sentences"]:
                sent_text.setdefault(sid, f" {fold(U['text'][sid])} ")
        for k in keys_by_owner.get(al, []):
            pad = f" {k['phrase']} "

            def fit(c):
                # Share of the card's sentences containing the phrase; the
                # card's own front counts as a full fit.
                if pad in f" {fold(c['front'])} ":
                    return 1.0
                n = sum(1 for s in c["sentences"] if pad in sent_text[s])
                return n / max(len(c["sentences"]), 1)

            hit = [c for c in cards if fit(c) >= KEY_FIT]
            if hit:
                best = max(hit, key=lambda c: (fit(c), c["questions"]))
                best["keys"].append(k["phrase"])
                best.setdefault("kdiffs", set()).update(k.get("diffs", []))
                if "key" not in best["tiers"]:
                    best["tiers"].insert(0, "key")
                best["questions"] = max(best["questions"], k["support"])
            else:
                cards.append(dict(front=k["examples"][0] if k["examples"] else k["phrase"],
                                  tiers=["key"], questions=k["support"], sentences=set(),
                                  position=None, examples=k["examples"][1:], keys=[k["phrase"]],
                                  kdiffs=set(k.get("diffs", []))))
        lab = key_label.get(al)
        raw = None
        if lab is not None:
            for i, b in enumerate(L["unit_label"]):
                if b == lab:
                    raw = U["answer"][i]
                    break
        for c in cards:
            # qbreader set difficulty (1-10) of every question behind the card
            c["diffs"] = sorted({int(U["diff"][s]) for s in c["sentences"]} | c.pop("kdiffs", set()))
        cards.sort(key=lambda c: (-len(c["tiers"]), -c["questions"]))
        parent = sorted({p for k in keys_by_owner.get(al, []) for p in k.get("owner_parent", [])})
        out.append(dict(answerline=al, answer=display_answer(raw) if raw else al, parent=parent,
                        cards=[{**c, "sentences": sorted(c["sentences"])} for c in cards]))
    return out


def highlight(text, phrases, e):
    t = e(text)
    for p in sorted(phrases, key=len, reverse=True):
        words = [re.escape(w) for w in p.split()]
        pat = re.compile(r"\b" + r"[\W_]+".join(words) + r"\b", re.I)
        t = pat.sub(lambda m: f"<mark>{m.group(0)}</mark>", t, count=1)
    return t


def render(slug, title, data):
    e = html.escape
    tot = sum(len(a["cards"]) for a in data)
    multi = sum(1 for a in data for c in a["cards"] if len(c["tiers"]) > 1)
    secs = []
    for a in data:
        if not a["cards"]:
            continue
        items = []
        for c in a["cards"]:
            chips = "".join(f'<span class="tier t-{t}">{t}</span>' for t in c["tiers"])
            pos = "" if c["position"] is None else \
                f'<span class="pos" title="mean position in the tossup: 0 = lead-in, 1 = giveaway">' \
                f'<i style="left:{100 * c["position"]:.0f}%"></i></span>'
            ex = "".join(f"<li>{highlight(x, c['keys'], e)}</li>" for x in c["examples"][:3])
            ds = [d for d in c.get("diffs", []) if d > 0]
            drange = (f'<span class="dr" title="set difficulties it appeared at: {", ".join(map(str, ds))}">'
                      f'd{ds[0]}{"–" + str(ds[-1]) if ds[-1] != ds[0] else ""}</span>') if ds else ""
            items.append(
                f'<li class="card" data-maxd="{ds[-1] if ds else 0}"><div class="meta">{chips}'
                f'<span class="nq">{c["questions"]}q</span>{drange}{pos}</div>'
                f'<div class="front">{highlight(c["front"], c["keys"], e)}</div>'
                + (f'<div class="key">key: {", ".join(e(k) for k in c["keys"])}</div>' if c["keys"] else "")
                + (f'<details><summary>more phrasings</summary><ul>{ex}</ul></details>' if ex else "")
                + "</li>")
        par = f' <span class="par">→ {e(", ".join(a["parent"]))}</span>' if a["parent"] else ""
        secs.append(f'<section><h2><span class="ans">{e(a["answer"])}</span>{par}'
                    f'<span class="cnt"><b class="vis">{len(a["cards"])}</b> cards</span></h2><ul class="cards">{"".join(items)}</ul></section>')
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{e(title)} Cards</title>
<style>
{theme_vars_css()}
body {{ background: var(--c-bg); color: var(--c-text); font: 15px/1.5 system-ui, -apple-system, "Segoe UI", sans-serif;
       max-width: 900px; margin: 0 auto; padding-block: 1.5rem 4rem; padding-inline: 16px; }}
h1 {{ font-size: 1.6rem; margin: 0 0 .3rem; text-wrap: balance; }}
.lede {{ color: var(--c-muted); max-width: 70ch; }}
h2 {{ font-size: 1.1rem; margin: 2rem 0 .5rem; padding-bottom: .3rem; border-bottom: 1px solid var(--c-border);
     display: flex; flex-wrap: wrap; gap: .3rem .6rem; align-items: baseline; }}
.par, .cnt {{ font-weight: 400; font-size: .85rem; color: var(--c-muted); }}
.cnt {{ margin-left: auto; }}
.cards {{ list-style: none; padding: 0; margin: 0; display: grid; gap: .45rem; }}
.card {{ background: var(--c-raised2); border: 1px solid var(--c-border); border-radius: 10px; padding: .55rem .75rem; min-width: 0; }}
.meta {{ display: flex; flex-wrap: wrap; gap: .35rem; align-items: center; font-size: .72rem; margin-bottom: .25rem; }}
.tier {{ text-transform: uppercase; letter-spacing: .05em; font-weight: 600; border-radius: 99px; padding: 0 .45rem; }}
.t-key {{ color: var(--c-link); background: var(--c-selbg); }}
.t-sentence {{ color: var(--c-winfg); background: var(--c-winbg); }}
.t-clause {{ color: var(--c-accent); background: var(--c-hl); }}
.nq {{ color: var(--c-muted); font-variant-numeric: tabular-nums; }}
.pos {{ position: relative; display: inline-block; width: 60px; height: 4px; border-radius: 2px; background: var(--c-border); }}
.pos i {{ position: absolute; top: -3px; width: 2px; height: 10px; margin-left: -1px; background: var(--c-text); }}
.front {{ font-size: .98rem; overflow-wrap: anywhere; }}
mark {{ background: var(--c-selbg); color: var(--c-text); border-radius: 3px; padding: 0 .1rem; }}
.key {{ font-size: .8rem; color: var(--c-link); margin-top: .15rem; }}
.dr {{ color: var(--c-muted); font-variant-numeric: tabular-nums; }}
.filter {{ display: flex; flex-wrap: wrap; gap: .4rem; align-items: center; margin: 1rem 0 0; font-size: .9rem; }}
.filter button {{ font: inherit; font-size: .85rem; border: 1px solid var(--c-border); background: var(--c-bg);
                  color: var(--c-text); border-radius: 99px; padding: .15rem .7rem; cursor: pointer; }}
.filter button[aria-pressed="true"] {{ background: var(--c-selbg); border-color: var(--c-selline); }}
.filter button:focus-visible {{ outline: 2px solid var(--c-link); outline-offset: 2px; }}
section.empty {{ display: none; }}
details {{ font-size: .82rem; color: var(--c-muted); margin-top: .25rem; }}
details ul {{ margin: .3rem 0 0 1rem; padding: 0; }}
</style></head><body>
<h1>{e(title)}: cards</h1>
<p class="lede">{tot} cards, {multi} confirmed by more than one tier. Every card is a binary: the clue points to
this answer and to nothing else in the corpus. <span class="tier t-key">key</span> = a name or phrase that
identifies it; <span class="tier t-sentence">sentence</span> and <span class="tier t-clause">clause</span> =
the same fact found by the sentence- and clause-level tests. The bar shows how early the clue comes in a tossup;
<span class="dr">d6–9</span> is the range of set difficulties (qbreader 1–10) it has appeared at.</p>
<div class="filter" role="group" aria-label="Filter by difficulty"><span>Show cards that appear at difficulty</span>
<button type="button" data-min="0" aria-pressed="true">any</button><button type="button" data-min="7" aria-pressed="false">7+</button>
<button type="button" data-min="8" aria-pressed="false">8+</button><button type="button" data-min="9" aria-pressed="false">9+</button>
<span class="dr" id="shown"></span></div>
{"".join(secs)}
<script>
(function () {{
  var btns = document.querySelectorAll(".filter button");
  function apply(min) {{
    var total = 0;
    document.querySelectorAll("section").forEach(function (sec) {{
      var n = 0;
      sec.querySelectorAll(".card").forEach(function (c) {{
        var ok = Number(c.dataset.maxd) >= min;
        c.hidden = !ok; if (ok) n++;
      }});
      var v = sec.querySelector(".vis"); if (v) v.textContent = n;
      sec.classList.toggle("empty", n === 0); total += n;
    }});
    document.getElementById("shown").textContent = total + " shown";
    btns.forEach(function (b) {{ b.setAttribute("aria-pressed", String(Number(b.dataset.min) === min)); }});
  }}
  btns.forEach(function (b) {{ b.addEventListener("click", function () {{ apply(Number(b.dataset.min)); }}); }});
  apply(0);
}})();
</script>
</body></html>"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("slug")
    ap.add_argument("--scope", default="music")
    ap.add_argument("--title")
    a = ap.parse_args()
    data = build(a.slug, a.scope)
    json.dump(data, open(BASE_OUT / f"cards_{a.slug}.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    page = render(a.slug, a.title or a.slug.replace("_", " ").title(), data)
    # Some mirror text carries U+FFFD from broken source encodings; keep it visible but escaped.
    (BASE_OUT / f"cards_{a.slug}.html").write_text(page.replace("�", "&#xFFFD;"), encoding="utf-8")
    n = sum(len(x["cards"]) for x in data)
    from collections import Counter
    tiers = Counter(tuple(c["tiers"]) for x in data for c in x["cards"])
    print(f"{n} cards over {sum(1 for x in data if x['cards'])} answerlines; by tiers: {dict(tiers)}")
    print(f"-> out/cards_{a.slug}.html")


if __name__ == "__main__":
    main()
