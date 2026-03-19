#!/usr/bin/env python3
"""
add_images_retry.py — Retry image searches for works that only got wiki links.
Uses Commons API for thumbnails instead of English Wikipedia API.
"""

import json
import re
import time
import requests
from pathlib import Path

OUTPUT_DIR = Path("output")
HEADERS = {'User-Agent': 'StockQB/1.0 (quizbowl study tool; contact: stock@example.com)'}

VISUAL_INDICATORS = {"Painting", "Sculpture", "Fresco", "Mural", "Altarpiece", "Print", "Engraving"}


def search_commons(query):
    """Search Wikimedia Commons for files matching query."""
    url = 'https://commons.wikimedia.org/w/api.php'
    params = {
        'action': 'query', 'list': 'search', 'srsearch': query,
        'srnamespace': 6, 'srlimit': 8, 'format': 'json'
    }
    try:
        r = requests.get(url, params=params, headers=HEADERS, timeout=20)
        r.raise_for_status()
        return [item['title'].replace('File:', '') for item in r.json().get('query', {}).get('search', [])]
    except Exception as e:
        print(f"      Search error: {e}")
        return []


def get_commons_thumb(filename, width=500):
    """Get thumbnail URL directly from Commons API."""
    url = 'https://commons.wikimedia.org/w/api.php'
    params = {
        'action': 'query', 'titles': f'File:{filename}',
        'prop': 'imageinfo', 'iiprop': 'url',
        'iiurlwidth': width, 'format': 'json'
    }
    try:
        r = requests.get(url, params=params, headers=HEADERS, timeout=20)
        r.raise_for_status()
        pages = r.json().get('query', {}).get('pages', {})
        for page in pages.values():
            info = page.get('imageinfo', [])
            if info:
                return info[0].get('thumburl')
    except Exception as e:
        print(f"      Thumb error: {e}")
    return None


def verify_url(url):
    if not url:
        return False
    try:
        r = requests.head(url, headers=HEADERS, timeout=10, allow_redirects=True)
        return r.status_code == 200
    except:
        return False


def clean_work_name(name):
    return re.sub(r"\s*\(.*?\)\s*$", "", name).strip()


def find_image(work_name, artist_name):
    """Search for image with multiple query strategies."""
    clean = clean_work_name(work_name)
    # Remove slashes for multi-name works
    parts = [p.strip() for p in clean.split('/')]

    queries = []
    for part in parts[:2]:  # Try first two alternative names
        queries.append(f"{part} {artist_name}")
    queries.append(f"{clean} painting")

    for query in queries:
        print(f"      Query: {query}")
        filenames = search_commons(query)
        time.sleep(1.0)  # More conservative rate limit

        for fname in filenames:
            # Skip PDFs and non-image files
            if fname.lower().endswith(('.pdf', '.svg', '.djvu', '.ogg', '.ogv', '.webm')):
                continue
            thumb = get_commons_thumb(fname)
            time.sleep(1.0)
            if thumb and verify_url(thumb):
                time.sleep(0.5)
                return thumb

    return None


def make_wiki_link(work_name, artist_name):
    query = f"{clean_work_name(work_name)} {artist_name}".replace(" ", "+")
    return f"https://en.wikipedia.org/w/index.php?search={query}"


# Topics to process
TOPICS = {
    "Albrecht Dürer": "albrecht_dürer",
    "Alfred Sisley": "alfred_sisley",
    "Andrea del Sarto": "andrea_del_sarto",
    "Andrea del Verrocchio": "andrea_del_verrocchio",
    "Andrea Mantegna": "andrea_mantegna",
    "Andrew Wyeth": "andrew_wyeth",
    "Annibale Carracci": "annibale_carracci",
    "Antoine Watteau": "antoine_watteau",
    "Augustus Saint-Gaudens": "augustus_saint-gaudens",
    "William-Adolphe Bouguereau": "bouguereau",
    "Camille Pissarro": "camille_pissarro",
    "Charles Demuth": "charles_demuth",
    "Charles Le Brun": "charles_le_brun",
    "Charles Willson Peale": "charles_willson_peale",
    "Cimabue": "cimabue",
    "Claes Oldenburg": "claes_oldenburg",
}


def process_topic(artist_name, slug):
    json_path = OUTPUT_DIR / f"{slug}_analysis.json"
    if not json_path.exists():
        print(f"  SKIP: {json_path} not found")
        return False

    with open(json_path) as f:
        analysis = json.load(f)

    works = analysis.get("works", [])
    cards = analysis.get("cards", [])
    modified = False

    for work in works:
        indicator = work.get("indicator", "")
        if indicator not in VISUAL_INDICATORS:
            continue

        # Check: only retry works that have empty-url images (wiki link fallbacks)
        existing_images = work.get("images", [])
        has_real_image = any(img.get("url") for img in existing_images)
        if has_real_image:
            continue

        # Has a link fallback or no images at all - try to find real image
        work_name = work["name"]
        clean = clean_work_name(work_name)
        print(f"    Retrying: {clean}")

        thumb_url = find_image(work_name, artist_name)

        if thumb_url:
            print(f"    FOUND: {thumb_url[:80]}...")
            work["images"] = [{"url": thumb_url, "caption": clean}]

            # Update basic cards for this work
            for card in cards:
                if card.get("work") == work_name and card.get("type") == "basic":
                    card_images = card.get("images", [])
                    if not any(img.get("url") for img in card_images):
                        card["images"] = [{"url": thumb_url, "side": "back"}]

            # Add image recognition card if missing
            has_img_card = any(
                c.get("type") == "image" and c.get("work") == work_name for c in cards
            )
            if not has_img_card:
                cards.append({
                    "type": "image", "indicator": indicator,
                    "front": "", "back": f"{clean} ({artist_name})",
                    "work": work_name, "frequency": 0, "tags": [],
                    "images": [{"url": thumb_url, "side": "front"}]
                })

            modified = True
        else:
            # Keep existing wiki link if present, or add one
            if not existing_images:
                wiki_link = make_wiki_link(work_name, artist_name)
                work["images"] = [{"url": "", "link": wiki_link, "caption": clean}]
                modified = True
            print(f"    Still not found")

    if modified:
        analysis["cards"] = cards
        with open(json_path, 'w') as f:
            json.dump(analysis, f, indent=2, ensure_ascii=False)
        print(f"  SAVED: {json_path}")
    else:
        print(f"  No changes needed")

    return modified


def main():
    print("=== Retry: Finding images via Commons API ===\n")
    changed = 0
    for artist_name, slug in TOPICS.items():
        print(f"\n--- {artist_name} ({slug}) ---")
        if process_topic(artist_name, slug):
            changed += 1

    print(f"\n=== Done! Modified {changed} of {len(TOPICS)} files ===")


if __name__ == "__main__":
    main()
