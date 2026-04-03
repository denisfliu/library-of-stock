#!/usr/bin/env python3
"""
build_changelog.py — Extract topic-level changelog from git history.

Scans git commits that touched output/*/analysis.json, identifies which
topics were newly added (first pass) vs updated (second pass / refinement),
and outputs dev/changelog_data.json for the changelog page.

Usage:
    python3 dev/build_changelog.py
"""
import json
import subprocess
import re
from pathlib import Path
from collections import defaultdict

ROOT = Path(__file__).parent.parent
OUTPUT = ROOT / 'dev' / 'changelog_data.json'

# Commits that mass-modify analysis.json for non-content reasons
SKIP_HASHES = {
    '643630af',  # fixed cross ref links — touched 545 files
}


def run(cmd):
    return subprocess.check_output(cmd, shell=True, cwd=ROOT, text=True).strip()


def main():
    # Build slug → canonical name mapping from topic_index.json
    slug_to_name = {}
    slug_to_category = {}
    index_path = ROOT / 'output' / 'topic_index.json'
    if index_path.exists():
        with open(index_path) as f:
            idx = json.load(f)
        for val in idx.values():
            if val.get('type') == 'topic':
                slug_to_name[val['slug']] = val['topic']
                slug_to_category[val['slug']] = val.get('category', '')

    # Get all commits that touched analysis.json
    log_lines = run(
        'git log --format="%h|%ad|%s" --date=short -- "output/*/analysis.json"'
    ).splitlines()

    days = defaultdict(lambda: {'added': set(), 'updated': set()})

    for line in log_lines:
        parts = line.split('|', 2)
        if len(parts) != 3:
            continue
        h, date, msg = [p.strip() for p in parts]

        if h[:8] in SKIP_HASHES:
            continue

        # Single diff-tree call with --name-status gives A/M status per file
        raw = run(
            f'git diff-tree --no-commit-id -r --name-status {h} '
            f'-- "output/*/analysis.json"'
        )

        for diff_line in raw.splitlines():
            diff_line = diff_line.strip()
            if not diff_line:
                continue
            # Format: "A\toutput/slug/analysis.json" or "M\t..."
            status, path = diff_line.split('\t', 1)
            m = re.match(r'output/(.+)/analysis\.json', path)
            if not m:
                continue
            slug = m.group(1)
            name = slug_to_name.get(slug, slug.replace('_', ' ').title())

            if status == 'A':
                days[date]['added'].add(name)
            elif status == 'M':
                days[date]['updated'].add(name)

    # Build result — don't double-count (added > updated for same day)
    result = []
    for date in sorted(days.keys(), reverse=True):
        d = days[date]
        added = sorted(d['added'])
        updated = sorted(d['updated'] - d['added'])
        if added or updated:
            result.append({
                'date': date,
                'added': added,
                'updated': updated,
            })

    with open(OUTPUT, 'w') as f:
        json.dump(result, f, indent=2, ensure_ascii=False)

    total_added = sum(len(d['added']) for d in result)
    total_updated = sum(len(d['updated']) for d in result)
    print(f'Wrote {OUTPUT} ({len(result)} days, '
          f'{total_added} first-pass, {total_updated} updated)')


if __name__ == '__main__':
    main()
