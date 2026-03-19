#!/usr/bin/env python3
"""
add_images_final.py — Final pass: find images for remaining works.
Uses Commons API with 2s delays to avoid rate limiting.
Only processes works that currently have NO real image URL.
"""

import json
import re
import time
import requests
from pathlib import Path

OUTPUT_DIR = Path("output")
HEADERS = {'User-Agent': 'StockQB/1.0 (quizbowl study; contact: stock@example.com)'}
VISUAL_INDICATORS = {"Painting", "Sculpture", "Fresco", "Mural", "Altarpiece", "Print", "Engraving"}
DELAY = 2.0  # seconds between API calls


def api_get(url, params):
    """Make an API request with error handling."""
    try:
        r = requests.get(url, params=params, headers=HEADERS, timeout=20)
        if r.status_code == 429:
            retry = int(r.headers.get('retry-after', 60))
            print(f"      Rate limited! Waiting {retry}s...")
            time.sleep(retry + 5)
            r = requests.get(url, params=params, headers=HEADERS, timeout=20)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        print(f"      API error: {e}")
        return None


def search_commons(query):
    data = api_get('https://commons.wikimedia.org/w/api.php', {
        'action': 'query', 'list': 'search', 'srsearch': query,
        'srnamespace': 6, 'srlimit': 8, 'format': 'json'
    })
    if not data:
        return []
    return [item['title'].replace('File:', '') for item in data.get('query', {}).get('search', [])]


def get_commons_thumb(filename, width=500):
    data = api_get('https://commons.wikimedia.org/w/api.php', {
        'action': 'query', 'titles': f'File:{filename}',
        'prop': 'imageinfo', 'iiprop': 'url',
        'iiurlwidth': width, 'format': 'json'
    })
    if not data:
        return None
    pages = data.get('query', {}).get('pages', {})
    for page in pages.values():
        info = page.get('imageinfo', [])
        if info:
            return info[0].get('thumburl')
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


def make_wiki_link(work_name, artist_name):
    query = f"{clean_work_name(work_name)} {artist_name}".replace(" ", "+")
    return f"https://en.wikipedia.org/w/index.php?search={query}"


# Specific search queries for tricky works
CUSTOM_QUERIES = {
    # (slug, work_substring): [list of search queries to try]
    ("albrecht_dürer", "Four Apostles"): ["Four Apostles Dürer", "Vier Apostel Dürer"],
    ("andrea_del_sarto", "Chiostro"): ["Chiostro Scalzo Andrea Sarto", "Baptism John Baptist Andrea Sarto"],
    ("andrea_del_sarto", "Madonna del Sacco"): ["Madonna Sacco Andrea Sarto", "Andrea del Sarto Madonna sack"],
    ("andrea_del_verrocchio", "Christ and Saint Thomas"): ["Verrocchio Christ Thomas Orsanmichele", "Incredulity Thomas Verrocchio"],
    ("andrea_mantegna", "San Zeno"): ["Mantegna San Zeno altarpiece", "Pala San Zeno Mantegna"],
    ("andrew_wyeth", "Christina"): ["Christina World Wyeth"],
    ("andrew_wyeth", "Helga"): ["Helga Wyeth painting"],
    ("andrew_wyeth", "Winter 1946"): ["Winter 1946 Wyeth"],
    ("annibale_carracci", "Butcher"): ["Butcher Shop Carracci", "Macelleria Carracci"],
    ("annibale_carracci", "Beaneater"): ["Beaneater Carracci", "Mangiafagioli Carracci"],
    ("annibale_carracci", "Flight into Egypt"): ["Flight Egypt Carracci landscape", "Fuga Egitto Carracci"],
    ("antoine_watteau", "Gersaint"): ["Enseigne Gersaint Watteau", "Gersaint shopsign Watteau"],
    ("antoine_watteau", "Gilles"): ["Pierrot Gilles Watteau", "Watteau Pierrot painting"],
    ("antoine_watteau", "Mezzetin"): ["Mezzetin Watteau painting", "Watteau Mezzetin lute"],
    ("antoine_watteau", "Love Lesson"): ["Lecon amour Watteau", "Love Lesson Watteau"],
    ("augustus_saint-gaudens", "Shaw"): ["Shaw Memorial Saint-Gaudens", "Robert Shaw 54th regiment memorial"],
    ("augustus_saint-gaudens", "Standing Lincoln"): ["Abraham Lincoln Saint-Gaudens Chicago", "Standing Lincoln statue"],
    ("augustus_saint-gaudens", "Adams"): ["Adams Memorial Saint-Gaudens grief", "Grief statue Rock Creek"],
    ("augustus_saint-gaudens", "Sherman"): ["Sherman monument Saint-Gaudens New York", "Sherman gilded statue"],
    ("augustus_saint-gaudens", "Amor"): ["Amor Caritas Saint-Gaudens bronze", "Amor Caritas relief"],
    ("augustus_saint-gaudens", "Diana"): ["Diana Saint-Gaudens statue", "Diana weathervane Saint-Gaudens"],
    ("augustus_saint-gaudens", "Double Eagle"): ["Saint-Gaudens double eagle coin", "1907 double eagle gold"],
    ("bouguereau", "Nymphs"): ["Nymphes Satyre Bouguereau", "Nymphs Satyr Bouguereau 1873"],
    ("camille_pissarro", "Boulevard"): ["Boulevard Montmartre Pissarro spring", "Pissarro Boulevard Montmartre"],
    ("camille_pissarro", "Pontoise"): ["Pissarro Pontoise landscape", "Hermitage Pontoise Pissarro"],
    ("charles_demuth", "Figure 5"): ["Figure 5 Gold Demuth", "I saw figure five Demuth"],
    ("charles_willson_peale", "Staircase"): ["Staircase Group Peale trompe", "Peale Staircase Group painting"],
    ("cimabue", "Crucifix"): ["Cimabue crucifix Santa Croce", "Crocifisso Cimabue"],
    ("cimabue", "Diptych"): ["Cimabue diptych", "Cimabue Madonna kitchen"],
    ("claes_oldenburg", "Lipstick"): ["Lipstick ascending caterpillar Yale", "Oldenburg lipstick sculpture"],
    ("claes_oldenburg", "Spoonbridge"): ["Spoonbridge cherry Minneapolis", "Oldenburg spoon cherry sculpture"],
    ("claes_oldenburg", "Floor Burger"): ["Oldenburg Floor Burger soft sculpture", "Floor Burger Oldenburg"],
    ("claes_oldenburg", "Dropped Cone"): ["Dropped Cone Oldenburg Cologne", "Dropped Cone Neumarkt"],
    ("claes_oldenburg", "Shuttlecocks"): ["Shuttlecocks Nelson-Atkins Oldenburg", "Oldenburg shuttlecock sculpture"],
}

# Topics
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
    "Charles Willson Peale": "charles_willson_peale",
    "Cimabue": "cimabue",
    "Claes Oldenburg": "claes_oldenburg",
}


def find_image_for_work(slug, work_name, artist_name):
    """Try to find a verified Commons thumbnail for a work."""
    clean = clean_work_name(work_name)
    parts = [p.strip() for p in clean.split('/')]

    # Check for custom queries
    queries = []
    for (s, sub), qs in CUSTOM_QUERIES.items():
        if s == slug and sub.lower() in work_name.lower():
            queries = qs
            break

    if not queries:
        for part in parts[:2]:
            queries.append(f"{part} {artist_name}")

    for query in queries:
        print(f"      Searching: {query}")
        filenames = search_commons(query)
        time.sleep(DELAY)

        for fname in filenames:
            # Skip non-image files
            if fname.lower().endswith(('.pdf', '.svg', '.djvu', '.ogg', '.ogv', '.webm', '.tif', '.tiff')):
                continue
            print(f"        Trying: {fname[:60]}...")
            thumb = get_commons_thumb(fname)
            time.sleep(DELAY)
            if thumb and verify_url(thumb):
                time.sleep(0.5)
                print(f"        VERIFIED!")
                return thumb

    return None


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

        existing = work.get("images", [])
        if any(img.get("url") for img in existing):
            continue

        work_name = work["name"]
        clean = clean_work_name(work_name)
        print(f"    {clean}")

        thumb_url = find_image_for_work(slug, work_name, artist_name)

        if thumb_url:
            work["images"] = [{"url": thumb_url, "caption": clean}]

            for card in cards:
                if card.get("work") == work_name and card.get("type") == "basic":
                    card_imgs = card.get("images", [])
                    if not any(img.get("url") for img in card_imgs):
                        card["images"] = [{"url": thumb_url, "side": "back"}]

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
            if not existing:
                wiki_link = make_wiki_link(work_name, artist_name)
                work["images"] = [{"url": "", "link": wiki_link, "caption": clean}]
                modified = True
            print(f"      No image found")

    if modified:
        analysis["cards"] = cards
        with open(json_path, 'w') as f:
            json.dump(analysis, f, indent=2, ensure_ascii=False)
        print(f"  SAVED: {json_path}")
    else:
        print(f"  No changes needed")

    return modified


def main():
    print("=== Final image search pass ===\n")

    # Check rate limit first
    try:
        r = requests.get('https://commons.wikimedia.org/w/api.php', params={
            'action': 'query', 'meta': 'siteinfo', 'format': 'json'
        }, headers=HEADERS, timeout=10)
        if r.status_code == 429:
            retry = int(r.headers.get('retry-after', 60))
            print(f"Rate limited! Waiting {retry}s...")
            time.sleep(retry + 5)
    except:
        pass

    changed = 0
    for artist_name, slug in TOPICS.items():
        print(f"\n--- {artist_name} ({slug}) ---")
        if process_topic(artist_name, slug):
            changed += 1

    print(f"\n=== Done! Modified {changed} files ===")


if __name__ == "__main__":
    main()
