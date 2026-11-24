"""Figure and summary for results/adversarial/runs.csv."""

from __future__ import annotations

import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

RES = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parents[1] / "results" / "adversarial"
SURFACE, INK, INK2, GRID, GRAY = "#fcfcfb", "#0b0b0b", "#52514e", "#e4e3df", "#8a8984"
POL = [("greedy rule", "#eb6834", "Greedy rule"), ("buffered rule", "#1baf7a", "Buffered rule"),
       ("look-ahead", "#eda100", "Look-ahead"),
       ("look-ahead (learned supply)", "#e87ba4", "Look-ahead, learned supply"),
       ("offline optimum", GRAY, "Offline optimum")]
plt.rcParams.update({
    "figure.facecolor": SURFACE, "axes.facecolor": SURFACE, "savefig.facecolor": SURFACE,
    "axes.edgecolor": GRID, "axes.labelcolor": INK2, "xtick.color": INK2, "ytick.color": INK2,
    "text.color": INK, "font.size": 10, "axes.spines.top": False, "axes.spines.right": False,
    "axes.grid": True, "grid.color": GRID, "axes.axisbelow": True,
})


def ci(x):
    x = np.asarray(x, float)
    return 1.96 * x.std(ddof=1) / np.sqrt(len(x)) if len(x) > 1 else 0.0


def val(d, exp, order, pol):
    x = d[(d.experiment == exp) & (d.policy == pol) & ((d.order == order) | (pol == "offline optimum"))]
    if x.empty:
        return np.nan, np.nan, 0
    return x.new_timber_m.mean(), ci(x.new_timber_m), len(x)


def main():
    d = pd.read_csv(RES / "runs.csv")
    groups = [("structured", "random", "Random order"),
              ("structured", "long first", "Long pieces first"),
              ("structured", "short first", "Short pieces first"),
              ("structured", "best class first", "Best class first"),
              ("structured", "best class last", "Best class last"),
              ("search", "random", "Random order\n(search batches)"),
              ("search", "adversarial search", "Worst order found\nby search"),
              ("mismatch", "biased supply", "Misleading supply\n(mostly short pieces)")]
    fig, ax = plt.subplots(figsize=(12.5, 4.8))
    w = 0.16
    x = np.arange(len(groups))
    for i, (pol, col, lab) in enumerate(POL):
        m = np.array([val(d, e, o, pol)[0] for e, o, _ in groups])
        e = np.array([val(d, ex, o, pol)[1] for ex, o, _ in groups])
        ok = ~np.isnan(m)
        ax.bar((x + (i - 2) * w)[ok], m[ok], w * 0.92, yerr=e[ok], color=col, label=lab,
               error_kw=dict(ecolor=INK2, lw=0.8, capsize=2))
    ax.axvline(4.5, color=GRID, lw=1)
    ax.axvline(6.5, color=GRID, lw=1)
    ax.set_xticks(x, [g[2] for g in groups], fontsize=8.5)
    ax.set_ylabel("New timber per component (m)")
    ax.set_title("Adversarial tests: open-geometry ladder", loc="left", fontsize=12)
    ax.legend(frameon=False, ncol=5, loc="upper left", fontsize=9)
    ax.grid(axis="x", visible=False)
    ax.text(0, -0.3, "Bars: mean, 95 % CI. Structured and misleading-supply: 40 batches; search: 20 batches, "
            "25 search steps per strategy and batch. Offline optimum does not depend on order. SYNTHETIC inventory.",
            transform=ax.transAxes, color=INK2, fontsize=8)
    fig.tight_layout()
    fig.savefig(RES / "fig_adversarial.png", dpi=180, bbox_inches="tight")

    L = ["# Adversarial tests — open-geometry ladder (synthetic inventory)", "",
         "| Test | Greedy rule | Buffered rule | Look-ahead | Look-ahead (learned supply) | Offline optimum |",
         "|---|---|---|---|---|---|"]
    for e, o, lab in groups:
        cells = []
        for pol in ("greedy rule", "buffered rule", "look-ahead", "look-ahead (learned supply)", "offline optimum"):
            m, c, n = val(d, e, o, pol)
            cells.append("" if n == 0 else f"{m:.2f} ± {c:.2f}")
        L.append(f"| {lab.replace(chr(10), ' ')} | " + " | ".join(cells) + " |")
    s = d[d.experiment == "search"]
    L += ["", "Search adversary, increase from random to worst order found (m):"]
    for pol in ("greedy rule", "buffered rule", "look-ahead"):
        a = s[(s.policy == pol) & (s.order == "random")].sort_values("stream").new_timber_m.values
        b = s[(s.policy == pol) & (s.order == "adversarial search")].sort_values("stream").new_timber_m.values
        L.append(f"- {pol}: +{(b - a).mean():.2f} m (worst single batch {b.max():.2f} m)")
    (RES / "summary.md").write_text("\n".join(L) + "\n")
    print("\n".join(L))


if __name__ == "__main__":
    main()
