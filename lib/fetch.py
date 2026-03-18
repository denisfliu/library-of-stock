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
CACHE_DIR = Path("cache")
DEFAULT_MIN_YEAR = 2012

# Minimum interval between requests to stay under rate limit.
MIN_INTERVAL = 1.0 / RATE_LIMIT + 0.01

_last_request_time = 0.0


def _rate_limited_get(url: str, params: dict) -> requests.Response:
    """Make a GET request, respecting the rate limit."""
    global _last_request_time
    elapsed = time.time() - _last_request_time
    if elapsed < MIN_INTERVAL:
        time.sleep(MIN_INTERVAL - elapsed)
    _last_request_time = time.time()
    resp = requests.get(url, params=params)
    resp.raise_for_status()
    return resp


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
    max_results: int = 25,
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
) -> dict:
    """
    Fetch answerline matches for a topic (single page).
    Results are cached locally.

    Returns dict with:
        - query_string, difficulties, min_year
        - answer_matches: {tossups, bonuses, tossups_found, bonuses_found}
    """
    key = _cache_key(query_string, difficulties, min_year, categories)
    cache_path = CACHE_DIR / f"{key}.json"

    if use_cache and cache_path.exists():
        print(f"Loading cached data from {cache_path}")
        with open(cache_path) as f:
            return json.load(f)

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

    CACHE_DIR.mkdir(exist_ok=True)
    with open(cache_path, "w") as f:
        json.dump(result, f, indent=2)
    print(f"Cached to {cache_path}")

    return result


def fetch_text_mentions(
    query_string: str,
    difficulties: list[int] | None = None,
    categories: list[str] | None = None,
    min_year: int = DEFAULT_MIN_YEAR,
    use_cache: bool = True,
) -> dict:
    """
    Fetch questions where the topic appears in the text (but may not be
    the answer). Kept separate so we only call this when needed.
    """
    key = _cache_key(query_string, difficulties, min_year, categories) + "_mentions"
    cache_path = CACHE_DIR / f"{key}.json"

    if use_cache and cache_path.exists():
        print(f"Loading cached mentions from {cache_path}")
        with open(cache_path) as f:
            return json.load(f)

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

    CACHE_DIR.mkdir(exist_ok=True)
    with open(cache_path, "w") as f:
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
