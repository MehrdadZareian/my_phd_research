"""Figures and summary for results/frame/ (run_frame.py must have run)."""

from __future__ import annotations

import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from stream_sim import sample_batch, synthetic_inventory  # noqa: E402
from stream_sim.frame import ALLOW, FrameLookAhead, FrameModel, run_frame_episode  # noqa: E402
from stream_sim.model import CUT_TOL  # noqa: E402

RES = ROOT / "results" / "frame"
SURFACE, INK, INK2, GRID, GRAY = "#fcfcfb", "#0b0b0b", "#52514e", "#e4e3df", "#8a8984"
COL = {"window rule": "#eb6834", "window look-ahead": "#eda100", "offline plan": GRAY}
LAB = {"window rule": "Window rule", "window look-ahead": "Window look-ahead",
       "offline plan": "Offline plan (exact for fixed, heuristic for floating)"}
plt.rcParams.update({
    "figure.facecolor": SURFACE, "axes.facecolor": SURFACE, "savefig.facecolor": SURFACE,
    "axes.edgecolor": GRID, "axes.labelcolor": INK2, "xtick.color": INK2, "ytick.color": INK2,
    "text.color": INK, "font.size": 10, "axes.spines.top": False, "axes.spines.right": False,
    "axes.grid": True, "grid.color": GRID, "axes.axisbelow": True,
})


def ci(x):
    x = np.asarray(x, float)
    return 1.96 * x.std(ddof=1) / np.sqrt(len(x)) if len(x) > 1 else 0.0


def bars(d):
    metrics = [("new_timber_m", "New timber (m)"), ("cuts", "Cuts (of 56 members)"), ("waste_m", "Offcut waste (m)")]
    groups = [(s, des) for s in (84, 140) for des in ("fixed nodes", "floating nodes")]
    pols = ["window rule", "window look-ahead", "offline plan"]
    fig, axes = plt.subplots(1, 3, figsize=(13, 4.2))
    x = np.arange(len(groups))
    for ax, (col, title) in zip(axes, metrics):
        for i, p in enumerate(pols):
            m = [d[(d.batch_size == s) & (d.design == g) & (d.policy == p)][col].mean() for s, g in groups]
            e = [ci(d[(d.batch_size == s) & (d.design == g) & (d.policy == p)][col]) for s, g in groups]
            ax.bar(x + (i - 1) * 0.26, m, 0.24, yerr=e, color=COL[p], label=LAB[p],
                   error_kw=dict(ecolor=INK2, lw=0.8, capsize=2))
        ax.set_xticks(x, [f"{g}\n{s} pieces" for s, g in groups], fontsize=8.5)
        ax.set_title(title, loc="left", fontsize=10.5)
        ax.grid(axis="x", visible=False)
    h, lab = axes[0].get_legend_handles_labels()
    fig.legend(h, lab, frameon=False, ncol=3, fontsize=9, loc="lower center", bbox_to_anchor=(0.5, -0.06))
    fig.suptitle("4 × 4 m panel: fixed nodes vs nodes that float with the material", x=0.01, ha="left", fontsize=12)
    n = d.groupby(["batch_size", "design", "policy"]).size().min()
    fig.text(0.01, -0.11, f"Mean of {n} streams, 95 % CI. 5-piece window, random order. SYNTHETIC inventory.",
             color=INK2, fontsize=8.5)
    fig.tight_layout()
    fig.savefig(RES / "fig_frame_metrics.png", dpi=180, bbox_inches="tight")
    plt.close(fig)


def drawing():
    inv = synthetic_inventory(400, best_fraction=0.15, seed=1)
    rng = np.random.default_rng(100_000 + 1000 * 84 + 3)
    batch = sample_batch(400, 84, rng)
    stream = rng.permutation(batch)
    fig, axes = plt.subplots(1, 2, figsize=(11, 5.6))
    for ax, open_g, title in zip(axes, (False, True), ("Fixed nodes (design before fabrication)",
                                                       "Floating nodes (geometry from the material)")):
        fm = FrameModel(inv, open_g)
        r, s = run_frame_episode(fm, stream, FrameLookAhead(6, 2, 30), 4, seed=3, return_state=True)
        pos = s["pos"]
        who = {m: p for p, m in s["placed"]}
        for m, (a, b) in enumerate(fm.members):
            xa, ya = pos[a]
            xb, yb = pos[b]
            if m not in who:
                ax.plot([xa, xb], [ya, yb], color="#e34948", lw=3.2, solid_capstyle="round", zorder=2)
            else:
                cut = fm.Lp[who[m]] - s["lengths"][m] - 2 * ALLOW > CUT_TOL
                ax.plot([xa, xb], [ya, yb], color="#2a78d6" if cut else "#1baf7a", lw=3.2,
                        solid_capstyle="round", zorder=2)
        ax.scatter(fm.nominal[:, 0], fm.nominal[:, 1], s=14, facecolor="none", edgecolor=GRAY, zorder=1)
        ax.scatter(pos[:, 0], pos[:, 1], s=26, color=INK, zorder=3)
        ax.set_aspect("equal")
        ax.set_xlim(-0.4, 4.4)
        ax.set_ylim(-0.4, 4.4)
        ax.grid(False)
        ax.set_xticks([])
        ax.set_yticks([])
        for sp in ax.spines.values():
            sp.set_visible(False)
        ax.set_title(title, loc="left", fontsize=10.5)
        ax.text(0, -0.32, f"new timber {r.new_timber_m:.1f} m · cuts {r.cuts} · offcut {r.waste_m:.1f} m",
                fontsize=9, color=INK2)
    from matplotlib.lines import Line2D
    h = [Line2D([], [], color="#1baf7a", lw=3, label="Reclaimed, no cut"),
         Line2D([], [], color="#2a78d6", lw=3, label="Reclaimed, cut"),
         Line2D([], [], color="#e34948", lw=3, label="New timber"),
         Line2D([], [], marker="o", ls="", markerfacecolor="none", markeredgecolor=GRAY, label="Nominal node")]
    fig.legend(handles=h, frameon=False, ncol=4, loc="lower center", fontsize=9, bbox_to_anchor=(0.5, -0.02))
    fig.suptitle("Same stream of 84 pieces, look-ahead, 5-piece window", x=0.01, ha="left", fontsize=12)
    fig.tight_layout(rect=(0, 0.05, 1, 1))
    fig.savefig(RES / "fig_frame_example.png", dpi=180, bbox_inches="tight")
    plt.close(fig)


def summary(d):
    L = ["# 4 × 4 m panel with floating nodes (synthetic inventory)", "",
         "| Pieces | Design | Strategy | New timber (m) | Cuts | Offcut (m) | Reclaimed share | Structural violations | Max node shift (m) |",
         "|---|---|---|---|---|---|---|---|---|"]
    for s in (84, 140):
        for g in ("fixed nodes", "floating nodes"):
            for p in ("window rule", "window look-ahead", "offline plan"):
                x = d[(d.batch_size == s) & (d.design == g) & (d.policy == p)]
                L.append(f"| {s} | {g} | {p} | {x.new_timber_m.mean():.2f} ± {ci(x.new_timber_m):.2f} | "
                         f"{x.cuts.mean():.1f} | {x.waste_m.mean():.1f} | {100 * x.reclaimed_share.mean():.1f} % | "
                         f"{x.violations.sum()} | {x.max_node_shift_m.mean():.2f} |")
    L.append("")
    for s in (84, 140):
        for g in ("fixed nodes", "floating nodes"):
            dd = d[(d.batch_size == s) & (d.design == g)]
            r = dd[dd.policy == "window rule"].sort_values("stream")
            la = dd[dd.policy == "window look-ahead"].sort_values("stream")
            for col in ("new_timber_m", "cuts", "waste_m"):
                diff = r[col].values - la[col].values
                L.append(f"- {s} pieces, {g}: rule − look-ahead {col} = {diff.mean():+.2f} ± {ci(diff):.2f} "
                         f"(look-ahead better {(diff > 1e-9).sum()}, worse {(diff < -1e-9).sum()} of {len(diff)})")
    (RES / "summary.md").write_text("\n".join(L) + "\n")
    print("\n".join(L))


if __name__ == "__main__":
    d = pd.read_csv(RES / "runs.csv")
    bars(d)
    drawing()
    summary(d)
