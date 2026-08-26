"""Figures for the PETG slides (deck p257-254).

  petg_pair.png      S30 vs S31 — and why only one of them can carry the strain numbers
  petg_vs_pla.png    PETG against PLA, curves plus the four properties
  petg_expect.png    what literature predicts vs what the rig measured

Everything is read through petg_data, which reads the CSVs, so no number here is typed in.
"""
import os
import sys

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt                                       # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import petg_data as PD                                                # noqa: E402

GRID = "#DDDDDD"
C_PETG, C_PETG2 = "#7048e8", "#b197fc"
C_PLA, C_PLA2 = "#1f77b4", "#7fb3d5"
C_BAD, C_GOOD, MUTED = "#d62728", "#2f9e44", "#666666"


def _style(ax):
    ax.grid(True, color=GRID, lw=0.6)
    ax.set_axisbelow(True)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)


def _curve(key):
    c = np.asarray(PD.get(key)["curve"], float)
    return c[np.argsort(c[:, 0])]


def fig_trio(out="petg_trio.png"):
    """All three PETG runs on one axis. One figure, one idea: they are the same material."""
    fig, ax = plt.subplots(1, 1, figsize=(9.6, 3.6))
    cols = {"S30": C_PETG, "S31": C_PETG2, "S32": "#e8590c"}
    for k in ("S30", "S31", "S32"):
        d = PD.get(k); c = _curve(k); off = _shift(k)
        u, assumed = PD.uts_corrected(k)
        ax.plot(c[:, 0], c[:, 1] + off, color=cols[k], lw=2.0,
                label="%s — %d %% tracked · peak %.0f N · UTS %.2f%s"
                      % (k, d["track"], PD.peak_load_N(k), u, " *" if assumed else ""))
        ax.plot(d["ef"] * 100, d["sigf"] + off, "o", color=cols[k], ms=7, mec="white", mew=1.2)
    ax.set_xlabel("DIC gauge strain ε (%)"); ax.set_ylabel("engineering stress σ (MPa)")
    ax.set_title("Three PETG specimens, same protocol — S31 simply STOPS where its markers were "
                 "lost", fontsize=11)
    ax.legend(fontsize=8.8, loc="lower left")
    ax.annotate("S31 ends here because TRACKING ended,\nnot because the specimen broke sooner",
                xy=(PD.get("S31")["ef"] * 100, PD.get("S31")["sigf"]),
                xytext=(4.6, 14), fontsize=8.6, color=MUTED,
                arrowprops=dict(arrowstyle="->", color="#999"))
    _style(ax)
    fig.tight_layout()
    p = os.path.join(HERE, "..", "figures", out); fig.savefig(p, dpi=170); plt.close(fig)
    return p


def fig_limits(out="petg_limits.png"):
    """What each run's limit does to its numbers — force survives, strain does not."""
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(13.0, 3.3))
    s30, s31 = PD.get("S30"), PD.get("S31")
    props = [("UTS", s30["uts"], s31["uts"], True), ("σ_y", s30["sy"], s31["sy"], True),
             ("E", s30["E"], s31["E"], False), ("ε_f", s30["ef"] * 100, s31["ef"] * 100, False),
             ("tough\n/1000", s30["tough"] / 1000, s31["tough"] / 1000, False)]
    x = np.arange(len(props))
    a1.bar(x - 0.19, [q[1] for q in props], width=0.36, color=C_PETG, label="S30 — 89 % tracked")
    a1.bar(x + 0.19, [q[2] for q in props], width=0.36, color=C_PETG2, label="S31 — 57 %")
    for i, (lab, v30, v31, force_based) in enumerate(props):
        a1.text(i, max(v30, v31) * 1.07, "%+.0f %%" % (100 * (v31 / v30 - 1)), ha="center",
                fontsize=9, weight="bold", color=C_GOOD if force_based else C_BAD)
    a1.set_xticks(x); a1.set_xticklabels([q[0] for q in props], fontsize=9)
    a1.set_ylim(0, max(max(q[1], q[2]) for q in props) * 1.28)
    a1.set_title("S31: LOAD-CELL numbers agree (green), DIC numbers do not (red)", fontsize=10.5)
    a1.legend(fontsize=8.4)
    _style(a1)

    # S32: the anchor, shown as the constant offset it is
    a32 = PD.get("S32"); c32 = _curve("S32")
    a2.plot(c32[:, 0], c32[:, 1], color="#adb5bd", lw=1.8, label="as analysed — anchor −1044 N")
    a2.plot(c32[:, 0], c32[:, 1] + _shift("S32"), color="#e8590c", lw=2.0,
            label="with the rig's usual 300 N preload")
    c30 = _curve("S30")
    a2.plot(c30[:, 0], c30[:, 1], color=C_PETG, lw=1.4, ls="--", alpha=0.8, label="S30 for scale")
    a2.axhline(0, color="#888", lw=0.8)
    a2.set_xlabel("DIC gauge strain ε (%)"); a2.set_ylabel("engineering stress σ (MPa)")
    a2.set_title("S32: a failed anchor is a CONSTANT SHIFT — it moves every\nstress and no slope",
                 fontsize=10.5)
    a2.legend(fontsize=8.2, loc="lower left")
    _style(a2)
    fig.tight_layout()
    p = os.path.join(HERE, "..", "figures", out); fig.savefig(p, dpi=170); plt.close(fig)
    return p


def fig_vs_pla(out="petg_vs_pla.png"):
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(13.6, 3.3),
                                 gridspec_kw={"width_ratios": [1.3, 1]})
    for k, c, ls, lab in (("S25", C_PLA, "-", "PLA S25"), ("S26", C_PLA2, "--", "PLA S26"),
                          ("S30", C_PETG, "-", "PETG S30")):
        d = PD.get(k); cur = _curve(k)
        a1.plot(cur[:, 0], cur[:, 1], color=c, ls=ls, lw=2.0,
                label="%s — UTS %.1f, E %.2f GPa" % (lab, d["uts"], d["E"]))
        a1.plot(d["ef"] * 100, d["sigf"], "o", color=c, ms=7, mec="white", mew=1.2)
    a1.set_xlabel("DIC gauge strain ε (%)"); a1.set_ylabel("engineering stress σ (MPa)")
    a1.set_title("PLA is stronger and much stiffer; PETG goes further before it breaks",
                 fontsize=10.5)
    a1.legend(fontsize=8.4, loc="lower right")
    _style(a1)

    P, L = PD.get(PD.PETG_REP), PD.get(PD.PLA_REP)
    props = [("UTS\nMPa", L["uts"], P["uts"]), ("σ_y\nMPa", L["sy"], P["sy"]),
             ("E\nGPa", L["E"], P["E"]), ("ε_f\n%", L["ef"] * 100, P["ef"] * 100),
             ("tough\nkJ/m³/1000", L["tough"] / 1000, P["tough"] / 1000)]
    x = np.arange(len(props))
    a2.bar(x - 0.19, [p[1] for p in props], width=0.36, color=C_PLA, label="PLA S25")
    a2.bar(x + 0.19, [p[2] for p in props], width=0.36, color=C_PETG, label="PETG S30")
    for i, (lab, lv, pv) in enumerate(props):
        a2.text(i, max(lv, pv) * 1.06, "%+.0f %%" % (100 * (pv / lv - 1)), ha="center",
                fontsize=8.8, weight="bold",
                color=C_GOOD if pv > lv else C_BAD)
    a2.set_xticks(x); a2.set_xticklabels([p[0] for p in props], fontsize=8.6)
    a2.set_ylim(0, max(max(p[1], p[2]) for p in props) * 1.25)
    a2.set_title("PETG relative to PLA", fontsize=10.5)
    a2.legend(fontsize=8.4)
    _style(a2)
    fig.tight_layout()
    p = os.path.join(HERE, "..", "figures", out); fig.savefig(p, dpi=170); plt.close(fig)
    return p


def fig_expect(out="petg_expect.png"):
    """Measured values against the published bands — the ordering is the prediction."""
    rows = [("UTS  (MPa)", "uts", 1.0), ("E  (GPa)", "E", 1.0), ("ε_f  (%)", "ef", 100.0)]
    fig, axes = plt.subplots(1, 3, figsize=(13.6, 3.15))
    P, L = PD.get(PD.PETG_REP), PD.get(PD.PLA_REP)
    for ax, (lab, key, sc) in zip(axes, rows):
        for i, (mat, val, col) in enumerate((("PLA", L[key] * sc, C_PLA),
                                             ("PETG", P[key] * sc, C_PETG))):
            lo, hi = PD.LIT[mat][{"uts": "UTS", "E": "E", "ef": "ef"}[key]]
            ax.barh(i, hi - lo, left=lo, height=0.34, color=col, alpha=0.22,
                    label="published range" if i == 0 else None)
            ax.plot([val], [i], "D", color=col, ms=11, mec="white", mew=1.4,
                    label="measured" if i == 0 else None)
            inside = lo <= val <= hi
            ax.text(val, i + 0.30, "%.2f  %s" % (val, "in band" if inside else "below band"),
                    ha="center", fontsize=8.4, weight="bold",
                    color=C_GOOD if inside else C_BAD)
        ax.set_yticks([0, 1]); ax.set_yticklabels(["PLA\nS25", "PETG\nS30"], fontsize=9)
        ax.set_ylim(-0.6, 1.7)
        ax.set_xlabel(lab)
        ax.set_title(lab.split("(")[0].strip(), fontsize=11)
        _style(ax)
    axes[0].legend(fontsize=8, loc="lower right")
    fig.suptitle("Measured against typical published ranges for 100 % infill printed parts — "
                 "the ORDERING is the prediction under test", fontsize=10.5, y=1.02)
    fig.tight_layout()
    p = os.path.join(HERE, "..", "figures", out); fig.savefig(p, dpi=170, bbox_inches="tight"); plt.close(fig)
    return p


def _shift(key):
    """Stress offset to draw a run comparably. Zero unless its anchor failed."""
    if key not in PD.ANCHOR_FAILED:
        return 0.0
    a = PD.get(key)
    return (PD.ASSUMED_PRELOAD_N - a["anchor"]) / 80.0


def plastic_slope(key, lo_frac=0.15, hi_frac=0.85):
    """d(sigma)/d(eps) over the POST-UTS region, in MPa per % strain.

    A SLOPE IS IMMUNE TO THE ANCHOR. The anchor enters the stress axis as a constant offset, so it
    cancels in any derivative - which is why S32 can be compared here on equal terms even though
    its absolute UTS cannot be trusted. That is not a convenience, it is the reason this comparison
    is the right one to make with the data we have.

    Fitted between lo_frac and hi_frac of the way from the UTS strain to fracture, so the turnover
    at the peak and the last dying samples are both left out.
    """
    a = PD.get(key)
    c = _curve(key)
    e, s = c[:, 0], c[:, 1]
    i_uts = int(np.argmax(s))
    e_uts, e_f = e[i_uts], e[-1]
    if e_f <= e_uts:
        return None
    lo = e_uts + lo_frac * (e_f - e_uts)
    hi = e_uts + hi_frac * (e_f - e_uts)
    m = (e >= lo) & (e <= hi)
    if m.sum() < 10:
        return None
    sl, ic = np.polyfit(e[m], s[m], 1)
    r2 = np.corrcoef(e[m], s[m])[0, 1] ** 2
    return {"slope": sl, "ic": ic, "r2": r2, "lo": lo, "hi": hi,
            "e_uts": e_uts, "e_f": e_f, "n": int(m.sum())}


def fig_plastic(out="petg_plastic.png"):
    """How the PLASTIC (post-UTS) slope varies between our own PETG specimens."""
    keys = [k for k in ("S30", "S31", "S32") if plastic_slope(k)]
    cols = {"S30": C_PETG, "S31": C_PETG2, "S32": "#e8590c"}
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(13.6, 3.35),
                                 gridspec_kw={"width_ratios": [1.35, 1]})
    for k in keys:
        d = PD.get(k); ps = plastic_slope(k); c = _curve(k); off = _shift(k)
        a1.plot(c[:, 0], c[:, 1] + off, color=cols[k], lw=1.9,
                label="%s — %d %% tracked%s" % (k, d["track"], "  (stress shifted)" if off else ""))
        m = (c[:, 0] >= ps["lo"]) & (c[:, 0] <= ps["hi"])
        a1.plot(c[m, 0], ps["slope"] * c[m, 0] + ps["ic"] + off, color="#111", lw=1.1, ls="--")
        a1.axvspan(ps["lo"], ps["hi"], color=cols[k], alpha=0.07)
    a1.set_xlabel("DIC gauge strain ε (%)"); a1.set_ylabel("engineering stress σ (MPa)")
    a1.set_title("PETG specimens with the POST-UTS region fitted\n"
                 "(dashed = the plastic slope of that run)", fontsize=10.5)
    a1.legend(fontsize=8.4, loc="lower left")
    _style(a1)

    xs = np.arange(len(keys))
    vals = [plastic_slope(k)["slope"] for k in keys]
    b = a2.bar(xs, vals, width=0.5, color=[cols[k] for k in keys])
    for r, k, v in zip(b, keys, vals):
        ps = plastic_slope(k)
        a2.text(r.get_x() + r.get_width() / 2, v - 0.12,
                "%.2f\nR² %.3f" % (v, ps["r2"]), ha="center", va="top",
                fontsize=9, weight="bold")
    a2.axhline(0, color="#888", lw=0.8)
    a2.set_xticks(xs); a2.set_xticklabels(keys, fontsize=10)
    a2.set_ylabel("plastic slope  dσ/dε  (MPa per % strain)")
    a2.set_ylim(min(vals) * 1.55, max(0.4, max(vals) * 1.2))
    sp = 100 * (max(vals) - min(vals)) / abs(np.mean(vals))
    a2.set_title("%d of the 3 runs have a post-UTS region long enough to fit,\n"
                 "and they agree to %.0f %%. A slope is immune to the anchor."
                 % (len(keys), sp), fontsize=10.5)
    _style(a2)
    fig.tight_layout()
    p = os.path.join(HERE, "..", "figures", out); fig.savefig(p, dpi=170); plt.close(fig)
    return p


if __name__ == "__main__":
    for k in ("S30", "S31", "S32"):
        ps = plastic_slope(k)
        if ps is None:
            print("%-4s no post-UTS region long enough to fit "
                  "(its curve ends %.2f %% after the peak)"
                  % (k, _curve(k)[:, 0].max() - _curve(k)[np.argmax(_curve(k)[:, 1]), 0]))
            continue
        print("%-4s plastic slope %+7.3f MPa per %% strain   R2 %.4f   fitted %.2f-%.2f %%  n=%d"
              % (k, ps["slope"], ps["r2"], ps["lo"], ps["hi"], ps["n"]))
    for f in (fig_trio(), fig_limits(), fig_vs_pla(), fig_expect(), fig_plastic()):
        print("wrote", os.path.basename(f))


def elastic_common(key, lo=0.05, hi=0.35):
    """E over a FIXED strain window, so the window rule is not part of the difference.

    0.05-0.35 % deliberately: it is the SAME interval the MOT extensometer comparison used on
    p245-247, so the two analyses in this deck can be read against each other instead of each
    inventing its own region.
    """
    c = _curve(key)
    e, s = c[:, 0], c[:, 1]
    m = (e >= lo) & (e <= hi)
    if m.sum() < 10:
        return None
    sl, ic = np.polyfit(e[m], s[m], 1)
    r2 = np.corrcoef(e[m], s[m])[0, 1] ** 2
    return {"E": sl * 100 / 1000.0, "slope": sl, "ic": ic, "r2": r2, "n": int(m.sum())}


def fig_elastic(out="petg_elastic.png"):
    """The ELASTIC slope for the three PETG runs — and why the three numbers differ.

    Two panels because there are two questions. What is each specimen's stiffness, and how much of
    the spread between them is the SPECIMEN rather than the fit rule? `analyze()` picks the steepest
    straight run per specimen, which is right for a single number but means the three E values are
    not measured over the same strain. The right-hand panel refits all three over one fixed window
    so that variable is removed.
    """
    keys = ("S30", "S31", "S32")
    cols = {"S30": C_PETG, "S31": C_PETG2, "S32": "#e8590c"}
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(13.6, 3.4),
                                 gridspec_kw={"width_ratios": [1.4, 1]})
    for k in keys:
        d = PD.get(k); c = _curve(k); off = _shift(k)
        m = c[:, 0] <= 1.15
        a1.plot(c[m, 0], c[m, 1] + off, color=cols[k], lw=2.0,
                label="%s — E %.2f GPa over %.2f–%.2f %%" % (k, d["E"], d["E_lo"], d["E_hi"]))
        w = (c[:, 0] >= d["E_lo"]) & (c[:, 0] <= d["E_hi"])
        sl, ic = np.polyfit(c[w, 0], c[w, 1], 1)
        xs = np.linspace(d["E_lo"], d["E_hi"], 5)
        a1.plot(xs, sl * xs + ic + off, color="#111", lw=1.2, ls="--")
        a1.axvspan(d["E_lo"], d["E_hi"], color=cols[k], alpha=0.09)
    a1.set_xlim(0, 1.15)
    a1.set_xlabel("DIC gauge strain ε (%)"); a1.set_ylabel("engineering stress σ (MPa)")
    a1.set_title("The elastic region, magnified — each run fitted over ITS OWN\n"
                 "steepest straight run (shaded), which is not the same strain", fontsize=10.5)
    a1.legend(fontsize=8.4, loc="upper left")
    _style(a1)

    x = np.arange(len(keys))
    own = [PD.get(k)["E"] for k in keys]
    com = [elastic_common(k)["E"] if elastic_common(k) else np.nan for k in keys]
    a2.bar(x - 0.19, own, width=0.36, color=[cols[k] for k in keys], label="own steepest run")
    a2.bar(x + 0.19, com, width=0.36, color=[cols[k] for k in keys], alpha=0.45,
           hatch="//", edgecolor="white", label="common window 0.05–0.35 % (as MOT)")
    for i, (o, c_) in enumerate(zip(own, com)):
        a2.text(i - 0.19, o + 0.05, "%.2f" % o, ha="center", fontsize=8.6, weight="bold")
        if np.isfinite(c_):
            a2.text(i + 0.19, c_ + 0.05, "%.2f" % c_, ha="center", fontsize=8.6)
    a2.set_xticks(x); a2.set_xticklabels(keys, fontsize=10)
    a2.set_ylabel("elastic modulus E (GPa)")
    a2.set_ylim(0, max(own + [v for v in com if np.isfinite(v)]) * 1.30)
    sp_own = 100 * (max(own) / min(own) - 1)
    fin = [v for v in com if np.isfinite(v)]
    sp_com = 100 * (max(fin) / min(fin) - 1) if len(fin) > 1 else float("nan")
    a2.set_title("Spread %.0f %% on each run's own window,\n%.0f %% over one common window"
                 % (sp_own, sp_com), fontsize=10.5)
    a2.legend(fontsize=8)
    _style(a2)
    fig.tight_layout()
    p = os.path.join(HERE, "..", "figures", out); fig.savefig(p, dpi=170); plt.close(fig)
    return p
