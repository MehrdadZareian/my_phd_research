"""Online episode: pieces arrive one by one; the policy places, buffers or discards.

Rules enforced by the simulator (identical for every policy):
- The policy only ever sees pieces that have already arrived.
- After each decision, at most ``buffer_size`` pieces may be kept in hand.
- Placements are irreversible and must be valid.
- Discarding a piece that still fits an open slot counts its full length as
  waste (it is lost reclaimed material). Pieces that fit no open slot are
  passed on to other uses and cost nothing.
- When the stream ends, the pieces still in hand are assigned optimally to
  the open slots (everything is known at that point); remaining slots get
  new timber.
- The episode stops as soon as every slot is filled.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from .model import Problem, assign


@dataclass
class Observation:
    t: int                   # index of the arriving piece in the stream
    new_piece: int           # pool index of the arriving piece
    hand: list[int]          # pool indices in hand, including new_piece
    open_slots: list[int]
    remaining: int           # number of pieces still to arrive after this one
    buffer_size: int


@dataclass
class Result:
    policy: str
    new_timber_m: float
    new_timber_count: int
    reclaimed_share: float   # share of required slot length filled with reclaimed wood
    waste_m: float           # offcut + length of discarded pieces that fitted an open slot
    discarded_usable: int    # pieces discarded although they fitted an open slot
    arrivals_used: int
    actions: list = field(default_factory=list, repr=False)


def run_episode(problem: Problem, stream, policy, buffer_size: int,
                seed: int = 0, record: bool = False) -> Result:
    stream = [int(i) for i in stream]
    rng = np.random.default_rng(seed)
    policy.reset(problem, buffer_size, rng)
    open_slots = list(range(len(problem.slots)))
    hand: list[int] = []
    waste = 0.0
    discarded_usable = 0
    log = []
    t = -1
    for t, p in enumerate(stream):
        if not open_slots:
            t -= 1
            break
        hand.append(p)
        obs = Observation(t, p, list(hand), list(open_slots),
                          len(stream) - t - 1, buffer_size)
        for act in policy.act(obs):
            if act[0] == "place":
                _, q, s = act
                if q not in hand or s not in open_slots or not problem.valid[q, s]:
                    raise RuntimeError(f"invalid action {act} by {policy.name}")
                hand.remove(q)
                open_slots.remove(s)
                waste += problem.waste[q, s]
            elif act[0] == "discard":
                q = act[1]
                if q not in hand:
                    raise RuntimeError(f"invalid action {act} by {policy.name}")
                if problem.valid[q, open_slots].any():
                    # Throwing away a piece that could still be used is waste;
                    # pieces that fit nothing open are passed on, not wasted.
                    discarded_usable += 1
                    waste += problem.pieces[q].length
                hand.remove(q)
            else:
                raise RuntimeError(f"unknown action {act}")
            if record:
                log.append((t, act))
        if len(hand) > buffer_size:
            raise RuntimeError(f"{policy.name} exceeded buffer ({len(hand)} > {buffer_size})")

    # End of stream: place what is in hand optimally.
    if open_slots and hand:
        _, pairs = assign(problem, open_slots, hand)
        filled = [open_slots[s] for _, s in pairs]
        for pp, ss in pairs:
            waste += problem.waste[hand[pp], open_slots[ss]]
        open_slots = [s for s in open_slots if s not in filled]
    return _result(problem, policy.name, open_slots, waste, discarded_usable, t + 1, log)


def offline_bound(problem: Problem, batch) -> Result:
    """Full foreknowledge and unlimited storage: a lower bound on new timber."""
    batch = [int(i) for i in batch]
    slots = list(range(len(problem.slots)))
    _, pairs = assign(problem, slots, batch)
    waste = sum(problem.waste[batch[p], s] for p, s in pairs)
    filled = {s for _, s in pairs}
    open_slots = [s for s in slots if s not in filled]
    return _result(problem, "offline optimum", open_slots, waste, 0, len(batch), [])


def _result(problem, name, open_slots, waste, discarded, used, log) -> Result:
    new_m = float(problem.new_cost[open_slots].sum()) if open_slots else 0.0
    return Result(name, new_m, len(open_slots), 1.0 - new_m / problem.total_required,
                  float(waste), discarded, used, log)
