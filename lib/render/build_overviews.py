"""build_overviews.py — Render every unit overview page.

Usage:
    python lib/render/build_overviews.py [--force] [--unit SLUG]

Incremental: a page is re-rendered when its overview.json OR the topic
index is newer than the existing overview.html — link resolution depends
on the whole corpus, so new topic pages must flip red links to blue.
"""
import argparse
import json
import sys as _sys
from pathlib import Path as _Path

_sys.path.insert(0, str(_Path(__file__).resolve().parent.parent.parent))
from lib.common import CATEGORIES_DIR, TOPIC_INDEX_FILE
from lib.render.render_overview import render_overview
from lib.sweep.matcher import TopicMatcher


def build(force: bool = False, only_unit: str | None = None,
          matcher: TopicMatcher | None = None) -> None:
    overview_files = sorted(CATEGORIES_DIR.glob('*/overview.json'))
    if only_unit:
        overview_files = [p for p in overview_files
                          if p.parent.name == only_unit]
        if not overview_files:
            raise SystemExit(f'No overview.json for unit {only_unit!r} '
                             f'under {CATEGORIES_DIR}')
    if not overview_files:
        print('No overview pages to render.')
        return

    index_mtime = (TOPIC_INDEX_FILE.stat().st_mtime
                   if TOPIC_INDEX_FILE.exists() else 0)

    # Coverage stats consumed by build_index.py for the explore strip.
    stats_path = CATEGORIES_DIR / 'stats.json'
    stats = {}
    if stats_path.exists():
        with open(stats_path, encoding='utf-8') as f:
            stats = json.load(f)

    rendered = skipped = 0
    for json_path in overview_files:
        # Legacy build artifact — panels now fetch unit_questions/{unit}
        # from R2 at view time; remove stragglers so deploy stops
        # shipping them via the *_data.js rule.
        legacy_js = json_path.parent / 'questions_data.js'
        if legacy_js.exists():
            legacy_js.unlink()
            print(f'  removed legacy {legacy_js}')
        out_path = json_path.parent / 'overview.html'
        ref_path = json_path.parent / 'questions.json'
        ref_mtime = ref_path.stat().st_mtime if ref_path.exists() else 0
        if (not force and out_path.exists()
                and out_path.stat().st_mtime >= json_path.stat().st_mtime
                and out_path.stat().st_mtime >= index_mtime
                and out_path.stat().st_mtime >= ref_mtime):
            skipped += 1
            continue
        with open(json_path, encoding='utf-8') as f:
            overview = json.load(f)
        if matcher is None:
            matcher = TopicMatcher()
        s = render_overview(overview, matcher, out_path)
        stats[s['unit']] = s
        rendered += 1
        print(f'  rendered {out_path}')

    if rendered:
        # Drop stats for deleted overviews.
        live = {p.parent.name for p in CATEGORIES_DIR.glob('*/overview.json')}
        stats = {k: v for k, v in stats.items() if k in live}
        with open(stats_path, 'w', encoding='utf-8') as f:
            json.dump(stats, f, indent=2, ensure_ascii=False)

    print(f'Overviews: {rendered} rendered, {skipped} up to date')


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--force', action='store_true')
    ap.add_argument('--unit', help='render only this unit slug')
    args = ap.parse_args()
    build(force=args.force, only_unit=args.unit)
