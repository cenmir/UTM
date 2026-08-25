"""Generate annotated schematic graphs for each advanced test mode, shown by the UI '?' help
icon so the operator sees exactly what each parameter (from the settings row) controls.
Outputs PNGs into ui_help/ next to this file. Re-run after changing a mode's parameters."""
import os
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "../ui/help")
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
    ax.plot(xs, ys, color=RED, lw=2.4, label="Linear ramp")
    # smooth (eased) ramp overlay: smoothstep between levels, flats unchanged
    sx, sy = [], []
    xx, prev = 0.0, 0.0
    for i in range(nlev):
        lvl = start + i * step
        tt = np.linspace(0, 1, 24); ss = 3 * tt ** 2 - 2 * tt ** 3
        sx += list(xx + tt * ramp); sy += list(prev + (lvl - prev) * ss); xx += ramp
        sx += [xx, xx + dwell]; sy += [lvl, lvl]; xx += dwell; prev = lvl
    ax.plot(sx, sy, color="#8e44ad", lw=2.0, ls="--", label="Smooth ramp")
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


# ---------------- Staircase -> FRACTURE ----------------
def staircase_to_fracture():
    """Two panels: what you SET (left) and what you GET (right). The right panel is the real payoff
    of this protocol — the dwell relaxation-drop is flat while the specimen is elastic and turns up
    sharply once a level passes yield, which is how T7.2 located the knee at 694 N."""
    fig, (ax, bx) = plt.subplots(1, 2, figsize=(9.4, 4.0), gridspec_kw={"width_ratios": [1.55, 1]})

    start, step, ramp_t, dwell_t = 1.0, 0.5, 0.42, 0.62
    drops = [0.03, 0.033, 0.038, 0.075, 0.16]          # relaxation drop per level: flat then knee
    T, F = [0.0], [0.0]
    for i, d in enumerate(drops):
        top = start + i * step
        T.append(T[-1] + ramp_t); F.append(top)                      # ramp to the level
        tt = np.linspace(0, dwell_t, 40)                             # dwell: force decays a little
        for k, s in enumerate(tt[1:]):
            T.append(T[-1] + (tt[1] - tt[0])); F.append(top - d * step * (1 - np.exp(-4 * s / dwell_t)))
    ax.plot(T, F, color=RED, lw=2.3)
    tb = T[-1]
    ax.plot([tb, tb + ramp_t * 0.85], [F[-1], start + len(drops) * step], color=RED, lw=2.3)
    xf = tb + ramp_t * 0.85; yf = start + len(drops) * step
    ax.plot([xf, xf + 0.10], [yf, 0.12], color=RED, lw=2.3)          # fracture: load collapses
    ax.plot([xf], [yf], "x", color="k", ms=11, mew=2.5)
    ax.text(xf + 0.16, yf * 0.86, "FRACTURE\n(auto-halt)", color="k", fontsize=10,
            fontweight="bold", va="top")

    xr = xf + 1.05
    ax.plot([0, xr], [start, start], "--", color="#0b5", lw=1.1)
    ax.text(xr, start, "  Start", va="center", ha="left", **PARAM)
    x2 = ramp_t * 2 + dwell_t * 1.05
    ax.annotate("", xy=(x2, start), xytext=(x2, start + step), arrowprops=dict(arrowstyle="<->", color="#0b5", lw=1.6))
    ax.text(x2 + 0.07, start + step * 0.42, "Step", **PARAM)
    xd0 = ramp_t; xd1 = ramp_t + dwell_t
    ax.annotate("", xy=(xd0, start * 1.06), xytext=(xd1, start * 1.06),
                arrowprops=dict(arrowstyle="<->", color="#0b5", lw=1.6))
    ax.text((xd0 + xd1) / 2, start * 1.13, "Dwell", ha="center", **PARAM)
    ax.annotate("slope = Speed", xy=(0.21, 0.50), xytext=(0.62, 0.22), fontsize=9, color=GREY,
                arrowprops=dict(arrowstyle="->", color=GREY, lw=1.2))
    ax.text(0.12, yf * 1.17, "keeps adding steps until it breaks — no Levels setting",
            color=GREY, fontsize=9.5, style="italic")
    ax.set_ylim(-0.05, yf * 1.30); ax.set_xlim(-0.1, xr + 1.0)
    _base(ax, "Staircase → FRACTURE — set")

    lv = np.arange(1, 10)
    dp = np.array([3.8, 3.2, 2.6, 1.6, 1.7, 1.8, 2.5, 3.2, 4.6])     # T7.2-shaped knee
    bx.plot(lv, dp, "o-", color=BLUE, lw=2.2, ms=6)
    bx.plot([4], [1.6], "o", color=RED, ms=13, mfc="none", mew=2.4)
    bx.annotate("yield onset\n(drop stops falling,\nstarts growing)", xy=(4.15, 1.65), xytext=(4.5, 3.5),
                fontsize=9.5, color=RED, ha="center",
                arrowprops=dict(arrowstyle="->", color=RED, lw=1.5))
    bx.set_xlabel("Level", fontsize=11); bx.set_ylabel("Dwell force drop (%)", fontsize=11)
    bx.set_title("→ what you get", fontsize=12, fontweight="bold", pad=10)
    bx.set_xticks(lv); bx.set_yticks([])
    for s in ("top", "right"):
        bx.spines[s].set_visible(False)
    fig.tight_layout()
    fig.savefig(os.path.join(OUT, "staircase_to_fracture.png"), dpi=105)
    plt.close(fig)


# ---------------- Progressive cyclic -> FRACTURE ----------------
def progressive_cyclic_to_fracture():
    """Left: the rising-peak load-unload schedule and its three parameters. Right: the stress-strain
    loops those unloads produce — the slope of each unload is the modulus at that damage state, and
    it visibly flattens, which is the stiffness-degradation curve this protocol exists to measure."""
    fig, (ax, bx) = plt.subplots(1, 2, figsize=(9.4, 4.0), gridspec_kw={"width_ratios": [1.55, 1]})

    first, pstep, floor = 1.0, 0.5, 0.32
    peaks = [first + i * pstep for i in range(5)]
    T, F, tp = [0.0], [0.0], []
    for p in peaks:
        T.append(T[-1] + 0.5 + (p - floor) * 0.30); F.append(p)       # rising stroke
        tp.append(T[-1])                                              # remember each apex time
        T.append(T[-1] + 0.42 + (p - floor) * 0.22); F.append(floor)  # unload to the floor
    ax.plot(T, F, color=RED, lw=2.3)
    yf = peaks[-1] + pstep
    xf = T[-1] + 0.5 + (yf - floor) * 0.30
    ax.plot([T[-1], xf], [floor, yf], color=RED, lw=2.3)
    ax.plot([xf, xf + 0.12], [yf, 0.12], color=RED, lw=2.3)
    ax.plot([xf], [yf], "x", color="k", ms=11, mew=2.5)
    ax.text(xf + 0.18, yf * 0.88, "FRACTURE\n(auto-halt)", color="k", fontsize=10,
            fontweight="bold", va="top")

    xr = xf + 1.15
    ax.plot([0, xr], [floor, floor], "--", color="#0b5", lw=1.1)
    ax.text(xr, floor, "  Unload to", va="center", ha="left", **PARAM)
    ax.annotate("", xy=(0.06, 0), xytext=(0.06, first), arrowprops=dict(arrowstyle="<->", color="#0b5", lw=1.6))
    ax.text(0.06, first + 0.10, "1st peak", ha="left", va="bottom", **PARAM)
    # Step arrow goes in the WIDE valley between the last two peaks — the early cycles are bunched
    # into the left ~15 % of the axis, so labelling there collides with "1st peak".
    xp = (tp[-2] + tp[-1]) / 2
    for y in (peaks[-2], peaks[-1]):
        ax.plot([xp - 0.75, xp + 0.75], [y, y], "--", color="#0b5", lw=1.0)
    ax.annotate("", xy=(xp, peaks[-2]), xytext=(xp, peaks[-1]), arrowprops=dict(arrowstyle="<->", color="#0b5", lw=1.6))
    ax.text(xp, peaks[-1] + 0.10, "Peak step", ha="center", va="bottom", **PARAM)
    ax.text(0.15, -0.17, "ramp slope (both directions) = Speed", color=GREY, fontsize=9, style="italic")
    ax.set_ylim(-0.28, yf * 1.15); ax.set_xlim(-0.1, xr + 1.5)
    _base(ax, "Progressive cyclic → FRACTURE — set")

    # Real nested loops: a saturating backbone, each unload a straight line whose SLOPE is the
    # modulus at that damage state. Softening 3.9 -> 2.3 makes the flattening visible while still
    # letting the permanent set accumulate left-to-right (a faster decay would cancel it out).
    A, B, sfloor = 3.4, 1.15, 0.15
    env = lambda e: A * (1 - np.exp(-B * e))
    inv = lambda s: -np.log(1 - s / A) / B
    E0 = A * B
    speaks = [1.0, 1.5, 2.0, 2.5, 3.0]
    ee = np.linspace(0, inv(speaks[-1]) * 1.04, 200)
    bx.plot(ee, env(ee), ":", color=GREY, lw=1.1)
    res = 0.0
    for i, p in enumerate(speaks):
        Ei = E0 * (1 - 0.10 * i)
        ep = inv(p)
        if i == 0:
            e0 = np.linspace(0, ep, 60); bx.plot(e0, env(e0), color=BLUE, lw=1.5)
        else:
            bx.plot([res, ep], [sfloor, p], color=BLUE, lw=1.5)       # reload to the new peak
        r = ep - (p - sfloor) / Ei
        bx.plot([ep, r], [p, sfloor], color=RED, lw=2.3)              # unload — slope = E at damage i
        res = r
    bx.annotate("each unload slope\n= E at that damage state", xy=(0.30, 1.03), xytext=(0.04, 2.62),
                fontsize=9.5, color=RED, arrowprops=dict(arrowstyle="->", color=RED, lw=1.5))
    bx.text(1.40, 0.38, "slopes flatten\n→ D = 1 − Eᵢ/E₀", color=RED, fontsize=9.5,
            fontweight="bold", ha="center")
    bx.set_xlim(-0.05, inv(speaks[-1]) * 1.08); bx.set_ylim(0, A * 0.98)
    bx.set_xlabel("Strain", fontsize=11); bx.set_ylabel("Stress", fontsize=11)
    bx.set_title("→ what you get", fontsize=12, fontweight="bold", pad=10)
    bx.set_xticks([]); bx.set_yticks([])
    for s in ("top", "right"):
        bx.spines[s].set_visible(False)
    fig.tight_layout()
    fig.savefig(os.path.join(OUT, "progressive_cyclic_to_fracture.png"), dpi=105)
    plt.close(fig)


if __name__ == "__main__":
    cyclic(); staircase(); relaxation(); creep()
    staircase_to_fracture(); progressive_cyclic_to_fracture()
    print("Wrote:", ", ".join(sorted(os.listdir(OUT))))
