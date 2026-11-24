"""Reclaimed-timber pieces: synthetic inventory, JSON loader, and streams.

The synthetic inventory is a STAND-IN for the labelled MZ/WI inventory.
It mimics a few demolition sources, each with a typical cross-section,
length distribution and quality mix. Replace it with ``load_inventory_json``
as soon as the real data is available.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np

QUALITY_CODES = {"reject": 0, "standard": 1, "best": 2}


@dataclass(frozen=True)
class Piece:
    id: str
    length: float   # m
    b: float        # mm (smaller side)
    h: float        # mm (larger side)
    quality: int    # 0 reject, 1 standard, 2 best
    source: str = ""


# (name, section b x h in mm, median length m, length spread, share of pieces)
SYNTHETIC_SOURCES = [
    ("battens", (40, 60), 0.9, 0.45, 0.30),
    ("studs", (45, 70), 1.3, 0.40, 0.30),
    ("rafters", (60, 80), 1.6, 0.35, 0.20),
    ("joists", (60, 120), 2.0, 0.30, 0.10),
    ("planks", (40, 100), 1.1, 0.50, 0.10),
]


def synthetic_inventory(n: int = 400, best_fraction: float = 0.25,
                        reject_fraction: float = 0.15,
                        seed: int = 0) -> list[Piece]:
    """Generate a synthetic inventory of ``n`` reclaimed pieces.

    ``best_fraction`` is the share of best-class pieces among all pieces and
    is the main scarcity knob. Each source gets a slightly different mix.
    """
    rng = np.random.default_rng(seed)
    shares = np.array([s[4] for s in SYNTHETIC_SOURCES])
    counts = rng.multinomial(n, shares / shares.sum())
    pieces: list[Piece] = []
    for (name, (b, h), med, spread, _), c in zip(SYNTHETIC_SOURCES, counts):
        fb = np.clip(best_fraction * rng.uniform(0.6, 1.4), 0.0, 1.0 - reject_fraction)
        probs = np.array([reject_fraction, 1.0 - reject_fraction - fb, fb])
        lengths = np.clip(med * np.exp(spread * rng.standard_normal(c)), 0.25, 3.0)
        quals = rng.choice(3, size=c, p=probs)
        for k in range(c):
            pieces.append(Piece(f"SY-{name}-{k:03d}", round(float(lengths[k]), 3),
                                b, h, int(quals[k]), name))
    return pieces


def load_inventory_json(path: str | Path) -> list[Piece]:
    """Load a labelled inventory (e.g. MZ/WI series) from JSON.

    Accepts a list of objects, or an object with a list under "pieces".
    Recognised keys (first match wins, case-insensitive):
      id:      id, label, name
      length:  length_m, length (m, or mm if > 20), length_mm
      b, h:    width/thickness/b and height/depth/h (mm), or section "40x60"
      quality: quality / class / grade as reject|standard|best or 0|1|2
      source:  source, batch, series (default: the id prefix, e.g. "MZ")
    """
    data = json.loads(Path(path).read_text())
    if isinstance(data, dict):
        data = data.get("pieces", list(data.values()))
    pieces = []
    for k, raw in enumerate(data):
        r = {str(key).lower(): v for key, v in raw.items()}
        pid = str(_first(r, ["id", "label", "name"], f"P{k:04d}"))
        if "length_mm" in r:
            length = float(r["length_mm"]) / 1000.0
        else:
            length = float(_first(r, ["length_m", "length"]))
            if length > 20:  # assume mm
                length /= 1000.0
        if "section" in r:
            b, h = (float(x) for x in str(r["section"]).lower().split("x"))
        else:
            b = float(_first(r, ["width", "thickness", "b"]))
            h = float(_first(r, ["height", "depth", "h"]))
        q = _first(r, ["quality", "class", "grade"], "standard")
        q = QUALITY_CODES[q.lower()] if isinstance(q, str) else int(q)
        src = str(_first(r, ["source", "batch", "series"], pid.split("-")[0][:2]))
        pieces.append(Piece(pid, length, min(b, h), max(b, h), q, src))
    return pieces


def _first(r: dict, keys: list[str], default=None):
    for key in keys:
        if key in r and r[key] is not None:
            return r[key]
    if default is None:
        raise KeyError(f"none of {keys} in record {r}")
    return default


# --- Streams ----------------------------------------------------------------

def sample_batch(n_inventory: int, batch_size: int,
                 rng: np.random.Generator) -> np.ndarray:
    """Indices of a batch drawn without replacement from the inventory."""
    return rng.choice(n_inventory, size=batch_size, replace=False)


def random_order(batch: np.ndarray, rng: np.random.Generator) -> np.ndarray:
    return rng.permutation(batch)


def batch_order(batch: np.ndarray, pieces: list[Piece],
                rng: np.random.Generator) -> np.ndarray:
    """Pieces of the same source arrive together, sources in random order."""
    by_src: dict[str, list[int]] = {}
    for i in batch:
        by_src.setdefault(pieces[i].source, []).append(int(i))
    order = []
    for src in rng.permutation(list(by_src)):
        order.extend(rng.permutation(by_src[src]).tolist())
    return np.array(order)
