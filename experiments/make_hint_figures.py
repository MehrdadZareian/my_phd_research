"""Figure and summary for results/hints/runs.csv."""

from __future__ import annotations

import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

RES = Path(__file__).resolve().parents[1] / "results" / "hints"
SURFACE, INK, INK2, GRID, GRAY = "#fcfcfb", "#0b0b0b", "#52514e", "#e4e3df", "#8a8984"
plt.rcParams.update({
    "figure.facecolor": SURFACE, "axes.facecolor": SURFACE, "savefig.facecolor": SURFACE,
    "axes.edgecolor": GRID, "axes.labelcolor": INK2, "xtick.color": INK2, "ytick.color": INK2,
    "text.color": INK, "font.size": 10, "axes.spines.top": False, "axes.spines.right": False,
    "axes.grid": True, "grid.color": GRID, "axes.axisbelow": True,
})
# Colour = kind of information (categorical slots, fixed order).
KIND = {"rule": "#1baf7a", "none": "#eda100", "hint": "#2a78d6", "bound": "#7c5fc8", "storage": "#eb6834",
        "offline": GRAY}
ROWS_A = [
    ("buffered rule", "rule", "Buffered rule"),
    ("look-ahead, no hint", "none", "Look-ahead, no hint"),
    ("look-ahead, learned supply", "none", "Look-ahead, learns supply from arrivals"),
    ("hint wrong ('mostly long', 20 %)", "hint", "Hint wrong ('mostly long')"),
    ("hint wrong + update", "hint", "Hint wrong + revised from arrivals"),
    ("hint vague ('mostly short', 70 %)", "hint", "Hint vague ('mostly short', 70 %)"),
    ("hint vague + update", "hint", "Hint vague + revised from arrivals"),
    ("hint exaggerated (95 % short)", "hint", "Hint exaggerated (95 %)"),
    ("hint correct (85 % short)", "hint", "Hint correct (85 %)"),
    ("perfect supply model", "bound", "Perfect supply model (true distribution)"),
    ("clairvoyant look-ahead", "bound", "Clairvoyant: sees the actual future, buffer 3"),
    ("buffered rule, buffer 8", "storage", "Buffered rule, buffer 8"),
    ("look-ahead, no hint, buffer 8", "storage", "Look-ahead, no hint, buffer 8"),
    ("offline optimum", "offline", "Offline optimum"),
]


def ci(x):
    x = np.asarray(x, float)
    return 1.96 * x.std(ddof=1) / np.sqrt(len(x)) if len(x) > 1 else 0.0


def main():
    d = pd.read_csv(RES / "runs.csv")
    A = d[d.world == "A"]
    fig, ax = plt.subplots(figsize=(9, 5.6))
    y = np.arange(len(ROWS_A))[::-1]
    m = [A[A.policy == p].new_timber_m.mean() for p, _, _ in ROWS_A]
    e = [ci(A[A.policy == p].new_timber_m) for p, _, _ in ROWS_A]
    ax.barh(y, m, xerr=e, height=0.62, color=[KIND[k] for _, k, _ in ROWS_A],
            error_kw=dict(ecolor=INK2, lw=1, capsize=3))
    for yi, mi, ei in zip(y, m, e):
        ax.text(mi + ei + 0.12, yi, f"{mi:.2f}", va="center", fontsize=9)
    ax.set_yticks(y, [lab for _, _, lab in ROWS_A], fontsize=9)
    base = A[A.policy == "look-ahead, no hint"].new_timber_m.mean()
    ax.axvline(base, color=INK2, lw=1, ls=":")
    ax.set_xlabel("New timber per component (m)")
    ax.set_xlim(0, max(a + b for a, b in zip(m, e)) * 1.12)
    ax.grid(axis="y", visible=False)
    ax.set_title("Misleading supply (mostly short pieces): what helps?", loc="left", fontsize=12)
    ax.text(0, -0.2, "Mean of 40 batches, 95 % CI. Dotted line: look-ahead without hint. "
            "Colours: green rule · yellow no hint · blue human hint · violet reference bounds · "
            "orange more storage · grey offline. SYNTHETIC inventory.",
            transform=ax.transAxes, color=INK2, fontsize=7.8, wrap=True)
    fig.tight_layout()
    fig.savefig(RES / "fig_hints.png", dpi=180, bbox_inches="tight")

    L = ["# Human supply hints — open-geometry ladder (synthetic inventory)", ""]
    for world, title in (("A", "World A: misleading supply (true short share ≈ 0.8, source statistics say 0.34)"),
                         ("B", "World B: normal supply (true short share ≈ 0.35)")):
        dw = d[d.world == world]
        base = dw[dw.policy == "look-ahead, no hint"].sort_values("stream").new_timber_m.values
        off = dw[dw.policy == "offline optimum"].new_timber_m.mean()
        L += [f"## {title}", "",
              "| Strategy | New timber (m) | ±95 % CI | Gain vs no hint (paired) | Better / worse streams | Share of gap to offline closed |",
              "|---|---|---|---|---|---|"]
        for p in dw.policy.unique():
            x = dw[dw.policy == p].sort_values("stream").new_timber_m.values
            diff = base - x
            gap = 100 * (base.mean() - x.mean()) / (base.mean() - off)
            L.append(f"| {p} | {x.mean():.2f} | {ci(x):.2f} | {diff.mean():+.2f} ± {ci(diff):.2f} | "
                     f"{(diff > 1e-9).sum()} / {(diff < -1e-9).sum()} | {gap:.0f} % |")
        L.append("")
    (RES / "summary.md").write_text("\n".join(L))
    print("\n".join(L))


if __name__ == "__main__":
    main()
