import numpy as np
import pytest

from stream_sim import random_order, sample_batch, synthetic_inventory
from stream_sim.frame import (FrameLookAhead, FrameModel, FrameWindowRule,
                              frame_offline, run_frame_episode, truss_forces)
from stream_sim.structure import Member, Truss, solve_member_forces


def test_stiffness_matches_method_of_joints_on_determinate_truss():
    pos = np.array([[0.0, 0.0], [2.0, 0.0], [1.0, 1.0]])
    members = [(0, 1), (0, 2), (1, 2)]
    loads = np.zeros((3, 2))
    loads[2] = (3.0, -10.0)
    f = truss_forces(pos, members, {0: (0, 1), 1: (1,)}, loads)
    tr = Truss(pos, [Member(a, b, "x") for a, b in members], {0: (True, True), 1: (False, True)}, loads)
    f_ref, _ = solve_member_forces(tr)
    assert f == pytest.approx(f_ref, abs=1e-6)


@pytest.fixture(scope="module")
def models():
    inv = synthetic_inventory(200, seed=4)
    return FrameModel(inv, True, n_samples=60), FrameModel(inv, False)


def test_topology(models):
    fo, ff = models
    assert fo.M == 56 and len(fo.nodes) == 25
    assert all(len(c) == 1 for c in ff.cands)
    assert (fo.dt >= ff.dt - 1e-9).all() and (fo.dc >= ff.dc - 1e-9).all()  # envelope >= nominal


@pytest.mark.parametrize("make", [FrameWindowRule, lambda: FrameLookAhead(2, 1, 10)])
def test_episodes(models, make):
    fo, ff = models
    rng = np.random.default_rng(1)
    batch = sample_batch(200, 90, rng)
    stream = random_order(batch, rng)
    for fm in (ff, fo):
        r = run_frame_episode(fm, stream, make(), 4, seed=0)  # asserts window size internally
        assert 0 <= r.reclaimed_share <= 1
        if not fm.open:
            assert r.violations == 0 and r.max_node_shift_m == 0


def test_fixed_offline_is_lower_bound(models):
    _, ff = models
    rng = np.random.default_rng(2)
    batch = sample_batch(200, 70, rng)
    off = frame_offline(ff, batch)
    on = run_frame_episode(ff, random_order(batch, rng), FrameWindowRule(), 4)
    assert off.new_timber_m <= on.new_timber_m + 1e-9
