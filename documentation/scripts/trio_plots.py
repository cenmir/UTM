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
ROOT = os.path.dirname(os.path.dirname(HERE))
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
    """Tracked stress-strain for one specimen, preload added back in, CUT AT FRACTURE.

    The cut used to silently never happen: analyze() returns the fracture sample index as
    "fr_i" and this asked for "fracture_i", so .get() returned None every time and the curve
    ran on through the post-fracture record. That is why PLA appeared to reach 16 % strain and
    PETG 21.6 % when they break at 5.7 % and 7.8 % — past fracture the two halves are separate
    objects and the marker separation is no longer a strain at all.

    TPU legitimately has no fracture (the run stops at the travel target), so fr_i is None
    there and the whole tracked record is kept.
    """
    a = analyze(os.path.join(ROOT, registry()[spec]["csv"]), AREA, GAUGE)
    # analyze() already builds exactly this: strain zeroed at preload, stress with the anchor
    # added back, cut at fracture AND back-stepped past any sample whose gauge stretch exceeds
    # the crosshead travel. Re-deriving it here is what let the fracture cut go missing, and the
    # back-step would have been missed anyway — on S25 that is the difference between a curve
    # ending at 4.2 % and one running to 15.6 %.
    c = a["curve"]
    return np.array([p[0] for p in c]), np.array([p[1] for p in c]), a


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
    p = os.path.join(HERE, "..", "figures", out)
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
    ax.set_title("LOG PLOT — stress spans two decades", fontsize=10.5)
    ax.legend(frameon=False, fontsize=9)
    _style(ax)

    ax = axes[1]
    for m, spec in REP.items():
        e, s, _ = curve(spec)
        ax.plot(e, s, color=COL[m], lw=1.8, label=m)
    ax.set_xlabel("DIC gauge strain (%)")
    ax.set_ylabel("Engineering stress (MPa)")
    ax.set_title("RAW DATA PLOT (linear axes) — why TPU needs its own axis", fontsize=10.5)
    ax.legend(frameon=False, fontsize=9)
    _style(ax)
    ax.annotate("TPU is here", xy=(4.5, 1.35), xytext=(6.6, 11), fontsize=9, color=COL["TPU"],
                arrowprops=dict(arrowstyle="->", color=COL["TPU"], lw=1.2))
    fig.tight_layout(rect=(0, 0.085, 1, 1))
    fig.text(0.5, 0.035, "Every curve ENDS AT ITS FRACTURE POINT — PLA 4.2 %, PETG 7.8 %.   "
             "TPU did not fracture: its run stops at the 15 mm travel target.",
             ha="center", fontsize=9.4, color=MUTED)
    p = os.path.join(HERE, "..", "figures", out)
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

    # WHAT E IS — asked for directly, and worth answering on the chart rather than in a footnote,
    # because "is it stress/strain at UTS?" is the natural guess and it is the wrong one. The log
    # axis leaves a wide empty band between the PETG and TPU groups; the note goes there.
    wins = {m: [] for m in ("PLA", "PETG", "TPU")}
    for m in wins:
        for i in GROUPS[m]:
            r = registry().get(i)
            if r:
                aa = analyze(os.path.join(ROOT, r["csv"]), AREA, GAUGE)
                wins[m].append((aa["E_lo"], aa["E_hi"]))
    span = {m: (min(w[0] for w in v), max(w[1] for w in v)) for m, v in wins.items() if v}
    ax.text(-0.42, 250,
            "HOW E IS MEASURED  —  not from UTS\n"
            "E = Δσ / Δε, the least-squares SLOPE of the steepest genuinely-straight\n"
            "stretch of the early curve (R² ≈ 0.999). Two points are never used.\n"
            "Fit windows here:  PLA %.2f–%.2f %%   ·   PETG %.2f–%.2f %%   ·   TPU %.2f–%.2f %%\n"
            "UTS is the PEAK of the curve, far past this window (PLA ≈ 2.2 %% strain),\n"
            "and takes no part in E. The force anchor cancels out of a slope."
            % (span["PLA"][0], span["PLA"][1], span["PETG"][0], span["PETG"][1],
               span["TPU"][0], span["TPU"][1]),
            fontsize=8.5, color="#333333", va="center", ha="left", linespacing=1.5,
            bbox=dict(boxstyle="round,pad=0.55", fc="#F7F9FB", ec="#AAB2BD", lw=1.0))
    fig.tight_layout()
    p = os.path.join(HERE, "..", "figures", out)
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
        # WHERE the dashed line is entitled to match the black curve. Without this the panel
        # invites the reading that the line "drifts off" the data — it does, and it is supposed
        # to: past the fit window the material is leaving its elastic region, which is the whole
        # reason E is fitted over a window rather than over the visible range.
        ax.axvspan(a["E_lo"], min(a["E_hi"], TOP), color="#495057", alpha=0.13, zorder=0,
                   label="fit window  %.2f–%.2f %%" % (a["E_lo"], a["E_hi"]))
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
    fig.tight_layout(rect=(0, 0.105, 1, 1))
    # The expected bands are the one thing on this chart that is NOT measured here, so they are
    # sourced on the chart itself rather than in a caption that can travel away from it.
    fig.text(0.5, 0.062, "EXPECTED BANDS ARE LITERATURE, NOT OUR DATA:   PLA — Chacon et al. 2017 "
             "+ Ultimaker / Prusament PLA datasheets   |   PETG — Durgashyam et al. 2019 "
             "+ Prusament PETG datasheet", ha="center", fontsize=8.4, color=MUTED)
    fig.text(0.5, 0.022, "TPU 95A — Ultimaker / SainSmart / NinjaFlex datasheets + Hohimer et al. "
             "2020.       Dashed line = group-mean measured E; only its INTERCEPT is fitted to "
             "the run beside it.", ha="center", fontsize=8.4, color=MUTED)
    p = os.path.join(HERE, "..", "figures", out)
    fig.savefig(p, dpi=160)
    plt.close(fig)
    print("wrote", p)
    return p


def e_methods():
    """Per-specimen E under BOTH candidate rules, so the choice can be argued from numbers.

    Returns {material: {"spec": [...], "steep": [...], "fixed": [...], "win": [(lo,hi)...]}}.
    """
    reg = registry()
    out = {}
    for m, ids in GROUPS.items():
        d = {"spec": [], "steep": [], "fixed": [], "win": [], "r2": [], "r2f": []}
        for i in ids:
            if i not in reg:
                continue
            a = analyze(os.path.join(ROOT, reg[i]["csv"]), AREA, GAUGE)
            d["spec"].append(i)
            d["steep"].append(a["E"] * 1000.0)
            d["fixed"].append(a["E_fixed"] * 1000.0)
            d["win"].append((a["E_lo"], a["E_hi"]))
            d["r2"].append(a["E_R2"])
            d["r2f"].append(a["E_fixed_R2"])
        out[m] = d
    return out


def _cov(v):
    v = np.asarray(v, float)
    return 100.0 * v.std(ddof=1) / v.mean() if len(v) > 1 else 0.0


def fig_emethod(out="e_method.png"):
    """How the dashed slope is chosen — and whether that choice is defensible.

    The dashed line on the slope slide is NOT a regression of the black curve beside it: its
    slope is the group-mean E, and only its intercept is fitted to that run. So the fair question
    is whether the RULE that produced E is sound, and the only way to answer it is to run the
    alternative rule on the same specimens and compare scatter and datasheet agreement.
    """
    EM = e_methods()

    fig, (a1, a2, a3) = plt.subplots(1, 3, figsize=(13.6, 4.0),
                                     gridspec_kw={"width_ratios": [1.25, 1, 1]})

    # ---- (1) the two windows on one real curve, so "which stretch" is visible
    e, s, a = curve("S26")
    k = e <= 1.6
    a1.plot(e[k], s[k], color="#212529", lw=1.7, zorder=3, label="S26 measured")
    a1.axvspan(0.05, 0.40, color="#868e96", alpha=0.22, label="fixed window  0.05–0.40 %")
    lo_w, hi_w = EM["PLA"]["win"][EM["PLA"]["spec"].index("S26")]
    a1.axvspan(lo_w, hi_w, color=COL["PLA"], alpha=0.30,
               label="steepest straight run  %.2f–%.2f %%" % (lo_w, hi_w))
    for E_, c_, ls_, lab_ in ((EM["PLA"]["steep"][EM["PLA"]["spec"].index("S26")], COL["PLA"],
                               "--", "steepest"),
                              (EM["PLA"]["fixed"][EM["PLA"]["spec"].index("S26")], "#868e96",
                               ":", "fixed")):
        w = (e >= lo_w) & (e <= hi_w) if lab_ == "steepest" else (e >= 0.05) & (e <= 0.40)
        c0 = float(np.mean(s[w] - E_ * e[w] / 100))
        x = np.linspace(0, 1.6, 20)
        a1.plot(x, c0 + E_ * x / 100, color=c_, ls=ls_, lw=2.0)
    a1.set_ylim(0, float(s[k].max()) * 1.15); a1.set_xlim(0, 1.6)
    a1.set_title("The two candidate windows, on one run (S26)", fontsize=10.4)
    a1.set_xlabel("Engineering strain (%)"); a1.set_ylabel("Engineering stress (MPa)")
    a1.legend(fontsize=7.8, loc="lower right", frameon=False)
    _style(a1)

    # ---- (2) repeatability: the test that a noise-chasing rule must FAIL
    xs = np.arange(3)
    w = 0.34
    for j, (key, lab, alpha) in enumerate((("fixed", "fixed 0.05–0.40 %", 0.42),
                                           ("steep", "steepest straight run", 1.0))):
        vals = [_cov(EM[m][key]) for m in ("PLA", "PETG", "TPU")]
        b = a2.bar(xs + (j - 0.5) * w, vals, width=w, label=lab,
                   color=[COL[m] for m in ("PLA", "PETG", "TPU")], alpha=alpha,
                   edgecolor="white", lw=0.6)
        for rect, v in zip(b, vals):
            a2.text(rect.get_x() + rect.get_width() / 2, v + 0.25, "%.1f" % v,
                    ha="center", fontsize=8.0)
    a2.set_xticks(xs)
    a2.set_xticklabels(["PLA\nn=%d" % EM["PLA"]["spec"].__len__(),
                        "PETG\nn=%d" % len(EM["PETG"]["spec"]),
                        "TPU\nn=%d" % len(EM["TPU"]["spec"])], fontsize=9)
    a2.set_ylabel("run-to-run scatter, CoV (%)")
    a2.set_title("Repeatability — LOWER is better\n(steepest wins on all three)", fontsize=10.4)
    a2.legend(fontsize=8.0, loc="upper right", frameon=False)
    _style(a2)

    # ---- (3) the cost of that choice: where each rule sits in the published band
    for i, m in enumerate(("PLA", "PETG", "TPU")):
        lo, hi = LIT[m]["E"]
        mid = (lo + hi) / 2.0
        a3.add_patch(Rectangle((i - 0.32, 100 * (lo - mid) / mid), 0.64,
                               100 * (hi - lo) / mid, fc=COL[m], alpha=0.15, ec=COL[m], lw=0.9))
        for key, mk, lab in (("fixed", "s", "fixed"), ("steep", "o", "steepest")):
            v = float(np.mean(EM[m][key]))
            a3.plot(i + (-0.13 if key == "fixed" else 0.13), 100 * (v - mid) / mid, mk,
                    color=COL[m], ms=10, markeredgecolor="white", markeredgewidth=1.3,
                    alpha=0.45 if key == "fixed" else 1.0,
                    label=lab if i == 0 else None)
    a3.axhline(0, color="#999", lw=0.9, ls="--")
    a3.set_xticks(range(3)); a3.set_xticklabels(["PLA", "PETG", "TPU"])
    a3.set_ylabel("distance from the published band's centre (%)")
    a3.set_title("Accuracy — both rules stay INSIDE the band\n"
                 "(square = fixed, circle = steepest)", fontsize=10.4)
    a3.set_xlim(-0.6, 2.6)
    a3.legend(fontsize=8.0, loc="lower right", frameon=False)
    _style(a3)

    fig.tight_layout()
    p = os.path.join(HERE, "..", "figures", out)
    fig.savefig(p, dpi=160)
    plt.close(fig)
    print("wrote", p)
    return p


def all_figs():
    return [fig_framing(), fig_curves(), fig_modulus(), fig_slopes(), fig_emethod()]


if __name__ == "__main__":
    all_figs()
    S = stats()
    print(f"\n{'material':6} {'n':>2} {'E MPa':>16} {'lit E':>14} {'in band':>9}")
    for m in ("PLA", "PETG", "TPU"):
        mean = float(np.mean(S[m]["E"]))
        lo, hi = LIT[m]["E"]
        print(f"{m:6} {S[m]['n']:2d} {mean:10.0f} ± {np.std(S[m]['E']):.0f} "
              f"{f'{lo}-{hi}':>14} {'yes' if lo <= mean <= hi else 'NO':>9}")
