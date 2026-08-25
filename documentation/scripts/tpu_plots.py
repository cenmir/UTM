"""Figures for the TPU pair, S35 and S36, compared over the SAME travel.

  tpu_pair.png   strain vs travel, stress vs strain, and the two moduli — over the common range

Both runs stop where the DIC stops, not where the specimen does: the marker reaches the edge of
the frame at about 15 mm of crosshead travel on this camera setup, which cannot be moved. So the
honest comparison is over the travel BOTH runs tracked, and that is what is drawn here.

Every number is read from the CSVs through utm_analysis — nothing is typed in.
"""
import os
import sys

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt                                       # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(ROOT, "Software", "UTM_PyQt6"))
from utm_analysis import read_csv, analyze, linfit                    # noqa: E402

TESTS = {
    "S35": os.path.join(ROOT, "Software", "UTM_PyQt6", "8.6.20 - Tensile test to Failure",
                        "Specimen_S35_V5_TPU_Spray_Video14", "UTM_Test_20260824_151910.csv"),
    "S36": os.path.join(ROOT, "Software", "UTM_PyQt6", "8.6.20 - Tensile test to Failure",
                        "Specimen_S36_V5_TPU_Spray", "UTM_Test_20260824_184604.csv"),
}
GRID = "#DDDDDD"
COL = {"S35": "#e8590c", "S36": "#1f77b4"}
MUTED = "#666666"
AREA = GAUGE = 80.0


def _style(ax):
    ax.grid(True, color=GRID, lw=0.6)
    ax.set_axisbelow(True)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)


def load():
    """Tracked samples only, with the recorded preload added back into the stress."""
    out = {}
    for k, path in TESTS.items():
        rows = read_csv(path)
        a = analyze(path, AREA, GAUGE)
        ok = [r for r in rows if r["lpx"] > 100]
        out[k] = {
            "pos": np.array([r["pos"] for r in ok]),
            "ec": np.array([r["ec"] for r in ok]),
            "sig": np.array([(r["F"] + a["anchor"]) / AREA for r in ok]),
            "E": a["E"] * 1000.0, "R2": a["E_R2"], "anchor": a["anchor"],
        }
    return out


def fig_pair(out="tpu_pair.png"):
    d = load()
    # The common range: neither run gets credit for travel the other could not track.
    cut = min(d[k]["pos"].max() for k in d)
    fig, axes = plt.subplots(1, 3, figsize=(13.2, 4.0))

    ax = axes[0]
    for k in ("S35", "S36"):
        m = d[k]["pos"] <= cut
        ax.plot(d[k]["pos"][m], d[k]["ec"][m] * 100, color=COL[k], lw=1.6, label=k)
    ax.axvline(cut, color=MUTED, ls=":", lw=1.0)
    ax.text(cut, ax.get_ylim()[1] * 0.05, f"  DIC ends\n  {cut:.1f} mm", color=MUTED, fontsize=8,
            va="bottom")
    ax.set_xlabel("Crosshead travel (mm)")
    ax.set_ylabel("DIC gauge strain (%)")
    ax.set_title("Strain vs travel — the same range for both", fontsize=10)
    ax.legend(frameon=False, fontsize=9)
    _style(ax)

    ax = axes[1]
    for k in ("S35", "S36"):
        m = d[k]["pos"] <= cut
        ax.plot(d[k]["ec"][m] * 100, d[k]["sig"][m], color=COL[k], lw=1.6, label=k)
    ax.set_xlabel("DIC gauge strain (%)")
    ax.set_ylabel("Engineering stress (MPa)")
    ax.set_title("Stress vs strain — still rising, no peak", fontsize=10)
    ax.legend(frameon=False, fontsize=9)
    _style(ax)

    # Agreement, as a number rather than two lines that look alike.
    ax = axes[2]
    grid = np.linspace(0.01, min(d[k]["ec"][d[k]["pos"] <= cut].max() for k in d), 40)
    s = {k: np.interp(grid, d[k]["ec"][d[k]["pos"] <= cut], d[k]["sig"][d[k]["pos"] <= cut])
         for k in d}
    diff = (s["S36"] - s["S35"]) / s["S35"] * 100
    ax.axhline(0, color=MUTED, lw=0.8)
    ax.plot(grid * 100, diff, color="#2f9e44", lw=1.6)
    ax.fill_between(grid * 100, -5, 5, color="#2f9e44", alpha=0.08)
    ax.set_xlabel("DIC gauge strain (%)")
    ax.set_ylabel("S36 − S35  (% of S35)")
    ax.set_ylim(-12, 12)
    ax.set_title(f"Repeatability: within ±{np.abs(diff).max():.0f} % everywhere", fontsize=10)
    _style(ax)
    ax.text(0.98, 0.04, f"E: {d['S35']['E']:.1f} vs {d['S36']['E']:.1f} MPa"
                        f"  ({abs(d['S36']['E'] - d['S35']['E']) / d['S35']['E'] * 100:.1f} % apart)",
            transform=ax.transAxes, ha="right", fontsize=9, color=MUTED)

    fig.tight_layout()
    p = os.path.join(HERE, "..", "figures", out)
    fig.savefig(p, dpi=160)
    plt.close(fig)
    print(f"wrote {p}")
    return p, d, cut


if __name__ == "__main__":
    _, d, cut = fig_pair()
    print(f"common travel range: 0 - {cut:.2f} mm")
    for k, v in d.items():
        m = v["pos"] <= cut
        print(f"  {k}: E {v['E']:.1f} MPa (R2 {v['R2']:.4f}), anchor {v['anchor']:.0f} N, "
              f"max strain in range {v['ec'][m].max() * 100:.2f} %, "
              f"max stress {v['sig'][m].max():.3f} MPa")
