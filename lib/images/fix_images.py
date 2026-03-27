#!/usr/bin/env python3
"""Fix missing images across all VFA analysis JSONs.

Thin wrapper around lib/images.py — scans all analysis files and calls
find_image() for any visual work missing an embedded image URL.

Usage:
    python3 lib/images/fix_images.py                  # fix all missing (skip known failures)
    python3 lib/images/fix_images.py --slug hokusai   # fix one topic only
    python3 lib/images/fix_images.py --retry          # retry previously failed lookups
    python3 lib/images/fix_images.py --delay 1        # custom delay (default 2s)
"""
import json, sys
from pathlib import Path

# Add project root to path; remove lib/ to avoid shadowing stdlib queue
_project_root = str(Path(__file__).resolve().parent.parent.parent)
_lib_dir = str(Path(__file__).resolve().parent.parent.parent / "lib")
sys.path.insert(0, _project_root)
if _lib_dir in sys.path:
    sys.path.remove(_lib_dir)
from lib.images.images import find_image, set_work_image, API_DELAY, CACHE_FILE
import lib.images.images as img_module

ROOT = Path(__file__).resolve().parent.parent.parent

# Indicators that represent visual works (should have images)
VISUAL_INDICATORS = {'Painting', 'Sculpture', 'Fresco', 'Print', 'Engraving',
                     'Mural', 'Drawing', 'Installation', 'Relief', 'Mosaic',
                     'Building', 'Architect', 'Architecture'}

SKIP_NAME_FRAGMENTS = ['General', 'Biographical', 'Other Works', 'sonnet',
                       'poem', 'Poem', 'symphony', 'Symphony']


def main():
    output_dir = ROOT / 'output'

    # Parse flags
    delay = API_DELAY
    slug = None
    retry = '--retry' in sys.argv

    if '--delay' in sys.argv:
        idx = sys.argv.index('--delay')
        if idx + 1 < len(sys.argv):
            delay = float(sys.argv[idx + 1])
            img_module.API_DELAY = delay

    if '--slug' in sys.argv:
        idx = sys.argv.index('--slug')
        if idx + 1 < len(sys.argv):
            slug = sys.argv[idx + 1]

    # Load failure cache to skip works already tried and not found
    known_cache = {}
    if CACHE_FILE.exists():
        with open(CACHE_FILE) as f:
            known_cache = json.load(f)

    # Determine which analysis files to scan
    if slug:
        analysis_files = [output_dir / slug / 'analysis.json']
        analysis_files = [f for f in analysis_files if f.exists()]
    else:
        analysis_files = sorted(output_dir.glob('*/analysis.json'))

    # Collect visual works needing images
    needs_fix = []
    skipped_failures = 0
    for f in analysis_files:
        with open(f) as fh:
            data = json.load(fh)
        if data.get('category') != 'Fine Arts':
            continue
        topic = data['topic']
        for w in data.get('works', []):
            ind = w.get('indicator', '')
            name = w.get('name', '')
            # Only search for visual works
            if ind not in VISUAL_INDICATORS:
                continue
            if any(x in name for x in SKIP_NAME_FRAGMENTS):
                continue
            has_url = any(i.get('url') for i in w.get('images', []))
            if has_url:
                continue
            # Skip previously failed lookups unless --retry
            cache_key = f'{topic} / {name}'
            if not retry and cache_key in known_cache and known_cache[cache_key] == '':
                skipped_failures += 1
                continue
            needs_fix.append((f, topic, name))

    scope = f'slug={slug}' if slug else 'all topics'
    print(f'Visual works to search: {len(needs_fix)} ({scope}, delay: {delay}s)'
          + (f', skipping {skipped_failures} known failures (use --retry to re-try)' if skipped_failures else ''),
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
