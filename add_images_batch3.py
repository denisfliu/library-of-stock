"""
Batch image finder v3 - uses only Commons API to avoid double rate limiting.
"""
import requests
import json
import time
import sys
from pathlib import Path

OUTPUT_DIR = Path("/home/laufey/code/stock/output")
HEADERS = {'User-Agent': 'StockQB/1.0 (contact: studytool@example.com)'}
DELAY = 2.5  # seconds between API calls

def api_get(url, params, max_retries=3):
    for attempt in range(max_retries):
        try:
            r = requests.get(url, params=params, headers=HEADERS, timeout=20)
            if r.status_code == 429:
                wait = 60 * (attempt + 1)
                print(f"    Rate limited, waiting {wait}s...", flush=True)
                time.sleep(wait)
                continue
            if r.status_code == 200:
                return r.json()
            print(f"    HTTP {r.status_code}, retry {attempt+1}", flush=True)
        except Exception as e:
            print(f"    Error: {e}, retry {attempt+1}", flush=True)
        time.sleep(10)
    return None

def search_and_get_thumb(query, width=500):
    """Search commons and get thumbnail in minimal API calls."""
    # Step 1: Search
    data = api_get('https://commons.wikimedia.org/w/api.php', {
        'action': 'query', 'list': 'search', 'srsearch': query,
        'srnamespace': 6, 'srlimit': 5, 'format': 'json'
    })
    time.sleep(DELAY)

    if not data:
        return []

    results = data.get('query', {}).get('search', [])
    if not results:
        return []

    # Filter out non-image files
    filenames = []
    for item in results:
        fn = item['title'].replace('File:', '')
        if not any(fn.lower().endswith(ext) for ext in ['.svg', '.ogg', '.ogv', '.wav', '.mp3', '.webm', '.pdf']):
            filenames.append(fn)

    if not filenames:
        return []

    # Step 2: Get thumbnails for all results in ONE call
    titles = '|'.join(f'File:{fn}' for fn in filenames[:5])
    data2 = api_get('https://commons.wikimedia.org/w/api.php', {
        'action': 'query', 'titles': titles, 'prop': 'imageinfo',
        'iiprop': 'url', 'iiurlwidth': width, 'format': 'json'
    })
    time.sleep(DELAY)

    if not data2:
        return []

    pages = data2.get('query', {}).get('pages', {})
    results_with_thumbs = []
    for page in pages.values():
        title = page.get('title', '').replace('File:', '')
        info = page.get('imageinfo', [{}])[0]
        thumb = info.get('thumburl')
        if thumb and title:
            results_with_thumbs.append((title, thumb))

    return results_with_thumbs

def verify_url(url):
    try:
        r = requests.head(url, headers=HEADERS, timeout=10, allow_redirects=True)
        time.sleep(1)
        return r.status_code == 200
    except:
        time.sleep(1)
        return False

def find_image(search_queries, artist_name, work_name):
    """Try search queries, validate results match the artist/work."""
    artist_parts = [p.lower() for p in artist_name.split() if len(p) > 3]
    work_simple = work_name.split("(")[0].strip().lower()
    work_parts = [p.lower() for p in work_simple.split() if len(p) > 3]

    for query in search_queries:
        print(f"    Searching: {query}", flush=True)
        results = search_and_get_thumb(query)

        for fn, thumb_url in results:
            fn_lower = fn.lower()

            # Validate filename relates to artist or work
            artist_match = any(p in fn_lower for p in artist_parts)
            work_match = any(p in fn_lower for p in work_parts)

            if not artist_match and not work_match:
                continue

            if verify_url(thumb_url):
                print(f"    FOUND: {fn}", flush=True)
                return thumb_url

    return None

def make_wiki_link(artist_name):
    return f"https://en.wikipedia.org/wiki/{artist_name.replace(' ', '_')}"

TASKS = [
    ("giovanni_battista_tiepolo", "Giovanni Battista Tiepolo", [
        ("Wurzburg Residence Frescoes (Apollo and the Four Continents)",
         ["Tiepolo Apollo Continents Wurzburg", "Tiepolo Wurzburg Residence ceiling", "Giambattista Tiepolo Wurzburg"],
         "Painting", None),
        ("Royal Palace of Madrid (Apotheosis of the Spanish Monarchy)",
         ["Tiepolo Apotheosis Spanish Monarchy", "Tiepolo Royal Palace Madrid", "Giambattista Tiepolo Madrid"],
         "Painting", None),
        ("Palazzo Labia (Cleopatra and Marc Antony series)",
         ["Tiepolo Banquet Cleopatra", "Giambattista Tiepolo Cleopatra", "Tiepolo Palazzo Labia"],
         "Painting", None),
        ("Other Works and Prints",
         ["Tiepolo Immaculate Conception painting", "Giambattista Tiepolo painting"],
         "Painting", None),
    ]),
    ("gustav_klimt", "Gustav Klimt", [
        ("Danae (1907-1908)",
         ["Gustav Klimt Danae", "Klimt Danae 1907 painting"],
         "Painting", None),
        ("Stoclet Frieze / Palais Stoclet",
         ["Klimt Stoclet Frieze", "Klimt Tree Life Stoclet", "Gustav Klimt Expectation"],
         "Painting", None),
    ]),
    ("gustave_moreau", "Gustave Moreau", [
        ("The Life of Humanity",
         ["Gustave Moreau Life Humanity", "Gustave Moreau polyptych"],
         "Painting", None),
        ("Les Licornes (The Unicorns, c. 1885)",
         ["Gustave Moreau Unicorns", "Moreau Les Licornes", "Gustave Moreau licornes"],
         "Painting", None),
    ]),
    ("hannah_hoch", "Hannah Höch", [
        ("From an Ethnographic Museum (series)",
         ["Hannah Höch Ethnographic Museum", "Hannah Hoch Ethnographic Museum", "Hannah Höch photomontage"],
         "Painting", "https://en.wikipedia.org/wiki/Hannah_H%C3%B6ch"),
    ]),
    ("hans_memling", "Hans Memling", [
        ("The Last Judgment",
         ["Hans Memling Last Judgment", "Memling Last Judgment triptych Gdansk"],
         "Painting", None),
        ("Shrine of St. Ursula",
         ["Hans Memling Shrine Ursula", "Memling St Ursula shrine Bruges"],
         "Painting", None),
        ("Mystic Marriage of St. Catherine",
         ["Memling Mystic Marriage Saint Catherine", "Hans Memling Catherine painting"],
         "Painting", None),
        ("Scenes from the Passion of Christ",
         ["Hans Memling Scenes Passion Christ", "Memling Passion painting"],
         "Painting", None),
        ("Other Works",
         ["Hans Memling Donne Triptych", "Memling portrait painting"],
         "Painting", None),
    ]),
    ("henry_ossawa_tanner", "Henry Ossawa Tanner", [
        ("The Banjo Lesson (1893)",
         ["Henry Ossawa Tanner Banjo Lesson"],
         "Painting", None),
        ("The Thankful Poor",
         ["Henry Ossawa Tanner Thankful Poor"],
         "Painting", None),
        ("The Annunciation (1898)",
         ["Henry Ossawa Tanner Annunciation"],
         "Painting", None),
        ("Other Religious Works",
         ["Henry Ossawa Tanner Daniel Lions", "Henry Ossawa Tanner Nicodemus"],
         "Painting", None),
    ]),
    ("hokusai", "Hokusai", [
        ("Thirty-Six Views of Mount Fuji (General)",
         ["Hokusai Thirty-six Views Fuji", "Katsushika Hokusai Fuji"],
         "Painting", None),
        ("The Great Wave off Kanagawa",
         ["Great Wave Kanagawa Hokusai", "Hokusai Great Wave"],
         "Painting", None),
        ("Fine Wind, Clear Morning (Red Fuji)",
         ["Hokusai Red Fuji", "Fine Wind Clear Morning Hokusai"],
         "Painting", None),
        ("Dream of the Fisherman's Wife (Shunga/Erotica)",
         ["Hokusai Dream Fisherman Wife", "Tako to Ama Hokusai"],
         "Painting", None),
        ("Hokusai Manga",
         ["Hokusai Manga illustration", "Hokusai Manga sketches"],
         "Painting", None),
        ("Quick Lessons in Simplified Drawing",
         ["Hokusai Quick Lessons Drawing", "Hokusai Ryakuga"],
         "Painting", None),
        ("One Hundred Ghost Stories",
         ["Hokusai Hyaku Monogatari", "Hokusai Hundred Ghost Tales"],
         "Painting", None),
        ("Oceans of Wisdom Series",
         ["Hokusai Chie no umi", "Hokusai Oceans Wisdom whaling"],
         "Painting", None),
        ("Other Works",
         ["Hokusai Phoenix painting", "Katsushika Hokusai painting"],
         "Painting", None),
    ]),
    ("hugo_van_der_goes", "Hugo van der Goes", [
        ("Portinari Altarpiece (Adoration of the Shepherds)",
         ["Hugo van der Goes Portinari Altarpiece", "Portinari Triptych Hugo Goes"],
         "Painting", None),
        ("Monforte Altarpiece",
         ["Hugo van der Goes Monforte Altarpiece", "Hugo van der Goes Adoration Magi Berlin"],
         "Painting", None),
    ]),
    ("ilya_repin", "Ilya Repin", [
        ("Religious Procession in Kursk Province (1880-1883)",
         ["Repin Religious Procession Kursk", "Ilya Repin procession Kursk"],
         "Painting", None),
    ]),
    ("jacob_epstein", "Jacob Epstein", [
        ("BMA Building Sculptures (1908)",
         ["Jacob Epstein BMA sculptures", "Epstein British Medical Association"],
         "Sculpture", None),
        ("Jacob and the Angel",
         ["Jacob Epstein Jacob Angel", "Epstein Jacob Angel sculpture"],
         "Sculpture", None),
    ]),
    ("jacob_lawrence", "Jacob Lawrence", [
        ("Migration Series (1940–1941)",
         ["Jacob Lawrence Migration Series", "Lawrence Migration panel"],
         "Painting", "https://en.wikipedia.org/wiki/Migration_Series"),
        ("The Legend of John Brown (1941)",
         ["Jacob Lawrence John Brown legend", "Jacob Lawrence John Brown"],
         "Painting", "https://en.wikipedia.org/wiki/Jacob_Lawrence"),
        ("Toussaint Louverture Series",
         ["Jacob Lawrence Toussaint Louverture"],
         "Painting", "https://en.wikipedia.org/wiki/Jacob_Lawrence"),
        ("Other Works",
         ["Jacob Lawrence Builders", "Jacob Lawrence painting"],
         "Painting", "https://en.wikipedia.org/wiki/Jacob_Lawrence"),
    ]),
    ("jacopo_pontormo", "Jacopo Pontormo", [
        ("Vertumnus and Pomona (lunette)",
         ["Pontormo Vertumnus Pomona", "Pontormo lunette Poggio Caiano"],
         "Painting", None),
    ]),
    ("james_ensor", "James Ensor", [
        ("Skeletons Fighting Over a Pickled Herring",
         ["James Ensor Skeletons Herring", "Ensor squelettes hareng"],
         "Painting", None),
    ]),
    ("jan_steen", "Jan Steen", [
        ("The Merry Family",
         ["Jan Steen Merry Family", "Jan Steen vrolijke huisgezin"],
         "Painting", None),
    ]),
    ("jean-honoré_fragonard", "Jean-Honoré Fragonard", [
        ("The Swing (1767)",
         ["Fragonard The Swing", "Fragonard Escarpolette"],
         "Painting", None),
        ("The Progress of Love (1771–1773)",
         ["Fragonard Progress of Love", "Fragonard Pursuit Love Frick"],
         "Painting", None),
        ("The Bolt (Le Verrou)",
         ["Fragonard Le Verrou", "Fragonard The Bolt"],
         "Painting", None),
        ("Other Works",
         ["Fragonard The Reader", "Jean-Honoré Fragonard painting"],
         "Painting", None),
    ]),
    ("john_everett_millais", "John Everett Millais", [
        ("Ophelia (1851–1852)",
         ["Millais Ophelia painting", "John Everett Millais Ophelia"],
         "Painting", None),
        ("Christ in the House of His Parents (1849–1850)",
         ["Millais Christ House Parents", "Millais Carpenter Shop"],
         "Painting", None),
        ("The Order of Release (1853)",
         ["Millais Order Release", "John Everett Millais Order Release"],
         "Painting", None),
        ("Peace Concluded (1856)",
         ["Millais Peace Concluded 1856"],
         "Painting", None),
        ("Other Works",
         ["Millais Autumn Leaves painting", "Millais Bubbles painting"],
         "Painting", None),
    ]),
    ("jose_clemente_orozco", "José Clemente Orozco", [
        ("The Epic of American Civilization (Baker Library, Dartmouth)",
         ["Orozco Epic American Civilization", "Orozco Dartmouth mural", "José Clemente Orozco mural"],
         "Painting", "https://en.wikipedia.org/wiki/The_Epic_of_American_Civilization"),
    ]),
]


def clean_bad_images(data, works_to_find):
    """Remove images/cards added in previous runs for these works."""
    work_names = {w[0] for w in works_to_find}

    for w in data.get("works", []):
        if w["name"] in work_names:
            w.pop("images", None)

    # Remove image recognition cards added for these works
    data["cards"] = [
        c for c in data.get("cards", [])
        if not (c.get("type") == "image" and c.get("work") in work_names)
    ]

    # Remove images from basic cards for these works
    for c in data.get("cards", []):
        if c.get("work") in work_names and c.get("type") == "basic":
            c.pop("images", None)


def process_all():
    total_found = 0
    total_fallback = 0

    for slug, artist_name, works_to_find in TASKS:
        json_path = OUTPUT_DIR / f"{slug}_analysis.json"
        print(f"\n{'='*60}", flush=True)
        print(f"Processing: {artist_name}", flush=True)
        print(f"{'='*60}", flush=True)

        with open(json_path) as f:
            data = json.load(f)

        clean_bad_images(data, works_to_find)
        modified = False

        for work_name, search_queries, indicator, wiki_link_override in works_to_find:
            print(f"\n  Work: {work_name}", flush=True)

            work_obj = None
            for w in data.get("works", []):
                if w["name"] == work_name:
                    work_obj = w
                    break

            if not work_obj:
                print(f"    WARNING: Not found in JSON!", flush=True)
                continue

            caption = work_name.split(" (")[0] if "(" in work_name else work_name
            thumb_url = find_image(search_queries, artist_name, work_name)

            if thumb_url:
                work_obj["images"] = [{"url": thumb_url, "caption": caption}]
                print(f"    Added image: {thumb_url[:80]}...", flush=True)
                total_found += 1

                for card in data.get("cards", []):
                    if card.get("work") == work_name and card.get("type") == "basic":
                        card["images"] = [{"url": thumb_url, "side": "back"}]

                back_text = f"{caption} ({artist_name})"
                image_card = {
                    "type": "image",
                    "indicator": indicator,
                    "front": "",
                    "back": back_text,
                    "work": work_name,
                    "frequency": 0,
                    "tags": [],
                    "images": [{"url": thumb_url, "side": "front"}]
                }
                data.setdefault("cards", []).append(image_card)
                print(f"    Added image recognition card", flush=True)
            else:
                wiki_link = wiki_link_override or make_wiki_link(artist_name)
                work_obj["images"] = [{"url": "", "link": wiki_link, "caption": caption}]
                print(f"    Fallback: wiki link", flush=True)
                total_fallback += 1

            modified = True

        if modified:
            with open(json_path, "w") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            print(f"\n  Saved: {json_path.name}", flush=True)

    print(f"\n\nSUMMARY: {total_found} images found, {total_fallback} fallbacks", flush=True)

if __name__ == "__main__":
    process_all()
