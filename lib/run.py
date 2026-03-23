"""
run.py — Runner script for the stock knowledge pipeline.

Usage:
    python run.py <topic> [difficulties] [min_year] [category] [--mentions] [--outdir <path>]

Examples:
    python run.py "Smetana" "7,8,9,10"
    python run.py "Beethoven" "7,8,9,10" 2015
    python run.py "The Rite of Spring"
    python run.py "Indiana" "5,6,7,8,9,10" 2012 "Literature"
    python run.py "Smetana" "5,6,7,8,9,10" --mentions
    python run.py "Beckett" "7,8,9,10" --outdir output/samuel_beckett
"""

import sys
from pathlib import Path

# Ensure project root is on sys.path so imports work from any cwd.
# Also remove lib/ from sys.path — Python adds the script's own directory
# automatically, but lib/queue/ would shadow the stdlib 'queue' module.
_project_root = str(Path(__file__).resolve().parent.parent)
_lib_dir = str(Path(__file__).resolve().parent)
sys.path.insert(0, _project_root)
if _lib_dir in sys.path:
    sys.path.remove(_lib_dir)

from lib.pipeline.fetch import fetch_topic, fetch_text_mentions
from lib.pipeline.parse import parse_answer_clues, parse_text_mention_clues


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


def format_text_mentions_for_analysis(parsed: dict) -> str:
    """
    Format text mention clues into a readable text block.
    Similar to format_clues_for_analysis but indicates these are
    text mentions (topic appears in text but is NOT the answer).
    """
    lines = []
    query = parsed['query_string']
    stats = parsed['stats']

    lines.append(f"=== TEXT MENTION CLUES: {query} ===")
    lines.append(f"(Questions where '{query}' appears in the text but is NOT the answer)")
    lines.append(f"Tossup questions: {stats['tossup_questions']} found, "
                 f"{stats['tossup_clue_sentences']} clue sentences")
    lines.append(f"Bonus questions: {stats['bonus_questions']} found, "
                 f"{stats['bonus_clue_parts']} bonus parts")
    lines.append("")

    # Group tossup clues by source question
    lines.append("--- TEXT MENTION TOSSUPS ---")
    lines.append("")

    tossup_groups = {}
    for clue in parsed['tossup_clues']:
        qid = clue['source']['id']
        if qid not in tossup_groups:
            tossup_groups[qid] = {'source': clue['source'], 'clues': []}
        tossup_groups[qid]['clues'].append(clue)

    for i, (qid, group) in enumerate(tossup_groups.items(), 1):
        src = group['source']
        lines.append(f"[TM{i}] {src['set']} ({src['year']}) | "
                     f"Diff: {src['difficulty']} | {src['category']}")
        lines.append(f"     Answer: {src['answer']}")
        for clue in group['clues']:
            lines.append(f"  - {clue['text'][:300]}")
        lines.append("")

    # Bonus mentions
    lines.append("--- TEXT MENTION BONUSES ---")
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
        lines.append(f"[BM{i}] {src['set']} ({src['year']}) | "
                     f"Diff: {src['difficulty']} | {src['category']}")
        lines.append(f"     Leadin: {group['leadin']}")
        for part in group['parts']:
            lines.append(f"  Part {part['part_index']+1} "
                         f"(ans: {part['part_answer']}):")
            lines.append(f"    {part['text'][:300]}")
        lines.append("")

    return "\n".join(lines)


def main():
    if len(sys.argv) < 2:
        print("Usage: python run.py <topic> [difficulties] [min_year] [category] [--mentions]")
        print('Example: python run.py "Smetana" "7,8,9,10"')
        print('Example: python run.py "Smetana" "7,8,9,10" --mentions')
        print('Example: python run.py "Indiana" "7,8,9,10" 2012 "Literature"')
        sys.exit(1)

    # Parse flags
    mentions_mode = '--mentions' in sys.argv
    raw_flags = [a for a in sys.argv[1:] if a.startswith('--')]
    args = [a for a in sys.argv[1:] if not a.startswith('--')]

    # --outdir <path>: save into an explicit directory (use simplified filenames)
    outdir = None
    for i, flag in enumerate(raw_flags):
        if flag == '--outdir' and i + 1 < len(raw_flags):
            outdir = raw_flags[i + 1]
            break
    # Also handle --outdir=<path> style or positional after flag
    for arg in sys.argv[1:]:
        if arg.startswith('--outdir='):
            outdir = arg.split('=', 1)[1]
            break
        if arg == '--outdir':
            idx = sys.argv.index('--outdir')
            if idx + 1 < len(sys.argv):
                outdir = sys.argv[idx + 1]
            break

    # Remove outdir value from positional args if present
    if outdir and outdir in args:
        args = [a for a in args if a != outdir]

    topic = args[0]
    diffs = None
    min_year = 2012
    categories = None

    if len(args) > 1:
        diffs = [int(d) for d in args[1].split(",")]
    if len(args) > 2:
        min_year = int(args[2])
    if len(args) > 3:
        categories = [c.strip() for c in args[3].split(",")]

    if outdir:
        # Canonical slug directory provided — use simplified filenames
        topic_dir = Path(outdir)
        topic_dir.mkdir(parents=True, exist_ok=True)
        clue_filename = "mentions_clues.txt" if mentions_mode else "clues.txt"
    else:
        # No outdir — derive directory from search term (legacy/work-subquery behavior)
        safe_name = topic.strip().lower().replace(" ", "_")
        topic_dir = Path("output") / safe_name
        topic_dir.mkdir(parents=True, exist_ok=True)
        clue_filename = f"{safe_name}_mentions_clues.txt" if mentions_mode else f"{safe_name}_clues.txt"

    if mentions_mode:
        # Text mention search
        data = fetch_text_mentions(topic, difficulties=diffs, categories=categories,
                                   min_year=min_year, cache_dir=topic_dir)
        parsed = parse_text_mention_clues(data)
        output = format_text_mentions_for_analysis(parsed)
        out_path = topic_dir / clue_filename
    else:
        # Standard answerline search
        data = fetch_topic(topic, difficulties=diffs, categories=categories,
                           min_year=min_year, cache_dir=topic_dir)
        parsed = parse_answer_clues(data)
        output = format_clues_for_analysis(parsed)
        out_path = topic_dir / clue_filename

    with open(out_path, "w") as f:
        f.write(output)

    print(f"\nClue output saved to {out_path}")
    print(f"({len(output)} characters, ~{len(output)//4} tokens)")

    # Also print to stdout
    print("\n" + output)


if __name__ == "__main__":
    main()
