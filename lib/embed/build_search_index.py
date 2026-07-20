"""build_search_index.py — stage the online semantic-search index for R2.

Reads sentence + bonus-part vectors from mirror/embeddings.sqlite and
produces mirror/search_index/:
    centroids.f16        K x 1024 fp16 k-means centroids (spherical)
    bundle_{b:02d}.bin   partitions packed back-to-back; each row is
                         20B meta + 128B binary code (sign bits of the
                         1024-dim vector) + f16 scale + int8 rerank vec:
                           12B question id (Mongo hex -> bytes)
                            1B kind (0 tossup-sentence, 1 bonus part)
                            1B sent index (255 = bonus leadin)
                            2B set ordinal (into manifest set_slugs)
                            1B category ordinal (manifest categories)
                            1B subcategory ordinal (255 = none/unknown)
                            1B alternate-subcategory ordinal
                               (255 = null, 254 = off-taxonomy)
                            1B difficulty (255 = unknown)
    search_manifest.json {version, dims, k, rows, meta_bytes, parts:
                          [bundle, offset, length, count], set_slugs,
                          set_names, set_years, categories,
                          subcategories, alternate_subcategories}

The Worker (sync/worker.js /search) picks nprobe partitions by centroid
dot product, range-reads them from the bundles, scans Hamming distance,
and applies qbreader-/db-style filters against the per-row meta bytes.
Clients resolve ids to text via the published sets/{slug}.json shards —
set_slugs here uses the SAME slug derivation as publish.py, and the
taxonomy ordinal tables are lib/mirror/query.py's canonical lists (the
search page embeds the same lists, so ordinals agree end to end).

--eval measures recall of the quantized pipeline against exact float
search on sample queries before anything is uploaded. --upload pushes
the staged artifacts to R2 under search/ (bundles stay uncompressed —
the Worker range-reads them, which Content-Encoding would break).

Usage: python lib/embed/build_search_index.py [--eval-only] [--k 2048]
                                              [--upload] [--bucket B]
"""
import argparse
import json
import sqlite3
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from lib.common import MIRROR_DIR
from lib.embed.model import DIMS, MODEL_ID
from lib.embed.store import DB_PATH as STORE_PATH

OUT_DIR = MIRROR_DIR / "search_index"
QBREADER_DB = MIRROR_DIR / "qbreader.sqlite"
K_DEFAULT = 2048
NPROBE_EVAL = 24  # keep in lockstep with NPROBE in sync/worker.js
RERANK_TOP = 200      # Hamming candidates the int8 tier rescores
# Full-width rerank: the July 2026 variant eval showed Qwen3-0.6B's first
# 512 dims rank poorly (f32@512=0.71 vs f32@1024=0.88 recall@10) — the
# quality lives in the full vector, and int8 loses nothing (0.875).
RERANK_DIMS = DIMS
BUNDLES = 32
META_BYTES = 20
CODE_BYTES = DIMS // 8
# Row: meta + binary code + f16 scale + int8 rerank vector. The rerank
# tier rides in the partition row so the Worker reranks from bytes it has
# already fetched — a separate fetch round would blow the Workers free
# plan's 50-subrequest cap.
ROW_BYTES = META_BYTES + CODE_BYTES + 2 + RERANK_DIMS
KIND_SENTENCE, KIND_BONUS = 0, 1
LEADIN_SIDX = 255
ORD_NULL = 255       # taxonomy field absent (NULL/'' in the mirror)
ORD_OFF_TAXONOMY = 254  # value present but not in the canonical list


def _rerank_quantize(mat_f16, chunk=200_000):
    """(int8 matrix, f16 scales): first RERANK_DIMS dims, renormalized
    per vector, symmetric int8."""
    n = mat_f16.shape[0]
    q = np.empty((n, RERANK_DIMS), np.int8)
    scales = np.empty(n, np.float16)
    for lo in range(0, n, chunk):
        v = mat_f16[lo:lo + chunk, :RERANK_DIMS].astype(np.float32)
        v /= np.maximum(np.linalg.norm(v, axis=1, keepdims=True), 1e-9)
        s = np.maximum(np.abs(v).max(axis=1), 1e-9) / 127.0
        q[lo:lo + chunk] = np.round(v / s[:, None]).astype(np.int8)
        scales[lo:lo + chunk] = s.astype(np.float16)
    return q, scales


def _load_vectors():
    """(meta, fp16 matrix): meta rows are (id_hex, kind, sidx). Streams
    from the store without materializing an fp32 copy."""
    db = sqlite3.connect(STORE_PATH)
    n = db.execute(
        "select count(*) from embeddings where model=? and kind in ('sentence','bonus_part')",
        (MODEL_ID,)).fetchone()[0]
    mat = np.empty((n, DIMS), np.float16)
    meta = []
    cur = db.execute(
        "select kind, id, part, vector from embeddings "
        "where model=? and kind in ('sentence','bonus_part') order by kind, id, part",
        (MODEL_ID,))
    for i, (kind, id_, part, blob) in enumerate(cur):
        mat[i] = np.frombuffer(blob, np.float16)
        if kind == "sentence":
            meta.append((id_, KIND_SENTENCE, part))
        else:
            meta.append((id_, KIND_BONUS, LEADIN_SIDX if part < 0 else part))
    db.close()
    return meta, mat


def _taxonomy_ord(value, canonical_index):
    if not value:
        return ORD_NULL
    return canonical_index.get(value, ORD_OFF_TAXONOMY)


def _row_meta(meta):
    """Per-row filter metadata + the manifest lookup tables.

    Returns (set_rows u16, cat u8, sub u8, alt u8, diff u8, tables) where
    tables carries set_slugs/set_names/set_years and the canonical
    taxonomy lists (lib/mirror/query.py order — the ordinal contract
    shared with the Worker and the search page).
    """
    from qbmirror import db as mirror_db
    from qbmirror import query as mirror_query
    from lib.mirror.publish import _unique_slugs

    cat_idx = {c: i for i, c in enumerate(mirror_query.CATEGORIES)}
    sub_idx = {s: i for i, s in enumerate(mirror_query.SUBCATEGORIES)}
    alt_idx = {a: i for i, a in enumerate(mirror_query.ALTERNATE_SUBCATEGORIES)}

    qb = mirror_db.open_db()
    byid = {}
    for table in ("tossups", "bonuses"):
        for id_, sname, cat, sub, alt, diff in qb.execute(
                f"select id, set_name, category, subcategory, "
                f"alternate_subcategory, difficulty from {table}"):
            byid[id_] = (sname, cat, sub, alt, diff)
    set_names = mirror_query.set_list(conn=qb)
    set_years = {name: year for name, year in
                 qb.execute("select name, year from sets")}
    qb.close()

    slug_map = _unique_slugs(set_names)
    ordinals = {name: i for i, name in enumerate(set_names)}
    tables = {
        "set_slugs": [slug_map[name] for name in set_names],
        "set_names": set_names,
        "set_years": [set_years.get(name) or 0 for name in set_names],
        "categories": mirror_query.CATEGORIES,
        "subcategories": mirror_query.SUBCATEGORIES,
        "alternate_subcategories": mirror_query.ALTERNATE_SUBCATEGORIES,
    }

    n = len(meta)
    set_rows = np.full(n, 0xFFFF, np.uint16)
    cat = np.full(n, ORD_NULL, np.uint8)
    sub = np.full(n, ORD_NULL, np.uint8)
    alt = np.full(n, ORD_NULL, np.uint8)
    diff = np.full(n, ORD_NULL, np.uint8)
    for i, (id_, _k, _s) in enumerate(meta):
        row = byid.get(id_)
        if row is None:
            continue
        sname, c, s, a, d = row
        set_rows[i] = ordinals.get(sname, 0xFFFF)
        cat[i] = _taxonomy_ord(c, cat_idx)
        sub[i] = _taxonomy_ord(s, sub_idx)
        alt[i] = _taxonomy_ord(a, alt_idx)
        diff[i] = ORD_NULL if d is None else max(0, min(253, int(d)))
    return set_rows, cat, sub, alt, diff, tables


def _binarize(mat_f16, chunk=200_000):
    codes = np.empty((mat_f16.shape[0], CODE_BYTES), np.uint8)
    for lo in range(0, mat_f16.shape[0], chunk):
        codes[lo:lo + chunk] = np.packbits(
            (mat_f16[lo:lo + chunk] > 0), axis=1)
    return codes


def _train_assign(mat_f16, k, sample=250_000, chunk=100_000, seed=13):
    import faiss

    rng = np.random.default_rng(seed)
    idx = rng.choice(mat_f16.shape[0], min(sample, mat_f16.shape[0]),
                     replace=False)
    train = mat_f16[np.sort(idx)].astype(np.float32)
    km = faiss.Kmeans(DIMS, k, niter=15, seed=seed, spherical=True,
                      verbose=True)
    km.train(train)
    centroids = km.centroids.reshape(k, DIMS)
    centroids /= np.maximum(np.linalg.norm(centroids, axis=1, keepdims=True),
                            1e-9)
    assign = np.empty(mat_f16.shape[0], np.int32)
    for lo in range(0, mat_f16.shape[0], chunk):
        sims = mat_f16[lo:lo + chunk].astype(np.float32) @ centroids.T
        assign[lo:lo + chunk] = sims.argmax(axis=1)
    return centroids, assign


def _hamming_topk(qbits, codes, topk):
    dists = np.unpackbits(codes ^ qbits, axis=1).sum(axis=1)
    order = np.argsort(dists)[:topk]
    return order, dists[order]


def evaluate(mat_f16, codes, centroids, assign, rq=None, rscale=None,
             n_queries=100, topk=10, variants=False):
    """Decomposed recall of the quantized pipeline vs exact float search:
      ivf      — exact top-k found in the probed partitions at all (pruning
                 ceiling: no scan can beat this)
      ham@N    — exact top-k contained in the Hamming top-N of the probed
                 candidates (what a top-N rerank tier can recover)
      pipeline — the shipped path: Hamming top-RERANK_TOP, int8@RERANK_DIMS
                 rescore, take top-k
    """
    rng = np.random.default_rng(7)
    qidx = rng.choice(mat_f16.shape[0], n_queries, replace=False)
    rerank_ns = (topk, 50, 100, 200)
    hits = {"ivf": 0, **{f"ham@{n}": 0 for n in rerank_ns}}
    if rq is not None:
        hits["pipeline"] = 0
    if variants:
        hits.update({"f32@512": 0, "f32@1024": 0, "i8@1024": 0})
    for qi in qidx:
        q = mat_f16[qi].astype(np.float32)
        exact_sims = np.empty(mat_f16.shape[0], np.float32)
        chunk = 400_000
        for lo in range(0, mat_f16.shape[0], chunk):
            exact_sims[lo:lo + chunk] = mat_f16[lo:lo + chunk].astype(np.float32) @ q
        exact = set(np.argsort(-exact_sims)[1:topk + 1].tolist())  # skip self

        probes = np.argsort(-(centroids @ q))[:NPROBE_EVAL]
        cand = np.where(np.isin(assign, probes))[0]
        cand_set = set(cand.tolist())
        hits["ivf"] += len(exact & cand_set)
        qbits = np.packbits(q > 0)
        order, _ = _hamming_topk(qbits, codes[cand], max(rerank_ns) + 1)
        ranked = [c for c in cand[order].tolist() if c != int(qi)]
        for n in rerank_ns:
            hits[f"ham@{n}"] += len(exact & set(ranked[:n]))
        if rq is not None:
            pool = np.array(ranked[:RERANK_TOP], np.int64)
            qr = q[:RERANK_DIMS] / max(np.linalg.norm(q[:RERANK_DIMS]), 1e-9)
            scores = (rq[pool].astype(np.float32) @ qr) * rscale[pool].astype(np.float32)
            final = pool[np.argsort(-scores)[:topk]]
            hits["pipeline"] += len(exact & set(final.tolist()))
        if variants:
            pool = np.array(ranked[:RERANK_TOP], np.int64)
            pv = mat_f16[pool].astype(np.float32)
            for name, dims in (("f32@512", 512), ("f32@1024", DIMS)):
                sub = pv[:, :dims]
                sub = sub / np.maximum(np.linalg.norm(sub, axis=1, keepdims=True), 1e-9)
                qs = q[:dims] / max(np.linalg.norm(q[:dims]), 1e-9)
                final = pool[np.argsort(-(sub @ qs))[:topk]]
                hits[name] += len(exact & set(final.tolist()))
            # int8 at full dims
            sub = pv / np.maximum(np.linalg.norm(pv, axis=1, keepdims=True), 1e-9)
            s = np.maximum(np.abs(sub).max(axis=1), 1e-9) / 127.0
            qi8 = np.round(sub / s[:, None])
            final = pool[np.argsort(-((qi8 @ q) * s))[:topk]]
            hits["i8@1024"] += len(exact & set(final.tolist()))
    return {k: v / (n_queries * topk) for k, v in hits.items()}


def stage(meta, codes, centroids, assign, row_meta, k, rq, rscale):
    set_rows, cat, sub, alt, diff, tables = row_meta
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    centroids.astype(np.float16).tofile(OUT_DIR / "centroids.f16")

    order = np.argsort(assign, kind="stable")
    parts_meta = []
    bundle_paths = [OUT_DIR / f"bundle_{b:02d}.bin" for b in range(BUNDLES)]
    handles = [p.open("wb") for p in bundle_paths]
    offsets = [0] * BUNDLES
    pos = 0
    for p in range(k):
        rows = []
        while pos < len(order) and assign[order[pos]] == p:
            rows.append(order[pos])
            pos += 1
        b = p % BUNDLES
        buf = bytearray()
        for r in rows:
            id_hex, kind, sidx = meta[r]
            buf += bytes.fromhex(id_hex)[:12].ljust(12, b"\0")
            buf += bytes([kind, sidx])
            buf += int(set_rows[r]).to_bytes(2, "little")
            buf += bytes([cat[r], sub[r], alt[r], diff[r]])
            buf += codes[r].tobytes()
            buf += rscale[r].tobytes()
            buf += rq[r].tobytes()
        handles[b].write(buf)
        parts_meta.append([b, offsets[b], len(buf), len(rows)])
        offsets[b] += len(buf)
    for h in handles:
        h.close()

    manifest = {
        "version": 3, "model": MODEL_ID, "dims": DIMS, "k": k,
        "rows": len(meta), "row_bytes": ROW_BYTES,
        "meta_bytes": META_BYTES, "bundles": BUNDLES,
        "rerank_dims": RERANK_DIMS, "rerank_top": RERANK_TOP,
        "parts": parts_meta, **tables,
    }
    (OUT_DIR / "search_manifest.json").write_text(
        json.dumps(manifest, separators=(",", ":")), encoding="utf-8")
    total = sum(p.stat().st_size for p in bundle_paths)
    print(f"staged {len(meta)} rows, {k} parts, {BUNDLES} bundles "
          f"({total/1e6:.0f}MB) + centroids ({centroids.nbytes//2/1e6:.1f}MB) "
          f"-> {OUT_DIR}")


def upload(bucket: str) -> None:
    """Push the staged index to R2 under search/. Bundles upload raw
    (the Worker range-reads them); the manifest goes LAST so a reader
    that fetched the old manifest never sees mixed strides."""
    from lib.mirror.publish import _wrangler

    paths = sorted(OUT_DIR.glob("bundle_*.bin")) + [OUT_DIR / "centroids.f16"]
    manifest_path = OUT_DIR / "search_manifest.json"
    for path in paths + [manifest_path]:
        if not path.exists():
            raise SystemExit(f"missing staged artifact: {path} — run stage first")
    for i, path in enumerate(paths, 1):
        proc = _wrangler(["r2", "object", "put", f"{bucket}/search/{path.name}",
                          "--file", str(path),
                          "--content-type", "application/octet-stream",
                          "--cache-control", "public, max-age=300",
                          "--remote"])
        if proc.returncode != 0:
            raise SystemExit(f"upload failed for {path.name}: "
                             f"{proc.stderr.strip()[-300:]}")
        print(f"  {i}/{len(paths)} {path.name}")
    proc = _wrangler(["r2", "object", "put",
                      f"{bucket}/search/search_manifest.json",
                      "--file", str(manifest_path),
                      "--content-type", "application/json",
                      "--cache-control", "public, max-age=300",
                      "--remote"])
    if proc.returncode != 0:
        raise SystemExit(f"manifest upload failed: {proc.stderr.strip()[-300:]}")
    print("upload complete (manifest updated last)")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--k", type=int, default=K_DEFAULT)
    ap.add_argument("--eval-only", action="store_true")
    ap.add_argument("--variants", action="store_true",
                    help="also eval rerank alternatives (f32/512-dim/1024-dim)")
    ap.add_argument("--upload", action="store_true",
                    help="push the staged index to R2 under search/")
    ap.add_argument("--upload-only", action="store_true",
                    help="upload what's already staged, no rebuild")
    ap.add_argument("--bucket", default=None,
                    help="R2 bucket (default: lib/mirror/publish.py's)")
    args = ap.parse_args()

    if args.upload or args.upload_only:
        from lib.mirror.publish import DEFAULT_BUCKET
        bucket = args.bucket or DEFAULT_BUCKET
    if args.upload_only:
        upload(bucket)
        return

    t0 = time.time()
    meta, mat = _load_vectors()
    print(f"loaded {len(meta)} vectors in {time.time()-t0:.0f}s")

    centroids, assign = _train_assign(mat, args.k)
    codes = _binarize(mat)
    rq, rscale = _rerank_quantize(mat)

    recall = evaluate(mat, codes, centroids, assign, rq, rscale,
                      variants=args.variants)
    print(f"recall@10 vs exact (nprobe={NPROBE_EVAL}): "
          + "  ".join(f"{k}={v:.3f}" for k, v in recall.items()))
    if args.eval_only:
        return

    stage(meta, codes, centroids, assign, _row_meta(meta), args.k,
          rq, rscale)
    if args.upload:
        upload(bucket)


if __name__ == "__main__":
    main()
