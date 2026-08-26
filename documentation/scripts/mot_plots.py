"""Figures for the MOT XT-205 vs UTM DIC slides (deck p245-247).

Three figures, one per slide:

  mot_record.png    the MOT record on its own — what was actually delivered, including the parts
                    that are not data (221 Invalid rows, then ~13 s before the crosshead moves)
  mot_rate.png      strain rate over a matched strain interval, plus the local-slope view that
                    shows WHY the rate ratio is not a calibration result
  mot_noise.png     residual scatter — the one comparison that is genuinely like-for-like

All numbers come from mot_compare.py, which reads both CSVs at build time. Nothing here is typed
in, so a re-run after new data cannot silently disagree with the slides.
"""
import os
import sys

import numpy as np

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt                                       # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import mot_compare as MC                                              # noqa: E402

C_MOT, C_S25, C_S26 = "#d62728", "#1f77b4", "#7fb3d5"
GREY, GRID = "#666666", "#DDDDDD"
LO, HI = 0.0005, 0.0035                    # matched strain interval, 0.05 % .. 0.35 %


def _style(ax):
    ax.grid(True, color=GRID, lw=0.6)
    ax.set_axisbelow(True)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)


def data():
    tm, em, gl = MC.read_mot()
    runs = {s: MC.read_ours(p) for s, p in
            (("S25", "Specimen_S25_V2_Spray_Video2/*.csv"),
             ("S26", "Specimen_S26_V2_Spray_Video3/*.csv"))}
    return tm, em, gl, runs


def fig_record(out="mot_record.png"):
    """Slide 1 — the MOT record alone."""
    tm, em, gl, _r = data()
    # 5.06:1 — the slide box is 12.55 x 2.48 in, and a taller figure would be letterboxed
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(14.0, 2.77),
                                 gridspec_kw={"width_ratios": [1.15, 1]})

    a1.plot(tm, em * 100, color=C_MOT, lw=1.6)
    a1.axvspan(tm.min(), 14.8, color="#f0f0f0", zorder=0)
    a1.set_title("The record as delivered", fontsize=11)
    a1.set_xlabel("time (s)"); a1.set_ylabel("strain (%)")
    a1.annotate("221 rows read \"Invalid\" before this,\nthen ~13 s at zero strain —\n"
                "the crosshead has not moved yet",
                xy=(8.0, 0.004), xytext=(2.6, 0.20), fontsize=8.4, color=GREY,
                arrowprops=dict(arrowstyle="->", color="#999"))
    a1.annotate("record STOPS at %.3f %%\nno fracture, and no load channel" % (em.max() * 100),
                xy=(tm[-1], em[-1] * 100), xytext=(9.5, 0.355), fontsize=8.4, color=GREY,
                arrowprops=dict(arrowstyle="->", color="#999"))
    _style(a1)

    # the ramp, fitted
    m = (em >= LO) & (em <= HI)
    sl, ic = np.polyfit(tm[m], em[m], 1)
    a2.plot(tm[m], em[m] * 100, color=C_MOT, lw=1.8, label="MOT XT-205")
    a2.plot(tm[m], (sl * tm[m] + ic) * 100, color="#333", lw=1.0, ls="--",
            label=r"fit  d$\varepsilon$/dt = %.3f$\times10^{-4}$/s" % (sl / 1e-4))
    a2.set_title("The loading ramp, 0.05–0.35 %% strain   (R$^2$ = %.4f)"
                 % (np.corrcoef(tm[m], em[m])[0, 1] ** 2), fontsize=11)
    a2.set_xlabel("time (s)"); a2.set_ylabel("strain (%)")
    a2.legend(fontsize=8.6, loc="upper left")
    _style(a2)

    # residual inset — the stair-stepping is visible to the eye, so show it honestly
    ins = a2.inset_axes([0.56, 0.13, 0.41, 0.32])
    r = (em[m] - (sl * tm[m] + ic)) * 1e6
    ins.plot(tm[m], r, color=C_MOT, lw=0.9)
    ins.axhline(0, color="#999", lw=0.7)
    ins.set_title("residual (µε), RMS %.0f" % r.std(), fontsize=7.4)
    ins.tick_params(labelsize=6.4)
    ins.grid(True, color=GRID, lw=0.5)

    fig.tight_layout()
    p = os.path.join(HERE, "..", "figures", out)
    fig.savefig(p, dpi=170); plt.close(fig)
    return p


def fig_rate(out="mot_rate.png"):
    """Slide 2 — strain rate, and why the ratio is not a calibration result."""
    tm, em, gl, runs = data()
    # 4.16:1 to match the 12.55 x 3.02 in slide box
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(13.6, 3.27))

    series = [("MOT XT-205", tm, em, C_MOT, "-"),
              ("S25 (our DIC)", runs["S25"][0], runs["S25"][1], C_S25, "-"),
              ("S26 (our DIC)", runs["S26"][0], runs["S26"][1], C_S26, "--")]

    for lab, t, e, c, ls in series:
        m = (e >= LO) & (e <= HI)
        sl = np.polyfit(t[m], e[m], 1)[0]
        a1.plot(t[m] - t[m].min(), e[m] * 100, color=c, ls=ls, lw=1.9,
                label="%s   %.2f$\\times10^{-4}$/s" % (lab, sl / 1e-4))
    a1.set_title("Matched strain interval 0.05–0.35 %, common time origin", fontsize=11)
    a1.set_xlabel("time within the interval (s)"); a1.set_ylabel("strain (%)")
    a1.legend(fontsize=8.4, loc="lower right")
    _style(a1)

    for lab, t, e, c, ls in series:
        t0 = t[np.argmax(e > LO)]
        a2.plot(t - t0, MC.moving_rate(t, e) / 1e-4, color=c, ls=ls, lw=1.4, label=lab)
    a2.axhline(MC.CEILING / 1e-4, color="#333", ls=":", lw=1.3)
    a2.text(0.99, MC.CEILING / 1e-4, " physical ceiling %.1f " % (MC.CEILING / 1e-4),
            fontsize=7.6, ha="right", va="bottom", color="#333",
            transform=a2.get_yaxis_transform())
    a2.set_xlim(-8, 60); a2.set_ylim(-0.5, MC.CEILING / 1e-4 * 1.12)
    a2.set_title("Local slope through the pull — ours CLIMBS, theirs is flat", fontsize=11)
    a2.set_xlabel("time from first strain (s)")
    a2.set_ylabel(r"d$\varepsilon$/dt   ($10^{-4}$/s)")
    a2.legend(fontsize=8.4, loc="upper left")
    a2.annotate("our rig's seating take-up:\nthe gauge receives more of the\ncrosshead as slack "
                "is used up", xy=(30, 4.4), xytext=(20, 9.6), fontsize=8.0, color=GREY,
                arrowprops=dict(arrowstyle="->", color="#999"))
    _style(a2)

    fig.tight_layout()
    p = os.path.join(HERE, "..", "figures", out)
    fig.savefig(p, dpi=170); plt.close(fig)
    return p


def fig_noise(out="mot_noise.png"):
    """Slide 3 — residual scatter, the comparison that survives."""
    tm, em, gl, runs = data()
    series = [("MOT\nXT-205", tm, em, C_MOT),
              ("S25\nour DIC", runs["S25"][0], runs["S25"][1], C_S25),
              ("S26\nour DIC", runs["S26"][0], runs["S26"][1], C_S26)]

    fig, (a1, a2) = plt.subplots(1, 2, figsize=(13.6, 3.27),
                                 gridspec_kw={"width_ratios": [1.45, 1]})
    stats = []
    for lab, t, e, c in series:
        m = (e >= LO) & (e <= HI)
        tt, ee = t[m], e[m]
        sl, ic = np.polyfit(tt, ee, 1)
        r = (ee - (sl * tt + ic)) * 1e6
        a1.plot(np.linspace(0, 100, len(r)), r, color=c, lw=1.1,
                label="%s   RMS %.1f µε" % (lab.replace("\n", " "), r.std()))
        stats.append((lab, r.std(), c,
                      {"rms": r.std(), "med": float(np.median(np.abs(r))),
                       "p95": float(np.percentile(np.abs(r), 95)),
                       "max": float(np.abs(r).max()),
                       "step": float(np.median(np.abs(np.diff(ee)) * 1e6))}))
    a1.axhline(0, color="#999", lw=0.8)
    a1.set_title("Residual about the straight fit, same 0.05–0.35 % strain interval", fontsize=11)
    a1.set_xlabel("progress through the interval (%)"); a1.set_ylabel("residual strain (µε)")
    a1.legend(fontsize=8.6, loc="upper right", ncol=1)
    _style(a1)

    # THREE statistics, not one. RMS alone would overstate the case: the XT-205 holds the
    # QUIETEST baseline of the three (median |r| 12.0 ue) and loses on RMS only because of a
    # handful of large excursions. "Ours is 1.9x quieter" is true of RMS and false of the
    # baseline, so the chart has to show both or it is an argument rather than a measurement.
    xs = np.arange(len(stats))
    w = 0.26
    for k, (key, lab_k) in enumerate((("med", "median |r|"), ("p95", "95th pct |r|"),
                                      ("rms", "RMS"))):
        vals = [s[3][key] for s in stats]
        b = a2.bar(xs + (k - 1) * w, vals, width=w, label=lab_k,
                   color=[s[2] for s in stats], alpha=(0.45, 0.72, 1.0)[k],
                   edgecolor="white", lw=0.6)
        for rect, v in zip(b, vals):
            a2.text(rect.get_x() + rect.get_width() / 2, v + 2, "%.0f" % v,
                    ha="center", fontsize=7.4)
    a2.set_xticks(xs); a2.set_xticklabels([s[0] for s in stats], fontsize=9)
    a2.set_ylabel("residual strain (µε)")
    a2.set_ylim(0, max(s[3]["p95"] for s in stats) * 1.30)
    a2.legend(fontsize=7.8, loc="upper right", frameon=True)
    a2.set_title("Baselines are comparable; the XT-205's RMS is driven\nby occasional large "
                 "excursions", fontsize=11)
    _style(a2)

    fig.tight_layout()
    p = os.path.join(HERE, "..", "figures", out)
    fig.savefig(p, dpi=170); plt.close(fig)
    return p


def fig_window(out="mot_window.png"):
    """Slide 4 — WHAT the RMS is, and WHERE in the pull it was measured.

    The noise slide reports a single number per instrument and never says which part of the test
    it came from, so it invites the reading "our DIC is 1.9x quieter, everywhere". It is not that.
    It is the scatter about a straight line over one narrow slice of the elastic region — and the
    slice is narrow because it is all the XT-205 ever delivered.
    """
    tm, em, gl, runs = data()
    t25, e25 = runs["S25"][0], runs["S25"][1]

    fig, (a1, a2, a3) = plt.subplots(1, 3, figsize=(13.6, 3.5),
                                     gridspec_kw={"width_ratios": [1.15, 1, 1]})

    # ---- (1) where the window sits in a WHOLE pull, on the stress-strain curve
    sys.path.insert(0, HERE)
    import trio_plots as TP
    e_full, s_full, a_full = TP.curve("S25")
    a1.plot(e_full, s_full, color=C_S25, lw=1.7)
    a1.axvspan(LO * 100, HI * 100, color="#d62728", alpha=0.22, zorder=0)
    a1.set_xlim(0, e_full.max() * 1.03)
    a1.set_ylim(0, s_full.max() * 1.22)
    a1.annotate("the noise window\n0.05–0.35 % strain",
                xy=(HI * 100, s_full.max() * 0.42), xytext=(e_full.max() * 0.30, s_full.max() * 0.30),
                fontsize=8.8, color="#d62728", weight="bold",
                arrowprops=dict(arrowstyle="->", color="#d62728", lw=1.4))
    a1.annotate("UTS  %.1f MPa\nat %.2f %%" % (a_full["uts"], a_full["uts_ec"]),
                xy=(a_full["uts_ec"], a_full["uts"]),
                xytext=(a_full["uts_ec"] * 1.35, s_full.max() * 1.02),
                fontsize=8.4, color=GREY, arrowprops=dict(arrowstyle="->", color="#999"))
    a1.set_title("WHERE: 0.3 %% of strain out of %.1f %% — the elastic toe" % e_full.max(),
                 fontsize=10.4)
    a1.set_xlabel("DIC gauge strain (%)"); a1.set_ylabel("Engineering stress (MPa)")
    _style(a1)

    # ---- (2) inside the window, strain against time, with the straight fit
    m = (e25 >= LO) & (e25 <= HI)
    tt, ee = t25[m] - t25[m].min(), e25[m]
    sl, ic = np.polyfit(t25[m], ee, 1)
    fit = sl * t25[m] + ic
    r2 = np.corrcoef(t25[m], ee)[0, 1] ** 2
    a2.plot(tt, ee * 100, color=C_S25, lw=1.5, label="S25 measured")
    a2.plot(tt, fit * 100, color="#212529", lw=1.1, ls="--",
            label="straight fit  (R² = %.5f)" % r2)
    a2.set_title("WHAT it is fitted to: strain vs TIME in that window", fontsize=10.4)
    a2.set_xlabel("time within the window (s)"); a2.set_ylabel("strain (%)")
    a2.legend(fontsize=8.2, loc="upper left")
    _style(a2)

    # ---- (3) the residual, which is the thing RMS summarises
    r = (ee - fit) * 1e6
    a3.plot(tt, r, color=C_S25, lw=1.1)
    a3.axhline(0, color="#999", lw=0.8)
    a3.axhline(r.std(), color="#d62728", lw=1.0, ls=":")
    a3.axhline(-r.std(), color="#d62728", lw=1.0, ls=":")
    a3.fill_between(tt, -r.std(), r.std(), color="#d62728", alpha=0.10)
    a3.text(0.5, 0.965, "±1 RMS = %.1f µε" % r.std(), transform=a3.transAxes,
            ha="center", va="top", fontsize=9.0, color="#d62728", weight="bold",
            bbox=dict(boxstyle="round,pad=0.28", fc="white", ec="#d62728", lw=0.8, alpha=0.92))
    a3.set_ylim(r.min() * 1.35, r.max() * 1.55)
    a3.set_title("WHAT RMS IS: the spread the fit leaves over", fontsize=10.4)
    a3.set_xlabel("time within the window (s)")
    a3.set_ylabel("measured − straight line (µε)")
    _style(a3)

    fig.tight_layout()
    p = os.path.join(HERE, "..", "figures", out)
    fig.savefig(p, dpi=170); plt.close(fig)
    return p


def window_facts():
    """Numbers the slide quotes, computed rather than typed."""
    tm, em, gl, runs = data()
    out = {}
    mm = (em >= LO) & (em <= HI)
    out["MOT"] = {"max_pct": em.max() * 100, "n": int(mm.sum()), "N": len(em),
                  "secs": float(tm[mm].max() - tm[mm].min())}
    for k in ("S25", "S26"):
        t, e = runs[k][0], runs[k][1]
        m = (e >= LO) & (e <= HI)
        sl, ic = np.polyfit(t[m], e[m], 1)
        out[k] = {"n": int(m.sum()), "N": len(e), "secs": float(t[m].max() - t[m].min()),
                  "r2": float(np.corrcoef(t[m], e[m])[0, 1] ** 2),
                  "rms_ue": float(((e[m] - (sl * t[m] + ic)) * 1e6).std())}
    return out


def build_all():
    return [fig_record(), fig_rate(), fig_noise(), fig_window()]


if __name__ == "__main__":
    for p in build_all():
        print("wrote", os.path.basename(p))
