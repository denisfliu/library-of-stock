#!/usr/bin/env python
"""
build_changelog.py — Extract topic-level changelog from git history.

Scans git commits that touched output/*/analysis.json, identifies which
topics were newly added (first pass) vs updated (second pass / refinement),
and outputs dev/changelog_data.json for the changelog page.

Usage:
    python dev/build_changelog.py
"""
import sys as _sys
from pathlib import Path as _Path
_sys.path.insert(0, str(_Path(__file__).resolve().parent.parent))
import lib.common  # noqa: F401  (utf-8 stdio + shared paths)

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
    '0c294ad2',  # cross_refs schema migration (target_* -> slug/topic/work) — 663 files
}


def run(args):
    return subprocess.check_output(args, cwd=ROOT, text=True, encoding='utf-8').strip()


def main():
    # Build slug → canonical name mapping from topic_index.json
    slug_to_name = {}
    index_path = ROOT / 'output' / 'topic_index.json'
    if index_path.exists():
        with open(index_path, encoding='utf-8') as f:
            idx = json.load(f)
        for val in idx.values():
            if val.get('type') == 'topic':
                slug_to_name[val['slug']] = val['topic']

    # One git call for the whole history: commit header lines followed by
    # per-file name-status lines for each commit.
    try:
        raw = run(['git', 'log', '--format=%h|%ad', '--date=short',
                   '--name-status', '--', 'output/*/analysis.json'])
    except (subprocess.CalledProcessError, OSError) as e:
        print(f'WARNING: git log failed ({e}); leaving changelog unchanged')
        return

    days = defaultdict(lambda: {'added': set(), 'updated': set()})
    current_date = None
    skip_commit = False

    for line in raw.splitlines():
        line = line.rstrip()
        if not line:
            continue
        if '|' in line and '\t' not in line:
            h, current_date = line.split('|', 1)
            skip_commit = h[:8] in SKIP_HASHES
            continue
        if skip_commit or current_date is None or '\t' not in line:
            continue
        # "A\tpath", "M\tpath", or "R100\toldpath\tnewpath" (renames are
        # detected by default in git log; count them at the new path like
        # the old diff-tree plumbing counted an A).
        fields = line.split('\t')
        status, path = fields[0], fields[-1]
        m = re.match(r'output/(.+)/analysis\.json', path)
        if not m:
            continue
        name = slug_to_name.get(m.group(1), m.group(1).replace('_', ' ').title())
        if status.startswith(('A', 'R', 'C')):
            days[current_date]['added'].add(name)
        elif status == 'M':
            days[current_date]['updated'].add(name)

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

    with open(OUTPUT, 'w', encoding='utf-8') as f:
        json.dump(result, f, indent=2, ensure_ascii=False)

    total_added = sum(len(d['added']) for d in result)
    total_updated = sum(len(d['updated']) for d in result)
    print(f'Wrote {OUTPUT} ({len(result)} days, '
          f'{total_added} first-pass, {total_updated} updated)')


if __name__ == '__main__':
    main()
