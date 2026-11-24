"""Adversarial tests for the open-geometry ladder -> results/adversarial/.

1. Structured bad orders of the same batch (offline optimum is unchanged,
   since it does not depend on order):
     random | long first | short first | best class last | best class first
2. Search adversary: for each batch and each strategy separately, hill-climb
   over arrival orders (swaps and segment reversals) to maximise that
   strategy's new timber. The adversary knows the strategy and its random seed.
3. Misleading supply: the batch is drawn with a strong bias towards short
   pieces, while the look-ahead still assumes the source statistics. A
   variant that learns the supply from pieces seen so far is added.

Usage: python experiments/run_adversarial.py [--quick]
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
                               LadderLookAhead, LadderRule, LadderSpec,
                               ladder_offline, run_ladder_episode)

B, BATCH, BEST = 3, 45, 0.15
SEARCH_ITERS = 25
_cat = None


def cat():
    global _cat
    if _cat is None:
        _cat = LadderCatalogue(LadderSpec(), synthetic_inventory(400, best_fraction=BEST, seed=1))
    return _cat


def policies(with_learned=False):
    pols = [("greedy rule", LadderRule), ("buffered rule", LadderBufferedRule),
            ("look-ahead", lambda: LadderLookAhead(16, 3))]
    if with_learned:
        pols.append(("look-ahead (learned supply)", lambda: LadderLookAhead(16, 3, supply="observed")))
    return pols


def order(batch, kind, pieces, rng):
    b = rng.permutation(batch)
    L = np.array([pieces[i].length for i in b])
    Q = np.array([pieces[i].quality for i in b])
    if kind == "long first":
        return b[np.argsort(-L, kind="stable")]
    if kind == "short first":
        return b[np.argsort(L, kind="stable")]
    if kind == "best class last":
        return b[np.argsort(Q == 2, kind="stable")]
    if kind == "best class first":
        return b[np.argsort(Q != 2, kind="stable")]
    return b


def row(exp, k, kind, policy, r):
    return dict(experiment=exp, stream=k, order=kind, policy=policy,
                new_timber_m=r.new_timber_m, reclaimed_share=r.reclaimed_share, waste_m=r.waste_m)


def job_structured(k):
    c = cat()
    pcs = c.problem.pieces
    rng = np.random.default_rng(30_000 + k)
    batch = sample_batch(len(pcs), BATCH, rng)
    rows = [row("structured", k, "any", "offline optimum", ladder_offline(c, batch))]
    for kind in ("random", "long first", "short first", "best class last", "best class first"):
        st = order(batch, kind, pcs, np.random.default_rng(k))
        for name, make in policies():
            rows.append(row("structured", k, kind, name, run_ladder_episode(c, st, make(), B, seed=k)))
    return rows


def job_search(k):
    c = cat()
    rng = np.random.default_rng(40_000 + k)
    batch = sample_batch(len(c.problem.pieces), BATCH, rng)
    rows = [row("search", k, "any", "offline optimum", ladder_offline(c, batch))]
    start = rng.permutation(batch)
    for name, make in policies():
        cost = lambda s: run_ladder_episode(c, s, make(), B, seed=k)  # noqa: E731
        best_s, best = start.copy(), cost(start)
        rows.append(row("search", k, "random", name, best))
        for _ in range(SEARCH_ITERS):
            s = best_s.copy()
            i, j = sorted(rng.choice(len(s), 2, replace=False))
            if rng.random() < 0.5:
                s[i], s[j] = s[j], s[i]
            else:
                s[i:j + 1] = s[i:j + 1][::-1]
            r = cost(s)
            if r.new_timber_m >= best.new_timber_m:
                best_s, best = s, r
        rows.append(row("search", k, "adversarial search", name, best))
    return rows


def job_mismatch(k):
    c = cat()
    pcs = c.problem.pieces
    rng = np.random.default_rng(50_000 + k)
    w = np.array([1.0 / p.length ** 3 for p in pcs])  # strongly favour short pieces
    batch = rng.choice(len(pcs), BATCH, replace=False, p=w / w.sum())
    st = rng.permutation(batch)
    rows = [row("mismatch", k, "biased supply", "offline optimum", ladder_offline(c, batch))]
    for name, make in policies(with_learned=True):
        rows.append(row("mismatch", k, "biased supply", name, run_ladder_episode(c, st, make(), B, seed=k)))
    return rows


def run(fn, k):
    return fn(k)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--quick", action="store_true")
    ap.add_argument("--out", default=str(ROOT / "results" / "adversarial"))
    a = ap.parse_args()
    n_struct, n_search, n_mis = (2, 1, 2) if a.quick else (40, 20, 40)
    jobs = ([(job_search, k) for k in range(n_search)] + [(job_structured, k) for k in range(n_struct)]
            + [(job_mismatch, k) for k in range(n_mis)])
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    t0, rows = time.time(), []
    with Pool(2) as pool:
        for i, r in enumerate(pool.starmap(run, jobs, chunksize=1)):
            rows += r
    rows.sort(key=lambda r: (r["experiment"], r["order"], r["policy"], r["stream"]))
    with open(out / "runs.csv", "w", newline="") as f:
        wr = csv.DictWriter(f, fieldnames=list(rows[0]))
        wr.writeheader()
        wr.writerows(rows)
    print(f"{len(rows)} rows in {time.time() - t0:.0f} s")


if __name__ == "__main__":
    main()
