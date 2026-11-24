"""Piece-slot compatibility and the assignment oracle.

A piece fits a slot if it is not a reject, is long enough after the joint
allowance, and its tension and compression capacities cover the slot's
demands. Cutting is allowed; the offcut counts as waste (v1: offcuts are
not reused).

The oracle answers: given open slots and a set of pieces, what is the
cheapest way to fill the slots, using new timber where no piece fits?
It is a rectangular assignment problem solved exactly with the Hungarian
algorithm (scipy ``linear_sum_assignment``).
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy.optimize import linear_sum_assignment

from .inventory import Piece
from .structure import Slot, capacities

# Cost of 1 m of offcut relative to 1 m of new timber in a slot.
WASTE_WEIGHT = 0.05
# A piece needs a cut if it is longer than the slot by more than this (m).
CUT_TOL = 0.02
_BIG = 1e6


@dataclass
class Problem:
    slots: list[Slot]
    pieces: list[Piece]      # the whole pool (inventory) the batch comes from
    valid: np.ndarray        # (P, S) bool
    waste: np.ndarray        # (P, S) offcut length in m (only meaningful if valid)
    util: np.ndarray         # (P, S) structural utilisation in [0, 1] if valid
    new_cost: np.ndarray     # (S,) m of new timber if the slot is not filled
    cost: np.ndarray         # (P, S) assignment cost, _BIG if invalid
    fit: np.ndarray          # (P, S) tight-fit score (lower = tighter), inf if invalid

    @property
    def total_required(self) -> float:
        return float(self.new_cost.sum())


def build_problem(pieces: list[Piece], slots: list[Slot],
                  cut_cost: float | None = None) -> Problem:
    """Objective per placement: WASTE_WEIGHT * offcut length (default), or,
    with ``cut_cost``, cut_cost per cut (+ a tiny offcut tie-break)."""
    P, S = len(pieces), len(slots)
    valid = np.zeros((P, S), dtype=bool)
    waste = np.zeros((P, S))
    util = np.zeros((P, S))
    for i, pc in enumerate(pieces):
        for j, sl in enumerate(slots):
            if pc.quality == 0 or pc.length < sl.required_length:
                continue
            t_cap, c_cap = capacities(pc.b, pc.h, pc.quality, sl.buckling_length)
            u = max(sl.tension_kN / t_cap, sl.compression_kN / c_cap)
            if u <= 1.0:
                valid[i, j] = True
                waste[i, j] = pc.length - sl.required_length
                util[i, j] = u
    new_cost = np.array([s.required_length for s in slots])
    if cut_cost is None:
        cost = np.where(valid, WASTE_WEIGHT * waste, _BIG)
        # Tight fit: little offcut and little unused structural capacity.
        fit = np.where(valid, waste + 0.5 * (1.0 - util), np.inf)
    else:
        cut = waste > CUT_TOL
        cost = np.where(valid, cut_cost * cut + 0.001 * waste, _BIG)
        # Rule: prefer fits without a cut, then little offcut and unused capacity.
        fit = np.where(valid, 1.0 * cut + 0.1 * waste + 0.5 * (1.0 - util), np.inf)
    return Problem(slots, pieces, valid, waste, util, new_cost, cost, fit)


def assign(problem: Problem, slot_idx, piece_idx) -> tuple[float, list[tuple[int, int]]]:
    """Exact min-cost filling of ``slot_idx`` with pieces ``piece_idx``.

    ``piece_idx`` may contain repeats (sampled scenarios). Returns the total
    cost (m of new timber + WASTE_WEIGHT * m of offcut) and the list of
    (piece position in piece_idx, slot position in slot_idx) pairs that use
    a reclaimed piece.
    """
    slot_idx = np.asarray(slot_idx, dtype=int)
    piece_idx = np.asarray(piece_idx, dtype=int)
    k, m = len(slot_idx), len(piece_idx)
    if k == 0:
        return 0.0, []
    nc = problem.new_cost[slot_idx]
    if m == 0:
        return float(nc.sum()), []
    C = np.empty((k, m + k))
    C[:, :m] = problem.cost[np.ix_(piece_idx, slot_idx)].T
    C[:, m:] = nc[:, None]
    rows, cols = linear_sum_assignment(C)
    total = float(C[rows, cols].sum())
    pairs = [(int(c), int(r)) for r, c in zip(rows, cols) if c < m]
    return total, pairs


def assign_cost(problem: Problem, slot_idx, piece_idx) -> float:
    return assign(problem, slot_idx, piece_idx)[0]
