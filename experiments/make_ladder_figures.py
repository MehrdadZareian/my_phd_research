"""Figures and summary for results/ladder/runs.csv."""

from __future__ import annotations

import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

RES = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parents[1] / "results" / "ladder"
SURFACE, INK, INK2, GRID, GRAY = "#fcfcfb", "#0b0b0b", "#52514e", "#e4e3df", "#8a8984"
COL = {"rule (tight fit + geometry)": "#eb6834", "buffered rule": "#1baf7a",
       "look-ahead": "#eda100", "offline optimum": GRAY}
ROWS = [("fixed design", "rule (tight fit + geometry)", "Fixed design · tight-fit rule"),
        ("fixed design", "look-ahead", "Fixed design · look-ahead"),
        ("fixed design", "offline optimum", "Fixed design · offline optimum"),
        ("open geometry", "rule (tight fit + geometry)", "Open geometry · greedy rule"),
        ("open geometry", "buffered rule", "Open geometry · buffered rule"),
        ("open geometry", "look-ahead", "Open geometry · look-ahead"),
        ("open geometry", "offline optimum", "Open geometry · offline optimum")]

plt.rcParams.update({
    "figure.facecolor": SURFACE, "axes.facecolor": SURFACE, "savefig.facecolor": SURFACE,
    "axes.edgecolor": GRID, "axes.labelcolor": INK2, "xtick.color": INK2, "ytick.color": INK2,
    "text.color": INK, "font.size": 10, "axes.spines.top": False, "axes.spines.right": False,
    "axes.grid": True, "grid.color": GRID, "axes.axisbelow": True, "hatch.color": SURFACE,
})


def ci(x):
    x = np.asarray(x, float)
    return 1.96 * x.std(ddof=1) / np.sqrt(len(x)) if len(x) > 1 else 0.0


def sel(d, design, policy):
    return d[(d.design == design) & (d.policy == policy)]


def fig_main(df):
    d = df[df.experiment == "main"]
    fig, axes = plt.subplots(1, 2, figsize=(10.5, 4.2), sharey=True)
    for ax, order, title in zip(axes, ["random", "batch"], ["Random arrival order", "Batch arrival order (by source)"]):
        dd = d[d.order == order]
        y = np.arange(len(ROWS))[::-1]
        m = [sel(dd, a, b).new_timber_m.mean() for a, b, _ in ROWS]
        e = [ci(sel(dd, a, b).new_timber_m) for a, b, _ in ROWS]
        bars = ax.barh(y, m, xerr=e, height=0.62, color=[COL[b] for _, b, _ in ROWS],
                       error_kw=dict(ecolor=INK2, lw=1, capsize=3))
        for bar, (a, _, _) in zip(bars, ROWS):
            if a == "fixed design":
                bar.set_hatch("///")
        for yi, mi, ei in zip(y, m, e):
            ax.text(mi + ei + 0.12, yi, f"{mi:.2f} m", va="center", fontsize=9)
        ax.set_yticks(y, [r[2] for r in ROWS])
        ax.axhline(3.5, color=GRID, lw=1)
        ax.set_xlim(0, max(a + b for a, b in zip(m, e)) * 1.3 + 0.1)
        ax.set_title(title, loc="left", fontsize=10.5)
        ax.set_xlabel("New timber needed per component (m)")
        ax.grid(axis="y", visible=False)
    n = sel(d[d.order == "random"], "open geometry", "look-ahead").shape[0]
    fig.suptitle("Open geometry: new timber per 4 m ladder truss", x=0.01, ha="left", fontsize=12)
    fig.text(0.01, -0.03, f"Mean of {n} streams, 95 % CI. 45 pieces per batch, buffer 3, 15 % best class. "
             "Fixed design = 8 × 0.5 m panels chosen in advance (hatched). SYNTHETIC inventory.",
             color=INK2, fontsize=8.5)
    fig.tight_layout()
    fig.savefig(RES / "fig_ladder_main.png", dpi=180, bbox_inches="tight")
    plt.close(fig)


def fig_sweep(df, param, xlabel, fname, title, fmt):
    d = df[(df.experiment == f"sweep_{param}") | ((df.experiment == "main") & (df.order == "random"))]
    xs = sorted(d[param].unique())
    pos = np.arange(len(xs), dtype=float)
    fig, ax = plt.subplots(figsize=(6.6, 4.8))
    lines = [("fixed design", "rule (tight fit + geometry)", "Fixed design · tight-fit rule", "s", "--"),
             ("open geometry", "rule (tight fit + geometry)", "Open geometry · greedy rule", "s", "-"),
             ("open geometry", "buffered rule", "Open geometry · buffered rule", "^", "-"),
             ("open geometry", "look-ahead", "Open geometry · look-ahead", "D", "-"),
             ("open geometry", "offline optimum", "Open geometry · offline optimum", "x", "--")]
    for i, (a, b, lab, mk, ls) in enumerate(lines):
        ys = [sel(d[d[param] == x], a, b).new_timber_m.mean() for x in xs]
        ax.plot(pos + (i - 2) * 0.05, ys, color=COL[b], marker=mk, ls=ls, lw=2, ms=7,
                mec=COL[b] if mk == "x" else SURFACE, mew=1.2, label=lab, alpha=0.75 if a == "fixed design" else 1)
    ax.set_xticks(pos, [fmt(x) for x in xs])
    ax.set_xlabel(xlabel)
    ax.set_ylabel("New timber per component (m)")
    ax.set_title(title, loc="left", fontsize=11)
    ax.set_ylim(bottom=0)
    ax.legend(frameon=False, fontsize=8.5, loc="upper center", bbox_to_anchor=(0.5, -0.17), ncol=2)
    ax.text(-0.12, -0.55, "Means over 40–60 streams per point, random order. SYNTHETIC inventory.",
            transform=ax.transAxes, color=INK2, fontsize=8)
    fig.tight_layout()
    fig.savefig(RES / fname, dpi=180, bbox_inches="tight")
    plt.close(fig)


def summary(df):
    L = ["# Ladder (open geometry) results — synthetic inventory", ""]
    d = df[df.experiment == "main"]
    L += ["| Order | Design | Policy | New timber (m) | ±95 % CI | Reclaimed share | Waste (m) | Components with any new timber |",
          "|---|---|---|---|---|---|---|---|"]
    for o in ("random", "batch"):
        for a, b, _ in ROWS:
            x = sel(d[d.order == o], a, b)
            L.append(f"| {o} | {a} | {b} | {x.new_timber_m.mean():.2f} | {ci(x.new_timber_m):.2f} | "
                     f"{100 * x.reclaimed_share.mean():.1f} % | {x.waste_m.mean():.1f} | "
                     f"{100 * (x.new_timber_m > 1e-9).mean():.0f} % |")
    for o in ("random", "batch"):
        dd = d[d.order == o]
        r = sel(dd, "open geometry", "rule (tight fit + geometry)").sort_values("stream").new_timber_m.values
        la = sel(dd, "open geometry", "look-ahead").sort_values("stream").new_timber_m.values
        df_ = r - la
        L += ["", f"Paired ({o}): greedy rule minus look-ahead = {df_.mean():.2f} ± {ci(df_):.2f} m; "
              f"look-ahead better in {(df_ > 1e-9).sum()} of {len(df_)} streams, worse in {(df_ < -1e-9).sum()}."]
    for param in ("best_fraction", "batch_size"):
        dp = df[(df.experiment == f"sweep_{param}") | ((df.experiment == "main") & (df.order == "random"))]
        L += ["", f"## Sweep: {param} (random order)", "",
              f"| {param} | fixed · rule | open · rule | open · buffered | open · look-ahead | open · offline |",
              "|---|---|---|---|---|---|"]
        for v in sorted(dp[param].unique()):
            dv = dp[dp[param] == v]
            vals = [sel(dv, "fixed design", "rule (tight fit + geometry)"), sel(dv, "open geometry", "rule (tight fit + geometry)"),
                    sel(dv, "open geometry", "buffered rule"), sel(dv, "open geometry", "look-ahead"),
                    sel(dv, "open geometry", "offline optimum")]
            L.append(f"| {v:g} | " + " | ".join(f"{x.new_timber_m.mean():.2f}" for x in vals) + " |")
    (RES / "summary.md").write_text("\n".join(L) + "\n")
    print("\n".join(L))


def main():
    df = pd.read_csv(RES / "runs.csv")
    fig_main(df)
    fig_sweep(df, "best_fraction", "Share of best-class pieces", "fig_ladder_scarcity.png",
              "Open geometry under scarcity", lambda v: f"{v:.0%}")
    fig_sweep(df, "batch_size", "Pieces per batch", "fig_ladder_supply.png",
              "Open geometry vs supply volume", lambda v: f"{v:g}")
    summary(df)


if __name__ == "__main__":
    main()
