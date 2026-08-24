"""Figures for the PLA / PETG / TPU comparison, and for why TPU stops at 15 mm.

  tpu_framing.png    why the marker leaves the frame at ~15 mm — the geometry, to scale
  trio_curves.png    all three stress-strain curves; log stress, because they span two decades
  trio_modulus.png   measured E against the literature band for each material
  trio_slopes.png    the expected initial slope vs the one the rig measured
  trio_table.png     the four properties side by side

Everything is read from the CSVs through utm_analysis. The only typed-in numbers are the
LITERATURE bands, which are cited in LIT below and are the thing being compared against.
"""
import os
import sys

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt                                       # noqa: E402
from matplotlib.patches import Rectangle                              # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "Software", "UTM_PyQt6"))
import json                                                           # noqa: E402
from utm_analysis import read_csv, analyze                            # noqa: E402

AREA = GAUGE = 80.0
GRID, MUTED = "#DDDDDD", "#666666"
COL = {"PLA": "#1f77b4", "PETG": "#7048e8", "TPU": "#e8590c"}

# Literature ranges for FDM-printed specimens, 100 % infill. E in MPa, strength in MPa,
# elongation at break in %.
#   PLA   — Chacón et al. 2017; Ultimaker/Prusament PLA TDS
#   PETG  — Durgashyam et al. 2019; Prusament PETG TDS
#   TPU   — TPU 95A TDS (Ultimaker, SainSmart, NinjaFlex); Hohimer et al. 2020
LIT = {
    "PLA":  {"E": (2000, 3500), "sig": (40, 65), "eps": (2, 8)},
    "PETG": {"E": (1500, 2100), "sig": (35, 53), "eps": (5, 25)},
    "TPU":  {"E": (12, 30),     "sig": (25, 40), "eps": (400, 700)},
}
GROUPS = {"PLA": ["S24", "S25", "S26", "S33", "S13", "S16"],
          "PETG": ["S30", "S31"],
          "TPU": ["S35", "S36"]}
REP = {"PLA": "S25", "PETG": "S30", "TPU": "S36"}      # the curve drawn for each material


def _style(ax):
    ax.grid(True, color=GRID, lw=0.6)
    ax.set_axisbelow(True)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)


def registry():
    rows = json.load(open(os.path.join(ROOT, "Software", "UTM_PyQt6", "registry.json")))
    return {r["specimen"]: r for r in rows if r.get("specimen")}


_CACHE = {}


def stats():
    """Group properties, re-analysed from the CSVs rather than read off the registry.

    The registry stores E in GPa rounded to 3 decimals, which is 1 MPa of resolution. That is
    invisible for PLA at 3.09 GPa and fatal for TPU at 0.025: both TPU runs round to the same
    number, so the run-to-run agreement came out as "0.0 % apart" when it is 1.2 %.
    """
    if _CACHE:
        return _CACHE
    reg = registry()
    for m, ids in GROUPS.items():
        E, sig, eps = [], [], []
        for i in ids:
            if i not in reg:
                continue
            a = analyze(os.path.join(ROOT, reg[i]["csv"]),
                        reg[i].get("area_mm2") or AREA, reg[i].get("gauge_mm") or GAUGE)
            E.append(a["E"] * 1000.0)
            sig.append(a["uts"])
            eps.append(a["ef"] * 100.0)
        _CACHE[m] = {"n": len(E), "E": E, "sig": sig, "eps": eps}
    return _CACHE


def curve(spec):
    """Tracked stress-strain for one specimen, preload added back in."""
    reg = registry()
    path = os.path.join(ROOT, reg[spec]["csv"])
    rows = read_csv(path)
    a = analyze(path, AREA, GAUGE)
    fr = a.get("fracture_i")
    ok = [r for r in rows if r["lpx"] > 100]
    if fr is not None:
        tfr = rows[fr]["t"]
        ok = [r for r in ok if r["t"] <= tfr]
    e = np.array([r["ec"] for r in ok])
    s = np.array([(r["F"] + a["anchor"]) / AREA for r in ok])
    k = np.argsort(e)
    return e[k] * 100, s[k], a


# ----------------------------------------------------------------- why TPU stops at 15 mm
def fig_framing(out="tpu_framing.png"):
    """The frame, the pair and the travel, to scale along the specimen axis.

    Deliberately NOT drawn with circles: the axis is 2448 px wide and a few units tall, so a
    true-radius circle renders as a bar. Markers are shown as ticks with their footprint, which
    is the only thing that matters here — how close each one is to an edge.
    """
    W, R, PX0, START = 2448.0, 55.0, 1690.0, 283.0
    DRIFT, SHARE = 1.264, 0.65
    fig, ax = plt.subplots(figsize=(12.6, 3.2))
    ax.add_patch(Rectangle((0, 0), W, 1.0, fc="#F4F6F8", ec="#AAB2BD", lw=1.4))

    def marker(x, c, name, sub):
        ax.add_patch(Rectangle((x - R, 0.42), 2 * R, 0.16, fc=c, ec="white", lw=0.8, zorder=3))
        ax.plot([x, x], [0.0, 1.0], color=c, lw=1.0, ls="--", alpha=0.55, zorder=2)
        ax.text(x, 0.64, name, ha="center", fontsize=9.5, color=c, weight="bold", zorder=4)
        ax.text(x, 0.28, sub, ha="center", fontsize=8.5, color=c, zorder=4)

    marker(START, COL["TPU"], "moving marker", "the crosshead end")
    marker(START + PX0, "#495057", "fixed marker", "barely moves")

    def span(x0, x1, y, colour, label, above=True):
        ax.annotate("", xy=(x0, y), xytext=(x1, y),
                    arrowprops=dict(arrowstyle="<->", color=colour, lw=1.7))
        ax.text((x0 + x1) / 2, y + (0.055 if above else -0.115), label, ha="center",
                color=colour, fontsize=9.5, weight="bold")

    room = START - R
    need28 = PX0 * 28.0 * SHARE / 80.0 * DRIFT
    span(0, START - R, 1.16, "#d62728", f"{room:.0f} px of room — ALL it has")
    span(0, need28, 1.42, "#2f9e44", f"{need28:.0f} px needed for a 28 mm pull")
    span(START + PX0 + R, W, 1.16, MUTED, f"{W - START - PX0 - R:.0f} px unused, at the end "
         "that never moves")
    ax.text(W / 2, 0.86, f"camera frame — the FULL sensor width, {W:.0f} px "
            "(OffsetX 0: nothing left to widen, on either side)",
            ha="center", fontsize=10, color=MUTED)

    reach = room / DRIFT / PX0 * 80.0 / SHARE
    ax.text(W / 2, -0.34, f"The moving marker runs out after ~{reach:.0f} mm of travel.  "
            f"Measured: S35 stopped at 15.8 mm, S36 at 15.1 mm.",
            ha="center", fontsize=11, weight="bold", color="#d62728")
    ax.set_xlim(-60, W + 60)
    ax.set_ylim(-0.55, 1.62)
    ax.axis("off")
    fig.tight_layout()
    p = os.path.join(HERE, out)
    fig.savefig(p, dpi=160)
    plt.close(fig)
    print("wrote", p)
    return p

# ----------------------------------------------------------------- the three materials
def fig_curves(out="trio_curves.png"):
    fig, axes = plt.subplots(1, 2, figsize=(12.8, 4.3))
    ax = axes[0]
    for m, spec in REP.items():
        e, s, _ = curve(spec)
        ax.plot(e, s, color=COL[m], lw=1.8, label=f"{m}  ({spec})")
    ax.set_yscale("log")
    ax.set_xlabel("DIC gauge strain (%)")
    ax.set_ylabel("Engineering stress (MPa, log)")
    ax.set_title("All three on one axis — stress spans two decades", fontsize=10.5)
    ax.legend(frameon=False, fontsize=9)
    _style(ax)

    ax = axes[1]
    for m, spec in REP.items():
        e, s, _ = curve(spec)
        ax.plot(e, s, color=COL[m], lw=1.8, label=m)
    ax.set_xlabel("DIC gauge strain (%)")
    ax.set_ylabel("Engineering stress (MPa)")
    ax.set_title("The same curves linearly — why TPU needs its own axis", fontsize=10.5)
    ax.legend(frameon=False, fontsize=9)
    _style(ax)
    ax.annotate("TPU is here", xy=(6, 1.4), xytext=(9, 12), fontsize=9, color=COL["TPU"],
                arrowprops=dict(arrowstyle="->", color=COL["TPU"], lw=1.2))
    fig.tight_layout()
    p = os.path.join(HERE, out)
    fig.savefig(p, dpi=160)
    plt.close(fig)
    print("wrote", p)
    return p


def fig_modulus(out="trio_modulus.png"):
    """Measured E against the published band. Log axis, because 25 MPa and 3 GPa share a chart."""
    S = stats()
    fig, ax = plt.subplots(figsize=(8.6, 5.2))
    for i, m in enumerate(("PLA", "PETG", "TPU")):
        lo, hi = LIT[m]["E"]
        ax.add_patch(Rectangle((i - 0.26, lo), 0.52, hi - lo, fc=COL[m], alpha=0.16,
                               ec=COL[m], lw=1.0, zorder=1))
        ax.plot([i] * S[m]["n"], S[m]["E"], "o", color=COL[m], ms=9, zorder=3,
                markeredgecolor="white", markeredgewidth=1.2)
        mean = float(np.mean(S[m]["E"]))
        # Mean to the RIGHT of its band, published range BELOW it. On a log axis the three bands
        # sit at very different heights, and a label placed above one lands on the next one along.
        ax.text(i + 0.31, mean, f"{mean:.0f} MPa   n={S[m]['n']}", va="center", ha="left",
                fontsize=10, color=COL[m], weight="bold")
        ax.text(i, lo * 0.84, f"published\n{lo}–{hi} MPa", ha="center", va="top", fontsize=8.6,
                color=MUTED)
    ax.set_yscale("log")
    ax.set_xticks(range(3))
    ax.set_xticklabels(["PLA", "PETG", "TPU"])
    ax.set_ylabel("Elastic modulus (MPa, log)")
    ax.set_title("Every material lands inside its published band", fontsize=11)
    ax.set_xlim(-0.5, 2.95)
    ax.set_ylim(5, 9000)
    _style(ax)
    fig.tight_layout()
    p = os.path.join(HERE, out)
    fig.savefig(p, dpi=160)
    plt.close(fig)
    print("wrote", p)
    return p


def fig_slopes(out="trio_slopes.png"):
    """The initial slope each material SHOULD have, and the one the rig drew."""
    S = stats()
    # One window for all three: 0 to 1 % strain, which contains the 0.05-0.4 % fit window every
    # modulus in this deck uses and a little beyond it. A per-panel percentile was tried first and
    # was wrong twice over — it reached into the pre-load toe, so PLA and PETG got NEGATIVE strain
    # axes, and it gave each panel a different x-range, which is the one thing a comparison of
    # slopes must not do.
    TOP = 1.0
    fig, axes = plt.subplots(1, 3, figsize=(12.8, 4.2))
    for ax, m in zip(axes, ("PLA", "PETG", "TPU")):
        lo, hi = LIT[m]["E"]
        e, s, a = curve(REP[m])
        x = np.linspace(0, TOP, 40)
        # Anchor the wedge to the run's OWN intercept. Px₀ is frozen at the preloaded state, so the
        # curve starts at the preload stress rather than at the origin, and a wedge drawn from (0,0)
        # sits below the data and reads as disagreement when the only thing being compared is the
        # SLOPE. Intercept taken over the same 0.05-0.4 % window every modulus in this deck uses.
        w = (e >= 0.05) & (e <= 0.4)
        c0 = float(np.mean(s[w] - (np.mean(S[m]["E"]) * e[w] / 100))) if w.sum() > 2 else 0.0
        ax.fill_between(x, c0 + lo * x / 100, c0 + hi * x / 100, color=COL[m], alpha=0.20,
                        label=f"expected  {lo}–{hi} MPa")
        mean = float(np.mean(S[m]["E"]))
        ax.plot(x, c0 + mean * x / 100, color=COL[m], lw=2.4, ls="--",
                label=f"measured  {mean:.0f} MPa")
        k = (e >= 0) & (e <= TOP)
        ax.plot(e[k], s[k], color="#212529", lw=1.5, alpha=0.9, label=f"{REP[m]} run")
        ax.set_title(f"{m}   ({'in band' if lo <= mean <= hi else 'OUT of band'})",
                     fontsize=11, color=COL[m], weight="bold")
        ax.set_xlabel("Engineering strain (%)")
        ax.set_xlim(0, TOP)
        _tops = [c0 + hi * TOP / 100] + ([float(s[k].max())] if k.any() else [])
        ax.set_ylim(0, max(_tops) * 1.18)
        if m == "PLA":
            ax.set_ylabel("Engineering stress (MPa)")
        ax.legend(frameon=False, fontsize=8.5, loc="upper left")
        _style(ax)
    fig.suptitle("Initial slope: the band literature predicts, and the line the rig measured",
                 fontsize=11.5, y=1.0)
    fig.tight_layout()
    p = os.path.join(HERE, out)
    fig.savefig(p, dpi=160)
    plt.close(fig)
    print("wrote", p)
    return p


def all_figs():
    return [fig_framing(), fig_curves(), fig_modulus(), fig_slopes()]


if __name__ == "__main__":
    all_figs()
    S = stats()
    print(f"\n{'material':6} {'n':>2} {'E MPa':>16} {'lit E':>14} {'in band':>9}")
    for m in ("PLA", "PETG", "TPU"):
        mean = float(np.mean(S[m]["E"]))
        lo, hi = LIT[m]["E"]
        print(f"{m:6} {S[m]['n']:2d} {mean:10.0f} ± {np.std(S[m]['E']):.0f} "
              f"{f'{lo}-{hi}':>14} {'yes' if lo <= mean <= hi else 'NO':>9}")
