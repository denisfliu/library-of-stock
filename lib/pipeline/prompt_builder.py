#!/usr/bin/env python3
"""
prompt_builder.py — Assemble agent prompts from building blocks.

Reads markdown blocks from docs/, concatenates them in the correct order,
renumbers steps sequentially, and wraps in the agent loop template.

Usage:
    python3 lib/pipeline/prompt_builder.py first --category Literature
    python3 lib/pipeline/prompt_builder.py second --category Philosophy
    python3 lib/pipeline/prompt_builder.py first --category "Fine Arts"
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent.parent  # project root
DOCS_DIR = ROOT / 'docs'

CATEGORY_SUPPLEMENTS = {
    'literature': 'analysis_literature.md',
    'fine arts': 'analysis_vfa.md',
    'auditory fine arts': 'analysis_afa.md',
    'philosophy': 'analysis_philosophy.md',
    'science': 'analysis_science.md',
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

    # 4. Card generation rules (always included — agents generate cards inline)
    blocks.append(read_block(DOCS_DIR / 'analysis_cards.md'))

    # Concatenate with dividers and renumber all steps sequentially
    combined = '\n\n---\n\n'.join(b for b in blocks if b)
    return renumber_steps(combined)


# ---------------------------------------------------------------------------
# Loop templates — the operational steps agents execute per topic
# ---------------------------------------------------------------------------

FIRST_PASS_LOOP = """## Process one topic

### Pop topic
```bash
python3 lib/queue/batch_worker.py pop first --category "{category}"
```
If output is "EMPTY", queue is empty — exit.
Parse JSON output to get the full topic name and metadata.

### Derive slug
`slug = full_topic_name.lower().replace(" ", "_")`
Examples: "Samuel Beckett" → `samuel_beckett` | "Béla Bartók" → `béla_bartók` | "Bong Joon-ho" → `bong_joon-ho`

### Fetch clues
```
python3 lib/run.py "SEARCH TERM" "7,8,9,10" --outdir output/{{slug}}
```
Use the minimally identifiable search term (usually last name or common name). Saves `output/{{slug}}/clues.txt`.

### Expand if sparse
If fewer than **10 total tossups + bonuses**, run:
1. `python3 lib/run.py "SEARCH TERM" "5,6,7,8,9,10" --outdir output/{{slug}}`
2. `python3 lib/run.py "SEARCH TERM" "5,6,7,8,9,10" --mentions --outdir output/{{slug}}`

Read all output files. Label text mention clues as contextual.

### Analyze and write analysis.json
Read `output/{{slug}}/clues.txt`. Create `output/{{slug}}/analysis.json` following the analysis protocol above.
Set "topic" to the FULL proper name (from the answerline). Reference `output/emily_carr/analysis.json` for formatting.

Required fields: `topic`, `summary` (non-empty), `works`, `comprehensive_summary`, `cards`, `category`, `subcategory`, `genre`, `year`, `continent`, `country`, `tags`, `links`, `recursive_suggestions`

Generate the `cards` array following the card generation rules in this prompt. Every clue with specific learnable content gets a card.

### Self-check (MANDATORY)
- [ ] `summary` filled (concise blurb — NOT empty)
- [ ] More than 1 work section if clues mention multiple works/ideas
- [ ] Every work mentioned 3+ times has its own section
- [ ] `indicator` set on every work; description is a mini-paragraph
- [ ] `comprehensive_summary` is real prose
- [ ] All metadata present: category, subcategory, year, continent, country, tags

### Render
```bash
python3 -c "from lib.render.render import render_html; import json; f=open('output/{{slug}}/analysis.json'); a=json.load(f); render_html(a, 'output/{{slug}}/stock.html')"
```

### Mark complete
```bash
python3 lib/queue/batch_worker.py complete "FULL TOPIC NAME"
python3 lib/queue/topic_queue.py remove-first "FULL TOPIC NAME"
```

## RULES
- Do NOT manually construct or guess image URLs. VFA agents: run `fix_images.py --slug {{slug}}` after writing analysis.json as instructed in the protocol above. All other categories: no image steps.
- ALWAYS run `python3 lib/run.py` to fetch clues — NEVER write clues.txt manually. The API cache JSON is required for the questions page renderer.
- If 0 results: mark complete with "(no results)" and exit."""

SECOND_PASS_LOOP = """## Process one topic

### Pop topic
```bash
python3 lib/queue/batch_worker.py pop second --category "{category}"
```
If output is "EMPTY", queue is empty — exit.
Parse JSON output to get the topic name and slug.

### Load existing analysis
Read `output/{{slug}}/analysis.json`. Note work sections, card count, and thin-coverage works.

### Fetch additional data
If sparse (<10 original tossups+bonuses or <4 work sections):
```bash
python3 lib/run.py "SEARCH TERM" "5,6,7,8,9,10" --mentions --outdir output/{{slug}}
```

For each major work (skip "General / Biographical" and "Other Works"):
```bash
python3 lib/run.py "WORK NAME" "7,8,9,10" --outdir output/{{slug}}
```
Always use `--outdir output/{{slug}}` — never let subitem results land in their own top-level directories.
Strip dates and parentheticals (e.g. "The Course of Empire (1833–1836)" → "The Course of Empire").
Skip works with 5+ clues already. If 0 results, skip.

### Merge and update analysis.json
Read ALL new clue files. Follow the merge protocol above.
Reference `output/emily_carr/analysis.json` for formatting.

Generate cards for any new clues added during this pass (append to the existing `cards` array). Follow the card generation rules in this prompt.

### Self-check (MANDATORY)
- [ ] All existing work sections preserved; no frequency counts reduced
- [ ] New clues added to appropriate sections
- [ ] `comprehensive_summary` rewritten to include new info
- [ ] `summary` blurb filled and high quality
- [ ] `second_pass` tracking field added

### Render
```bash
python3 -c "from lib.render.render import render_html; import json; f=open('output/{{slug}}/analysis.json'); a=json.load(f); render_html(a, 'output/{{slug}}/stock.html')"
```

### Mark complete
```bash
python3 lib/queue/batch_worker.py complete "FULL TOPIC NAME"
python3 lib/queue/topic_queue.py remove-second "FULL TOPIC NAME"
```

## RULES
- VFA and Other Fine Arts (architecture) agents: run `python3 lib/images/fix_images.py --slug {{slug}}` after updating analysis.json — same as first pass. All other categories: no image steps.
- Do NOT remove existing data — only add to it."""


CARD_AGENT_TEMPLATE = """\
You are a card generation agent for the topic "{topic}". Generate its `cards` array from scratch, then exit. Do NOT ask for confirmation.

Working directory: /home/laufey/code/stock

## Card Rules

{cards_block}

---

### 1. Read the analysis
Read `output/{slug}/analysis.json`. Study all work sections and clues carefully.

### 2. Generate cards
Following the card rules above, produce a complete `cards` array. Every clue with specific learnable content gets a card. Do not skip clues.

### 3. Write back
Replace ONLY the `cards` field in `output/{slug}/analysis.json`. Do not modify any other field.

### 4. Render
```bash
python3 lib/render/render_cards.py
```\
"""

CARD_AGENT_BATCH_TEMPLATE = """\
You are a card generation agent. Generate the `cards` array for each of the {n} topics below, then exit. Do NOT ask for confirmation.

Working directory: /home/laufey/code/stock

## Card Rules

{cards_block}

---

## Topics ({n} total)

{topic_list}

## For each topic (in order):

### Step A — Read the analysis
Read `output/<slug>/analysis.json`. Study all work sections and clues carefully.

### Step B — Generate cards
Following the card rules above, produce a complete `cards` array. Every clue with specific learnable content gets a card. Do not skip clues.

### Step C — Write back
Replace ONLY the `cards` field in `output/<slug>/analysis.json`. Do not modify any other field.

Finish all topics before rendering.

## After all topics are done:

```bash
python3 lib/render/render_cards.py
```\
"""


AGENT_TEMPLATE = """You are a {pass_label} agent for {category} topics. Process one topic from the shared batch queue, then exit. Do NOT ask for confirmation.

## ANALYSIS PROTOCOL

{protocol}

{loop}"""


def build_card_prompt_batch(topics: list, category: str | None = None) -> str:
    """Build a card agent prompt for a batch of 3–5 topics.

    Each entry in topics is either a string (topic name) or a dict with
    'topic' and optional 'category' and 'slug' keys.
    """
    cards_block = read_block(DOCS_DIR / 'analysis_cards.md')

    supplement_block = ''
    if category:
        cat_key = category.lower()
        if cat_key in CATEGORY_SUPPLEMENTS:
            sup_path = DOCS_DIR / CATEGORY_SUPPLEMENTS[cat_key]
            if sup_path.exists():
                supplement_block = '\n\n---\n\n' + read_block(sup_path)

    lines = []
    for entry in topics:
        if isinstance(entry, dict):
            name = entry.get('topic', '')
            slug = entry.get('slug') or name.lower().replace(' ', '_')
        else:
            name = entry
            slug = name.lower().replace(' ', '_')
        lines.append(f"- **{name}** → `output/{slug}/analysis.json`")

    topic_list = '\n'.join(lines)

    return CARD_AGENT_BATCH_TEMPLATE.format(
        n=len(topics),
        cards_block=cards_block + supplement_block,
        topic_list=topic_list,
    ).strip()


def build_card_prompt(topic: str, category: str | None = None) -> str:
    """Build the card agent prompt for a single topic.

    Injects analysis_cards.md and the category supplement (if known) directly
    into the prompt — same pattern as build_protocol().
    """
    slug = topic.lower().replace(' ', '_')
    cards_block = read_block(DOCS_DIR / 'analysis_cards.md')

    supplement_block = ''
    if category:
        cat_key = category.lower()
        if cat_key in CATEGORY_SUPPLEMENTS:
            sup_path = DOCS_DIR / CATEGORY_SUPPLEMENTS[cat_key]
            if sup_path.exists():
                supplement_block = '\n\n---\n\n' + read_block(sup_path)

    return CARD_AGENT_TEMPLATE.format(
        topic=topic,
        slug=slug,
        cards_block=cards_block + supplement_block,
    ).strip()


def build_prompt(pass_type: str, category: str) -> str:
    """Build the full agent prompt for a given pass type and category."""
    protocol = build_protocol(pass_type, category)

    if pass_type == 'first':
        pass_label = 'stock guide generation'
        loop = FIRST_PASS_LOOP.format(category=category)
    else:
        pass_label = 'second-pass enrichment'
        loop = SECOND_PASS_LOOP.format(category=category)

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
    i = 1
    while i < len(args):
        if args[i] == '--category' and i + 1 < len(args):
            category = args[i + 1]
            i += 2
        else:
            i += 1

    if not category:
        print('--category is required')
        sys.exit(1)

    print(build_prompt(pass_type, category))
