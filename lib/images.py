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
import requests, json, time, re, fcntl
from pathlib import Path

ROOT = Path(__file__).parent.parent
CACHE_FILE = ROOT / 'cache' / 'image_urls.json'
LOCK_FILE = ROOT / 'cache' / '.images.lock'

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


def _filename_matches(filename, work_name, artist_name):
    """Check if a Commons filename matches the artist and work.

    Returns:
        'pass'    — auto-accept (artist name in filename)
        'fail'    — auto-reject (different artist named, or generic junk)
        'pending' — needs LLM review (ambiguous)
    """
    fn_lower = filename.lower()

    # Build name variants for the artist
    parts = artist_name.split()
    name_variants = set()
    for p in parts:
        if len(p) > 2 and p.lower() not in ('the', 'von', 'van', 'de', 'del', 'di', 'el', 'der', 'den'):
            name_variants.add(p.lower())
    name_variants.add(artist_name.lower().replace(' ', '_'))

    artist_match = any(nv in fn_lower for nv in name_variants)

    # AUTO-PASS: artist name in filename
    if artist_match:
        return 'pass'

    # AUTO-FAIL: filename explicitly names a DIFFERENT artist
    if re.match(r'^[a-z]+_[a-z]+_-_', fn_lower):
        return 'fail'
    if '_by_' in fn_lower:
        return 'fail'

    # AUTO-FAIL: obviously generic filenames
    generic = ['thumbnail', 'photo', 'image', 'picture', 'file', 'untitled',
               'img_', 'dsc_', 'screenshot', 'panorama', 'cute', 'vacation',
               'nature', 'abstract_design']
    if any(g in fn_lower for g in generic):
        return 'fail'

    # Everything else → pending for LLM review
    return 'pending'


PENDING_FILE = ROOT / 'cache' / 'pending_images.json'


def _load_pending():
    if PENDING_FILE.exists():
        with open(PENDING_FILE) as f:
            return json.load(f)
    return {}


def _save_pending(pending):
    PENDING_FILE.parent.mkdir(exist_ok=True)
    with open(PENDING_FILE, 'w') as f:
        json.dump(pending, f, indent=2, ensure_ascii=False)


def find_image(work_name, artist_name):
    """Find a verified Wikimedia Commons image URL for a painting.

    Returns a verified URL string, or None if not found.
    Results are cached — repeated calls for the same painting are free.

    Images that auto-pass (artist name in filename) are accepted immediately.
    Images that auto-fail (wrong artist, generic) are rejected.
    Ambiguous images are saved to cache/pending_images.json for LLM review.

    This is the ONLY function that should be used to get image URLs.
    Never construct Wikimedia URLs manually.
    """
    cache = _load_cache()
    cache_key = f'{artist_name} / {work_name}'

    # Return cached result (empty string = previously not found)
    if cache_key in cache:
        return cache[cache_key] or None

    # Acquire file lock so only one process hits Wikimedia at a time
    LOCK_FILE.parent.mkdir(exist_ok=True)
    lock_fd = open(LOCK_FILE, 'w')
    fcntl.flock(lock_fd, fcntl.LOCK_EX)
    try:
        # Re-check cache after acquiring lock (another process may have found it)
        cache = _load_cache()
        if cache_key in cache:
            return cache[cache_key] or None

        return _search_and_validate(work_name, artist_name, cache_key, cache)
    finally:
        fcntl.flock(lock_fd, fcntl.LOCK_UN)
        lock_fd.close()


def _search_and_validate(work_name, artist_name, cache_key, cache):
    """Internal: search Commons, validate, cache. Called under lock."""
    clean = _clean_work_name(work_name)
    pending = _load_pending()

    # Search both strategies, collect candidates
    all_files = []
    files1 = _search_commons(f'{clean} {artist_name}')
    files2 = _search_commons(clean)
    seen = set()
    for fn in files1 + files2:
        if fn not in seen:
            seen.add(fn)
            all_files.append(fn)

    for fn in all_files:
        verdict = _filename_matches(fn, work_name, artist_name)

        if verdict == 'fail':
            continue

        url = _get_thumb(fn)
        if not url or not verify_url(url):
            continue

        if verdict == 'pass':
            # Auto-accept
            cache[cache_key] = url
            _save_cache()
            return url

        if verdict == 'pending':
            # Save for LLM review — don't auto-accept
            pending[cache_key] = {
                'url': url,
                'filename': fn,
                'artist': artist_name,
                'work': work_name,
            }
            _save_pending(pending)
            print(f'    PENDING: {cache_key} → {fn[:60]}', flush=True)
            break  # Only save the first pending candidate

    # Not auto-accepted — cache as not found for now
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
