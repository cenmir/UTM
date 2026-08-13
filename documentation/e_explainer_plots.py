import os as _os  # [doc-folder] run from repo root so the test CSVs resolve
_os.chdir(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '..'))
"""Figures for the 'how E is calculated' explainer deck.

Two pictures, both from the SAME real test (V6d / S11, 100 % infill):
  e_fig_window.png   where on the curve the modulus is measured
  e_fig_riserun.png  the rise/run triangle, drawn on the actual data points

Outputs into documentation/. Numbers are recomputed from the CSV, never typed in.
"""
import sys
from statistics import median
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

sys.path.insert(0, _os.path.join("Software", "UTM_PyQt6"))
import utm_analysis as UA

CSV = _os.path.join("Software", "UTM_PyQt6", "8.6.20 - Tensile test to Failure",
                    "Specimen_S11_V2_Spray", "UTM_Test_20260625_154219_V6d_TensionFailure.csv")
OUT = "documentation"

BLUE, RED, GREEN, GREY = "#1f77b4", "#d62728", "#2a9d5c", "#888888"


def load():
    meta = UA.read_meta(CSV)
    area = meta.get("area", 80.0)
    data = UA.read_csv(CSV)
    r = UA.analyze(CSV, area=area)
    base = sorted(d["pos"] for d in data[:30])[15]
    mv = next(i for i, d in enumerate(data) if d["pos"] > base + 0.005)
    ec0 = median([d["ec"] for d in data[:mv] if d["lpx"] > 100] or [0.0])
    for d in data:
        d["sig"] = (d["F"] + r["anchor"]) / area
        d["ecz"] = d["ec"] - ec0
    test = [d for d in data[mv:r["fr_i"]] if d["lpx"] > 100]
    win = [d for d in test if 0.0005 <= d["ecz"] <= 0.004]
    E, c1, r2 = UA.linfit([d["ecz"] for d in win], [d["sig"] for d in win])
    return r, test, win, E, c1, r2, area


R, TEST, WIN, E, C1, R2, AREA = load()
EPS = [d["ecz"] for d in WIN]
SIG = [d["sig"] for d in WIN]


def fig_window():
    """The whole test, with the measured region marked — 'we only use this bit'."""
    fig, ax = plt.subplots(figsize=(6.6, 4.9))
    ax.plot([d["ecz"] * 100 for d in TEST], [d["sig"] for d in TEST], "-", color=GREY, lw=2.2)
    ax.axvspan(0.05, 0.40, color=BLUE, alpha=0.16, zorder=0)
    ax.plot([e * 100 for e in EPS], SIG, "-", color=BLUE, lw=4, solid_capstyle="round")
    xr = [0, 1.15]
    ax.plot(xr, [E * (x / 100) + C1 for x in xr], "--", color=RED, lw=1.9)

    ax.annotate("the straight part\n— this is what E measures",
                xy=(0.30, E * 0.003 + C1), xytext=(1.15, 12),
                fontsize=11, color=BLUE, weight="bold",
                arrowprops=dict(arrowstyle="->", color=BLUE, lw=1.6))
    ax.annotate("the material starts to give;\nno longer a straight line",
                xy=(1.9, 43.5), xytext=(1.35, 27), fontsize=10.5, color="#444444",
                arrowprops=dict(arrowstyle="->", color="#444444", lw=1.4))
    ax.plot(R["uts_ec"], R["uts"], "o", color="black", ms=7)
    ax.annotate(f"UTS {R['uts']:.1f} MPa", xy=(R["uts_ec"], R["uts"]),
                xytext=(R["uts_ec"] + 0.35, R["uts"] + 1.5), fontsize=10)

    ax.set_xlabel("Engineering strain, DIC  (%)   — how much the gauge stretched", fontsize=10.5)
    ax.set_ylabel("Engineering stress  (MPa)   — force ÷ area", fontsize=10.5)
    ax.set_xlim(-0.15, 5.2); ax.set_ylim(0, 52)
    ax.grid(alpha=0.3)
    ax.set_title("E is measured ONLY on the straight part, at the very start",
                 fontsize=12, weight="bold")
    fig.tight_layout()
    p = _os.path.join(OUT, "e_fig_window.png")
    fig.savefig(p, dpi=170); plt.close(fig)
    print("  ", p)


def fig_riserun():
    """Rise and run drawn as a triangle on the real points."""
    fig, ax = plt.subplots(figsize=(7.4, 5.2))
    ax.plot([e * 100 for e in EPS], SIG, "o", color=BLUE, ms=5.5, zorder=3,
            label=f"the {len(WIN)} measurements")
    x1, x2 = 0.05, 0.40
    y1, y2 = E * (x1 / 100) + C1, E * (x2 / 100) + C1
    ax.plot([x1, x2], [y1, y2], "-", color=RED, lw=2.6, zorder=4,
            label="the best straight line through them")

    # the triangle
    ax.plot([x1, x2], [y1, y1], "-", color=GREEN, lw=2.4, zorder=5)
    ax.plot([x2, x2], [y1, y2], "-", color=GREEN, lw=2.4, zorder=5)
    ax.annotate("", xy=(x2, y1), xytext=(x1, y1),
                arrowprops=dict(arrowstyle="<->", color=GREEN, lw=2.4))
    ax.annotate("", xy=(x2, y2), xytext=(x2, y1),
                arrowprops=dict(arrowstyle="<->", color=GREEN, lw=2.4))

    ax.text((x1 + x2) / 2, y1 - 1.05, "RUN  =  how much it STRETCHED",
            ha="center", fontsize=12, weight="bold", color=GREEN)
    ax.text((x1 + x2) / 2, y1 - 1.75, "0.0035   (0.05 % → 0.40 % strain)",
            ha="center", fontsize=11, color=GREEN)
    ax.text(x2 + 0.012, (y1 + y2) / 2, f"RISE  =  how much\nthe STRESS grew\n\n{y2 - y1:.2f} MPa",
            va="center", fontsize=12, weight="bold", color=GREEN)

    ax.text(0.055, y2 - 0.6,
            f"E  =  RISE ÷ RUN\n   =  {y2 - y1:.2f} MPa ÷ 0.0035\n   =  {E:.0f} MPa"
            f"  =  {E/1000:.2f} GPa",
            fontsize=13, weight="bold", color=RED, va="top",
            bbox=dict(boxstyle="round,pad=0.5", fc="#fff4f4", ec=RED, lw=1.4))

    ax.set_xlabel("Engineering strain, DIC  (%)", fontsize=11)
    ax.set_ylabel("Engineering stress  (MPa)", fontsize=11)
    # ylim leaves room UNDER the run arrow for its two-line caption, and the legend goes top-right
    # where nothing else lives — bottom-right is where the RUN caption has to sit.
    ax.set_xlim(0.02, 0.52); ax.set_ylim(5.0, 18.8)
    ax.grid(alpha=0.3); ax.legend(loc="upper right", fontsize=9)
    ax.set_title("Rise ÷ Run — that slope IS Young's modulus", fontsize=13, weight="bold")
    fig.tight_layout()
    p = _os.path.join(OUT, "e_fig_riserun.png")
    fig.savefig(p, dpi=170); plt.close(fig)
    print("  ", p)


# --------------------------------------------------------------------------------------------
# The two grey lines in the report's stress-strain panel, labelled ON the lines themselves.
# Built from S16 — the specimen in the report screenshot — so the picture matches the PDF the
# operator is actually holding. Its E (1.88 GPa) is low, which is WHY sigma_y lands almost on
# UTS here: a shallower elastic line takes longer to catch the curve.
S16_CSV = _os.path.join("Software", "UTM_PyQt6", "8.6.20 - Tensile test to Failure",
                        "Specimen_S16_V2_Spray", "UTM_Test_20260728_200615.csv")
MAGENTA, DARKGREY = "#b03060", "#333333"


def _s16():
    meta = UA.read_meta(S16_CSV)
    r = UA.analyze(S16_CSV, area=meta.get("area", 80.0))
    return r, r["E"], r["c1"]


def fig_two_lines():
    """Which line is which — labels sit ON the lines, not in a legend."""
    r, E16, c16 = _s16()
    fig, (ax, az) = plt.subplots(1, 2, figsize=(12.6, 5.35),
                                 gridspec_kw={"width_ratios": [1.62, 1]})
    xs, ys = zip(*r["curve"])

    def draw(a, xmax_line):
        a.plot(xs, ys, "-", color=BLUE, lw=2.4, zorder=3)
        xe = [0.0, 0.6]
        a.plot(xe, [10 * E16 * x + c16 for x in xe], "--", color=DARKGREY, lw=2.6, zorder=4)
        a.plot([0.2, xmax_line], [10 * E16 * (x - 0.2) + c16 for x in (0.2, xmax_line)],
               ":", color=MAGENTA, lw=2.8, zorder=4)
        a.grid(alpha=0.3)
        a.set_xlabel("Engineering strain, DIC  (%)", fontsize=10.5)
        a.set_ylabel("Engineering stress  (MPa)", fontsize=10.5)

    # ---- main view ----
    draw(ax, 3.0)
    ax.set_xlim(-0.08, 6.2); ax.set_ylim(0, 56)
    ax.plot(r["sy_ec"], r["sy"], "s", color="#2a9d5c", ms=12, mec="black", mew=0.9, zorder=6)

    ax.annotate("①  ELASTIC FIT\nshort dashed line, slope = E\nit hugs the curve at the start",
                xy=(0.42, 10 * E16 * 0.42 + c16), xytext=(1.05, 5.0),
                fontsize=11.5, weight="bold", color=DARKGREY,
                arrowprops=dict(arrowstyle="->", color=DARKGREY, lw=2))
    ax.annotate("②  0.2 % OFFSET LINE\nthe SAME line moved 0.2 % right\nthe long dotted one",
                xy=(2.15, 10 * E16 * (2.15 - 0.2) + c16), xytext=(3.05, 24.0),
                fontsize=11.5, weight="bold", color=MAGENTA,
                arrowprops=dict(arrowstyle="->", color=MAGENTA, lw=2))
    ax.annotate(f"σ_y = {r['sy']:.1f} MPa\nwhere ② meets the curve",
                xy=(r["sy_ec"], r["sy"]), xytext=(3.15, 47.5),
                fontsize=11.5, weight="bold", color="#2a9d5c",
                arrowprops=dict(arrowstyle="->", color="#2a9d5c", lw=2))
    ax.set_title("the report's stress–strain panel", fontsize=12, weight="bold")

    # ---- zoom on the start, where the shift is visible ----
    draw(az, 0.95)
    az.set_xlim(-0.02, 0.95); az.set_ylim(0, 22)
    y0 = c16
    az.annotate("", xy=(0.2, y0), xytext=(0.0, y0),
                arrowprops=dict(arrowstyle="<->", color=MAGENTA, lw=2.4))
    az.text(0.10, y0 - 2.1, "0.2 %", ha="center", fontsize=12.5, weight="bold", color=MAGENTA)
    # Leaders, not floating glyphs: a bare ① parked in white space is exactly the ambiguity this
    # figure exists to remove.
    az.annotate("①  ELASTIC FIT", xy=(0.34, 10 * E16 * 0.34 + c16), xytext=(0.03, 19.0),
                fontsize=12.5, weight="bold", color=DARKGREY,
                arrowprops=dict(arrowstyle="->", color=DARKGREY, lw=2))
    az.annotate("②  0.2 % OFFSET\n(same slope — parallel)",
                xy=(0.80, 10 * E16 * (0.80 - 0.2) + c16), xytext=(0.40, 6.4),
                fontsize=12.5, weight="bold", color=MAGENTA,
                arrowprops=dict(arrowstyle="->", color=MAGENTA, lw=2))
    az.set_title("zoomed on the start", fontsize=12, weight="bold")

    fig.suptitle("① and ② are the SAME slope (= E).  ② is just shifted 0.2 % to the right.",
                 fontsize=13, weight="bold")
    fig.tight_layout()
    p = _os.path.join(OUT, "e_fig_two_lines.png")
    fig.savefig(p, dpi=170); plt.close(fig)
    print("  ", p)
    return r


if __name__ == "__main__":
    print("figures:")
    fig_window()
    fig_riserun()
    r16 = fig_two_lines()
    print(f"\n  V6d : E={E:.1f} MPa ({E/1000:.3f} GPa) · c1={C1:.3f} MPa · R2={R2:.5f} · n={len(WIN)}")
    print(f"  S16 : E={r16['E']:.2f} GPa · sy={r16['sy']:.1f} MPa @ {r16['sy_ec']:.2f} % · "
          f"UTS={r16['uts']:.1f} MPa @ {r16['uts_ec']:.2f} %")
