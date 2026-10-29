"""Step 2: exact all-pairs nearest neighbours over every clue unit (GPU).

For each unit keeps the top-K most similar OTHER units with cosine >=
FLOOR (the high-recall candidate set; same-fact precision comes later).
Exact: blocked fp16 matmul over the full 1024-dim vectors, no ANN.

Writes out/nbr_idx.npy (int32, -1 = empty slot) and out/nbr_cos.npy
(fp16), both N x K, sorted by descending cosine.

Usage: python dev/binary/sweep.py [--k 64] [--floor 0.70] [--queries N]
       (--queries N: only rows 0..N-1 search; the rest are search targets
       only, e.g. the clause universe's non-scope sentences)
"""
import argparse
import time

import numpy as np
import torch

from common import OUT

QB, KB = 8192, 32768


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--k", type=int, default=64)
    ap.add_argument("--floor", type=float, default=0.70)
    ap.add_argument("--queries", type=int, default=0, help="search only rows 0..N-1")
    args = ap.parse_args()
    K = args.k

    V = torch.from_numpy(np.load(OUT / "vecs.npy")).cuda()
    n = V.shape[0]
    idx_out = np.lib.format.open_memmap(OUT / "nbr_idx.npy", mode="w+", dtype=np.int32, shape=(n, K))
    cos_out = np.lib.format.open_memmap(OUT / "nbr_cos.npy", mode="w+", dtype=np.float16, shape=(n, K))
    t0 = time.time()
    with torch.no_grad():
        nq = args.queries or n
        idx_out[nq:] = -1
        cos_out[nq:] = 0
        for qs in range(0, nq, QB):
            qe = min(qs + QB, nq)
            Q = V[qs:qe]
            best_v = torch.full((qe - qs, K), -2.0, device="cuda", dtype=torch.float16)
            best_i = torch.full((qe - qs, K), -1, device="cuda", dtype=torch.int64)
            for ks in range(0, n, KB):
                ke = min(ks + KB, n)
                S = Q @ V[ks:ke].T
                if ks < qe and qs < ke:              # mask self-similarity
                    r = torch.arange(max(qs, ks), min(qe, ke), device="cuda")
                    S[r - qs, r - ks] = -2.0
                tv, ti = torch.topk(S, K, dim=1)
                cv = torch.cat([best_v, tv], 1)
                ci = torch.cat([best_i, ti + ks], 1)
                best_v, sel = torch.topk(cv, K, dim=1)
                best_i = torch.gather(ci, 1, sel)
            best_i[best_v < args.floor] = -1
            idx_out[qs:qe] = best_i.int().cpu().numpy()
            cos_out[qs:qe] = best_v.cpu().numpy()
            if (qs // QB) % 20 == 0:
                done = qe / nq
                el = time.time() - t0
                print(f"{qe}/{n} {el / 60:.1f} min, eta {el / done * (1 - done) / 60:.1f} min", flush=True)
    idx_out.flush(); cos_out.flush()
    filled = (np.load(OUT / "nbr_idx.npy", mmap_mode="r") >= 0).sum(1)
    print(f"done in {(time.time() - t0) / 60:.1f} min; neighbours >= {args.floor}: "
          f"mean {filled.mean():.1f}, median {np.median(filled):.0f}, "
          f"saturated (=K) {np.mean(filled == K):.1%}, none {np.mean(filled == 0):.1%}")


if __name__ == "__main__":
    main()
