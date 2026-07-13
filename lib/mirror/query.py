"""query.py — local reimplementation of qbreader's question search
against the SQLite mirror.

Semantics are transliterated from qbreader/website (fetched July 2026):
  - database/qbreader/get-query.js         → query()
  - database/qbreader/get-frequency-list.js → frequency_list()
  - database/qbreader/get-set-list.js      → set_list()
  - routes/validators/category-bundle.js   → _expand_category_bundle()
  - shared/unformat-string.js              → unformat_string()
  - shared/categories.js                   → the taxonomy tables below

Where MongoDB behavior is quirky, the quirk is kept on purpose so
results match what the live API returned when the committed question
store was fetched:
  - a text query is a case-insensitive substring/regex match on the
    *sanitized* fields; on array fields (bonus parts/answers) any one
    element matching counts;
  - an alternateSubcategories filter also matches questions with NO
    alternate_subcategory (get-query.js appends null) — but the
    frequency list filters on exact equality, with no null;
  - passing only a category expands to all of its subcategories and
    alternate subcategories (category-bundle), so unknown off-taxonomy
    values never match;
  - result order is set.name DESC, packet.number ASC, number ASC.

Known acceptable drift: Mongo's $toLower is ASCII-only while Python's
str.lower() is Unicode-aware (affects only non-ASCII answerline casing
in frequency lists).
"""
import json
import re
import sys
import unicodedata
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from lib.mirror import db as mirror_db

DEFAULT_QUERY_RETURN_LENGTH = 25
MAX_QUERY_RETURN_LENGTH = 10000

# shared/categories.js
CATEGORY_TO_SUBCATEGORY = {
    'Literature': ['American Literature', 'British Literature',
                   'Classical Literature', 'European Literature',
                   'World Literature', 'Other Literature'],
    'History': ['American History', 'Ancient History', 'European History',
                'World History', 'Other History'],
    'Science': ['Biology', 'Chemistry', 'Physics', 'Other Science'],
    'Fine Arts': ['Visual Fine Arts', 'Auditory Fine Arts', 'Other Fine Arts'],
    'Religion': ['Religion'],
    'Mythology': ['Mythology'],
    'Philosophy': ['Philosophy'],
    'Social Science': ['Social Science'],
    'Current Events': ['Current Events'],
    'Geography': ['Geography'],
    'Other Academic': ['Other Academic'],
    'Pop Culture': ['Movies', 'Music', 'Sports', 'Television',
                    'Video Games', 'Other Pop Culture'],
}
CATEGORY_TO_ALTERNATE_SUBCATEGORIES = {
    'Literature': ['Drama', 'Long Fiction', 'Poetry', 'Short Fiction',
                   'Misc Literature'],
    'Science': ['Math', 'Astronomy', 'Computer Science', 'Earth Science',
                'Engineering', 'Misc Science'],
    'Fine Arts': ['Architecture', 'Dance', 'Film', 'Jazz', 'Musicals',
                  'Opera', 'Photography', 'Misc Arts'],
    'Social Science': ['Anthropology', 'Economics', 'Linguistics',
                       'Psychology', 'Sociology', 'Other Social Science'],
}
SUBCATEGORY_TO_CATEGORY = {sub: cat
                           for cat, subs in CATEGORY_TO_SUBCATEGORY.items()
                           for sub in subs}
ALTERNATE_SUBCATEGORY_TO_CATEGORY = {
    alt: cat
    for cat, alts in CATEGORY_TO_ALTERNATE_SUBCATEGORIES.items()
    for alt in alts}
CATEGORIES = list(CATEGORY_TO_SUBCATEGORY)
SUBCATEGORIES = list(SUBCATEGORY_TO_CATEGORY)
ALTERNATE_SUBCATEGORIES = list(ALTERNATE_SUBCATEGORY_TO_CATEGORY)


def unformat_string(s: str) -> str:
    s = unicodedata.normalize('NFD', s)
    s = re.sub(r'[̀-ͯ]', '', s)
    s = re.sub(r'[‐-―]', '-', s)
    s = re.sub(r'[‘-‛]', "'", s)
    s = re.sub(r'[“-‟]', '"', s)
    s = s.replace('…', '...')
    s = re.sub(r'[′-‷]', "'", s)
    s = re.sub(r'[·⋅‧]', '', s)
    return s.replace('ł', 'l').replace('ø', 'o')


def escape_regexp(s: str) -> str:
    return re.sub(r'[.*+?^${}()|[\]\\]', r'\\\g<0>', s)


def _expand_category_bundle(categories, subcategories, alternate_subcategories):
    """category-bundle.js: validate against the taxonomy and make the
    three lists mutually consistent. Returns None (no filtering) when
    nothing was requested."""
    cats = [c for c in (categories or []) if c in CATEGORIES]
    subs = [s for s in (subcategories or []) if s in SUBCATEGORIES]
    alts = [a for a in (alternate_subcategories or [])
            if a in ALTERNATE_SUBCATEGORIES]

    if not cats and not subs and not alts:
        return None

    for sub in subs:
        cat = SUBCATEGORY_TO_CATEGORY[sub]
        if cat not in cats:
            cats.append(cat)
    for alt in alts:
        cat = ALTERNATE_SUBCATEGORY_TO_CATEGORY[alt]
        if cat not in cats:
            cats.append(cat)
    for cat in cats:
        if not any(s in subs for s in CATEGORY_TO_SUBCATEGORY[cat]):
            subs.extend(CATEGORY_TO_SUBCATEGORY[cat])
    for cat in cats:
        cat_alts = CATEGORY_TO_ALTERNATE_SUBCATEGORIES.get(cat, [])
        if not any(a in alts for a in cat_alts):
            alts.extend(cat_alts)
    return cats, subs, alts


def _build_where(difficulties, bundle, min_year, max_year, set_name):
    """SQL prefilter for everything except the text search."""
    clauses, params = [], []
    if difficulties:
        clauses.append(f"difficulty IN ({','.join('?' * len(difficulties))})")
        params.extend(difficulties)
    if bundle:
        cats, subs, alts = bundle
        clauses.append(f"category IN ({','.join('?' * len(cats))})")
        params.extend(cats)
        clauses.append(f"subcategory IN ({','.join('?' * len(subs))})")
        params.extend(subs)
        # get-query.js appends null: unset alternate_subcategory matches.
        alt_in = f"alternate_subcategory IN ({','.join('?' * len(alts))})" \
            if alts else "0"
        clauses.append(f"({alt_in} OR alternate_subcategory IS NULL)")
        params.extend(alts)
    if min_year is not None:
        clauses.append("set_year >= ?")
        params.append(min_year)
    if max_year is not None:
        clauses.append("set_year <= ?")
        params.append(max_year)
    if set_name:
        names = set_name if isinstance(set_name, list) else [set_name]
        ors = []
        for name in names:
            ors.append("instr(lower(set_name), lower(?)) > 0")
            params.append(name)
        clauses.append("(" + " OR ".join(ors) + ")")
    return (" AND ".join(clauses) or "1"), params


def _compile_words(query_string, exact_phrase, ignore_word_order,
                   case_sensitive, regex):
    """get-query.js validateOptions: returns (processed_query_string,
    [compiled regex per word]); every word must match (AND)."""
    query_string = query_string or ''
    if not regex:
        query_string = unformat_string(query_string.strip())
        query_string = escape_regexp(query_string)
    else:
        exact_phrase = ignore_word_order = False

    if ignore_word_order:
        words = [w for w in query_string.split(' ') if w]
    else:
        words = [query_string]
    if exact_phrase and not regex:
        query_string = rf'\b{query_string}\b'
        words = [rf'\b{w}\b' for w in words]

    flags = 0 if case_sensitive else re.IGNORECASE
    return query_string, [re.compile(w, flags) for w in words]


def _matches(patterns, texts):
    """Every pattern must match at least one of the texts (Mongo $and of
    $or; regex on an array field matches if any element matches)."""
    return all(any(p.search(t) for t in texts if t) for p in patterns)


def _mongo_sort_key(row):
    # set.name DESC, packet.number ASC, number ASC; Mongo sorts null
    # before numbers ascending.
    def null_first(v):
        return (v is not None, v if v is not None else 0)
    return (_Desc(row['set_name']), null_first(row['packet_number']),
            null_first(row['number']))


class _Desc(str):
    def __lt__(self, other):
        return str.__gt__(self, other)


class _Catalog:
    """Cached set/packet lookups for rebuilding API-shaped docs."""

    def __init__(self, conn):
        self.sets = {r['id']: r for r in
                     conn.execute("SELECT * FROM sets").fetchall()}
        self.packet_names = {r['id']: r['name'] for r in
                             conn.execute("SELECT id, name FROM packets")}

    def set_doc(self, row):
        s = self.sets.get(row['set_id'])
        doc = {'_id': row['set_id'], 'name': row['set_name']}
        if row['set_year'] is not None:
            doc['year'] = row['set_year']
        if s is not None:
            doc['standard'] = bool(s['standard'])
        return doc

    def packet_doc(self, row):
        if row['packet_id'] is None:
            return None
        doc = {'_id': row['packet_id']}
        name = self.packet_names.get(row['packet_id'])
        if name is not None:
            doc['name'] = name
        if row['packet_number'] is not None:
            doc['number'] = row['packet_number']
        return doc


def _base_doc(row, catalog):
    doc = {'_id': row['id']}
    for col in ('category', 'subcategory', 'alternate_subcategory',
                'number', 'difficulty'):
        if row[col] is not None:
            doc[col] = row[col]
    packet = catalog.packet_doc(row)
    if packet:
        doc['packet'] = packet
    doc['set'] = catalog.set_doc(row)
    if row['updated_at'] is not None:
        doc['updatedAt'] = row['updated_at']
    if row['extra']:
        extra = json.loads(row['extra'])
        extra.pop('reports', None)  # get-query.js: $project {reports: 0}
        doc.update(extra)
    return doc


def _tossup_doc(row, catalog):
    doc = _base_doc(row, catalog)
    for col in ('question', 'question_sanitized', 'answer', 'answer_sanitized'):
        if row[col] is not None:
            doc[col] = row[col]
    return doc


def _bonus_doc(row, catalog):
    doc = _base_doc(row, catalog)
    for col in ('leadin', 'leadin_sanitized'):
        if row[col] is not None:
            doc[col] = row[col]
    for col, key in (('parts', 'parts'), ('parts_sanitized', 'parts_sanitized'),
                     ('answers', 'answers'),
                     ('answers_sanitized', 'answers_sanitized'),
                     ('values', 'values'),
                     ('difficulty_modifiers', 'difficultyModifiers')):
        if row[col] is not None:
            doc[key] = json.loads(row[col])
    return doc


def query(query_string='', search_type='all', question_type='all',
          difficulties=None, categories=None, subcategories=None,
          alternate_subcategories=None, set_name=None,
          min_year=None, max_year=None,
          max_return_length=DEFAULT_QUERY_RETURN_LENGTH,
          exact_phrase=False, ignore_word_order=False, case_sensitive=False,
          regex=False, powermark_only=False,
          tossup_pagination=1, bonus_pagination=1, conn=None) -> dict:
    """Local /api/query. Returns the API response shape:
    {tossups: {count, questionArray}, bonuses: {...}, queryString}."""
    if search_type not in ('question', 'answer', 'exactAnswer', 'all'):
        raise ValueError('Invalid search type specified.')
    if question_type not in ('tossup', 'bonus', 'all'):
        raise ValueError('Invalid question type specified.')
    max_return_length = min(max_return_length, MAX_QUERY_RETURN_LENGTH)
    if max_return_length <= 0:
        max_return_length = DEFAULT_QUERY_RETURN_LENGTH

    processed, patterns = _compile_words(
        query_string, exact_phrase, ignore_word_order, case_sensitive, regex)
    has_text_query = processed != ''

    bundle = _expand_category_bundle(categories, subcategories,
                                     alternate_subcategories)
    where, params = _build_where(difficulties, bundle, min_year, max_year,
                                 set_name)
    if powermark_only:
        where += " AND question_sanitized LIKE '%(*)%'"

    own_conn = conn is None
    if own_conn:
        conn = mirror_db.open_db()
    try:
        catalog = _Catalog(conn)
        result = {'queryString': processed}

        def run(table, texts_for, doc_for, pagination):
            rows = conn.execute(
                f"SELECT * FROM {table} WHERE {where}", params).fetchall()
            if has_text_query:
                rows = [r for r in rows if _matches(patterns, texts_for(r))]
            rows.sort(key=_mongo_sort_key)
            start = (max(pagination, 1) - 1) * max_return_length
            page = rows[start:start + max_return_length]
            return {'count': len(rows),
                    'questionArray': [doc_for(r, catalog) for r in page]}

        def tossup_texts(r):
            texts = []
            if search_type in ('question', 'all'):
                texts.append(r['question_sanitized'])
            if search_type in ('answer', 'exactAnswer', 'all'):
                texts.append(r['answer_sanitized'])
            return texts

        def bonus_texts(r):
            texts = []
            if search_type in ('question', 'all'):
                texts.append(r['leadin_sanitized'])
                texts.extend(json.loads(r['parts_sanitized'] or '[]'))
            if search_type in ('answer', 'exactAnswer', 'all'):
                texts.extend(json.loads(r['answers_sanitized'] or '[]'))
            return texts

        if search_type == 'exactAnswer':
            flags = 0 if case_sensitive else re.IGNORECASE
            patterns = [re.compile(rf'^\s*{w.pattern}\s*(\[.*|\(.*)?$', flags)
                        for w in patterns]

        if question_type in ('tossup', 'all'):
            result['tossups'] = run('tossups', tossup_texts, _tossup_doc,
                                    tossup_pagination)
        else:
            result['tossups'] = {'count': 0, 'questionArray': []}
        if question_type in ('bonus', 'all'):
            # powermark_only references question_sanitized, which bonuses
            # lack — the live API errors similarly; keep it tossup-only.
            if powermark_only:
                result['bonuses'] = {'count': 0, 'questionArray': []}
            else:
                result['bonuses'] = run('bonuses', bonus_texts, _bonus_doc,
                                        bonus_pagination)
        else:
            result['bonuses'] = {'count': 0, 'questionArray': []}
        return result
    finally:
        if own_conn:
            conn.close()


_FREQ_PREFIX = re.compile(r'^[^[(]*')
_FREQ_OUTSIDE_PARENS = re.compile(r'[^()]+(?![^(]*\))')


def _normalize_freq_answer(answer_sanitized: str):
    """get-frequency-list.js normalization: text before the first '('
    or '[', trimmed; display form + lowercase de-hyphenated group key.
    Returns (answer, answer_normalized) or None when it degenerates."""
    if answer_sanitized is None:
        return None
    prefix = _FREQ_PREFIX.match(answer_sanitized).group(0)
    m = _FREQ_OUTSIDE_PARENS.search(prefix)
    if m is None:
        return None
    answer = m.group(0).strip()
    normalized = answer.replace('-', ' ').lower()
    if not normalized:
        return None
    return answer, normalized


def frequency_list(category=None, subcategory=None, alternate_subcategory=None,
                   difficulties=None, limit=None, min_year=None, max_year=None,
                   question_type='all', conn=None) -> list[dict]:
    """Local /api/frequency-list. Returns
    [{answer, answer_normalized, count}] sorted by count desc."""
    if not category and not subcategory and not alternate_subcategory:
        return []
    if question_type not in ('tossup', 'bonus', 'all'):
        raise ValueError('Invalid question type')

    clauses, params = [], []
    if difficulties:
        clauses.append(f"difficulty IN ({','.join('?' * len(difficulties))})")
        params.extend(difficulties)
    for col, val in (('category', category), ('subcategory', subcategory),
                     ('alternate_subcategory', alternate_subcategory)):
        if val:
            clauses.append(f"{col} = ?")
            params.append(val)
    if min_year is not None:
        clauses.append("set_year >= ?")
        params.append(min_year)
    if max_year is not None:
        clauses.append("set_year <= ?")
        params.append(max_year)
    where = " AND ".join(clauses) or "1"

    own_conn = conn is None
    if own_conn:
        conn = mirror_db.open_db()
    try:
        def tally(table, answers_of):
            groups = {}
            for row in conn.execute(
                    f"SELECT * FROM {table} WHERE {where} ORDER BY rowid",
                    params):
                for ans in answers_of(row):
                    norm = _normalize_freq_answer(ans)
                    if norm is None:
                        continue
                    answer, key = norm
                    entry = groups.setdefault(
                        key, {'answer': answer, 'answer_normalized': key,
                              'count': 0})
                    entry['count'] += 1
            return groups

        groups = {}
        if question_type in ('tossup', 'all'):
            groups = tally('tossups', lambda r: [r['answer_sanitized']])
        if question_type in ('bonus', 'all'):
            for key, entry in tally(
                    'bonuses',
                    lambda r: json.loads(r['answers_sanitized'] or '[]')
            ).items():
                if key in groups:
                    groups[key]['count'] += entry['count']
                else:
                    groups[key] = entry
    finally:
        if own_conn:
            conn.close()

    # Merge order is answer_normalized asc, then a stable sort by count
    # desc — matches the JS merge + Array.sort.
    merged = [groups[k] for k in sorted(groups)]
    merged.sort(key=lambda e: -e['count'])
    if limit:
        del merged[limit:]
    return merged


def set_list(conn=None) -> list[str]:
    """Local /api/set-list: names sorted year desc, name asc."""
    own_conn = conn is None
    if own_conn:
        conn = mirror_db.open_db()
    try:
        rows = conn.execute(
            "SELECT name FROM sets "
            "ORDER BY year DESC, name ASC").fetchall()
        return [r['name'] for r in rows]
    finally:
        if own_conn:
            conn.close()


def num_packets(set_name: str, conn=None) -> int:
    own_conn = conn is None
    if own_conn:
        conn = mirror_db.open_db()
    try:
        row = conn.execute(
            "SELECT COUNT(*) AS n FROM packets WHERE set_name = ?",
            (set_name,)).fetchone()
        return row['n']
    finally:
        if own_conn:
            conn.close()


def set_payload(set_name: str, conn, catalog=None) -> dict:
    """Whole set as one nested structure (the reader's per-set artifact):
    {name, year, difficulty, standard, packets: [{number, name, tossups,
    bonuses}]} with API-shaped question docs."""
    catalog = catalog or _Catalog(conn)
    srow = conn.execute("SELECT * FROM sets WHERE name = ?",
                        (set_name,)).fetchone()
    if srow is None:
        raise KeyError(f"set not in mirror: {set_name!r}")

    packets = {}
    for prow in conn.execute(
            "SELECT * FROM packets WHERE set_id = ? ORDER BY number",
            (srow["id"],)):
        packets[prow["number"]] = {"number": prow["number"],
                                   "name": prow["name"],
                                   "tossups": [], "bonuses": []}
    for table, doc_for, key in (("tossups", _tossup_doc, "tossups"),
                                ("bonuses", _bonus_doc, "bonuses")):
        for row in conn.execute(
                f"SELECT * FROM {table} WHERE set_id = ? "
                f"ORDER BY packet_number, number", (srow["id"],)):
            packets.setdefault(row["packet_number"],
                               {"number": row["packet_number"], "name": None,
                                "tossups": [], "bonuses": []}
                               )[key].append(doc_for(row, catalog))

    return {
        "name": srow["name"],
        "year": srow["year"],
        "difficulty": srow["difficulty"],
        "standard": bool(srow["standard"]),
        "packets": [packets[n] for n in sorted(packets)],
    }


def packet(set_name: str, packet_number: int, conn=None) -> dict:
    """Local /api/packet: {tossups, bonuses} for one packet, in question
    order."""
    own_conn = conn is None
    if own_conn:
        conn = mirror_db.open_db()
    try:
        catalog = _Catalog(conn)
        out = {}
        for table, doc_for, key in (('tossups', _tossup_doc, 'tossups'),
                                    ('bonuses', _bonus_doc, 'bonuses')):
            rows = conn.execute(
                f"SELECT * FROM {table} WHERE set_name = ? "
                f"AND packet_number = ? ORDER BY number",
                (set_name, packet_number)).fetchall()
            out[key] = [doc_for(r, catalog) for r in rows]
        return out
    finally:
        if own_conn:
            conn.close()
