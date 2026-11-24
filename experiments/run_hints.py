"""Human supply hints for the open-geometry ladder -> results/hints/.

A hint is a coarse statement a person could make: "about h of the coming
pieces are shorter than 1 m". Look-ahead uses it as its supply prior,
optionally revising it from the pieces that actually arrive.

World A, misleading supply: the batch is biased towards short pieces
  (true expected short share 0.85; the source statistics say 0.34).
World B, normal supply: random batch (true short share 0.34). Tests what a
  wrong "mostly short" hint costs when nothing unusual is happening.

Usage: python experiments/run_hints.py [--quick]
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

B, BATCH = 3, 45
_cat = None


def cat():
    global _cat
    if _cat is None:
        _cat = LadderCatalogue(LadderSpec(), synthetic_inventory(400, best_fraction=0.15, seed=1))
    return _cat


def LA(**kw):
    return LadderLookAhead(16, 3, **kw)


POLICIES_A = [
    ("buffered rule", lambda: LadderBufferedRule()),
    ("look-ahead, no hint", lambda: LA()),
    ("look-ahead, learned supply", lambda: LA(supply="observed")),
    ("hint correct (85 % short)", lambda: LA(supply="hint", hint_short_share=0.85)),
    ("hint vague ('mostly short', 70 %)", lambda: LA(supply="hint", hint_short_share=0.70)),
    ("hint exaggerated (95 % short)", lambda: LA(supply="hint", hint_short_share=0.95)),
    ("hint wrong ('mostly long', 20 %)", lambda: LA(supply="hint", hint_short_share=0.20)),
    ("hint vague + update", lambda: LA(supply="hint", hint_short_share=0.70, hint_update=True)),
    ("hint wrong + update", lambda: LA(supply="hint", hint_short_share=0.20, hint_update=True)),
]
POLICIES_B = [
    ("buffered rule", lambda: LadderBufferedRule()),
    ("look-ahead, no hint", lambda: LA()),
    ("hint wrong ('mostly short', 80 %)", lambda: LA(supply="hint", hint_short_share=0.80)),
    ("hint wrong + update", lambda: LA(supply="hint", hint_short_share=0.80, hint_update=True)),
]


def job(world, k):
    c = cat()
    pcs = c.problem.pieces
    rng = np.random.default_rng((60_000 if world == "A" else 70_000) + k)
    if world == "A":
        w = np.array([1.0 / p.length ** 3 for p in pcs])
        batch = rng.choice(len(pcs), BATCH, replace=False, p=w / w.sum())
    else:
        batch = sample_batch(len(pcs), BATCH, rng)
    stream = rng.permutation(batch)
    short = float(np.mean([pcs[i].length < 1.0 for i in batch]))
    rows = []
    for name, make in [("offline optimum", None)] + (POLICIES_A if world == "A" else POLICIES_B):
        r = ladder_offline(c, batch) if make is None else run_ladder_episode(c, stream, make(), B, seed=k)
        rows.append(dict(world=world, stream=k, true_short_share=short, policy=name,
                         new_timber_m=r.new_timber_m, reclaimed_share=r.reclaimed_share, waste_m=r.waste_m))
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--quick", action="store_true")
    ap.add_argument("--out", default=str(ROOT / "results" / "hints"))
    a = ap.parse_args()
    n = 2 if a.quick else 40
    jobs = [("A", k) for k in range(n)] + [("B", k) for k in range(n)]
    out = Path(a.out)
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
