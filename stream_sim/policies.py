"""Decision strategies.

Reactive (no look-ahead):
- Greedy:           place the new piece in the first open slot it fits
                    (build order), otherwise discard it.
- TightFit:         place the new piece immediately in the open slot where it
                    fits most tightly (least offcut, least unused capacity),
                    otherwise discard it. Comparable to rule-based ranking.
- BufferedTightFit: keep pieces in the buffer; when the buffer overflows,
                    place the tightest (piece, slot) pair in hand. Uses the
                    buffer but has no model of future supply.

Planning ahead:
- LookAhead:        when the buffer overflows, compare candidate actions
                    (place piece p in slot s, or discard p) on sampled futures
                    and commit the best one (receding horizon). Futures come
                    from a supply model:
                      "source":   statistics of the source inventory (sampled
                                  with replacement; never the actual future),
                      "observed": bootstrap from pieces seen so far.
                    Each (action, future) pair is scored by an evaluator:
                      "rollout":   simulate the future with the TightFit rule,
                                   then place what is still in hand optimally.
                                   This is an achievable plan under the buffer
                                   limit (rollout algorithm, Bertsekas), so the
                                   estimate is not optimistic.
                      "hindsight": exact assignment over hand + future, i.e.
                                   as if the future were known and storage
                                   unlimited. Optimistic; kept for comparison.

All policies return a list of actions; the simulator checks them.
"""

from __future__ import annotations

import numpy as np

from .model import WASTE_WEIGHT, Problem, assign_cost


class Policy:
    name = "policy"

    def reset(self, problem: Problem, buffer_size: int, rng: np.random.Generator):
        self.problem = problem
        self.buffer_size = buffer_size
        self.rng = rng

    def act(self, obs) -> list:
        raise NotImplementedError


class Greedy(Policy):
    name = "greedy"

    def act(self, obs):
        p = obs.new_piece
        for s in obs.open_slots:  # build order
            if self.problem.valid[p, s]:
                return [("place", p, s)]
        return [("discard", p)]


class TightFit(Policy):
    name = "tight fit (rule)"

    def act(self, obs):
        p = obs.new_piece
        cands = [s for s in obs.open_slots if self.problem.valid[p, s]]
        if not cands:
            return [("discard", p)]
        s = min(cands, key=lambda s: self.problem.fit[p, s])
        return [("place", p, s)]


def _discard_useless(problem, hand, open_slots):
    """Pieces that fit no open slot can never be used: discard them."""
    acts = []
    for q in list(hand):
        if not problem.valid[q, open_slots].any():
            acts.append(("discard", q))
            hand.remove(q)
    return acts


class BufferedTightFit(Policy):
    name = "buffered tight fit"

    def act(self, obs):
        hand = list(obs.hand)
        acts = _discard_useless(self.problem, hand, obs.open_slots)
        open_slots = list(obs.open_slots)
        while len(hand) > self.buffer_size:
            pairs = [(q, s) for q in hand for s in open_slots if self.problem.valid[q, s]]
            q, s = min(pairs, key=lambda qs: self.problem.fit[qs])
            acts.append(("place", q, s))
            hand.remove(q)
            open_slots.remove(s)
            acts += _discard_useless(self.problem, hand, open_slots)
        return acts


def rollout_cost(problem: Problem, open_mask: np.ndarray, hand, future) -> float:
    """Cost of following TightFit on ``future`` and placing ``hand`` at the end."""
    open_mask = open_mask.copy()
    cost = 0.0
    fit = problem.fit
    for p in future:
        row = np.where(open_mask, fit[p], np.inf)
        s = int(row.argmin())
        if np.isfinite(row[s]):
            open_mask[s] = False
            cost += WASTE_WEIGHT * problem.waste[p, s]
            if not open_mask.any():
                break
    open_slots = np.flatnonzero(open_mask)
    return cost + assign_cost(problem, open_slots, hand)


class LookAhead(Policy):
    def __init__(self, n_scenarios: int = 16, top_k: int = 3,
                 supply: str = "source", evaluator: str = "rollout",
                 horizon: int | None = None):
        self.n_scenarios = n_scenarios
        self.top_k = top_k
        self.supply = supply
        self.evaluator = evaluator
        self.horizon = horizon
        name = "look-ahead"
        if supply == "observed":
            name += " (learned supply)"
        if evaluator == "hindsight":
            name += " (hindsight)"
        self.name = name

    def reset(self, problem, buffer_size, rng):
        super().reset(problem, buffer_size, rng)
        self.seen: list[int] = []

    def _scenarios(self, n: int) -> list[np.ndarray]:
        if n == 0:
            return [np.empty(0, dtype=int)]
        if self.supply == "observed" and len(self.seen) >= 5:
            pool = np.array(self.seen)
            return [pool[self.rng.integers(0, len(pool), n)] for _ in range(self.n_scenarios)]
        P = len(self.problem.pieces)
        return [self.rng.integers(0, P, n) for _ in range(self.n_scenarios)]

    def _value(self, open_slots, hand, scen) -> float:
        pr = self.problem
        if self.evaluator == "hindsight":
            return float(np.mean([
                assign_cost(pr, open_slots, np.concatenate([hand, sc]).astype(int))
                for sc in scen]))
        mask = np.zeros(len(pr.slots), dtype=bool)
        mask[open_slots] = True
        return float(np.mean([rollout_cost(pr, mask, hand, sc) for sc in scen]))

    def act(self, obs):
        pr = self.problem
        self.seen.append(obs.new_piece)
        hand = list(obs.hand)
        acts = _discard_useless(pr, hand, obs.open_slots)
        open_slots = list(obs.open_slots)
        while len(hand) > self.buffer_size:
            n_future = obs.remaining if self.horizon is None else min(obs.remaining, self.horizon)
            scen = self._scenarios(n_future)  # common random numbers for all actions
            best, best_val = None, np.inf
            for q in hand:
                cands = sorted((s for s in open_slots if pr.valid[q, s]),
                               key=lambda s: pr.fit[q, s])[: self.top_k]
                rest = [h for h in hand if h != q]
                options = [("place", q, s) for s in cands] + [("discard", q)]
                for a in options:
                    if a[0] == "place":
                        slots_after = [s for s in open_slots if s != a[2]]
                        now = WASTE_WEIGHT * pr.waste[q, a[2]]
                    else:
                        # Discarding a usable piece wastes its whole length.
                        slots_after = open_slots
                        now = WASTE_WEIGHT * pr.pieces[q].length
                    val = now + self._value(slots_after, rest, scen)
                    if val < best_val - 1e-9:
                        best, best_val = a, val
            acts.append(best)
            hand.remove(best[1])
            if best[0] == "place":
                open_slots.remove(best[2])
            acts += _discard_useless(pr, hand, open_slots)
        return acts


def default_policies(n_scenarios: int = 16, with_variants: bool = False) -> list[Policy]:
    pols = [Greedy(), TightFit(), BufferedTightFit(), LookAhead(n_scenarios)]
    if with_variants:
        pols += [LookAhead(n_scenarios, supply="observed"),
                 LookAhead(n_scenarios, evaluator="hindsight")]
    return pols
