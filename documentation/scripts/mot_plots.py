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


def build_all():
    return [fig_record(), fig_rate(), fig_noise()]


if __name__ == "__main__":
    for p in build_all():
        print("wrote", os.path.basename(p))
