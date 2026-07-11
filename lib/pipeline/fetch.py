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
# Difficulty range for frequency lists and set sweeps: easy college (5)
# through nationals (10). Topic fetches keep passing difficulties
# explicitly from the queue entries.
DEFAULT_DIFFICULTIES = [5, 7, 8, 9, 10]
# qbreader's frequency-list default limit is 100, which truncates far
# above a frequency>=3 threshold on big subcategories (American Lit has
# 1313 answerlines at freq>=3). 5000 reaches frequency 1 there.
DEFAULT_FREQ_LIMIT = 5000

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


def _load_cache(cache_path: Path) -> dict | list | None:
    if cache_path.exists():
        with open(cache_path, encoding='utf-8') as f:
            return json.load(f)
    return None


def _write_cache(cache_path: Path, data) -> None:
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    with open(cache_path, "w", encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def fetch_frequency_list(
    freq_params: dict,
    difficulties: list[int] | None = None,
    limit: int = DEFAULT_FREQ_LIMIT,
    question_type: str = "all",
    min_year: int = DEFAULT_MIN_YEAR,
    max_year: int | None = None,
    use_cache: bool = True,
    cache_dir: Path | None = None,
) -> dict:
    """
    Fetch the most frequent answerlines for a category slice.

    freq_params holds the taxonomy filter exactly as the API expects it
    (some combination of category / subcategory / alternateSubcategory —
    at least one required; see lib/units.py Unit.freq_params).

    Returns dict with:
        - params: the full request parameters
        - fetched: ISO date of the API call
        - frequency_list: [{answer, frequency}, ...] sorted desc
    """
    if difficulties is None:
        difficulties = DEFAULT_DIFFICULTIES
    if not freq_params:
        raise ValueError("freq_params must set category, subcategory, "
                         "or alternateSubcategory")

    cache_dir = Path(cache_dir) if cache_dir else DEFAULT_CACHE_DIR / "frequency"
    key_base = "_".join(_sanitize_filename(v) for v in freq_params.values())
    key = _cache_key(key_base, difficulties, min_year)
    key += f"_q{question_type}_l{limit}"
    if max_year:
        key += f"_maxy{max_year}"
    cache_path = cache_dir / f"{key}.json"

    if use_cache:
        cached = _load_cache(cache_path)
        if cached and cached.get("frequency_list"):
            print(f"Loading cached frequency list from {cache_path}")
            return cached

    params = dict(freq_params)
    params["limit"] = limit
    params["questionType"] = question_type
    params["minYear"] = min_year
    if max_year:
        params["maxYear"] = max_year
    if difficulties:
        params["difficulties"] = ",".join(str(d) for d in difficulties)

    print(f"Fetching frequency list: {freq_params} "
          f"(diff={difficulties}, year>={min_year}, limit={limit})...")
    resp = _rate_limited_get(f"{API_BASE}/frequency-list", params)
    data = resp.json()
    raw_list = data.get("frequencyList", data if isinstance(data, list) else [])
    # Live API entries are {answer, answer_normalized, count} (docs say
    # {answer, frequency}); normalize to a stable internal shape.
    freq_list = [
        {
            "answer": e.get("answer", ""),
            "answer_normalized": e.get("answer_normalized", ""),
            "frequency": e.get("count", e.get("frequency", 0)),
        }
        for e in raw_list
    ]
    print(f"    Got {len(freq_list)} answerlines")
    if len(freq_list) >= limit:
        tail = freq_list[-1]["frequency"] if freq_list else "?"
        print(f"    WARNING: hit limit={limit} (tail frequency {tail}) — "
              f"raise the limit if the threshold in use is <= that")

    result = {
        "params": params,
        "fetched": time.strftime("%Y-%m-%d"),
        "frequency_list": freq_list,
    }
    _write_cache(cache_path, result)
    print(f"Cached to {cache_path}")
    return result


def fetch_unit_questions(
    taxonomy: dict,
    difficulties: list[int] | None = None,
    min_year: int = DEFAULT_MIN_YEAR,
    use_cache: bool = True,
    cache_dir: Path | None = None,
    page_size: int = 1000,
) -> dict:
    """
    Fetch EVERY question in a taxonomy slice (paginated empty-query
    search). taxonomy uses frequency-list style keys (category /
    subcategory / alternateSubcategory, see lib/units.py) and is mapped
    to the query endpoint's plural parameter names.

    Returns {"params": ..., "fetched": ..., "tossups": [...], "bonuses": [...]}.
    """
    if difficulties is None:
        difficulties = DEFAULT_DIFFICULTIES

    cache_dir = Path(cache_dir) if cache_dir else DEFAULT_CACHE_DIR / "unit_questions"
    key_base = "_".join(_sanitize_filename(v) for v in taxonomy.values())
    cache_path = cache_dir / f"{_cache_key(key_base, difficulties, min_year)}.json"

    if use_cache:
        cached = _load_cache(cache_path)
        if cached and (cached.get("tossups") or cached.get("bonuses")):
            print(f"Loading cached unit questions from {cache_path}")
            return cached

    param_names = {"category": "categories", "subcategory": "subcategories",
                   "alternateSubcategory": "alternateSubcategories"}
    base_params = {param_names[k]: v for k, v in taxonomy.items()}
    base_params.update({
        "queryString": "",
        "maxReturnLength": page_size,
        "minYear": min_year,
        "difficulties": ",".join(str(d) for d in difficulties),
    })

    print(f"Fetching all questions for {taxonomy} "
          f"(diff={difficulties}, year>={min_year})...")

    def _paged(question_type: str, page_param: str, array_key: str) -> list:
        items, page = [], 1
        while True:
            params = dict(base_params)
            params["questionType"] = question_type
            params[page_param] = page
            resp = _rate_limited_get(f"{API_BASE}/query", params)
            data = resp.json()[array_key]
            items.extend(data["questionArray"])
            total = data["count"]
            print(f"    {array_key}: {len(items)}/{total}")
            if len(items) >= total or not data["questionArray"]:
                return items
            page += 1

    tossups = _paged("tossup", "tossupPagination", "tossups")
    bonuses = _paged("bonus", "bonusPagination", "bonuses")

    result = {
        "params": base_params,
        "fetched": time.strftime("%Y-%m-%d"),
        "tossups": tossups,
        "bonuses": bonuses,
    }
    _write_cache(cache_path, result)
    print(f"Cached to {cache_path}")
    return result


def fetch_set_list(use_cache: bool = True, cache_dir: Path | None = None) -> list[str]:
    """Fetch the list of all set names in the qbreader database."""
    cache_dir = Path(cache_dir) if cache_dir else DEFAULT_CACHE_DIR / "sets"
    cache_path = cache_dir / "set_list.json"

    if use_cache:
        cached = _load_cache(cache_path)
        if cached:
            return cached

    print("Fetching set list...")
    resp = _rate_limited_get(f"{API_BASE}/set-list", {})
    data = resp.json()
    set_list = data.get("setList", data) if isinstance(data, dict) else data
    print(f"    Got {len(set_list)} sets")
    _write_cache(cache_path, set_list)
    return set_list


def fetch_num_packets(set_name: str, use_cache: bool = True,
                      cache_dir: Path | None = None) -> int:
    """Number of packets in a set."""
    cache_dir = Path(cache_dir) if cache_dir else DEFAULT_CACHE_DIR / "sets"
    cache_path = cache_dir / _sanitize_filename(set_name) / "num_packets.json"

    if use_cache:
        cached = _load_cache(cache_path)
        if cached and cached.get("numPackets"):
            return cached["numPackets"]

    resp = _rate_limited_get(f"{API_BASE}/num-packets", {"setName": set_name})
    data = resp.json()
    num = data["numPackets"] if isinstance(data, dict) else int(data)
    _write_cache(cache_path, {"setName": set_name, "numPackets": num})
    return num


def fetch_packet(set_name: str, packet_number: int, use_cache: bool = True,
                 cache_dir: Path | None = None) -> dict:
    """
    Fetch one packet (1-based) from a set.

    Returns the raw API response: {tossups, bonuses, packet}.
    """
    cache_dir = Path(cache_dir) if cache_dir else DEFAULT_CACHE_DIR / "sets"
    cache_path = (cache_dir / _sanitize_filename(set_name)
                  / f"packet_{packet_number:02d}.json")

    if use_cache:
        cached = _load_cache(cache_path)
        if cached and (cached.get("tossups") or cached.get("bonuses")):
            return cached

    print(f"  Fetching packet {packet_number} of '{set_name}'...")
    resp = _rate_limited_get(f"{API_BASE}/packet",
                             {"setName": set_name, "packetNumber": packet_number})
    data = resp.json()
    _write_cache(cache_path, data)
    return data


def fetch_set(set_name: str, use_cache: bool = True,
              cache_dir: Path | None = None) -> dict:
    """
    Fetch every packet of a set (cached per packet, so interrupted runs
    resume where they left off).

    Returns {set_name, num_packets, packets: [raw packet responses]}.
    """
    num = fetch_num_packets(set_name, use_cache=use_cache, cache_dir=cache_dir)
    print(f"Fetching set '{set_name}' ({num} packets)...")
    packets = [
        fetch_packet(set_name, n, use_cache=use_cache, cache_dir=cache_dir)
        for n in range(1, num + 1)
    ]
    total_t = sum(len(p.get("tossups", [])) for p in packets)
    total_b = sum(len(p.get("bonuses", [])) for p in packets)
    print(f"    {total_t} tossups, {total_b} bonuses")
    return {"set_name": set_name, "num_packets": num, "packets": packets}


if __name__ == "__main__":
    import sys

    topic = sys.argv[1] if len(sys.argv) > 1 else "Beethoven"
    diffs = [int(d) for d in sys.argv[2].split(",")] if len(sys.argv) > 2 else None
    data = fetch_topic(topic, difficulties=diffs)
    print(f"\nResults for '{topic}':")
    print(f"  Answerline: "
          f"{data['answer_matches']['tossups_found']} tossups, "
          f"{data['answer_matches']['bonuses_found']} bonuses")
