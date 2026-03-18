"""
images.py — Wikimedia Commons image lookup for visual topics.

Searches for painting images on Wikimedia Commons and returns
direct thumbnail URLs that can be embedded in HTML.
"""

import requests

COMMONS_API = "https://commons.wikimedia.org/w/api.php"
HEADERS = {"User-Agent": "StockQB/1.0 (quizbowl study tool)"}


def search_commons(query: str, limit: int = 5) -> list[dict]:
    """
    Search Wikimedia Commons for image files matching a query.

    Returns list of dicts with: title, url (full), thumb (500px thumbnail).
    """
    r = requests.get(COMMONS_API, params={
        "action": "query",
        "list": "search",
        "srsearch": query,
        "srnamespace": "6",  # File namespace
        "srlimit": limit,
        "format": "json",
    }, headers=HEADERS)
    results = r.json().get("query", {}).get("search", [])

    images = []
    for result in results:
        title = result["title"]
        # Skip PDFs and non-image files
        if title.lower().endswith((".pdf", ".svg", ".ogv", ".webm")):
            continue
        info = _get_image_info(title)
        if info:
            images.append(info)
    return images


def _get_image_info(file_title: str, thumb_width: int = 500) -> dict | None:
    """Get URL info for a specific Wikimedia Commons file."""
    r = requests.get(COMMONS_API, params={
        "action": "query",
        "titles": file_title,
        "prop": "imageinfo",
        "iiprop": "url",
        "iiurlwidth": thumb_width,
        "format": "json",
    }, headers=HEADERS)
    data = r.json()
    for pid, page in data["query"]["pages"].items():
        if "imageinfo" in page:
            info = page["imageinfo"][0]
            return {
                "title": file_title,
                "url": info.get("thumburl", info["url"]),
                "full_url": info["url"],
                "link": info.get("descriptionurl", ""),
            }
    return None


def find_painting(artist: str, painting: str) -> dict | None:
    """
    Try to find a specific painting on Wikimedia Commons.

    Returns dict with url/thumb/link or None if not found.
    """
    results = search_commons(f"{artist} {painting}", limit=5)
    # Try to find the best match
    painting_lower = painting.lower()
    artist_lower = artist.lower()
    for r in results:
        title_lower = r["title"].lower()
        if painting_lower.replace(" ", "") in title_lower.replace(" ", ""):
            return r
    # If no exact match, return first result that mentions the artist
    for r in results:
        if artist_lower.split()[-1].lower() in r["title"].lower():
            return r
    return results[0] if results else None


if __name__ == "__main__":
    import sys
    artist = sys.argv[1] if len(sys.argv) > 1 else "Emily Carr"
    painting = sys.argv[2] if len(sys.argv) > 2 else "Indian Church"
    result = find_painting(artist, painting)
    if result:
        print(f"Found: {result['title']}")
        print(f"  Thumbnail: {result['url']}")
        print(f"  Full: {result['full_url']}")
    else:
        print("Not found")
