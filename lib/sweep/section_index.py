"""section_index.py — Map any question's answerline to its overview section.

The overview pages group each unit's curated answerlines into thematic
sections (era/school/movement — e.g. "Classical Antiquity" for European
Literature). This module inverts that grouping into a lookup so the
reader can filter the WHOLE question corpus by section, not just the
questions whose answerline happens to have a wiki page.

The index is a pure function of the overview.json files: it is rebuilt
from scratch on every call, so newly synced sets and edited overviews
are reflected automatically at publish time — nothing to invalidate.

    idx = SectionIndex()                      # reads all overview.json
    idx.section_for(category, subcategory, alternate_subcategory, answer)
        -> (unit_slug, section_name) or None

Matching is mechanical: a question's answerline yields candidate keys
(the primary answer plus each acceptable bracket alternative), each
normalized with answerlines.normalize; the first key found in the unit's
section map wins. Freq-2 appendix answerlines and the freq-1 tail have
no section and return None (the reader buckets those as "Unsectioned").
"""
import json
import re
import sys as _sys
from pathlib import Path as _Path

_sys.path.insert(0, str(_Path(__file__).resolve().parent.parent.parent))
from lib.common import CATEGORIES_DIR
from lib.sweep.answerlines import normalize
from lib.units import unit_for_guide

_ALT_SPLIT = re.compile(r'[;,]| or ')
_LEAD = re.compile(r'^(?:or|accept|and|also accept)\s+', re.I)
_SKIP = re.compile(r'^(?:do not|reject|antiprompt|prompt)\b', re.I)


def candidate_keys(answer: str) -> list[str]:
    """Normalized lookup keys for a raw answerline: the primary answer
    plus each acceptable bracket alternative (rejects/prompts dropped)."""
    if not answer:
        return []
    keys = []
    seen = set()

    def add(s: str):
        k = normalize(s)
        if k and k not in seen:
            seen.add(k)
            keys.append(k)

    primary = answer.split('[')[0].split('(')[0]
    if primary.strip():
        add(primary)
    for seg_group in re.findall(r'\[([^\]]*)\]', answer):
        for seg in _ALT_SPLIT.split(seg_group):
            seg = seg.strip()
            if not seg or _SKIP.match(seg):
                continue
            add(_LEAD.sub('', seg))
    return keys


class SectionIndex:
    """answerline -> section lookup, built from every overview.json."""

    def __init__(self, categories_dir: _Path = CATEGORIES_DIR):
        # unit_slug -> {normalized answerline: section name}
        self._by_unit: dict[str, dict[str, str]] = {}
        for ov_path in sorted(categories_dir.glob('*/overview.json')):
            try:
                ov = json.loads(ov_path.read_text(encoding='utf-8'))
            except (OSError, json.JSONDecodeError):
                continue
            sm: dict[str, str] = {}
            for section in ov.get('sections', []):
                name = section.get('name')
                if not name:
                    continue
                for entry in section.get('entries', []):
                    self._add_entry(sm, entry, name)
                    for work in entry.get('works', []):
                        self._add_entry(sm, work, name)
            if sm:
                self._by_unit[ov_path.parent.name] = sm

    @staticmethod
    def _add_entry(sm: dict, entry: dict, section: str) -> None:
        for raw in ([entry.get('answerline', '')]
                    + [v.get('answerline', '') for v in entry.get('variants', [])]):
            for key in candidate_keys(raw):
                sm.setdefault(key, section)

    def unit_slug(self, category: str, subcategory: str,
                  alternate_subcategory: str = '') -> str | None:
        u = unit_for_guide(category or '', subcategory or '',
                           alternate_subcategory or '')
        return u.slug if u else None

    def section_for(self, category: str, subcategory: str,
                    alternate_subcategory: str, answer: str):
        """Return (unit_slug, section_name) or None."""
        slug = self.unit_slug(category, subcategory, alternate_subcategory)
        if slug is None:
            return None
        sm = self._by_unit.get(slug)
        if not sm:
            return None
        for key in candidate_keys(answer):
            section = sm.get(key)
            if section is not None:
                return (slug, section)
        return None

    def stats(self) -> dict:
        return {slug: len(sm) for slug, sm in self._by_unit.items()}
