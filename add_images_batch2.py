"""
Batch image finder v2 - with retry logic and longer delays.
"""
import requests
import json
import time
from pathlib import Path

OUTPUT_DIR = Path("/home/laufey/code/stock/output")
HEADERS = {'User-Agent': 'StockQB/1.0 (contact: studytool@example.com)'}
DELAY = 2.0  # seconds between API calls

def api_get(url, params, max_retries=3):
    for attempt in range(max_retries):
        try:
            r = requests.get(url, params=params, headers=HEADERS, timeout=20)
            if r.status_code == 429:
                wait = 30 * (attempt + 1)
                print(f"    Rate limited, waiting {wait}s...")
                time.sleep(wait)
                continue
            if r.status_code == 200:
                return r.json()
            print(f"    HTTP {r.status_code}, retry {attempt+1}")
        except Exception as e:
            print(f"    Error: {e}, retry {attempt+1}")
        time.sleep(5)
    return None

def search_commons(query):
    data = api_get('https://commons.wikimedia.org/w/api.php', {
        'action': 'query', 'list': 'search', 'srsearch': query,
        'srnamespace': 6, 'srlimit': 5, 'format': 'json'
    })
    time.sleep(DELAY)
    if data:
        return [item['title'].replace('File:', '') for item in data.get('query', {}).get('search', [])]
    return []

def get_wiki_thumb(filename, width=500):
    data = api_get('https://en.wikipedia.org/w/api.php', {
        'action': 'query', 'titles': f'File:{filename}', 'prop': 'imageinfo',
        'iiprop': 'url', 'iiurlwidth': width, 'format': 'json'
    })
    time.sleep(DELAY)
    if data:
        pages = data.get('query', {}).get('pages', {})
        for page in pages.values():
            return page.get('imageinfo', [{}])[0].get('thumburl')
    return None

def verify_url(url):
    try:
        r = requests.head(url, headers=HEADERS, timeout=10, allow_redirects=True)
        time.sleep(DELAY)
        return r.status_code == 200
    except:
        time.sleep(DELAY)
        return False

def find_image(search_queries):
    for query in search_queries:
        print(f"    Searching: {query}")
        filenames = search_commons(query)
        for fn in filenames:
            if any(fn.lower().endswith(ext) for ext in ['.svg', '.ogg', '.ogv', '.wav', '.mp3', '.webm']):
                continue
            thumb = get_wiki_thumb(fn)
            if thumb and verify_url(thumb):
                print(f"    FOUND: {fn}")
                return thumb, fn
    return None, None

def make_wiki_link(work_name, artist_name):
    artist_slug = artist_name.replace(' ', '_')
    return f"https://en.wikipedia.org/wiki/{artist_slug}"


# All tasks - same as before
TASKS = [
    ("giovanni_battista_tiepolo", "Giovanni Battista Tiepolo", [
        ("Wurzburg Residence Frescoes (Apollo and the Four Continents)",
         ["Tiepolo Apollo Four Continents Wurzburg", "Tiepolo Wurzburg Residence ceiling", "Giovanni Battista Tiepolo Wurzburg"],
         "Painting", None),
        ("Royal Palace of Madrid (Apotheosis of the Spanish Monarchy)",
         ["Tiepolo Apotheosis Spanish Monarchy", "Tiepolo Royal Palace Madrid", "Giovanni Battista Tiepolo Madrid ceiling"],
         "Painting", None),
        ("Palazzo Labia (Cleopatra and Marc Antony series)",
         ["Tiepolo Banquet Cleopatra", "Giambattista Tiepolo Cleopatra", "Tiepolo Palazzo Labia"],
         "Painting", None),
        ("Other Works and Prints",
         ["Tiepolo Immaculate Conception", "Giovanni Battista Tiepolo painting"],
         "Painting", None),
    ]),
    ("gustav_klimt", "Gustav Klimt", [
        ("Danae (1907-1908)",
         ["Gustav Klimt Danae", "Klimt Danae 1907"],
         "Painting", None),
        ("Stoclet Frieze / Palais Stoclet",
         ["Klimt Stoclet Frieze", "Klimt Tree Life Stoclet", "Gustav Klimt Expectation"],
         "Painting", None),
    ]),
    ("gustave_moreau", "Gustave Moreau", [
        ("The Life of Humanity",
         ["Gustave Moreau Life Humanity polyptych", "Gustave Moreau polyptych"],
         "Painting", None),
        ("Les Licornes (The Unicorns, c. 1885)",
         ["Gustave Moreau Unicorns", "Moreau Les Licornes", "Gustave Moreau licornes painting"],
         "Painting", None),
    ]),
    ("hannah_hoch", "Hannah Höch", [
        ("From an Ethnographic Museum (series)",
         ["Hannah Höch Ethnographic Museum", "Hannah Hoch Ethnographic", "Hannah Höch photomontage"],
         "Painting", "https://en.wikipedia.org/wiki/Hannah_H%C3%B6ch"),
    ]),
    ("hans_memling", "Hans Memling", [
        ("The Last Judgment",
         ["Hans Memling Last Judgment triptych", "Memling Last Judgment Gdansk", "Hans Memling Last Judgement"],
         "Painting", None),
        ("Shrine of St. Ursula",
         ["Hans Memling Shrine Ursula", "Memling Shrine Saint Ursula Bruges", "Memling Ursula reliquary"],
         "Painting", None),
        ("Mystic Marriage of St. Catherine",
         ["Memling Mystic Marriage Saint Catherine", "Hans Memling Catherine triptych"],
         "Painting", None),
        ("Scenes from the Passion of Christ",
         ["Hans Memling Scenes Passion", "Memling Passion Christ Turin"],
         "Painting", None),
        ("Other Works",
         ["Hans Memling Donne Triptych", "Memling Portrait Man Red Hat"],
         "Painting", None),
    ]),
    ("henry_ossawa_tanner", "Henry Ossawa Tanner", [
        ("The Banjo Lesson (1893)",
         ["Henry Ossawa Tanner Banjo Lesson", "Tanner Banjo Lesson 1893"],
         "Painting", None),
        ("The Thankful Poor",
         ["Henry Ossawa Tanner Thankful Poor"],
         "Painting", None),
        ("The Annunciation (1898)",
         ["Henry Ossawa Tanner Annunciation", "Tanner Annunciation painting 1898"],
         "Painting", None),
        ("Other Religious Works",
         ["Henry Ossawa Tanner Daniel Lions Den", "Henry Ossawa Tanner Nicodemus"],
         "Painting", None),
    ]),
    ("hokusai", "Hokusai", [
        ("Thirty-Six Views of Mount Fuji (General)",
         ["Hokusai Thirty-six Views Mount Fuji", "Katsushika Hokusai Fuji views"],
         "Painting", None),
        ("The Great Wave off Kanagawa",
         ["Great Wave Kanagawa Hokusai", "Hokusai Great Wave woodblock"],
         "Painting", None),
        ("Fine Wind, Clear Morning (Red Fuji)",
         ["Hokusai Red Fuji", "Hokusai Fine Wind Clear Morning", "South Wind Clear Sky Hokusai"],
         "Painting", None),
        ("Dream of the Fisherman's Wife (Shunga/Erotica)",
         ["Hokusai Dream Fisherman Wife", "Tako to Ama Hokusai", "Hokusai octopus shunga"],
         "Painting", None),
        ("Hokusai Manga",
         ["Hokusai Manga illustration", "Hokusai Manga volume sketch"],
         "Painting", None),
        ("Quick Lessons in Simplified Drawing",
         ["Hokusai Ryakuga hayashinan", "Hokusai Quick Lessons Drawing"],
         "Painting", None),
        ("One Hundred Ghost Stories",
         ["Hokusai Hyaku Monogatari", "Hokusai Hundred Ghost Stories", "Hokusai ghost Oiwa"],
         "Painting", None),
        ("Oceans of Wisdom Series",
         ["Hokusai Chie no umi", "Hokusai Oceans Wisdom", "Hokusai whaling ocean"],
         "Painting", None),
        ("Other Works",
         ["Hokusai Phoenix painting", "Hokusai Dragon ceiling Obuse"],
         "Painting", None),
    ]),
    ("hugo_van_der_goes", "Hugo van der Goes", [
        ("Portinari Altarpiece (Adoration of the Shepherds)",
         ["Hugo van der Goes Portinari Altarpiece", "Portinari Triptych Hugo", "Hugo van der Goes Adoration Shepherds"],
         "Painting", None),
        ("Monforte Altarpiece",
         ["Hugo van der Goes Monforte Altarpiece", "Hugo van der Goes Adoration Magi Monforte"],
         "Painting", None),
    ]),
    ("ilya_repin", "Ilya Repin", [
        ("Religious Procession in Kursk Province (1880-1883)",
         ["Repin Religious Procession Kursk", "Ilya Repin Krestny Khod Kursk", "Repin procession Kursk painting"],
         "Painting", None),
    ]),
    ("jacob_epstein", "Jacob Epstein", [
        ("BMA Building Sculptures (1908)",
         ["Jacob Epstein BMA sculptures", "Epstein British Medical Association statues", "Epstein Strand sculptures 1908"],
         "Sculpture", None),
        ("Jacob and the Angel",
         ["Jacob Epstein Jacob Angel sculpture", "Epstein Jacob Angel alabaster"],
         "Sculpture", None),
    ]),
    ("jacob_lawrence", "Jacob Lawrence", [
        ("Migration Series (1940–1941)",
         ["Jacob Lawrence Migration Series", "Lawrence Migration panel painting"],
         "Painting", "https://en.wikipedia.org/wiki/Migration_Series"),
        ("The Legend of John Brown (1941)",
         ["Jacob Lawrence John Brown legend", "Jacob Lawrence John Brown series"],
         "Painting", "https://en.wikipedia.org/wiki/Jacob_Lawrence"),
        ("Toussaint Louverture Series",
         ["Jacob Lawrence Toussaint Louverture", "Jacob Lawrence Toussaint series"],
         "Painting", "https://en.wikipedia.org/wiki/Jacob_Lawrence"),
        ("Other Works",
         ["Jacob Lawrence Builders painting", "Jacob Lawrence painting"],
         "Painting", "https://en.wikipedia.org/wiki/Jacob_Lawrence"),
    ]),
    ("jacopo_pontormo", "Jacopo Pontormo", [
        ("Vertumnus and Pomona (lunette)",
         ["Pontormo Vertumnus Pomona", "Pontormo lunette Poggio Caiano", "Jacopo Pontormo Vertumnus"],
         "Painting", None),
    ]),
    ("james_ensor", "James Ensor", [
        ("Skeletons Fighting Over a Pickled Herring",
         ["Ensor Skeletons Fighting Herring", "James Ensor squelettes hareng", "Ensor Skeletons Pickled Herring"],
         "Painting", None),
    ]),
    ("jan_steen", "Jan Steen", [
        ("The Merry Family",
         ["Jan Steen Merry Family", "Jan Steen vrolijke huisgezin", "Steen Merry Family Rijksmuseum"],
         "Painting", None),
    ]),
    ("jean-honoré_fragonard", "Jean-Honoré Fragonard", [
        ("The Swing (1767)",
         ["Fragonard The Swing", "Fragonard Escarpolette painting", "Happy Accidents Swing Fragonard"],
         "Painting", None),
        ("The Progress of Love (1771–1773)",
         ["Fragonard Progress Love painting", "Fragonard Meeting Love Frick"],
         "Painting", None),
        ("The Bolt (Le Verrou)",
         ["Fragonard Le Verrou", "Fragonard The Bolt painting"],
         "Painting", None),
        ("Other Works",
         ["Fragonard The Reader painting", "Jean-Honoré Fragonard painting"],
         "Painting", None),
    ]),
    ("john_everett_millais", "John Everett Millais", [
        ("Ophelia (1851–1852)",
         ["Millais Ophelia painting", "John Everett Millais Ophelia"],
         "Painting", None),
        ("Christ in the House of His Parents (1849–1850)",
         ["Millais Christ House Parents", "Millais Carpenter Shop painting"],
         "Painting", None),
        ("The Order of Release (1853)",
         ["Millais Order Release 1853", "John Everett Millais Order Release"],
         "Painting", None),
        ("Peace Concluded (1856)",
         ["Millais Peace Concluded 1856", "John Everett Millais Peace Concluded"],
         "Painting", None),
        ("Other Works",
         ["Millais Bubbles painting", "Millais Autumn Leaves"],
         "Painting", None),
    ]),
    ("jose_clemente_orozco", "José Clemente Orozco", [
        ("The Epic of American Civilization (Baker Library, Dartmouth)",
         ["Orozco Epic American Civilization", "Orozco Dartmouth mural Baker", "José Clemente Orozco mural"],
         "Painting", "https://en.wikipedia.org/wiki/The_Epic_of_American_Civilization"),
    ]),
]


def clean_bad_images(data, works_to_find):
    """Remove images/cards that were incorrectly added in previous run."""
    work_names = [w[0] for w in works_to_find]
    
    for w in data.get("works", []):
        if w["name"] in work_names:
            imgs = w.get("images", [])
            # Remove fallback links and wrong images from previous run
            if imgs:
                # Keep only images that have valid URLs (not empty/fallback)
                # But we're re-processing, so just clear them
                w["images"] = []
    
    # Remove image recognition cards that were incorrectly added
    data["cards"] = [
        c for c in data.get("cards", [])
        if not (c.get("type") == "image" and c.get("work") in work_names)
    ]
    
    # Remove back images from basic cards for these works
    for c in data.get("cards", []):
        if c.get("work") in work_names and c.get("type") == "basic":
            c.pop("images", None)


def process_all():
    total_found = 0
    total_fallback = 0
    
    for slug, artist_name, works_to_find in TASKS:
        json_path = OUTPUT_DIR / f"{slug}_analysis.json"
        print(f"\n{'='*60}")
        print(f"Processing: {artist_name}")
        print(f"{'='*60}")
        
        with open(json_path) as f:
            data = json.load(f)
        
        # Clean up any bad images from previous run
        clean_bad_images(data, works_to_find)
        
        modified = False
        
        for work_name, search_queries, indicator, wiki_link_override in works_to_find:
            print(f"\n  Work: {work_name}")
            
            work_obj = None
            for w in data.get("works", []):
                if w["name"] == work_name:
                    work_obj = w
                    break
            
            if not work_obj:
                print(f"    WARNING: Work not found in JSON!")
                continue
            
            # Search for image
            thumb_url, filename = find_image(search_queries)
            
            # Validate: filename should relate to the artist/work
            if thumb_url and filename:
                fn_lower = filename.lower()
                artist_parts = artist_name.lower().split()
                # Basic sanity: at least one part of artist name or work name in filename
                work_simple = work_name.split("(")[0].strip().lower()
                work_parts = [p for p in work_simple.split() if len(p) > 3]
                
                artist_match = any(p in fn_lower for p in artist_parts if len(p) > 3)
                work_match = any(p in fn_lower for p in work_parts if len(p) > 3)
                
                if not artist_match and not work_match:
                    print(f"    WARNING: Filename doesn't match artist/work, skipping: {filename}")
                    thumb_url = None
            
            caption = work_name.split(" (")[0] if "(" in work_name else work_name
            
            if thumb_url:
                work_obj["images"] = [{"url": thumb_url, "caption": caption}]
                print(f"    Added image: {thumb_url[:80]}...")
                total_found += 1
                
                # Update basic cards for this work
                for card in data.get("cards", []):
                    if card.get("work") == work_name and card.get("type") == "basic":
                        card["images"] = [{"url": thumb_url, "side": "back"}]
                
                # Add image recognition card
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
                print(f"    Added image recognition card")
                modified = True
            else:
                wiki_link = wiki_link_override or make_wiki_link(work_name, artist_name)
                work_obj["images"] = [{"url": "", "link": wiki_link, "caption": caption}]
                print(f"    Fallback: wiki link")
                total_fallback += 1
                modified = True
        
        if modified:
            with open(json_path, "w") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            print(f"\n  Saved: {json_path.name}")
    
    print(f"\n\nSUMMARY: {total_found} images found, {total_fallback} fallbacks")

if __name__ == "__main__":
    process_all()
