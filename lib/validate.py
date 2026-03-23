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

OUTPUT_DIR = Path("output")
CACHE_DIR = Path("cache")


def run_checks() -> list[str]:
    issues = []

    analysis_files = sorted(OUTPUT_DIR.glob("*/analysis.json"))

    for f in analysis_files:
        try:
            analysis = json.load(open(f))
        except json.JSONDecodeError as e:
            issues.append(f"[BROKEN JSON] {f.parent.name}/analysis.json: {e}")
            continue

        topic = analysis.get("topic", f.parent.name)
        topic_key = f.parent.name

        # 1. Missing summary
        if not analysis.get("summary", "").strip():
            issues.append(f"[EMPTY SUMMARY] {topic}")

        # 2. No cards
        cards = analysis.get("cards", [])
        if not cards:
            issues.append(f"[NO CARDS] {topic}")

        # 3. Works with images but image cards missing
        # (only flag if render_cards.py hasn't synthesized them — i.e., no type=image card at all
        # and at least one work has an image url)
        has_image_work = any(
            isinstance(w.get("image"), dict) and w["image"].get("url")
            for w in analysis.get("works", [])
        )
        has_image_card = any(c.get("type") == "image" for c in cards)
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

        # 7. Stale recorded cache_file (file no longer exists in topic dir or cache/)
        recorded_cache = analysis.get("cache_file")
        if recorded_cache:
            topic_cache = f.parent / recorded_cache
            fallback_cache = CACHE_DIR / recorded_cache
            if not topic_cache.exists() and not fallback_cache.exists():
                issues.append(f"[STALE CACHE_FILE] {topic}: '{recorded_cache}' not found")

        # 8. Score clues flagged for ABC notation review
        for clue in analysis.get("score_clues", []):
            if clue.get("needs_review") and clue.get("abc"):
                work = clue.get("work", "?")
                issues.append(f"[NEEDS_ABC_REVIEW] {topic}: '{work}'")

    return issues


def main():
    strict = "--strict" in sys.argv
    issues = run_checks()

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
