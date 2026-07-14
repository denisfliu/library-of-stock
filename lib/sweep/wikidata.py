"""wikidata.py — config-driven, high-precision answerline resolution.

A free structured source for the answerline KB: resolve a question's
answerline to a Wikidata entity and read off type / creator / movement /
country / era / coordinates. Runs BEFORE the LLM so tokens go only to
what Wikidata can't place (themes, common-links, obscure entries).

Naive label lookup is noisy (title collisions, engravings-of-people,
disambiguation pages), so every match passes precision guards:
  - alias-aware: match rdfs:label OR skos:altLabel (so "Nile River"
    finds the entity labeled "Nile");
  - type-constrained per category: the entity must read as an allowed
    person / work / place kind (keyword match on P31 / occupation),
    never a disambiguation page or common noun;
  - notability-ranked: among type-valid candidates, the most-sitelinked
    wins;
  - cross-checked: a resolved work's section is inherited from its
    creator only when that creator is already sectioned in the unit.

Results (including misses) are cached to a committed file so re-runs and
new syncs never re-query. The engine is shared; only CATEGORY_CONFIG is
category-specific.
"""
import json
import sys as _sys
import time
import urllib.parse
import urllib.request
from pathlib import Path as _Path

_sys.path.insert(0, str(_Path(__file__).resolve().parent.parent.parent))
from lib.common import OUTPUT_DIR
from lib.sweep.answerlines import normalize
from lib.sweep.section_index import SectionIndex, candidate_keys
from lib.units import UNITS_BY_SLUG

CACHE_PATH = OUTPUT_DIR / '_answerlines' / '_wikidata_cache.json'
ENDPOINT = 'https://query.wikidata.org/sparql'
UA = 'LibraryOfStock/1.0 (quizbowl study tool; denisliu10@gmail.com)'
BATCH = 40
DELAY = 1.2         # polite pacing between SPARQL calls
MIN_SITELINKS = 3   # notability floor — cuts junk matches on short/odd labels

# Per-category resolution config. person_kw / work_kw / place_kw are
# lowercase keyword sets matched against an entity's P31 (instance-of)
# and occupation labels — an entity is accepted only if it reads as one
# of the allowed kinds. creator_prop is the property linking a work to
# the figure whose section it inherits. type_section maps a place/work
# kind keyword to an overview section name (used where the section is a
# function of the entity kind, e.g. Geography).
CATEGORY_CONFIG = {
    'Fine Arts': {
        'person_kw': ['painter', 'artist', 'sculptor', 'photographer',
                      'printmaker', 'engraver', 'architect', 'illustrator',
                      'draughtsman', 'ceramicist'],
        'work_kw': ['painting', 'sculpture', 'work of art', 'artwork',
                    'fresco', 'drawing', 'print', 'installation', 'mural',
                    'triptych', 'altarpiece', 'statue', 'portrait'],
        'creator_prop': 'P170',
    },
    'Literature': {
        'person_kw': ['writer', 'poet', 'novelist', 'playwright', 'author',
                      'dramatist', 'essayist', 'philologist'],
        'work_kw': ['novel', 'poem', 'play', 'literary work', 'short story',
                    'novella', 'book', 'epic', 'poetry collection', 'tragedy',
                    'comedy', 'literary character'],
        'creator_prop': 'P50',
    },
    'Auditory Fine Arts': {
        'person_kw': ['composer', 'musician', 'conductor', 'pianist',
                      'violinist', 'songwriter'],
        'work_kw': ['opera', 'symphony', 'concerto', 'musical work',
                    'composition', 'song', 'ballet', 'sonata', 'oratorio',
                    'suite', 'mass'],
        'creator_prop': 'P86',
    },
    'History': {
        'person_kw': ['politician', 'monarch', 'king', 'queen', 'emperor',
                      'military', 'general', 'president', 'statesman', 'ruler',
                      'noble', 'revolutionary', 'pharaoh', 'sultan', 'tsar'],
        'work_kw': ['battle', 'war', 'siege', 'revolution', 'treaty',
                    'empire', 'dynasty', 'event', 'uprising', 'rebellion',
                    'massacre', 'conflict', 'crisis', 'movement'],
        'creator_prop': None,
    },
    'Geography': {
        'place_kw': ['river', 'mountain', 'lake', 'city', 'country', 'sea',
                     'ocean', 'island', 'desert', 'capital', 'state',
                     'province', 'region', 'peninsula', 'volcano', 'waterfall',
                     'strait', 'bay', 'peak', 'national park', 'megacity',
                     'town', 'municipality', 'plateau', 'glacier', 'gulf',
                     'archipelago', 'reservoir', 'canal'],
        'coords': True,
        # place-kind keyword -> overview section (Geography groups by kind)
        'type_section': [
            (['river', 'lake', 'wetland', 'waterfall', 'reservoir', 'canal',
              'bay', 'gulf', 'strait'], 'Rivers, Lakes, and Wetlands'),
            (['mountain', 'peak', 'volcano', 'desert', 'plateau', 'glacier',
              'landform', 'peninsula', 'valley'], 'Mountains, Deserts, and Landforms'),
            (['ocean', 'sea', 'island', 'archipelago'], 'Oceans, Seas, and Islands'),
            (['city', 'megacity', 'town', 'municipality', 'capital'],
             'Cities and Urban Geography'),
            (['country', 'sovereign state', 'nation'],
             'Countries and Sovereign States'),
            (['state', 'province', 'region', 'territory', 'county'],
             'States, Provinces, and Subnational Regions'),
            (['national park', 'protected area', 'reserve'],
             'National Parks and Protected Areas'),
        ],
    },
    'Philosophy': {
        'person_kw': ['philosopher', 'logician', 'theologian'],
        'work_kw': ['written work', 'book', 'treatise', 'essay', 'dialogue'],
        'creator_prop': 'P50',
    },
    'Social Science': {
        'person_kw': ['economist', 'psychologist', 'sociologist',
                      'anthropologist', 'linguist', 'political scientist',
                      'social scientist'],
        'work_kw': ['book', 'written work', 'theory', 'model'],
        'creator_prop': 'P50',
    },
    'Science': {
        'person_kw': ['scientist', 'physicist', 'chemist', 'biologist',
                      'mathematician', 'astronomer', 'geologist', 'engineer',
                      'computer scientist', 'naturalist'],
        'work_kw': [],
        'creator_prop': None,
    },
    'Religion': {
        'person_kw': ['theologian', 'religious figure', 'saint', 'prophet',
                      'clergy', 'religious leader'],
        'work_kw': ['religious text', 'scripture', 'book'],
        'creator_prop': None,
    },
    'Mythology': {
        'person_kw': ['deity', 'mythological figure', 'god', 'goddess',
                      'legendary figure', 'mythical creature'],
        'work_kw': [],
        'creator_prop': None,
    },
}

# P31 QIDs we always reject (not real entities for our purposes).
_REJECT_TYPES = {
    'Q4167410',   # Wikimedia disambiguation page
    'Q4167836',   # Wikimedia category
    'Q13406463',  # Wikimedia list article
    'Q11266439',  # Wikimedia template
}


def _load_cache() -> dict:
    if CACHE_PATH.exists():
        try:
            return json.loads(CACHE_PATH.read_text(encoding='utf-8'))
        except (OSError, json.JSONDecodeError):
            pass
    return {}


def _save_cache(cache: dict) -> None:
    CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    CACHE_PATH.write_text(json.dumps(cache, ensure_ascii=False, sort_keys=True),
                          encoding='utf-8')


def _sparql(query: str, retries: int = 2) -> list:
    url = ENDPOINT + '?' + urllib.parse.urlencode({'query': query, 'format': 'json'})
    req = urllib.request.Request(url, headers={'User-Agent': UA})
    for attempt in range(retries + 1):
        try:
            with urllib.request.urlopen(req, timeout=90) as resp:
                return json.loads(resp.read())['results']['bindings']
        except Exception:
            if attempt == retries:
                raise
            time.sleep(3 * (attempt + 1))
    return []


def _esc(s: str) -> str:
    return s.replace('\\', '\\\\').replace('"', '\\"')


def _era_bucket(year):
    if year is None:
        return None
    y = int(year)
    if y < 1500: return 'Pre-1500'
    if y < 1600: return '1500s'
    if y < 1700: return '1600s'
    if y < 1800: return '1700s'
    if y < 1900: return '1800s'
    if y < 1946: return '1900–1945'
    return 'Post-1945'


class WikidataResolver:
    def __init__(self):
        self._cache = _load_cache()
        self._section_idx = SectionIndex()

    # ---- candidate selection (Phase 1) -------------------------------
    def _candidates(self, labels, cfg):
        """label -> best (qid, sitelinks, kind) that passes type guards."""
        vals = ' '.join('"%s"@en' % _esc(s) for s in labels)
        q = ('SELECT ?lab ?item ?sl ?p31Label ?occLabel WHERE {'
             ' VALUES ?lab { %s }'
             ' ?item rdfs:label|skos:altLabel ?lab; wikibase:sitelinks ?sl.'
             ' OPTIONAL { ?item wdt:P31 ?p31. }'
             ' OPTIONAL { ?item wdt:P106 ?occ. }'
             ' SERVICE wikibase:label { bd:serviceParam wikibase:language "en". } }'
             % vals)
        rows = _sparql(q)
        # gather per (label,item): sitelinks, type labels, occ labels, p31 qids
        agg = {}
        for b in rows:
            lab = b['lab']['value']
            qid = b['item']['value'].rsplit('/', 1)[-1]
            e = agg.setdefault((lab, qid), {
                'sl': int(b['sl']['value']), 'types': set(), 'occs': set(),
                'p31': set()})
            if 'p31Label' in b:
                e['types'].add(b['p31Label']['value'].lower())
            if 'occLabel' in b:
                e['occs'].add(b['occLabel']['value'].lower())
        # also collect p31 QIDs to reject disambig pages
        # (query again lightly is overkill; infer from type labels instead)
        best = {}
        for (lab, qid), e in agg.items():
            if e['sl'] < MIN_SITELINKS:
                continue
            kind = self._classify(e, cfg)
            if kind is None:
                continue
            if lab not in best or e['sl'] > best[lab][1]:
                best[lab] = (qid, e['sl'], kind, frozenset(e['types']))
        return best

    @staticmethod
    def _kw_hit(text_set, keywords):
        return any(any(kw in t for t in text_set) for kw in keywords)

    def _classify(self, e, cfg):
        types = e['types']
        if any('disambiguation' in t or 'wikimedia' in t for t in types):
            return None
        if cfg.get('person_kw') and self._kw_hit(e['occs'], cfg['person_kw']):
            return 'person'
        if cfg.get('place_kw') and self._kw_hit(types, cfg['place_kw']):
            return 'place'
        if cfg.get('work_kw') and self._kw_hit(types, cfg['work_kw']):
            return 'work'
        return None

    # ---- property pull (Phase 2) -------------------------------------
    def _properties(self, qids, cfg):
        qvals = ' '.join('wd:%s' % q for q in qids)
        creator_prop = cfg.get('creator_prop')
        creator_line = ('OPTIONAL { ?item wdt:%s ?creator. }' % creator_prop
                        if creator_prop else '')
        q = ('SELECT ?item ?creatorLabel ?movementLabel ?countryLabel'
             ' ?p17Label (YEAR(?birth) AS ?by) (YEAR(?inc) AS ?iy) ?coord WHERE {'
             ' VALUES ?item { %s }'
             ' %s'
             ' OPTIONAL { ?item wdt:P135 ?movement. }'
             ' OPTIONAL { ?item wdt:P27 ?country. }'
             ' OPTIONAL { ?item wdt:P17 ?p17. }'
             ' OPTIONAL { ?item wdt:P569 ?birth. }'
             ' OPTIONAL { ?item wdt:P571 ?inc. }'
             ' OPTIONAL { ?item wdt:P625 ?coord. }'
             ' SERVICE wikibase:label { bd:serviceParam wikibase:language "en". } }'
             % (qvals, creator_line))
        out = {}
        for b in _sparql(q):
            qid = b['item']['value'].rsplit('/', 1)[-1]
            p = out.setdefault(qid, {'movements': set()})
            if 'creatorLabel' in b and 'creator' not in p:
                v = b['creatorLabel']['value']
                if not v.startswith('http'):
                    p['creator'] = v
            if 'movementLabel' in b:
                v = b['movementLabel']['value']
                if not v.startswith('http'):
                    p['movements'].add(v)
            for src, dst in (('countryLabel', 'country'), ('p17Label', 'country')):
                if src in b and 'country' not in p:
                    p['country'] = b[src]['value']
            for src, dst in (('by', 'year'), ('iy', 'year')):
                if src in b and 'year' not in p:
                    p['year'] = b[src]['value']
            if 'coord' in b and 'coord' not in p:
                p['coord'] = b['coord']['value']
        return out

    # ---- section derivation ------------------------------------------
    def _section(self, unit, kind, props, cfg, types):
        # work: inherit the creator's section if the creator is sectioned
        if kind == 'work' and props.get('creator'):
            hit = self._section_idx.section_for(
                unit.category, unit.subcategory, '', props['creator'])
            if hit:
                return hit[1]
        # place: map the entity kind to a section (Geography groups by kind)
        if kind == 'place' and cfg.get('type_section'):
            for keywords, section in cfg['type_section']:
                if self._kw_hit(types, keywords):
                    return section
        return None

    # ---- public API ---------------------------------------------------
    def resolve(self, unit_slug, labels):
        """labels -> {norm_label: record|None}. Cached; only uncached
        labels hit the network."""
        unit = UNITS_BY_SLUG[unit_slug]
        cfg = CATEGORY_CONFIG.get(unit.category)
        result = {}
        pending = []
        for lab in labels:
            nlab = normalize(lab)
            # skip degenerate answerlines that only ever match junk
            if len(nlab) < 4 or nlab.isdigit() or not any(c.isalpha() for c in nlab):
                result[nlab] = None
                continue
            ck = f'{unit_slug}␟{nlab}'
            if ck in self._cache:
                result[nlab] = self._cache[ck]
            else:
                pending.append(lab)
        if not cfg or not pending:
            _save_cache(self._cache)
            return result

        for i in range(0, len(pending), BATCH):
            chunk = pending[i:i + BATCH]
            try:
                best = self._candidates(chunk, cfg)
            except Exception:
                best = {}
            qids = {v[0] for v in best.values()}
            props = self._properties(qids, cfg) if qids else {}
            time.sleep(DELAY)
            for lab in chunk:
                nlab = normalize(lab)
                ck = f'{unit_slug}␟{nlab}'
                rec = None
                if lab in best:
                    qid, sl, kind, types = best[lab]
                    p = props.get(qid, {})
                    section = self._section(unit, kind, p, cfg, types)
                    movement = sorted(p.get('movements', []))
                    rec = {
                        'display': lab,
                        'type': {'person': 'person', 'work': 'work',
                                 'place': 'place'}.get(kind, 'other'),
                        'section': section,
                        'movement': movement,
                        'era': _era_bucket(p.get('year')),
                        'country': p.get('country'),
                        'creator': p.get('creator'),
                        'coord': p.get('coord'),
                        'qid': qid,
                        'source': 'wikidata',
                    }
                self._cache[ck] = rec
                result[nlab] = rec
        _save_cache(self._cache)
        return result
