"""Figures and summary for results/real_frame/ (real MZ/WI inventory)."""

from __future__ import annotations

import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from matplotlib.lines import Line2D  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "experiments"))
from run_real_frame import model  # noqa: E402
from stream_sim.frame import ALLOW, FrameLookAhead, run_frame_episode  # noqa: E402
from stream_sim.model import CUT_TOL  # noqa: E402

RES = ROOT / "results" / "real_frame"
SURFACE, INK, INK2, GRID, GRAY = "#fcfcfb", "#0b0b0b", "#52514e", "#e4e3df", "#8a8984"
POL = [("window rule", "#eb6834", "s", "Window rule"),
       ("window look-ahead (learned supply)", "#e87ba4", "o", "Look-ahead, learned supply"),
       ("window look-ahead", "#eda100", "D", "Look-ahead, knows inventory statistics"),
       ("offline plan", GRAY, "x", "Offline plan (all boards known)")]
plt.rcParams.update({
    "figure.facecolor": SURFACE, "axes.facecolor": SURFACE, "savefig.facecolor": SURFACE,
    "axes.edgecolor": GRID, "axes.labelcolor": INK2, "xtick.color": INK2, "ytick.color": INK2,
    "text.color": INK, "font.size": 10, "axes.spines.top": False, "axes.spines.right": False,
    "axes.grid": True, "grid.color": GRID, "axes.axisbelow": True,
})


def ci(x):
    x = np.asarray(x, float)
    return 1.96 * x.std(ddof=1) / np.sqrt(len(x)) if len(x) > 1 else 0.0


def curves(d):
    boxes = sorted(d.box_m.unique())
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.4))
    for ax, col, lab, scale in ((axes[0], "reclaimed_share", "Reclaimed share of member length (%)", 100),
                                (axes[1], "cuts", "Cuts (of 56 members)", 1)):
        for i, (p, c, mk, name) in enumerate(POL):
            m = [scale * d[(d.box_m == b) & (d.policy == p)][col].mean() for b in boxes]
            e = [scale * ci(d[(d.box_m == b) & (d.policy == p)][col]) for b in boxes]
            ax.errorbar(np.array(boxes) * 100 + (i - 1.5) * 0.35, m, yerr=e, color=c, marker=mk, ms=7,
                        lw=2, capsize=2, mec=c if mk == "x" else SURFACE, label=name,
                        ls="--" if p == "offline plan" else "-")
        ax.set_xticks(np.array(boxes) * 100, ["0 (fixed design)" if b == 0 else f"±{b * 100:.0f}" for b in boxes])
        ax.set_xlabel("How far each node may move (cm)")
        ax.set_title(lab, loc="left", fontsize=10.5)
    h, l_ = axes[0].get_legend_handles_labels()
    fig.legend(h, l_, frameon=False, ncol=4, fontsize=9, loc="lower center", bbox_to_anchor=(0.5, -0.07))
    n = d.groupby(["box_m", "policy"]).size().min()
    fig.suptitle("Real MZ/WI inventory (80 boards), 2 × 2 m panel: more node freedom, more reclaimed wood",
                 x=0.01, ha="left", fontsize=12)
    fig.text(0.01, -0.13, f"Mean of {n} random arrival orders of all 80 boards, 95 % CI, 5-piece window. "
             "No quality grades in the data (all 'standard'); loads and capacities are placeholders.",
             color=INK2, fontsize=8.5)
    fig.tight_layout()
    fig.savefig(RES / "fig_real_freedom.png", dpi=180, bbox_inches="tight")
    plt.close(fig)


def drawing():
    k = 0
    rng = np.random.default_rng(200_000 + k)
    fig, axes = plt.subplots(1, 3, figsize=(14, 5.4))
    for ax, box in zip(axes, (0.0, 0.10, 0.15)):
        fm = model(box)
        stream = rng.permutation(len(fm.pieces)) if box == 0.0 else stream
        r, s = run_frame_episode(fm, stream, FrameLookAhead(6, 2, 30, supply="observed"), 4, seed=k,
                                 return_state=True)
        pos = s["pos"]
        who = {m: p for p, m in s["placed"]}
        for m, (a, b) in enumerate(fm.members):
            if m not in who:
                c = "#e34948"
            else:
                c = "#2a78d6" if fm.Lp[who[m]] - s["lengths"][m] - 2 * ALLOW > CUT_TOL else "#1baf7a"
            ax.plot(*zip(pos[a], pos[b]), color=c, lw=3.2, solid_capstyle="round", zorder=2)
        ax.scatter(fm.nominal[:, 0], fm.nominal[:, 1], s=14, facecolor="none", edgecolor=GRAY, zorder=1)
        ax.scatter(pos[:, 0], pos[:, 1], s=24, color=INK, zorder=3)
        ax.set_aspect("equal")
        ax.set_xlim(-0.2, 2.2)
        ax.set_ylim(-0.2, 2.2)
        ax.axis("off")
        ax.set_title("Fixed design" if box == 0 else f"Nodes may move ±{box * 100:.0f} cm", loc="left", fontsize=10.5)
        ax.text(0, -0.17, f"reclaimed {100 * r.reclaimed_share:.0f} % · new timber {r.new_timber_m:.1f} m · "
                f"cuts {r.cuts}", fontsize=9, color=INK2)
    h = [Line2D([], [], color="#1baf7a", lw=3, label="Reclaimed board, no cut"),
         Line2D([], [], color="#2a78d6", lw=3, label="Reclaimed board, cut"),
         Line2D([], [], color="#e34948", lw=3, label="New timber"),
         Line2D([], [], marker="o", ls="", markerfacecolor="none", markeredgecolor=GRAY, label="Nominal node")]
    fig.legend(handles=h, frameon=False, ncol=4, loc="lower center", fontsize=9, bbox_to_anchor=(0.5, -0.01))
    fig.suptitle("Real inventory, same arrival order, look-ahead with learned supply", x=0.01, ha="left", fontsize=12)
    fig.tight_layout(rect=(0, 0.05, 1, 1))
    fig.savefig(RES / "fig_real_example.png", dpi=180, bbox_inches="tight")
    plt.close(fig)


def summary(d):
    L = ["# 2 × 2 m panel on the real MZ/WI inventory", "",
         "| Node freedom | Strategy | Reclaimed share | New timber (m) | Cuts | Offcut (m) | Violations |",
         "|---|---|---|---|---|---|---|"]
    for b in sorted(d.box_m.unique()):
        for p, *_ in POL:
            x = d[(d.box_m == b) & (d.policy == p)]
            L.append(f"| {'fixed' if b == 0 else f'±{b * 100:.0f} cm'} | {p} | "
                     f"{100 * x.reclaimed_share.mean():.1f} ± {100 * ci(x.reclaimed_share):.1f} % | "
                     f"{x.new_timber_m.mean():.2f} | {x.cuts.mean():.1f} | {x.waste_m.mean():.1f} | {x.violations.sum()} |")
    L.append("")
    for b in sorted(d.box_m.unique()):
        dd = d[d.box_m == b]
        r = dd[dd.policy == "window rule"].sort_values("stream").new_timber_m.values
        for p in ("window look-ahead (learned supply)", "window look-ahead"):
            x = dd[dd.policy == p].sort_values("stream").new_timber_m.values
            df = r - x
            L.append(f"- {b * 100:.0f} cm, rule − {p}: {df.mean():+.2f} ± {ci(df):.2f} m new timber "
                     f"(better {(df > 1e-9).sum()}, worse {(df < -1e-9).sum()} of {len(df)})")
    (RES / "summary.md").write_text("\n".join(L) + "\n")
    print("\n".join(L))


if __name__ == "__main__":
    d = pd.read_csv(RES / "runs.csv")
    curves(d)
    drawing()
    summary(d)
