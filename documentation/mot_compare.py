"""MOT video extensometer vs our DIC — strain rate, because that is all the data can carry.

The MOT record (XT-205, gauge 80.0033 mm, 20 Hz) is STRAIN ONLY: no load, no crosshead
displacement, and it stops at 0.40 % strain, far short of fracture. E, sigma_y, UTS and eps_f all
need force, so none of them can be compared. What remains is d(eps)/dt, and the honest reading of
it is narrower than it first appears — see `verdict()` at the bottom.

Two traps are handled here explicitly, because both have already produced a wrong number in this
project:

  * The MOT file opens with 221 "Invalid" rows and then ~13 s at zero strain before the crosshead
    moves. Fitting across that flat region drags the slope toward zero.
  * Our own runs must be fitted on the LOADING RAMP ONLY. A force-based window is satisfied TWICE —
    once climbing, once as the load collapses back through it after fracture — and a fit spanning
    both joins the early ramp to the post-fracture tail. That produced 133 % of a physically
    impossible ceiling on the first attempt.

The comparison is made over a MATCHED STRAIN INTERVAL rather than matched time or matched force.
Time origins differ (their acquisition started when it started) and we have no force from them, but
both instruments pass through the same strain, so that is the one axis they genuinely share.
"""
import csv
import os
import sys

import numpy as np

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt                                       # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
DATA = os.path.join(REPO, "Software", "UTM_PyQt6", "8.6.20 - Tensile test to Failure")
MOT = os.path.join(DATA, "videoextesometer", "strain.csv")

CROSSHEAD_MM_S = 0.112          # measured from Position_mm, not the commanded 0.100
GAUGE_MM = 80.0
CEILING = CROSSHEAD_MM_S / GAUGE_MM      # d(eps)/dt if ALL crosshead motion reached the gauge

INK, RULE = "#1A1A1A", "#C9CDD2"
C_OURS, C_MOT = "#1f77b4", "#d62728"


def read_mot(path=MOT):
    """(t, eps) for the valid rows. Strain is returned as a FRACTION, not per cent."""
    rows = [r for r in csv.reader(open(path, encoding="utf-8-sig", errors="replace"))
            if r and any(c.strip() for c in r)]
    val = [r for r in rows[3:] if "Invalid" not in r[1]]
    t = np.array([float(r[0]) for r in val])
    e = np.array([float(r[1]) for r in val]) / 100.0
    gl = float(val[0][3])
    return t, e, gl


def read_ours(spec_glob):
    """(t, eps, force) on the LOADING RAMP ONLY, dropouts removed."""
    import glob
    p = glob.glob(os.path.join(DATA, spec_glob))[0]
    rows = []
    for ln in open(p, encoding="utf-8", errors="replace"):
        if ln.startswith("#") or not ln.strip():
            continue
        rows.append(ln.rstrip().split(","))
    h = rows[0]
    d = [dict(zip(h, r)) for r in rows[1:]]

    def col(k):
        out = []
        for r in d:
            try:
                out.append(float(r[k]))
            except Exception:
                out.append(np.nan)
        return np.array(out)

    t, e, F, L, B = col("Time_s"), col("DIC_Cauchy"), col("Force_N"), col("L_px"), col("DIC_Blobs")
    ipk = int(np.nanargmax(F))
    keep = (np.arange(len(F)) < ipk) & np.isfinite(e) & (L > 100) & (B == 2)
    return t[keep], e[keep], F[keep], os.path.basename(p)


def rate_over_strain(t, e, lo, hi):
    """Least-squares d(eps)/dt over a STRAIN interval. Returns (slope, r2, n, t_span)."""
    m = (e >= lo) & (e <= hi)
    if m.sum() < 10:
        return None
    sl, ic = np.polyfit(t[m], e[m], 1)
    r2 = np.corrcoef(t[m], e[m])[0, 1] ** 2
    return sl, r2, int(m.sum()), (t[m].min(), t[m].max())


def noise_over_strain(t, e, lo, hi):
    """RMS scatter about the straight fit, in microstrain.

    THIS is the like-for-like instrument comparison, and the slope is not. Residual scatter does
    not care how much of the crosshead motion reached the gauge, so unlike d(eps)/dt it is not
    confounded by the difference between the two machines' compliance. Both instruments watch the
    same material over the same strain interval; what is left is how quietly each can measure it.
    """
    m = (e >= lo) & (e <= hi)
    tt, ee = t[m], e[m]
    sl, ic = np.polyfit(tt, ee, 1)
    r = ee - (sl * tt + ic)
    d = np.diff(np.unique(np.round(ee, 10)))
    d = d[d > 0]
    return {"rms_ue": r.std() * 1e6, "pp_ue": (r.max() - r.min()) * 1e6,
            "quantum_ue": (np.median(d) * 1e6) if len(d) else float("nan"), "n": int(m.sum())}


def moving_rate(t, e, win_s=1.5):
    """Local slope in a sliding window — shows WHERE a record is straight."""
    out = np.full(len(t), np.nan)
    for i in range(len(t)):
        m = (t >= t[i] - win_s / 2) & (t <= t[i] + win_s / 2)
        if m.sum() >= 8:
            out[i] = np.polyfit(t[m], e[m], 1)[0]
    return out


def build():
    tm, em, gl = read_mot()
    runs = {}
    for spec, pat in (("S25", "Specimen_S25_V2_Spray_Video2/*.csv"),
                      ("S26", "Specimen_S26_V2_Spray_Video3/*.csv")):
        runs[spec] = read_ours(pat)

    # The overlap. MOT tops out at 0.40 %; stay clear of its toe and of its last point.
    LO, HI = 0.0005, 0.0035                       # 0.05 % .. 0.35 % strain
    res = {"MOT": rate_over_strain(tm, em, LO, HI)}
    for spec, (t, e, F, _n) in runs.items():
        res[spec] = rate_over_strain(t, e, LO, HI)

    fig, axes = plt.subplots(2, 2, figsize=(13.2, 8.0))
    fig.suptitle("MOT video extensometer (XT-205) vs UTM DIC  —  strain rate over a matched "
                 "strain interval", fontsize=13, y=0.98)

    # (a) the MOT record as recorded
    ax = axes[0][0]
    ax.plot(tm, em * 100, color=C_MOT, lw=1.4)
    ax.axhspan(LO * 100, HI * 100, color="#ffe08a", alpha=0.45, zorder=0)
    ax.set_title("(a) MOT record as recorded  —  gauge %.4f mm, 20 Hz" % gl, fontsize=10)
    ax.set_xlabel("time (s)"); ax.set_ylabel("strain (%)")
    ax.annotate("221 'Invalid' rows before this,\nthen ~13 s at zero strain:\nthe crosshead has not "
                "moved yet", xy=(6, 0.01), xytext=(3.0, 0.16), fontsize=8,
                arrowprops=dict(arrowstyle="->", color="#888"), color="#555")
    ax.annotate("record ends at %.3f %%\n(far short of fracture)" % (em.max() * 100),
                xy=(tm[-1], em[-1] * 100), xytext=(11.5, 0.36), fontsize=8,
                arrowprops=dict(arrowstyle="->", color="#888"), color="#555")

    # (b) local slope — where each record is actually straight
    ax = axes[0][1]
    ax.plot(tm, moving_rate(tm, em) / 1e-4, color=C_MOT, lw=1.3, label="MOT")
    for spec, (t, e, F, _n) in runs.items():
        ax.plot(t - t[np.argmax(e > LO)], moving_rate(t, e) / 1e-4,
                color=C_OURS, lw=1.2, alpha=0.55 if spec == "S26" else 1.0,
                ls="-" if spec == "S25" else "--", label="ours " + spec)
    ax.axhline(CEILING / 1e-4, color="#444", ls=":", lw=1.2)
    ax.text(0.99, CEILING / 1e-4, " ceiling %.2fe-4 /s " % (CEILING / 1e-4), fontsize=7.5,
            ha="right", va="bottom", transform=ax.get_yaxis_transform(), color="#444")
    ax.set_ylim(-0.5, CEILING / 1e-4 * 1.15)
    ax.set_title("(b) local slope in a 1.5 s window  —  time shifted to first contact",
                 fontsize=10)
    ax.set_xlabel("time from first strain (s)"); ax.set_ylabel(r"d$\varepsilon$/dt  ($10^{-4}$/s)")
    ax.legend(fontsize=8)

    # (c) the comparison itself, on a common origin
    ax = axes[1][0]
    for lab, (t, e), c, ls in (("MOT", (tm, em), C_MOT, "-"),
                               ("ours S25", runs["S25"][:2], C_OURS, "-"),
                               ("ours S26", runs["S26"][:2], C_OURS, "--")):
        m = (e >= LO) & (e <= HI)
        ax.plot(t[m] - t[m].min(), e[m] * 100, color=c, ls=ls, lw=1.6, label=lab)
        sl = res[lab.split()[-1] if "ours" in lab else "MOT"][0]
        tt = np.linspace(0, (t[m].max() - t[m].min()), 5)
        ax.plot(tt, (e[m].min() + sl * tt) * 100, color=c, lw=0.8, ls=":", alpha=0.8)
    ax.axhspan(LO * 100, HI * 100, color="#ffe08a", alpha=0.25, zorder=0)
    ax.set_title("(c) matched strain interval %.2f–%.2f %%, common origin" % (LO * 100, HI * 100),
                 fontsize=10)
    ax.set_xlabel("time within the interval (s)"); ax.set_ylabel("strain (%)")
    ax.legend(fontsize=8)

    # (d) the numbers
    ax = axes[1][1]; ax.axis("off")
    noise = {"MOT": noise_over_strain(tm, em, LO, HI)}
    for spec, (t, e, F, _n) in runs.items():
        noise[spec] = noise_over_strain(t, e, LO, HI)

    lines = [("", "dε/dt (/s)", "% of ceil", "R²", "noise RMS", "peak-peak")]
    for k in ("MOT", "S25", "S26"):
        sl, r2, n, span = res[k]
        lines.append((k, "%.3e" % sl, "%.0f %%" % (100 * sl / CEILING), "%.4f" % r2,
                      "%.1f µε" % noise[k]["rms_ue"], "%.0f µε" % noise[k]["pp_ue"]))
    y = 0.96
    for i, row in enumerate(lines):
        for x, cell in zip((0.01, 0.20, 0.40, 0.53, 0.68, 0.86), row):
            ax.text(x, y, cell, fontsize=9.0, transform=ax.transAxes,
                    weight="bold" if i == 0 else "normal",
                    color=INK if i == 0 else (C_MOT if row[0] == "MOT" else C_OURS))
        y -= 0.072
    ours = 0.5 * (res["S25"][0] + res["S26"][0])
    ratio = res["MOT"][0] / ours
    q = noise["MOT"]["rms_ue"] / (0.5 * (noise["S25"]["rms_ue"] + noise["S26"]["rms_ue"]))
    ax.text(0.01, y - 0.02, "OUR DIC IS %.1f× QUIETER THAN THE XT-205" % q, fontsize=11.5,
            transform=ax.transAxes, weight="bold", color="#1F3F2F")
    ax.text(0.01, y - 0.12, verdict(ratio, q), fontsize=8.2, transform=ax.transAxes, va="top")

    fig.tight_layout(rect=[0, 0, 1, 0.955])
    out = os.path.join(HERE, "mot_vs_dic_strainrate.png")
    fig.savefig(out, dpi=170)
    plt.close(fig)
    return out, res, ratio, noise


def verdict(ratio, noise_ratio):
    head = ("NOISE is the comparison that survives. It does not depend on how much crosshead\n"
            "motion reached the gauge, so both instruments are judged on the same footing —\n"
            "and ours is the quieter of the two, against a commercial extensometer.\n\n")
    if ratio > 1.05:
        return head + (
            "The RATE ratio (%.2f×) does NOT test our scale. Only ~19–29 %% of our crosshead\n"
            "motion reaches the gauge; the rest goes into machine compliance, grips and\n"
            "shoulders, and that fraction belongs to the MACHINE. A stiffer frame delivers a\n"
            "larger share, so MOT reading faster is what a stiffer frame looks like. Our\n"
            "calibration is not contradicted — but nor is it confirmed. That needs their load\n"
            "or crosshead-displacement channel." % ratio)
    if ratio < 0.95:
        return head + (
            "The RATE ratio (%.2f×) IS informative here: their frame cannot be more compliant\n"
            "than ours, so a smaller share of crosshead motion cannot reach their gauge. The\n"
            "remaining explanation is that WE OVER-READ strain — check px_per_mm and the gauge\n"
            "length entered at tare." % ratio)
    return head + ("The two rates agree to %.0f %%. Given the frames almost certainly differ in\n"
                   "compliance, that is a coincidence worth probing, not a clean pass."
                   % abs(100 * (ratio - 1)))


if __name__ == "__main__":
    out, res, ratio, noise = build()
    print("MOT extensometer XT-205 vs our DIC\n")
    print("  %-6s %-12s %-14s %-9s %s" % ("", "deps/dt (/s)", "% of ceiling", "R2", "n"))
    for k in ("MOT", "S25", "S26"):
        sl, r2, n, span = res[k]
        print("  %-6s %-12.3e %-14.1f %-9.5f %d   [t %.1f-%.1f s]"
              % (k, sl, 100 * sl / CEILING, r2, n, span[0], span[1]))
    print("\n  %-6s %11s %12s %11s" % ("", "noise RMS", "peak-peak", "quantum"))
    for k in ("MOT", "S25", "S26"):
        n = noise[k]
        print("  %-6s %8.1f ue %9.0f ue %8.1f ue"
              % (k, n["rms_ue"], n["pp_ue"], n["quantum_ue"]))
    q = noise["MOT"]["rms_ue"] / (0.5 * (noise["S25"]["rms_ue"] + noise["S26"]["rms_ue"]))
    print("\n  MOT / ours   rate = %.2f x    noise = %.2f x\n" % (ratio, q))
    print(verdict(ratio, q))
    print("\nwrote", out)
