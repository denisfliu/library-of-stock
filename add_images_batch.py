"""
Batch image finder for quizbowl study tool.
Searches Wikimedia Commons for artwork images, verifies URLs, and updates analysis JSONs.
"""
import requests
import json
import time
import re
from pathlib import Path

OUTPUT_DIR = Path("/home/laufey/code/stock/output")
HEADERS = {'User-Agent': 'StockQB/1.0'}

def search_commons(query):
    url = 'https://commons.wikimedia.org/w/api.php'
    params = {'action': 'query', 'list': 'search', 'srsearch': query, 'srnamespace': 6, 'srlimit': 5, 'format': 'json'}
    try:
        r = requests.get(url, params=params, headers=HEADERS, timeout=15)
        results = [item['title'].replace('File:', '') for item in r.json().get('query', {}).get('search', [])]
    except Exception as e:
        print(f"    Search error: {e}")
        results = []
    time.sleep(0.5)
    return results

def get_wiki_thumb(filename, width=500):
    url = 'https://en.wikipedia.org/w/api.php'
    params = {'action': 'query', 'titles': f'File:{filename}', 'prop': 'imageinfo', 'iiprop': 'url', 'iiurlwidth': width, 'format': 'json'}
    try:
        r = requests.get(url, params=params, headers=HEADERS, timeout=15)
        pages = r.json().get('query', {}).get('pages', {})
        for page in pages.values():
            info = page.get('imageinfo', [{}])[0]
            thumb = info.get('thumburl')
            time.sleep(0.5)
            return thumb
    except Exception as e:
        print(f"    Thumb error: {e}")
    time.sleep(0.5)
    return None

def verify_url(url):
    try:
        r = requests.head(url, headers=HEADERS, timeout=10, allow_redirects=True)
        time.sleep(0.5)
        return r.status_code == 200
    except:
        time.sleep(0.5)
        return False

def find_image(search_queries):
    """Try multiple search queries, return first verified URL or None."""
    for query in search_queries:
        print(f"    Searching: {query}")
        filenames = search_commons(query)
        for fn in filenames:
            # Skip SVG, audio, video files
            if any(fn.lower().endswith(ext) for ext in ['.svg', '.ogg', '.ogv', '.wav', '.mp3', '.webm']):
                continue
            thumb = get_wiki_thumb(fn)
            if thumb and verify_url(thumb):
                print(f"    FOUND: {fn}")
                return thumb, fn
    return None, None

def make_wiki_link(work_name, artist_name):
    """Generate a plausible Wikipedia link for fallback."""
    # Try artist page
    artist_slug = artist_name.replace(' ', '_')
    return f"https://en.wikipedia.org/wiki/{artist_slug}"

# Define all search tasks
# Format: (slug, artist_name, [(work_name, [search_queries], indicator, wiki_link_override)])
TASKS = [
    ("giovanni_battista_tiepolo", "Giovanni Battista Tiepolo", [
        ("Wurzburg Residence Frescoes (Apollo and the Four Continents)", 
         ["Tiepolo Apollo Four Continents Wurzburg", "Tiepolo Wurzburg Residence fresco", "Tiepolo Apollo continents"],
         "Painting", None),
        ("Royal Palace of Madrid (Apotheosis of the Spanish Monarchy)",
         ["Tiepolo Apotheosis Spanish Monarchy Madrid", "Tiepolo Royal Palace Madrid ceiling"],
         "Painting", None),
        ("Palazzo Labia (Cleopatra and Marc Antony series)",
         ["Tiepolo Banquet of Cleopatra", "Tiepolo Palazzo Labia Cleopatra", "Tiepolo Meeting Antony Cleopatra"],
         "Painting", None),
        ("Other Works and Prints",
         ["Tiepolo Immaculate Conception painting", "Tiepolo ceiling fresco"],
         "Painting", None),
    ]),
    ("gustav_klimt", "Gustav Klimt", [
        ("Danae (1907-1908)",
         ["Gustav Klimt Danae", "Klimt Danae 1907"],
         "Painting", None),
        ("Stoclet Frieze / Palais Stoclet",
         ["Klimt Stoclet Frieze", "Klimt Tree of Life Stoclet", "Klimt Expectation Stoclet"],
         "Painting", None),
    ]),
    ("gustave_moreau", "Gustave Moreau", [
        ("The Life of Humanity",
         ["Gustave Moreau Life of Humanity", "Gustave Moreau polyptych"],
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
         ["Hans Memling Last Judgment", "Memling Last Judgment triptych", "Memling Last Judgement Gdansk"],
         "Painting", None),
        ("Shrine of St. Ursula",
         ["Memling Shrine Saint Ursula", "Memling Ursula Shrine", "Hans Memling St Ursula shrine"],
         "Painting", None),
        ("Mystic Marriage of St. Catherine",
         ["Memling Mystic Marriage Catherine", "Hans Memling Saint Catherine"],
         "Painting", None),
        ("Scenes from the Passion of Christ",
         ["Memling Scenes Passion Christ", "Hans Memling Passion Christ painting"],
         "Painting", None),
        ("Other Works",
         ["Memling Donne Triptych", "Hans Memling portrait painting"],
         "Painting", None),
    ]),
    ("henry_ossawa_tanner", "Henry Ossawa Tanner", [
        ("The Banjo Lesson (1893)",
         ["Henry Ossawa Tanner Banjo Lesson", "Tanner Banjo Lesson painting"],
         "Painting", None),
        ("The Thankful Poor",
         ["Henry Ossawa Tanner Thankful Poor", "Tanner Thankful Poor painting"],
         "Painting", None),
        ("The Annunciation (1898)",
         ["Henry Ossawa Tanner Annunciation", "Tanner Annunciation 1898"],
         "Painting", None),
        ("Other Religious Works",
         ["Henry Ossawa Tanner Daniel Lions Den", "Henry Ossawa Tanner Nicodemus"],
         "Painting", None),
    ]),
    ("hokusai", "Hokusai", [
        ("Thirty-Six Views of Mount Fuji (General)",
         ["Hokusai Thirty-six Views Mount Fuji", "Hokusai 36 views Fuji"],
         "Painting", None),
        ("The Great Wave off Kanagawa",
         ["Great Wave Kanagawa Hokusai", "Hokusai Great Wave"],
         "Painting", None),
        ("Fine Wind, Clear Morning (Red Fuji)",
         ["Hokusai Red Fuji", "Hokusai Fine Wind Clear Morning", "South Wind Clear Sky Hokusai"],
         "Painting", None),
        ("Dream of the Fisherman's Wife (Shunga/Erotica)",
         ["Hokusai Dream Fisherman Wife", "Tako to Ama Hokusai"],
         "Painting", None),
        ("Hokusai Manga",
         ["Hokusai Manga sketches", "Hokusai Manga page"],
         "Painting", None),
        ("Quick Lessons in Simplified Drawing",
         ["Hokusai Quick Lessons Simplified Drawing", "Hokusai Ryakuga hayashinan"],
         "Painting", None),
        ("One Hundred Ghost Stories",
         ["Hokusai Hyaku Monogatari ghost", "Hokusai One Hundred Ghost Stories"],
         "Painting", None),
        ("Oceans of Wisdom Series",
         ["Hokusai Oceans of Wisdom", "Hokusai Chie no umi"],
         "Painting", None),
        ("Other Works",
         ["Hokusai Phoenix painting", "Hokusai Dragon painting"],
         "Painting", None),
    ]),
    ("hugo_van_der_goes", "Hugo van der Goes", [
        ("Portinari Altarpiece (Adoration of the Shepherds)",
         ["Hugo van der Goes Portinari Altarpiece", "Portinari Triptych", "Hugo van der Goes Adoration Shepherds"],
         "Painting", None),
        ("Monforte Altarpiece",
         ["Hugo van der Goes Monforte Altarpiece", "Hugo van der Goes Adoration Magi"],
         "Painting", None),
    ]),
    ("ilya_repin", "Ilya Repin", [
        ("Religious Procession in Kursk Province (1880-1883)",
         ["Repin Religious Procession Kursk", "Ilya Repin Krestny Khod", "Repin procession Kursk Province"],
         "Painting", None),
    ]),
    ("jacob_epstein", "Jacob Epstein", [
        ("BMA Building Sculptures (1908)",
         ["Jacob Epstein BMA Building sculptures", "Epstein British Medical Association sculptures", "Epstein Strand statues"],
         "Sculpture", None),
        ("Jacob and the Angel",
         ["Jacob Epstein Jacob Angel sculpture", "Epstein Jacob and the Angel alabaster"],
         "Sculpture", None),
    ]),
    ("jacob_lawrence", "Jacob Lawrence", [
        ("Migration Series (1940–1941)",
         ["Jacob Lawrence Migration Series", "Lawrence Migration Series painting"],
         "Painting", "https://en.wikipedia.org/wiki/Migration_Series"),
        ("The Legend of John Brown (1941)",
         ["Jacob Lawrence John Brown series", "Jacob Lawrence Legend John Brown"],
         "Painting", "https://en.wikipedia.org/wiki/Jacob_Lawrence"),
        ("Toussaint Louverture Series",
         ["Jacob Lawrence Toussaint Louverture", "Jacob Lawrence Toussaint L'Ouverture"],
         "Painting", "https://en.wikipedia.org/wiki/Jacob_Lawrence"),
        ("Other Works",
         ["Jacob Lawrence painting Harlem", "Jacob Lawrence Builders"],
         "Painting", "https://en.wikipedia.org/wiki/Jacob_Lawrence"),
    ]),
    ("jacopo_pontormo", "Jacopo Pontormo", [
        ("Vertumnus and Pomona (lunette)",
         ["Pontormo Vertumnus Pomona", "Pontormo lunette Poggio a Caiano", "Pontormo Vertumnus Pomona Medici"],
         "Painting", None),
    ]),
    ("james_ensor", "James Ensor", [
        ("Skeletons Fighting Over a Pickled Herring",
         ["James Ensor Skeletons Fighting Pickled Herring", "Ensor Skeletons Herring", "Ensor squelettes hareng"],
         "Painting", None),
    ]),
    ("jan_steen", "Jan Steen", [
        ("The Merry Family",
         ["Jan Steen Merry Family", "Jan Steen vrolijke huisgezin", "Steen Merry Family Rijksmuseum"],
         "Painting", None),
    ]),
    ("jean-honoré_fragonard", "Jean-Honoré Fragonard", [
        ("The Swing (1767)",
         ["Fragonard The Swing painting", "Fragonard Happy Accidents Swing", "Fragonard Escarpolette"],
         "Painting", None),
        ("The Progress of Love (1771–1773)",
         ["Fragonard Progress of Love", "Fragonard Meeting Love Frick", "Fragonard Pursuit Love"],
         "Painting", None),
        ("The Bolt (Le Verrou)",
         ["Fragonard The Bolt painting", "Fragonard Le Verrou"],
         "Painting", None),
        ("Other Works",
         ["Fragonard The Reader painting", "Fragonard Bathers painting"],
         "Painting", None),
    ]),
    ("john_everett_millais", "John Everett Millais", [
        ("Ophelia (1851–1852)",
         ["John Everett Millais Ophelia", "Millais Ophelia painting Tate"],
         "Painting", None),
        ("Christ in the House of His Parents (1849–1850)",
         ["Millais Christ House Parents", "Millais Carpenter Shop painting"],
         "Painting", None),
        ("The Order of Release (1853)",
         ["Millais Order of Release", "John Everett Millais Order Release"],
         "Painting", None),
        ("Peace Concluded (1856)",
         ["Millais Peace Concluded", "John Everett Millais Peace Concluded 1856"],
         "Painting", None),
        ("Other Works",
         ["Millais Bubbles painting", "Millais Autumn Leaves painting"],
         "Painting", None),
    ]),
    ("jose_clemente_orozco", "José Clemente Orozco", [
        ("The Epic of American Civilization (Baker Library, Dartmouth)",
         ["Orozco Epic American Civilization", "Orozco Dartmouth mural", "Orozco Baker Library"],
         "Painting", "https://en.wikipedia.org/wiki/The_Epic_of_American_Civilization"),
    ]),
]

def process_all():
    for slug, artist_name, works_to_find in TASKS:
        json_path = OUTPUT_DIR / f"{slug}_analysis.json"
        print(f"\n{'='*60}")
        print(f"Processing: {artist_name} ({json_path.name})")
        print(f"{'='*60}")
        
        with open(json_path) as f:
            data = json.load(f)
        
        modified = False
        
        for work_name, search_queries, indicator, wiki_link_override in works_to_find:
            print(f"\n  Work: {work_name}")
            
            # Find matching work in data
            work_obj = None
            for w in data.get("works", []):
                if w["name"] == work_name:
                    work_obj = w
                    break
            
            if not work_obj:
                print(f"    WARNING: Work not found in JSON, skipping")
                continue
            
            # Check if already has valid images
            existing_images = work_obj.get("images", [])
            if any(img.get("url") for img in existing_images):
                print(f"    Already has image, skipping")
                continue
            
            # Search for image
            thumb_url, filename = find_image(search_queries)
            
            if thumb_url:
                # Add image to work
                caption = work_name.split(" (")[0] if "(" in work_name else work_name
                work_obj["images"] = [{"url": thumb_url, "caption": caption}]
                print(f"    Added image to work: {thumb_url[:80]}...")
                
                # Update cards: add images to basic cards for this work
                for card in data.get("cards", []):
                    if card.get("work") == work_name and card.get("type") == "basic":
                        if not card.get("images") or not any(img.get("url") for img in card.get("images", [])):
                            card["images"] = [{"url": thumb_url, "side": "back"}]
                
                # Add image recognition card if not exists
                has_image_card = any(
                    c.get("type") == "image" and c.get("work") == work_name
                    for c in data.get("cards", [])
                )
                if not has_image_card:
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
                # No image found - add link fallback
                wiki_link = wiki_link_override or make_wiki_link(work_name, artist_name)
                caption = work_name.split(" (")[0] if "(" in work_name else work_name
                work_obj["images"] = [{"url": "", "link": wiki_link, "caption": caption}]
                print(f"    No image found, added wiki link fallback")
                modified = True
        
        if modified:
            with open(json_path, "w") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            print(f"\n  Saved: {json_path}")
        else:
            print(f"\n  No changes needed")

if __name__ == "__main__":
    process_all()
    print("\n\nDone! All topics processed.")
