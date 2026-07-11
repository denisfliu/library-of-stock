"""
validate.py — Post-build health check for the stock knowledge pipeline.

Scans all analysis JSONs and rendered HTML files and prints a report of
any issues that would require manual intervention.

Usage:
    python lib/validate.py           # full report
    python lib/validate.py --strict  # exit with code 1 if any issues found
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from lib.common import load_cards, load_corpus
from lib.questions_store import load_store


def run_checks(analyses=None, parse_errors=None, store=None) -> list[str]:
    if analyses is None:
        analyses, parse_errors = load_corpus()

    issues = [f"[BROKEN JSON] {p.parent.name}/analysis.json: {msg}"
              for p, msg in (parse_errors or [])]

    for slug, f, analysis in analyses:
        topic = analysis.get("topic", slug)

        # 1. Missing summary
        if not analysis.get("summary", "").strip():
            issues.append(f"[EMPTY SUMMARY] {topic}")

        # 2. No cards
        cards = load_cards(f.parent.name)
        if not cards:
            issues.append(f"[NO CARDS] {topic}")

        # 3. Works with images but image cards missing
        # (only flag if render_cards.py hasn't synthesized them — i.e., no type=image card at all
        # and at least one work has an image url)
        has_image_work = any(
            isinstance(w.get("image"), dict) and w["image"].get("url")
            for w in analysis.get("works", [])
        )
        # After Tier 1, render_cards.py synthesizes these at render time — not a JSON-level issue.
        # Only flag if the cards.html is also missing (meaning render failed entirely).
        cards_html = f.parent / "cards.html"
        if has_image_work and not cards_html.exists():
            issues.append(f"[MISSING CARDS PAGE] {topic}")

        # 4. Missing questions page
        questions_html = f.parent / "questions.html"
        if not questions_html.exists():
            issues.append(f"[MISSING QUESTIONS PAGE] {topic}")

        # 5. Missing stock page
        stock_html = f.parent / "stock.html"
        if not stock_html.exists():
            issues.append(f"[MISSING STOCK PAGE] {topic}")

        # 6. Fine Arts / Other Fine Arts topic with empty genre
        # Skip topics that are legitimately cross-genre or uncategorised OFA
        _OFA_NO_GENRE_OK = {"Linda Nochlin", "Étienne Maurice Falconet"}
        if (analysis.get("category") == "Fine Arts"
                and analysis.get("subcategory") == "Other Fine Arts"
                and not analysis.get("genre", "").strip()
                and topic not in _OFA_NO_GENRE_OK):
            issues.append(f"[EMPTY GENRE] {topic} (Fine Arts / Other Fine Arts)")

        # 7. Question refs: the topic should have a questions_ref.json and
        # every referenced id must resolve in the question store.
        ref_path = f.parent / "questions_ref.json"
        if not ref_path.exists():
            issues.append(f"[NO QUESTIONS REF] {topic}")
        else:
            if store is None:
                store = load_store()
            try:
                refs = json.load(open(ref_path, encoding='utf-8'))
            except json.JSONDecodeError as e:
                issues.append(f"[BROKEN JSON] {slug}/questions_ref.json: {e}")
                refs = []
            dangling = sum(1 for entry in refs
                           for kind in ("tossups", "bonuses")
                           for qid in entry.get(kind, []) if qid not in store)
            if dangling:
                issues.append(f"[DANGLING QUESTION REF] {topic}: "
                              f"{dangling} ids not in output/_questions/")

        # 8. Score clues flagged for ABC notation review
        for clue in analysis.get("score_clues", []):
            if clue.get("needs_review") and clue.get("abc"):
                work = clue.get("work", "?")
                issues.append(f"[NEEDS_ABC_REVIEW] {topic}: '{work}'")

    return issues


def main(analyses=None, parse_errors=None, store=None):
    strict = "--strict" in sys.argv
    issues = run_checks(analyses, parse_errors, store=store)

    if not issues:
        print("Validation OK — no issues found.")
        return

    by_type: dict[str, list[str]] = {}
    for issue in issues:
        label = issue.split("]")[0].lstrip("[")
        by_type.setdefault(label, []).append(issue)

    print(f"\nVALIDATION REPORT — {len(issues)} issue(s) found:")
    for label, items in sorted(by_type.items()):
        print(f"\n  {label} ({len(items)})")
        for item in items:
            # Print just the topic part after the label
            print(f"    - {item.split('] ', 1)[-1]}")

    if strict:
        sys.exit(1)


if __name__ == "__main__":
    main()
