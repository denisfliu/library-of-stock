#!/usr/bin/env python3
"""Verify all image URLs across VFA analysis JSONs.

Checks every embedded image URL returns HTTP 200.
Broken URLs are cleared (set to empty string) so fix_images.py can re-find them.
Uses persistent cache to avoid re-verifying known-good URLs.

Usage:
    python3 lib/verify_images.py          # default 1s delay
    python3 lib/verify_images.py 0.5      # faster
"""
import requests, json, time, sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
VERIFIED_CACHE = ROOT / 'cache' / 'verified_urls.json'

session = requests.Session()
session.headers['User-Agent'] = 'StockQB/1.0 (quizbowl study tool)'


def load_verified():
    if VERIFIED_CACHE.exists():
        with open(VERIFIED_CACHE) as f:
            return set(json.load(f))
    return set()

def save_verified(verified):
    VERIFIED_CACHE.parent.mkdir(exist_ok=True)
    with open(VERIFIED_CACHE, 'w') as f:
        json.dump(sorted(verified), f)


def check_url(url, delay, retries=2):
    """Return True if URL returns 200, False if 404, None if rate-limited."""
    for attempt in range(retries):
        try:
            time.sleep(delay)
            r = session.head(url, timeout=10, allow_redirects=True)
            if r.status_code == 200:
                return True
            elif r.status_code == 404:
                return False
            elif r.status_code == 429:
                wait = delay * (2 ** (attempt + 1))
                print(f'    Rate limited, waiting {wait:.0f}s...', flush=True)
                time.sleep(wait)
                continue
            else:
                return False  # other errors = broken
        except:
            if attempt < retries - 1:
                time.sleep(delay * 2)
    return None  # couldn't determine


def main():
    output_dir = ROOT / 'output'
    delay = float(sys.argv[1]) if len(sys.argv) > 1 else 1.0

    verified_cache = load_verified()
    print(f'Verified cache: {len(verified_cache)} known-good URLs', flush=True)

    total = 0
    ok = 0
    broken = 0
    rate_limited = 0
    cleared_files = set()

    for f in sorted(output_dir.glob('*_analysis.json')):
        with open(f) as fh:
            data = json.load(fh)

        changed = False
        for w in data.get('works', []):
            for img in w.get('images', []):
                url = img.get('url', '')
                if not url:
                    continue
                total += 1

                # Skip if already verified
                if url in verified_cache:
                    ok += 1
                    continue

                result = check_url(url, delay)
                if result is True:
                    ok += 1
                    verified_cache.add(url)
                elif result is False:
                    broken += 1
                    print(f'  BROKEN: {data.get("topic", "?")} / {w["name"]}', flush=True)
                    print(f'          {url[:90]}', flush=True)
                    img['url'] = ''  # Clear so fix_images.py can re-find it
                    changed = True
                else:
                    rate_limited += 1
                    print(f'  SKIP (rate limited): {data.get("topic", "?")} / {w["name"]}', flush=True)

        if changed:
            # Also clear matching card images
            for w in data.get('works', []):
                for img in w.get('images', []):
                    if not img.get('url'):
                        work_name = w['name']
                        for c in data.get('cards', []):
                            if c.get('work') == work_name:
                                for ci in c.get('images', []):
                                    ci['url'] = ''

            with open(f, 'w') as fh:
                json.dump(data, fh, indent=2, ensure_ascii=False)
            cleared_files.add(f.name)

    save_verified(verified_cache)

    print(f'\n=== Results ===', flush=True)
    print(f'Total URLs checked: {total}', flush=True)
    print(f'OK: {ok}', flush=True)
    print(f'Broken (cleared): {broken}', flush=True)
    print(f'Rate limited (skipped): {rate_limited}', flush=True)
    print(f'Files modified: {len(cleared_files)}', flush=True)

    if broken > 0:
        print(f'\nRun `python3 lib/fix_images.py` to re-find cleared images.', flush=True)


if __name__ == '__main__':
    main()
