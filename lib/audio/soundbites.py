"""soundbites.py — Wikimedia Commons audio for overview pages.

Overview entries can carry real (usually public-domain) recordings of
famous excerpts — a 1927 Pertile "Nessun dorma", not the synthesized
score-clue MP3s (those exist only for score-identification study on
topic pages).

Data lives in output/_categories/{unit}/soundbites.json, curated by an
agent/human with the search CLI below and committed:

    {
      "<normalize(answerline)>": [
        {"label": "Nessun dorma — Aureliano Pertile (1927)",
         "file": "File:'Nessun Dorma', Aureliano Pertile, 1927.ogg",
         "url": "https://upload.wikimedia.org/..."}
      ]
    }

Keys use lib.sweep.answerlines.normalize of the entry's answerline —
the same key the questions panel uses. render_overview.py embeds an
<audio> player per clip with a Commons attribution link.

CLI:
    python lib/audio/soundbites.py search "Nessun dorma"      # find candidates
    python lib/audio/soundbites.py verify opera               # HEAD-check all URLs
"""
import argparse
import json
import sys as _sys
from pathlib import Path as _Path

import requests

_sys.path.insert(0, str(_Path(__file__).resolve().parent.parent.parent))
from lib.common import CATEGORIES_DIR

API = 'https://commons.wikimedia.org/w/api.php'
HEADERS = {'User-Agent': 'library-of-stock/1.0 (quizbowl study tool)'}
AUDIO_EXTS = ('.ogg', '.oga', '.mp3', '.flac', '.wav', '.opus', '.mid')


def search_audio(query: str, limit: int = 8) -> list[dict]:
    """Search Commons for audio files. Returns [{title, url, size_kb}]."""
    r = requests.get(API, params={
        'action': 'query', 'list': 'search', 'format': 'json',
        'srsearch': f'{query} filetype:audio', 'srnamespace': 6,
        'srlimit': limit,
    }, headers=HEADERS, timeout=30)
    r.raise_for_status()
    titles = [h['title'] for h in r.json()['query']['search']
              if h['title'].lower().endswith(AUDIO_EXTS)]
    if not titles:
        return []
    r = requests.get(API, params={
        'action': 'query', 'prop': 'imageinfo', 'format': 'json',
        'iiprop': 'url|size', 'titles': '|'.join(titles[:limit]),
    }, headers=HEADERS, timeout=30)
    r.raise_for_status()
    out = []
    for page in r.json()['query']['pages'].values():
        info = (page.get('imageinfo') or [{}])[0]
        if info.get('url'):
            out.append({'title': page['title'], 'url': info['url'],
                        'size_kb': info.get('size', 0) // 1024})
    # keep search ranking order
    order = {t: i for i, t in enumerate(titles)}
    out.sort(key=lambda x: order.get(x['title'], 99))
    return out


def load_soundbites(unit_slug: str) -> dict:
    path = CATEGORIES_DIR / unit_slug / 'soundbites.json'
    if path.exists():
        with open(path, encoding='utf-8') as f:
            return json.load(f)
    return {}


def verify(unit_slug: str) -> int:
    """Check every clip of a unit against the Commons API.

    One pipe-joined imageinfo query per ~50 files: confirms each File:
    page exists and that the stored URL matches the canonical one.
    (Deliberately does NOT hit upload.wikimedia.org — its rate limiter
    429s bursts of HEAD/ranged-GET requests even for valid files.)
    """
    bites = load_soundbites(unit_slug)
    entries = [(key, c) for key, clips in bites.items() for c in clips]
    canonical: dict[str, str | None] = {}
    titles = [c['file'] for _key, c in entries if c.get('file')]
    for i in range(0, len(titles), 50):
        r = requests.get(API, params={
            'action': 'query', 'prop': 'imageinfo', 'format': 'json',
            'iiprop': 'url', 'titles': '|'.join(titles[i:i + 50]),
        }, headers=HEADERS, timeout=30)
        r.raise_for_status()
        data = r.json()['query']
        # normalized: request title -> canonical page title
        renames = {n['to']: n['from'] for n in data.get('normalized', [])}
        for page in data['pages'].values():
            title = renames.get(page['title'], page['title'])
            info = (page.get('imageinfo') or [{}])[0]
            canonical[title] = None if 'missing' in page else info.get('url')

    failures = 0
    for key, c in entries:
        want = canonical.get(c.get('file', ''))
        if want is None:
            failures += 1
            print(f'BROKEN (missing on Commons) {key}: {c.get("file")}')
        elif want != c['url']:
            failures += 1
            print(f'URL MISMATCH {key}:\n  stored    {c["url"]}\n  canonical {want}')
    print(f'{unit_slug}: {len(entries)} clips, {failures} broken')
    return failures


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    sub = ap.add_subparsers(dest='cmd', required=True)
    s = sub.add_parser('search')
    s.add_argument('query')
    s.add_argument('--limit', type=int, default=8)
    v = sub.add_parser('verify')
    v.add_argument('unit')
    args = ap.parse_args()

    if args.cmd == 'search':
        for hit in search_audio(args.query, args.limit):
            print(f"{hit['size_kb']:7d}KB  {hit['title']}")
            print(f"           {hit['url']}")
    else:
        raise SystemExit(1 if verify(args.unit) else 0)


if __name__ == '__main__':
    main()
