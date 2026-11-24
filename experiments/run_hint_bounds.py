"""Decompose the misleading-supply gap (world A of run_hints.py):
  perfect supply model: look-ahead samples futures from the TRUE biased distribution
                        (the best any hint about the distribution can do)
  clairvoyant look-ahead: the scenario is the actual remaining stream
                        (perfect knowledge, but still online with a buffer of 3)
  larger storage: look-ahead without hint, and buffered rule, with a buffer of 8
Appends rows to results/hints/runs.csv."""
from __future__ import annotations
import csv, sys
from multiprocessing import Pool
from pathlib import Path
import numpy as np
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from stream_sim.ladder import LadderBufferedRule, LadderLookAhead, run_ladder_episode  # noqa: E402
import run_hints as H  # noqa: E402


class TrueSupply(LadderLookAhead):
    def __init__(self, p):
        super().__init__(16, 3, name="perfect supply model")
        self.p = p

    def _scenario(self, n):
        return self.rng.choice(len(self.p), n, p=self.p)


class Clairvoyant(LadderLookAhead):
    def __init__(self, stream):
        super().__init__(1, 3, name="clairvoyant look-ahead")
        self.stream = list(stream)

    def _scenario(self, n):
        return np.array(self.stream[len(self.stream) - n:], dtype=int)


def job(k):
    c = H.cat()
    pcs = c.problem.pieces
    rng = np.random.default_rng(60_000 + k)
    w = np.array([1.0 / p.length ** 3 for p in pcs])
    p = w / w.sum()
    batch = rng.choice(len(pcs), H.BATCH, replace=False, p=p)
    stream = rng.permutation(batch)
    short = float(np.mean([pcs[i].length < 1.0 for i in batch]))
    out = []
    for pol, b in ((TrueSupply(p), H.B), (Clairvoyant(stream), H.B),
                   (LadderLookAhead(16, 3, name="look-ahead, no hint, buffer 8"), 8),
                   (LadderBufferedRule(), 8)):
        if b == 8 and isinstance(pol, LadderBufferedRule):
            pol.name = "buffered rule, buffer 8"
        r = run_ladder_episode(c, stream, pol, b, seed=k)
        out.append(dict(world="A", stream=k, true_short_share=short, policy=pol.name,
                        new_timber_m=r.new_timber_m, reclaimed_share=r.reclaimed_share, waste_m=r.waste_m))
    return out


if __name__ == "__main__":
    sys.path.insert(0, str(ROOT / "experiments"))
    with Pool(2) as pool:
        rows = [r for rs in pool.map(job, range(40)) for r in rs]
    f = ROOT / "results" / "hints" / "runs.csv"
    with open(f, "a", newline="") as fh:
        csv.DictWriter(fh, fieldnames=list(rows[0])).writerows(rows)
    print(len(rows), "rows appended")
