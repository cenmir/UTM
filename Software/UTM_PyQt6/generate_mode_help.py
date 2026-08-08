"""Generate annotated schematic graphs for each advanced test mode, shown by the UI '?' help
icon so the operator sees exactly what each parameter (from the settings row) controls.
Outputs PNGs into ui_help/ next to this file. Re-run after changing a mode's parameters."""
import os
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ui_help")
os.makedirs(OUT, exist_ok=True)

BLUE, RED, GREY = "#1f6fb2", "#c0392b", "#7f8c8d"
PARAM = dict(color="#0b5", fontsize=11, fontweight="bold")


def _base(ax, title, xlabel="Time  →", ylabel="Force (N)"):
    ax.set_title(title, fontsize=13, fontweight="bold", pad=10)
    ax.set_xlabel(xlabel, fontsize=11)
    ax.set_ylabel(ylabel, fontsize=11)
    ax.set_xticks([]); ax.set_yticks([])
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)


def _hline(ax, y, x0, x1, label, color=GREY):
    ax.plot([x0, x1], [y, y], "--", color=color, lw=1.2)
    ax.text(x1, y, "  " + label, va="center", ha="left", color=color, fontsize=10)


def _dbl_arrow(ax, x0, x1, y, label, vertical=False, color="#0b5"):
    a = FancyArrowPatch((x0, y), (x1, y) if not vertical else (x0, x1),
                        arrowstyle="<->", mutation_scale=14, color=color, lw=1.6)
    ax.add_patch(a)
    if vertical:
        ax.text(x0, (y + x1) / 2 if False else (y), "", )  # not used
    else:
        ax.text((x0 + x1) / 2, y, label, ha="center", va="bottom", **PARAM)


# ---------------- Cyclic ----------------
def cyclic():
    fig, ax = plt.subplots(figsize=(6.4, 4.2))
    lo, hi, ncyc = 1.0, 4.0, 3
    xs, ys = [0], [lo]
    t = 0
    for _ in range(ncyc):
        xs += [t + 1, t + 2]; ys += [hi, lo]; t += 2
    ax.plot(xs, ys, color=RED, lw=2.4, label="Triangle")
    # sine waveform between the same bounds (eases at each peak)
    tg = np.linspace(0, t, 500)
    mid = (lo + hi) / 2; amp = (hi - lo) / 2
    sine = mid - amp * np.cos(np.pi * tg)      # starts at Low, peaks at High each half-period
    ax.plot(tg, sine, color="#8e44ad", lw=2.2, ls="--", label="Sine (smooth peaks)")
    _hline(ax, hi, 0, t, "High  (N)", RED)
    _hline(ax, lo, 0, t, "Low  (N)", BLUE)
    ax.legend(loc="lower right", fontsize=9, framealpha=0.9, ncol=2)
    # one cycle bracket
    ax.annotate("", xy=(0, hi + 0.5), xytext=(2, hi + 0.5),
                arrowprops=dict(arrowstyle="<->", color="#0b5", lw=1.6))
    ax.text(1, hi + 0.62, "1 cycle", ha="center", color="#0b5", fontsize=11, fontweight="bold")
    ax.text(0.2, lo - 0.9, "repeat × Cycles", ha="left", **PARAM)
    ax.annotate("slope = Speed", xy=(0.5, (lo + hi) / 2), xytext=(0.7, hi + 0.1),
                color=GREY, fontsize=9, arrowprops=dict(arrowstyle="->", color=GREY))
    ax.set_ylim(lo - 1.3, hi + 1.2)
    _base(ax, "Cyclic — load / unload between two force bounds")
    fig.tight_layout(); fig.savefig(os.path.join(OUT, "cyclic.png"), dpi=110); plt.close(fig)


# ---------------- Staircase ----------------
def staircase():
    fig, ax = plt.subplots(figsize=(6.4, 4.2))
    start, step, nlev, dwell, ramp = 1.0, 1.0, 4, 1.4, 0.6
    x, y = 0, 0
    xs, ys = [0], [0]
    for i in range(nlev):
        lvl = start + i * step
        x += ramp; xs.append(x); ys.append(lvl)      # ramp up
        x += dwell; xs.append(x); ys.append(lvl)      # dwell (flat)
    ax.plot(xs, ys, color=RED, lw=2.4, label="Crosshead force")
    ax.legend(loc="upper left", fontsize=9, framealpha=0.9)
    # Start level
    _hline(ax, start, 0, xs[-1], "", BLUE)
    ax.annotate("Start (N)", xy=(0.05, start), xytext=(0.1, start + 0.3),
                color="#0b5", fontsize=11, fontweight="bold",
                arrowprops=dict(arrowstyle="->", color="#0b5"))
    # Step (vertical gap between level 2 and 3)
    xa = ramp * 3 + dwell * 2 + 0.1
    ax.annotate("", xy=(xa, start + step), xytext=(xa, start + 2 * step),
                arrowprops=dict(arrowstyle="<->", color="#0b5", lw=1.6))
    ax.text(xa + 0.1, start + 1.5 * step, "Step (N)", va="center", **PARAM)
    # Dwell (flat width on first level)
    d0 = ramp
    ax.annotate("", xy=(d0, start - 0.35), xytext=(d0 + dwell, start - 0.35),
                arrowprops=dict(arrowstyle="<->", color="#0b5", lw=1.6))
    ax.text(d0 + dwell / 2, start - 0.62, "Dwell (s)", ha="center", va="top", **PARAM)
    ax.text(xs[-1], ys[-1] + 0.25, "Levels = steps", ha="right", **PARAM)
    ax.set_ylim(-0.9, start + (nlev - 1) * step + 1.0)
    _base(ax, "Staircase — step load up, hold (dwell) at each level")
    fig.tight_layout(); fig.savefig(os.path.join(OUT, "staircase.png"), dpi=110); plt.close(fig)


# ---------------- Relaxation ----------------
def relaxation():
    fig, ax = plt.subplots(figsize=(6.4, 4.2))
    tr = 2.0            # ramp end
    T = np.linspace(0, 8, 400)
    eps = np.where(T < tr, (T / tr), 1.0)                          # strain: ramp then flat
    F = np.where(T < tr, (T / tr), np.exp(-(T - tr) / 2.5))        # force: rise then decay
    ax.plot(T, eps, color=BLUE, lw=2.4, label="Strain (held fixed)")
    ax2 = ax.twinx(); ax2.plot(T, F, color=RED, lw=2.4, label="Force (relaxes)")
    ax2.set_yticks([])
    l1, la1 = ax.get_legend_handles_labels(); l2, la2 = ax2.get_legend_handles_labels()
    ax.legend(l1 + l2, la1 + la2, loc="upper right", fontsize=9, framealpha=0.9)
    _hline(ax, 1.0, 0, 8, "Hold strain", BLUE)
    # Duration bracket over the hold
    ax.annotate("", xy=(tr, -0.13), xytext=(8, -0.13),
                arrowprops=dict(arrowstyle="<->", color="#0b5", lw=1.6))
    ax.text((tr + 8) / 2, -0.22, "Duration (s)", ha="center", va="top", **PARAM)
    ax.text(0.9, 0.45, "slope = Speed", color=GREY, fontsize=9, rotation=38)
    ax2.text(5.2, 0.55, "force decays\n(measured)", color=RED, fontsize=10, ha="center")
    ax.set_ylim(-0.3, 1.25)
    _base(ax, "Relaxation — hold strain fixed, force decays", ylabel="Strain")
    fig.tight_layout(); fig.savefig(os.path.join(OUT, "relaxation.png"), dpi=110); plt.close(fig)


# ---------------- Creep ----------------
def creep():
    fig, ax = plt.subplots(figsize=(6.4, 4.2))
    tr = 2.0
    T = np.linspace(0, 8, 400)
    F = np.where(T < tr, (T / tr), 1.0)                                   # force: ramp then flat
    eps = np.where(T < tr, (T / tr) * 0.6, 0.6 + 0.4 * (1 - np.exp(-(T - tr) / 3.0)))  # strain creeps up
    ax.plot(T, eps, color=BLUE, lw=2.4, label="Strain (creeps)")
    ax2 = ax.twinx(); ax2.plot(T, F, color=RED, lw=2.4, label="Force (held fixed)")
    ax2.set_ylim(0, 1.3); ax2.set_yticks([])
    ax2.plot([0, 8], [1.0, 1.0], "--", color=RED, lw=1.2)
    l1, la1 = ax.get_legend_handles_labels(); l2, la2 = ax2.get_legend_handles_labels()
    ax.legend(l1 + l2, la1 + la2, loc="center right", fontsize=9, framealpha=0.9)
    ax2.text(8, 1.0, "  Load (N)", va="center", color=RED, fontsize=10)
    ax.annotate("", xy=(tr, -0.13), xytext=(8, -0.13),
                arrowprops=dict(arrowstyle="<->", color="#0b5", lw=1.6))
    ax.text((tr + 8) / 2, -0.2, "Duration (s)", ha="center", va="top", **PARAM)
    ax.text(0.7, 0.28, "slope = Speed", color=GREY, fontsize=9, rotation=33)
    ax.text(5.2, 0.72, "strain creeps\n(measured)", color=BLUE, fontsize=10, ha="center")
    ax.set_ylim(-0.28, 1.15)
    _base(ax, "Creep — hold force fixed, strain grows", ylabel="Strain")
    fig.tight_layout(); fig.savefig(os.path.join(OUT, "creep.png"), dpi=110); plt.close(fig)


if __name__ == "__main__":
    cyclic(); staircase(); relaxation(); creep()
    print("Wrote:", ", ".join(sorted(os.listdir(OUT))))
