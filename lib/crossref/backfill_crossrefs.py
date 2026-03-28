#!/usr/bin/env python3
"""
Backfill cross_refs for topics that are missing them.
Conservative approach: only match canonical names (not single-word aliases).

Usage: python3 backfill_crossrefs.py [--dry-run]
"""

import json
import re
import sys
from pathlib import Path

DRY_RUN = '--dry-run' in sys.argv

# Load topic index
with open('output/topic_index.json') as f:
    index = json.load(f)

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

searchable = {}
for name, entry in index.items():
    if name in SKIP_TERMS:
        continue
    if len(name) < MIN_LEN:
        continue
    if not is_canonical(name, entry):
        continue
    searchable[name] = entry

# Sort by length descending (match longer names first, avoiding partial matches)
search_names = sorted(searchable.keys(), key=len, reverse=True)

print(f'Searchable canonical entries: {len(search_names)}')


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


def find_cross_refs(d, topic_name, topic_slug):
    """Find all cross-refs for a given analysis dict."""
    full_text = get_text_fields(d)
    # We'll mask matched spans with spaces to prevent shorter names from matching
    # within already-matched longer names
    masked_text = full_text
    found = []
    seen_targets = set()  # (target_topic, target_work) to avoid duplicates

    for name in search_names:
        entry = searchable[name]

        # Check if name appears in masked text with word boundaries
        pattern = r'\b' + re.escape(name) + r'\b'
        m = re.search(pattern, masked_text)
        if not m:
            continue

        # For single-word names (topic type), verify the match isn't part of
        # a longer multi-word name (e.g., 'Raphael' in 'Anton Raphael Mengs').
        # Require that the match is either at start of text, end of text, or
        # surrounded by non-alpha characters (punctuation, spaces, numbers).
        if len(name.split()) == 1 and entry.get('type') == 'topic':
            start = m.start()
            end = m.end()
            before = masked_text[start-1] if start > 0 else ' '
            after = masked_text[end] if end < len(masked_text) else ' '
            # If preceded by a capital letter word (another name word), skip
            # More precisely: if preceded by an alphabetic character that's part of a word
            if start > 0 and masked_text[start-1].isalpha():
                # This match is preceded by a letter — could be a compound name
                # Skip this match (e.g., 'Raphael' preceded by 'Anton ')
                pass  # word boundary already handles this
            # Check: if preceded by Title case word (another name), it's a full name
            # Look back for the previous word
            pre_match = masked_text[:start].rstrip()
            pre_words = re.findall(r'\b\w+\b', pre_match)
            if pre_words:
                prev_word = pre_words[-1]
                # If prev word is a capitalized word (potential first name) and
                # next part is also a word (potential last name), this is risky
                post_match = masked_text[end:].lstrip()
                post_words = re.findall(r'\b\w+\b', post_match)
                next_word = post_words[0] if post_words else ''
                # If surrounded by capitalized words, it's likely a middle name
                if (prev_word and prev_word[0].isupper() and
                    next_word and next_word[0].isupper() and
                    len(prev_word) > 2 and len(next_word) > 2):
                    # e.g., 'Anton Raphael Mengs' — skip
                    # But not 'The Raphael tradition' — 'The' is too common
                    # Actually check: is prev_word a likely first name?
                    # Simple heuristic: if prev_word is not in a small stop-word set
                    stop_words = {'The', 'A', 'An', 'And', 'Or', 'But', 'In', 'On',
                                  'At', 'To', 'For', 'Of', 'By', 'As', 'Is', 'Was',
                                  'His', 'Her', 'Their', 'Its', 'This', 'That', 'These'}
                    if prev_word not in stop_words:
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

        target_topic = entry['topic']
        target_slug = entry['slug']
        entry_type = entry['type']
        target_work = entry.get('work') if entry_type == 'work' else None

        # Dedup key
        dedup_key = (target_topic, target_work)
        if dedup_key in seen_targets:
            continue
        seen_targets.add(dedup_key)

        ref = {
            'name': name,
            'topic': target_topic,
            'slug': target_slug,
            'work': target_work,
            'type': entry_type,
            'exists': True,
        }
        found.append(ref)

    return found


def get_slug(filepath, d):
    """Get slug from filepath."""
    return filepath.parent.name


# Find all topics missing cross_refs
missing_files = []
for f in sorted(Path('output').glob('*/analysis.json')):
    d = json.load(open(f))
    if not d.get('cross_refs'):
        missing_files.append((f, d))

print(f'Found {len(missing_files)} topics missing cross_refs')
print()

updated = 0
no_refs_found = []

for filepath, d in missing_files:
    topic_name = d.get('topic', filepath.stem)
    topic_slug = get_slug(filepath, d)
    refs = find_cross_refs(d, topic_name, topic_slug)

    if refs:
        d['cross_refs'] = refs
        if not DRY_RUN:
            with open(filepath, 'w') as f:
                json.dump(d, f, indent=2, ensure_ascii=False)
        updated += 1
        print(f'  {topic_name}: {len(refs)} refs')
        for r in refs[:3]:
            print(f'    -> {r["name"]!r} ({r["target_topic"]})')
    else:
        d['cross_refs'] = []
        if not DRY_RUN:
            with open(filepath, 'w') as f:
                json.dump(d, f, indent=2, ensure_ascii=False)
        no_refs_found.append(topic_name)
        print(f'  {topic_name}: (no external refs found)')

print()
print('Summary:')
print(f'  Topics with refs added: {updated}')
print(f'  Topics with no refs: {len(no_refs_found)}')
if no_refs_found:
    print(f'  Empty: {no_refs_found}')
