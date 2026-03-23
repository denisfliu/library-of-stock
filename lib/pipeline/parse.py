"""
parse.py — Clue extraction from fetched qbreader data.

Takes the cached JSON from fetch.py and extracts individual clues with
metadata, preparing structured input for analysis.
"""

import json
import re
from pathlib import Path


def _strip_html(text: str) -> str:
    """Remove HTML tags from a string."""
    return re.sub(r'<[^>]+>', '', text)


def _split_sentences(text: str) -> list[str]:
    """
    Split question text into sentence-level clues.
    Splits on sentence-ending punctuation followed by a space and uppercase.
    """
    sentences = re.split(
        r'(?<=[.!?])\s+(?=[A-Z"\(\[])',
        text.strip()
    )
    return [s.strip() for s in sentences if s.strip()]


def _is_in_power(sentence: str, full_html: str) -> bool:
    """Check if a sentence falls within the bold (power) region of a tossup."""
    bold_parts = re.findall(r'<b>(.*?)</b>', full_html, re.DOTALL)
    bold_text = ' '.join(_strip_html(p) for p in bold_parts)
    check = sentence[:40]
    return check in bold_text


def extract_tossup_clues(tossup: dict) -> list[dict]:
    """
    Extract individual clues from a tossup.

    Returns a list of clue dicts with:
        - text, in_power, is_giveaway, source metadata
    """
    sanitized = tossup.get('question_sanitized', '')
    html = tossup.get('question', '')

    # Remove pronunciation guides and reading instructions
    cleaned = re.sub(r'\("[\w\s\-\'\.]+"\)', '', sanitized)
    cleaned = re.sub(r'\[read slowly\]\s*', '', cleaned)

    sentences = _split_sentences(cleaned)

    clues = []
    for sent in sentences:
        is_giveaway = bool(re.search(
            r'for (?:10|ten) points', sent, re.IGNORECASE
        ))
        clues.append({
            'text': sent,
            'in_power': _is_in_power(sent, html),
            'is_giveaway': is_giveaway,
            'source': {
                'type': 'tossup',
                'answer': tossup.get('answer_sanitized', ''),
                'set': tossup.get('set', {}).get('name', ''),
                'year': tossup.get('set', {}).get('year', ''),
                'difficulty': tossup.get('difficulty', ''),
                'category': tossup.get('category', ''),
                'subcategory': tossup.get('subcategory', ''),
                'id': tossup.get('_id', ''),
            },
        })

    return clues


def extract_bonus_clues(bonus: dict) -> list[dict]:
    """
    Extract individual clues from a bonus.

    Returns a list of clue dicts with:
        - text, part_index, part_answer, leadin, source metadata
    """
    leadin = bonus.get('leadin_sanitized', '')
    parts = bonus.get('parts_sanitized', [])
    answers = bonus.get('answers_sanitized', [])

    clues = []
    for i, (part, answer) in enumerate(zip(parts, answers)):
        clues.append({
            'text': part,
            'part_index': i,
            'part_answer': answer,
            'leadin': leadin,
            'source': {
                'type': 'bonus',
                'set': bonus.get('set', {}).get('name', ''),
                'year': bonus.get('set', {}).get('year', ''),
                'difficulty': bonus.get('difficulty', ''),
                'category': bonus.get('category', ''),
                'subcategory': bonus.get('subcategory', ''),
                'id': bonus.get('_id', ''),
            },
        })

    return clues


def parse_answer_clues(data: dict) -> dict:
    """
    Parse answerline match data into structured clues.

    Parameters
    ----------
    data : dict
        Output from fetch.fetch_topic().

    Returns dict with:
        - query_string
        - tossup_clues: list of clue dicts
        - bonus_clues: list of clue dicts
        - stats: summary counts
    """
    tossup_clues = []
    for t in data['answer_matches']['tossups']:
        tossup_clues.extend(extract_tossup_clues(t))

    bonus_clues = []
    for b in data['answer_matches']['bonuses']:
        bonus_clues.extend(extract_bonus_clues(b))

    return {
        'query_string': data['query_string'],
        'tossup_clues': tossup_clues,
        'bonus_clues': bonus_clues,
        'stats': {
            'tossup_questions': data['answer_matches']['tossups_found'],
            'bonus_questions': data['answer_matches']['bonuses_found'],
            'tossup_clue_sentences': len(tossup_clues),
            'bonus_clue_parts': len(bonus_clues),
        },
    }


def parse_text_mention_clues(data: dict) -> dict:
    """
    Parse text mention data into structured clues.

    Text mentions are questions where the topic appears in the clue text
    but is NOT the answer. These provide contextual information.

    Parameters
    ----------
    data : dict
        Output from fetch.fetch_text_mentions().

    Returns dict with:
        - query_string
        - tossup_clues: list of clue dicts (includes the actual answer)
        - bonus_clues: list of clue dicts (includes the actual answer)
        - stats: summary counts
    """
    mentions = data.get('text_mentions', {})

    tossup_clues = []
    for t in mentions.get('tossups', []):
        clues = extract_tossup_clues(t)
        # Add the actual answer since the topic is NOT the answer
        for clue in clues:
            clue['source']['answer'] = t.get('answer_sanitized', '')
            clue['source']['search_type'] = 'text_mention'
        tossup_clues.extend(clues)

    bonus_clues = []
    for b in mentions.get('bonuses', []):
        clues = extract_bonus_clues(b)
        for clue in clues:
            clue['source']['search_type'] = 'text_mention'
        bonus_clues.extend(clues)

    return {
        'query_string': data.get('query_string', ''),
        'tossup_clues': tossup_clues,
        'bonus_clues': bonus_clues,
        'stats': {
            'tossup_questions': mentions.get('tossups_found', len(mentions.get('tossups', []))),
            'bonus_questions': mentions.get('bonuses_found', len(mentions.get('bonuses', []))),
            'tossup_clue_sentences': len(tossup_clues),
            'bonus_clue_parts': len(bonus_clues),
        },
    }


if __name__ == "__main__":
    import sys
    from fetch import fetch_topic

    topic = sys.argv[1] if len(sys.argv) > 1 else "Smetana"
    diffs = [int(d) for d in sys.argv[2].split(",")] if len(sys.argv) > 2 else None

    data = fetch_topic(topic, difficulties=diffs)
    parsed = parse_answer_clues(data)

    print(f"Parsed clues for '{parsed['query_string']}':")
    print(f"  Tossup clues: {len(parsed['tossup_clues'])}")
    print(f"  Bonus clues: {len(parsed['bonus_clues'])}")

    print("\n--- Sample tossup clues ---")
    for clue in parsed['tossup_clues'][:8]:
        power = " [PWR]" if clue['in_power'] else ""
        give = " [GIVE]" if clue['is_giveaway'] else ""
        print(f"  {power}{give} {clue['text'][:120]}")
