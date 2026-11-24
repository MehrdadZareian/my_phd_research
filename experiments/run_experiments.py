"""Run the stream-simulation experiments and write results/ (CSV, summary, figures).

Usage:
    python experiments/run_experiments.py                # synthetic inventory
    python experiments/run_experiments.py --inventory data/mz_wi.json
    python experiments/run_experiments.py --quick        # few streams, for testing

Every policy sees exactly the same batches and arrival orders.
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

from stream_sim import (BufferedTightFit, Greedy, LookAhead, TightFit,  # noqa: E402
                        batch_order, build_problem, load_inventory_json,
                        make_slots, offline_bound, pratt_truss, random_order,
                        run_episode, sample_batch, synthetic_inventory)

DEFAULTS = dict(order="random", buffer=3, best_fraction=0.15, supply_ratio=1.5,
                node_load=4.5)
N_SCEN = 16
_INVENTORY_PATH = None


def make_policies(variants: bool):
    pols = [Greedy(), TightFit(), BufferedTightFit(), LookAhead(N_SCEN)]
    if variants:
        pols += [LookAhead(N_SCEN, supply="observed"), LookAhead(N_SCEN, evaluator="hindsight")]
    return pols


_cache = {}


def get_problem(best_fraction, node_load):
    key = (best_fraction, node_load)
    if key not in _cache:
        slots = make_slots(pratt_truss(node_load_kN=node_load))
        if _INVENTORY_PATH:
            inv = load_inventory_json(_INVENTORY_PATH)
        else:
            inv = synthetic_inventory(400, best_fraction=best_fraction, seed=1)
        _cache[key] = build_problem(inv, slots)
    return _cache[key]


def run_job(job):
    experiment, cfg, k, variants = job
    pb = get_problem(cfg["best_fraction"], cfg["node_load"])
    rng = np.random.default_rng(10_000 + k)
    batch = sample_batch(len(pb.pieces), int(round(cfg["supply_ratio"] * len(pb.slots))), rng)
    stream = random_order(batch, rng) if cfg["order"] == "random" else batch_order(batch, pb.pieces, rng)
    rows = []
    results = [offline_bound(pb, batch)]
    for pol in make_policies(variants):
        results.append(run_episode(pb, stream, pol, cfg["buffer"], seed=k))
    for r in results:
        rows.append(dict(experiment=experiment, stream=k, **cfg, policy=r.policy,
                         new_timber_m=r.new_timber_m,
                         new_timber_pct=100 * r.new_timber_m / pb.total_required,
                         new_timber_count=r.new_timber_count,
                         reclaimed_share=r.reclaimed_share, waste_m=r.waste_m,
                         discarded_usable=r.discarded_usable, arrivals_used=r.arrivals_used))
    return rows


def build_jobs(n_main, n_sweep):
    jobs = []
    for order in ("random", "batch"):
        cfg = dict(DEFAULTS, order=order)
        jobs += [("main", cfg, k, True) for k in range(n_main)]
    sweeps = {
        "buffer": [0, 1, 2, 4, 8],
        "best_fraction": [0.05, 0.10, 0.15, 0.25, 0.40],
        "supply_ratio": [1.0, 1.25, 1.5, 2.0, 2.5],
    }
    for param, values in sweeps.items():
        for v in values:
            cfg = dict(DEFAULTS, **{param: v})
            jobs += [(f"sweep_{param}", cfg, k, False) for k in range(n_sweep)]
    return jobs


def _init(path):
    global _INVENTORY_PATH
    _INVENTORY_PATH = path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--inventory", default=None, help="labelled inventory JSON (default: synthetic)")
    ap.add_argument("--quick", action="store_true")
    ap.add_argument("--workers", type=int, default=2)
    ap.add_argument("--out", default=str(ROOT / "results"))
    args = ap.parse_args()
    n_main, n_sweep = (8, 4) if args.quick else (100, 60)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    jobs = build_jobs(n_main, n_sweep)
    t0 = time.time()
    rows = []
    with Pool(args.workers, initializer=_init, initargs=(args.inventory,)) as pool:
        for i, r in enumerate(pool.imap_unordered(run_job, jobs, chunksize=4)):
            rows.extend(r)
            if i % 100 == 0:
                print(f"{i}/{len(jobs)} jobs, {time.time() - t0:.0f} s", flush=True)
    rows.sort(key=lambda r: (r["experiment"], str(r), r["stream"]))
    with open(out / "runs.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    print(f"wrote {len(rows)} rows in {time.time() - t0:.0f} s")
    meta = dict(inventory=args.inventory or "synthetic (400 pieces, seed 1)",
                n_main=n_main, n_sweep=n_sweep, scenarios=N_SCEN, **DEFAULTS)
    (out / "config.txt").write_text("\n".join(f"{k}: {v}" for k, v in meta.items()) + "\n")


if __name__ == "__main__":
    main()
