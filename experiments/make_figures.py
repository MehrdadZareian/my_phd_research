"""Make figures and a summary table from results/runs.csv."""

from __future__ import annotations

import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

RES = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parents[1] / "results"

SURFACE = "#fcfcfb"
INK = "#0b0b0b"
INK2 = "#52514e"
GRID = "#e4e3df"
OFFLINE = "#8a8984"
# Categorical slots 1-4 of the reference palette, fixed order (validated).
STYLE = {
    "greedy": ("#2a78d6", "o", "Greedy (first fit)"),
    "tight fit (rule)": ("#eb6834", "s", "Tight-fit rule"),
    "buffered tight fit": ("#1baf7a", "^", "Buffered tight fit"),
    "look-ahead": ("#eda100", "D", "Look-ahead (this project)"),
}
ORDER = list(STYLE)

plt.rcParams.update({
    "figure.facecolor": SURFACE, "axes.facecolor": SURFACE, "savefig.facecolor": SURFACE,
    "axes.edgecolor": GRID, "axes.labelcolor": INK2, "xtick.color": INK2, "ytick.color": INK2,
    "text.color": INK, "font.size": 10, "axes.spines.top": False, "axes.spines.right": False,
    "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.8, "axes.axisbelow": True,
})


def ci95(x):
    x = np.asarray(x, float)
    return 1.96 * x.std(ddof=1) / np.sqrt(len(x)) if len(x) > 1 else 0.0


def gap_closed(df_cfg, policy):
    g = df_cfg[df_cfg.policy == "greedy"].new_timber_pct.mean()
    o = df_cfg[df_cfg.policy == "offline optimum"].new_timber_pct.mean()
    p = df_cfg[df_cfg.policy == policy].new_timber_pct.mean()
    return np.nan if g - o < 1e-9 else 100 * (g - p) / (g - o)


def fig_main(df):
    d = df[df.experiment == "main"]
    pols = ORDER + ["offline optimum"]
    fig, axes = plt.subplots(1, 2, figsize=(10, 3.8), sharey=True)
    for ax, order, title in zip(axes, ["random", "batch"],
                                ["Random arrival order", "Batch arrival order (by source)"]):
        dd = d[d.order == order]
        means = [dd[dd.policy == p].new_timber_pct.mean() for p in pols]
        errs = [ci95(dd[dd.policy == p].new_timber_pct) for p in pols]
        colors = [STYLE[p][0] if p in STYLE else OFFLINE for p in pols]
        y = np.arange(len(pols))[::-1]
        ax.barh(y, means, xerr=errs, color=colors, height=0.6,
                error_kw=dict(ecolor=INK2, lw=1, capsize=3))
        for yi, m, e in zip(y, means, errs):
            ax.text(m + e + 0.2, yi, f"{m:.1f} %", va="center", color=INK, fontsize=9)
        ax.set_yticks(y, [STYLE[p][2] if p in STYLE else "Offline optimum (knows the future)" for p in pols])
        ax.set_title(title, loc="left", color=INK, fontsize=10.5)
        ax.set_xlabel("New timber needed (% of required member length)")
        ax.grid(axis="y", visible=False)
        ax.set_xlim(0, max(m + e for m, e in zip(means, errs)) * 1.25 + 0.5)
    n = d[d.policy == "greedy"].groupby("order").size().min()
    fig.suptitle("Cost of not knowing: new timber per component", x=0.01, ha="left",
                 fontsize=12, color=INK)
    fig.text(0.01, -0.02, f"Mean of {n} streams per order, 95 % CI. Buffer 3 pieces, supply 1.5× slots, "
             "15 % best-class. SYNTHETIC inventory.", color=INK2, fontsize=8.5)
    fig.tight_layout()
    fig.savefig(RES / "fig1_main.png", dpi=180, bbox_inches="tight")
    plt.close(fig)


def fig_sweep(df, param, xlabel, fname, title, fmt=lambda v: f"{v:g}"):
    d = df[df.experiment == f"sweep_{param}"]
    xs = sorted(d[param].unique())
    fig, ax = plt.subplots(figsize=(6.4, 3.9))
    pos = np.arange(len(xs), dtype=float)  # evenly spaced categories
    # Small horizontal dodge so that policies with equal results stay visible.
    dodge = dict(zip(ORDER + ["offline optimum"], np.linspace(-0.12, 0.12, len(ORDER) + 1)))
    off = [d[(d[param] == x) & (d.policy == "offline optimum")].new_timber_pct.mean() for x in xs]
    ax.plot(pos + dodge["offline optimum"], off, color=OFFLINE, lw=2, ls="--", marker="x", ms=6,
            label="Offline optimum (knows the future)", zorder=2)
    for p in ORDER:
        c, m, lab = STYLE[p]
        ys = [d[(d[param] == x) & (d.policy == p)].new_timber_pct.mean() for x in xs]
        ax.plot(pos + dodge[p], ys, color=c, lw=2, marker=m, ms=7, mec=SURFACE, mew=1.5, label=lab, zorder=3)
    ax.set_xticks(pos, [fmt(x) for x in xs])
    ax.set_xlabel(xlabel)
    ax.set_ylabel("New timber (% of required length)")
    ax.set_title(title, loc="left", color=INK, fontsize=11)
    ax.legend(frameon=False, fontsize=8.5, loc="upper center", bbox_to_anchor=(0.5, -0.25), ncol=3)
    ax.set_ylim(bottom=0)
    n = d[d.policy == "greedy"].groupby(param).size().min()
    ax.text(-0.12, -0.7, f"Mean of {n} streams per point. Other settings as in Fig. 1. SYNTHETIC inventory.",
            transform=ax.transAxes, color=INK2, fontsize=8)
    fig.tight_layout()
    fig.savefig(RES / fname, dpi=180, bbox_inches="tight")
    plt.close(fig)


def summary(df):
    lines = ["# Results summary (synthetic inventory)", ""]
    d = df[df.experiment == "main"]
    lines += ["## Main comparison", "",
              "| Order | Policy | New timber (% of length) | ±95 % CI | Waste (m) | Discarded usable | Gap to offline closed vs greedy |",
              "|---|---|---|---|---|---|---|"]
    for order in ["random", "batch"]:
        dd = d[d.order == order]
        for p in ORDER + ["look-ahead (learned supply)", "look-ahead (hindsight)", "offline optimum"]:
            x = dd[dd.policy == p]
            if x.empty:
                continue
            gc = gap_closed(dd, p)
            lines.append(f"| {order} | {p} | {x.new_timber_pct.mean():.2f} | {ci95(x.new_timber_pct):.2f} | "
                         f"{x.waste_m.mean():.2f} | {x.discarded_usable.mean():.2f} | "
                         f"{'' if np.isnan(gc) else f'{gc:.0f} %'} |")
    for param in ["buffer", "best_fraction", "supply_ratio"]:
        d = df[df.experiment == f"sweep_{param}"]
        lines += ["", f"## Sweep: {param}", "",
                  "| " + param + " | " + " | ".join(ORDER + ["offline optimum"]) + " | look-ahead gap closed |",
                  "|" + "---|" * (len(ORDER) + 3)]
        for v in sorted(d[param].unique()):
            dv = d[d[param] == v]
            vals = [f"{dv[dv.policy == p].new_timber_pct.mean():.2f}" for p in ORDER + ["offline optimum"]]
            gc = gap_closed(dv, "look-ahead")
            lines.append(f"| {v:g} | " + " | ".join(vals) + f" | {'' if np.isnan(gc) else f'{gc:.0f} %'} |")
    # Paired comparison look-ahead vs tight fit (main, random).
    dd = df[(df.experiment == "main") & (df.order == "random")]
    a = dd[dd.policy == "tight fit (rule)"].sort_values("stream").new_timber_pct.values
    b = dd[dd.policy == "look-ahead"].sort_values("stream").new_timber_pct.values
    diff = a - b
    lines += ["", "## Paired difference (main, random order)", "",
              f"Tight-fit rule minus look-ahead: {diff.mean():.2f} ± {ci95(diff):.2f} percentage points "
              f"(look-ahead better in {np.sum(diff > 1e-9)} of {len(diff)} streams, worse in {np.sum(diff < -1e-9)})."]
    (RES / "summary.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))


def main():
    df = pd.read_csv(RES / "runs.csv")
    fig_main(df)
    fig_sweep(df, "buffer", "Buffer size (pieces kept for later)", "fig2_buffer.png",
              "What storage is worth")
    fig_sweep(df, "best_fraction", "Share of best-class pieces in the supply", "fig3_scarcity.png",
              "Where planning matters: scarcity of good pieces", fmt=lambda v: f"{v:.0%}")
    fig_sweep(df, "supply_ratio", "Pieces arriving per slot of the component", "fig4_supply.png",
              "Effect of supply volume", fmt=lambda v: f"{v:g}×")
    summary(df)


if __name__ == "__main__":
    main()
