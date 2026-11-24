"""Open-geometry (ladder) experiments -> results/ladder/.

Compares, on identical streams:
  fixed design (8 x 0.5 m, decided before fabrication): tight-fit rule, offline optimum
  open geometry: rule, buffered rule, look-ahead, offline optimum

Usage: python experiments/run_ladder.py [--quick] [--inventory file.json]
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

from stream_sim import (batch_order, load_inventory_json, random_order,  # noqa: E402
                        sample_batch, synthetic_inventory)
from stream_sim.ladder import (LadderBufferedRule, LadderCatalogue,  # noqa: E402
                               LadderLookAhead, LadderRule, LadderSpec,
                               ladder_offline, run_ladder_episode)

DEFAULTS = dict(order="random", buffer=3, best_fraction=0.15, batch_size=45)
_INV = None
_cache: dict = {}


def cats(best_fraction):
    if best_fraction not in _cache:
        inv = load_inventory_json(_INV) if _INV else synthetic_inventory(400, best_fraction=best_fraction, seed=1)
        _cache[best_fraction] = (LadderCatalogue(LadderSpec(), inv),
                                 LadderCatalogue(LadderSpec(widths_u=(5,)), inv))
    return _cache[best_fraction]


def run_job(job):
    exp, cfg, k = job
    open_cat, fixed_cat = cats(cfg["best_fraction"])
    rng = np.random.default_rng(20_000 + k)
    batch = sample_batch(len(open_cat.problem.pieces), cfg["batch_size"], rng)
    stream = (random_order(batch, rng) if cfg["order"] == "random"
              else batch_order(batch, open_cat.problem.pieces, rng))
    B = cfg["buffer"]
    res = [("fixed design", ladder_offline(fixed_cat, batch)),
           ("fixed design", run_ladder_episode(fixed_cat, stream, LadderRule(), B, seed=k)),
           ("fixed design", run_ladder_episode(fixed_cat, stream, LadderLookAhead(16, 3), B, seed=k)),
           ("open geometry", ladder_offline(open_cat, batch))]
    for pol in (LadderRule(), LadderBufferedRule(), LadderLookAhead(16, 3)):
        res.append(("open geometry", run_ladder_episode(open_cat, stream, pol, B, seed=k)))
    return [dict(experiment=exp, stream=k, **cfg, design=d, policy=r.policy,
                 new_timber_m=r.new_timber_m, reclaimed_share=r.reclaimed_share,
                 waste_m=r.waste_m, total_length_m=r.total_length_m,
                 panels=" ".join(f"{w:.1f}" for w in r.panels))
            for d, r in res]


def _init(path):
    global _INV
    _INV = path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--quick", action="store_true")
    ap.add_argument("--inventory", default=None)
    ap.add_argument("--workers", type=int, default=2)
    ap.add_argument("--out", default=str(ROOT / "results" / "ladder"))
    a = ap.parse_args()
    n_main, n_sweep = (4, 2) if a.quick else (60, 40)
    jobs = [("main", dict(DEFAULTS, order=o), k) for o in ("random", "batch") for k in range(n_main)]
    for v in (0.05, 0.10, 0.25):
        jobs += [("sweep_best_fraction", dict(DEFAULTS, best_fraction=v), k) for k in range(n_sweep)]
    for v in (35, 60):
        jobs += [("sweep_batch_size", dict(DEFAULTS, batch_size=v), k) for k in range(n_sweep)]
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    t0, rows = time.time(), []
    with Pool(a.workers, initializer=_init, initargs=(a.inventory,)) as pool:
        for i, r in enumerate(pool.imap_unordered(run_job, jobs)):
            rows += r
            if i % 25 == 0:
                print(f"{i}/{len(jobs)} {time.time() - t0:.0f} s", flush=True)
    rows.sort(key=lambda r: (r["experiment"], r["order"], r["best_fraction"], r["batch_size"],
                             r["stream"], r["design"], r["policy"]))
    with open(out / "runs.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    (out / "config.txt").write_text(
        f"inventory: {a.inventory or 'synthetic (400 pieces, seed 1)'}\n"
        f"n_main: {n_main}\nn_sweep: {n_sweep}\nscenarios: 16, top_k: 3\n"
        + "".join(f"{k}: {v}\n" for k, v in DEFAULTS.items())
        + "spec: span 4.0 m, depth 0.6 m, panel widths 0.4-0.8 m, q 8 kN/m, max 2 open panels\n")
    print(f"done in {time.time() - t0:.0f} s")


if __name__ == "__main__":
    main()
