"""publish.py — export the mirror + our topic metadata as static website
artifacts and upload them to Cloudflare R2.

This is the static data plane for the question reader (Denis decisions
July 2026: R2 static shards, no server; see docs/mirror.md). Artifacts
are staged under mirror/publish/ and uploaded incrementally — a file is
re-uploaded only when its hash differs from the remote manifest's.

  sets/{slug}.json    one file per set — the unit of fetch for reading
  catalog.json        columnar index of every question (id, set, packet,
                      number, taxonomy, difficulty) — random mode + filters
  answerlines.json    answer text aligned with catalog rows — client-side
                      answerline search
  topics.json         study-guide overlay: our metadata (year, country,
                      coordinates, tags, group, unit, ...) + question refs
  manifest.json       hashes + counts; clients cache-bust and the uploader
                      diffs against it

Usage:
    python lib/mirror/publish.py                  # stage only
    python lib/mirror/publish.py --upload         # stage + upload changed
    python lib/mirror/publish.py --upload --all   # force re-upload
Upload shells out to `npx wrangler r2 object put` (needs `npx wrangler
login` once; several uploads run in parallel).
"""
import argparse
import gzip
import hashlib
import json
import re
import shutil
import subprocess
import sys
import time
import unicodedata
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from lib.common import CATEGORIES_DIR, MIRROR_DIR, OUTPUT_DIR
from lib.mirror import db as mirror_db
from lib.mirror import query as mirror_query
from lib.questions_store import shard_slug
from lib.sweep.answerline_kb import KBLookup
from lib.sweep.section_index import SectionIndex
from lib.units import unit_for_guide

PUBLISH_DIR = MIRROR_DIR / "publish"
DEFAULT_BUCKET = "library-of-stock-data"

_NORM_NONALNUM = re.compile(r"[^a-z0-9\s]")
_NORM_WS = re.compile(r"\s+")
_NORM_ARTICLE = re.compile(r"^(the|a|an) ")


def norm_ans(s: str) -> str:
    """Port of reader.js normAns — canonicalizes an answer string to a key.

    The reader re-applies its own normAns (idempotent) so the JS normalizer
    stays authoritative and the keys line up with each LOG entry's key.
    """
    s = unicodedata.normalize("NFD", s or "")
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    s = _NORM_NONALNUM.sub(" ", s.lower())
    s = _NORM_WS.sub(" ", s).strip()
    return _NORM_ARTICLE.sub("", s)


_U_SPAN = re.compile(r"<u>(.*?)</u>", re.I | re.S)
_B_SPAN = re.compile(r"<b>(.*?)</b>", re.I | re.S)
_TAG = re.compile(r"<[^>]+>")


def answer_key(raw: str, san: str) -> str:
    """The drill/stats answerline key — the bold-underline CORE of the raw
    answer (not the full accept/prompt clause), so one answer unifies across
    questions that phrase their accept clauses differently. Falls back to the
    pre-bracket main answer when there's no markup. Mirrors reader.js
    answerKey; deduped into catalog.answerline_values.
    """
    raw = raw or ""
    cores = [_TAG.sub("", m) for m in _U_SPAN.findall(raw)]
    if not cores:
        cores = [_TAG.sub("", m) for m in _B_SPAN.findall(raw)]
    cores = [c for c in cores if c.strip()]
    if cores:
        base = cores[0]
    else:
        base = re.split(r"[\[(]", _TAG.sub("", san or raw))[0]
    return norm_ans(base)

# Topic metadata fields published to topics.json (when present).
_TOPIC_FIELDS = ("topic", "category", "subcategory", "genre", "year",
                 "year_end", "continent", "country", "coordinates", "group",
                 "tags")


def _dump(data) -> bytes:
    return json.dumps(data, ensure_ascii=False,
                      separators=(",", ":")).encode("utf-8")


def _write_if_changed(path: Path, payload: bytes) -> bool:
    if path.exists() and path.read_bytes() == payload:
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)
    return True


def _unique_slugs(names: list[str]) -> dict[str, str]:
    """Deterministic per-set file slugs. shard_slug can collide (e.g.
    '2023 CREEK' vs '2023 CREEK+'); later occurrences in set-list order
    get a numeric suffix. The catalog publishes the mapping, so clients
    never derive slugs themselves."""
    slugs, used = {}, {}
    for name in names:
        base = shard_slug(name)
        used[base] = used.get(base, 0) + 1
        slugs[name] = base if used[base] == 1 else f"{base}_{used[base]}"
    return slugs


def stage_sets(conn, catalog, slug_map: dict[str, str]) -> int:
    """One JSON file per set."""
    written = 0
    for name, slug in slug_map.items():
        payload = _dump(mirror_query.set_payload(name, conn, catalog=catalog))
        written += _write_if_changed(PUBLISH_DIR / "sets" / f"{slug}.json",
                                     payload)
    print(f"sets/: {len(slug_map)} files staged ({written} changed)")
    return written


def stage_catalog_and_answerlines(conn, slug_map: dict[str, str]) -> dict:
    """Columnar catalog + aligned answerline arrays, one pass per table.

    Row order is deterministic: set-list order, then packet, number, id.
    Enum columns index into the header lists; -1 = no value.
    """
    set_names = mirror_query.set_list(conn=conn)
    set_meta = {r["name"]: r for r in conn.execute("SELECT * FROM sets")}
    packet_counts = dict(conn.execute(
        "SELECT set_name, COUNT(*) FROM packets GROUP BY set_name"))
    set_index = {name: i for i, name in enumerate(set_names)}

    # Overview-section lookup, rebuilt fresh each publish (no stale state):
    # newly synced sets and edited overviews are sectioned automatically.
    # The answerline KB is the enriched fallback for answerlines the
    # mechanical index can't place (and carries era/movement metadata).
    section_index = SectionIndex()
    kb = KBLookup()
    section_values: list[list[str]] = []   # [unit_slug, section_name] pairs
    section_ids: dict[tuple, int] = {}

    def section_id(category, subcategory, alt, answer):
        hit = section_index.section_for(category, subcategory, alt, answer)
        if hit is None and kb:
            rec = kb.record(category, subcategory, alt, answer)
            if rec:
                u = unit_for_guide(category or '', subcategory or '', alt or '')
                if u and rec.get('section'):
                    hit = (u.slug, rec['section'])
                elif u and rec.get('type') == 'common-link':
                    # thematic "what is depicted / what concept" answers have
                    # no era/school home — give them a practice group of their
                    # own rather than leaving them Unsectioned.
                    hit = (u.slug, 'Common Links & Themes')
        if hit is None:
            return -1
        idx = section_ids.get(hit)
        if idx is None:
            idx = len(section_values)
            section_values.append([hit[0], hit[1]])
            section_ids[hit] = idx
        return idx

    # Deduped normalized answerlines, int-encoded per tossup row. Powers the
    # reader's spaced-repetition drill (per-answerline mastery state) without
    # shipping the full row-aligned answer strings.
    answerline_values: list[str] = []
    answerline_ids: dict[str, int] = {}

    def answerline_id(raw_answer: str, sanitized_answer: str) -> int:
        key = answer_key(raw_answer, sanitized_answer)
        if not key:
            return -1
        idx = answerline_ids.get(key)
        if idx is None:
            idx = len(answerline_values)
            answerline_values.append(key)
            answerline_ids[key] = idx
        return idx

    enums: dict[str, list] = {"category": [], "subcategory": [],
                              "alternate_subcategory": []}
    enum_index: dict[str, dict] = {k: {} for k in enums}

    def enum_id(col, value):
        if value is None:
            return -1
        idx = enum_index[col].get(value)
        if idx is None:
            idx = len(enums[col])
            enums[col].append(value)
            enum_index[col][value] = idx
        return idx

    catalog = {
        "version": 1,
        "sets": [
            {"slug": slug_map[n], "name": n,
             "year": set_meta[n]["year"],
             "difficulty": set_meta[n]["difficulty"],
             "standard": bool(set_meta[n]["standard"]),
             "packets": packet_counts.get(n, 0)}
            for n in set_names
        ],
    }
    answerlines = {"version": 1}

    counts = {}
    for table in ("tossups", "bonuses"):
        cols = {k: [] for k in ("id", "set", "packet", "number", "category",
                                "subcategory", "alternate_subcategory",
                                "difficulty", "section", "answerline")}
        answers = []
        # sanitized text for the aligned answerlines array (client display);
        # the raw (marked-up) answer feeds the section join, which reads the
        # bold-underline core.
        san_col = "answer_sanitized" if table == "tossups" else "answers_sanitized"
        raw_col = "answer" if table == "tossups" else "answers"
        rows = conn.execute(
            f"SELECT id, set_name, packet_number, number, category, "
            f"subcategory, alternate_subcategory, difficulty, "
            f"{san_col} AS ans_san, {raw_col} AS ans_raw "
            f"FROM {table}").fetchall()
        rows.sort(key=lambda r: (set_index.get(r["set_name"], 1 << 30),
                                 r["packet_number"] or 0, r["number"] or 0,
                                 r["id"]))
        for r in rows:
            cols["id"].append(r["id"])
            cols["set"].append(set_index.get(r["set_name"], -1))
            cols["packet"].append(r["packet_number"])
            cols["number"].append(r["number"])
            cols["category"].append(enum_id("category", r["category"]))
            cols["subcategory"].append(enum_id("subcategory", r["subcategory"]))
            cols["alternate_subcategory"].append(
                enum_id("alternate_subcategory", r["alternate_subcategory"]))
            cols["difficulty"].append(r["difficulty"])
            if table == "tossups":
                answers.append(r["ans_san"] or "")
                # section join reads the raw (marked-up) answer
                cols["section"].append(section_id(
                    r["category"], r["subcategory"],
                    r["alternate_subcategory"], r["ans_raw"] or ""))
                # drill key = bold-underline core of the raw answer (matches
                # the reader's LOG entries via the shared answerKey logic)
                cols["answerline"].append(
                    answerline_id(r["ans_raw"] or "", r["ans_san"] or ""))
            else:
                answers.append(json.loads(r["ans_san"] or "[]"))
                raw_parts = json.loads(r["ans_raw"] or "[]")
                cols["section"].append([
                    section_id(r["category"], r["subcategory"],
                               r["alternate_subcategory"], p or "")
                    for p in raw_parts])
                cols["answerline"].append(-1)   # tossups-only; keep rectangular
        catalog[table] = cols
        answerlines[table] = answers
        counts[table] = len(rows)

    for col, values in enums.items():
        catalog[col + "_values"] = values
    catalog["section_values"] = section_values
    catalog["answerline_values"] = answerline_values

    for name, data in (("catalog.json", catalog),
                       ("answerlines.json", answerlines)):
        changed = _write_if_changed(PUBLISH_DIR / name, _dump(data))
        print(f"{name}: {counts['tossups']} tossups + {counts['bonuses']} "
              f"bonuses ({'changed' if changed else 'unchanged'})")
    return counts


def _docs_by_id(conn, catalog, ids: set[str]) -> dict[str, dict]:
    """Batch-resolve qbreader ids to API-shaped docs (tagged with 'type').
    Ids absent from the mirror are simply missing from the result — the
    callers treat that as a fatal dangling ref."""
    docs = {}
    id_list = sorted(ids)
    for table, doc_for, qtype in (("tossups", mirror_query._tossup_doc, "tossup"),
                                  ("bonuses", mirror_query._bonus_doc, "bonus")):
        for i in range(0, len(id_list), 900):
            chunk = id_list[i:i + 900]
            marks = ",".join("?" * len(chunk))
            for row in conn.execute(
                    f"SELECT * FROM {table} WHERE id IN ({marks})", chunk):
                docs[row["id"]] = dict(doc_for(row, catalog), type=qtype)
    return docs


def stage_topic_questions(conn, catalog) -> int:
    """Per-topic resolved question files backing the runtime-fetch
    questions.html: ordered entries mirroring questions_ref.json, with
    the ids resolved to full docs. A ref id missing from the mirror
    aborts the publish (the DANGLING-ref check lives here now)."""
    refs_by_slug = {}
    all_ids = set()
    for ref_path in sorted(OUTPUT_DIR.glob("*/questions_ref.json")):
        entries = json.loads(ref_path.read_text(encoding="utf-8"))
        refs_by_slug[ref_path.parent.name] = entries
        for e in entries:
            all_ids.update(e.get("tossups", []))
            all_ids.update(e.get("bonuses", []))

    docs = _docs_by_id(conn, catalog, all_ids)
    dangling = [(slug, _id)
                for slug, entries in refs_by_slug.items()
                for e in entries
                for _id in e.get("tossups", []) + e.get("bonuses", [])
                if _id not in docs]
    if dangling:
        for slug, _id in dangling[:10]:
            print(f"DANGLING REF: {slug} -> {_id}", file=sys.stderr)
        raise SystemExit(
            f"{len(dangling)} question ref(s) missing from the mirror — "
            f"run lib/mirror/sync.py (or --refresh the edited set) first")

    written = 0
    for slug, entries in refs_by_slug.items():
        payload = _dump([
            {"query_string": e.get("query_string", ""),
             "mentions": bool(e.get("mentions")),
             "tossups": [docs[i] for i in e.get("tossups", [])],
             "bonuses": [docs[i] for i in e.get("bonuses", [])]}
            for e in entries
        ])
        written += _write_if_changed(
            PUBLISH_DIR / "topic_questions" / f"{slug}.json", payload)
    print(f"topic_questions/: {len(refs_by_slug)} files staged "
          f"({written} changed)")
    return len(refs_by_slug)


def stage_unit_questions(conn, catalog) -> int:
    """Per-unit resolved panels backing overview pages: the exact
    QUESTIONS_DATA shape build_overviews used to embed —
    {normalized answerline: [{type, text, set, diff}]} (sanitized text;
    bonus refs resolve leadin + the referenced part)."""
    units = {}
    all_ids = set()
    for q_path in sorted(CATEGORIES_DIR.glob("*/questions.json")):
        refs = json.loads(q_path.read_text(encoding="utf-8"))
        units[q_path.parent.name] = refs
        for ref_list in refs.values():
            all_ids.update(r["id"] for r in ref_list if r.get("id"))

    docs = _docs_by_id(conn, catalog, all_ids)

    written = 0
    for unit, refs in units.items():
        data, dangling = {}, []
        for answerline, ref_list in refs.items():
            resolved = []
            for ref in ref_list:
                doc = docs.get(ref.get("id") or "")
                if doc is None:
                    dangling.append(ref.get("id"))
                    continue
                if ref.get("part") is None:
                    qtype, text = "tossup", doc.get("question_sanitized", "")
                else:
                    parts = doc.get("parts_sanitized", [])
                    j = ref["part"]
                    part = parts[j] if j < len(parts) else ""
                    qtype = "bonus"
                    text = f"{doc.get('leadin_sanitized', '')} {part}".strip()
                if text:
                    resolved.append({"type": qtype, "text": text,
                                     "set": (doc.get("set") or {}).get("name", ""),
                                     "diff": doc.get("difficulty", "")})
            if resolved:
                data[answerline] = resolved
        if dangling:
            raise SystemExit(
                f"{len(dangling)} unit ref(s) in {unit} missing from the "
                f"mirror — run lib/mirror/sync.py first (e.g. {dangling[0]})")
        written += _write_if_changed(
            PUBLISH_DIR / "unit_questions" / f"{unit}.json", _dump(data))
    print(f"unit_questions/: {len(units)} files staged ({written} changed)")
    return len(units)


def stage_topics() -> int:
    """Our study-guide overlay: per topic slug, the metadata fields we
    author (analysis.json) plus the question ids backing its pages
    (questions_ref.json), mentions kept separate."""
    topics = {}
    for ref_path in sorted(OUTPUT_DIR.glob("*/questions_ref.json")):
        slug = ref_path.parent.name
        entry = {}
        analysis_path = ref_path.parent / "analysis.json"
        if analysis_path.exists():
            try:
                analysis = json.loads(analysis_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                analysis = {}
            for field in _TOPIC_FIELDS:
                value = analysis.get(field)
                if value not in (None, "", []):
                    entry["name" if field == "topic" else field] = value
            unit = unit_for_guide(analysis.get("category", ""),
                                  analysis.get("subcategory", ""),
                                  analysis.get("genre", ""))
            if unit:
                entry["unit"] = unit.slug

        related_path = ref_path.parent / "related.json"
        if related_path.exists():
            entry["related"] = json.loads(
                related_path.read_text(encoding="utf-8"))

        refs = json.loads(ref_path.read_text(encoding="utf-8"))
        for key, mentions in (("tossups", False), ("bonuses", False),
                              ("mention_tossups", True),
                              ("mention_bonuses", True)):
            qkey = key.replace("mention_", "")
            seen, ids = set(), []
            for ref in refs:
                if bool(ref.get("mentions")) != mentions:
                    continue
                for _id in ref.get(qkey, []):
                    if _id not in seen:
                        seen.add(_id)
                        ids.append(_id)
            if ids:
                entry[key] = ids
        topics[slug] = entry

    changed = _write_if_changed(PUBLISH_DIR / "topics.json",
                                _dump({"version": 1, "topics": topics}))
    print(f"topics.json: {len(topics)} topics "
          f"({'changed' if changed else 'unchanged'})")
    return len(topics)


def stage(conn) -> dict:
    catalog = mirror_query._Catalog(conn)
    slug_map = _unique_slugs(mirror_query.set_list(conn=conn))
    stage_sets(conn, catalog, slug_map)
    counts = stage_catalog_and_answerlines(conn, slug_map)
    n_topics = stage_topics()
    n_topic_q = stage_topic_questions(conn, catalog)
    n_unit_q = stage_unit_questions(conn, catalog)

    files = {}
    for path in sorted(PUBLISH_DIR.rglob("*.json")):
        rel = path.relative_to(PUBLISH_DIR).as_posix()
        if rel == "manifest.json":
            continue
        data = path.read_bytes()
        files[rel] = {"sha256": hashlib.sha256(data).hexdigest(),
                      "bytes": len(data)}
    expected = ({f"sets/{s}.json" for s in slug_map.values()}
                | {f"topic_questions/{p.parent.name}.json"
                   for p in OUTPUT_DIR.glob("*/questions_ref.json")}
                | {f"unit_questions/{p.parent.name}.json"
                   for p in CATEGORIES_DIR.glob("*/questions.json")}
                | {"catalog.json", "answerlines.json", "topics.json"})
    stale = set(files) - expected
    for rel in stale:
        (PUBLISH_DIR / rel).unlink()
        del files[rel]
        print(f"removed stale artifact {rel}")

    manifest = {
        "version": 1,
        "generated": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "counts": {"sets": len(slug_map), "topics": n_topics,
                   "topic_questions": n_topic_q, "unit_questions": n_unit_q,
                   **counts},
        "mirror": {"seeded_from_backup":
                   mirror_db.get_meta(conn, "seeded_from_backup"),
                   "last_sync": mirror_db.get_meta(conn, "last_sync")},
        "files": files,
    }
    _write_if_changed(PUBLISH_DIR / "manifest.json", _dump(manifest))
    total = sum(f["bytes"] for f in files.values())
    print(f"staged {len(files)} files, {total / 1e6:.0f} MB (pre-compression) "
          f"→ {PUBLISH_DIR}")
    return manifest


_NPX = shutil.which("npx") or "npx"


def _wrangler(args: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run([_NPX, "--yes", "wrangler", *args],
                          capture_output=True, text=True, shell=False,
                          encoding="utf-8", errors="replace")


def _remote_manifest(bucket: str) -> dict:
    tmp = PUBLISH_DIR / ".remote_manifest.json"
    proc = _wrangler(["r2", "object", "get", f"{bucket}/manifest.json",
                      "--file", str(tmp), "--remote"])
    if proc.returncode != 0:
        return {}
    try:
        return json.loads(tmp.read_text(encoding="utf-8"))
    finally:
        tmp.unlink(missing_ok=True)


def upload(manifest: dict, bucket: str, force_all: bool = False,
           workers: int = 6) -> None:
    remote = {} if force_all else _remote_manifest(bucket).get("files", {})
    todo = [rel for rel, info in manifest["files"].items()
            if remote.get(rel, {}).get("sha256") != info["sha256"]]
    if not todo and remote:
        print("remote is current — uploading manifest only")
    print(f"uploading {len(todo)} changed files + manifest to r2://{bucket}")

    failures = []
    gzip_dir = PUBLISH_DIR / ".gz"

    def put(rel: str):
        # Stored pre-gzipped with Content-Encoding metadata: r2.dev does
        # no edge compression, and browsers decompress transparently.
        gz_path = gzip_dir / rel
        gz_path.parent.mkdir(parents=True, exist_ok=True)
        gz_path.write_bytes(gzip.compress(
            (PUBLISH_DIR / rel).read_bytes(), 6, mtime=0))
        proc = _wrangler(["r2", "object", "put", f"{bucket}/{rel}",
                          "--file", str(gz_path),
                          "--content-type", "application/json",
                          "--content-encoding", "gzip",
                          "--cache-control", "public, max-age=300",
                          "--remote"])
        gz_path.unlink(missing_ok=True)
        if proc.returncode != 0:
            failures.append((rel, proc.stderr.strip()[-300:]))
        return rel

    with ThreadPoolExecutor(max_workers=workers) as pool:
        for i, rel in enumerate(pool.map(put, todo), 1):
            if i % 25 == 0 or i == len(todo):
                print(f"  {i}/{len(todo)} ({rel})")

    if failures:
        print(f"FAILED: {len(failures)} uploads — manifest NOT updated "
              f"(remote stays consistent); rerun --upload to retry")
        for rel, err in failures[:5]:
            print(f"  {rel}: {err}")
        raise SystemExit(1)

    put("manifest.json")
    if failures:
        print(f"FAILED to upload manifest: {failures[0][1]}")
        raise SystemExit(1)
    print("upload complete (manifest updated last)")


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--upload", action="store_true",
                        help="upload staged artifacts to R2 after staging")
    parser.add_argument("--all", action="store_true",
                        help="ignore the remote manifest; re-upload everything")
    parser.add_argument("--bucket", default=DEFAULT_BUCKET)
    parser.add_argument("--workers", type=int, default=6,
                        help="parallel wrangler uploads")
    args = parser.parse_args()

    conn = mirror_db.open_db()
    try:
        manifest = stage(conn)
    finally:
        conn.close()
    if args.upload:
        upload(manifest, args.bucket, force_all=args.all,
               workers=args.workers)


if __name__ == "__main__":
    main()
