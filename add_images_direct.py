#!/usr/bin/env python3
"""
add_images_direct.py — Add images using known Wikimedia Commons filenames.
Constructs thumbnail URLs directly, verifies with HEAD requests only.
Does not hit the search or query APIs (which are rate-limited).
"""

import json
import re
import time
import hashlib
import urllib.parse
import requests
from pathlib import Path

OUTPUT_DIR = Path("output")
HEADERS = {'User-Agent': 'StockQB/1.0 (quizbowl study tool)'}

VISUAL_INDICATORS = {"Painting", "Sculpture", "Fresco", "Mural", "Altarpiece", "Print", "Engraving"}


def commons_thumb_url(filename, width=500):
    """Construct a Wikimedia Commons thumbnail URL from a filename.
    Uses the standard hash-based path structure."""
    # Normalize: spaces to underscores
    filename = filename.replace(' ', '_')
    # URL-encode the filename
    encoded = urllib.parse.quote(filename)
    # Compute MD5 hash
    md5 = hashlib.md5(filename.encode('utf-8')).hexdigest()
    a, b = md5[0], md5[:2]
    return f"https://upload.wikimedia.org/wikipedia/commons/thumb/{a}/{b}/{encoded}/{width}px-{encoded}"


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


# Known filenames for works that need images.
# Format: (slug, artist_name, [(work_name_substring, commons_filename, caption)])
KNOWN_IMAGES = [
    # Albrecht Dürer
    ("albrecht_dürer", "Albrecht Dürer", [
        ("Nature Studies", "Albrecht_Dürer_-_Hare,_1502_-_Google_Art_Project.jpg", "Young Hare"),
        ("The Four Apostles", "Albrecht_Dürer_-_The_Four_Apostles_-_WGA06940.jpg", "The Four Apostles"),
    ]),
    # Alfred Sisley
    ("alfred_sisley", "Alfred Sisley", [
        ("Thames series", "Alfred_Sisley_070.jpg", "Under the Bridge at Hampton Court"),
    ]),
    # Andrea del Sarto
    ("andrea_del_sarto", "Andrea del Sarto", [
        ("Chiostro dello Scalzo", "Battesimo_delle_moltitudini,_andrea_del_sarto.jpg", "Chiostro dello Scalzo - Baptism"),
        ("Madonna del Sacco", "Andrea_del_Sarto_-_Madonna_del_Sacco.jpg", "Madonna del Sacco"),
    ]),
    # Andrea del Verrocchio
    ("andrea_del_verrocchio", "Andrea del Verrocchio", [
        ("Christ and Saint Thomas", "Andrea_del_Verrocchio_-_Christ_and_St._Thomas_-_Orsanmichele.jpg", "Christ and Saint Thomas"),
    ]),
    # Andrea Mantegna
    ("andrea_mantegna", "Andrea Mantegna", [
        ("San Zeno Altarpiece", "Andrea_Mantegna_-_San_Zeno_Altarpiece.jpg", "San Zeno Altarpiece"),
    ]),
    # Andrew Wyeth - copyrighted, use wiki links
    ("andrew_wyeth", "Andrew Wyeth", []),
    # Annibale Carracci
    ("annibale_carracci", "Annibale Carracci", [
        ("Butcher's Shop", "Annibale_Carracci_-_The_Butcher's_Shop_-_WGA04410.jpg", "The Butcher's Shop"),
        ("Beaneater", "Annibale_Carracci_The_Beaneater.jpg", "The Beaneater"),
        ("Landscape with the Flight into Egypt", "Annibale_Carracci_-_Flight_into_Egypt_-_WGA04423.jpg", "Landscape with the Flight into Egypt"),
    ]),
    # Antoine Watteau
    ("antoine_watteau", "Antoine Watteau", [
        ("Embarkation for Cythera", "L'Embarquement_pour_Cythère,_by_Antoine_Watteau,_from_C2RMF_retouched.jpg", "The Embarkation for Cythera"),
        ("Gersaint", "Antoine_Watteau_047.jpg", "Gersaint's Shop Sign"),
        ("Gilles", "Jean-Antoine_Watteau_-_Pierrot,_dit_autrefois_Gilles.jpg", "Gilles (Pierrot)"),
        ("Mezzetin", "Jean-Antoine_Watteau_-_Mezzetin.JPG", "Mezzetin"),
        ("Love Lesson", "Antoine_Watteau_-_La_Leçon_d'amour.jpg", "The Love Lesson"),
    ]),
    # Augustus Saint-Gaudens
    ("augustus_saint-gaudens", "Augustus Saint-Gaudens", [
        ("Robert Gould Shaw", "Robert_Gould_Shaw_Memorial_-_detail_(Robert_Gould_Shaw).jpg", "Robert Gould Shaw Memorial"),
        ("Standing Lincoln", "Lincoln_-_Saint-Gaudens_-_Chicago.jpg", "Standing Lincoln"),
        ("Adams Memorial", "Adams-memorial-SaintGaudens.jpg", "Adams Memorial"),
        ("Sherman Memorial", "Sherman_gilded_jeh.JPG", "Sherman Memorial"),
        ("Amor Caritas", "Amor_Caritas_MET_DP170854.jpg", "Amor Caritas"),
        ("Diana", "Augustus_Saint-Gaudens_-_Diana.jpg", "Diana"),
        ("Double Eagle", "NNC-US-1907-G$20-Saint_Gaudens_(Arabic).jpg", "Double Eagle Gold Coin"),
    ]),
    # Bouguereau
    ("bouguereau", "William-Adolphe Bouguereau", [
        ("Nymphs and Satyr", "William-Adolphe_Bouguereau_(1825-1905)_-_Nymphs_and_Satyr_(1873).jpg", "Nymphs and Satyr"),
    ]),
    # Camille Pissarro
    ("camille_pissarro", "Camille Pissarro", [
        ("Boulevard Montmartre", "Camille_Pissarro_-_Boulevard_Montmartre,_Spring_-_Google_Art_Project.jpg", "Boulevard Montmartre, Spring"),
        ("Pontoise", "Camille_Pissarro_-_Jalais_Hill,_Pontoise_-_Google_Art_Project.jpg", "Jalais Hill, Pontoise"),
    ]),
    # Charles Demuth
    ("charles_demuth", "Charles Demuth", [
        ("Figure 5", "Charles_Demuth_-_The_Figure_5_in_Gold_(1928).jpg", "I Saw the Figure 5 in Gold"),
        ("My Egypt", "Charles_Demuth_-_My_Egypt.jpg", "My Egypt"),
    ]),
    # Charles Le Brun
    ("charles_le_brun", "Charles Le Brun", [
        ("Alexander", "Charles_Le_Brun_-_Entry_of_Alexander_into_Babylon.JPG", "Entry of Alexander into Babylon"),
    ]),
    # Charles Willson Peale
    ("charles_willson_peale", "Charles Willson Peale", [
        ("Staircase Group", "Charles_Willson_Peale_001.jpg", "The Staircase Group"),
    ]),
    # Cimabue
    ("cimabue", "Cimabue", [
        ("Santa Trinita", "Cimabue_-_Maestà_di_Santa_Trinita_-_Google_Art_Project.jpg", "Santa Trinita Maestà"),
        ("Crucifix", "Cimabue_019.jpg", "Crucifix (Santa Croce)"),
    ]),
    # Claes Oldenburg
    ("claes_oldenburg", "Claes Oldenburg", [
        ("Lipstick", "Lipstick_Ascending_on_Caterpillar_Tracks_Morse_College_3.jpg", "Lipstick (Ascending) on Caterpillar Tracks"),
        ("Spoonbridge", "Minneapolis_Sculpture_Garden-2005-07-13.jpg", "Spoonbridge and Cherry"),
        ("Dropped Cone", "Dropped_Cone_Claes_Oldenburg_and_Coosje_van_Bruggen.jpg", "Dropped Cone"),
        ("Shuttlecocks", "Nelson-Atkins_Museum_Shuttlecock_6.jpg", "Shuttlecocks"),
    ]),
]


def process_topic(slug, artist_name, image_specs):
    json_path = OUTPUT_DIR / f"{slug}_analysis.json"
    if not json_path.exists():
        print(f"  SKIP: {json_path} not found")
        return False

    with open(json_path) as f:
        analysis = json.load(f)

    works = analysis.get("works", [])
    cards = analysis.get("cards", [])
    modified = False

    for work_sub, commons_filename, caption in image_specs:
        # Find matching work
        matching_work = None
        for w in works:
            if work_sub.lower() in w.get("name", "").lower():
                matching_work = w
                break

        if not matching_work:
            print(f"    WARNING: '{work_sub}' not found in works")
            continue

        indicator = matching_work.get("indicator", "")
        if indicator not in VISUAL_INDICATORS:
            print(f"    SKIP (indicator={indicator}): {matching_work['name'][:60]}")
            continue

        # Skip if already has a real image
        existing = matching_work.get("images", [])
        if any(img.get("url") for img in existing):
            print(f"    Already has image: {matching_work['name'][:60]}")
            continue

        work_name = matching_work["name"]
        clean = clean_work_name(work_name)

        # Try the known filename
        thumb = commons_thumb_url(commons_filename)
        print(f"    Trying: {commons_filename[:60]}...")

        if verify_url(thumb):
            print(f"    VERIFIED: {thumb[:80]}...")
            matching_work["images"] = [{"url": thumb, "caption": caption}]

            # Update basic cards
            for card in cards:
                if card.get("work") == work_name and card.get("type") == "basic":
                    card_imgs = card.get("images", [])
                    if not any(img.get("url") for img in card_imgs):
                        card["images"] = [{"url": thumb, "side": "back"}]

            # Add image recognition card if missing
            has_img_card = any(
                c.get("type") == "image" and c.get("work") == work_name for c in cards
            )
            if not has_img_card:
                cards.append({
                    "type": "image", "indicator": indicator,
                    "front": "", "back": f"{clean} ({artist_name})",
                    "work": work_name, "frequency": 0, "tags": [],
                    "images": [{"url": thumb, "side": "front"}]
                })

            modified = True
            time.sleep(0.3)
        else:
            print(f"    NOT FOUND (URL doesn't resolve)")
            # Keep existing wiki link fallback
            time.sleep(0.3)

    if modified:
        analysis["cards"] = cards
        with open(json_path, 'w') as f:
            json.dump(analysis, f, indent=2, ensure_ascii=False)
        print(f"  SAVED: {json_path}")
    else:
        print(f"  No changes")

    return modified


def main():
    print("=== Adding images from known filenames ===\n")
    changed = 0
    for slug, artist, specs in KNOWN_IMAGES:
        if not specs:
            print(f"\n--- {artist} (skipped - copyrighted/no specs) ---")
            continue
        print(f"\n--- {artist} ({slug}) ---")
        if process_topic(slug, artist, specs):
            changed += 1

    print(f"\n=== Done! Modified {changed} files ===")


if __name__ == "__main__":
    main()
