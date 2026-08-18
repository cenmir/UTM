"""Figures for the S27/S28 50 % infill pair and the infill knock-down factor."""
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt                                    # noqa: E402
import numpy as np                                                 # noqa: E402

import s27_s28_data as S                                           # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
INK, MUTED, GRID = "#1A1A1A", "#666666", "#DDDDDD"
RED, GREEN, AMBER = "#C0392B", "#2F9E44", "#D29922"


def _frame(ax):
    ax.grid(True, color=GRID, lw=0.7, zorder=0)
    ax.set_axisbelow(True)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    for s in ("left", "bottom"):
        ax.spines[s].set_color(MUTED)
        ax.spines[s].set_linewidth(0.9)
    ax.tick_params(colors=MUTED, labelsize=8.5)
    for t in ax.get_xticklabels() + ax.get_yticklabels():
        t.set_color(INK)


def _save(fig, path, dpi=190):
    fig.savefig(path, dpi=dpi, facecolor="white")
    plt.close(fig)
    return path


def pair(path=None, *, figsize=(12.8, 4.15)):
    """S27 against S28 — how repeatable is a 50 % specimen under the capture protocol?"""
    fig, axes = plt.subplots(1, 2, figsize=figsize,
                             gridspec_kw=dict(width_ratios=[1.35, 1.0]))
    fig.subplots_adjust(wspace=0.20, left=0.062, right=0.978, top=0.84, bottom=0.155)

    ax = axes[0]
    for tag in S.PAIR_50:
        x, y = S.curve(tag)
        s = S.summary(tag)
        ax.plot(x, y, lw=2.2, color=s["colour"], zorder=5,
                label=f"{s['label']}   UTS {s['UTS']:.2f} · E {s['E']:.3f} · ε_f {s['ef']:.2f} %")
        r = S.run(tag)["r"]
        ax.scatter([r["uts_ec"]], [r["uts"]], s=70, facecolor="white",
                   edgecolor=s["colour"], lw=2, zorder=6)
    ax.set_title("50 % infill, same protocol, 14 minutes apart", fontsize=10.5, color=INK)
    ax.set_xlabel("DIC gauge strain ε (%)", fontsize=9.5, color=INK)
    ax.set_ylabel("Engineering stress σ (MPa)", fontsize=9.5, color=INK)
    ax.set_xlim(0, None)
    ax.set_ylim(0, None)
    _frame(ax)
    ax.legend(loc="lower right", fontsize=8.5, frameon=True, edgecolor=GRID)

    ax = axes[1]
    keys = [("UTS", "UTS"), ("σ_y", "sy"), ("E", "E"), ("ε_f", "ef")]
    x = np.arange(len(keys))
    p50 = [S.group_spread(S.PAIR_50, k) for _, k in keys]
    p100 = [S.group_spread(S.PAIR_100, k) for _, k in keys]
    ax.bar(x - 0.2, p50, 0.4, color=GREEN, zorder=5, label="50 % pair (S27 vs S28)")
    ax.bar(x + 0.2, p100, 0.4, color="#BBBBBB", zorder=4, label="100 % pair (S25 vs S26)")
    for xi, (a, b) in enumerate(zip(p50, p100)):
        ax.text(xi - 0.2, a + 0.6, f"{a:.1f}", ha="center", fontsize=8.5, color=INK)
        ax.text(xi + 0.2, b + 0.6, f"{b:.1f}", ha="center", fontsize=8.5, color=INK)
    ax.set_xticks(x)
    ax.set_xticklabels([n for n, _ in keys], fontsize=9.5)
    ax.set_ylabel("difference within the pair (%)", fontsize=9.5, color=INK)
    ax.set_title("The 50 % pair is the MORE repeatable of the two", fontsize=10.5, color=INK)
    ax.set_ylim(0, 36)
    _frame(ax)
    ax.legend(loc="upper left", fontsize=8.5, frameon=True, edgecolor=GRID)

    fig.suptitle("S27 vs S28 — the 50 % infill video pair", fontsize=12, color=INK, y=0.965)
    return _save(fig, path) if path else fig


def knockdown(path=None, *, figsize=(12.8, 4.4)):
    """50 % against 100 %, and both against the datasheet."""
    fig, axes = plt.subplots(1, 3, figsize=figsize,
                             gridspec_kw=dict(width_ratios=[1.5, 1.0, 1.0]))
    fig.subplots_adjust(wspace=0.30, left=0.055, right=0.985, top=0.83, bottom=0.145)

    ax = axes[0]
    for tag in S.ORDER:
        x, y = S.curve(tag)
        s = S.summary(tag)
        ax.plot(x, y, lw=2.0, color=s["colour"], zorder=5,
                label=f"{s['label']} · {s['infill']:.0f} %   UTS {s['UTS']:.2f} MPa")
    ax.axhline(S.TDS["UTS"], color=MUTED, ls="--", lw=1.4, zorder=3)
    ax.text(0.15, S.TDS["UTS"] + 1.2, f"{S.TDS_NAME}  {S.TDS['UTS']:.0f} MPa",
            fontsize=8.5, color=MUTED)
    ax.set_title("All four capture runs, against the datasheet", fontsize=10.5, color=INK)
    ax.set_xlabel("DIC gauge strain ε (%)", fontsize=9.5, color=INK)
    ax.set_ylabel("Engineering stress σ (MPa)", fontsize=9.5, color=INK)
    ax.set_xlim(0, None)
    ax.set_ylim(0, 64)
    _frame(ax)
    ax.legend(loc="center right", fontsize=8, frameon=True, edgecolor=GRID)

    ax = axes[1]
    labs = ["UTS", "E"]
    x = np.arange(len(labs))
    k50 = [S.knockdown(S.PAIR_50, k) for k in ("UTS", "E")]
    k100 = [S.knockdown(S.PAIR_100, k) for k in ("UTS", "E")]
    ax.bar(x - 0.2, k50, 0.4, color=GREEN, zorder=5, label="50 % infill")
    ax.bar(x + 0.2, k100, 0.4, color="#1F6FB4", zorder=5, label="100 % infill")
    ax.axhline(1.0, color=RED, ls="--", lw=1.5, zorder=6)
    # The gap BETWEEN the two bar groups is the only part of this panel empty at that height —
    # anywhere to the right sits on the 100 % E bar, which is 1.05 tall.
    ax.text(0.5, 1.10, "k = 1  —  solid material", fontsize=8.5, color=RED, ha="center")
    for xi, (a, b) in enumerate(zip(k50, k100)):
        ax.text(xi - 0.2, a + 0.06, f"{a:.2f}", ha="center", fontsize=9, color=INK)
        ax.text(xi + 0.2, b + 0.06, f"{b:.2f}", ha="center", fontsize=9, color=INK)
    ax.set_xticks(x)
    ax.set_xticklabels(labs, fontsize=9.5)
    ax.set_ylabel("knock-down  k = datasheet / measured", fontsize=9.5, color=INK)
    ax.set_ylim(0, 3.5)
    ax.set_title("How far short of solid material", fontsize=10.5, color=INK)
    _frame(ax)
    ax.legend(loc="upper right", fontsize=8.5, frameon=True, edgecolor=GRID)

    ax = axes[2]
    labs = ["UTS", "E", "ε_f"]
    x = np.arange(len(labs))
    ratio = [S.group_mean(S.PAIR_100, k) / S.group_mean(S.PAIR_50, k) for k in ("UTS", "E", "ef")]
    ax.bar(x, ratio, 0.5, color=AMBER, zorder=5)
    ax.axhline(2.0, color=RED, ls="--", lw=1.5, zorder=6)
    ax.text(2.45, 2.06, "2× — what\n'twice the material'\nwould give", fontsize=8, color=RED,
            ha="right")
    for xi, v in enumerate(ratio):
        ax.text(xi, v + 0.06, f"{v:.2f}×", ha="center", fontsize=9.5, color=INK)
    ax.set_xticks(x)
    ax.set_xticklabels(labs, fontsize=9.5)
    ax.set_ylabel("100 % ÷ 50 %", fontsize=9.5, color=INK)
    ax.set_ylim(0, 3.0)
    ax.set_title("Doubling infill more than doubles strength", fontsize=10.5, color=INK)
    _frame(ax)

    fig.suptitle("The infill knock-down factor — 50 % vs 100 %, same protocol, same week",
                 fontsize=12, color=INK, y=0.965)
    return _save(fig, path) if path else fig


FIGURES = {"s27_s28_pair.png": pair, "infill_knockdown.png": knockdown}

if __name__ == "__main__":
    for name, fn in FIGURES.items():
        print("wrote", fn(os.path.join(HERE, name)))
