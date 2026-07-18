"""embeddings.sqlite — sidecar store for corpus vectors.

Separate DB from qbreader.sqlite so re-seeding the mirror from a backup
never touches embeddings; rows join back via qbreader ``_id``. Vectors are
stored as fp16 blobs (half the size of fp32, negligible quality impact)
and returned as normalized fp32 matrices.

Keying: (kind, id, part, model). ``part`` is -1 except for bonus parts
(0-based part index). ``kind`` ∈ {'tossup', 'bonus_part', 'topic'} so far;
'topic' rows use the output/ slug as ``id``.
"""
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from lib.common import MIRROR_DIR

DB_PATH = MIRROR_DIR / "embeddings.sqlite"

_SCHEMA = """
create table if not exists embeddings (
    kind text not null,
    id text not null,
    part integer not null default -1,
    model text not null,
    dims integer not null,
    vector blob not null,
    updated_at text not null,
    primary key (kind, id, part, model)
);
"""


class EmbeddingStore:
    def __init__(self, path: Path = DB_PATH):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(path)
        self.db.executescript(_SCHEMA)

    def existing_ids(self, kind: str, model: str) -> set:
        """(id, part) pairs already embedded — for resumable runs."""
        rows = self.db.execute(
            "select id, part from embeddings where kind=? and model=?", (kind, model)
        )
        return set(rows)

    def put_many(self, kind: str, model: str, rows) -> None:
        """rows: iterable of (id, part, fp32_vector). Commits once."""
        now = datetime.now(timezone.utc).isoformat(timespec="seconds")
        self.db.executemany(
            "insert or replace into embeddings values (?,?,?,?,?,?,?)",
            (
                (kind, id_, part, model, len(vec), np.asarray(vec, np.float16).tobytes(), now)
                for id_, part, vec in rows
            ),
        )
        self.db.commit()

    def load_matrix(self, kind: str, model: str):
        """Returns (keys, matrix): keys is [(id, part)], matrix is fp32
        L2-normalized, row-aligned with keys."""
        keys, blobs, dims = [], [], None
        for id_, part, d, blob in self.db.execute(
            "select id, part, dims, vector from embeddings where kind=? and model=? order by id, part",
            (kind, model),
        ):
            keys.append((id_, part))
            blobs.append(blob)
            dims = d
        if not keys:
            return [], np.empty((0, 0), np.float32)
        mat = np.frombuffer(b"".join(blobs), np.float16).reshape(len(keys), dims).astype(np.float32)
        norms = np.linalg.norm(mat, axis=1, keepdims=True)
        norms[norms == 0] = 1.0
        return keys, mat / norms

    def count(self, kind: str, model: str) -> int:
        return self.db.execute(
            "select count(*) from embeddings where kind=? and model=?", (kind, model)
        ).fetchone()[0]
