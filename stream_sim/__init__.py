"""Stream simulation: building a load-bearing timber component from an
unknown stream of reclaimed pieces, comparing reactive and look-ahead
strategies against the full-foreknowledge optimum."""

from .inventory import (Piece, batch_order, load_inventory_json, random_order,
                        sample_batch, synthetic_inventory)
from .model import Problem, assign, build_problem
from .policies import (BufferedTightFit, Greedy, LookAhead, TightFit,
                       default_policies)
from .simulator import Result, offline_bound, run_episode
from .structure import make_slots, pratt_truss, solve_member_forces

__all__ = [
    "Piece", "batch_order", "load_inventory_json", "random_order", "sample_batch",
    "synthetic_inventory", "Problem", "assign", "build_problem", "BufferedTightFit",
    "Greedy", "LookAhead", "TightFit", "default_policies", "Result", "offline_bound",
    "run_episode", "make_slots", "pratt_truss", "solve_member_forces",
]
