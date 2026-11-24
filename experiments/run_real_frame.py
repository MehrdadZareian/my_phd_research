"""2 x 2 m panel on the REAL MZ/WI inventory (data/mz_wi_inventory.json)
-> results/real_frame/.

Panel: 4 x 4 grid of 0.5 m cells, one diagonal each (25 nodes, 56 members),
pinned at the two bottom corners, 6 kN on each top node, 2 kN horizontal on
each left-edge node (placeholders). All 80 boards arrive in random order
(one stream = one shuffle of the whole inventory), 5-piece window.
Node freedom (box): 0 (fixed design), +-5, +-10, +-15 cm, on a 2.5 cm grid.
The inventory has no quality grades: all boards are taken as "standard".

Strategies: window rule; look-ahead with supply = inventory statistics
(knows the length distribution of the 80 boards, not the order);
look-ahead with learned supply (only boards seen so far); offline plan
(exact for the fixed design, heuristic local search for floating nodes).

Usage: python experiments/run_real_frame.py [--quick] [--streams N]
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

from stream_sim import load_inventory_json  # noqa: E402
from stream_sim.frame import (FrameLookAhead, FrameModel, FrameWindowRule,  # noqa: E402
                              frame_offline, run_frame_episode)

B = 4
BOXES = (0.0, 0.05, 0.10, 0.15)
KW = dict(n=4, cell=0.5, step=0.025, top_load=6.0, side_load=2.0, n_samples=300)
_m: dict = {}


def model(box):
    if box not in _m:
        inv = load_inventory_json(ROOT / "data" / "mz_wi_inventory.json")
        _m[box] = FrameModel(inv, box > 0, box=box, **KW)
    return _m[box]


def job(box, k):
    fm = model(box)
    rng = np.random.default_rng(200_000 + k)
    stream = rng.permutation(len(fm.pieces))   # same order for every box
    res = [frame_offline(fm, stream, seed=k),
           run_frame_episode(fm, stream, FrameWindowRule(), B, seed=k),
           run_frame_episode(fm, stream, FrameLookAhead(6, 2, 30), B, seed=k),
           run_frame_episode(fm, stream, FrameLookAhead(6, 2, 30, supply="observed"), B, seed=k)]
    return [dict(box_m=box, stream=k, policy=r.policy, new_timber_m=r.new_timber_m,
                 reclaimed_share=r.reclaimed_share, waste_m=r.waste_m, cuts=r.cuts,
                 violations=r.violations, max_node_shift_m=r.max_node_shift_m) for r in res]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--quick", action="store_true")
    ap.add_argument("--streams", type=int, default=20)
    a = ap.parse_args()
    n = 2 if a.quick else a.streams
    out = ROOT / "results" / "real_frame"
    out.mkdir(parents=True, exist_ok=True)
    jobs = [(b, k) for b in BOXES for k in range(n)]
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
