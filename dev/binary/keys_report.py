"""Render Tier A key phrases (keys.py output) as a review page.

Per chosen creator: the keys that point straight at them, then each of
their works with the keys that point at the work (phrase -> work ->
creator), then ambiguous phrases where they are one of several owners.
Plus scope-wide totals and a random sample for spot-checking precision.

Usage: python dev/binary/keys_report.py --scope music "bela bartok" "sofia gubaidulina" ...
"""
import argparse
import html
import json
import random
from collections import Counter, defaultdict

from common import OUT
from lib.render.theme import theme_vars_css


def fmt_key(k, e):
    ex = "".join(f"<li>{e(x)}</li>" for x in k["examples"])
    tip = f'{k["support"]} questions where it is the answer, {k["conflicts"]} where a rival is'
    out = (f'<span class="out">{", ".join(e(o) for o, _ in k["outside"])}</span>'
           if k["conflicts"] and k["outside"] else "")
    desc = '<span class="desc" title="lowercase descriptive phrase">desc</span>' if k.get("source") == "lowercase" else ""
    return (f'<li class="key{" lower" if desc else ""}"><span class="ph">{e(k["phrase"])}</span>{desc}'
            f'<span class="ev" title="{tip}">{k["support"]}<i>/</i>{k["conflicts"]}</span>{out}'
            f'<details><summary>examples</summary><ul>{ex}</ul></details></li>')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scope", default="music")
    ap.add_argument("creators", nargs="+")
    a = ap.parse_args()
    d = json.load(open(OUT / f"keys_{a.scope}.json", encoding="utf-8"))
    K, N = d["keys"], d["near"]
    e = html.escape
    by_owner = defaultdict(list)
    for k in K:
        by_owner[k["owner"]].append(k)
    sections = []
    for c in a.creators:
        direct = sorted(by_owner.get(c, []), key=lambda k: -k["support"])
        works = defaultdict(list)
        for k in K:
            if c in k.get("owner_parent", []):
                works[k["owner"]].append(k)
        work_html = ""
        for w, ks in sorted(works.items(), key=lambda x: -sum(k["support"] for k in x[1])):
            ks.sort(key=lambda k: -k["support"])
            work_html += (f'<div class="work"><h4>{e(w)} <span class="arrow">→ {e(c)}</span></h4>'
                          f'<ul class="keys">{"".join(fmt_key(k, e) for k in ks)}</ul></div>')
        amb = [x for x in N if any(o == c for o, _ in x["competing"])]
        amb.sort(key=lambda x: -x["questions"])
        amb_html = "".join(
            f'<li><span class="ph">{e(x["phrase"])}</span> <span class="muted">{x["questions"]}q · '
            + ", ".join(f'{e(o)} {s:.0%}' for o, s in x["competing"][:4]) + "</span></li>"
            for x in amb[:12])
        n_keys = len(direct) + sum(len(v) for v in works.values())
        sections.append(
            f'<section id="{e(c.replace(" ", "-"))}"><h2>{e(c.title())}</h2>'
            f'<p class="muted">{n_keys} keys: {len(direct)} point straight here, '
            f'{sum(len(v) for v in works.values())} point at one of {len(works)} works</p>'
            f'<ul class="keys">{"".join(fmt_key(k, e) for k in direct)}</ul>{work_html}'
            + (f'<h4 class="amb">Not binary: shared with another owner</h4><ul class="ambl">{amb_html}</ul>'
               if amb_html else "") + "</section>")
    random.seed(7)
    sample = random.sample(K, min(40, len(K)))
    sample_html = "".join(
        f'<li><span class="ph">{e(k["phrase"])}</span> → <b>{e(k["owner"])}</b>'
        + (f' → {e(k["owner_parent"][0])}' if k.get("owner_parent") else "")
        + f' <span class="ev">{k["support"]}<i>/</i>{k["conflicts"]}</span>'
        + (' <span class="desc">desc</span>' if k.get("source") == "lowercase" else "") + '</li>' for k in sample)
    kinds = Counter(k["kind"] or "other" for k in K)
    n_desc = sum(1 for k in K if k.get("source") == "lowercase")
    nav = " · ".join(f'<a href="#{e(c.replace(" ", "-"))}">{e(c.title())}</a>' for c in a.creators)
    page = f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Key Phrases: {e(a.scope.title())}</title>
<style>
{theme_vars_css()}
body {{ background: var(--c-bg); color: var(--c-text); font: 15px/1.5 system-ui, -apple-system, "Segoe UI", sans-serif;
       max-width: 980px; margin: 0 auto; padding-block: 1.5rem 4rem; padding-inline: 16px; }}
h1 {{ font-size: 1.6rem; margin: 0 0 .3rem; text-wrap: balance; }}
h2 {{ font-size: 1.2rem; margin: 2.2rem 0 .3rem; padding-bottom: .3rem; border-bottom: 1px solid var(--c-border); }}
h4 {{ font-size: .95rem; margin: 1rem 0 .3rem; }}
.muted, .arrow {{ color: var(--c-muted); font-weight: 400; }}
.lede {{ max-width: 70ch; }}
nav {{ font-size: .9rem; margin: .8rem 0 0; line-height: 1.9; }}
a {{ color: var(--c-link); }}
.keys {{ list-style: none; padding: 0; margin: .4rem 0; display: flex; flex-wrap: wrap; gap: .35rem; }}
.key {{ background: var(--c-raised2); border: 1px solid var(--c-border); border-radius: 8px; padding: .2rem .55rem;
        display: inline-flex; flex-wrap: wrap; align-items: baseline; gap: .4rem; max-width: 100%; }}
.ph {{ font-weight: 600; overflow-wrap: anywhere; }}
.ev {{ font: 12px ui-monospace, Consolas, monospace; color: var(--c-good); }}
.ev i {{ color: var(--c-faint); font-style: normal; }}
.out {{ font-size: 12px; color: var(--c-warn); }}
.desc {{ font-size: 10.5px; text-transform: uppercase; letter-spacing: .05em; color: var(--c-link);
         border: 1px solid var(--c-selline); border-radius: 99px; padding: 0 .35rem; }}
.key.lower .ph {{ font-weight: 500; font-style: italic; }}
.key details {{ flex-basis: 100%; font-size: 12.5px; color: var(--c-muted); }}
.key details summary {{ cursor: pointer; }}
.key details ul {{ margin: .2rem 0 .3rem 1rem; padding: 0; }}
.work {{ border-left: 2px solid var(--c-border); padding-left: .8rem; margin: .6rem 0; }}
.amb {{ color: var(--c-warn); }}
.ambl, .sample {{ margin: .3rem 0; padding-left: 1.1rem; font-size: .92rem; }}
.stats {{ display: flex; flex-wrap: wrap; gap: .4rem 1.2rem; font-size: .9rem; font-variant-numeric: tabular-nums; }}
</style></head><body>
<h1>Key phrases: {e(a.scope)}</h1>
<p class="lede muted">A phrase is a <b>key</b> for an answer when, in every question where it appears and
the hidden answer is the same kind of thing, that answer is this one (or one of its works). Questions
that name the answer outright are context, not evidence; questions about a different kind of thing
(a country, an instrument) can't compete. <span class="ev">support<i>/</i>conflicts</span> counts
those questions; keys need 2+ support and ≥ 80% share. Candidates come from {e(a.scope)} questions;
evidence comes from the whole corpus.</p>
<div class="stats"><span><b>{len(K):,}</b> keys</span><span><b>{n_desc:,}</b> of them lowercase descriptions <span class="desc">desc</span></span>{"".join(f"<span><b>{v:,}</b> → {e(k)}</span>" for k, v in kinds.most_common())}<span><b>{len(N):,}</b> ambiguous phrases</span></div>
<nav>{nav} · <a href="#sample">random sample</a></nav>
{"".join(sections)}
<section id="sample"><h2>Random sample (all music)</h2><ul class="sample">{sample_html}</ul></section>
</body></html>"""
    out = OUT / f"keys_{a.scope}.html"
    out.write_text(page.replace("�", "&#xFFFD;"), encoding="utf-8")   # broken source chars
    print(f"-> {out}")


if __name__ == "__main__":
    main()
