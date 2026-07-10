"""
fetch.py — Data collection from qbreader API.

Queries the qbreader database for a topic and caches results locally as JSON.
Uses the raw REST API instead of the Python wrapper (which has enum bugs).

Default behavior: single page (25 results), year >= 2012.
"""

import json
import re
import time
from pathlib import Path

import requests

API_BASE = "https://www.qbreader.org/api"
RATE_LIMIT = 20  # max requests per second
DEFAULT_CACHE_DIR = Path("cache")
DEFAULT_MIN_YEAR = 2012
# qbreader returns at most maxReturnLength results with no pagination.
# 500 covers the biggest canon topics (Beethoven: 107 tossups / 111
# bonuses at diff 7-10); the old default of 25 silently truncated them.
DEFAULT_MAX_RESULTS = 500

# Minimum interval between requests to stay under rate limit.
MIN_INTERVAL = 1.0 / RATE_LIMIT + 0.01

_last_request_time = 0.0


def _rate_limited_get(url: str, params: dict, max_retries: int = 5) -> requests.Response:
    """Make a GET request, respecting the rate limit. Retries on 503 with backoff."""
    global _last_request_time
    for attempt in range(max_retries):
        elapsed = time.time() - _last_request_time
        if elapsed < MIN_INTERVAL:
            time.sleep(MIN_INTERVAL - elapsed)
        _last_request_time = time.time()
        resp = requests.get(url, params=params)
        if resp.status_code == 503 and attempt < max_retries - 1:
            wait = 2 ** attempt * 5  # 5, 10, 20, 40, 80 seconds
            print(f"    503 error, retrying in {wait}s (attempt {attempt + 1}/{max_retries})...")
            time.sleep(wait)
            continue
        resp.raise_for_status()
        return resp


def _is_truncated(matches: dict) -> bool:
    """True if a cached result holds fewer questions than qbreader reported.
    Detects caches written before the 25-result cap was lifted."""
    if not matches:
        return True
    return (len(matches.get('tossups', [])) < matches.get('tossups_found', 0)
            or len(matches.get('bonuses', [])) < matches.get('bonuses_found', 0))


def _sanitize_filename(name: str) -> str:
    """Convert a query string into a safe filename."""
    return re.sub(r'[^\w\-]', '_', name.strip().lower())


def _cache_key(query_string: str, difficulties: list[int] | None,
               min_year: int, categories: list[str] | None = None) -> str:
    """Build a unique cache filename incorporating filter params."""
    safe = _sanitize_filename(query_string)
    parts = [safe]
    if difficulties:
        parts.append(f"d{'_'.join(str(d) for d in sorted(difficulties))}")
    if categories:
        parts.append(f"c{'_'.join(_sanitize_filename(c) for c in sorted(categories))}")
    parts.append(f"y{min_year}")
    return "_".join(parts)


def query_page(
    query_string: str,
    search_type: str = "answer",
    difficulties: list[int] | None = None,
    categories: list[str] | None = None,
    min_year: int = DEFAULT_MIN_YEAR,
    max_results: int = DEFAULT_MAX_RESULTS,
) -> dict:
    """
    Fetch a single page of results from qbreader.

    Returns raw API response dict with tossups and bonuses.
    """
    params = {
        "queryString": query_string,
        "searchType": search_type,
        "maxReturnLength": max_results,
        "minYear": min_year,
    }
    if difficulties:
        params["difficulties"] = ",".join(str(d) for d in difficulties)
    if categories:
        params["categories"] = ",".join(categories)

    print(f"  Fetching '{query_string}' (type={search_type}, "
          f"diff={difficulties}, year>={min_year})...")
    resp = _rate_limited_get(f"{API_BASE}/query", params)
    data = resp.json()

    tossups = data["tossups"]["questionArray"]
    bonuses = data["bonuses"]["questionArray"]
    print(f"    Got {len(tossups)} tossups (of {data['tossups']['count']}), "
          f"{len(bonuses)} bonuses (of {data['bonuses']['count']})")
    if (len(tossups) < data['tossups']['count']
            or len(bonuses) < data['bonuses']['count']):
        print(f"    WARNING: results truncated at maxReturnLength={max_results} "
              f"— raise DEFAULT_MAX_RESULTS in fetch.py")

    return {
        "tossups": tossups,
        "bonuses": bonuses,
        "tossups_found": data["tossups"]["count"],
        "bonuses_found": data["bonuses"]["count"],
    }


def fetch_topic(
    query_string: str,
    difficulties: list[int] | None = None,
    categories: list[str] | None = None,
    min_year: int = DEFAULT_MIN_YEAR,
    use_cache: bool = True,
    cache_dir: Path | None = None,
) -> dict:
    """
    Fetch answerline matches for a topic (single page).
    Results are cached locally.

    Returns dict with:
        - query_string, difficulties, min_year
        - answer_matches: {tossups, bonuses, tossups_found, bonuses_found}
    """
    cache_dir = Path(cache_dir) if cache_dir else DEFAULT_CACHE_DIR
    key = _cache_key(query_string, difficulties, min_year, categories)
    cache_path = cache_dir / f"{key}.json"

    if use_cache and cache_path.exists():
        with open(cache_path, encoding='utf-8') as f:
            cached = json.load(f)
        if not _is_truncated(cached.get('answer_matches', {})):
            print(f"Loading cached data from {cache_path}")
            return cached
        print(f"Cached data at {cache_path} was truncated (old 25-result cap) — refetching")

    print(f"Fetching topic: '{query_string}'")

    answer_data = query_page(
        query_string,
        search_type="answer",
        difficulties=difficulties,
        categories=categories,
        min_year=min_year,
    )

    result = {
        "query_string": query_string,
        "difficulties": difficulties,
        "min_year": min_year,
        "answer_matches": answer_data,
    }

    cache_dir.mkdir(parents=True, exist_ok=True)
    with open(cache_path, "w", encoding='utf-8') as f:
        json.dump(result, f, indent=2)
    print(f"Cached to {cache_path}")

    return result


def fetch_text_mentions(
    query_string: str,
    difficulties: list[int] | None = None,
    categories: list[str] | None = None,
    min_year: int = DEFAULT_MIN_YEAR,
    use_cache: bool = True,
    cache_dir: Path | None = None,
) -> dict:
    """
    Fetch questions where the topic appears in the text (but may not be
    the answer). Kept separate so we only call this when needed.
    """
    cache_dir = Path(cache_dir) if cache_dir else DEFAULT_CACHE_DIR
    key = _cache_key(query_string, difficulties, min_year, categories) + "_mentions"
    cache_path = cache_dir / f"{key}.json"

    if use_cache and cache_path.exists():
        with open(cache_path, encoding='utf-8') as f:
            cached = json.load(f)
        if not _is_truncated(cached.get('text_mentions', {})):
            print(f"Loading cached mentions from {cache_path}")
            return cached
        print(f"Cached mentions at {cache_path} were truncated (old 25-result cap) — refetching")

    print(f"Fetching text mentions: '{query_string}'")

    question_data = query_page(
        query_string,
        search_type="question",
        difficulties=difficulties,
        categories=categories,
        min_year=min_year,
    )

    result = {
        "query_string": query_string,
        "difficulties": difficulties,
        "min_year": min_year,
        "text_mentions": question_data,
    }

    cache_dir.mkdir(parents=True, exist_ok=True)
    with open(cache_path, "w", encoding='utf-8') as f:
        json.dump(result, f, indent=2)
    print(f"Cached to {cache_path}")

    return result


if __name__ == "__main__":
    import sys

    topic = sys.argv[1] if len(sys.argv) > 1 else "Beethoven"
    diffs = [int(d) for d in sys.argv[2].split(",")] if len(sys.argv) > 2 else None
    data = fetch_topic(topic, difficulties=diffs)
    print(f"\nResults for '{topic}':")
    print(f"  Answerline: "
          f"{data['answer_matches']['tossups_found']} tossups, "
          f"{data['answer_matches']['bonuses_found']} bonuses")
