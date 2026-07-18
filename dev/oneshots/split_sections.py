"""split_sections.py — Split lumped-movement overview sections into atomic ones.

Some overview sections group two or more clearly-distinct movements/schools
under one heading ("Baroque and Rococo", "Surrealism and Dada"). This tool
splits such a section into its constituent sections and re-buckets every
entry into the right one, so both the overview page and the reader's Group
facet expose the finer categories.

The split is a pure function of two inputs, so it stays re-derivable:
  * a snapshot of the pre-split authoring (``sections.pre_split.txt``,
    created on first run and never edited by hand afterward), and
  * a per-unit spec ``section_splits.json``:

    {
      "splits": [
        {
          "source": "Baroque and Rococo",
          "fallback": "Baroque",
          "targets": [
            {"name": "Baroque", "blurb": "...",
             "match": ["baroque", "tenebrism", "dutch golden age", ...],
             "eras": ["1500s", "1600s"]},
            {"name": "Rococo", "blurb": "...",
             "match": ["rococo", "fete galante", "watteau", ...],
             "eras": ["1700s"]}
          ]
        }
      ]
    }

Re-bucketing is mechanical. An overview entry (rich note) is scored by how
many of each target's ``match`` terms appear in "answer + note"; the best
target wins, ties/none fall back to ``fallback`` (reported for review). A
KB tail record (sparse) is scored over "display + movement + creator", then
by ``eras`` against its era bucket; no signal -> Unsectioned.

    python dev/oneshots/split_sections.py apply UNIT [--reapply]
        Rewrite sections.txt from the snapshot + spec; print ambiguities.
    python dev/oneshots/split_sections.py kb UNIT
        Re-bucket the unit's answerline-KB sections the same way.
    python dev/oneshots/split_sections.py check UNIT
        Dry-run apply: show the new section sizes + ambiguities only.
"""
import argparse
import json
import re
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from lib.common import CATEGORIES_DIR
from lib.sweep.answerline_kb import load_kb, save_kb


def _unit_dir(unit: str) -> Path:
    d = CATEGORIES_DIR / unit
    if not d.exists():
        raise SystemExit(f"no such unit dir: {d}")
    return d


def _load_spec(unit: str) -> dict:
    p = _unit_dir(unit) / "section_splits.json"
    if not p.exists():
        raise SystemExit(f"no split spec: {p}")
    spec = json.loads(p.read_text(encoding="utf-8"))
    by_source = {}
    for s in spec.get("splits", []):
        names = [t["name"] for t in s["targets"]]
        if s.get("fallback") and s["fallback"] not in names:
            raise SystemExit(
                f"{unit}: fallback {s['fallback']!r} is not a target of "
                f"{s['source']!r}")
        by_source[s["source"]] = s
    return spec, by_source


def _term_re(term: str) -> re.Pattern:
    # word-ish boundary so short terms ("dada") don't match inside words
    return re.compile(r"(?<![a-z0-9])" + re.escape(term.lower()) + r"(?![a-z0-9])")


def _score(text: str, target: dict) -> int:
    text = text.lower()
    return sum(1 for t in target.get("match", []) if _term_re(t).search(text))


def _bucket_by_text(text: str, split: dict):
    """Best target for a text blob, or (fallback, ambiguous=True) when no
    match term hits. Returns (target_name, matched_bool)."""
    if len(split["targets"]) == 1:      # single target = a pure rename
        return split["targets"][0]["name"], True
    scores = [(_score(text, t), t["name"]) for t in split["targets"]]
    best = max(scores, key=lambda x: x[0])
    if best[0] == 0:
        return split.get("fallback"), False
    # tie between top targets -> fallback if it's one of the tied, else best
    top = [name for sc, name in scores if sc == best[0]]
    if len(top) > 1:
        fb = split.get("fallback")
        return (fb if fb in top else best[1]), True
    return best[1], True


# ----------------------------- overview side -----------------------------

def _snapshot(unit: str) -> Path:
    d = _unit_dir(unit)
    snap = d / "sections.pre_split.txt"
    live = d / "sections.txt"
    if not snap.exists():
        if not live.exists():
            raise SystemExit(f"{live} missing")
        shutil.copyfile(live, snap)
        print(f"snapshot -> {snap.name}")
    return snap


def _parse_sections(text: str):
    """[(name, blurb, [entry_block, ...])]; an entry_block is the list of
    raw lines for one top-level entry (its own line plus any '- ' children)."""
    sections = []
    cur = None
    for raw in text.splitlines():
        line = raw.rstrip("\n")
        s = line.strip()
        if not s:
            continue
        if s.startswith("#"):
            cur = [s.lstrip("#").strip(), "", []]
            sections.append(cur)
        elif s.startswith(">"):
            if cur:
                cur[1] = s.lstrip(">").strip()
        elif cur is not None:
            if s.startswith("- ") and cur[2]:
                cur[2][-1].append(line)      # nested work -> previous entry
            else:
                cur[2].append([line])
    return sections


def _entry_text(block: list) -> str:
    """answer(s) + note across the entry's lines, for keyword matching."""
    parts = []
    for line in block:
        s = line.strip().lstrip("- ").strip()
        head, _, note = s.partition("|")
        head = head.split("->")[0]
        parts.append(head.replace("=", " "))
        parts.append(note)
    return " ".join(parts)


def _rebucket_overview(unit: str):
    _, by_source = _load_spec(unit)
    snap = _snapshot(unit)
    sections = _parse_sections(snap.read_text(encoding="utf-8"))

    out_lines, report, sizes = [], [], {}
    for name, blurb, blocks in sections:
        if name not in by_source:
            out_lines.append(f"# {name}")
            if blurb:
                out_lines.append(f"> {blurb}")
            for blk in blocks:
                out_lines.extend(blk)
            out_lines.append("")
            continue
        split = by_source[name]
        buckets = {t["name"]: [] for t in split["targets"]}
        for blk in blocks:
            tgt, matched = _bucket_by_text(_entry_text(blk), split)
            buckets.setdefault(tgt, []).append(blk)
            if not matched:
                report.append((name, tgt, blk[0].split("|")[0].strip()))
        for t in split["targets"]:
            blks = buckets.get(t["name"], [])
            sizes[t["name"]] = len(blks)
            out_lines.append(f"# {t['name']}")
            if t.get("blurb"):
                out_lines.append(f"> {t['blurb']}")
            for blk in blks:
                out_lines.extend(blk)
            out_lines.append("")
    return "\n".join(out_lines).rstrip() + "\n", report, sizes


def apply(unit: str, reapply: bool):
    live = _unit_dir(unit) / "sections.txt"
    snap = _unit_dir(unit) / "sections.pre_split.txt"
    if snap.exists() and not reapply:
        # already split once; regenerating from the snapshot is safe and
        # idempotent, but warn so hand edits to the snapshot are intentional
        print("note: re-generating sections.txt from snapshot "
              "(edit sections.pre_split.txt, not sections.txt)")
    new_text, report, sizes = _rebucket_overview(unit)
    live.write_text(new_text, encoding="utf-8")
    print(f"wrote {live} — new section sizes:")
    for name, n in sizes.items():
        print(f"  {n:4d}  {name}")
    _print_report(report)


def check(unit: str):
    _, report, sizes = _rebucket_overview(unit)
    print("new section sizes (dry run):")
    for name, n in sizes.items():
        print(f"  {n:4d}  {name}")
    _print_report(report)


def _print_report(report):
    if not report:
        print("no fallback/ambiguous entries — every entry matched a target")
        return
    print(f"\n{len(report)} entries fell back (no distinctive term) — review:")
    for src, tgt, ans in report:
        print(f"  [{src}] -> {tgt}: {ans}")


# -------------------------------- KB side --------------------------------

def kb(unit: str):
    _, by_source = _load_spec(unit)
    shard = load_kb(unit)
    changed = fell = 0
    for rec in shard.values():
        original = rec.get("_presplit_section") or rec.get("section")
        if original not in by_source:
            continue
        split = by_source[original]
        rec.setdefault("_presplit_section", original)
        blob = " ".join([rec.get("display") or "",
                         " ".join(rec.get("movement") or []),
                         rec.get("creator") or ""])
        tgt, matched = _bucket_by_text(blob, split)
        if not matched:
            # no movement/name term — try the era bucket, then fall back to
            # the split's default target (mirrors how the overview buckets
            # its own no-signal entries; keeps the tail sectioned rather
            # than dumping it into Unsectioned).
            era = rec.get("era")
            tgt = next((t["name"] for t in split["targets"]
                        if era and era in t.get("eras", [])), None)
            if tgt is None:
                tgt = split.get("fallback")
                fell += 1
        rec["section"] = tgt
        changed += 1
    save_kb(unit, shard)
    print(f"{unit}: re-bucketed {changed} KB sections "
          f"({fell} used the section's fallback for lack of signal)")


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("cmd", choices=["apply", "kb", "check"])
    ap.add_argument("unit")
    ap.add_argument("--reapply", action="store_true",
                    help="regenerate sections.txt from the snapshot again")
    args = ap.parse_args()
    if args.cmd == "apply":
        apply(args.unit, args.reapply)
    elif args.cmd == "check":
        check(args.unit)
    else:
        kb(args.unit)


if __name__ == "__main__":
    main()
