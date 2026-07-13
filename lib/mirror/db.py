"""db.py — SQLite schema and helpers for the full qbreader mirror.

The mirror is a gitignored, local-first copy of the entire qbreader
question database (mirror/qbreader.sqlite). It is seeded once from the
official backup dumps (lib/mirror/import_backup.py) and kept current by
lib/mirror/sync.py, which is the pipeline's only remaining live-API
dependency. Everything else (topic fetches, frequency lists, unit
captures, set builds) reads from here.

Design: every qbreader field is preserved. Fields the pipeline queries
by get their own indexed columns; anything else lands verbatim in the
`extra` JSON column (e.g. `reports`), so schema drift upstream never
loses data. Docs arrive as plain JSON — mongoexport extended-JSON
wrappers ($oid/$numberInt/$date) are decoded by decode_extended() first,
so the same flatten_* row builders serve both the backup importer and
the live-API sync.
"""
import json
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from lib.common import MIRROR_DIR

DB_PATH = MIRROR_DIR / "qbreader.sqlite"

SCHEMA = """
CREATE TABLE IF NOT EXISTS sets (
    id         TEXT PRIMARY KEY,
    name       TEXT NOT NULL UNIQUE,
    year       INTEGER,
    difficulty INTEGER,
    standard   INTEGER,
    extra      TEXT
);

CREATE TABLE IF NOT EXISTS packets (
    id       TEXT PRIMARY KEY,
    set_id   TEXT NOT NULL,
    set_name TEXT NOT NULL,
    name     TEXT,
    number   INTEGER,
    extra    TEXT
);
CREATE INDEX IF NOT EXISTS idx_packets_set ON packets(set_id);

CREATE TABLE IF NOT EXISTS tossups (
    id                    TEXT PRIMARY KEY,
    set_id                TEXT NOT NULL,
    set_name              TEXT NOT NULL,
    set_year              INTEGER,
    packet_id             TEXT,
    packet_number         INTEGER,
    number                INTEGER,
    category              TEXT,
    subcategory           TEXT,
    alternate_subcategory TEXT,
    difficulty            INTEGER,
    question              TEXT,
    question_sanitized    TEXT,
    answer                TEXT,
    answer_sanitized      TEXT,
    updated_at            TEXT,
    extra                 TEXT
);
CREATE INDEX IF NOT EXISTS idx_tossups_set ON tossups(set_name);
CREATE INDEX IF NOT EXISTS idx_tossups_taxonomy ON tossups(category, subcategory);
CREATE INDEX IF NOT EXISTS idx_tossups_difficulty ON tossups(difficulty);

CREATE TABLE IF NOT EXISTS bonuses (
    id                    TEXT PRIMARY KEY,
    set_id                TEXT NOT NULL,
    set_name              TEXT NOT NULL,
    set_year              INTEGER,
    packet_id             TEXT,
    packet_number         INTEGER,
    number                INTEGER,
    category              TEXT,
    subcategory           TEXT,
    alternate_subcategory TEXT,
    difficulty            INTEGER,
    leadin                TEXT,
    leadin_sanitized      TEXT,
    parts                 TEXT,
    parts_sanitized       TEXT,
    answers               TEXT,
    answers_sanitized     TEXT,
    "values"              TEXT,
    difficulty_modifiers  TEXT,
    updated_at            TEXT,
    extra                 TEXT
);
CREATE INDEX IF NOT EXISTS idx_bonuses_set ON bonuses(set_name);
CREATE INDEX IF NOT EXISTS idx_bonuses_taxonomy ON bonuses(category, subcategory);
CREATE INDEX IF NOT EXISTS idx_bonuses_difficulty ON bonuses(difficulty);

CREATE TABLE IF NOT EXISTS meta (
    key   TEXT PRIMARY KEY,
    value TEXT
);
"""


def open_db(path: Path | None = None, create: bool = False) -> sqlite3.Connection:
    """Open the mirror database. With create=True, missing tables are
    created; without it, a missing file is an error (points the user at
    the importer instead of silently querying an empty mirror)."""
    path = Path(path) if path else DB_PATH
    if not create and not path.exists():
        raise FileNotFoundError(
            f"{path} not found — seed the mirror with "
            f"lib/mirror/import_backup.py (see docs/question_store.md)")
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    if create:
        conn.executescript(SCHEMA)
    return conn


def decode_extended(value):
    """Recursively decode mongoexport extended-JSON wrappers to plain
    Python values ($oid → str, $numberInt/Long → int, $numberDouble →
    float, $date → ISO-8601 UTC string)."""
    if isinstance(value, dict):
        if len(value) == 1:
            (key, inner), = value.items()
            if key == "$oid":
                return inner
            if key in ("$numberInt", "$numberLong"):
                return int(inner)
            if key == "$numberDouble":
                return float(inner)
            if key == "$date":
                inner = decode_extended(inner)
                if isinstance(inner, (int, float)):
                    # Millisecond precision, matching the live API's
                    # ISO strings, so backup-seeded and synced rows agree.
                    dt = datetime.fromtimestamp(inner / 1000, tz=timezone.utc)
                    return (dt.strftime("%Y-%m-%dT%H:%M:%S")
                            + f".{int(inner) % 1000:03d}Z")
                return inner
        return {k: decode_extended(v) for k, v in value.items()}
    if isinstance(value, list):
        return [decode_extended(v) for v in value]
    return value


def _json_or_none(value):
    return json.dumps(value, ensure_ascii=False) if value is not None else None


def _extra(doc: dict, mapped: set) -> str | None:
    leftover = {k: v for k, v in doc.items() if k not in mapped}
    return json.dumps(leftover, ensure_ascii=False) if leftover else None


def flatten_set(doc: dict) -> dict:
    mapped = {"_id", "name", "year", "difficulty", "standard"}
    return {
        "id": doc["_id"],
        "name": doc["name"],
        "year": doc.get("year"),
        "difficulty": doc.get("difficulty"),
        "standard": 1 if doc.get("standard") else 0,
        "extra": _extra(doc, mapped),
    }


def flatten_packet(doc: dict) -> dict:
    mapped = {"_id", "set", "name", "number"}
    return {
        "id": doc["_id"],
        "set_id": doc["set"]["_id"],
        "set_name": doc["set"]["name"],
        "name": doc.get("name"),
        "number": doc.get("number"),
        "extra": _extra(doc, mapped),
    }


_QUESTION_BASE = {"_id", "set", "packet", "number", "category", "subcategory",
                  "alternate_subcategory", "difficulty", "updatedAt"}


def _question_base(doc: dict) -> dict:
    return {
        "id": doc["_id"],
        "set_id": doc["set"]["_id"],
        "set_name": doc["set"]["name"],
        "set_year": doc["set"].get("year"),
        "packet_id": (doc.get("packet") or {}).get("_id"),
        "packet_number": (doc.get("packet") or {}).get("number"),
        "number": doc.get("number"),
        "category": doc.get("category"),
        "subcategory": doc.get("subcategory"),
        "alternate_subcategory": doc.get("alternate_subcategory"),
        "difficulty": doc.get("difficulty"),
        "updated_at": doc.get("updatedAt"),
    }


def flatten_tossup(doc: dict) -> dict:
    mapped = _QUESTION_BASE | {"question", "question_sanitized",
                               "answer", "answer_sanitized"}
    row = _question_base(doc)
    row.update({
        "question": doc.get("question"),
        "question_sanitized": doc.get("question_sanitized"),
        "answer": doc.get("answer"),
        "answer_sanitized": doc.get("answer_sanitized"),
        "extra": _extra(doc, mapped),
    })
    return row


def flatten_bonus(doc: dict) -> dict:
    mapped = _QUESTION_BASE | {"leadin", "leadin_sanitized", "parts",
                               "parts_sanitized", "answers",
                               "answers_sanitized", "values",
                               "difficultyModifiers"}
    row = _question_base(doc)
    row.update({
        "leadin": doc.get("leadin"),
        "leadin_sanitized": doc.get("leadin_sanitized"),
        "parts": _json_or_none(doc.get("parts")),
        "parts_sanitized": _json_or_none(doc.get("parts_sanitized")),
        "answers": _json_or_none(doc.get("answers")),
        "answers_sanitized": _json_or_none(doc.get("answers_sanitized")),
        "values": _json_or_none(doc.get("values")),
        "difficulty_modifiers": _json_or_none(doc.get("difficultyModifiers")),
        "extra": _extra(doc, mapped),
    })
    return row


def upsert_rows(conn: sqlite3.Connection, table: str, rows: list[dict]) -> None:
    """INSERT OR REPLACE a batch of flattened rows (idempotent by id)."""
    if not rows:
        return
    cols = list(rows[0].keys())
    col_list = ", ".join(f'"{c}"' for c in cols)
    placeholders = ", ".join(f":{c}" for c in cols)
    conn.executemany(
        f'INSERT OR REPLACE INTO {table} ({col_list}) VALUES ({placeholders})',
        rows)


def set_meta(conn: sqlite3.Connection, key: str, value: str) -> None:
    conn.execute("INSERT OR REPLACE INTO meta (key, value) VALUES (?, ?)",
                 (key, value))


def get_meta(conn: sqlite3.Connection, key: str) -> str | None:
    row = conn.execute("SELECT value FROM meta WHERE key = ?", (key,)).fetchone()
    return row["value"] if row else None
