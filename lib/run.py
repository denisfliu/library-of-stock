"""
run.py — Runner script for the stock knowledge pipeline.

Usage:
    python run.py <topic> [difficulties] [min_year] [category]

Examples:
    python run.py "Smetana" "7,8,9,10"
    python run.py "Beethoven" "7,8,9,10" 2015
    python run.py "The Rite of Spring"
    python run.py "Indiana" "5,6,7,8,9,10" 2012 "Literature"
"""

import json
import os
import sys
from pathlib import Path

# Ensure project root is on sys.path so imports work from any cwd
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from lib.fetch import fetch_topic
from lib.parse import parse_answer_clues


def format_clues_for_analysis(parsed: dict) -> str:
    """
    Format parsed clues into a readable text block for LLM analysis.

    Groups clues by source question to preserve context, and includes
    metadata tags.
    """
    lines = []
    query = parsed['query_string']
    stats = parsed['stats']

    lines.append(f"=== STOCK CLUES: {query} ===")
    lines.append(f"Tossup questions: {stats['tossup_questions']} found, "
                 f"{stats['tossup_clue_sentences']} clue sentences extracted")
    lines.append(f"Bonus questions: {stats['bonus_questions']} found, "
                 f"{stats['bonus_clue_parts']} bonus parts extracted")
    lines.append("")

    # Group tossup clues by source question
    lines.append("--- TOSSUP ANSWERLINE CLUES ---")
    lines.append("")

    tossup_groups = {}
    for clue in parsed['tossup_clues']:
        qid = clue['source']['id']
        if qid not in tossup_groups:
            tossup_groups[qid] = {
                'source': clue['source'],
                'clues': [],
            }
        tossup_groups[qid]['clues'].append(clue)

    for i, (qid, group) in enumerate(tossup_groups.items(), 1):
        src = group['source']
        lines.append(f"[T{i}] {src['set']} ({src['year']}) | "
                     f"Diff: {src['difficulty']} | {src['category']}")
        lines.append(f"     Answer: {src['answer']}")
        for clue in group['clues']:
            tags = []
            if clue['in_power']:
                tags.append("PWR")
            if clue['is_giveaway']:
                tags.append("GIVE")
            tag_str = f" [{','.join(tags)}]" if tags else ""
            lines.append(f"  - {clue['text']}{tag_str}")
        lines.append("")

    # Group bonus clues by source question
    lines.append("--- BONUS ANSWERLINE CLUES ---")
    lines.append("")

    bonus_groups = {}
    for clue in parsed['bonus_clues']:
        qid = clue['source']['id']
        if qid not in bonus_groups:
            bonus_groups[qid] = {
                'source': clue['source'],
                'leadin': clue.get('leadin', ''),
                'parts': [],
            }
        bonus_groups[qid]['parts'].append(clue)

    for i, (qid, group) in enumerate(bonus_groups.items(), 1):
        src = group['source']
        lines.append(f"[B{i}] {src['set']} ({src['year']}) | "
                     f"Diff: {src['difficulty']} | {src['category']}")
        lines.append(f"     Leadin: {group['leadin']}")
        for part in group['parts']:
            lines.append(f"  Part {part['part_index']+1} "
                         f"(ans: {part['part_answer']}):")
            lines.append(f"    {part['text']}")
        lines.append("")

    return "\n".join(lines)


def main():
    if len(sys.argv) < 2:
        print("Usage: python run.py <topic> [difficulties] [min_year] [category]")
        print('Example: python run.py "Smetana" "7,8,9,10"')
        print('Example: python run.py "Indiana" "7,8,9,10" 2012 "Literature"')
        sys.exit(1)

    topic = sys.argv[1]
    diffs = None
    min_year = 2012
    categories = None

    if len(sys.argv) > 2:
        diffs = [int(d) for d in sys.argv[2].split(",")]
    if len(sys.argv) > 3:
        min_year = int(sys.argv[3])
    if len(sys.argv) > 4:
        categories = [c.strip() for c in sys.argv[4].split(",")]

    # Fetch and parse
    data = fetch_topic(topic, difficulties=diffs, categories=categories,
                       min_year=min_year)
    parsed = parse_answer_clues(data)

    # Format for analysis
    output = format_clues_for_analysis(parsed)

    # Save to output file for easy reading
    out_dir = Path("output")
    out_dir.mkdir(exist_ok=True)
    safe_name = topic.strip().lower().replace(" ", "_")
    out_path = out_dir / f"{safe_name}_clues.txt"
    with open(out_path, "w") as f:
        f.write(output)

    print(f"\nClue output saved to {out_path}")
    print(f"({len(output)} characters, ~{len(output)//4} tokens)")

    # Also print to stdout
    print("\n" + output)


if __name__ == "__main__":
    main()
