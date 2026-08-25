"""Figures for the marker-spacing test: S33/S34 at 45 mm against S25/S26 at 80 mm.

  gauge_geometry.png  the two marker spacings on the same specimen, to scale
  gauge_pair.png      S33 vs S34 — repeatability at the new spacing
  gauge_compare.png   45 mm vs 80 mm — the curves, and strain at matched stress
  gauge_scatter.png   the test that settles it: within-group scatter vs between-group difference

Everything is read from the CSVs. The comparison is made at MATCHED STRESS rather than matched
strain, because stress is the independent variable here — force is applied, strain is measured, and
the question is whether the measured strain depends on how far apart the markers are.
"""
import os
import sys

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt                                       # noqa: E402
from matplotlib.patches import Rectangle                              # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
FIGS = os.path.join(HERE, "..", "figures")
sys.path.insert(0, os.path.abspath(os.path.join(ROOT, "Software", "UTM_PyQt6")))
import json                                                           # noqa: E402
from utm_analysis import read_csv, analyze                            # noqa: E402

AREA = 80.0
GAUGE = {"S33": 45.0, "S34": 45.0, "S25": 80.0, "S26": 80.0}
PX0 = {"S33": 939.9, "S34": 938.3, "S25": 1675.3, "S26": 1676.0}
C45, C45b = "#c0392b", "#e8836f"
C80, C80b = "#1f6fb4", "#7fb3d5"
COL = {"S33": C45, "S34": C45b, "S25": C80, "S26": C80b}
GRID, MUTED, INK = "#DDDDDD", "#666666", "#212529"
PAIRS = (("S33", "S25"), ("S34", "S26"))


def _style(ax):
    ax.grid(True, color=GRID, lw=0.6)
    ax.set_axisbelow(True)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)


def load():
    reg = {r["specimen"]: r for r in
           json.load(open(os.path.join(ROOT, "Software", "UTM_PyQt6", "registry.json")))
           if r.get("specimen")}
    out = {}
    for k, g in GAUGE.items():
        path = os.path.join(ROOT, reg[k]["csv"])
        a = analyze(path, AREA, g)
        rows = read_csv(path)
        fr = a.get("fracture_i")
        ok = [r for r in rows if r["lpx"] > 100]
        if fr is not None:
            tfr = rows[fr]["t"]
            ok = [r for r in ok if r["t"] <= tfr]
        e = np.array([r["ec"] for r in ok])
        s = np.array([(r["F"] + a["anchor"]) / AREA for r in ok])
        i = np.argsort(e)
        out[k] = {"e": e[i], "s": s[i], "a": a, "L": g}
    return out


def eps_at(d, sigma, tol=0.6):
    m = np.abs(d["s"] - sigma) < tol
    return float(np.median(d["e"][m])) if m.any() else float("nan")


# --------------------------------------------------------------------- 1. the geometry
def fig_geometry(out="gauge_geometry.png"):
    # Markers are RECTANGLES sized in data units, not plt.Circle: the axis is 150 mm wide and about
    # 2 units tall, so a true circle renders as a tall bar. Same trap as tpu_framing.png.
    fig, ax = plt.subplots(figsize=(12.4, 3.3))
    LEFT = 34.0                                    # room for the row labels, in data units
    for row, (L, col, label, px0) in enumerate((
            (80.0, C80, "S25 / S26 — 80 mm apart", 1675.0),
            (45.0, C45, "S33 / S34 — 45 mm apart", 939.0))):
        y = 1.0 - row * 0.78
        ax.add_patch(Rectangle((LEFT, y - 0.15), 120, 0.30, fc="#F2F4F6", ec="#AAB2BD", lw=1.1))
        x0 = LEFT + (120 - L) / 2
        for x in (x0, x0 + L):
            ax.add_patch(Rectangle((x - 1.6, y - 0.11), 3.2, 0.22, fc=col, ec="white",
                                   lw=0.9, zorder=3))
        ax.annotate("", xy=(x0, y - 0.25), xytext=(x0 + L, y - 0.25),
                    arrowprops=dict(arrowstyle="<->", color=col, lw=1.7))
        ax.text(x0 + L / 2, y - 0.40, f"{L:.0f} mm   =   {px0:.0f} px at 20.9 px/mm",
                ha="center", va="top", color=col, fontsize=10.5, weight="bold")
        ax.text(LEFT - 4, y, label, ha="right", va="center", fontsize=10.5, color=col,
                weight="bold")
    ax.text(LEFT + 60, -0.78, "Same specimen geometry, same 80 mm² section, same 0.10 mm/s. "
                              "The ONLY change is how far apart the two dots are sprayed.",
            ha="center", fontsize=10.5, color=INK)
    ax.set_xlim(-2, LEFT + 124)
    ax.set_ylim(-0.95, 1.30)
    ax.axis("off")
    fig.tight_layout()
    p = os.path.join(FIGS, out)
    fig.savefig(p, dpi=160)
    plt.close(fig)
    print("wrote", os.path.basename(p))
    return p


# --------------------------------------------------------------------- 2. the 45 mm pair
def fig_pair(out="gauge_pair.png"):
    D = load()
    fig, axes = plt.subplots(1, 2, figsize=(12.4, 4.2))
    ax = axes[0]
    for k in ("S33", "S34"):
        ax.plot(D[k]["e"] * 100, D[k]["s"], color=COL[k], lw=1.7, label=f"{k}  (45 mm)")
    ax.set_xlabel("DIC strain (%)")
    ax.set_ylabel("Engineering stress (MPa)")
    ax.set_title("The 45 mm pair, to fracture", fontsize=10.5)
    ax.legend(frameon=False, fontsize=9)
    _style(ax)

    ax = axes[1]
    sig = np.arange(8, 45, 1.0)
    d33 = np.array([eps_at(D["S33"], s) for s in sig])
    d34 = np.array([eps_at(D["S34"], s) for s in sig])
    ax.axhline(0, color=MUTED, lw=0.9)
    ax.fill_between(sig, -5, 5, color="#2f9e44", alpha=0.09)
    ax.plot(sig, (d34 - d33) / d33 * 100, color=C45, lw=1.8)
    ax.set_xlabel("Engineering stress (MPa)")
    ax.set_ylabel("S34 − S33  (% of S33 strain)")
    ax.set_ylim(-40, 40)
    ax.set_title("Specimen-to-specimen difference at matched stress", fontsize=10.5)
    ax.text(0.98, 0.05, "shaded = ±5 %", transform=ax.transAxes, ha="right",
            fontsize=9, color=MUTED)
    _style(ax)
    fig.tight_layout()
    p = os.path.join(FIGS, out)
    fig.savefig(p, dpi=160)
    plt.close(fig)
    print("wrote", os.path.basename(p))
    return p


# --------------------------------------------------------------------- 3. 45 vs 80
def fig_compare(out="gauge_compare.png"):
    D = load()
    fig, axes = plt.subplots(1, 2, figsize=(12.6, 4.3))
    ax = axes[0]
    for k in ("S25", "S26", "S33", "S34"):
        ax.plot(D[k]["e"] * 100, D[k]["s"], color=COL[k], lw=1.7,
                label=f"{k}  ({D[k]['L']:.0f} mm)")
    ax.set_xlabel("DIC strain (%)")
    ax.set_ylabel("Engineering stress (MPa)")
    ax.set_title("All four runs — the curves do not separate by gauge", fontsize=10.5)
    ax.legend(frameon=False, fontsize=8.5, ncol=2)
    _style(ax)

    ax = axes[1]
    sig = np.arange(10, 42, 1.0)
    for (a45, b80), col, lab in zip(PAIRS, (C45, C80),
                                    ("S33 (45) vs S25 (80)", "S34 (45) vs S26 (80)")):
        x = np.array([eps_at(D[a45], s) for s in sig])
        y = np.array([eps_at(D[b80], s) for s in sig])
        ax.plot(sig, (x - y) / y * 100, color=col, lw=1.9, label=lab)
    ax.axhline(0, color=MUTED, lw=0.9)
    ax.fill_between(sig, -5, 5, color="#2f9e44", alpha=0.09)
    ax.set_xlabel("Engineering stress (MPa)")
    ax.set_ylabel("45 mm − 80 mm  (% of the 80 mm strain)")
    ax.set_ylim(-40, 40)
    ax.set_title("Strain difference at matched stress", fontsize=10.5)
    ax.legend(frameon=False, fontsize=9, loc="lower right")
    _style(ax)
    fig.tight_layout()
    p = os.path.join(FIGS, out)
    fig.savefig(p, dpi=160)
    plt.close(fig)
    print("wrote", os.path.basename(p))
    return p


# --------------------------------------------------------------------- 4. the deciding test
def fig_scatter(out="gauge_scatter.png"):
    """Within-group scatter against between-group difference. If the bars on the left are as tall
    as the bar on the right, the gauge length is not what is moving the numbers."""
    D = load()
    stresses = [15, 20, 25, 30, 35, 40]
    w45, w80, betw = [], [], []
    for t in stresses:
        a, b = eps_at(D["S33"], t), eps_at(D["S34"], t)
        c, d = eps_at(D["S25"], t), eps_at(D["S26"], t)
        w45.append(abs(a / b - 1) * 100)
        w80.append(abs(c / d - 1) * 100)
        betw.append(abs(((a + b) / 2) / ((c + d) / 2) - 1) * 100)
    x = np.arange(len(stresses))
    fig, ax = plt.subplots(figsize=(10.4, 4.3))
    ax.bar(x - 0.26, w45, 0.24, color=C45, label="scatter WITHIN the 45 mm pair")
    ax.bar(x, w80, 0.24, color=C80, label="scatter WITHIN the 80 mm pair")
    ax.bar(x + 0.26, betw, 0.24, color="#2f9e44",
           label="difference BETWEEN 45 mm and 80 mm")
    ax.set_xticks(x)
    ax.set_xticklabels([f"{s} MPa" for s in stresses])
    ax.set_ylabel("difference in measured strain (%)")
    ax.set_title("The between-gauge difference is no larger than the scatter between two "
                 "specimens of the SAME gauge", fontsize=10.5)
    ax.legend(frameon=False, fontsize=9)
    _style(ax)
    fig.tight_layout()
    p = os.path.join(FIGS, out)
    fig.savefig(p, dpi=160)
    plt.close(fig)
    print("wrote", os.path.basename(p))
    return p


def all_figs():
    return [fig_geometry(), fig_pair(), fig_compare(), fig_scatter()]


def summary():
    """The numbers the slides quote, computed once."""
    D = load()
    out = {"pair_diff": {}, "cross": {}, "props": {}}
    for t in (10, 20, 30, 40):
        out["cross"][t] = {f"{a}/{b}": (eps_at(D[a], t) / eps_at(D[b], t) - 1) * 100
                           for a, b in PAIRS}
    for k in D:
        a = D[k]["a"]
        out["props"][k] = dict(E=a["E"], uts=a["uts"], sy=a["sy"], ef=a["ef"] * 100,
                               anchor=a["anchor"], L=D[k]["L"], px0=PX0[k])
    # bound on a fixed per-marker centroid bias
    diffs = [abs(eps_at(D["S33"], t) - eps_at(D["S25"], t)) for t in (15, 20, 25, 30, 35, 40)]
    out["bias_px"] = float(np.mean(diffs)) / (1 / PX0["S33"] - 1 / PX0["S25"])
    return out


if __name__ == "__main__":
    all_figs()
    s = summary()
    print(f"\nfixed centroid-bias bound: {s['bias_px']:.3f} px")
    for t, v in s["cross"].items():
        print(f"  at {t:2d} MPa: " + "   ".join(f"{k} {d:+.1f} %" for k, d in v.items()))
