#!/usr/bin/env python3
"""Fix missing images across all VFA analysis JSONs.

Thin wrapper around lib/images.py — scans all analysis files and calls
find_image() for any visual work missing an embedded image URL.

Usage:
    python3 lib/fix_images.py          # fix all missing
    python3 lib/fix_images.py --delay 1  # custom delay (default 2s)
"""
import json, sys
from pathlib import Path

# Add parent to path so we can import from lib
sys.path.insert(0, str(Path(__file__).parent.parent))
from lib.images import find_image, set_work_image, API_DELAY
import lib.images as img_module

ROOT = Path(__file__).parent.parent

# Indicators that represent visual works (should have images)
VISUAL_INDICATORS = {'Painting', 'Sculpture', 'Fresco', 'Print', 'Engraving',
                     'Mural', 'Drawing', 'Installation', 'Relief', 'Mosaic'}

SKIP_NAME_FRAGMENTS = ['General', 'Biographical', 'Other Works', 'sonnet',
                       'poem', 'Poem', 'symphony', 'Symphony']


def main():
    output_dir = ROOT / 'output'

    # Parse --delay flag
    delay = API_DELAY
    if '--delay' in sys.argv:
        idx = sys.argv.index('--delay')
        if idx + 1 < len(sys.argv):
            delay = float(sys.argv[idx + 1])
            img_module.API_DELAY = delay

    # Collect visual works needing images
    needs_fix = []
    for f in sorted(output_dir.glob('*_analysis.json')):
        with open(f) as fh:
            data = json.load(fh)
        if data.get('category') != 'Fine Arts':
            continue
        for w in data.get('works', []):
            ind = w.get('indicator', '')
            name = w.get('name', '')
            # Only search for visual works
            if ind not in VISUAL_INDICATORS:
                continue
            if any(x in name for x in SKIP_NAME_FRAGMENTS):
                continue
            has_url = any(i.get('url') for i in w.get('images', []))
            if not has_url:
                needs_fix.append((f, data['topic'], w['name']))

    print(f'Visual works needing images: {len(needs_fix)} (delay: {delay}s)',
          flush=True)

    fixed = 0
    cached = 0
    failed = 0

    for f, topic, work_name in needs_fix:
        url = find_image(work_name, topic)

        if not url:
            failed += 1
            print(f'  MISS: {topic} / {work_name}', flush=True)
            continue

        # Load fresh, update, save
        with open(f) as fh:
            data = json.load(fh)

        set_work_image(data, work_name, url)

        with open(f, 'w') as fh:
            json.dump(data, fh, indent=2, ensure_ascii=False)

        fixed += 1
        print(f'  OK: {topic} / {work_name}', flush=True)

    print(f'\nDone! Fixed: {fixed}, Missing: {failed}', flush=True)


if __name__ == '__main__':
    main()
