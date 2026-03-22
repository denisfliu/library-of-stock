#!/usr/bin/env python3
"""
prompt_builder.py — Assemble agent prompts from building blocks.

Reads markdown blocks from docs/, concatenates them in the correct order,
renumbers steps sequentially, and wraps in the agent loop template.

Usage:
    python3 lib/prompt_builder.py first --category Literature
    python3 lib/prompt_builder.py second --category Philosophy
    python3 lib/prompt_builder.py first --category "Fine Arts" --max-topics 5
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
DOCS_DIR = ROOT / 'docs'

CATEGORY_SUPPLEMENTS = {
    'literature': 'analysis_literature.md',
    'fine arts': 'analysis_vfa.md',
    'auditory fine arts': 'analysis_afa.md',
    'philosophy': 'analysis_philosophy.md',
    'science': 'analysis_science.md',
}

DEFAULT_MAX_TOPICS = {
    'first': 10,
    'second': 5,
}


def read_block(path: Path) -> str:
    """Read a markdown block file."""
    if not path.exists():
        print(f'Warning: block not found: {path}', file=sys.stderr)
        return ''
    return path.read_text().strip()


def renumber_steps(text: str) -> str:
    """Find all '## Step N:' headers across concatenated blocks and renumber sequentially."""
    counter = [0]
    def replace(match):
        counter[0] += 1
        rest = match.group(1)
        return f'## Step {counter[0]}:{rest}'
    return re.sub(r'## Step \d+:(.*)', replace, text)


def build_protocol(pass_type: str, category: str) -> str:
    """Assemble the analysis protocol from building blocks.

    Concatenation order:
        analysis_core → analysis_{pass_type} → category_supplement → analysis_cards
    """
    blocks = []

    # 1. Core protocol
    blocks.append(read_block(DOCS_DIR / 'analysis_core.md'))

    # 2. Pass-specific block
    if pass_type == 'first':
        blocks.append(read_block(DOCS_DIR / 'analysis_first_pass.md'))
    else:
        blocks.append(read_block(DOCS_DIR / 'analysis_second_pass.md'))

    # 3. Category supplement (if one exists)
    cat_key = category.lower()
    if cat_key in CATEGORY_SUPPLEMENTS:
        sup_path = DOCS_DIR / CATEGORY_SUPPLEMENTS[cat_key]
        if sup_path.exists():
            blocks.append(read_block(sup_path))

    # 4. Card generation rules
    blocks.append(read_block(DOCS_DIR / 'analysis_cards.md'))

    # Concatenate with dividers and renumber all steps sequentially
    combined = '\n\n---\n\n'.join(b for b in blocks if b)
    return renumber_steps(combined)


# ---------------------------------------------------------------------------
# Loop templates — the operational steps agents execute per topic
# ---------------------------------------------------------------------------

FIRST_PASS_LOOP = """## LOOP: Pop and process topics (up to {max_topics})

### Pop next topic
Run: `python3 lib/batch_worker.py pop first --category "{category}"`
If output is "EMPTY", you are done — exit.
Parse the JSON output to get the topic name and metadata.

### Fetch clues
Use the minimally identifiable search term (usually last name or common name):
`python3 lib/run.py "SEARCH TERM" "7,8,9,10"`
Example: search "Falconet" not "Étienne Maurice Falconet"

### Expand search if sparse
If the initial fetch returned fewer than **10 total tossups + bonuses**, run two additional queries:
1. Expanded difficulty: `python3 lib/run.py "SEARCH TERM" "5,6,7,8,9,10"`
2. Text mentions: `python3 lib/run.py "SEARCH TERM" "5,6,7,8,9,10" --mentions`
Read all output files and incorporate into your analysis. Text mention clues should be labeled as contextual.

### Read clues and create analysis JSON
Read `output/{{slug}}_clues.txt`. Create `output/{{slug}}_analysis.json` following the analysis protocol above.
IMPORTANT: Set "topic" to the FULL proper name (from the answerline), not the search term.
Reference `output/emily_carr_analysis.json` for JSON formatting.

Required top-level fields:
- "topic": full proper name
- "summary": concise paragraph (DO NOT LEAVE EMPTY)
- "works": array of work sections
- "comprehensive_summary": multi-paragraph prose
- "cards": array of flashcards
- "category", "subcategory", "year", "continent", "country", "tags"
- "links": Wikipedia links
- "recursive_suggestions": topics worth deeper investigation

### Self-check (MANDATORY)
- [ ] "summary" field is filled (concise paragraph blurb — NOT empty)
- [ ] More than 1 work section (if data mentions multiple works/ideas)
- [ ] Cards array is non-empty
- [ ] Every work/concept mentioned 3+ times has its own section
- [ ] Indicator field set on every work
- [ ] Description is a mini-paragraph (not a terse phrase)
- [ ] comprehensive_summary is real prose (multiple sentences)
- [ ] Metadata present: category, subcategory, year, continent, country, tags
- [ ] Each card tests ONE fact
- [ ] Every card has `"type": "basic"` or `"type": "image"` — NEVER a work type like "Fanfare", "Symphony", "Painting"

### Render
```bash
python3 -c "from lib.render import render_html; import json; f=open('output/{{slug}}_analysis.json'); a=json.load(f); render_html(a, 'output/{{slug}}_stock.html')"
python3 lib/render_cards.py
```

### Mark complete
```bash
python3 lib/batch_worker.py complete "FULL TOPIC NAME"
python3 lib/topic_queue.py remove-first "FULL TOPIC NAME"
```

Then go back to Pop and process the next topic. Stop after {max_topics} topics or when queue is empty.

## RULES
- Do NOT search for images. Images are handled separately after analysis.
- Do NOT use WebSearch for images or construct Wikimedia URLs.
- Process ALL steps for each topic before popping the next.
- If 0 results, mark complete with "(no results)" and move on."""

SECOND_PASS_LOOP = """## LOOP: Pop and process topics (up to {max_topics})

### Pop next topic
Run: `python3 lib/batch_worker.py pop second --category "{category}"`
If output is "EMPTY", you are done — exit.
Parse the JSON output to get the topic name and slug.

### Load existing analysis
Read `output/{{slug}}_analysis.json`. Note how many work sections, cards, and which works have thin coverage.

### Fetch additional data
If the page is sparse (<10 original tossups+bonuses or <4 work sections):
`python3 lib/run.py "TOPIC" "5,6,7,8,9,10" --mentions`

For each major work listed (skip "General / Biographical", "Other Works"):
`python3 lib/run.py "WORK NAME" "7,8,9,10"`
Strip dates and parentheticals from work names. If 0 results, skip.

### Merge and update analysis
Read ALL new clue files. Follow the merge protocol in the analysis protocol above.
Reference `output/emily_carr_analysis.json` for JSON formatting.

### Self-check (MANDATORY)
- [ ] All existing work sections preserved
- [ ] No frequency counts reduced
- [ ] New clues added to appropriate sections
- [ ] Cards generated for new clues
- [ ] comprehensive_summary rewritten to include new info
- [ ] "summary" blurb is filled and high quality
- [ ] second_pass tracking field added
- [ ] Each card tests ONE fact

### Render
```bash
python3 -c "from lib.render import render_html; import json; f=open('output/{{slug}}_analysis.json'); a=json.load(f); render_html(a, 'output/{{slug}}_stock.html')"
python3 lib/render_cards.py
```

### Mark complete
```bash
python3 lib/batch_worker.py complete "FULL TOPIC NAME"
python3 lib/topic_queue.py remove-second "FULL TOPIC NAME"
```

Then go back to Pop and process the next topic. Stop after {max_topics} topics or when queue is empty.

## RULES
- Do NOT search for images. Images are handled separately after analysis.
- Do NOT remove existing data — only add to it.
- Process ALL steps for each topic before popping the next."""


AGENT_TEMPLATE = """You are a {pass_label} agent for {category} topics. Process topics from the shared batch queue. Do NOT ask for confirmation.

## ANALYSIS PROTOCOL

{protocol}

{loop}"""


def build_prompt(pass_type: str, category: str, max_topics: int = None) -> str:
    """Build the full agent prompt for a given pass type and category."""
    if max_topics is None:
        max_topics = DEFAULT_MAX_TOPICS[pass_type]

    protocol = build_protocol(pass_type, category)

    if pass_type == 'first':
        pass_label = 'stock guide generation'
        loop = FIRST_PASS_LOOP.format(category=category, max_topics=max_topics)
    else:
        pass_label = 'second-pass enrichment'
        loop = SECOND_PASS_LOOP.format(category=category, max_topics=max_topics)

    return AGENT_TEMPLATE.format(
        pass_label=pass_label,
        category=category,
        protocol=protocol,
        loop=loop,
    ).strip()


if __name__ == '__main__':
    args = sys.argv[1:]
    if not args or args[0] in ('-h', '--help'):
        print(__doc__.strip())
        sys.exit(0)

    pass_type = args[0]
    if pass_type not in ('first', 'second'):
        print(f'Unknown pass type: {pass_type}. Use "first" or "second".')
        sys.exit(1)

    category = None
    max_topics = None
    i = 1
    while i < len(args):
        if args[i] == '--category' and i + 1 < len(args):
            category = args[i + 1]
            i += 2
        elif args[i] == '--max-topics' and i + 1 < len(args):
            max_topics = int(args[i + 1])
            i += 2
        else:
            i += 1

    if not category:
        print('--category is required')
        sys.exit(1)

    print(build_prompt(pass_type, category, max_topics))
