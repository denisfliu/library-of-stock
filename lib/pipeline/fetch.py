"""
fetch.py — Question data access for the pipeline.

Since July 2026 every query is answered from the local qbreader mirror
(mirror/qbreader.sqlite — the qb-mirror package, extracted to
github.com/qbsuite/qb-mirror), not the live API: topic fetches, text
mentions, frequency lists, unit sweeps, set/packet reads all work
offline and without rate limits. Result shapes are unchanged from the
API era, and qbmirror.query replicates the API's search semantics
exactly (verified against live results at cutover, and re-verified
byte-identical at package extraction).

The live REST API is used only by `qbmirror sync` (qbmirror.api) to
pull new sets. To pick up question *edits* inside already-mirrored
sets, re-seed from a newer official backup (`qbmirror import-backup`)
or run sync with --refresh. lib/common sets QBMIRROR_DB/QBMIRROR_CACHE
so the package finds the repo's mirror and cache.
"""
import json
import re
import sys as _sys
import time
from pathlib import Path

_sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
import lib.common  # noqa: F401 — sets QBMIRROR_DB before qbmirror opens it
from qbmirror import db as mirror_db
from qbmirror import query as mirror_query

DEFAULT_MIN_YEAR = 2012
# The mirror has no pagination cost, so return everything up to the
# API-parity ceiling (the old 500 cap existed to limit HTTP payloads).
DEFAULT_MAX_RESULTS = 10000
# Difficulty range for frequency lists and set sweeps: easy college (5)
# through nationals (10). Topic fetches keep passing difficulties
# explicitly from the queue entries.
DEFAULT_DIFFICULTIES = [5, 7, 8, 9, 10]
# Frequency limit: high enough to reach frequency 1 on the biggest
# subcategories (American Lit has 1313 answerlines at freq>=3).
DEFAULT_FREQ_LIMIT = 5000

_mirror_conn = None


def _mirror():
    global _mirror_conn
    if _mirror_conn is None:
        _mirror_conn = mirror_db.open_db()
    return _mirror_conn


def query_page(
    query_string: str,
    search_type: str = "answer",
    difficulties: list[int] | None = None,
    categories: list[str] | None = None,
    min_year: int = DEFAULT_MIN_YEAR,
    max_results: int = DEFAULT_MAX_RESULTS,
    exact_phrase: bool = False,
) -> dict:
    """
    Run one query against the mirror (formerly one API page).

    Returns dict with tossups, bonuses, tossups_found, bonuses_found.
    """
    print(f"  Querying mirror for '{query_string}' (type={search_type}, "
          f"diff={difficulties}, year>={min_year})...")
    data = mirror_query.query(
        query_string,
        search_type=search_type,
        difficulties=difficulties,
        categories=categories,
        min_year=min_year,
        max_return_length=max_results,
        exact_phrase=exact_phrase,
        conn=_mirror(),
    )

    tossups = data["tossups"]["questionArray"]
    bonuses = data["bonuses"]["questionArray"]
    print(f"    Got {len(tossups)} tossups (of {data['tossups']['count']}), "
          f"{len(bonuses)} bonuses (of {data['bonuses']['count']})")
    if (len(tossups) < data["tossups"]["count"]
            or len(bonuses) < data["bonuses"]["count"]):
        print(f"    WARNING: results truncated at max_results={max_results} "
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
) -> dict:
    """
    Fetch answerline matches for a topic from the mirror.

    Returns dict with:
        - query_string, difficulties, min_year
        - answer_matches: {tossups, bonuses, tossups_found, bonuses_found}
    """
    print(f"Fetching topic: '{query_string}'")
    # exact_phrase adds \b word boundaries. Without it the API's substring
    # match attributes foreign questions to the topic: "Hanson" ⊂ "Chanson
    # de Roland", "Edward I" ⊂ "Charles Edward Ives" / "Edward III". Found
    # July 2026 via spurious related.json links; dev/oneshots/repair_refs.py
    # cleaned the committed questions_ref.json files retroactively.
    answer_data = query_page(
        query_string,
        search_type="answer",
        difficulties=difficulties,
        categories=categories,
        min_year=min_year,
        exact_phrase=True,
    )
    return {
        "query_string": query_string,
        "difficulties": difficulties,
        "min_year": min_year,
        "answer_matches": answer_data,
    }


def fetch_text_mentions(
    query_string: str,
    difficulties: list[int] | None = None,
    categories: list[str] | None = None,
    min_year: int = DEFAULT_MIN_YEAR,
) -> dict:
    """
    Fetch questions where the topic appears in the text (but may not be
    the answer).
    """
    print(f"Fetching text mentions: '{query_string}'")
    question_data = query_page(
        query_string,
        search_type="question",
        difficulties=difficulties,
        categories=categories,
        min_year=min_year,
        exact_phrase=True,  # same boundary rule as fetch_topic
    )
    return {
        "query_string": query_string,
        "difficulties": difficulties,
        "min_year": min_year,
        "text_mentions": question_data,
    }


def fetch_frequency_list(
    freq_params: dict,
    difficulties: list[int] | None = None,
    limit: int = DEFAULT_FREQ_LIMIT,
    question_type: str = "all",
    min_year: int = DEFAULT_MIN_YEAR,
    max_year: int | None = None,
) -> dict:
    """
    Compute the most frequent answerlines for a category slice from the
    mirror.

    freq_params holds the taxonomy filter exactly as the API expected it
    (some combination of category / subcategory / alternateSubcategory —
    at least one required; see lib/units.py Unit.freq_params).

    Returns dict with:
        - params: the full request parameters
        - fetched: ISO date of the computation
        - frequency_list: [{answer, answer_normalized, frequency}, ...]
          sorted desc
    """
    if difficulties is None:
        difficulties = DEFAULT_DIFFICULTIES
    if not freq_params:
        raise ValueError("freq_params must set category, subcategory, "
                         "or alternateSubcategory")

    params = dict(freq_params)
    params["limit"] = limit
    params["questionType"] = question_type
    params["minYear"] = min_year
    if max_year:
        params["maxYear"] = max_year
    if difficulties:
        params["difficulties"] = ",".join(str(d) for d in difficulties)

    print(f"Computing frequency list: {freq_params} "
          f"(diff={difficulties}, year>={min_year}, limit={limit})...")
    raw_list = mirror_query.frequency_list(
        category=freq_params.get("category"),
        subcategory=freq_params.get("subcategory"),
        alternate_subcategory=freq_params.get("alternateSubcategory"),
        difficulties=difficulties,
        limit=limit,
        min_year=min_year,
        max_year=max_year,
        question_type=question_type,
        conn=_mirror(),
    )
    freq_list = [
        {
            "answer": e["answer"],
            "answer_normalized": e["answer_normalized"],
            "frequency": e["count"],
        }
        for e in raw_list
    ]
    print(f"    Got {len(freq_list)} answerlines")
    if len(freq_list) >= limit:
        tail = freq_list[-1]["frequency"] if freq_list else "?"
        print(f"    WARNING: hit limit={limit} (tail frequency {tail}) — "
              f"raise the limit if the threshold in use is <= that")

    return {
        "params": params,
        "fetched": time.strftime("%Y-%m-%d"),
        "frequency_list": freq_list,
    }


def fetch_unit_questions(
    taxonomy: dict,
    difficulties: list[int] | None = None,
    min_year: int = DEFAULT_MIN_YEAR,
    page_size: int = 1000,
) -> dict:
    """
    Fetch EVERY question in a taxonomy slice from the mirror. taxonomy
    uses frequency-list style keys (category / subcategory /
    alternateSubcategory, see lib/units.py).

    Returns {"params": ..., "fetched": ..., "tossups": [...], "bonuses": [...]}.
    """
    if difficulties is None:
        difficulties = DEFAULT_DIFFICULTIES

    print(f"Fetching all questions for {taxonomy} "
          f"(diff={difficulties}, year>={min_year})...")

    kwargs = {
        "categories": [taxonomy["category"]] if "category" in taxonomy else None,
        "subcategories": [taxonomy["subcategory"]] if "subcategory" in taxonomy else None,
        "alternate_subcategories": ([taxonomy["alternateSubcategory"]]
                                    if "alternateSubcategory" in taxonomy else None),
    }

    def _paged(question_type: str, page_key: str, array_key: str) -> list:
        items, page = [], 1
        while True:
            data = mirror_query.query(
                "",
                question_type=question_type,
                difficulties=difficulties,
                min_year=min_year,
                max_return_length=page_size,
                conn=_mirror(),
                **{page_key: page},
                **kwargs,
            )[array_key]
            items.extend(data["questionArray"])
            total = data["count"]
            print(f"    {array_key}: {len(items)}/{total}")
            if len(items) >= total or not data["questionArray"]:
                return items
            page += 1

    tossups = _paged("tossup", "tossup_pagination", "tossups")
    bonuses = _paged("bonus", "bonus_pagination", "bonuses")

    param_names = {"category": "categories", "subcategory": "subcategories",
                   "alternateSubcategory": "alternateSubcategories"}
    base_params = {param_names[k]: v for k, v in taxonomy.items()}
    base_params.update({
        "queryString": "",
        "maxReturnLength": page_size,
        "minYear": min_year,
        "difficulties": ",".join(str(d) for d in difficulties),
    })

    return {
        "params": base_params,
        "fetched": time.strftime("%Y-%m-%d"),
        "tossups": tossups,
        "bonuses": bonuses,
    }


def fetch_set_list() -> list[str]:
    """List of all set names in the mirror (year desc, name asc — the
    API's ordering)."""
    return mirror_query.set_list(conn=_mirror())


def fetch_num_packets(set_name: str) -> int:
    """Number of packets in a set."""
    return mirror_query.num_packets(set_name, conn=_mirror())


def fetch_packet(set_name: str, packet_number: int) -> dict:
    """One packet (1-based) of a set from the mirror: {tossups, bonuses}."""
    return mirror_query.packet(set_name, packet_number, conn=_mirror())


def fetch_set(set_name: str) -> dict:
    """
    Every packet of a set from the mirror.

    Returns {set_name, num_packets, packets: [{tossups, bonuses}]}.
    """
    num = fetch_num_packets(set_name)
    print(f"Reading set '{set_name}' from mirror ({num} packets)...")
    packets = [fetch_packet(set_name, n) for n in range(1, num + 1)]
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
