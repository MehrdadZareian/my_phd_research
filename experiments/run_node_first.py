"""Node-first (decide node positions from the whole 5-board window) vs the
current one-board-per-node rule, on the real MZ/WI inventory, 2 x 2 m panel.
Objective: number of cuts, where every new-timber member counts as one cut.
-> results/node_first/

Usage: python experiments/run_node_first.py [--streams N]
"""
from __future__ import annotations

import argparse
import csv
import sys
from multiprocessing import Pool
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "experiments"))
from run_real_frame import model  # noqa: E402
from stream_sim.frame import FrameNodeFirst, FrameWindowRule, frame_offline, run_frame_episode  # noqa: E402

BOXES = (0.05, 0.10, 0.15)


def job(box, k):
    fm = model(box)
    fm.objective = "cuts"
    stream = np.random.default_rng(200_000 + k).permutation(len(fm.pieces))
    res = [run_frame_episode(fm, stream, FrameWindowRule(), 4, seed=k),
           run_frame_episode(fm, stream, FrameNodeFirst(), 4, seed=k),
           frame_offline(fm, stream, iters=3000, seed=k)]
    return [dict(box_m=box, stream=k, policy=r.policy, reclaimed_share=r.reclaimed_share,
                 reclaimed_cuts=r.cuts, new_members=r.new_members, total_cuts=r.cuts + r.new_members,
                 new_timber_m=r.new_timber_m, waste_m=r.waste_m, violations=r.violations) for r in res]


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--streams", type=int, default=40)
    a = ap.parse_args()
    out = ROOT / "results" / "node_first"
    out.mkdir(parents=True, exist_ok=True)
    with Pool(2) as pool:
        rows = [r for rs in pool.starmap(job, [(b, k) for b in BOXES for k in range(a.streams)]) for r in rs]
    with open(out / "runs.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    print(len(rows), "rows")
