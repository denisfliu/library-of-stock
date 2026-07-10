#!/usr/bin/env python
"""
Backfill cross_refs for topics that are missing them.
Conservative approach: only match canonical names (not single-word aliases).

Usage: python lib/crossref/backfill_crossrefs.py [--dry-run]
"""

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from lib.common import TOPIC_INDEX_FILE, iter_analyses

# Build CANONICAL-only search set:
# - For topics: only include if name == entry['topic'] (exact canonical name)
# - For works: only include if name == entry['work'] (exact canonical work name)
# This filters out single-word aliases like 'Blake' -> 'William Blake'
# which would cause false positives.
#
# We also skip generic/ambiguous entries.

SKIP_TERMS = {
    # Generic section headers
    'Loop', 'Plot and Characters', 'Songs and Scenes', 'Overview', 'Introduction',
    'Background', 'Legacy', 'Works', 'Style', 'Life', 'Career', 'Themes',
    'Technique', 'Influence', 'Reception', 'Awards', 'Death', 'Early Life',
    'Personal Life', 'Education', 'The',
    # Ambiguous single words
    'Ghosts', 'Opening', 'General', 'Form', 'Forms', 'Verse', 'Drama',
    'Prose', 'Fiction', 'Poetry', 'Novels', 'Novel', 'Songs', 'Song',
    'Plays', 'Play', 'Stories', 'Story', 'Art', 'Arts', 'Music', 'Film',
    'Theater', 'Theatre', 'Philosophy', 'Science', 'Nature', 'History',
    'Beauty', 'Truth', 'Love', 'War', 'Death', 'God', 'Man', 'Woman',
    'Time', 'Space', 'Light', 'Dark', 'White', 'Black', 'Red', 'Blue',
    'Green', 'Gold', 'Silver', 'Night', 'Day', 'Sun', 'Moon', 'Star',
    'Water', 'Fire', 'Earth', 'Wind', 'Rain', 'Snow', 'Spring', 'Summer',
    'Autumn', 'Winter', 'North', 'South', 'East', 'West',
    # Generic section-like names
    'Early Works', 'Late Works', 'Major Works', 'Selected Works',
    'Key Works', 'Important Works', 'Notable Works',
    'Historical Context', 'Critical Reception',
    # Ambiguous common words that ARE in index but cause false positives
    'Short Stories', 'Short Story', 'The Musical', 'The Book',
    'The Novel', 'The Play', 'The Poem', 'The Film', 'The Opera',
    'Essays', 'Letters', 'Journals', 'Diaries',
    'Characters', 'Symbols', 'Motifs',
    'Literary Criticism', 'Literary Theory',
    # Common English words that are last-word shortcuts for person names
    # (these match non-specifically in text)
    'School', 'Church', 'French', 'College', 'Company', 'Chamber',
    # Ambiguous geographical/common terms
    'Indiana', 'Seeing', 'America', 'Africa', 'Europe', 'Asia',
    'Aurora', 'Atlas',
    # Things too short or generic even if in index
    'Realism', 'Criticism', 'Poets', 'Artists',
    # Multi-word terms that cause naming conflicts (title shared with common phrase or different work)
    'Memento Mori',  # Muriel Spark novel vs. common artistic motif
    'The Alchemist',  # Ben Jonson play vs. Paulo Coelho novel (both real)
    'Ave Maria',  # Frank O'Hara poem vs. common religious phrase/Schubert/others
    'The Homecoming',  # Harold Pinter play vs. panel title in Beckmann triptych
    'The Castle',  # Kafka novel vs. various other uses
    'The Movement',  # New Criticism movement vs. general use of "the movement"
    'The Flea',   # John Donne poem vs. other uses (e.g., 'The Flea Catcher')
    'The Misanthrope',  # Moliere play, also Bruegel painting title
    'Washington Square',  # Henry James novel vs. location name
    'the mother',  # Gwendolyn Brooks poem vs. very common phrase
    'Baptism of Christ',  # Both Verrocchio and Piero della Francesca painted this
}

# Minimum name length to avoid very short matches
MIN_LEN = 5

def is_canonical(name, entry):
    """Return True only if 'name' is the canonical name (not an alias/shortcut).

    Rules:
    - Topic entries: canonical if name == entry['topic']
    - Work entries: canonical if name == entry['work'], AND name has 2+ words
      (single-word work titles cause too many false positives)
    """
    etype = entry.get('type', '')
    topic = entry.get('topic', '')
    work = entry.get('work', '')

    if etype == 'topic':
        # Must exactly match the topic name
        return name == topic
    elif etype == 'work':
        # Must exactly match the work name AND be multi-word (2+ words)
        # Single-word work titles (Cathedral, Beloved, etc.) match common words
        return name == work and len(name.split()) >= 2
    return False

def build_searchable(index):
    """Filter the topic index down to canonical, unambiguous names."""
    searchable = {}
    for name, entry in index.items():
        if name in SKIP_TERMS:
            continue
        if len(name) < MIN_LEN:
            continue
        if not is_canonical(name, entry):
            continue
        searchable[name] = entry
    return searchable


def get_text_fields(d):
    """Extract all searchable text from an analysis dict."""
    texts = []
    if d.get('summary'):
        texts.append(d['summary'])
    if d.get('comprehensive_summary'):
        texts.append(d['comprehensive_summary'])
    for work in d.get('works', []):
        if work.get('name'):
            texts.append(work['name'])
        if work.get('description'):
            texts.append(work['description'])
    for card in d.get('cards', []):
        if card.get('clue'):
            texts.append(card['clue'])
        if card.get('answer'):
            texts.append(card['answer'])
    return '\n'.join(texts)


# Words that may legitimately precede a single-word name without forming
# a longer proper name ("The Raphael tradition" vs "Anton Raphael Mengs").
_STOP_WORDS = {'The', 'A', 'An', 'And', 'Or', 'But', 'In', 'On',
               'At', 'To', 'For', 'Of', 'By', 'As', 'Is', 'Was',
               'His', 'Her', 'Their', 'Its', 'This', 'That', 'These'}


def _is_part_of_longer_name(masked_text, m):
    """True if a single-word match sits between two capitalized words,
    i.e. it is likely a middle chunk of a longer proper name
    (e.g. 'Raphael' inside 'Anton Raphael Mengs')."""
    pre_words = re.findall(r'\b\w+\b', masked_text[:m.start()].rstrip())
    post_words = re.findall(r'\b\w+\b', masked_text[m.end():].lstrip())
    prev_word = pre_words[-1] if pre_words else ''
    next_word = post_words[0] if post_words else ''
    return (prev_word and prev_word[0].isupper() and
            next_word and next_word[0].isupper() and
            len(prev_word) > 2 and len(next_word) > 2 and
            prev_word not in _STOP_WORDS)


def find_cross_refs(d, topic_name, topic_slug, searchable, search_names):
    """Find all cross-refs for a given analysis dict."""
    full_text = get_text_fields(d)
    # We'll mask matched spans with spaces to prevent shorter names from matching
    # within already-matched longer names
    masked_text = full_text
    found = []
    seen_targets = set()  # (topic, work) to avoid duplicates

    for name in search_names:
        entry = searchable[name]

        # Check if name appears in masked text with word boundaries
        pattern = r'\b' + re.escape(name) + r'\b'
        m = re.search(pattern, masked_text)
        if not m:
            continue

        if (len(name.split()) == 1 and entry.get('type') == 'topic'
                and _is_part_of_longer_name(masked_text, m)):
            masked_text = re.sub(pattern, ' ' * len(name), masked_text)
            continue

        # Always mask this name to prevent shorter sub-names from re-matching
        masked_text = re.sub(pattern, ' ' * len(name), masked_text)

        # Skip if this points to the same topic as the current page
        if entry.get('slug') == topic_slug:
            continue
        if entry.get('topic') == topic_name:
            continue
        # Skip if the name appears as a substring of the current topic's name
        # (e.g., 'Augustus' in 'Augustus Saint-Gaudens')
        if name in topic_name:
            continue

        entry_type = entry['type']
        work = entry.get('work') if entry_type == 'work' else None

        # Dedup key
        dedup_key = (entry['topic'], work)
        if dedup_key in seen_targets:
            continue
        seen_targets.add(dedup_key)

        found.append({
            'name': name,
            'topic': entry['topic'],
            'slug': entry['slug'],
            'work': work,
            'type': entry_type,
            'exists': True,
        })

    return found


def main():
    dry_run = '--dry-run' in sys.argv

    with open(TOPIC_INDEX_FILE, encoding='utf-8') as f:
        index = json.load(f)

    searchable = build_searchable(index)
    # Sort by length descending (match longer names first, avoiding partial matches)
    search_names = sorted(searchable.keys(), key=len, reverse=True)
    print(f'Searchable canonical entries: {len(search_names)}')

    # Find all topics missing cross_refs
    missing_files = []
    for _slug, path, d in iter_analyses():
        if not d.get('cross_refs'):
            missing_files.append((path, d))

    print(f'Found {len(missing_files)} topics missing cross_refs')
    print()

    updated = 0
    no_refs_found = []

    for filepath, d in missing_files:
        topic_name = d.get('topic', filepath.stem)
        topic_slug = filepath.parent.name
        refs = find_cross_refs(d, topic_name, topic_slug, searchable, search_names)

        d['cross_refs'] = refs
        if not dry_run:
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(d, f, indent=2, ensure_ascii=False)
        if refs:
            updated += 1
            print(f'  {topic_name}: {len(refs)} refs')
            for r in refs[:3]:
                print(f'    -> {r["name"]!r} ({r["topic"]})')
        else:
            no_refs_found.append(topic_name)
            print(f'  {topic_name}: (no external refs found)')

    print()
    print('Summary:')
    print(f'  Topics with refs added: {updated}')
    print(f'  Topics with no refs: {len(no_refs_found)}')
    if no_refs_found:
        print(f'  Empty: {no_refs_found}')


if __name__ == '__main__':
    main()
