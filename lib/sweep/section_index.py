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
_PAREN = re.compile(r'\([^)]*\)')   # optional-name / pronunciation groups
_TAG = re.compile(r'<[^>]+>')
_BOLD = re.compile(r'<b><u>(.*?)</u></b>', re.S)


def bold_core(raw: str) -> str | None:
    """The qbreader bold-underline span = the minimal accepted answer
    (e.g. 'Georgia Totto <b><u>O'Keeffe</u></b>' -> 'O'Keeffe'). Returns
    None when the raw answer carries no markup."""
    if not raw:
        return None
    m = _BOLD.search(raw)
    return _TAG.sub('', m.group(1)) if m else None


def candidate_keys(answer: str) -> list[str]:
    """Normalized lookup keys for a raw answerline: the primary answer
    plus each acceptable bracket alternative (rejects/prompts dropped)."""
    if not answer:
        return []
    keys = []
    seen = set()

    def add(s: str):
        # Drop parenthetical groups (optional given names like "(Paul)",
        # pronunciation guides) rather than truncating at the first "(",
        # which would blank a leading-parenthetical answer.
        k = normalize(_PAREN.sub(' ', s))
        if k and k not in seen:
            seen.add(k)
            keys.append(k)

    primary = answer.split('[')[0]
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

    def __init__(self, categories_dir: _Path = CATEGORIES_DIR,
                 topic_index_path: _Path | None = None):
        # unit_slug -> {normalized answerline: section name}
        self._by_unit: dict[str, dict[str, str]] = {}
        # unit_slug -> {last token: section} — only tokens that map to a
        # single section within the unit (ambiguous surnames excluded), so
        # "Georgia Totto O'Keeffe" reaches O'Keeffe's section via "keeffe".
        self._lasttok: dict[str, dict[str, str]] = {}
        # normalized work title -> normalized creator name, from
        # topic_index.json — lets a standalone work answerline inherit its
        # creator's section ("The Persistence of Memory" -> Dalí -> Surrealism).
        self._work_creator: dict[str, str] = {}
        self._load_work_index(topic_index_path)
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
                slug = ov_path.parent.name
                self._by_unit[slug] = sm
                self._lasttok[slug] = self._last_token_index(sm)

    def _load_work_index(self, topic_index_path: _Path | None) -> None:
        if topic_index_path is None:
            topic_index_path = CATEGORIES_DIR.parent / 'topic_index.json'
        try:
            index = json.loads(_Path(topic_index_path).read_text(encoding='utf-8'))
        except (OSError, json.JSONDecodeError):
            return
        for surface, meta in index.items():
            if meta.get('type') != 'work':
                continue
            creator = normalize(meta.get('topic', ''))
            if not creator:
                continue
            for key in candidate_keys(surface):
                self._work_creator.setdefault(key, creator)

    @staticmethod
    def _last_token_index(sm: dict[str, str]) -> dict[str, str]:
        by_tok: dict[str, set[str]] = {}
        for key, section in sm.items():
            toks = key.split()
            if len(toks) >= 2:
                by_tok.setdefault(toks[-1], set()).add(section)
        return {tok: next(iter(secs)) for tok, secs in by_tok.items()
                if len(secs) == 1}

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
        """Return (unit_slug, section_name) or None. `answer` may carry
        qbreader bold-underline markup; the bold core is used as an extra
        candidate."""
        slug = self.unit_slug(category, subcategory, alternate_subcategory)
        if slug is None:
            return None
        sm = self._by_unit.get(slug)
        if not sm:
            return None
        # Candidate keys: sanitized answerline (primary + accepted alts),
        # plus the bold-underline core if the raw answer carries markup.
        keys = candidate_keys(_TAG.sub('', answer))
        core = bold_core(answer)
        if core:
            for k in candidate_keys(core):
                if k not in keys:
                    keys.append(k)
        for key in keys:
            section = sm.get(key)
            if section is not None:
                return (slug, section)
        # Last-token fallback: an unambiguous surname/last word. A
        # multi-word candidate contributes its last token (full birth name
        # -> surname); a single-word candidate (e.g. a bold core "Pollock")
        # IS its own surname.
        lt = self._lasttok.get(slug, {})
        for key in keys:
            toks = key.split()
            surname = toks[-1] if toks else None
            if surname:
                section = lt.get(surname)
                if section is not None:
                    return (slug, section)
        # Work -> creator inheritance: a standalone work answerline takes
        # its creator's section, if that creator is sectioned in this unit.
        for key in keys:
            creator = self._work_creator.get(key)
            if not creator:
                continue
            section = sm.get(creator)
            if section is None:
                ctoks = creator.split()
                if ctoks:
                    section = lt.get(ctoks[-1])
            if section is not None:
                return (slug, section)
        return None

    def stats(self) -> dict:
        return {slug: len(sm) for slug, sm in self._by_unit.items()}
