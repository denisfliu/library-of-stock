#!/usr/bin/env python3
"""
add_images_batch_b.py — Find images for batch B topics via Commons API.
Batch: Tiepolo, Klimt, Moreau, Höch, Memling, Tanner, Hokusai, Hugo van der Goes,
       Repin, Epstein, Lawrence, Pontormo, Ensor, Steen, Fragonard, Millais, Orozco
"""
import json
import re
import time
import sys
import requests
from pathlib import Path

OUTPUT_DIR = Path("output")
HEADERS = {'User-Agent': 'StockQB/1.0 (quizbowl study; contact: stock@example.com)'}
VISUAL_INDICATORS = {"Painting", "Sculpture", "Fresco", "Mural", "Altarpiece", "Print",
                     "Engraving", "Collage", "Woodblock Print", "Woodcut", "Drawing"}
DELAY = 2.0


def api_get(url, params):
    for attempt in range(3):
        try:
            r = requests.get(url, params=params, headers=HEADERS, timeout=20)
            if r.status_code == 429:
                retry = int(r.headers.get('retry-after', 60))
                print(f"      Rate limited! Waiting {retry}s...", flush=True)
                time.sleep(retry + 5)
                continue
            r.raise_for_status()
            return r.json()
        except Exception as e:
            print(f"      API error (attempt {attempt+1}): {e}", flush=True)
            time.sleep(10)
    return None


def search_and_get_thumbs(query, width=500):
    """Search commons AND get thumbnails in just 2 API calls (batched)."""
    # Step 1: Search
    data = api_get('https://commons.wikimedia.org/w/api.php', {
        'action': 'query', 'list': 'search', 'srsearch': query,
        'srnamespace': 6, 'srlimit': 5, 'format': 'json'
    })
    time.sleep(DELAY)
    if not data:
        return []

    filenames = []
    for item in data.get('query', {}).get('search', []):
        fn = item['title'].replace('File:', '')
        if not fn.lower().endswith(('.pdf', '.svg', '.djvu', '.ogg', '.ogv', '.webm')):
            filenames.append(fn)

    if not filenames:
        return []

    # Step 2: Get thumbnails for ALL results in ONE batch call
    titles = '|'.join(f'File:{fn}' for fn in filenames)
    data2 = api_get('https://commons.wikimedia.org/w/api.php', {
        'action': 'query', 'titles': titles,
        'prop': 'imageinfo', 'iiprop': 'url',
        'iiurlwidth': width, 'format': 'json'
    })
    time.sleep(DELAY)
    if not data2:
        return []

    # Return list of (filename, thumb_url)
    results = []
    pages = data2.get('query', {}).get('pages', {})
    for page in pages.values():
        title = page.get('title', '').replace('File:', '')
        info = page.get('imageinfo', [])
        if info and info[0].get('thumburl'):
            results.append((title, info[0]['thumburl']))

    return results


def clean_work_name(name):
    return re.sub(r"\s*\(.*?\)\s*$", "", name).strip()


def make_wiki_link(work_name, artist_name):
    query = f"{clean_work_name(work_name)} {artist_name}".replace(" ", "+")
    return f"https://en.wikipedia.org/w/index.php?search={query}"


# Custom search queries keyed by (slug, substring_in_work_name)
CUSTOM_QUERIES = {
    # Tiepolo
    ("giovanni_battista_tiepolo", "Wurzburg"): ["Tiepolo Apollo continents Wurzburg fresco", "Tiepolo Wurzburg residence ceiling"],
    ("giovanni_battista_tiepolo", "Apotheosis"): ["Tiepolo Apotheosis Spanish Monarchy", "Tiepolo Throne Room Madrid"],
    ("giovanni_battista_tiepolo", "Cleopatra"): ["Giambattista Tiepolo Banquet Cleopatra painting", "Tiepolo Cleopatra"],
    ("giovanni_battista_tiepolo", "Other Works"): ["Tiepolo Immaculate Conception", "Giambattista Tiepolo painting"],
    # Klimt
    ("gustav_klimt", "Danae"): ["Gustav Klimt Danae painting", "Klimt Danae 1907"],
    ("gustav_klimt", "Stoclet"): ["Klimt Stoclet Frieze", "Klimt Tree Life mosaic", "Gustav Klimt Expectation Stoclet"],
    # Moreau
    ("gustave_moreau", "Life of Humanity"): ["Gustave Moreau Life Humanity polyptych"],
    ("gustave_moreau", "Licornes"): ["Gustave Moreau Licornes Unicorns painting", "Moreau Unicorns painting"],
    # Hannah Höch
    ("hannah_hoch", "Ethnographic"): ["Hannah Höch Ethnographic Museum photomontage", "Hannah Hoch collage"],
    # Memling
    ("hans_memling", "Last Judgment"): ["Hans Memling Last Judgment triptych", "Memling Last Judgement Gdansk painting"],
    ("hans_memling", "Ursula"): ["Hans Memling Shrine Saint Ursula", "Memling Ursula reliquary Bruges"],
    ("hans_memling", "Catherine"): ["Memling Mystic Marriage Saint Catherine triptych"],
    ("hans_memling", "Passion"): ["Hans Memling Scenes Passion Christ", "Memling Passion Turin painting"],
    ("hans_memling", "Other"): ["Hans Memling Donne Triptych", "Memling portrait man"],
    # Tanner
    ("henry_ossawa_tanner", "Banjo"): ["Henry Ossawa Tanner Banjo Lesson painting"],
    ("henry_ossawa_tanner", "Thankful"): ["Henry Ossawa Tanner Thankful Poor"],
    ("henry_ossawa_tanner", "Annunciation"): ["Henry Ossawa Tanner Annunciation painting"],
    ("henry_ossawa_tanner", "Other"): ["Henry Ossawa Tanner painting"],
    # Hokusai
    ("hokusai", "Thirty-Six"): ["Katsushika Hokusai Thirty-six Views Fuji"],
    ("hokusai", "Great Wave"): ["Great Wave Kanagawa Hokusai woodblock", "Tsunami Hokusai"],
    ("hokusai", "Red Fuji"): ["Hokusai Red Fuji South Wind", "Fine Wind Clear Morning Hokusai"],
    ("hokusai", "Fisherman"): ["Hokusai Dream Fisherman Wife octopus", "Tako Ama Hokusai"],
    ("hokusai", "Manga"): ["Hokusai Manga illustration volume"],
    ("hokusai", "Quick Lessons"): ["Hokusai drawing lesson"],
    ("hokusai", "Ghost"): ["Hokusai Hyaku Monogatari ghost", "Hokusai Oiwa ghost"],
    ("hokusai", "Oceans"): ["Hokusai Chie no umi", "Hokusai whaling"],
    ("hokusai", "Other"): ["Katsushika Hokusai painting", "Hokusai Phoenix"],
    # Hugo van der Goes
    ("hugo_van_der_goes", "Portinari"): ["Hugo van der Goes Portinari Altarpiece Uffizi", "Portinari Triptych"],
    ("hugo_van_der_goes", "Monforte"): ["Hugo van der Goes Monforte Altarpiece Berlin", "Hugo Goes Adoration Magi"],
    # Repin
    ("ilya_repin", "Procession"): ["Repin Religious Procession Kursk Province painting", "Ilya Repin Krestny Khod"],
    # Epstein
    ("jacob_epstein", "BMA"): ["Jacob Epstein BMA sculpture", "Epstein British Medical Association statues Strand"],
    ("jacob_epstein", "Jacob and the Angel"): ["Jacob Epstein Jacob Angel alabaster sculpture"],
    # Lawrence
    ("jacob_lawrence", "Migration"): ["Jacob Lawrence Migration Series panel"],
    ("jacob_lawrence", "John Brown"): ["Jacob Lawrence John Brown series"],
    ("jacob_lawrence", "Toussaint"): ["Jacob Lawrence Toussaint Louverture"],
    ("jacob_lawrence", "Other"): ["Jacob Lawrence Builders painting", "Jacob Lawrence painting"],
    # Pontormo
    ("jacopo_pontormo", "Vertumnus"): ["Pontormo Vertumnus Pomona lunette", "Pontormo Poggio Caiano"],
    # Ensor
    ("james_ensor", "Skeletons"): ["James Ensor Skeletons Herring painting", "Ensor squelettes hareng"],
    # Steen
    ("jan_steen", "Merry"): ["Jan Steen Merry Family Rijksmuseum", "Jan Steen vrolijke huisgezin"],
    # Fragonard
    ("jean-honoré_fragonard", "Swing"): ["Fragonard The Swing painting", "Fragonard Escarpolette"],
    ("jean-honoré_fragonard", "Progress"): ["Fragonard Progress Love painting", "Fragonard Pursuit Love Frick"],
    ("jean-honoré_fragonard", "Bolt"): ["Fragonard Le Verrou painting", "Fragonard The Bolt Louvre"],
    ("jean-honoré_fragonard", "Other"): ["Fragonard The Reader painting", "Jean-Honoré Fragonard painting"],
    # Millais
    ("john_everett_millais", "Ophelia"): ["Millais Ophelia painting Tate", "John Everett Millais Ophelia"],
    ("john_everett_millais", "Christ"): ["Millais Christ House Parents painting", "Millais Carpenter Shop"],
    ("john_everett_millais", "Order"): ["Millais Order Release 1853", "John Everett Millais Order Release"],
    ("john_everett_millais", "Peace"): ["Millais Peace Concluded 1856"],
    ("john_everett_millais", "Other"): ["Millais Autumn Leaves painting", "John Everett Millais painting"],
    # Orozco
    ("jose_clemente_orozco", "Epic"): ["Orozco Epic American Civilization Dartmouth", "Orozco mural Baker Library"],
}

TOPICS = {
    "Giovanni Battista Tiepolo": "giovanni_battista_tiepolo",
    "Gustav Klimt": "gustav_klimt",
    "Gustave Moreau": "gustave_moreau",
    "Hannah Höch": "hannah_hoch",
    "Hans Memling": "hans_memling",
    "Henry Ossawa Tanner": "henry_ossawa_tanner",
    "Hokusai": "hokusai",
    "Hugo van der Goes": "hugo_van_der_goes",
    "Ilya Repin": "ilya_repin",
    "Jacob Epstein": "jacob_epstein",
    "Jacob Lawrence": "jacob_lawrence",
    "Jacopo Pontormo": "jacopo_pontormo",
    "James Ensor": "james_ensor",
    "Jan Steen": "jan_steen",
    "Jean-Honoré Fragonard": "jean-honoré_fragonard",
    "John Everett Millais": "john_everett_millais",
    "José Clemente Orozco": "jose_clemente_orozco",
}

# Wiki link overrides for copyrighted/hard-to-find works
WIKI_OVERRIDES = {
    ("hannah_hoch", "Ethnographic"): "https://en.wikipedia.org/wiki/Hannah_H%C3%B6ch",
    ("jacob_lawrence", "Migration"): "https://en.wikipedia.org/wiki/Migration_Series",
    ("jacob_lawrence", "John Brown"): "https://en.wikipedia.org/wiki/Jacob_Lawrence",
    ("jacob_lawrence", "Toussaint"): "https://en.wikipedia.org/wiki/Jacob_Lawrence",
    ("jacob_lawrence", "Other"): "https://en.wikipedia.org/wiki/Jacob_Lawrence",
    ("jose_clemente_orozco", "Epic"): "https://en.wikipedia.org/wiki/The_Epic_of_American_Civilization",
}


def find_image(slug, work_name, artist_name):
    clean = clean_work_name(work_name)
    parts = [p.strip() for p in clean.split('/')]

    queries = []
    for (s, sub), qs in CUSTOM_QUERIES.items():
        if s == slug and sub.lower() in work_name.lower():
            queries = list(qs)
            break
    if not queries:
        for part in parts[:2]:
            queries.append(f"{part} {artist_name}")

    for query in queries:
        print(f"      Q: {query}", flush=True)
        results = search_and_get_thumbs(query)  # Just 2 API calls total

        for fname, thumb_url in results:
            print(f"        -> {fname[:70]}...", flush=True)
            if thumb_url:
                return thumb_url

    return None


def process_topic(artist_name, slug):
    json_path = OUTPUT_DIR / f"{slug}_analysis.json"
    if not json_path.exists():
        print(f"  FILE NOT FOUND: {json_path}", flush=True)
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
        print(f"    {clean}", flush=True)

        thumb_url = find_image(slug, work_name, artist_name)

        if thumb_url:
            print(f"    FOUND: {thumb_url[:80]}...", flush=True)
            work["images"] = [{"url": thumb_url, "caption": clean}]

            # Add back images to basic cards
            for card in cards:
                if card.get("work") == work_name and card.get("type") == "basic":
                    card_imgs = card.get("images", [])
                    if not any(img.get("url") for img in card_imgs):
                        card["images"] = [{"url": thumb_url, "side": "back"}]

            # Add image recognition card
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
            if not existing or not any(img.get("url") or img.get("link") for img in existing):
                # Find wiki override
                wiki_link = None
                for (s, sub), link in WIKI_OVERRIDES.items():
                    if s == slug and sub.lower() in work_name.lower():
                        wiki_link = link
                        break
                if not wiki_link:
                    wiki_link = make_wiki_link(work_name, artist_name)
                work["images"] = [{"url": "", "link": wiki_link, "caption": clean}]
                modified = True
            print(f"      NOT FOUND", flush=True)

    if modified:
        analysis["cards"] = cards
        with open(json_path, 'w') as f:
            json.dump(analysis, f, indent=2, ensure_ascii=False)
        print(f"  SAVED: {json_path}", flush=True)
    else:
        print(f"  No changes needed", flush=True)

    return modified


def main():
    print("=== Batch B image search ===\n", flush=True)
    changed = 0
    for artist_name, slug in TOPICS.items():
        print(f"\n--- {artist_name} ---", flush=True)
        if process_topic(artist_name, slug):
            changed += 1
    print(f"\n=== Done! Modified {changed} files ===", flush=True)


if __name__ == "__main__":
    main()
