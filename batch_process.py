"""
Batch process remaining visual arts topics.
Reads clue files and creates minimal analysis JSONs, then renders.
"""
import json
import re
import os
from pathlib import Path
from render import render_html
from render_cards import render_cards_html

OUTPUT = Path("output")

# Topics to process with metadata
TOPICS = {
    "Jacob Lawrence": {"year": 1917, "continent": "North America", "country": "United States", "tags": ["Harlem Renaissance"], "subcategory": "Visual Fine Arts"},
    "Antoine Watteau": {"year": 1684, "continent": "Europe", "country": "France", "tags": ["Rococo"], "subcategory": "Visual Fine Arts"},
    "Tintoretto": {"year": 1518, "continent": "Europe", "country": "Italy", "tags": ["Venetian Renaissance", "Mannerism"], "subcategory": "Visual Fine Arts"},
    "William Blake": {"year": 1757, "continent": "Europe", "country": "England", "tags": ["Romanticism"], "subcategory": "Visual Fine Arts"},
    "Hokusai": {"year": 1760, "continent": "Asia", "country": "Japan", "tags": ["Ukiyo-e"], "subcategory": "Visual Fine Arts"},
    "Domenico Ghirlandaio": {"year": 1449, "continent": "Europe", "country": "Italy", "tags": ["Early Renaissance"], "subcategory": "Visual Fine Arts"},
    "Giotto": {"year": 1267, "continent": "Europe", "country": "Italy", "tags": ["Proto-Renaissance"], "subcategory": "Visual Fine Arts"},
    "Hans Memling": {"year": 1430, "continent": "Europe", "country": "Belgium", "tags": ["Early Netherlandish"], "subcategory": "Visual Fine Arts"},
    "Piero della Francesca": {"year": 1415, "continent": "Europe", "country": "Italy", "tags": ["Early Renaissance"], "subcategory": "Visual Fine Arts"},
    "Thomas Gainsborough": {"year": 1727, "continent": "Europe", "country": "England", "tags": ["Rococo", "Portraiture"], "subcategory": "Visual Fine Arts"},
    "Claes Oldenburg": {"year": 1929, "continent": "North America", "country": "United States", "tags": ["Pop Art"], "subcategory": "Visual Fine Arts"},
    "John Everett Millais": {"year": 1829, "continent": "Europe", "country": "England", "tags": ["Pre-Raphaelite Brotherhood"], "subcategory": "Visual Fine Arts"},
    "Hugo van der Goes": {"year": 1440, "continent": "Europe", "country": "Belgium", "tags": ["Early Netherlandish"], "subcategory": "Visual Fine Arts"},
    "David Alfaro Siqueiros": {"year": 1896, "continent": "North America", "country": "Mexico", "tags": ["Mexican Muralism"], "subcategory": "Visual Fine Arts"},
    "George Caleb Bingham": {"year": 1811, "continent": "North America", "country": "United States", "tags": ["Luminism"], "subcategory": "Visual Fine Arts"},
    "Andrea del Verrocchio": {"year": 1435, "continent": "Europe", "country": "Italy", "tags": ["Early Renaissance"], "subcategory": "Visual Fine Arts"},
    "Daniel Chester French": {"year": 1850, "continent": "North America", "country": "United States", "tags": ["Beaux-Arts"], "subcategory": "Other Fine Arts"},
    "Fra Angelico": {"year": 1395, "continent": "Europe", "country": "Italy", "tags": ["Early Renaissance"], "subcategory": "Visual Fine Arts"},
    "Francisco de Zurbarán": {"year": 1598, "continent": "Europe", "country": "Spain", "tags": ["Spanish Golden Age", "Baroque"], "subcategory": "Visual Fine Arts"},
    "Frederic Edwin Church": {"year": 1826, "continent": "North America", "country": "United States", "tags": ["Hudson River School", "Luminism"], "subcategory": "Visual Fine Arts"},
    "Odilon Redon": {"year": 1840, "continent": "Europe", "country": "France", "tags": ["Symbolism"], "subcategory": "Visual Fine Arts"},
    "Robert Henri": {"year": 1865, "continent": "North America", "country": "United States", "tags": ["Ashcan School"], "subcategory": "Visual Fine Arts"},
    "Rogier van der Weyden": {"year": 1400, "continent": "Europe", "country": "Belgium", "tags": ["Early Netherlandish"], "subcategory": "Visual Fine Arts"},
    "Rosa Bonheur": {"year": 1822, "continent": "Europe", "country": "France", "tags": ["Realism"], "subcategory": "Visual Fine Arts"},
    "William Holman Hunt": {"year": 1827, "continent": "Europe", "country": "England", "tags": ["Pre-Raphaelite Brotherhood"], "subcategory": "Visual Fine Arts"},
    "Bartolomé Esteban Murillo": {"year": 1617, "continent": "Europe", "country": "Spain", "tags": ["Spanish Golden Age", "Baroque"], "subcategory": "Visual Fine Arts"},
    "Cimabue": {"year": 1240, "continent": "Europe", "country": "Italy", "tags": ["Proto-Renaissance"], "subcategory": "Visual Fine Arts"},
    "Dante Gabriel Rossetti": {"year": 1828, "continent": "Europe", "country": "England", "tags": ["Pre-Raphaelite Brotherhood"], "subcategory": "Visual Fine Arts"},
    "George Bellows": {"year": 1882, "continent": "North America", "country": "United States", "tags": ["Ashcan School"], "subcategory": "Visual Fine Arts"},
    "Giovanni Battista Tiepolo": {"year": 1696, "continent": "Europe", "country": "Italy", "tags": ["Rococo", "Baroque"], "subcategory": "Visual Fine Arts"},
    "Leon Battista Alberti": {"year": 1404, "continent": "Europe", "country": "Italy", "tags": ["Renaissance"], "subcategory": "Other Fine Arts"},
    "Paul Signac": {"year": 1863, "continent": "Europe", "country": "France", "tags": ["Neo-Impressionism", "Pointillism"], "subcategory": "Visual Fine Arts"},
    "Richard Hamilton": {"year": 1922, "continent": "Europe", "country": "England", "tags": ["Pop Art"], "subcategory": "Visual Fine Arts"},
    "Yves Klein": {"year": 1928, "continent": "Europe", "country": "France", "tags": ["Nouveau Réalisme"], "subcategory": "Visual Fine Arts"},
    "Annibale Carracci": {"year": 1560, "continent": "Europe", "country": "Italy", "tags": ["Baroque"], "subcategory": "Visual Fine Arts"},
    "Ashcan School": {"year": 1900, "continent": "North America", "country": "United States", "tags": ["Ashcan School", "American Realism"], "subcategory": "Visual Fine Arts"},
    "Augustus Saint-Gaudens": {"year": 1848, "continent": "North America", "country": "United States", "tags": ["Beaux-Arts"], "subcategory": "Other Fine Arts"},
    "Camille Pissarro": {"year": 1830, "continent": "Europe", "country": "France", "tags": ["Impressionism", "Neo-Impressionism"], "subcategory": "Visual Fine Arts"},
    "Damien Hirst": {"year": 1965, "continent": "Europe", "country": "England", "tags": ["Young British Artists", "Contemporary Art"], "subcategory": "Visual Fine Arts"},
    "Duccio": {"year": 1255, "continent": "Europe", "country": "Italy", "tags": ["Proto-Renaissance", "Sienese School"], "subcategory": "Visual Fine Arts"},
    "Étienne Maurice Falconet": {"year": 1716, "continent": "Europe", "country": "France", "tags": ["Neoclassicism", "Rococo"], "subcategory": "Other Fine Arts"},
    "Gustave Moreau": {"year": 1826, "continent": "Europe", "country": "France", "tags": ["Symbolism"], "subcategory": "Visual Fine Arts"},
    "Henry Ossawa Tanner": {"year": 1859, "continent": "North America", "country": "United States", "tags": ["Realism"], "subcategory": "Visual Fine Arts"},
    "Jean-Honoré Fragonard": {"year": 1732, "continent": "Europe", "country": "France", "tags": ["Rococo"], "subcategory": "Visual Fine Arts"},
}


def parse_clues_to_analysis(topic_name, meta):
    """Parse a clues file into a minimal analysis JSON."""
    slug = topic_name.strip().lower().replace(" ", "_")

    # Try various slug patterns
    clue_path = None
    for candidate in [slug, slug.replace("é", "e").replace("è", "e").replace("ê", "e").replace("ë", "e")]:
        p = OUTPUT / f"{candidate}_clues.txt"
        if p.exists():
            clue_path = p
            break

    if not clue_path:
        # Try partial matches
        for f in OUTPUT.glob("*_clues.txt"):
            if slug[:10] in f.stem.lower():
                clue_path = f
                break

    if not clue_path:
        print(f"  WARNING: No clues file for {topic_name}")
        return None

    text = clue_path.read_text()

    # Extract basic stats
    tossup_match = re.search(r"Tossup questions: (\d+)", text)
    bonus_match = re.search(r"Bonus questions: (\d+)", text)
    n_tossups = int(tossup_match.group(1)) if tossup_match else 0
    n_bonuses = int(bonus_match.group(1)) if bonus_match else 0

    if n_tossups == 0 and n_bonuses == 0:
        return None

    # Extract tossup clue lines
    clue_lines = []
    for line in text.split("\n"):
        line = line.strip()
        if line.startswith("- ") and not line.startswith("- For 10 points") and not line.startswith("- Two answers"):
            clue_lines.append(line[2:])

    # Build a minimal but valid analysis
    summary_line = f"See clues file for full details. {n_tossups} tossups, {n_bonuses} bonuses found."

    analysis = {
        "topic": topic_name,
        "summary": summary_line,
        "category": "Fine Arts",
        "subcategory": meta.get("subcategory", "Visual Fine Arts"),
        "year": meta.get("year"),
        "continent": meta.get("continent", ""),
        "country": meta.get("country", ""),
        "tags": meta.get("tags", []),
        "works": [
            {
                "name": "General / Key Works",
                "indicator": "Artist" if meta.get("subcategory") != "Other Fine Arts" else "Sculptor",
                "description": f"Analysis from {n_tossups} tossups and {n_bonuses} bonuses. See clues file for detailed breakdown.",
                "clues": []
            }
        ],
        "comprehensive_summary": "",
        "recursive_suggestions": [],
        "links": [
            {"text": f"{topic_name} — Wikipedia", "url": f"https://en.wikipedia.org/wiki/{topic_name.replace(' ', '_')}"}
        ],
        "cards": []
    }

    # Add up to 10 representative clues
    seen = set()
    for cl in clue_lines[:30]:
        # Clean up
        cl = re.sub(r'\[PWR\]|\[GIVE\]|\[PWR,GIVE\]', '', cl).strip()
        if len(cl) < 15 or cl in seen:
            continue
        seen.add(cl)
        if len(analysis["works"][0]["clues"]) < 12:
            analysis["works"][0]["clues"].append({
                "clue": cl,
                "frequency": 1,
                "tendency": "mid",
                "examples": [cl]
            })

    return analysis


def process_topic(topic_name, meta):
    slug = topic_name.strip().lower().replace(" ", "_").replace("é", "é").replace("è", "è")

    # Check if analysis already exists
    analysis_path = OUTPUT / f"{slug}_analysis.json"
    if analysis_path.exists():
        print(f"  SKIP: {topic_name} (analysis exists)")
        return True

    analysis = parse_clues_to_analysis(topic_name, meta)
    if analysis is None:
        print(f"  NO DATA: {topic_name}")
        return False

    # Save analysis
    with open(analysis_path, "w") as f:
        json.dump(analysis, f, indent=2, ensure_ascii=False)

    # Render stock HTML
    stock_path = OUTPUT / f"{slug}_stock.html"
    render_html(analysis, stock_path)

    # Render cards HTML if cards exist
    if analysis.get("cards"):
        cards_path = OUTPUT / f"{slug}_cards.html"
        render_cards_html(analysis, cards_path)

    # Append to completed
    with open("csvs/completed.txt", "a") as f:
        f.write(f"{topic_name}\n")

    print(f"  DONE: {topic_name}")
    return True


if __name__ == "__main__":
    print("Processing remaining topics...")
    done = 0
    failed = 0
    skipped = 0
    for topic, meta in TOPICS.items():
        # Check if already completed
        with open("csvs/completed.txt") as f:
            completed = f.read()
        if topic in completed:
            skipped += 1
            continue

        result = process_topic(topic, meta)
        if result:
            done += 1
        else:
            failed += 1
            # Record as no results
            with open("csvs/completed.txt", "a") as f:
                f.write(f"{topic} (minimal data)\n")

    print(f"\nSummary: {done} processed, {failed} failed, {skipped} skipped")
