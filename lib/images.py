#!/usr/bin/env python3
"""Single source of truth for all image URL operations.

ALL image URLs must go through this module. Never construct or write
Wikimedia URLs directly — always use find_image() which searches,
verifies, and caches.

Usage:
    from lib.images import find_image, set_work_image

    url = find_image("The Great Wave off Kanagawa", "Hokusai")
    if url:
        set_work_image(analysis_data, "The Great Wave off Kanagawa", url)
"""
import requests, json, time, re
from pathlib import Path

ROOT = Path(__file__).parent.parent
CACHE_FILE = ROOT / 'cache' / 'image_urls.json'

# Delay between API calls (seconds). 2s keeps us well under rate limits.
API_DELAY = 2.0

_session = None
_cache = None


def _get_session():
    global _session
    if _session is None:
        _session = requests.Session()
        # Wikimedia User-Agent policy: BotName/version (URL; contact email)
        _session.headers['User-Agent'] = (
            'StockQB/1.0 (https://github.com/denisfliu/library-of-stock; '
            'denisfliu@gmail.com)'
        )
        # Session automatically handles cookies (WMF-Uniq etc.)
    return _session


def _load_cache():
    global _cache
    if _cache is None:
        if CACHE_FILE.exists():
            with open(CACHE_FILE) as f:
                _cache = json.load(f)
        else:
            _cache = {}
    return _cache


def _save_cache():
    if _cache is not None:
        CACHE_FILE.parent.mkdir(exist_ok=True)
        with open(CACHE_FILE, 'w') as f:
            json.dump(_cache, f, indent=2, ensure_ascii=False)


def _api_get(base_url, params, retries=3):
    """API call with retry and Retry-After support. Returns parsed JSON or {}."""
    session = _get_session()
    for attempt in range(retries):
        try:
            time.sleep(API_DELAY)
            r = session.get(base_url, params=params, timeout=15)
            if r.status_code == 429:
                # Respect Retry-After header per Wikimedia policy
                retry_after = r.headers.get('Retry-After')
                if retry_after:
                    wait = int(retry_after)
                else:
                    wait = max(5, API_DELAY * (2 ** (attempt + 1)))
                print(f'    Rate limited, Retry-After: {wait}s', flush=True)
                time.sleep(wait)
                continue
            return r.json()
        except Exception:
            if attempt < retries - 1:
                time.sleep(API_DELAY * (attempt + 2))
    return {}


def verify_url(url):
    """Confirm URL returns HTTP 200. Respects Retry-After on 429."""
    session = _get_session()
    for attempt in range(2):
        try:
            r = session.head(url, timeout=10, allow_redirects=True)
            if r.status_code == 200:
                return True
            if r.status_code == 429:
                retry_after = r.headers.get('Retry-After')
                wait = int(retry_after) if retry_after else max(5, API_DELAY * (2 ** (attempt + 1)))
                print(f'    Verify rate limited, Retry-After: {wait}s', flush=True)
                time.sleep(wait)
                continue
            return False
        except Exception:
            return False
    return False


def _search_commons(query, limit=3):
    """Search Wikimedia Commons for filenames matching query."""
    data = _api_get('https://commons.wikimedia.org/w/api.php', {
        'action': 'query', 'list': 'search',
        'srsearch': f'{query} filetype:bitmap',
        'srnamespace': 6, 'srlimit': limit, 'format': 'json',
    })
    return [item['title'].replace('File:', '')
            for item in data.get('query', {}).get('search', [])]


def _get_thumb(filename, width=500):
    """Get thumbnail URL from a Commons filename."""
    data = _api_get('https://commons.wikimedia.org/w/api.php', {
        'action': 'query', 'titles': f'File:{filename}',
        'prop': 'imageinfo', 'iiprop': 'url',
        'iiurlwidth': width, 'format': 'json',
    })
    pages = data.get('query', {}).get('pages', {})
    for page in pages.values():
        return page.get('imageinfo', [{}])[0].get('thumburl')
    return None


def _clean_work_name(name):
    """Strip parentheticals, slashes, dates for better search."""
    name = re.sub(r'\(.*?\)', '', name).strip()
    name = re.sub(r'\s*/\s*.*', '', name).strip()
    name = re.sub(r',?\s*c\.\s*\d{4}.*', '', name).strip()
    return name


def find_image(work_name, artist_name):
    """Find a verified Wikimedia Commons image URL for a painting.

    Returns a verified URL string, or None if not found.
    Results are cached — repeated calls for the same painting are free.

    This is the ONLY function that should be used to get image URLs.
    Never construct Wikimedia URLs manually.
    """
    cache = _load_cache()
    cache_key = f'{artist_name} / {work_name}'

    # Return cached result (empty string = previously not found)
    if cache_key in cache:
        return cache[cache_key] or None

    clean = _clean_work_name(work_name)

    # Strategy 1: painting name + artist
    files = _search_commons(f'{clean} {artist_name}')
    for fn in files:
        url = _get_thumb(fn)
        if url and verify_url(url):
            cache[cache_key] = url
            _save_cache()
            return url

    # Strategy 2: just painting name
    files = _search_commons(clean)
    for fn in files:
        url = _get_thumb(fn)
        if url and verify_url(url):
            cache[cache_key] = url
            _save_cache()
            return url

    # Not found — cache as empty so we don't re-search
    cache[cache_key] = ''
    _save_cache()
    return None


def set_work_image(data, work_name, url):
    """Set the image URL for a work and sync to its cards.

    Only call this with a URL returned by find_image() — never with
    a manually constructed URL.
    """
    for w in data.get('works', []):
        if w['name'] == work_name:
            if w.get('images'):
                w['images'][0]['url'] = url
            else:
                w['images'] = [{'url': url, 'caption': work_name}]
            break

    # Sync to cards
    for c in data.get('cards', []):
        if c.get('work') == work_name:
            for ci in c.get('images', []):
                if not ci.get('url'):
                    ci['url'] = url


if __name__ == '__main__':
    import sys
    if len(sys.argv) < 3:
        print('Usage: python3 lib/images.py "Painting Name" "Artist Name"')
        sys.exit(1)
    painting = sys.argv[1]
    artist = sys.argv[2]
    url = find_image(painting, artist)
    if url:
        print(f'Found: {url}')
    else:
        print('Not found')
