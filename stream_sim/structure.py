"""Planar truss model, method of joints, and slot requirements.

The component is a statically determinate, triangulated (Pratt) truss.
Member forces are computed once by the method of joints (global nodal
equilibrium, a square linear system). For a determinate truss the forces
do not depend on member stiffness, so they can be precomputed per topology
and turned into per-slot demands.

A *slot* is one position that one reclaimed piece fills. Chords can span
several panels (one piece covers ``chord_span`` consecutive segments);
verticals and diagonals are one slot each.

All structural values are ILLUSTRATIVE and conservative placeholders. They
must be agreed with the structural engineers before results are reported.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np


@dataclass
class Member:
    i: int
    j: int
    kind: str  # "top", "bottom", "vertical", "diagonal"


@dataclass
class Truss:
    nodes: np.ndarray  # (n, 2) in metres
    members: list[Member]
    supports: dict[int, tuple[bool, bool]]  # node -> (fix x, fix y)
    loads: np.ndarray  # (n, 2) external nodal loads in kN (y up)

    def member_length(self, m: Member) -> float:
        return float(np.linalg.norm(self.nodes[m.j] - self.nodes[m.i]))


def pratt_truss(span: float = 4.0, height: float = 0.6, panels: int = 8,
                node_load_kN: float = 3.5) -> Truss:
    """Pratt truss with a pin at the left and a roller at the right support.

    Bottom nodes 0..panels, top nodes panels+1..2*panels+1. A downward load
    acts on every top node. Diagonals slope down towards mid-span.
    """
    w = span / panels
    n = panels
    bottom = [(k * w, 0.0) for k in range(n + 1)]
    top = [(k * w, height) for k in range(n + 1)]
    nodes = np.array(bottom + top, dtype=float)
    t = lambda k: n + 1 + k  # noqa: E731  top node index

    members: list[Member] = []
    for k in range(n):
        members.append(Member(k, k + 1, "bottom"))
    for k in range(n):
        members.append(Member(t(k), t(k + 1), "top"))
    for k in range(n + 1):
        members.append(Member(k, t(k), "vertical"))
    for k in range(n):
        if k < n / 2:
            members.append(Member(t(k), k + 1, "diagonal"))
        else:
            members.append(Member(t(k + 1), k, "diagonal"))

    loads = np.zeros_like(nodes)
    for k in range(n + 1):
        loads[t(k), 1] = -node_load_kN
    supports = {0: (True, True), n: (False, True)}
    return Truss(nodes, members, supports, loads)


def solve_member_forces(truss: Truss) -> tuple[np.ndarray, np.ndarray]:
    """Method of joints as one linear system.

    Returns (member forces in kN, tension positive; reactions in kN).
    Raises ValueError if the truss is not statically determinate.
    """
    n = len(truss.nodes)
    m = len(truss.members)
    reac = [(node, d) for node, fix in truss.supports.items()
            for d, f in enumerate(fix) if f]
    if m + len(reac) != 2 * n:
        raise ValueError(
            f"not statically determinate: m + r = {m + len(reac)}, 2j = {2 * n}")
    A = np.zeros((2 * n, m + len(reac)))
    for col, mem in enumerate(truss.members):
        d = truss.nodes[mem.j] - truss.nodes[mem.i]
        u = d / np.linalg.norm(d)
        # A tension member pulls node i towards j and node j towards i.
        A[2 * mem.i: 2 * mem.i + 2, col] += u
        A[2 * mem.j: 2 * mem.j + 2, col] -= u
    for k, (node, d) in enumerate(reac):
        A[2 * node + d, m + k] = 1.0
    b = -truss.loads.reshape(-1)
    if np.linalg.matrix_rank(A) < A.shape[0]:
        raise ValueError("truss is a mechanism (singular equilibrium matrix)")
    x = np.linalg.solve(A, b)
    return x[:m], x[m:]


@dataclass
class Slot:
    id: int
    kind: str
    members: list[int]
    length: float            # geometric length covered by one piece (m)
    buckling_length: float   # longest unbraced segment (m)
    tension_kN: float        # max tension demand (>= 0)
    compression_kN: float    # max compression demand (>= 0)
    required_length: float = field(default=0.0)  # length incl. joint allowance


def make_slots(truss: Truss, chord_span: int = 2,
               joint_allowance: float = 0.05) -> list[Slot]:
    """Group members into slots and attach demands from the method of joints."""
    forces, _ = solve_member_forces(truss)
    groups: list[tuple[str, list[int]]] = []
    for kind in ("bottom", "top"):
        idx = [k for k, mem in enumerate(truss.members) if mem.kind == kind]
        for a in range(0, len(idx), chord_span):
            groups.append((kind, idx[a:a + chord_span]))
    for kind in ("vertical", "diagonal"):
        for k, mem in enumerate(truss.members):
            if mem.kind == kind:
                groups.append((kind, [k]))

    slots = []
    for sid, (kind, mids) in enumerate(groups):
        lens = [truss.member_length(truss.members[k]) for k in mids]
        f = forces[mids]
        L = float(sum(lens))
        slots.append(Slot(
            id=sid, kind=kind, members=mids, length=L,
            buckling_length=float(max(lens)),
            tension_kN=float(max(0.0, f.max())),
            compression_kN=float(max(0.0, -f.min())),
            required_length=L + 2 * joint_allowance,
        ))
    return slots


# --- Capacities -----------------------------------------------------------
# Characteristic values loosely after EN 338 (standard ~ C16, best ~ C24).
# Design factor k_mod / gamma_M = 0.8 / 1.3. Tension uses a net-section
# factor for fastener holes. Compression uses a Rankine combination of
# squash load and Euler buckling about the weak axis. PLACEHOLDERS.
QUALITY_PROPS = {
    1: dict(name="standard", ft=8.5, fc=17.0, E05=5400.0),
    2: dict(name="best", ft=14.5, fc=21.0, E05=7400.0),
}
DESIGN_FACTOR = 0.8 / 1.3
NET_SECTION = 0.8


def capacities(b_mm: float, h_mm: float, quality: int,
               buckling_length_m: float) -> tuple[float, float]:
    """(tension capacity, compression capacity) in kN. Quality 0 -> (0, 0)."""
    if quality not in QUALITY_PROPS:
        return 0.0, 0.0
    p = QUALITY_PROPS[quality]
    A = b_mm * h_mm
    t_cap = p["ft"] * DESIGN_FACTOR * NET_SECTION * A / 1000.0
    n_pl = p["fc"] * DESIGN_FACTOR * A / 1000.0
    i_min = min(b_mm, h_mm) / np.sqrt(12.0)
    lam = buckling_length_m * 1000.0 / i_min
    n_cr = np.pi ** 2 * p["E05"] * A / lam ** 2 / 1000.0
    c_cap = 1.0 / (1.0 / n_pl + 1.0 / n_cr)
    return float(t_cap), float(c_cap)
