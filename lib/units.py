"""units.py — Canonical registry of category "units".

A unit is the smallest category slice the site builds an overview page
for, and equals what qbreader's /api/frequency-list can address: a
subcategory, or an alternate_subcategory ("genre") where the canonical
taxonomy in categories.md defines one (Other Fine Arts, Other Science,
Social Science).

Also home to the drift-reconciliation map: existing analysis.json files
carry non-canonical subcategory/genre values (Philosophy period names,
"Canadian Literature", AFA period genres). ``unit_for_guide`` is the
single place those get normalized — renderers and matchers must classify
guides through it rather than reading raw subcategory strings.
"""
from dataclasses import dataclass, field


@dataclass(frozen=True)
class Unit:
    slug: str          # directory name under output/_categories/
    title: str
    category: str      # canonical categories.md category
    subcategory: str   # canonical parent subcategory ("Other Fine Arts" for genre units)
    genre: str         # "" except for genre-level units ("Film", "Math", "Psychology")
    freq_params: dict = field(hash=False)  # exact /api/frequency-list filter params


def _sub(title, category, subcategory=None):
    subcategory = subcategory or title
    return Unit(
        slug=title.lower().replace(' ', '_'),
        title=title, category=category, subcategory=subcategory, genre='',
        freq_params={'subcategory': subcategory},
    )


def _genre(genre, category, subcategory):
    return Unit(
        slug=genre.lower().replace(' ', '_'),
        title=genre, category=category, subcategory=subcategory, genre=genre,
        freq_params={'subcategory': subcategory, 'alternateSubcategory': genre},
    )


UNITS: list[Unit] = [
    # Literature
    _sub('American Literature', 'Literature'),
    _sub('British Literature', 'Literature'),
    _sub('Classical Literature', 'Literature'),
    _sub('European Literature', 'Literature'),
    _sub('World Literature', 'Literature'),
    _sub('Other Literature', 'Literature'),
    # History
    _sub('American History', 'History'),
    _sub('Ancient History', 'History'),
    _sub('European History', 'History'),
    _sub('World History', 'History'),
    _sub('Other History', 'History'),
    # Science
    _sub('Biology', 'Science'),
    _sub('Chemistry', 'Science'),
    _sub('Physics', 'Science'),
    _genre('Math', 'Science', 'Other Science'),
    _genre('Astronomy', 'Science', 'Other Science'),
    _genre('Computer Science', 'Science', 'Other Science'),
    _genre('Earth Science', 'Science', 'Other Science'),
    _genre('Engineering', 'Science', 'Other Science'),
    _genre('Misc Science', 'Science', 'Other Science'),
    # Fine Arts
    _sub('Visual Fine Arts', 'Fine Arts'),
    _sub('Auditory Fine Arts', 'Fine Arts'),
    _genre('Architecture', 'Fine Arts', 'Other Fine Arts'),
    _genre('Dance', 'Fine Arts', 'Other Fine Arts'),
    _genre('Film', 'Fine Arts', 'Other Fine Arts'),
    _genre('Jazz', 'Fine Arts', 'Other Fine Arts'),
    _genre('Musicals', 'Fine Arts', 'Other Fine Arts'),
    _genre('Opera', 'Fine Arts', 'Other Fine Arts'),
    _genre('Photography', 'Fine Arts', 'Other Fine Arts'),
    _genre('Misc Arts', 'Fine Arts', 'Other Fine Arts'),
    # Social Science (alternate_subcategory level)
    _genre('Psychology', 'Social Science', 'Social Science'),
    _genre('Anthropology', 'Social Science', 'Social Science'),
    _genre('Economics', 'Social Science', 'Social Science'),
    _genre('Linguistics', 'Social Science', 'Social Science'),
    _genre('Sociology', 'Social Science', 'Social Science'),
    _genre('Other Social Science', 'Social Science', 'Social Science'),
    # Single-subcategory categories
    _sub('Religion', 'Religion'),
    _sub('Mythology', 'Mythology'),
    _sub('Philosophy', 'Philosophy'),
    _sub('Geography', 'Geography'),
    # Current Events / Other Academic / Pop Culture deliberately deferred:
    # no corpus presence yet. Add here when the first topics land.
]

UNITS_BY_SLUG: dict[str, Unit] = {u.slug: u for u in UNITS}

# Categories where every guide maps to the single unit no matter what the
# (frequently drifted) subcategory field says.
_SINGLE_UNIT_CATEGORIES = {
    'Philosophy': 'philosophy',
    'Religion': 'religion',
    'Mythology': 'mythology',
    'Geography': 'geography',
}

# Observed drifted subcategory values -> unit slug (None = unresolvable
# without re-checking the source questions; leave unclassified).
# Keyed by (category, subcategory). See the corpus census in the
# category-pages push plan; shrink this map as M5 data cleanup lands.
SUBCATEGORY_ALIASES: dict[tuple[str, str], str | None] = {
    ('Fine Arts', 'Music'): 'auditory_fine_arts',
    # TODO(M3): verify against qbreader — Canadian lit may classify as
    # American or Other in the live data.
    ('Literature', 'Canadian Literature'): 'world_literature',
    # Form-level values (alternate_subcategory leaked into subcategory);
    # the real regional subcategory is unrecoverable without refetching.
    ('Literature', 'Drama'): None,
    ('Literature', 'Poetry'): None,
}

# AFA guides misuse genre for period/tradition; two of those values are
# really Other Fine Arts units.
_AFA_GENRE_UNITS = {'Opera': 'opera', 'Jazz': 'jazz'}


def unit_for_slug(slug: str) -> Unit | None:
    return UNITS_BY_SLUG.get(slug)


def unit_for_guide(category: str, subcategory: str, genre: str = '') -> Unit | None:
    """Map a guide's (possibly drifted) metadata to its canonical Unit.

    Returns None when the metadata is too broken to classify — callers
    should fall back to raw values rather than guessing.
    """
    category = (category or '').strip()
    subcategory = (subcategory or '').strip()
    genre = (genre or '').strip()

    single = _SINGLE_UNIT_CATEGORIES.get(category)
    if single:
        return UNITS_BY_SLUG[single]

    if (category, subcategory) in SUBCATEGORY_ALIASES:
        slug = SUBCATEGORY_ALIASES[(category, subcategory)]
        return UNITS_BY_SLUG[slug] if slug else None

    if category == 'Fine Arts':
        if subcategory == 'Visual Fine Arts':
            # A few VFA guides carry genre="Architecture" — that's an OFA unit.
            if genre == 'Architecture':
                return UNITS_BY_SLUG['architecture']
            return UNITS_BY_SLUG['visual_fine_arts']
        if subcategory == 'Auditory Fine Arts':
            unit = _AFA_GENRE_UNITS.get(genre)
            if unit:
                return UNITS_BY_SLUG[unit]
            # Other AFA genre values (Baroque, Classical, Romantic, ...)
            # are period drift, not units.
            return UNITS_BY_SLUG['auditory_fine_arts']
        if subcategory == 'Other Fine Arts':
            unit = _match_genre_unit('Fine Arts', 'Other Fine Arts', genre)
            return unit or UNITS_BY_SLUG['misc_arts']
        return None

    if category == 'Science':
        if subcategory in ('Biology', 'Chemistry', 'Physics'):
            return UNITS_BY_SLUG[subcategory.lower()]
        if subcategory == 'Other Science':
            unit = _match_genre_unit('Science', 'Other Science', genre)
            return unit or UNITS_BY_SLUG['misc_science']
        return None

    if category == 'Social Science':
        unit = _match_genre_unit('Social Science', 'Social Science', genre)
        return unit or UNITS_BY_SLUG['other_social_science']

    # Literature / History: canonical subcategory names map directly.
    for u in UNITS:
        if u.category == category and u.subcategory == subcategory and not u.genre:
            return u
    return None


def _match_genre_unit(category: str, subcategory: str, genre: str) -> Unit | None:
    for u in UNITS:
        if u.category == category and u.subcategory == subcategory and u.genre == genre:
            return u
    return None


if __name__ == '__main__':
    for u in UNITS:
        print(f'{u.slug:24s} {u.category} > {u.subcategory}'
              + (f' > {u.genre}' if u.genre else ''))
    print(f'{len(UNITS)} units')
