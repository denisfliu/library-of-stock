"""matcher.py — Resolve answerlines to existing topic pages.

TopicMatcher matches a cleaned answerline against the corpus in tiers:

    override  output/answerline_overrides.json — LLM/user-confirmed
              mappings (value null = confirmed no-topic). Checked first;
              this is how ambiguous or fuzzy cases get pinned down.
    exact     the normalized topic name of an analysis.json (or its slug
              read as a name).
    alias     topic_index.json entries: last-name aliases and work
              titles. Only aliases that resolve to a single slug count;
              ambiguous ones are dropped. Alias hits are trustworthy
              enough to link, but reports list them for verification.
    unmatched nothing found — a red "no page yet" entry and report row.

Matching runs at render/build time so pages self-heal: once a topic page
is created, every overview and sweep page linking that answerline flips
from red to blue on the next build.
"""
import json
import sys as _sys
from dataclasses import dataclass
from pathlib import Path as _Path

_sys.path.insert(0, str(_Path(__file__).resolve().parent.parent.parent))
from lib.common import OVERRIDES_FILE, TOPIC_INDEX_FILE, resolve_analyses
from lib.sweep.answerlines import normalize


@dataclass
class Match:
    status: str          # "override" | "exact" | "alias" | "unmatched"
    slug: str | None     # None: no page (unmatched, or null override)
    topic: str | None
    via: str | None      # index key that matched, for report display


def load_overrides() -> dict:
    if OVERRIDES_FILE.exists():
        with open(OVERRIDES_FILE, encoding='utf-8') as f:
            return json.load(f)
    return {}


class TopicMatcher:
    def __init__(self, rebuild_index: bool = False, analyses=None):
        """Build lookup tables from the corpus.

        rebuild_index=True refreshes topic_index.json first (the build
        runs crossref.py before the sweep step, so the default trusts
        the file on disk). analyses is the pre-parsed corpus from
        build.py; standalone use loads it here.
        """
        if rebuild_index or not TOPIC_INDEX_FILE.exists():
            from lib.crossref.crossref import rebuild_index as _rebuild
            _rebuild(analyses=analyses)

        self.overrides = load_overrides()

        # Exact tier: normalized analysis topic (and slug-as-name) -> (topic, slug)
        self.exact: dict[str, tuple[str, str]] = {}
        for slug, _path, data in resolve_analyses(analyses, warn=False):
            topic = data.get('topic', '') or slug
            self.exact.setdefault(normalize(topic), (topic, slug))
            self.exact.setdefault(normalize(slug.replace('_', ' ')), (topic, slug))

        # Alias tier: topic_index entries not already exact keys, kept
        # only while they map to a unique slug. The topic's category is
        # kept so alias hits can be gated on category agreement.
        self.aliases: dict[str, tuple[str, str, str, str]] = {}  # key -> (topic, slug, via, category)
        ambiguous: set[str] = set()
        if TOPIC_INDEX_FILE.exists():
            with open(TOPIC_INDEX_FILE, encoding='utf-8') as f:
                index = json.load(f)
            for name, entry in index.items():
                key = normalize(name)
                if not key or key in self.exact:
                    continue
                if key in ambiguous:
                    continue
                prior = self.aliases.get(key)
                if prior and prior[1] != entry['slug']:
                    ambiguous.add(key)
                    del self.aliases[key]
                    continue
                via = f"work:{entry['work']}" if entry.get('type') == 'work' else name
                self.aliases.setdefault(
                    key, (entry['topic'], entry['slug'], via,
                          entry.get('category', '')))

    def match(self, answer_clean: str, category: str | None = None) -> Match:
        """Match an answerline. When ``category`` is given (sweep rows
        and frequency lists know theirs), alias-tier hits require the
        topic's category to agree — a "China" history tossup must not
        link to the Nixon in China opera page via its work title."""
        key = normalize(answer_clean)
        if not key:
            return Match('unmatched', None, None, None)

        if key in self.overrides:
            ov = self.overrides[key]
            if ov is None:
                return Match('override', None, None, 'confirmed no-topic')
            return Match('override', ov.get('slug'), ov.get('topic'), 'override')

        if key in self.exact:
            topic, slug = self.exact[key]
            return Match('exact', slug, topic, None)

        if key in self.aliases:
            topic, slug, via, topic_cat = self.aliases[key]
            if category and topic_cat and topic_cat != category:
                return Match('unmatched', None, None, None)
            return Match('alias', slug, topic, via)

        return Match('unmatched', None, None, None)

    def match_dict(self, answer_clean: str, category: str | None = None) -> dict:
        m = self.match(answer_clean, category=category)
        return {'status': m.status, 'slug': m.slug, 'topic': m.topic, 'via': m.via}
