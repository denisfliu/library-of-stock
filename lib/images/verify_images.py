#!/usr/bin/env python3
"""Verify all image URLs across VFA analysis JSONs.

Checks every unique embedded image URL returns HTTP 200.
Works through the image_urls.json cache to deduplicate.
Broken URLs are cleared from cache so fix_images.py can re-find them.

Respects Wikimedia Retry-After headers per rate limit policy.

Usage:
    python3 lib/verify_images.py          # default 2s delay
    python3 lib/verify_images.py 1        # 1s delay (faster)
"""
import requests, json, time, sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
CACHE_FILE = ROOT / 'cache' / 'image_urls.json'

session = requests.Session()
# Wikimedia User-Agent policy: BotName/version (URL; contact email)
session.headers['User-Agent'] = (
    'StockQB/1.0 (https://github.com/denisfliu/library-of-stock; '
    'denisfliu@gmail.com)'
)


def check_url(url, delay, retries=2):
    """Return True if URL returns 200, False if broken, None if rate-limited and exhausted retries."""
    for attempt in range(retries):
        try:
            time.sleep(delay)
            r = session.head(url, timeout=10, allow_redirects=True)
            if r.status_code == 200:
                return True
            elif r.status_code == 429:
                # Respect Retry-After header per Wikimedia policy
                retry_after = r.headers.get('Retry-After')
                if retry_after:
                    wait = int(retry_after)
                else:
                    wait = max(5, delay * (2 ** (attempt + 1)))
                print(f'    Rate limited, Retry-After: {wait}s', flush=True)
                time.sleep(wait)
                continue
            else:
                return False  # 404, 403, etc = broken
        except:
            if attempt < retries - 1:
                time.sleep(delay * 2)
    return None  # couldn't determine


def main():
    delay = float(sys.argv[1]) if len(sys.argv) > 1 else 2.0
    output_dir = ROOT / 'output'

    # Work through image_urls.json cache — check each unique URL once
    if not CACHE_FILE.exists():
        print('No image cache found. Run fix_images.py first.', flush=True)
        return

    with open(CACHE_FILE) as f:
        cache = json.load(f)

    # Deduplicate: group cache keys by URL
    url_to_keys = {}
    for key, url in cache.items():
        if url:
            url_to_keys.setdefault(url, []).append(key)

    unique_count = len(url_to_keys)
    print(f'Unique URLs to verify: {unique_count} (delay: {delay}s)', flush=True)
    print(f'Estimated time: ~{unique_count * delay / 60:.0f} minutes', flush=True)

    ok = 0
    broken_urls = {}  # url -> keys
    rate_limited = 0

    for i, (url, keys) in enumerate(url_to_keys.items()):
        result = check_url(url, delay)
        if result is True:
            ok += 1
        elif result is False:
            broken_urls[url] = keys
            print(f'  [{i+1}/{unique_count}] BROKEN: {keys[0]}', flush=True)
        else:
            rate_limited += 1
            print(f'  [{i+1}/{unique_count}] RATE LIMITED: {keys[0]} — will retry later', flush=True)

        if (i + 1) % 50 == 0:
            print(f'  ... {i+1}/{unique_count} checked (ok={ok}, broken={len(broken_urls)}, rate_limited={rate_limited})', flush=True)

    # Clear broken URLs from cache
    cleared = 0
    for url, keys in broken_urls.items():
        for key in keys:
            cache[key] = ''  # Mark as not-found
            cleared += 1

    # Also clear broken URLs from analysis JSONs and cards
    files_modified = set()
    for f in sorted(output_dir.glob('*/analysis.json')):
        with open(f) as fh:
            data = json.load(fh)

        changed = False
        for w in data.get('works', []):
            for img in w.get('images', []):
                if img.get('url') in broken_urls:
                    img['url'] = ''
                    changed = True
                    # Clear matching card images
                    for c in data.get('cards', []):
                        if c.get('work') == w['name']:
                            for ci in c.get('images', []):
                                if ci.get('url') in broken_urls:
                                    ci['url'] = ''

        if changed:
            with open(f, 'w') as fh:
                json.dump(data, fh, indent=2, ensure_ascii=False)
            files_modified.add(f.name)

    with open(CACHE_FILE, 'w') as f:
        json.dump(cache, f, indent=2, ensure_ascii=False)

    print(f'\n=== Results ===', flush=True)
    print(f'Unique URLs checked: {ok + len(broken_urls) + rate_limited}/{unique_count}', flush=True)
    print(f'OK: {ok}', flush=True)
    print(f'Broken (cleared from cache + JSONs): {len(broken_urls)} ({cleared} cache entries)', flush=True)
    print(f'Rate limited (unchecked): {rate_limited}', flush=True)
    print(f'Files modified: {len(files_modified)}', flush=True)

    if broken_urls:
        print(f'\nRun `python3 lib/fix_images.py` to re-find cleared images.', flush=True)
    if rate_limited:
        print(f'Re-run `python3 lib/verify_images.py` later to check remaining {rate_limited} URLs.', flush=True)


if __name__ == '__main__':
    main()
