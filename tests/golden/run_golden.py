"""run_golden.py — Golden-file render test.

Renders a small frozen corpus (tests/golden/fixtures/output/) through the
real renderers in a throwaway sandbox — pointed there via the STOCK_ROOT
env override in lib/common.py — and diffs every produced artifact against
the committed snapshots in tests/golden/expected/.

Usage:
    python tests/golden/run_golden.py            # verify; exit 1 on drift
    python tests/golden/run_golden.py --update   # rebless the snapshots

A failure means renderer output changed. If the change is intended, eyeball
the diff, re-run with --update, and commit the new snapshots together with
the renderer change. Snapshots are stored with LF line endings; comparison
normalizes CRLF so the test passes identically on Windows and Linux CI.
"""
import difflib
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent
FIXTURES = HERE / 'fixtures'
EXPECTED = HERE / 'expected'

# Renderer entry points under test, in build.sh order.
STEPS = [
    ['lib/crossref/crossref.py'],
    ['lib/rerender.py', '--force'],
    ['lib/render/render_cards.py', '--force'],
    ['lib/render/render_questions.py', '--force'],
    ['lib/sweep/build_set.py', '--all', '--rematch-only'],
    ['lib/render/build_overviews.py', '--force'],
]

# Every artifact the steps produce that is deterministic. report.json is
# deliberately absent: it embeds a generation date.
GOLDEN_FILES = [
    'output/topic_index.json',
    'output/amos_tutuola/stock.html',
    'output/amos_tutuola/cards.html',
    'output/amos_tutuola/questions.html',
    'output/christopher_okigbo/stock.html',
    'output/christopher_okigbo/cards.html',
    'output/christopher_okigbo/questions.html',
    'output/_categories/fixture_lit/overview.html',
    'output/_sets/fixture_set/set.json',
    'output/_sets/fixture_set/sweep.html',
]

MAX_DIFF_LINES = 60


def render_into_sandbox(sandbox: Path) -> bool:
    shutil.copytree(FIXTURES / 'output', sandbox / 'output')
    env = {
        **os.environ,
        'STOCK_ROOT': str(sandbox),
        # Set-iteration order must never leak into rendered output; pinning
        # the hash seed makes any such leak a hard failure instead of flake.
        'PYTHONHASHSEED': '0',
    }
    for step in STEPS:
        cmd = [sys.executable, str(REPO / step[0]), *step[1:]]
        proc = subprocess.run(cmd, cwd=sandbox, env=env,
                              capture_output=True, text=True, encoding='utf-8')
        if proc.returncode != 0:
            print(f'STEP FAILED ({proc.returncode}): {" ".join(step)}')
            print(proc.stdout)
            print(proc.stderr, file=sys.stderr)
            return False
    return True


def normalized(path: Path) -> str:
    return path.read_text(encoding='utf-8').replace('\r\n', '\n')


def compare(sandbox: Path) -> int:
    failures = 0
    for rel in GOLDEN_FILES:
        produced = sandbox / rel
        golden = EXPECTED / rel
        if not produced.exists():
            print(f'MISSING OUTPUT: {rel} was not produced')
            failures += 1
            continue
        if not golden.exists():
            print(f'MISSING SNAPSHOT: tests/golden/expected/{rel} '
                  f'(run with --update)')
            failures += 1
            continue
        got, want = normalized(produced), normalized(golden)
        if got != want:
            failures += 1
            print(f'DIFF: {rel}')
            diff = difflib.unified_diff(
                want.splitlines(), got.splitlines(),
                fromfile=f'expected/{rel}', tofile=f'produced/{rel}',
                lineterm='')
            for i, line in enumerate(diff):
                if i >= MAX_DIFF_LINES:
                    print('  ... (diff truncated)')
                    break
                print(f'  {line}')
    return failures


def update(sandbox: Path) -> None:
    for rel in GOLDEN_FILES:
        produced = sandbox / rel
        if not produced.exists():
            raise SystemExit(f'MISSING OUTPUT: {rel} was not produced')
        golden = EXPECTED / rel
        golden.parent.mkdir(parents=True, exist_ok=True)
        with open(golden, 'w', encoding='utf-8', newline='\n') as f:
            f.write(normalized(produced))
        print(f'  blessed {rel}')


def main() -> int:
    do_update = '--update' in sys.argv
    with tempfile.TemporaryDirectory(prefix='stock_golden_') as tmp:
        sandbox = Path(tmp)
        if not render_into_sandbox(sandbox):
            return 1
        if do_update:
            update(sandbox)
            print('Snapshots updated. Review the diff, then commit.')
            return 0
        failures = compare(sandbox)
    if failures:
        print(f'\nGOLDEN TEST FAILED: {failures} file(s) drifted. '
              f'If intended: python tests/golden/run_golden.py --update')
        return 1
    print(f'Golden test passed: {len(GOLDEN_FILES)} files match.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
