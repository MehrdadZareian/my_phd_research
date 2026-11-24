"""A 4 x 4 m wall panel whose node positions emerge from the material.

Intent (fixed in advance): outline 4 x 4 m, a 4 x 4 grid of cells with one
diagonal each (fixed topology, 25 nodes, 56 members), supports at the two
bottom corners, a vertical load on every top node and a horizontal load on
every left-edge node.

Geometry (emerges): corner nodes are fixed; edge nodes slide along their edge
and interior nodes move in a box, each within +-``box`` on a ``step`` grid.
A member can be built once at least one of its nodes is placed. If the other
node is not placed yet, the piece that is built decides where it goes, so the
member can match the piece with little or no cut ("fit the node to the piece").

Structure: the panel is statically indeterminate, so member forces come from
a linear stiffness solve (uniform EA). With open geometry, demands are
conservative envelopes over sampled node layouts (x ``margin``); every finished
panel is re-checked on its actual geometry. Values are ILLUSTRATIVE.

``FrameModel(open_geometry=False)`` gives the same panel with every node fixed
at its nominal position (the design decided before fabrication).
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
from scipy.optimize import linear_sum_assignment

from .model import CUT_TOL, WASTE_WEIGHT
from .structure import DESIGN_FACTOR, NET_SECTION, QUALITY_PROPS

ALLOW = 0.05  # joint allowance at each end (m)
_BIG = 1e6


# --- Stiffness solver ---------------------------------------------------------

def truss_forces(pos, members, supports, loads, EA=3.0e4) -> np.ndarray:
    """Axial member forces (kN, tension +) of a pin-jointed plane truss."""
    n = len(pos)
    K = np.zeros((2 * n, 2 * n))
    geo = []
    for a, b in members:
        d = pos[b] - pos[a]
        L = float(np.hypot(*d))
        c, s = d / L
        k = EA / L * np.outer([-c, -s, c, s], [-c, -s, c, s])
        idx = [2 * a, 2 * a + 1, 2 * b, 2 * b + 1]
        K[np.ix_(idx, idx)] += k
        geo.append((L, c, s))
    fixed = [2 * nd + d for nd, dofs in supports.items() for d in dofs]
    free = np.setdiff1d(np.arange(2 * n), fixed)
    u = np.zeros(2 * n)
    u[free] = np.linalg.solve(K[np.ix_(free, free)], loads.reshape(-1)[free])
    return np.array([EA / L * ((u[2 * b] - u[2 * a]) * c + (u[2 * b + 1] - u[2 * a + 1]) * s)
                     for (a, b), (L, c, s) in zip(members, geo)])


# --- Model ---------------------------------------------------------------------

class FrameModel:
    def __init__(self, pieces, open_geometry: bool = True, n: int = 4, cell: float = 1.0,
                 box: float = 0.25, step: float = 0.05, top_load: float = 6.0,
                 side_load: float = 2.0, n_samples: int = 300, margin: float = 1.05, seed: int = 0):
        self.n, self.open = n, open_geometry
        # "waste": new timber (m) + WASTE_WEIGHT * offcut;  "cuts": one unit per cut,
        # where every new-timber member also counts as one cut (+ 0.05 per m as tie-break).
        self.objective = "waste"
        N = n + 1
        self.nodes = [(i, j) for j in range(N) for i in range(N)]
        nid = {ij: k for k, ij in enumerate(self.nodes)}
        self.nominal = np.array([(i * cell, j * cell) for i, j in self.nodes])
        # Candidate positions per node.
        offs = np.round(np.arange(-box, box + 1e-9, step), 6) if open_geometry else np.array([0.0])
        self.cands, self.nom_idx = [], []
        for (i, j), p0 in zip(self.nodes, self.nominal):
            corner = i in (0, n) and j in (0, n)
            if corner:
                c = np.array([p0])
            elif j in (0, n):        # bottom/top edge: slide in x
                c = np.array([p0 + (o, 0.0) for o in offs])
            elif i in (0, n):        # left/right edge: slide in y
                c = np.array([p0 + (0.0, o) for o in offs])
            else:
                c = np.array([p0 + (ox, oy) for ox in offs for oy in offs])
            self.cands.append(c)
            self.nom_idx.append(int(np.argmin(np.hypot(*(c - p0).T))))
        self.nom_idx = np.array(self.nom_idx)
        # Topology.
        self.members = []
        for j in range(N):
            for i in range(n):
                self.members.append((nid[(i, j)], nid[(i + 1, j)]))
        for j in range(n):
            for i in range(N):
                self.members.append((nid[(i, j)], nid[(i, j + 1)]))
        for j in range(n):
            for i in range(n):
                if (i + j) % 2 == 0:
                    self.members.append((nid[(i, j)], nid[(i + 1, j + 1)]))
                else:
                    self.members.append((nid[(i + 1, j)], nid[(i, j + 1)]))
        self.M = len(self.members)
        # Distance tables between candidate sets of each member's nodes.
        self.D = [np.hypot(*(self.cands[a][:, None, :] - self.cands[b][None, :, :]).transpose(2, 0, 1))
                  for a, b in self.members]
        self.Lmin = np.array([d.min() for d in self.D])
        self.incident = [[m for m, (a, b) in enumerate(self.members) if k in (a, b)]
                         for k in range(len(self.nodes))]
        # Supports and loads.
        self.supports = {nid[(0, 0)]: (0, 1), nid[(n, 0)]: (0, 1)}
        self.loads = np.zeros((len(self.nodes), 2))
        for i in range(N):
            self.loads[nid[(i, n)], 1] -= top_load
        for j in range(1, N):
            self.loads[nid[(0, j)], 0] += side_load
        # Demand envelopes.
        rng = np.random.default_rng(seed)
        samples = [self.nom_idx] if not open_geometry else \
            [self.nom_idx] + [np.array([rng.integers(len(c)) for c in self.cands]) for _ in range(n_samples)]
        F = np.array([truss_forces(self.positions(ci), self.members, self.supports, self.loads)
                      for ci in samples])
        m = 1.0 if not open_geometry else margin
        self.dt = np.maximum(0.0, F.max(axis=0)) * m
        self.dc = np.maximum(0.0, -F.min(axis=0)) * m
        # Pieces.
        self.pieces = pieces
        self.Lp = np.array([p.length for p in pieces])
        self.q = np.array([p.quality for p in pieces])
        A = np.array([p.b * p.h for p in pieces], float)
        get = lambda key: np.array([QUALITY_PROPS.get(p.quality, {key: 0.0})[key] for p in pieces])  # noqa: E731
        self.tcap = get("ft") * DESIGN_FACTOR * NET_SECTION * A / 1000.0
        self.npl = get("fc") * DESIGN_FACTOR * A / 1000.0
        self.EA05 = get("E05") * A
        self.imin = np.array([min(p.b, p.h) for p in pieces]) / np.sqrt(12.0)
        # Could piece p ever fit member m (shortest geometry)?
        self.usable0 = self.valid_matrix(np.arange(len(pieces)), self.Lmin)

    def positions(self, ci) -> np.ndarray:
        ci = np.where(np.asarray(ci) < 0, self.nom_idx, ci)
        return np.array([self.cands[k][c] for k, c in enumerate(ci)])

    def lengths(self, ci) -> np.ndarray:
        ci = np.where(np.asarray(ci) < 0, self.nom_idx, ci)
        return np.array([self.D[m][ci[a], ci[b]] for m, (a, b) in enumerate(self.members)])

    def ccap(self, P, L):
        lam = np.asarray(L) * 1000.0 / self.imin[P]
        ncr = np.pi ** 2 * self.EA05[P] / np.maximum(lam, 1e-9) ** 2 / 1000.0
        with np.errstate(divide="ignore", invalid="ignore"):
            return np.where(self.npl[P] > 0, 1.0 / (1.0 / self.npl[P] + 1.0 / ncr), 0.0)

    def valid_matrix(self, P, L, members=None):
        """(len(P), len(members)) validity for member lengths L."""
        mem = np.arange(self.M) if members is None else np.asarray(members)
        P = np.asarray(P)
        L = np.asarray(L)[None, :] if np.ndim(L) else L
        Lr = np.broadcast_to(L, (1, len(mem)))
        ok = (self.q[P, None] > 0) & (self.Lp[P, None] >= Lr + 2 * ALLOW)
        ok &= self.tcap[P, None] >= self.dt[mem][None, :]
        cc = self.ccap(P[:, None], Lr)
        ok &= cc >= self.dc[mem][None, :]
        return ok

    def util(self, p, m, L):
        t = self.dt[m] / self.tcap[p] if self.tcap[p] > 0 else np.inf
        c = self.dc[m] / self.ccap(np.array([p]), np.array([L]))[0] if self.dc[m] > 0 else 0.0
        return max(t, c)


# --- State and actions -----------------------------------------------------------

@dataclass
class FrameState:
    ci: np.ndarray                      # candidate index per node, -1 = not placed
    built: np.ndarray                   # bool per member
    L: np.ndarray                       # member length if both nodes placed, else nan
    hand: list = field(default_factory=list)
    placed: list = field(default_factory=list)   # (piece, member)

    def copy(self):
        return FrameState(self.ci.copy(), self.built.copy(), self.L.copy(),
                          list(self.hand), list(self.placed))


def _update_lengths(fm, st, node):
    for m in fm.incident[node]:
        a, b = fm.members[m]
        if st.ci[a] >= 0 and st.ci[b] >= 0:
            st.L[m] = fm.D[m][st.ci[a], st.ci[b]]


def initial_state(fm: FrameModel) -> FrameState:
    ci = np.full(len(fm.nodes), -1)
    for k, c in enumerate(fm.cands):
        if len(c) == 1:
            ci[k] = 0
    st = FrameState(ci, np.zeros(fm.M, bool), np.full(fm.M, np.nan))
    for k in range(len(ci)):
        if ci[k] >= 0:
            _update_lengths(fm, st, k)
    return st


def options(fm: FrameModel, st: FrameState, p: int, two_choices: bool = False):
    """Possible placements of piece p: list of (score, action, waste)."""
    out = []
    if fm.q[p] == 0:
        return out
    Lp = fm.Lp[p]
    # Members with both nodes placed (vectorised).
    mm = np.flatnonzero(~st.built & ~np.isnan(st.L) & (fm.tcap[p] >= fm.dt))
    if len(mm):
        L = st.L[mm]
        cc = fm.ccap(np.full(len(mm), p), L)
        ok = (Lp >= L + 2 * ALLOW) & (cc >= fm.dc[mm])
        mm, L, cc = mm[ok], L[ok], cc[ok]
        w = Lp - L - 2 * ALLOW
        u = np.maximum(fm.dt[mm] / fm.tcap[p], np.where(fm.dc[mm] > 0, fm.dc[mm] / cc, 0.0))
        out += [(float(wi + 0.5 * (1 - ui)), ("place", p, int(m), -1, -1), float(wi))
                for m, wi, ui in zip(mm, w, u)]
    # Members with exactly one node placed: the piece decides the other node.
    for m in np.flatnonzero(~st.built & np.isnan(st.L)):
        a, b = fm.members[m]
        ra, rb = st.ci[a] >= 0, st.ci[b] >= 0
        if not (ra or rb) or fm.tcap[p] < fm.dt[m]:
            continue
        node = b if ra else a
        row = fm.D[m][st.ci[a], :] if ra else fm.D[m][:, st.ci[b]]
        ok = row + 2 * ALLOW <= Lp
        if fm.dc[m] > 0 and ok.any():
            ok &= fm.ccap(np.full(len(row), p), row) >= fm.dc[m]
        if not ok.any():
            continue
        idx = np.flatnonzero(ok)
        picks = [idx[np.argmax(row[idx])]]                      # fit the node to the piece
        if two_choices:
            nomd = np.hypot(*(fm.cands[node][idx] - fm.nominal[node]).T)
            picks.append(idx[np.argmin(nomd)])                   # stay near the nominal design
        for c in dict.fromkeys(int(x) for x in picks):
            L = row[c]
            w = Lp - L - 2 * ALLOW
            out.append((w + 0.5 * (1 - fm.util(p, m, L)), ("place", p, int(m), int(node), c), w))
    out.sort(key=lambda o: o[0])
    return out


def piece_useful(fm, st, p) -> bool:
    return bool(fm.usable0[p, ~st.built].any())


def action_cost(fm, st, act, waste=None) -> float:
    if act[0] == "place":
        return WASTE_WEIGHT * waste
    return WASTE_WEIGHT * fm.Lp[act[1]] if piece_useful(fm, st, act[1]) else 0.0


def apply(fm, st, act) -> float:
    """Apply in place; return offcut (place) or 0."""
    if act[0] == "discard":
        st.hand.remove(act[1])
        return 0.0
    _, p, m, node, c = act
    assert p in st.hand and not st.built[m]
    if node >= 0:
        assert st.ci[node] < 0
        st.ci[node] = c
        _update_lengths(fm, st, node)
    a, b = fm.members[m]
    assert st.ci[a] >= 0 and st.ci[b] >= 0
    L = fm.D[m][st.ci[a], st.ci[b]]
    assert fm.Lp[p] >= L + 2 * ALLOW - 1e-9
    st.built[m] = True
    st.hand.remove(p)
    st.placed.append((p, m))
    return float(fm.Lp[p] - L - 2 * ALLOW)


def completion(fm, st, extra=()) -> tuple[float, list]:
    """Unplaced nodes at nominal; assign hand (+ extra pieces) optimally to
    unbuilt members; the rest gets new timber. Returns (cost, pairs)."""
    mem = np.flatnonzero(~st.built)
    if len(mem) == 0:
        return 0.0, []
    L = fm.lengths(st.ci)[mem]
    P = np.array(list(st.hand) + list(extra), dtype=int)
    new = L + 2 * ALLOW
    if len(P) == 0:
        return float(new.sum() if fm.objective != "cuts" else len(new) + WASTE_WEIGHT * new.sum()), []
    V = fm.valid_matrix(P, L, mem)
    W = fm.Lp[P, None] - (L + 2 * ALLOW)[None, :]
    if fm.objective == "cuts":
        C = np.where(V, (W > CUT_TOL) + 0.001 * W, _BIG).T
        newc = 1.0 + WASTE_WEIGHT * new
    else:
        C = np.where(V, WASTE_WEIGHT * W, _BIG).T
        newc = new
    C = np.hstack([C, np.tile(newc[:, None], (1, len(mem)))])
    r, c = linear_sum_assignment(C)
    pairs = [(int(P[cc]), int(mem[rr])) for rr, cc in zip(r, c) if cc < len(P)]
    return float(C[r, c].sum()), pairs


# --- Policies ----------------------------------------------------------------------

class FrameWindowRule:
    """Tightest fit among the pieces in the window (fit the node to the piece)."""
    name = "window rule"

    def reset(self, fm, B, rng):
        self.fm, self.B, self.rng = fm, B, rng

    def best_or_discard(self, st):
        best = None
        for p in st.hand:
            o = options(self.fm, st, p)
            if o and (best is None or o[0][0] < best[0]):
                best = o[0]
        if best is not None:
            return best[1]
        p = min(st.hand, key=lambda q: (piece_useful(self.fm, st, q), self.fm.Lp[q]))
        return ("discard", p)

    def act(self, st, remaining):
        st = st.copy()
        acts = []
        while len(st.hand) > self.B:
            a = self.best_or_discard(st)
            acts.append(a)
            apply(self.fm, st, a)
        return acts


def rollout(fm, st, future, horizon):
    st = st.copy()
    hand = st.hand
    cost = 0.0
    for p in future[:horizon]:
        if st.built.all():
            break
        st.hand = [int(p)]
        o = options(fm, st, int(p))
        if o:
            cost += WASTE_WEIGHT * o[0][2]
            apply(fm, st, o[0][1])
    st.hand = hand
    return cost + completion(fm, st, extra=future[horizon:])[0]


class FrameLookAhead(FrameWindowRule):
    """supply="source": futures sampled from the inventory statistics;
    supply="observed": futures bootstrapped from pieces seen so far."""
    name = "window look-ahead"

    def __init__(self, n_scenarios=6, top_k=2, horizon=30, supply="source"):
        self.n_scenarios, self.top_k, self.horizon, self.supply = n_scenarios, top_k, horizon, supply
        if supply == "observed":
            self.name = "window look-ahead (learned supply)"

    def reset(self, fm, B, rng):
        super().reset(fm, B, rng)
        self.seen = []

    def _scenario(self, n):
        if self.supply == "observed" and len(self.seen) >= 5:
            pool = np.array(self.seen)
            return pool[self.rng.integers(0, len(pool), n)]
        return self.rng.integers(0, len(self.fm.pieces), n)

    def act(self, st, remaining):
        fm = self.fm
        st = st.copy()
        self.seen.append(st.hand[-1])
        acts = []
        while len(st.hand) > self.B:
            scen = [self._scenario(remaining) for _ in range(self.n_scenarios)]
            best, best_val = None, np.inf
            for p in st.hand:
                cand = [(a, w) for _, a, w in options(fm, st, p, two_choices=True)[: self.top_k + 1]]
                cand.append((("discard", p), None))
                for a, w in cand:
                    s2 = st.copy()
                    now = action_cost(fm, s2, a, w)
                    apply(fm, s2, a)
                    val = now + float(np.mean([rollout(fm, s2, sc, self.horizon) for sc in scen]))
                    if val < best_val - 1e-9:
                        best, best_val = a, val
            acts.append(best)
            apply(fm, st, best)
        return acts


# --- Node-first: choose a node position from the whole window ------------------------

def _max_matching(fit):
    """Maximum bipartite matching on a small boolean matrix (boards x members)."""
    nb, nm = fit.shape
    match_m = [-1] * nm

    def try_board(i, seen):
        for j in np.flatnonzero(fit[i]):
            if not seen[j]:
                seen[j] = True
                if match_m[j] < 0 or try_board(match_m[j], seen):
                    match_m[j] = i
                    return True
        return False

    for i in range(nb):
        try_board(i, [False] * nm)
    return [(match_m[j], j) for j in range(nm) if match_m[j] >= 0]


def node_first_options(fm, st, tol=CUT_TOL, max_per_node=3):
    """For every unplaced node with placed neighbours: the candidate position
    where the most boards in the window fit its members WITHOUT a cut.
    Returns list of (n_boards, waste, shift, action)."""
    hand = np.array(st.hand, dtype=int)
    if len(hand) == 0:
        return []
    out = []
    for v in np.flatnonzero(st.ci < 0):
        nb = []
        for m in fm.incident[v]:
            if st.built[m]:
                continue
            a, b = fm.members[m]
            u = b if a == v else a
            if st.ci[u] >= 0:
                nb.append((m, u, a == v))
        if not nb:
            continue
        d = np.array([fm.D[m][:, st.ci[u]] if v_is_a else fm.D[m][st.ci[u], :] for m, u, v_is_a in nb])
        ms = np.array([m for m, _, _ in nb])
        w = fm.Lp[hand][:, None, None] - (d + 2 * ALLOW)[None]           # (H, n_nb, K)
        fit = (w >= 0) & (w <= tol) & (fm.q[hand] > 0)[:, None, None]
        fit &= (fm.tcap[hand][:, None] >= fm.dt[ms][None, :])[:, :, None]
        if not fit.any():
            continue
        cc = fm.ccap(hand[:, None, None], d[None])
        fit &= cc >= fm.dc[ms][None, :, None]
        n_any = fit.any(axis=0).sum(axis=0)                               # members with a fitting board
        for c in np.flatnonzero(n_any >= max(1, n_any.max())):
            pairs = _max_matching(fit[:, :, c])[:max_per_node]
            if not pairs:
                continue
            waste = float(sum(w[i, j, c] for i, j in pairs))
            shift = float(np.hypot(*(fm.cands[v][c] - fm.nominal[v])))
            act = ("node", int(v), int(c), [(int(hand[i]), int(ms[j])) for i, j in pairs])
            out.append((len(pairs), waste, shift, act))
    out.sort(key=lambda o: (-o[0], o[1], o[2]))
    return out


def apply_node(fm, st, act) -> list:
    _, v, c, pairs = act
    st.ci[v] = c
    _update_lengths(fm, st, v)
    wastes = []
    for p, m in pairs:
        wastes.append(apply(fm, st, ("place", p, m, -1, -1)))
    return wastes


class FrameNodeFirst(FrameWindowRule):
    """Decide node positions from the whole window: place the node where the
    most boards fit its members without cutting. Order of preference:
      1. a node position that fits >= 2 boards without cuts,
      2. a board that fits an existing member without a cut,
      3. a node position that fits 1 board without a cut,
      4. the tightest placement with a cut, 5. discard."""
    name = "node-first rule"

    def act(self, st, remaining):
        fm = self.fm
        st = st.copy()
        acts = []
        while len(st.hand) > self.B:
            nodes = node_first_options(fm, st)
            exact = [o for p in st.hand for o in options(fm, st, p)
                     if o[1][3] < 0 and o[2] <= CUT_TOL]
            if nodes and nodes[0][0] >= 2:
                a = nodes[0][3]
            elif exact:
                a = min(exact, key=lambda o: o[2])[1]
            elif nodes:
                a = nodes[0][3]
            else:
                a = self.best_or_discard(st)
            acts.append(a)
            if a[0] == "node":
                apply_node(fm, st, a)
            else:
                apply(fm, st, a)
        return acts


# --- Episode, offline plan, verification --------------------------------------------

@dataclass
class FrameResult:
    policy: str
    new_timber_m: float
    reclaimed_share: float
    waste_m: float
    cuts: int
    violations: int
    max_node_shift_m: float
    new_members: int = 0


def finish(fm, st, name, waste, cuts, return_state=False):
    _, pairs = completion(fm, st)
    ci = np.where(st.ci < 0, fm.nom_idx, st.ci)
    L = fm.lengths(ci)
    placed = st.placed + pairs
    for p, m in pairs:
        w = fm.Lp[p] - L[m] - 2 * ALLOW
        waste += w
        cuts += int(w > CUT_TOL)
    filled = {m for _, m in placed}
    need = L + 2 * ALLOW
    new_m = float(sum(need[m] for m in range(fm.M) if m not in filled))
    F = truss_forces(fm.positions(ci), fm.members, fm.supports, fm.loads)
    viol = 0
    for p, m in placed:
        if F[m] > 0 and fm.tcap[p] < F[m] - 1e-6:
            viol += 1
        if F[m] < 0 and fm.ccap(np.array([p]), np.array([L[m]]))[0] < -F[m] - 1e-6:
            viol += 1
    shift = float(np.max(np.hypot(*(fm.positions(ci) - fm.nominal).T)))
    res = FrameResult(name, new_m, 1 - new_m / need.sum(), float(waste), int(cuts), viol, shift,
                      fm.M - len(filled))
    if return_state:
        return res, dict(pos=fm.positions(ci), placed=placed, lengths=L, forces=F)
    return res


def run_frame_episode(fm, stream, policy, B, seed=0, return_state=False):
    rng = np.random.default_rng(seed)
    policy.reset(fm, B, rng)
    st = initial_state(fm)
    stream = [int(p) for p in stream]
    waste, cuts = 0.0, 0
    for t, p in enumerate(stream):
        if st.built.all():
            break
        st.hand.append(p)
        for a in policy.act(st.copy(), len(stream) - t - 1):
            if a[0] == "node":
                ws = apply_node(fm, st, a)
            elif a[0] == "place":
                ws = [apply(fm, st, a)]
            else:
                apply(fm, st, a)
                ws = []
            waste += sum(ws)
            cuts += sum(int(w > CUT_TOL) for w in ws)
        assert len(st.hand) <= B
    return finish(fm, st, policy.name, waste, cuts, return_state)


def frame_offline(fm, batch, iters=1500, seed=0) -> FrameResult:
    """Fixed geometry: exact assignment. Open geometry: local search over node
    positions, each evaluated by exact assignment (heuristic, not a bound)."""
    rng = np.random.default_rng(seed)
    batch = [int(p) for p in batch]
    st = initial_state(fm)
    st.ci = np.where(st.ci < 0, fm.nom_idx, st.ci)
    st.L = fm.lengths(st.ci)
    st.hand = list(batch)
    best = completion(fm, st)[0]
    movable = [k for k, c in enumerate(fm.cands) if len(c) > 1]
    for _ in range(iters if movable else 0):
        k = movable[rng.integers(len(movable))]
        old = st.ci[k]
        st.ci[k] = rng.integers(len(fm.cands[k]))
        c = completion(fm, st)[0]
        if c <= best:
            best = c
        else:
            st.ci[k] = old
    return finish(fm, st, "offline plan", 0.0, 0)
