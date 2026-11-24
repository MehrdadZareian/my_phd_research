"""4 x 4 m panel: fixed node positions vs floating nodes -> results/frame/.

5-piece window, random order. Two supply levels: 84 pieces (1.5 x members,
scarce) and 140 pieces (2.5 x members, ample).

Usage: python experiments/run_frame.py [--quick]
"""

from __future__ import annotations

import argparse
import csv
import sys
import time
from multiprocessing import Pool
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from stream_sim import sample_batch, synthetic_inventory  # noqa: E402
from stream_sim.frame import (FrameLookAhead, FrameModel, FrameWindowRule,  # noqa: E402
                              frame_offline, run_frame_episode)

B = 4
_m = {}


def models():
    if not _m:
        inv = synthetic_inventory(400, best_fraction=0.15, seed=1)
        _m["fixed nodes"] = FrameModel(inv, False)
        _m["floating nodes"] = FrameModel(inv, True)
    return _m


def job(size, k):
    ms = models()
    rng = np.random.default_rng(100_000 + 1000 * size + k)
    batch = sample_batch(400, size, rng)
    stream = rng.permutation(batch)
    rows = []
    for design, fm in ms.items():
        res = [frame_offline(fm, batch, seed=k),
               run_frame_episode(fm, stream, FrameWindowRule(), B, seed=k),
               run_frame_episode(fm, stream, FrameLookAhead(6, 2, 30), B, seed=k)]
        for r in res:
            rows.append(dict(batch_size=size, stream=k, design=design, policy=r.policy,
                             new_timber_m=r.new_timber_m, reclaimed_share=r.reclaimed_share,
                             waste_m=r.waste_m, cuts=r.cuts, violations=r.violations,
                             max_node_shift_m=r.max_node_shift_m))
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--quick", action="store_true")
    a = ap.parse_args()
    n = 2 if a.quick else 30
    jobs = [(s, k) for s in (84, 140) for k in range(n)]
    out = ROOT / "results" / "frame"
    out.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    with Pool(2) as pool:
        rows = [r for rs in pool.starmap(job, jobs, chunksize=1) for r in rs]
    with open(out / "runs.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    print(f"{len(rows)} rows in {time.time() - t0:.0f} s")


if __name__ == "__main__":
    main()
