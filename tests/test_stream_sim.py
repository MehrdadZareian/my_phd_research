import numpy as np
import pytest

from stream_sim import (BufferedTightFit, Greedy, LookAhead, TightFit,
                        build_problem, make_slots, offline_bound, pratt_truss,
                        random_order, run_episode, sample_batch,
                        solve_member_forces, synthetic_inventory)
from stream_sim.inventory import Piece, batch_order, load_inventory_json
from stream_sim.structure import Member, Truss, capacities


# --- Structure --------------------------------------------------------------

def test_single_triangle_method_of_joints():
    # Symmetric triangle, span 2, height 1, 10 kN down at apex.
    nodes = np.array([[0.0, 0.0], [2.0, 0.0], [1.0, 1.0]])
    members = [Member(0, 1, "bottom"), Member(0, 2, "top"), Member(1, 2, "top")]
    loads = np.zeros((3, 2))
    loads[2, 1] = -10.0
    tr = Truss(nodes, members, {0: (True, True), 1: (False, True)}, loads)
    f, r = solve_member_forces(tr)
    # Hand calculation: rafters -5*sqrt(2) kN (compression), tie +5 kN.
    assert f[0] == pytest.approx(5.0)
    assert f[1] == pytest.approx(-5.0 * np.sqrt(2))
    assert f[2] == pytest.approx(-5.0 * np.sqrt(2))
    assert r == pytest.approx([0.0, 5.0, 5.0])


def test_pratt_truss_equilibrium_and_symmetry():
    tr = pratt_truss(span=4.0, height=0.6, panels=8, node_load_kN=4.0)
    f, r = solve_member_forces(tr)
    assert r.sum() == pytest.approx(-tr.loads[:, 1].sum())
    bottom = f[:8]
    top = f[8:16]
    assert np.all(bottom >= -1e-9) and np.all(top <= 1e-9)  # tie in tension, top in compression
    assert bottom == pytest.approx(bottom[::-1])
    # Beam analogy: chord force ~ M / h. Nine 4 kN loads at 0.5 m spacing,
    # reaction 18 kN; moment at x = 1.5 m (panel point governing the central
    # Pratt bottom chord) = 18*1.5 - 4*(1.5 + 1.0 + 0.5) = 15 kNm.
    assert bottom.max() == pytest.approx(15.0 / 0.6)


def test_mechanism_is_rejected():
    tr = pratt_truss(panels=4)
    tr.members = [m for m in tr.members if m.kind != "diagonal"]
    with pytest.raises(ValueError):
        solve_member_forces(tr)


def test_capacities_monotone():
    t1, c1 = capacities(45, 70, 1, 0.5)
    t2, c2 = capacities(45, 70, 2, 0.5)
    assert t2 > t1 and c2 > c1
    _, c_long = capacities(45, 70, 2, 1.5)
    assert c_long < c2  # buckling
    assert capacities(45, 70, 0, 0.5) == (0.0, 0.0)


# --- Simulation -------------------------------------------------------------

@pytest.fixture(scope="module")
def problem():
    slots = make_slots(pratt_truss(node_load_kN=4.5))
    inv = synthetic_inventory(300, best_fraction=0.15, seed=3)
    return build_problem(inv, slots)


ALL = [Greedy, TightFit, BufferedTightFit, lambda: LookAhead(n_scenarios=4)]


@pytest.mark.parametrize("make", ALL)
@pytest.mark.parametrize("B", [0, 2])
def test_actions_valid_and_offline_is_lower_bound(problem, make, B):
    for k in range(4):
        rng = np.random.default_rng(k)
        batch = sample_batch(len(problem.pieces), 35, rng)
        stream = random_order(batch, rng)
        res = run_episode(problem, stream, make(), B, seed=k)  # raises on invalid action / buffer overflow
        off = offline_bound(problem, batch)
        assert off.new_timber_m <= res.new_timber_m + 1e-9
        assert 0.0 <= res.reclaimed_share <= 1.0


def test_lookahead_never_sees_the_future(problem):
    """Same prefix, different suffix (same length): decisions on the prefix must match."""
    rng = np.random.default_rng(7)
    batch = sample_batch(len(problem.pieces), 60, rng)
    prefix, rest = batch[:20], batch[20:]
    other = np.setdiff1d(np.arange(len(problem.pieces)), batch)[:40]
    s1 = np.concatenate([prefix, rest])
    s2 = np.concatenate([prefix, rng.permutation(other)])
    r1 = run_episode(problem, s1, LookAhead(n_scenarios=4), 3, seed=1, record=True)
    r2 = run_episode(problem, s2, LookAhead(n_scenarios=4), 3, seed=1, record=True)
    a1 = [a for a in r1.actions if a[0] < 20]
    a2 = [a for a in r2.actions if a[0] < 20]
    assert a1 == a2


def test_buffer_helps_buffered_policies_on_average(problem):
    diffs = []
    for k in range(10):
        rng = np.random.default_rng(100 + k)
        batch = sample_batch(len(problem.pieces), 35, rng)
        st = random_order(batch, rng)
        a = run_episode(problem, st, BufferedTightFit(), 0, seed=k).new_timber_m
        b = run_episode(problem, st, BufferedTightFit(), 6, seed=k).new_timber_m
        diffs.append(a - b)
    assert np.mean(diffs) >= 0


def test_batch_order_is_permutation(problem):
    rng = np.random.default_rng(0)
    batch = sample_batch(len(problem.pieces), 40, rng)
    order = batch_order(batch, problem.pieces, rng)
    assert sorted(order.tolist()) == sorted(batch.tolist())


def test_json_loader(tmp_path):
    p = tmp_path / "inv.json"
    p.write_text('[{"id": "MZ-001", "length_mm": 1450, "section": "45x70", "quality": "best"},'
                 ' {"label": "WI-7", "length": 0.9, "width": 60, "height": 40, "class": 1}]')
    pcs = load_inventory_json(p)
    assert pcs[0] == Piece("MZ-001", 1.45, 45, 70, 2, "MZ")
    assert pcs[1].b == 40 and pcs[1].h == 60 and pcs[1].quality == 1 and pcs[1].source == "WI"
