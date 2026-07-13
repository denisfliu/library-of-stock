"""linker.py — the single name→cross-ref matching engine.

One place owns how surface strings in prose resolve to topic/work links
(previously triplicated across backfill_crossrefs, render's work-button
fallback, and ad-hoc agent judgment). Two tiers:

- **auto** — canonical names: a topic's full name, or a work name of 2+
  words. Linked outright (with the skip-terms / min-length / longer-name
  guards the old backfill used). Safe because canonical names are unique
  by construction (they key the topic index).
- **gated** — ambiguous surfaces: last-name aliases, single-word work
  titles, parenthetical/slash work-name variants. NEVER auto-linked —
  the corpus-unique-alias gamble is exactly what produced wrong-person
  links (Rimbaud "Duffy"→Carol Ann Duffy when the text meant Bruce
  Duffy). A gated hit either resolves through
  output/crossref_overrides.json (an adjudicated decision, applied as
  source:"override") or is emitted as a **candidate** for the
  adjudication agent. Decisions persist, so each surface is judged once
  per topic (or once per category via a global override).

Ref shape (canonical field order): name, type, exists, slug, topic,
work, source.
"""
import json
import re
import sys as _sys
from pathlib import Path as _Path

_sys.path.insert(0, str(_Path(__file__).resolve().parent.parent.parent))
from lib.common import CROSSREF_OVERRIDES_FILE, resolve_analyses

# Guards carried over from the retired backfill_crossrefs.py.
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
    'School', 'Church', 'French', 'College', 'Company', 'Chamber',
    # Ambiguous geographical/common terms
    'Indiana', 'Seeing', 'America', 'Africa', 'Europe', 'Asia',
    'Aurora', 'Atlas',
    # Things too short or generic even if in index
    'Realism', 'Criticism', 'Poets', 'Artists',
    # Multi-word terms with real-world naming collisions
    'Memento Mori', 'The Alchemist', 'Ave Maria', 'The Homecoming',
    'The Castle', 'The Movement', 'The Flea', 'The Misanthrope',
    'Washington Square', 'the mother', 'Baptism of Christ',
    'Bus Stop',  # Inge play/Monroe film vs literal bus stops
}

MIN_LEN = 5

_ALIAS_SKIP = {'the', 'van', 'von', 'de', 'del', 'di', 'der', 'den',
               'le', 'la', 'el'}

_STOP_WORDS = {'The', 'A', 'An', 'And', 'Or', 'But', 'In', 'On',
               'At', 'To', 'For', 'Of', 'By', 'As', 'Is', 'Was',
               'His', 'Her', 'Their', 'Its', 'This', 'That', 'These'}

_WORK_SECTION_FRAGMENTS = ('General', 'Biographical', 'Other Works', 'Other ')


def make_ref(surface: str, entry: dict, source: str) -> dict:
    """Canonical cross_refs object for a resolved surface."""
    return {
        'name': surface,
        'type': entry.get('type', 'topic'),
        'exists': bool(entry.get('exists', True)),
        'slug': entry.get('slug') or '',
        'topic': entry.get('topic', ''),
        'work': entry.get('work') or None,
        'source': source,
    }


def load_overrides(path=None) -> dict:
    path = _Path(path) if path else CROSSREF_OVERRIDES_FILE
    if not path.exists():
        return {'per_topic': {}, 'global': {}}
    with open(path, encoding='utf-8') as f:
        data = json.load(f)
    data.setdefault('per_topic', {})
    data.setdefault('global', {})
    return data


def _adjacent_cap(masked_text: str, m, side: str) -> bool:
    """True if the word immediately adjacent on `side` (whitespace only
    between — punctuation breaks adjacency, so sentence boundaries don't
    count) is a capitalized non-stopword."""
    if side == 'prev':
        chunk = masked_text[:m.start()]
        m2 = re.search(r'(\w+)(\s*)$', chunk)
        word, gap = (m2.group(1), m2.group(2)) if m2 else ('', None)
    else:
        chunk = masked_text[m.end():]
        m2 = re.match(r'(\s*)(\w+)', chunk)
        gap, word = (m2.group(1), m2.group(2)) if m2 else (None, '')
    if gap is None or not word:
        return False
    return (word[0].isupper() and len(word) > 2
            and word not in _STOP_WORDS)


def _is_part_of_longer_name(masked_text: str, m) -> bool:
    """True if a single-word match looks like a chunk of a longer proper
    name: an immediately adjacent capitalized word on either side
    ('Raphael' inside 'Anton Raphael Mengs', 'Carmen' inside 'Carmen
    Maria Machado')."""
    return (_adjacent_cap(masked_text, m, 'prev')
            or _adjacent_cap(masked_text, m, 'next'))


class Linker:
    """Lexicon + scanner. Build once, scan many topics.

    The lexicon is derived from the analyses themselves (not the
    flattened topic_index.json, whose setdefault drops alias collisions
    — the linker needs to KNOW 'Miller' is ambiguous)."""

    def __init__(self, analyses=None, overrides: dict | None = None):
        self.overrides = overrides if overrides is not None else load_overrides()
        self.auto: dict[str, dict] = {}
        self.gated: dict[str, list[dict]] = {}
        self._build_lexicon(resolve_analyses(analyses, warn=False))
        # Longest-first over every known surface, so masking prevents
        # sub-name rematches ('Anna Akhmatova' before 'Akhmatova').
        # Alphabetical tiebreak: equal-length surfaces must scan in a
        # stable order across processes (set order is hash-randomized).
        self._surfaces = sorted(set(self.auto) | set(self.gated),
                                key=lambda s: (-len(s), s))

    def _add_gated(self, surface: str, entry: dict) -> None:
        if surface in SKIP_TERMS or len(surface) < 3:
            return
        targets = self.gated.setdefault(surface, [])
        key = (entry['slug'], entry.get('work'))
        if not any((t['slug'], t.get('work')) == key for t in targets):
            targets.append(entry)

    def _build_lexicon(self, analyses) -> None:
        for slug, _path, data in analyses:
            topic = data.get('topic', '')
            cat = data.get('category', '')
            if not topic:
                continue
            entry = {'slug': slug, 'topic': topic, 'type': 'topic',
                     'category': cat}
            if topic not in SKIP_TERMS and len(topic) >= MIN_LEN:
                self.auto[topic] = entry

            parts = topic.split()
            if len(parts) >= 2:
                last = parts[-1]
                if last.lower() not in _ALIAS_SKIP and len(last) >= 3:
                    self._add_gated(last, entry)

            for w in data.get('works', []):
                wname = w.get('name', '')
                if not wname or any(x in wname
                                    for x in _WORK_SECTION_FRAGMENTS):
                    continue
                wentry = {'slug': slug, 'topic': topic, 'type': 'work',
                          'work': wname, 'category': cat}
                if (len(wname.split()) >= 2 and wname not in SKIP_TERMS
                        and len(wname) >= MIN_LEN):
                    self.auto.setdefault(wname, wentry)
                else:
                    self._add_gated(wname, wentry)
                # Parenthetical-stripped and slash-first variants are
                # ambiguous by nature -> gated.
                clean = re.sub(r'\s*\(.*?\)', '', wname).strip()
                if clean != wname and len(clean) > 3:
                    self._add_gated(clean, wentry)
                if '/' in clean:
                    first_part = clean.split('/')[0].strip()
                    if len(first_part) > 3:
                        self._add_gated(first_part, wentry)

    # -- override resolution -------------------------------------------

    def _override_for(self, surface: str, topic_slug: str,
                      category: str) -> tuple[bool, dict | None]:
        """Returns (decided, resolution). resolution None = never link.
        Precedence: per-topic > per-category global > '*' global."""
        per_topic = self.overrides['per_topic'].get(topic_slug, {})
        if surface in per_topic:
            return True, per_topic[surface]
        for cat in (category, '*'):
            by_cat = self.overrides['global'].get(cat, {})
            if surface in by_cat:
                return True, by_cat[surface]
        return False, None

    # -- scanning --------------------------------------------------------

    def scan(self, text: str, topic_slug: str, topic_name: str,
             category: str) -> tuple[list[dict], list[dict]]:
        """Scan prose for links. Returns (refs, candidates).

        refs carry source 'backfill' (auto tier) or 'override'
        (adjudicated gated tier). candidates are unresolved gated hits:
        {surface, targets, snippet}.
        """
        masked = text
        refs: list[dict] = []
        candidates: list[dict] = []
        seen_targets: set[tuple] = set()

        def is_self(entry) -> bool:
            return (entry.get('slug') == topic_slug
                    or entry.get('topic') == topic_name)

        def add_ref(surface, entry, source) -> None:
            key = (entry.get('topic'), entry.get('work'))
            if key in seen_targets:
                return
            seen_targets.add(key)
            refs.append(make_ref(surface, entry, source))

        for surface in self._surfaces:
            pattern = r'\b' + re.escape(surface) + r'\b'
            m = re.search(pattern, masked)
            if not m:
                continue

            auto_entry = self.auto.get(surface)
            # A single word snuggled against another capitalized word is
            # probably a chunk of some longer proper name — never a link
            # and not worth adjudicating either.
            if (len(surface.split()) == 1
                    and _is_part_of_longer_name(masked, m)):
                masked = re.sub(pattern, ' ' * len(surface), masked)
                continue

            snippet = text[max(0, m.start() - 60):m.end() + 60].replace(
                '\n', ' ').strip()
            masked = re.sub(pattern, ' ' * len(surface), masked)

            # Surface appearing inside the topic's own name is never a
            # link ('Augustus' in 'Augustus Saint-Gaudens').
            if surface in topic_name:
                continue

            if auto_entry is not None:
                if not is_self(auto_entry):
                    add_ref(surface, auto_entry, 'backfill')
                continue

            targets = [t for t in self.gated.get(surface, [])
                       if not is_self(t)]
            if not targets:
                continue
            decided, resolution = self._override_for(surface, topic_slug,
                                                     category)
            if decided:
                if resolution is not None and not is_self(resolution):
                    add_ref(surface, resolution, 'override')
                continue
            candidates.append({'surface': surface, 'targets': targets,
                               'snippet': snippet})

        return refs, candidates
