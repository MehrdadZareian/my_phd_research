"""Minimise the number of cuts instead of offcut length (open-geometry ladder,
5-piece window, random order) -> results/cuts/.

A placement needs a cut when the piece is longer than its slot by more than
2 cm. Objectives compared on identical streams:
  offcut length: new timber (m) + 0.05 * offcut (m)       [as before]
  cuts, lambda:  new timber (m) + lambda * number of cuts  (lambda = 0.1, 0.3 m per cut)

Usage: python experiments/run_cuts.py [--quick]
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
from stream_sim.ladder import (LadderBufferedRule, LadderCatalogue,  # noqa: E402
                               LadderLookAhead, LadderSpec, ladder_offline,
                               run_ladder_episode)

B, BATCH = 4, 45  # 5-piece window
OBJECTIVES = {"offcut length": None, "cuts, 0.1 m per cut": 0.1, "cuts, 0.3 m per cut": 0.3}
_cats: dict = {}


def cat(obj):
    if obj not in _cats:
        _cats[obj] = LadderCatalogue(LadderSpec(), synthetic_inventory(400, best_fraction=0.15, seed=1),
                                     cut_cost=OBJECTIVES[obj])
    return _cats[obj]


def job(k):
    rows = []
    for obj in OBJECTIVES:
        c = cat(obj)
        rng = np.random.default_rng(95_000 + k)
        batch = sample_batch(len(c.problem.pieces), BATCH, rng)
        stream = rng.permutation(batch)
        res = [ladder_offline(c, batch),
               run_ladder_episode(c, stream, LadderBufferedRule(), B, seed=k),
               run_ladder_episode(c, stream, LadderLookAhead(16, 3), B, seed=k)]
        names = ["offline optimum", "window rule", "window look-ahead"]
        for n, r in zip(names, res):
            rows.append(dict(objective=obj, stream=k, policy=n, new_timber_m=r.new_timber_m,
                             cuts=r.cuts, waste_m=r.waste_m, panels=len(r.panels),
                             reclaimed_share=r.reclaimed_share))
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--quick", action="store_true")
    a = ap.parse_args()
    n = 2 if a.quick else 40
    out = ROOT / "results" / "cuts"
    out.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    with Pool(2) as pool:
        rows = [r for rs in pool.map(job, range(n), chunksize=1) for r in rs]
    with open(out / "runs.csv", "w", newline="") as f:
        wr = csv.DictWriter(f, fieldnames=list(rows[0]))
        wr.writeheader()
        wr.writerows(rows)
    print(f"{len(rows)} rows in {time.time() - t0:.0f} s")


if __name__ == "__main__":
    main()
