"""Step 3b: calibration set for the same-fact decision.

`sample` draws candidate pairs (unit, one of its sweep neighbours from a
different question), computes (cos, anchor frac), and stratifies them
over cos bands x frac bands so precision can be measured per region —
not just on average. Writes out/calib_pairs.json and batch files
out/calib_batch_{i}.json for labelling (pairs only: id, answers, texts).

Labels go to out/calib_labels_{i}.json as [{"id": .., "label":
"same"|"different"}]. `report` joins them and prints per-cell precision
plus the candidate decision rules.

Usage: python dev/binary/calib.py sample [--per-cell 30] [--batches 6]
       python dev/binary/calib.py report
       python dev/binary/calib.py sample-low     # below-floor probe
"""
import argparse
import json
import random
import sys

import numpy as np

from anchors import Anchors
from common import OUT, load

COS_BANDS = [0.70, 0.75, 0.80, 0.85, 0.90, 1.01]
FRAC_BANDS = [0.0, 0.15, 0.35, 0.60, 1.01]


def _band(x, edges):
    return int(np.searchsorted(edges, x, side="right") - 1)


def sample(per_cell, batches, seed=7):
    rng = np.random.default_rng(seed)
    U = load("units.pkl")
    L = load("labels.pkl")
    idx = np.load(OUT / "nbr_idx.npy", mmap_mode="r")
    cos = np.load(OUT / "nbr_cos.npy", mmap_mode="r")
    n, K = idx.shape
    # 400k random (u, slot) draws -> plenty per cell
    us = rng.integers(0, n, 400_000)
    slots = rng.integers(0, K, 400_000)
    vs = idx[us, slots]
    cs = cos[us, slots].astype(np.float32)
    ok = vs >= 0
    us, vs, cs = us[ok], vs[ok], cs[ok]
    qid = U["qid"]
    diffq = np.array([qid[a] != qid[b] for a, b in zip(us, vs)])
    us, vs, cs = us[diffq], vs[diffq], cs[diffq]
    A = Anchors()
    _, frac = A.pair(us, vs)
    cells = {}
    for i in range(len(us)):
        key = (_band(cs[i], COS_BANDS), _band(frac[i], FRAC_BANDS))
        cells.setdefault(key, []).append(i)
    picked = []
    for key, members in sorted(cells.items()):
        random.Random(seed).shuffle(members)
        picked.extend(members[:per_cell])
    lab = L["unit_label"]
    pairs = []
    for j, i in enumerate(picked):
        u, v = int(us[i]), int(vs[i])
        pairs.append(dict(id=j, u=u, v=v, cos=round(float(cs[i]), 4), frac=round(float(frac[i]), 4),
                          same_label=bool(lab[u] == lab[v]),
                          ans_u=U["answer"][u][:120], ans_v=U["answer"][v][:120],
                          text_u=U["text"][u], text_v=U["text"][v],
                          shared=A.shared_terms(u, v)[:8]))
    json.dump(pairs, open(OUT / "calib_pairs.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    order = list(range(len(pairs)))
    random.Random(seed + 1).shuffle(order)          # labellers see no band order
    for b in range(batches):
        chunk = [{k: pairs[i][k] for k in ("id", "ans_u", "text_u", "ans_v", "text_v")}
                 for i in order[b::batches]]
        json.dump(chunk, open(OUT / f"calib_batch_{b}.json", "w", encoding="utf-8"),
                  ensure_ascii=False, indent=1)
    print(f"{len(pairs)} pairs in {len(cells)} cells -> {batches} batches")
    for key in sorted(cells):
        print(f"  cos[{COS_BANDS[key[0]]:.2f}) frac[{FRAC_BANDS[key[1]]:.2f}): {len(cells[key])} available")


def report():
    pairs = {p["id"]: p for p in json.load(open(OUT / "calib_pairs.json", encoding="utf-8"))}
    labels = {}
    for f in sorted(OUT.glob("calib_labels_*.json")):
        for r in json.load(open(f, encoding="utf-8")):
            labels[r["id"]] = r["label"]
    rows = [(p, labels[i] == "same") for i, p in pairs.items() if i in labels]
    print(f"{len(rows)} labelled of {len(pairs)}")
    print("P(same fact) by cell  (rows: cos band, cols: anchor frac band)")
    print("            " + "".join(f"frac>={b:<6.2f}" for b in FRAC_BANDS[:-1]))
    for ci in range(len(COS_BANDS) - 1):
        line = f"cos>={COS_BANDS[ci]:.2f}  "
        for fi in range(len(FRAC_BANDS) - 1):
            cell = [y for p, y in rows if _band(p["cos"], COS_BANDS) == ci
                    and _band(p["frac"], FRAC_BANDS) == fi]
            line += f"{sum(cell) / len(cell):.2f} n={len(cell):<3} " if cell else " --         "
        print(line)
    same_lab = [y for p, y in rows if p["same_label"]]
    diff_lab = [y for p, y in rows if not p["same_label"]]
    print(f"same-fact rate when answers equal: {np.mean(same_lab):.2f} (n={len(same_lab)}); "
          f"when answers differ: {np.mean(diff_lab):.2f} (n={len(diff_lab)})")
    # Candidate rules: same := cos >= c AND frac >= f. Precision/recall on
    # the stratified sample (recall is relative to labelled-same pairs).
    pos = sum(y for _, y in rows)
    print("rule (cos>=c and frac>=f): precision / recall-in-sample")
    for c in (0.70, 0.75, 0.78, 0.80, 0.85):
        line = f"  c={c:.2f}: "
        for f in (0.0, 0.15, 0.25, 0.35, 0.5):
            sel = [y for p, y in rows if p["cos"] >= c and p["frac"] >= f]
            if sel:
                line += f"f>={f:.2f} {np.mean(sel):.2f}/{sum(sel) / max(pos, 1):.2f}  "
        print(line)


if __name__ == "__main__" and sys.argv[1:2] != ["sample-low"]:
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["sample", "report"])
    ap.add_argument("--per-cell", type=int, default=30)
    ap.add_argument("--batches", type=int, default=6)
    a = ap.parse_args()
    sample(a.per_cell, a.batches) if a.cmd == "sample" else report()


def sample_low(n_units=3000, per_cell=15, seed=11):
    """Below-floor probe: how much same-fact mass sits under the sweep's
    0.70 floor (invisible to the binary test)? Exact sims for a random
    unit sample, pairs in [0.55, 0.70), stratified by cos x frac.
    Also prints the population rate of each band per unit, so labelled
    precision can be turned into expected missed same-fact pairs."""
    import torch
    rng = np.random.default_rng(seed)
    U = load("units.pkl")
    V = torch.from_numpy(np.load(OUT / "vecs.npy")).cuda()
    n = V.shape[0]
    us_pick = rng.choice(n, n_units, replace=False)
    qid = U["qid"]
    us, vs, cs = [], [], []
    for s in range(0, n_units, 256):
        q = torch.from_numpy(us_pick[s:s + 256]).cuda()
        S = V[q] @ V.T
        m = (S >= 0.55) & (S < 0.70)
        r, c = m.nonzero(as_tuple=True)
        us.append(q[r].cpu().numpy()); vs.append(c.cpu().numpy()); cs.append(S[r, c].float().cpu().numpy())
    us, vs, cs = np.concatenate(us), np.concatenate(vs), np.concatenate(cs)
    keep = np.array([qid[a] != qid[b] for a, b in zip(us, vs)])
    us, vs, cs = us[keep], vs[keep], cs[keep]
    A = Anchors()
    _, frac = A.pair(us, vs)
    low_cos = [0.55, 0.60, 0.65, 0.70]
    cells = {}
    for i in range(len(us)):
        cells.setdefault((_band(cs[i], low_cos), _band(frac[i], FRAC_BANDS)), []).append(i)
    print("pairs per unit by cell (population):")
    for key in sorted(cells):
        print(f"  cos[{low_cos[key[0]]:.2f}) frac[{FRAC_BANDS[key[1]]:.2f}): {len(cells[key]) / n_units:.2f}")
    picked = []
    for key, members in sorted(cells.items()):
        if key[1] == 0:          # frac < 0.15: already ~10% same at 0.70+, skip
            continue
        random.Random(seed).shuffle(members)
        picked.extend(members[:per_cell])
    pairs = [dict(id=10000 + j, u=int(us[i]), v=int(vs[i]), cos=round(float(cs[i]), 4),
                  frac=round(float(frac[i]), 4), rate=len(cells[(_band(cs[i], low_cos), _band(frac[i], FRAC_BANDS))]) / n_units,
                  ans_u=U["answer"][us[i]][:120], ans_v=U["answer"][vs[i]][:120],
                  text_u=U["text"][us[i]], text_v=U["text"][vs[i]]) for j, i in enumerate(picked)]
    json.dump(pairs, open(OUT / "calib_low_pairs.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    order = list(range(len(pairs)))
    random.Random(seed).shuffle(order)
    for b in range(2):
        json.dump([{k: pairs[i][k] for k in ("id", "ans_u", "text_u", "ans_v", "text_v")} for i in order[b::2]],
                  open(OUT / f"calib_low_batch_{b}.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"{len(pairs)} low-band pairs -> 2 batches")


if __name__ == "__main__" and len(sys.argv) > 1 and sys.argv[1] == "sample-low":
    sample_low()
