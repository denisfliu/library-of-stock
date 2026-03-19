#!/usr/bin/env python3
"""Fix missing/broken images across all VFA analysis JSONs.

Uses Wikimedia Commons search API to find painting images by name.
Saves progress incrementally so it can be interrupted and resumed.
"""
import requests, json, time, re, sys
from pathlib import Path

session = requests.Session()
session.headers['User-Agent'] = 'StockQB/1.0'

def search_commons(query, limit=3):
    try:
        params = {
            'action': 'query', 'list': 'search',
            'srsearch': f'{query} filetype:bitmap',
            'srnamespace': 6, 'srlimit': limit, 'format': 'json',
        }
        r = session.get('https://commons.wikimedia.org/w/api.php', params=params, timeout=10)
        return [item['title'].replace('File:', '') for item in r.json().get('query', {}).get('search', [])]
    except:
        time.sleep(3)
        return []

def get_thumb(filename, width=500):
    try:
        params = {
            'action': 'query', 'titles': f'File:{filename}',
            'prop': 'imageinfo', 'iiprop': 'url',
            'iiurlwidth': width, 'format': 'json',
        }
        r = session.get('https://commons.wikimedia.org/w/api.php', params=params, timeout=10)
        pages = r.json().get('query', {}).get('pages', {})
        for page in pages.values():
            return page.get('imageinfo', [{}])[0].get('thumburl')
    except:
        time.sleep(3)
    return None

def verify(url):
    try:
        r = session.head(url, timeout=5, allow_redirects=True)
        return r.status_code == 200
    except:
        return False

def clean_work_name(name):
    name = re.sub(r'\(.*?\)', '', name).strip()
    name = re.sub(r'\s*/\s*.*', '', name).strip()
    name = re.sub(r',?\s*c\.\s*\d{4}.*', '', name).strip()
    return name

def find_image(work_name, artist, delay=0.4):
    clean = clean_work_name(work_name)

    # Strategy 1: painting + artist
    time.sleep(delay)
    files = search_commons(f'{clean} {artist}')
    for fn in files:
        time.sleep(delay)
        url = get_thumb(fn)
        if url and verify(url):
            return url

    # Strategy 2: just painting name
    time.sleep(delay)
    files = search_commons(clean)
    for fn in files:
        time.sleep(delay)
        url = get_thumb(fn)
        if url and verify(url):
            return url

    return None

def main():
    output_dir = Path(__file__).parent.parent / 'output'
    delay = float(sys.argv[1]) if len(sys.argv) > 1 else 0.4

    # Collect all works needing images
    needs_fix = []
    for f in sorted(output_dir.glob('*_analysis.json')):
        with open(f) as fh:
            data = json.load(fh)
        if data.get('category') != 'Fine Arts':
            continue
        for w in data.get('works', []):
            ind = w.get('indicator', '')
            name = w.get('name', '')
            # Skip non-visual works: poems, novels, compositions, general sections
            skip_indicators = ('Artist', 'Movement', 'Poet', 'Poem', 'Author', 'Novel',
                               'Play', 'Playwright', 'Composer', 'Composition', 'Theorist', 'Architect')
            if ind in skip_indicators or any(x in name for x in ['General', 'Biographical', 'Other Works', 'sonnet', 'poem', 'Poem']):
                continue
            has_url = any(i.get('url') for i in w.get('images', []))
            if not has_url:
                needs_fix.append((f, data['topic'], w['name']))

    print(f'Works needing images: {len(needs_fix)}', flush=True)

    fixed = 0
    failed = 0

    for f, topic, work_name in needs_fix:
        url = find_image(work_name, topic, delay)

        # Load fresh, update, save immediately
        with open(f) as fh:
            data = json.load(fh)

        for w in data.get('works', []):
            if w['name'] == work_name:
                if url:
                    if w.get('images'):
                        w['images'][0]['url'] = url
                    else:
                        w['images'] = [{'url': url, 'caption': work_name}]

                    # Sync cards
                    for c in data.get('cards', []):
                        if c.get('work') == work_name:
                            for ci in c.get('images', []):
                                if not ci.get('url'):
                                    ci['url'] = url

                    with open(f, 'w') as fh:
                        json.dump(data, fh, indent=2, ensure_ascii=False)

                    fixed += 1
                    print(f'  OK: {topic} / {work_name}', flush=True)
                else:
                    failed += 1
                    print(f'  MISS: {topic} / {work_name}', flush=True)
                break

    print(f'\nDone! Fixed: {fixed}, Missing: {failed}', flush=True)

if __name__ == '__main__':
    main()
