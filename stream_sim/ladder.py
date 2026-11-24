"""Open geometry: a ladder truss whose panel widths emerge during fabrication.

Design intent (fixed in advance): span, depth, supports, a uniform line load,
and the allowed panel widths. Geometry (decided while building): how many
panels, and how wide each one is. The truss is built from the left support
to the right; it must close exactly at the right support.

Each panel [x, x + w] has a bottom chord, a top chord, a diagonal, and the
vertical at its right node. The vertical at x = 0 exists from the start.
All lengths are on a 0.1 m grid (integer units) to keep closure exact.

Demands use a conservative beam analogy that does not need the final
geometry: chord force <= max M(x) / depth over the panel, diagonal force <=
max |V(x)| * length / depth, vertical force <= |V| within one maximum panel
width + one tributary load.
``tests/test_ladder.py`` checks that these envelopes bound the method-of-
joints forces of fixed layouts. Values are ILLUSTRATIVE placeholders.

Decisions when a piece arrives (or when the buffer is full):
  place p in an open slot | open the next panel with width w, placing p as
  one of its members | keep | discard.
At most ``max_open_panels`` panels may be unfinished (the assembly front).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from functools import lru_cache

import numpy as np

from .model import CUT_TOL, WASTE_WEIGHT, Problem, assign, assign_cost, build_problem
from .structure import Slot

UNIT = 0.1  # m per grid unit
ROLES = ("B", "T", "D", "V")


@dataclass
class LadderSpec:
    span_u: int = 40                 # 4.0 m
    depth: float = 0.6               # m
    widths_u: tuple = (4, 5, 6, 7, 8)  # 0.4 ... 0.8 m
    q_kN_m: float = 8.0              # line load on the top chord
    joint_allowance: float = 0.05
    max_open_panels: int = 2


class LadderCatalogue:
    """Every slot that could ever exist, so validity can be precomputed."""

    def __init__(self, spec: LadderSpec, pieces, cut_cost: float | None = None):
        self.spec = spec
        S, H, q = spec.span_u * UNIT, spec.depth, spec.q_kN_m
        R = q * S / 2
        M = lambda x: q * x * (S - x) / 2  # noqa: E731
        V = lambda x: abs(R - q * x)       # noqa: E731
        slots: list[Slot] = []
        self.index: dict = {}

        def add(key, kind, length, buck, t, c):
            sid = len(slots)
            slots.append(Slot(sid, kind, [], length, buck, t, c,
                              length + 2 * spec.joint_allowance))
            self.index[key] = sid

        wmax = max(spec.widths_u) * UNIT
        for u in range(spec.span_u + 1):
            x = u * UNIT
            # A vertical carries the shear of an adjacent panel (up to one
            # maximum panel width away), plus a tributary load; either sign.
            v = max(V(max(0.0, x - wmax)), V(min(S, x + wmax))) + q * wmax / 2
            v = R if u in (0, spec.span_u) else v
            add(("V", u), "vertical", H, H, v, v)
        for u0 in range(spec.span_u):
            for w in spec.widths_u:
                if u0 + w > spec.span_u:
                    continue
                x0, x1 = u0 * UNIT, (u0 + w) * UNIT
                xm = min(max(S / 2, x0), x1)
                m = max(M(x0), M(x1), M(xm)) / H
                v = max(V(x0), V(x1))
                L = w * UNIT
                Ld = float(np.hypot(L, H))
                add(("B", u0, w), "bottom", L, L, m, 0.0)
                add(("T", u0, w), "top", L, L, 0.0, m)
                # Diagonals slope towards mid-span (tension). The panel that
                # straddles mid-span can see either sign.
                straddle = x0 < S / 2 < x1
                add(("D", u0, w), "diagonal", Ld, Ld, v * Ld / H,
                    v * Ld / H if straddle else 0.0)
        self.slots = slots
        self.future: dict = {}
        self.problem: Problem = build_problem(pieces, slots, cut_cost)

    def panel_slots(self, u0: int, w: int) -> dict:
        ix = self.index
        return {"B": ix[("B", u0, w)], "T": ix[("T", u0, w)],
                "D": ix[("D", u0, w)], "V": ix[("V", u0 + w)]}

    def layout_slots(self, start_u: int, widths) -> list[int]:
        out, u = [], start_u
        for w in widths:
            out += list(self.panel_slots(u, w).values())
            u += w
        return out


@lru_cache(maxsize=None)
def compositions(r: int, widths: tuple) -> tuple:
    """All ordered ways to split r units into allowed panel widths."""
    if r == 0:
        return ((),)
    out = []
    for w in widths:
        if w <= r:
            out += [(w,) + c for c in compositions(r - w, widths)]
    return tuple(out)


def closable(r: int, widths: tuple) -> bool:
    return len(compositions(r, widths)) > 0


@dataclass
class LadderState:
    x: int = 0
    panels: list = field(default_factory=list)   # (u0, w)
    open: list = field(default_factory=list)     # catalogue slot ids
    hand: list = field(default_factory=list)

    def copy(self):
        return LadderState(self.x, list(self.panels), list(self.open), list(self.hand))


def unfinished_panels(cat: LadderCatalogue, st: LadderState) -> int:
    n = 0
    for u0, w in st.panels:
        if any(s in st.open for s in cat.panel_slots(u0, w).values()):
            n += 1
    return n


def commit_options(cat: LadderCatalogue, st: LadderState, p: int):
    """(w, role, slot id) for opening the next panel with piece p."""
    spec, pr = cat.spec, cat.problem
    if st.x >= spec.span_u or unfinished_panels(cat, st) >= spec.max_open_panels:
        return []
    opts = []
    for w in spec.widths_u:
        r = spec.span_u - st.x - w
        if r < 0 or not closable(r, spec.widths_u):
            continue
        for role, sid in cat.panel_slots(st.x, w).items():
            if pr.valid[p, sid]:
                opts.append((w, role, sid))
    return opts


def action_cost(cat: LadderCatalogue, st: LadderState, act) -> float:
    """Objective cost of an action in the current state (before applying it)."""
    pr = cat.problem
    if act[0] == "place":
        return float(pr.cost[act[1], act[2]])
    if act[0] == "commit":
        _, p, w, role = act
        return float(pr.cost[p, cat.panel_slots(st.x, w)[role]])
    p = act[1]
    return WASTE_WEIGHT * pr.pieces[p].length if piece_has_use(cat, st, p) else 0.0


def apply(cat: LadderCatalogue, st: LadderState, act) -> float:
    """Apply an action in place; return its immediate waste in metres."""
    pr = cat.problem
    if act[0] == "place":
        _, p, sid = act
        assert p in st.hand and sid in st.open and pr.valid[p, sid], act
        st.hand.remove(p)
        st.open.remove(sid)
        return float(pr.waste[p, sid])
    if act[0] == "commit":
        _, p, w, role = act
        assert p in st.hand
        assert any(o[:2] == (w, role) for o in commit_options(cat, st, p)), act
        sl = cat.panel_slots(st.x, w)
        st.panels.append((st.x, w))
        st.x += w
        st.open += [s for k, s in sl.items() if k != role]
        st.hand.remove(p)
        return float(pr.waste[p, sl[role]])
    if act[0] == "discard":
        p = act[1]
        assert p in st.hand
        st.hand.remove(p)
        return float(pr.pieces[p].length) if piece_has_use(cat, st, p) else 0.0
    raise ValueError(act)


def piece_has_use(cat: LadderCatalogue, st: LadderState, p: int) -> bool:
    """Fits an open slot, or some slot of a panel that could still be opened."""
    pr = cat.problem
    if st.open and pr.valid[p, st.open].any():
        return True
    return bool(st.x < cat.spec.span_u and pr.valid[p, _future_slots(cat, st.x)].any())


def _future_slots(cat: LadderCatalogue, x: int) -> np.ndarray:
    if x not in cat.future:
        ids = sorted(s for (k, *rest), s in cat.index.items()
                     if (k == "V" and rest[0] > x) or (k != "V" and rest[0] >= x))
        cat.future[x] = np.array(ids, dtype=int)
    return cat.future[x]


def completion(cat: LadderCatalogue, st: LadderState) -> tuple[float, float, list]:
    """Finish the component with the pieces in hand and new timber.

    Tries every geometry for the remaining span; returns (objective,
    new timber m, best remaining widths).
    """
    pr, spec = cat.problem, cat.spec
    r = spec.span_u - st.x
    best = (np.inf, np.inf, None)
    for comp in compositions(r, spec.widths_u):
        slots = st.open + cat.layout_slots(st.x, comp)
        cost, pairs = assign(pr, slots, st.hand)
        if cost < best[0]:
            filled = {slots[s] for _, s in pairs}
            new_m = float(sum(pr.new_cost[s] for s in slots if s not in filled))
            best = (cost, new_m, list(comp))
    return best


@lru_cache(maxsize=None)
def _all_new_cost(cat_id: int, x: int):
    cat = _CATS[cat_id]
    spec, pr = cat.spec, cat.problem
    best = np.inf
    for comp in compositions(spec.span_u - x, spec.widths_u):
        best = min(best, float(pr.new_cost[cat.layout_slots(x, comp)].sum()))
    return 0.0 if spec.span_u == x else best


_CATS: dict = {}


def all_new_cost(cat: LadderCatalogue, x: int) -> float:
    """New timber to finish the span from x with no reclaimed pieces at all."""
    _CATS[id(cat)] = cat
    return _all_new_cost(id(cat), x)


# --- Policies -------------------------------------------------------------------

COMMIT_PENALTY = 0.05  # small preference for finishing open panels first


def candidate_actions(cat, st, p):
    pr = cat.problem
    acts = [(pr.fit[p, s], ("place", p, s)) for s in st.open if pr.valid[p, s]]
    acts += [(pr.fit[p, sid] + COMMIT_PENALTY, ("commit", p, w, role))
             for w, role, sid in commit_options(cat, st, p)]
    acts.sort(key=lambda a: a[0])
    return acts


class LadderRule:
    """Greedy with good rules: tightest fit among open slots and new panels."""
    name = "rule (tight fit + geometry)"

    def reset(self, cat, buffer_size, rng):
        self.cat, self.B, self.rng = cat, buffer_size, rng

    def act(self, st, remaining):
        acts = []
        p = st.hand[-1]
        cands = candidate_actions(self.cat, st, p)
        acts.append(cands[0][1] if cands else ("discard", p))
        return acts


class LadderBufferedRule(LadderRule):
    name = "buffered rule"

    def act(self, st, remaining):
        st = st.copy()
        acts = []
        while len(st.hand) > self.B:
            best = None
            for p in st.hand:
                c = candidate_actions(self.cat, st, p)
                if c and (best is None or c[0][0] < best[0]):
                    best = c[0]
            if best is None:  # nothing fits now: drop the piece with least use
                p = min(st.hand, key=lambda q: (piece_has_use(self.cat, st, q),
                                                self.cat.problem.pieces[q].length))
                best = (0, ("discard", p))
            acts.append(best[1])
            apply(self.cat, st, best[1])
        return acts


def rollout(cat, st: LadderState, future) -> float:
    """Follow the unbuffered rule on ``future``, then finish cheaply."""
    pr = cat.problem
    st = st.copy()
    hand = st.hand
    st.hand = []
    cost = 0.0
    for p in future:
        if st.x >= cat.spec.span_u and not st.open:
            break
        st.hand = [p]
        c = candidate_actions(cat, st, p)
        if c:
            cost += action_cost(cat, st, c[0][1])
            apply(cat, st, c[0][1])
    st.hand = hand
    return cost + assign_cost(pr, st.open, hand) + all_new_cost(cat, st.x)


class LadderLookAhead(LadderRule):
    name = "look-ahead"

    def __init__(self, n_scenarios: int = 8, top_k: int = 2, supply: str = "source",
                 hint_short_share: float | None = None, hint_update: bool = False,
                 short_threshold: float = 1.0, hint_strength: float = 10.0, name: str | None = None):
        """supply: "source" (source statistics), "observed" (bootstrap from seen
        pieces), or "hint": a person's coarse statement "a share h of the
        coming pieces is shorter than short_threshold". With hint_update the
        share is revised from the pieces that arrive (Beta prior with
        hint_strength pseudo-pieces); lengths within each bin follow the
        source statistics."""
        self.n_scenarios, self.top_k, self.supply = n_scenarios, top_k, supply
        self.h, self.h_update, self.thr, self.k0 = hint_short_share, hint_update, short_threshold, hint_strength
        if supply == "observed":
            self.name = "look-ahead (learned supply)"
        if name:
            self.name = name

    def reset(self, cat, buffer_size, rng):
        super().reset(cat, buffer_size, rng)
        self.seen: list[int] = []

    def _scenario(self, n):
        if self.supply == "hint":
            if not hasattr(self, "_bins"):
                L = np.array([p.length for p in self.cat.problem.pieces])
                self._bins = (np.flatnonzero(L < self.thr), np.flatnonzero(L >= self.thr))
            short, long_ = self._bins
            h = self.h
            if self.h_update:
                n_short = sum(self.cat.problem.pieces[i].length < self.thr for i in self.seen)
                h = (self.k0 * self.h + n_short) / (self.k0 + len(self.seen))
            is_short = self.rng.random(n) < h
            out = long_[self.rng.integers(0, len(long_), n)]
            out[is_short] = short[self.rng.integers(0, len(short), is_short.sum())]
            return out
        if self.supply == "observed" and len(self.seen) >= 5:
            pool = np.array(self.seen)
            return pool[self.rng.integers(0, len(pool), n)]
        return self.rng.integers(0, len(self.cat.problem.pieces), n)

    def act(self, st, remaining):
        cat = self.cat
        st = st.copy()
        self.seen.append(st.hand[-1])
        acts = []
        while len(st.hand) > self.B:
            scen = [self._scenario(remaining) for _ in range(self.n_scenarios)]
            best, best_val = None, np.inf
            for p in st.hand:
                cands = candidate_actions(cat, st, p)
                places = [a for _, a in cands if a[0] == "place"][: self.top_k]
                commits = [a for _, a in cands if a[0] == "commit"][: self.top_k]
                for a in places + commits + [("discard", p)]:
                    s2 = st.copy()
                    now = action_cost(cat, s2, a)
                    apply(cat, s2, a)
                    val = now + float(np.mean([rollout(cat, s2, sc) for sc in scen]))
                    if val < best_val - 1e-9:
                        best, best_val = a, val
            acts.append(best)
            apply(cat, st, best)
        return acts


# --- Episode and offline optimum ------------------------------------------------

@dataclass
class LadderResult:
    policy: str
    new_timber_m: float
    reclaimed_share: float
    waste_m: float
    panels: list
    total_length_m: float
    cuts: int = 0


def run_ladder_episode(cat: LadderCatalogue, stream, policy, buffer_size: int,
                       seed: int = 0) -> LadderResult:
    rng = np.random.default_rng(seed)
    policy.reset(cat, buffer_size, rng)
    st = LadderState(open=[cat.index[("V", 0)]])
    waste = 0.0
    cuts = 0
    stream = [int(p) for p in stream]
    for t, p in enumerate(stream):
        if st.x >= cat.spec.span_u and not st.open:
            break
        st.hand.append(p)
        for a in policy.act(st.copy(), len(stream) - t - 1):
            wa = apply(cat, st, a)
            waste += wa
            cuts += int(a[0] != "discard" and wa > CUT_TOL)
        if len(st.hand) > buffer_size:
            raise RuntimeError(f"{policy.name} exceeded the buffer")
    _, new_m, rest = completion(cat, st)
    # Waste of the end-of-stream assignment.
    slots = st.open + cat.layout_slots(st.x, rest)
    _, pairs = assign(cat.problem, slots, st.hand)
    waste += sum(cat.problem.waste[st.hand[a], slots[b]] for a, b in pairs)
    cuts += sum(int(cat.problem.waste[st.hand[a], slots[b]] > CUT_TOL) for a, b in pairs)
    widths = [w for _, w in st.panels] + rest
    total = float(cat.problem.new_cost[cat.layout_slots(0, widths)].sum()
                  + cat.problem.new_cost[cat.index[("V", 0)]])
    return LadderResult(policy.name, new_m, 1 - new_m / total, float(waste),
                        [w * UNIT for w in widths], total, cuts)


def ladder_offline(cat: LadderCatalogue, batch) -> LadderResult:
    """Exact optimum with the whole batch known and unlimited storage:
    every geometry is enumerated, each with an exact assignment."""
    pr = cat.problem
    batch = [int(p) for p in batch]
    v0 = cat.index[("V", 0)]
    best = None
    for comp in compositions(cat.spec.span_u, cat.spec.widths_u):
        slots = [v0] + cat.layout_slots(0, comp)
        cost, pairs = assign(pr, slots, batch)
        if best is None or cost < best[0]:
            best = (cost, comp, slots, pairs)
    cost, comp, slots, pairs = best
    filled = {slots[s] for _, s in pairs}
    new_m = float(sum(pr.new_cost[s] for s in slots if s not in filled))
    waste = float(sum(pr.waste[batch[a], slots[b]] for a, b in pairs))
    cuts = sum(int(pr.waste[batch[a], slots[b]] > CUT_TOL) for a, b in pairs)
    total = float(pr.new_cost[slots].sum())
    return LadderResult("offline optimum", new_m, 1 - new_m / total, waste,
                        [w * UNIT for w in comp], total, cuts)
