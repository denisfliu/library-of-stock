"""common.py — Shared paths and helpers for the stock pipeline.

Every script should resolve paths through these constants instead of
hand-rolling ``Path(__file__).parent.parent...`` chains or cwd-relative
paths. ``file_lock`` is the portable (Windows + POSIX) replacement for
the old ``fcntl.flock`` usage.
"""
import os
import sys
from pathlib import Path

from filelock import FileLock

# Windows consoles default to cp1252, which crashes print() on accented
# topic names (e.g. "Chénier"). Every entry script imports this module,
# so force UTF-8 stdio once here.
for _stream in (sys.stdout, sys.stderr):
    if _stream is not None and hasattr(_stream, 'reconfigure'):
        _stream.reconfigure(encoding='utf-8', errors='replace')

# STOCK_ROOT points the whole pipeline at an alternate tree; the golden
# render test (tests/golden/) uses it to run renderers against a fixture
# corpus in a sandbox. Unset (the normal case) means the repo root.
ROOT = Path(os.environ.get('STOCK_ROOT') or Path(__file__).resolve().parent.parent).resolve()
OUTPUT_DIR = ROOT / 'output'
QUEUE_DIR = ROOT / 'queue'
CACHE_DIR = ROOT / 'cache'
MIRROR_DIR = ROOT / 'mirror'
DEV_DIR = ROOT / 'dev'
TOPIC_INDEX_FILE = OUTPUT_DIR / 'topic_index.json'
# Non-topic namespaces under output/. The leading underscore keeps them
# disjoint from topic slugs (topic_slug never emits one) and out of the
# depth-1 */analysis.json and */stock.html globs.
CATEGORIES_DIR = OUTPUT_DIR / '_categories'
SETS_DIR = OUTPUT_DIR / '_sets'
OVERRIDES_FILE = OUTPUT_DIR / 'answerline_overrides.json'
CROSSREF_OVERRIDES_FILE = OUTPUT_DIR / 'crossref_overrides.json'

# Point the qb-mirror package (github.com/qbsuite/qb-mirror) at this
# repo's mirror + cache. setdefault so an explicit env override (or the
# golden test's STOCK_ROOT sandbox exporting its own) still wins; the
# values must be set before any qbmirror.db.open_db() with no path.
os.environ.setdefault('QBMIRROR_DB', str(MIRROR_DIR / 'qbreader.sqlite'))
os.environ.setdefault('QBMIRROR_CACHE', str(CACHE_DIR))


def file_lock(path: Path) -> FileLock:
    """Exclusive cross-process lock. Use as a context manager.

    Blocks until the lock is acquired. The lock file is created (with
    parents) if missing.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    return FileLock(str(path))


# Work-section names that are groupings rather than real works. Used when
# counting "real" works and when deciding which sections to skip in
# image lookup / crossref indexing.
SKIP_WORK_NAME_FRAGMENTS = ("General", "Biographical", "Other Works", "Other ")


def is_real_work(work: dict) -> bool:
    """True if a work section is an actual work, not a catch-all grouping."""
    name = work.get("name", "")
    return not any(fragment in name for fragment in SKIP_WORK_NAME_FRAGMENTS)


def anchor_slug(name: str) -> str:
    """Anchor id for a work section, as used in stock.html links."""
    import re
    return re.sub(r'[^a-z0-9]+', '-', name.lower()).strip('-')


def topic_slug(topic: str) -> str:
    """Directory slug for a topic: full canonical name, lowercased,
    spaces to underscores (accents preserved)."""
    return topic.strip().lower().replace(' ', '_')


def load_cards(slug: str) -> list:
    """Load a topic's cards from output/{slug}/cards.json ([] if absent).

    Cards live in their own file so agents that only need the analysis
    (second-pass, crossref) don't pay to read them, and card agents can't
    accidentally clobber analysis fields.
    """
    import json
    path = OUTPUT_DIR / slug / 'cards.json'
    if not path.exists():
        return []
    with open(path, encoding='utf-8') as f:
        return json.load(f)


def save_cards(slug: str, cards: list) -> None:
    """Write a topic's cards to output/{slug}/cards.json."""
    import json
    path = OUTPUT_DIR / slug / 'cards.json'
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(cards, f, indent=2, ensure_ascii=False)


def write_json_if_changed(path: Path, data) -> bool:
    """Write JSON only when the serialized content differs from what's
    on disk. Returns True if the file was written.

    Keeping mtimes stable when nothing changed matters: incremental
    renderers (e.g. build_overviews.py vs topic_index.json) and git
    status both key off it.
    """
    import json
    path = Path(path)
    text = json.dumps(data, indent=2, ensure_ascii=False)
    if path.exists():
        try:
            if path.read_text(encoding='utf-8') == text:
                return False
        except OSError:
            pass
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, 'w', encoding='utf-8') as f:
        f.write(text)
    return True


def iter_analyses(warn=True):
    """Yield (slug, json_path, data) for every output/*/analysis.json.

    Corrupt files are skipped with a warning instead of aborting the run.
    """
    import json
    for json_path in sorted(OUTPUT_DIR.glob('*/analysis.json')):
        try:
            with open(json_path, encoding='utf-8') as f:
                data = json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            if warn:
                print(f'WARNING: skipping {json_path}: {e}', file=sys.stderr)
            continue
        yield json_path.parent.name, json_path, data


def load_corpus():
    """Parse every analysis.json exactly once, for build.py.

    Returns (analyses, errors): analyses is [(slug, json_path, data)] and
    errors is [(json_path, message)] for files that failed to parse —
    validate.py turns those into [BROKEN JSON] issues.
    """
    import json
    analyses, errors = [], []
    for json_path in sorted(OUTPUT_DIR.glob('*/analysis.json')):
        try:
            with open(json_path, encoding='utf-8') as f:
                analyses.append((json_path.parent.name, json_path, json.load(f)))
        except (json.JSONDecodeError, OSError) as e:
            errors.append((json_path, str(e)))
    return analyses, errors


def resolve_analyses(analyses=None, warn=True):
    """Stage-function helper: return the given corpus, or load it.

    Every build stage takes ``analyses=None`` and calls this, so the stage
    works standalone (loads its own corpus) and under build.py (shares the
    single load) with the same code path.
    """
    return list(iter_analyses(warn=warn)) if analyses is None else analyses
