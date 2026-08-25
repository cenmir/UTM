"""Figures for the E-fit-window question: the mechanism, then the evidence."""
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt                                   # noqa: E402
from matplotlib.lines import Line2D                               # noqa: E402
import numpy as np                                                # noqa: E402

import e_fit_data as E                                            # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
INK, MUTED, GRID = "#1A1A1A", "#666666", "#DDDDDD"
ISO_C, OURS_C, STEEP_C = "#C0392B", "#D29922", "#2F9E44"


def _frame(ax):
    ax.grid(True, color=GRID, lw=0.7, zorder=0)
    ax.set_axisbelow(True)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    for s in ("left", "bottom"):
        ax.spines[s].set_color(MUTED)
        ax.spines[s].set_linewidth(0.9)
    ax.tick_params(colors=MUTED, labelsize=9)
    for t in ax.get_xticklabels() + ax.get_yticklabels():
        t.set_color(INK)


def mechanism(path=None, *, figsize=(11.0, 4.6), dpi=200, tags=("S24", "S25", "S26", "S16")):
    """Rolling local slope vs strain — is the curve even straight where the window looks?

    A single fitted number cannot show this. The rolling slope can, and it is the whole argument:
    the curve stiffens through the first half-percent, so a window fixed at 0.05-0.40 % reads
    whatever that particular specimen had reached by 0.40 %.
    """
    rows = {r["specimen"]: r for r in E.specimens()}
    fig, ax = plt.subplots(figsize=figsize)

    ax.axvspan(*E.ISO_WINDOW, color=ISO_C, alpha=0.12, zorder=1)
    ax.axvspan(*E.OURS_WINDOW, color=OURS_C, alpha=0.12, zorder=1)
    ax.axhline(E.DATASHEET_E, color=MUTED, ls="--", lw=1.3, zorder=2)

    colours = ["#1F6FB4", "#D95F02", "#6A3D9A", "#0B7A75"]
    for (tag, col) in zip(tags, colours):
        if tag not in rows:
            continue
        x, y, _r = E.curve(rows[tag])
        c, s = E.local_slope(x, y)
        ax.plot(c, s, lw=2.0, color=col, zorder=5, label=tag)
        st = E.steepest_run(x, y)
        if st:
            mid = (st[1] + st[2]) / 2
            ax.scatter([mid], [np.interp(mid, c, s)], s=80, zorder=6,
                       facecolor="white", edgecolor=col, linewidth=2.0)

    ax.set_xlabel("strain ε  (%)   — centre of a 0.20 %-wide rolling fit", fontsize=10.5, color=INK)
    ax.set_ylabel("local slope  (GPa)", fontsize=10.5, color=INK)
    ax.set_xlim(0, 1.6)
    ax.set_ylim(bottom=0)
    _frame(ax)

    spec = ax.legend(loc="lower right", fontsize=9.5, frameon=True, edgecolor=GRID,
                     ncol=2, title="specimen (100 % infill)")
    spec.get_title().set_fontsize(9.5)
    ax.add_artist(spec)
    ax.legend(handles=[
        Line2D([], [], lw=8, color=ISO_C, alpha=0.3,
               label=f"ISO fixed window {E.ISO_WINDOW[0]:.2f}–{E.ISO_WINDOW[1]:.2f} %"),
        Line2D([], [], lw=8, color=OURS_C, alpha=0.3,
               label=f"our fixed window {E.OURS_WINDOW[0]:.2f}–{E.OURS_WINDOW[1]:.2f} %"),
        Line2D([], [], marker="o", ls="", markersize=9, markerfacecolor="white",
               markeredgecolor=MUTED, markeredgewidth=1.8,
               label="centre of the steepest straight run"),
        Line2D([], [], ls="--", color=MUTED, lw=1.3,
               label=f"add:north E-PLA datasheet {E.DATASHEET_E:.2f} GPa")],
        loc="lower left", fontsize=9, frameon=True, edgecolor=GRID, ncol=1)

    fig.tight_layout()
    if path:
        fig.savefig(path, dpi=dpi, facecolor="white"); plt.close(fig); return path
    return fig


def evidence(path=None, *, figsize=(11.0, 4.8), dpi=200):
    """The same nine specimens under all three methods, with scatter and the datasheet."""
    rows = E.table()
    summ = E.summary(rows)
    fig, ax = plt.subplots(figsize=figsize)
    n = len(rows)
    idx = np.arange(n)
    w = 0.26

    for k, (key, col) in enumerate((("iso", ISO_C), ("ours", OURS_C), ("steep", STEEP_C))):
        vals = [r[key] for r in rows]
        s = summ[key]
        ax.bar(idx + (k - 1) * w, vals, w, color=col, zorder=4,
               label=f"{s['label']}   mean {s['mean']:.2f} GPa · CV {s['cv']:.1f} % · "
                     f"{s['vs_tds']:+.0f} % vs TDS")

    # The datasheet goes in the LEGEND, not as an in-plot annotation: the only clear space above
    # the line is over the tallest bars, which is exactly where a label must not sit.
    ax.axhline(E.DATASHEET_E, color=MUTED, ls="--", lw=1.4, zorder=5,
               label=f"add:north E-PLA datasheet   {E.DATASHEET_E:.2f} GPa")

    ax.set_xticks(idx)
    ax.set_xticklabels([f"{r['specimen']}\n{r['test'] if r['test'] != r['specimen'] else '—'}"
                        for r in rows], fontsize=8.5)
    ax.set_ylabel("Young's modulus  E  (GPa)", fontsize=10.5, color=INK)
    ax.set_ylim(0, 3.9)
    _frame(ax)
    ax.legend(loc="upper left", fontsize=9, frameon=True, edgecolor=GRID, ncol=1,
              title="how the fit window is chosen").get_title().set_fontsize(9)
    fig.tight_layout()
    if path:
        fig.savefig(path, dpi=dpi, facecolor="white"); plt.close(fig); return path
    return fig


if __name__ == "__main__":
    for name, fn in (("e_fit_mechanism.png", mechanism), ("e_fit_evidence.png", evidence)):
        print("wrote", fn(os.path.join(HERE, "..", "figures", name)))
