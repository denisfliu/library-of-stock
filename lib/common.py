"""common.py — Shared paths and helpers for the stock pipeline.

Every script should resolve paths through these constants instead of
hand-rolling ``Path(__file__).parent.parent...`` chains or cwd-relative
paths. ``file_lock`` is the portable (Windows + POSIX) replacement for
the old ``fcntl.flock`` usage.
"""
import sys
from pathlib import Path

from filelock import FileLock

# Windows consoles default to cp1252, which crashes print() on accented
# topic names (e.g. "Chénier"). Every entry script imports this module,
# so force UTF-8 stdio once here.
for _stream in (sys.stdout, sys.stderr):
    if _stream is not None and hasattr(_stream, 'reconfigure'):
        _stream.reconfigure(encoding='utf-8', errors='replace')

ROOT = Path(__file__).resolve().parent.parent
OUTPUT_DIR = ROOT / 'output'
QUEUE_DIR = ROOT / 'queue'
CACHE_DIR = ROOT / 'cache'
DEV_DIR = ROOT / 'dev'
TOPIC_INDEX_FILE = OUTPUT_DIR / 'topic_index.json'


def file_lock(path: Path) -> FileLock:
    """Exclusive cross-process lock. Use as a context manager.

    Blocks until the lock is acquired. The lock file is created (with
    parents) if missing.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    return FileLock(str(path))
