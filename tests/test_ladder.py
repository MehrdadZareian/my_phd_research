import numpy as np
import pytest

from stream_sim import random_order, sample_batch, synthetic_inventory
from stream_sim.ladder import (UNIT, LadderBufferedRule, LadderCatalogue,
                               LadderLookAhead, LadderRule, LadderSpec,
                               compositions, ladder_offline, run_ladder_episode)
from stream_sim.structure import Member, Truss, solve_member_forces


def layout_truss(widths_u, spec):
    """Pin-jointed Pratt ladder for a given layout, loads q * tributary width."""
    xs = np.concatenate([[0], np.cumsum(widths_u)]) * UNIT
    n = len(xs)
    S = spec.span_u * UNIT
    nodes = np.array([(x, 0.0) for x in xs] + [(x, spec.depth) for x in xs])
    t = lambda k: n + k  # noqa: E731
    members, kinds = [], []
    for k in range(n - 1):
        members += [Member(k, k + 1, "bottom"), Member(t(k), t(k + 1), "top")]
        mid = (xs[k] + xs[k + 1]) / 2
        members.append(Member(t(k), k + 1, "diagonal") if mid < S / 2
                       else Member(t(k + 1), k, "diagonal"))
    for k in range(n):
        members.append(Member(k, t(k), "vertical"))
    loads = np.zeros_like(nodes)
    for k in range(n):
        left = xs[k] - xs[k - 1] if k > 0 else 0.0
        right = xs[k + 1] - xs[k] if k < n - 1 else 0.0
        loads[t(k), 1] = -spec.q_kN_m * (left + right) / 2
    return Truss(nodes, members, {0: (True, True), n - 1: (False, True)}, loads), xs


@pytest.fixture(scope="module")
def cat():
    return LadderCatalogue(LadderSpec(), synthetic_inventory(200, seed=2))


def test_compositions_close_exactly():
    comps = compositions(40, (4, 5, 6, 7, 8))
    assert len(comps) == 14063
    assert all(sum(c) == 40 for c in comps)


def test_envelope_bounds_method_of_joints(cat):
    rng = np.random.default_rng(0)
    comps = compositions(40, cat.spec.widths_u)
    for i in rng.choice(len(comps), 300, replace=False):
        comp = comps[i]
        tr, xs = layout_truss(comp, cat.spec)
        f, _ = solve_member_forces(tr)
        u = np.round(xs / UNIT).astype(int)
        for m, force in zip(tr.members, f):
            if m.kind == "vertical":
                s = cat.slots[cat.index[("V", u[m.i])]]
            else:
                k = min(m.i % len(xs), m.j % len(xs))
                key = {"bottom": "B", "top": "T", "diagonal": "D"}[m.kind]
                s = cat.slots[cat.index[(key, u[k], u[k + 1] - u[k])]]
            if force >= 0:
                assert force <= s.tension_kN + 1e-6, (comp, m, force)
            else:
                assert -force <= s.compression_kN + 1e-6, (comp, m, force)


@pytest.mark.parametrize("make", [LadderRule, LadderBufferedRule, lambda: LadderLookAhead(4)])
def test_episodes_close_span_and_respect_bound(cat, make):
    for k in range(3):
        rng = np.random.default_rng(k)
        batch = sample_batch(len(cat.problem.pieces), 40, rng)
        res = run_ladder_episode(cat, random_order(batch, rng), make(), 3, seed=k)
        assert sum(res.panels) == pytest.approx(4.0)
        assert ladder_offline(cat, batch).new_timber_m <= res.new_timber_m + 1e-9
