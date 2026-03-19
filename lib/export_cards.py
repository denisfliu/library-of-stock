"""
export_cards.py — Export cards to Anki .apkg format using genanki.

Reads cards from either:
  1. A *_cards.json file (exported from the card editor)
  2. The cards field in a *_analysis.json file

Usage:
    python export_cards.py output/thomas_middleton_cards.json
    python export_cards.py output/thomas_middleton_analysis.json
    python export_cards.py  # exports all topics that have cards
"""

import json
import hashlib
import sys
from pathlib import Path

import genanki
import requests

OUTPUT_DIR = Path("output")


def _stable_id(name: str) -> int:
    """Generate a stable numeric ID from a string (for genanki model/deck IDs)."""
    return int(hashlib.md5(name.encode()).hexdigest()[:8], 16)


# Anki model for basic cards
BASIC_MODEL = genanki.Model(
    _stable_id("StockQB Basic"),
    "StockQB Basic",
    fields=[
        {"name": "Front"},
        {"name": "Back"},
        {"name": "Image"},
    ],
    templates=[{
        "name": "Card 1",
        "qfmt": "{{Front}}",
        "afmt": '{{FrontSide}}<hr id="answer">{{Back}}'
               '{{#Image}}<br><img src="{{Image}}">{{/Image}}',
    }],
    css="""
    .card {
        font-family: -apple-system, 'Segoe UI', Roboto, sans-serif;
        font-size: 18px;
        text-align: center;
        color: #202122;
        background: #fff;
        padding: 20px;
    }
    img { max-width: 400px; max-height: 400px; }
    """,
)

# Model for image recognition cards
IMAGE_MODEL = genanki.Model(
    _stable_id("StockQB Image"),
    "StockQB Image",
    fields=[
        {"name": "Image"},
        {"name": "Back"},
    ],
    templates=[{
        "name": "Card 1",
        "qfmt": '<img src="{{Image}}">',
        "afmt": '<img src="{{Image}}"><hr id="answer">{{Back}}',
    }],
    css="""
    .card {
        font-family: -apple-system, 'Segoe UI', Roboto, sans-serif;
        font-size: 18px;
        text-align: center;
        color: #202122;
        background: #fff;
        padding: 20px;
    }
    img { max-width: 500px; max-height: 500px; }
    """,
)


def download_image(url: str, cache_dir: Path) -> str | None:
    """Download an image and return the local filename."""
    cache_dir.mkdir(exist_ok=True)
    # Use hash of URL as filename to avoid conflicts
    ext = url.rsplit(".", 1)[-1].split("?")[0][:4]
    if ext not in ("jpg", "jpeg", "png", "gif", "webp", "svg"):
        ext = "jpg"
    fname = hashlib.md5(url.encode()).hexdigest()[:12] + "." + ext
    fpath = cache_dir / fname
    if fpath.exists():
        return fname
    try:
        r = requests.get(url, timeout=15, headers={"User-Agent": "StockQB/1.0"})
        r.raise_for_status()
        with open(fpath, "wb") as f:
            f.write(r.content)
        return fname
    except Exception as e:
        print(f"  Warning: failed to download {url}: {e}")
        return None


def export_apkg(cards: list[dict], topic: str, output_path: Path):
    """Export a list of card dicts to an .apkg file."""
    deck = genanki.Deck(_stable_id(f"StockQB::{topic}"), f"StockQB::{topic}")
    media_files = []
    img_cache = Path("cache/images")

    for card in cards:
        card_type = card.get("type", "basic")
        tags = [t.replace(" ", "_") for t in card.get("tags", [])]

        if card_type == "image" and card.get("image_url"):
            # Image recognition card
            fname = download_image(card["image_url"], img_cache)
            if fname:
                media_files.append(str(img_cache / fname))
                note = genanki.Note(
                    model=IMAGE_MODEL,
                    fields=[fname, card.get("back", "")],
                    tags=tags,
                )
                deck.add_note(note)
        else:
            # Basic card
            image_field = ""
            if card.get("image_url"):
                fname = download_image(card["image_url"], img_cache)
                if fname:
                    media_files.append(str(img_cache / fname))
                    image_field = fname

            note = genanki.Note(
                model=BASIC_MODEL,
                fields=[card.get("front", ""), card.get("back", ""), image_field],
                tags=tags,
            )
            deck.add_note(note)

    pkg = genanki.Package(deck)
    pkg.media_files = media_files
    pkg.write_to_file(str(output_path))
    return len(deck.notes)


def main():
    if len(sys.argv) == 2:
        # Export a specific file
        fpath = Path(sys.argv[1])
        with open(fpath) as f:
            data = json.load(f)

        # Could be a cards.json (list) or analysis.json (dict with 'cards' key)
        if isinstance(data, list):
            cards = data
            topic = fpath.stem.replace("_cards", "").replace("_", " ").title()
        else:
            cards = data.get("cards", [])
            topic = data.get("topic", fpath.stem.replace("_analysis", "").replace("_", " ").title())

        if not cards:
            print(f"No cards found in {fpath}")
            sys.exit(1)

        out_path = OUTPUT_DIR / f"{topic.lower().replace(' ', '_')}.apkg"
        count = export_apkg(cards, topic, out_path)
        print(f"Exported {count} cards to {out_path}")

    else:
        # Export all topics that have cards
        total = 0
        for f in sorted(OUTPUT_DIR.glob("*_analysis.json")):
            with open(f) as fh:
                data = json.load(fh)
            cards = data.get("cards", [])
            if not cards:
                continue
            topic = data.get("topic", "Unknown")
            topic_key = f.stem.replace("_analysis", "")
            out_path = OUTPUT_DIR / f"{topic_key}.apkg"
            count = export_apkg(cards, topic, out_path)
            print(f"  {topic}: {count} cards -> {out_path}")
            total += count
        print(f"Exported {total} total cards")


if __name__ == "__main__":
    main()
