"""The S25-vs-S26 overlay figure, shared by the deck and the reference PDF.

One figure, drawn once, used in both places — the alternative is two figures that agree today and
disagree after the next edit. The landmark markers wear the same three colours the tables fill
their rows with, so a reader who has learned the legend on one page can read the other without
re-learning it.
"""
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt                                   # noqa: E402
from matplotlib.lines import Line2D                               # noqa: E402

import s25_s26_data as D                                          # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
INK, MUTED, GRID = "#1A1A1A", "#666666", "#DDDDDD"


def _frame(ax):
    ax.grid(True, color=GRID, lw=0.7, zorder=0)
    ax.set_axisbelow(True)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(MUTED)
        ax.spines[side].set_linewidth(0.9)
    ax.tick_params(colors=MUTED, labelsize=9)
    for lbl in ax.get_xticklabels() + ax.get_yticklabels():
        lbl.set_color(INK)


# Six landmarks land within half a percent of strain of each other around the peak, so an
# automatic offset puts labels on top of one another. These are placed by hand: S25 (the lower
# curve) labels below it, S26 (the upper curve) above, with leader lines doing the rest.
_LABEL_OFFSET = {
    ("S25", "yield"): (-64, -34), ("S25", "UTS"): (2, -50), ("S25", "fracture"): (14, -44),
    ("S26", "yield"): (-72, 34), ("S26", "UTS"): (16, 30), ("S26", "fracture"): (-30, 32),
}


def _landmarks(ax, tag, *, labels=True, size=95):
    """Yield / UTS / fracture, in the colours the tables use for those rows."""
    for what, (e, s) in D.key_points(tag).items():
        m = D.MARKS[what]
        ax.scatter([e], [s], s=size, marker="o", zorder=7,
                   facecolor=m["fill"], edgecolor=m["edge"], linewidth=2.0)
        if labels:
            ax.annotate(f"{tag} {m['short']} · {s:.1f} MPa\nε {e:.2f} %", (e, s),
                        textcoords="offset points", xytext=_LABEL_OFFSET[(tag, what)],
                        fontsize=8.5, color=INK, zorder=8, ha="left",
                        bbox=dict(boxstyle="round,pad=0.3", fc="white", ec=m["edge"], lw=1.1),
                        arrowprops=dict(arrowstyle="-", color=m["edge"], lw=1.0,
                                        shrinkA=2, shrinkB=6))


def overlay(path=None, *, figsize=(11.0, 6.2), dpi=200):
    """Full stress-strain overlay with an elastic-region inset."""
    fig, ax = plt.subplots(figsize=figsize)

    for tag in D.ORDER:
        x, y = D.curve(tag)
        d = D.summary(tag)
        ax.plot(x, y, lw=2.0, color=d["colour"], zorder=4,
                label=f"{d['label']}   UTS {d['UTS']:.2f} MPa · E {d['E']:.2f} GPa · "
                      f"ε_f {d['ef']:.2f} %")
        _landmarks(ax, tag)

    ax.set_xlabel("DIC gauge strain  ε  (%)", fontsize=11, color=INK)
    ax.set_ylabel("Engineering stress  σ  (MPa)", fontsize=11, color=INK)
    # Headroom above the peak and to the right of the last fracture point, so the hand-placed
    # labels have somewhere to sit instead of being clipped by the axes.
    emax = max(D.curve(t)[0][-1] for t in D.ORDER)
    smax = max(D.curve(t)[1].max() for t in D.ORDER)
    ax.set_xlim(0, emax * 1.13)
    ax.set_ylim(0, smax * 1.18)
    _frame(ax)

    series = ax.legend(loc="lower right", bbox_to_anchor=(1.0, 0.0), fontsize=9.5, frameon=True,
                       framealpha=0.96, edgecolor=GRID,
                       title="Specimen  (100 % infill PLA, spray markers, LED on)")
    series.get_title().set_fontsize(9.5)
    ax.add_artist(series)
    # Landmark key goes ABOVE the axes: every in-axes corner is either under a curve, under the
    # inset, or under a callout, and a legend that covers a data label is worse than no legend.
    ax.legend(handles=[Line2D([], [], marker="o", ls="", markersize=9,
                              markerfacecolor=m["fill"], markeredgecolor=m["edge"],
                              markeredgewidth=1.8, label=m["pretty"])
                       for m in D.MARKS.values()],
              loc="lower left", bbox_to_anchor=(0.0, 1.01), ncol=3, fontsize=9.5, frameon=True,
              framealpha=0.96, edgecolor=GRID,
              title="Landmark  (marker fill = the fill that row wears in the data table)"
              ).get_title().set_fontsize(9.5)

    # Inset on the elastic region — the whole E / sigma_y discrepancy lives in the first 1 % of
    # strain, which is invisible at full scale. Parked in the empty wedge under the softening
    # tail, clear of both legends.
    ins = ax.inset_axes([0.29, 0.17, 0.28, 0.36])
    for tag in D.ORDER:
        x, y = D.curve(tag)
        keep = x <= 1.2
        ins.plot(x[keep], y[keep], lw=1.8, color=D.RUNS[tag]["colour"])
    ins.set_xlim(0, 1.2)
    ins.set_ylim(bottom=0)
    ins.set_title("elastic region  (ε ≤ 1.2 %)", fontsize=8.5, color=MUTED)
    ins.tick_params(labelsize=7.5, colors=MUTED)
    _frame(ins)
    ax.indicate_inset_zoom(ins, edgecolor=MUTED, alpha=0.6)

    fig.tight_layout()
    if path:
        fig.savefig(path, dpi=dpi, facecolor="white")
        plt.close(fig)
        return path
    return fig


def elastic(path=None, *, figsize=(11.0, 4.4), dpi=200):
    """Why the reported E differs: the fixed 0.05-0.40 % window vs each specimen's own straight run."""
    fig, axes = plt.subplots(1, 2, figsize=figsize)
    for ax, tag in zip(axes, D.ORDER):
        x, y = D.curve(tag)
        d, best = D.summary(tag), D.best_elastic_fit(tag)
        keep = x <= 1.4
        ax.plot(x[keep], y[keep], lw=2.0, color=d["colour"], zorder=4, label="measured")
        ax.axvspan(0.05, 0.40, color="#C0392B", alpha=0.13, zorder=1,
                   label=f"fixed window → {d['E']:.2f} GPa")
        ax.axvspan(best[1], best[2], color="#2F9E44", alpha=0.15, zorder=2,
                   label=f"straightest run → {best[0]:.2f} GPa  (R² {best[3]:.4f})")
        ax.set_title(d["label"], fontsize=11, color=INK)
        ax.set_xlabel("ε (%)", fontsize=10, color=INK)
        ax.set_xlim(0, 1.4)
        ax.set_ylim(bottom=0)
        ax.legend(loc="upper left", fontsize=8.5, frameon=True, edgecolor=GRID)
        _frame(ax)
    axes[0].set_ylabel("σ (MPa)", fontsize=10, color=INK)
    fig.tight_layout()
    if path:
        fig.savefig(path, dpi=dpi, facecolor="white")
        plt.close(fig)
        return path
    return fig


if __name__ == "__main__":
    for name, fn in (("s25_s26_overlay.png", overlay), ("s25_s26_elastic.png", elastic)):
        print("wrote", fn(os.path.join(HERE, "..", "figures", name)))
