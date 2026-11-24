"""Window protocol: the workshop holds exactly 5 pieces.

The first 5 pieces fill the window before any decision. At every step one of
the 5 must be used (placed, or used to open the next panel) or discarded,
and the next piece of the stream takes its place. In the simulator this is
a buffer of 4: after each arrival 5 pieces are in hand and one must leave.
When the stream runs out, the last pieces in the window are assigned
optimally (same for every strategy).

Strategies (all under the same window):
  window rule       tightest fit among the 5 pieces
  window look-ahead rollout look-ahead, supply from source statistics
  clairvoyant       look-ahead that sees the actual rest of the stream
                    (approximate reference for "perfect knowledge, same window")
  offline optimum   all pieces at once, unlimited storage (loose bound)

Usage: python experiments/run_window.py [--quick]
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

from stream_sim import batch_order, sample_batch, synthetic_inventory  # noqa: E402
from stream_sim.ladder import (LadderBufferedRule, LadderCatalogue,  # noqa: E402
                               LadderLookAhead, LadderSpec, ladder_offline,
                               run_ladder_episode)

WINDOW = 5
B = WINDOW - 1
BATCH = 45
_cat = None


def cat():
    global _cat
    if _cat is None:
        _cat = LadderCatalogue(LadderSpec(), synthetic_inventory(400, best_fraction=0.15, seed=1))
    return _cat


class Clairvoyant(LadderLookAhead):
    def __init__(self, stream):
        super().__init__(1, 3, name="clairvoyant (same window)")
        self.stream = [int(s) for s in stream]

    def _scenario(self, n):
        return np.array(self.stream[len(self.stream) - n:], dtype=int)


def job(world, k):
    c = cat()
    pcs = c.problem.pieces
    rng = np.random.default_rng({"random": 80_000, "batch": 85_000, "misleading": 90_000}[world] + k)
    if world == "misleading":
        w = np.array([1.0 / p.length ** 3 for p in pcs])
        batch = rng.choice(len(pcs), BATCH, replace=False, p=w / w.sum())
        stream = rng.permutation(batch)
    else:
        batch = sample_batch(len(pcs), BATCH, rng)
        stream = rng.permutation(batch) if world == "random" else batch_order(batch, pcs, rng)
    pols = [("window rule", LadderBufferedRule()), ("window look-ahead", LadderLookAhead(16, 3)),
            ("clairvoyant (same window)", Clairvoyant(stream))]
    rows = [("offline optimum", ladder_offline(c, batch))]
    rows += [(n, run_ladder_episode(c, stream, p, B, seed=k)) for n, p in pols]
    return [dict(world=world, stream=k, policy=n, new_timber_m=r.new_timber_m,
                 reclaimed_share=r.reclaimed_share, waste_m=r.waste_m) for n, r in rows]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--quick", action="store_true")
    a = ap.parse_args()
    n = 2 if a.quick else 60
    jobs = [(w, k) for w in ("random", "batch", "misleading") for k in range(n)]
    out = ROOT / "results" / "window"
    out.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    with Pool(2) as pool:
        rows = [r for rs in pool.starmap(job, jobs, chunksize=1) for r in rs]
    with open(out / "runs.csv", "w", newline="") as f:
        wr = csv.DictWriter(f, fieldnames=list(rows[0]))
        wr.writeheader()
        wr.writerows(rows)
    print(f"{len(rows)} rows in {time.time() - t0:.0f} s")


if __name__ == "__main__":
    main()
