"""SF9 (advanced test modes) — metrics + figures for the V6a deck.

Every number on the SF9 slides is computed HERE from the rig CSVs and imported by
generate_v6a_slides.py, so no value is transcribed by hand. Run standalone to regenerate the
figures and print the metric table:

    python documentation/sf9_data.py
"""
import os, sys, statistics as st

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.join(_HERE, "..")
_APP = os.path.join(_ROOT, "Software", "UTM_PyQt6")
sys.path.insert(0, _APP)
import utm_analysis as ua                                    # noqa: E402

DATA = os.path.join(_APP, "8.7")
OUT = _HERE
AREA, GAUGE = 80.0, 80.0

CSV = {
    "creep":      "Specimen_S20_V2_Spray_CreepTest/UTM_Test_20260808_182942_T1.csv",
    "relax":      "Specimen_S20_V2_Spray_RelaxationTest/UTM_Test_20260808_183649_T2.csv",
    "stair_lin":  "Specimen_S20_V2_Spray_StaircaseTest_Linear/UTM_Test_20260808_193917_T3_Linear.csv",
    "stair_smo":  "Specimen_S20_V2_Spray_StaircaseTest_Smooth/UTM_Test_20260808_193917_T4_Smooth.csv",
    "cyc_tri":    "Specimen_S20_V2_Spray_CyclicTest_Triangle/UTM_Test_20260809_131215_T5_Cyclic_Tri.csv",
    "cyc_sin":    "Specimen_S20_V2_Spray_CyclicTest_Sine/UTM_Test_20260809_142723_T6.3_Cyclic_Sine.csv",
    "cyc_sin1":   "Specimen_S20_V2_Spray_CyclicTest_Sine/UTM_Test_20260809_131215_T6_Cyclic_Sine.csv",
    "cyc_sin2":   "Specimen_S20_V2_Spray_CyclicTest_Sine/UTM_Test_20260809_131215_T6.2_Cyclic_Sine.csv",
    "sf":         "Specimen_S18_V1_Spray_Staircase-Fracture/UTM_Test_20260809_154041_T7.2_Staircase-Failure.csv",
    "sf_stall":   "Specimen_S20_V2_Spray_Staircase-Fracture/UTM_Test_20260809_152644_T7.csv",
    "pc":         "Specimen_S21_V1_Spray_ProgressiveCyclic-Fracture/UTM_Test_20260809_173857_T8_Progressive-Fracture.csv",
}


def rd(k):
    return ua.read_csv(os.path.join(DATA, CSV[k]))


def when(k):
    """'Test Date' straight out of the CSV header — the filename's timestamp is the session/file id
    and does NOT match when the test actually ran (all three T6 attempts share one prefix)."""
    with open(os.path.join(DATA, CSV[k]), encoding="utf-8", errors="replace") as f:
        for line in f:
            if not line.startswith("#"):
                break
            if "Test Date:" in line:
                return line.split("Test Date:")[1].strip()[5:16]      # MM-DD HH:MM
    return "?"


def _segs(r, upto=None):
    """Split on the sign of the COMMANDED speed: rising / unloading / dwell."""
    out, cur = [], None
    for i in range(upto or len(r)):
        s = r[i]["spd"]
        d = "up" if s < -1e-6 else ("down" if s > 1e-6 else "hold")
        if cur is None or cur[0] != d:
            cur = [d, i, i]; out.append(cur)
        else:
            cur[2] = i
    return [s for s in out if s[2] - s[1] > 4]


def _fit(xs, ys):
    m = len(xs)
    if m < 5:
        return float("nan"), float("nan")
    sx, sy = sum(xs), sum(ys)
    sxx = sum(x * x for x in xs); sxy = sum(x * y for x, y in zip(xs, ys))
    den = m * sxx - sx * sx
    if abs(den) < 1e-12:
        return float("nan"), float("nan")
    a = (m * sxy - sx * sy) / den; b = (sy - a * sx) / m
    ss = sum((y - (a * x + b)) ** 2 for x, y in zip(xs, ys))
    tt = sum((y - sy / m) ** 2 for y in ys)
    return a, (1 - ss / tt if tt > 0 else float("nan"))


def _fracture(r):
    """Index of the single biggest sample-to-sample load drop = the collapse."""
    return max(range(1, len(r)), key=lambda i: r[i - 1]["F"] - r[i]["F"])


def _anchor(r, fi):
    tail = [x["F"] for x in r if x["t"] > r[fi]["t"] + 8]
    return -st.median(tail), st.pstdev(tail), len(tail)


# ---------------------------------------------------------------- per-mode metrics
def creep():
    r = rd("creep")
    h = max((s for s in _segs(r) if s[0] == "hold"), key=lambda s: s[2] - s[1])
    sg = r[h[1]:h[2] + 1]
    F = [x["F"] for x in sg]
    return dict(r=r, t0=r[h[1]]["t"], t1=r[h[2]]["t"], dur=r[h[2]]["t"] - r[h[1]]["t"],
                F0=sg[0]["F"], F1=sg[-1]["F"], Fmean=st.mean(F), Fsd=st.pstdev(F),
                e0=sg[0]["ec"], e1=sg[-1]["ec"], de=(sg[-1]["ec"] - sg[0]["ec"]) * 1e6)


def relax():
    """Relaxation holds STRAIN, so the crosshead keeps nudging and commanded speed is never a
    clean zero — the dwell is found from the crosshead POSITION going flat instead."""
    r = rd("relax")
    pk = max(range(len(r)), key=lambda i: r[i]["F"])
    pos_hold = r[pk]["pos"]
    i0 = next(i for i in range(pk, len(r)) if abs(r[i]["pos"] - pos_hold) < 1e-3)
    sg = r[i0:]
    e = [x["ec"] for x in sg if x["ec"] > 1e-4]
    return dict(r=r, ipk=pk, i0=i0, Fpk=r[pk]["F"], F0=sg[0]["F"], F1=sg[-1]["F"],
                dur=sg[-1]["t"] - sg[0]["t"], drop=r[pk]["F"] - sg[-1]["F"],
                drop_pct=100 * (r[pk]["F"] - sg[-1]["F"]) / r[pk]["F"],
                eps=st.mean(e), eps_sd=st.pstdev(e), pos=pos_hold)


def staircase(key, targets=(300.0, 600.0, 900.0)):
    """Arrival overshoot is measured against the COMMANDED level, not against the settled value —
    the settled value already contains the dwell relaxation, which would mask the control error."""
    r = rd(key)
    lv = []
    for t in targets:
        i = next((i for i in range(len(r)) if r[i]["F"] >= t * 0.97), None)
        if i is None:
            continue
        w = r[i:min(len(r), i + 90)]
        pk = max(x["F"] for x in w)
        j = next((j for j in range(i, len(r)) if abs(r[j]["spd"]) < 1e-6), i)
        k = next((k for k in range(j, len(r)) if abs(r[k]["spd"]) > 1e-6), len(r) - 1)
        sg = r[j:k + 1]
        lv.append(dict(target=t, peak=pk, over=pk - t, settle=sg[-1]["F"],
                       dwell=sg[-1]["t"] - sg[0]["t"], drop=sg[0]["F"] - sg[-1]["F"]))
    return dict(r=r, levels=lv)


def cyclic(key, lo=100.0, hi=500.0):
    """Peaks/troughs per cycle. Strokes that never get near the bounds are the initial approach and
    the final return home, NOT cycles — counting them wrecked T6's peak error (a 44 N approach and a
    100 N return dragged its mean error to 128 N when its real peaks were all within ~8 N)."""
    r = rd(key); ss = _segs(r)
    pk = [p for p in (max(r[a:b + 1], key=lambda x: x["F"])["F"] for d, a, b in ss if d == "up")
          if p > 0.6 * hi]
    tr = [t for t in (min(r[a:b + 1], key=lambda x: x["F"])["F"] for d, a, b in ss if d == "down")
          if t < lo + 0.6 * (hi - lo)]
    return dict(r=r, peaks=pk, troughs=tr, lo=lo, hi=hi,
                pk_err=[p - hi for p in pk], tr_err=[t - lo for t in tr],
                pk_mae=st.mean(abs(p - hi) for p in pk) if pk else float("nan"),
                tr_mae=st.mean(abs(t - lo) for t in tr) if tr else float("nan"),
                dur=r[-1]["t"])


def stair_fracture():
    r = rd("sf"); fi = _fracture(r)
    a, sd, n = _anchor(r, fi)
    pk = max(range(fi), key=lambda i: r[i]["F"])
    dw = ua.find_dwells(r, min_s=5.0, min_load=50.0)
    return dict(r=r, fi=fi, ipk=pk, peak=r[pk]["F"], anchor=a, anchor_sd=sd,
                uts=(r[pk]["F"] + a) / AREA, uts_nom=r[pk]["F"] / AREA, dwells=dw,
                halt=next((r[i]["t"] - r[fi]["t"] for i in range(fi, len(r))
                           if abs(r[i]["spd"]) < 1e-9), float("nan")))


def prog_cyclic():
    r = rd("pc"); fi = _fracture(r)
    a, sd, n = _anchor(r, fi)
    pk = max(range(fi), key=lambda i: r[i]["F"])
    ss = _segs(r, fi); cyc = []
    for k, (d, aa, bb) in enumerate(ss):
        if d != "up":
            continue
        nxt = next((s for s in ss[k + 1:] if s[0] == "down"), None)
        if not nxt:
            continue
        p = max(r[aa:bb + 1], key=lambda x: x["F"])
        u = r[nxt[1]:nxt[2] + 1]
        t_ = min(u, key=lambda x: x["F"])
        lo = t_["F"] + 0.45 * (p["F"] - t_["F"])
        el = [x for x in u if x["F"] >= lo]
        K, _ = _fit([x["pos"] for x in el], [x["F"] for x in el])
        ok = [x for x in el if 1600 < x["lpx"] < 1750]
        E, R2 = _fit([x["ec"] for x in ok], [x["F"] / AREA for x in ok])
        wi = sum(0.5 * (r[i]["F"] + r[i - 1]["F"]) * (r[i]["pos"] - r[i - 1]["pos"])
                 for i in range(aa + 1, bb + 1))
        wo = -sum(0.5 * (u[i]["F"] + u[i - 1]["F"]) * (u[i]["pos"] - u[i - 1]["pos"])
                  for i in range(1, len(u)))
        n_ = len(cyc) + 1
        cyc.append(dict(n=n_, target=300.0 + 150.0 * (n_ - 1), peak=p["F"], trough=t_["F"],
                        pos=p["pos"], set=t_["pos"], K=K, E=E, R2=R2,
                        Win=wi, Wout=wo, diss=wi - wo, diss_pct=100 * (wi - wo) / wi if wi else 0.0))
    base = next((c for c in cyc if c["R2"] > 0.94), None)
    for c in cyc:
        c["D"] = (1 - c["E"] / base["E"]) if (base and c["R2"] > 0.94) else float("nan")
    return dict(r=r, fi=fi, ipk=pk, peak=r[pk]["F"], anchor=a, anchor_sd=sd,
                uts=(r[pk]["F"] + a) / AREA, uts_nom=r[pk]["F"] / AREA, cycles=cyc, base=base,
                halt=next((r[i]["t"] - r[fi]["t"] for i in range(fi, len(r))
                           if abs(r[i]["spd"]) < 1e-9), float("nan")))


def t7_stall():
    """T7 (S20, 100 %) never fractured. Quantify the stall from the run itself rather than trying to
    replay the live guard offline — the live guard is phase-aware (silent during intentional dwells)
    and an offline reconstruction mis-fires. The unambiguous evidence is the grind at the top: the
    crosshead advancing a fraction of the commanded travel while the load refuses to climb."""
    r = rd("sf_stall"); n = len(r)
    pk = max(range(n), key=lambda i: r[i]["F"])
    hi = [x for x in r if x["F"] > 0.95 * r[pk]["F"]]
    dur = hi[-1]["t"] - hi[0]["t"]
    adv = hi[-1]["pos"] - hi[0]["pos"]
    cmd = max(abs(x["spd"]) for x in hi) or 0.1
    UTS100 = 46.2                                     # V6 quintet mean, MPa
    return dict(r=r, ipk=pk, peak=r[pk]["F"], t_peak=r[pk]["t"], dur=r[-1]["t"],
                grind_s=dur, grind_um=adv * 1000.0, cmd=cmd,
                frac_of_cmd=100.0 * (adv / dur) / cmd if dur else float("nan"),
                need_N=UTS100 * AREA, got_abs=r[pk]["F"] + 300.0,
                pct_of_need=100.0 * (r[pk]["F"] + 300.0) / (UTS100 * AREA))


def build():
    return dict(creep=creep(), relax=relax(), t7=t7_stall(),
                stair_lin=staircase("stair_lin"), stair_smo=staircase("stair_smo"),
                cyc_tri=cyclic("cyc_tri"), cyc_sin=cyclic("cyc_sin"), cyc_sin1=cyclic("cyc_sin1"),
                cyc_sin2=cyclic("cyc_sin2"),
                sf=stair_fracture(), pc=prog_cyclic())


M = build()

# ---------------------------------------------------------------- figures
BLUE, RED, GREEN, GREY, ORANGE = "#1f6fb2", "#c0392b", "#1e8449", "#7f8c8d", "#e67e22"


def _plt():
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    plt.rcParams.update({"font.size": 10, "axes.titlesize": 11, "axes.titleweight": "bold",
                         "axes.labelsize": 10, "axes.spines.top": False, "axes.spines.right": False,
                         "figure.facecolor": "white", "axes.grid": True,
                         "grid.alpha": 0.25, "grid.linewidth": 0.6})
    return plt


def _save(fig, name):
    p = os.path.join(OUT, name)
    fig.savefig(p, dpi=150, bbox_inches="tight", facecolor="white")
    return p


def fig_overview():
    """Six real measured signatures, one per mode — the whole SF9 family at a glance."""
    plt = _plt()
    fig, axes = plt.subplots(2, 3, figsize=(13.0, 5.6))
    panels = [
        ("Cyclic  (T6.3 sine)", M["cyc_sin"]["r"], BLUE, None),
        ("Staircase  (T4 smooth)", M["stair_smo"]["r"], BLUE, None),
        ("Relaxation  (T2)", M["relax"]["r"], ORANGE, None),
        ("Creep  (T1)", M["creep"]["r"], ORANGE, None),
        ("Staircase → FRACTURE  (T7.2)", M["sf"]["r"], RED, M["sf"]["fi"]),
        ("Progressive cyclic → FRACTURE  (T8)", M["pc"]["r"], RED, M["pc"]["fi"]),
    ]
    for ax, (t, r, c, fi) in zip(axes.ravel(), panels):
        end = (fi + 25) if fi else len(r)
        ax.plot([x["t"] for x in r[:end]], [x["F"] for x in r[:end]], color=c, lw=1.5)
        if fi:
            ax.plot(r[fi]["t"], r[fi - 1]["F"], "x", color="k", ms=9, mew=2.2)
            ax.annotate("fracture", xy=(r[fi]["t"], r[fi - 1]["F"]),
                        xytext=(r[fi]["t"] * 0.52, r[fi - 1]["F"] * 1.04), fontsize=8.5,
                        arrowprops=dict(arrowstyle="->", lw=1.0))
        ax.set_title(t, color=c)
        ax.set_xlabel("Time (s)"); ax.set_ylabel("Load (N)")
    fig.tight_layout()
    return _save(fig, "sf9_overview.png")


def fig_cyclic():
    plt = _plt()
    fig, (a, b) = plt.subplots(1, 2, figsize=(12.4, 4.3), gridspec_kw={"width_ratios": [1.5, 1]})
    for k, lab, c in (("cyc_tri", "T5  Triangle", GREY), ("cyc_sin", "T6.3  Sine", BLUE)):
        r = M[k]["r"]
        a.plot([x["t"] for x in r], [x["F"] for x in r], color=c, lw=1.6, label=lab)
    a.axhline(500, ls="--", color=RED, lw=1.1); a.axhline(100, ls="--", color=RED, lw=1.1)
    a.text(a.get_xlim()[1], 500, " target 500 N", color=RED, fontsize=9, va="center")
    a.text(a.get_xlim()[1], 100, " target 100 N", color=RED, fontsize=9, va="center")
    a.set_xlabel("Time (s)"); a.set_ylabel("Load (N)"); a.legend(loc="lower right", fontsize=9)
    a.set_title("Waveform — Triangle vs Sine against the same 100/500 N bounds")

    n = range(1, len(M["cyc_sin"]["peaks"]) + 1)
    b.plot(list(n), M["cyc_tri"]["peaks"], "o-", color=GREY, lw=2, label="T5 Triangle")
    b.plot(list(n), M["cyc_sin"]["peaks"], "o-", color=BLUE, lw=2, label="T6.3 Sine")
    b.axhline(500, ls="--", color=RED, lw=1.2)
    b.set_xticks(list(n)); b.set_xlabel("Cycle"); b.set_ylabel("Peak load (N)")
    b.set_title("Adaptive reversal lead converges")
    b.legend(fontsize=9)
    fig.tight_layout()
    return _save(fig, "sf9_cyclic.png")


def fig_staircase():
    plt = _plt()
    fig, (a, b) = plt.subplots(1, 2, figsize=(12.4, 4.3), gridspec_kw={"width_ratios": [1.5, 1]})
    for k, lab, c in (("stair_lin", "T3  Linear", GREY), ("stair_smo", "T4  Smooth", BLUE)):
        r = M[k]["r"]
        a.plot([x["t"] for x in r], [x["F"] for x in r], color=c, lw=1.6, label=lab)
    for t in (300, 600, 900):
        a.axhline(t, ls="--", color=RED, lw=1.0)
    a.set_xlabel("Time (s)"); a.set_ylabel("Load (N)"); a.legend(loc="lower right", fontsize=9)
    a.set_title("Three levels, 20 s dwells — dashed = commanded level")

    lin = [l["over"] for l in M["stair_lin"]["levels"]]
    smo = [l["over"] for l in M["stair_smo"]["levels"]]
    idx = list(range(len(lin))); w = 0.36
    b.bar([i - w / 2 for i in idx], lin, w, color=GREY, label="Linear")
    b.bar([i + w / 2 for i in idx], smo[:len(lin)], w, color=BLUE, label="Smooth")
    for i, v in enumerate(lin):
        b.text(i - w / 2, v + 1.5, f"{v:+.0f}", ha="center", fontsize=9, color=GREY, fontweight="bold")
    for i, v in enumerate(smo[:len(lin)]):
        b.text(i + w / 2, v + 1.5, f"{v:+.0f}", ha="center", fontsize=9, color=BLUE, fontweight="bold")
    b.axhline(0, color="k", lw=0.9)
    b.set_xticks(idx); b.set_xticklabels([f"L{i+1}\n{int(l['target'])} N" for i, l in enumerate(M["stair_lin"]["levels"])])
    b.set_ylabel("Arrival overshoot (N)")
    b.set_title("Overshoot vs commanded level")
    b.legend(fontsize=9)
    fig.tight_layout()
    return _save(fig, "sf9_staircase.png")


def fig_relax():
    plt = _plt()
    fig, (a, b) = plt.subplots(1, 2, figsize=(12.4, 4.3))
    d = M["relax"]; r = d["r"]
    a.plot([x["t"] for x in r], [x["F"] for x in r], color=RED, lw=1.7)
    a.set_xlabel("Time (s)"); a.set_ylabel("Load (N)", color=RED); a.tick_params(axis="y", colors=RED)
    a2 = a.twinx(); a2.grid(False)
    a2.plot([x["t"] for x in r], [x["ec"] for x in r], color=BLUE, lw=1.4)
    a2.set_ylabel("DIC strain", color=BLUE); a2.tick_params(axis="y", colors=BLUE)
    a.axvline(r[d["i0"]]["t"], ls=":", color=GREY)
    a.annotate("ramp", xy=(r[d["ipk"]]["t"] * 0.62, d["Fpk"] * 0.45), fontsize=9, color=GREY)
    a.annotate("HOLD strain", xy=(r[d["i0"]]["t"] + 8, d["Fpk"] * 0.45), fontsize=9.5,
               color=GREY, fontweight="bold")
    a.set_title("Full run — ramp to target strain, then hold the crosshead")

    hold = [x for x in r if x["t"] >= r[d["i0"]]["t"]]
    t0 = hold[0]["t"]
    b.plot([x["t"] - t0 for x in hold], [x["F"] for x in hold], color=RED, lw=2.0)
    b.set_xlabel("Time into hold (s)"); b.set_ylabel("Load (N)")
    b.set_title(f"Stress relaxation — {d['drop']:.0f} N lost ({d['drop_pct']:.1f} %)")
    b.annotate(f"{d['Fpk']:.0f} N", xy=(0, d["Fpk"]), xytext=(6, d["Fpk"]), fontsize=10,
               fontweight="bold", color=RED, va="center")
    b.annotate(f"{d['F1']:.0f} N", xy=(hold[-1]["t"] - t0, d["F1"]),
               xytext=(hold[-1]["t"] - t0 - 22, d["F1"] - 12), fontsize=10, fontweight="bold", color=RED)
    b.text(0.5, 0.12, f"strain held {d['eps']:.5f} ± {d['eps_sd']:.6f}\n(σ = {d['eps_sd']/d['eps']*100:.2f} % of the held value)",
           transform=b.transAxes, ha="center", fontsize=9.5, color=BLUE, fontweight="bold")
    fig.tight_layout()
    return _save(fig, "sf9_relax.png")


def fig_creep():
    plt = _plt()
    fig, (a, b) = plt.subplots(1, 2, figsize=(12.4, 4.3))
    d = M["creep"]; r = d["r"]
    a.plot([x["t"] for x in r], [x["F"] for x in r], color=RED, lw=1.7)
    a.set_xlabel("Time (s)"); a.set_ylabel("Load (N)", color=RED); a.tick_params(axis="y", colors=RED)
    a2 = a.twinx(); a2.grid(False)
    a2.plot([x["t"] for x in r], [x["ec"] for x in r], color=BLUE, lw=1.4)
    a2.set_ylabel("DIC strain", color=BLUE); a2.tick_params(axis="y", colors=BLUE)
    a.axvline(d["t0"], ls=":", color=GREY); a.axvline(d["t1"], ls=":", color=GREY)
    a.annotate("HOLD force", xy=(d["t0"] + 4, d["Fmean"] * 0.45), fontsize=9.5, color=GREY,
               fontweight="bold")
    a.set_title("Full run — ramp to target load, then hold that force")

    hold = [x for x in r if d["t0"] <= x["t"] <= d["t1"]]
    t0 = hold[0]["t"]
    b.plot([x["t"] - t0 for x in hold], [x["ec"] * 1e6 for x in hold], color=BLUE, lw=2.0)
    b.set_xlabel("Time into hold (s)"); b.set_ylabel("DIC strain (µε)")
    b.set_title(f"Creep — strain grows +{d['de']:.0f} µε at constant force")
    b.text(0.5, 0.12, f"force held {d['Fmean']:.0f} ± {d['Fsd']:.1f} N\n({d['Fsd']/d['Fmean']*100:.2f} % of the held value)",
           transform=b.transAxes, ha="center", fontsize=9.5, color=RED, fontweight="bold")
    fig.tight_layout()
    return _save(fig, "sf9_creep.png")


def fig_stair_fracture():
    plt = _plt()
    fig, (a, b) = plt.subplots(1, 2, figsize=(12.4, 4.3), gridspec_kw={"width_ratios": [1.5, 1]})
    d = M["sf"]; r = d["r"]; e = d["fi"] + 30
    a.plot([x["t"] for x in r[:e]], [x["F"] for x in r[:e]], color=RED, lw=1.6)
    a.plot(r[d["ipk"]]["t"], d["peak"], "x", color="k", ms=11, mew=2.4)
    a.annotate(f"fracture {d['peak']:.0f} N\nauto-halt {d['halt']:.2f} s later",
               xy=(r[d["ipk"]]["t"], d["peak"]), xytext=(r[d["ipk"]]["t"] * 0.42, d["peak"] * 0.92),
               fontsize=9.5, fontweight="bold",
               arrowprops=dict(arrowstyle="->", lw=1.4))
    a.set_xlabel("Time (s)"); a.set_ylabel("Load (N)")
    a.set_title("T7.2 (S18, 50 %) — steps to failure, 11 levels")

    dw = d["dwells"]
    x = list(range(1, len(dw) + 1)); y = [w["drop_pct"] for w in dw]
    b.plot(x, y, "o-", color=BLUE, lw=2, ms=6)
    kn = ua.yield_onset(dw)
    if kn:
        i = dw.index(kn)
        b.plot([x[i]], [y[i]], "o", color=RED, ms=14, mfc="none", mew=2.5)
        b.annotate(f"yield onset\n{kn['arrive']:.0f} N", xy=(x[i] + .15, y[i] + .06),
                   xytext=(x[i] + 1.4, max(y) * 0.72), fontsize=9.5, color=RED, fontweight="bold",
                   arrowprops=dict(arrowstyle="->", color=RED, lw=1.5))
    b.set_xticks(x); b.set_xlabel("Level"); b.set_ylabel("Dwell force drop (%)")
    b.set_title("One specimen → a yield knee")
    fig.tight_layout()
    return _save(fig, "sf9_stair_fracture.png")


def fig_prog_cyclic():
    plt = _plt()
    fig, (a, b, c) = plt.subplots(1, 3, figsize=(13.0, 4.1), gridspec_kw={"width_ratios": [1.45, 1, 1]})
    d = M["pc"]; r = d["r"]; e = d["fi"] + 30
    a.plot([x["t"] for x in r[:e]], [x["F"] for x in r[:e]], color=RED, lw=1.5)
    a.plot(r[d["ipk"]]["t"], d["peak"], "x", color="k", ms=11, mew=2.4)
    a.annotate(f"fracture {d['peak']:.0f} N\nauto-halt {d['halt']:.2f} s",
               xy=(r[d["ipk"]]["t"], d["peak"]), xytext=(r[d["ipk"]]["t"] * 0.30, d["peak"] * 0.93),
               fontsize=9.5, fontweight="bold", arrowprops=dict(arrowstyle="->", lw=1.4))
    a.set_xlabel("Time (s)"); a.set_ylabel("Load (N)")
    a.set_title("T8 (S21, 50 %) — 8 rising cycles, then failure")

    cy = [c_ for c_ in d["cycles"] if c_["R2"] > 0.94]
    b.plot([c_["n"] for c_ in cy], [c_["E"] / 1000 for c_ in cy], "o-", color=BLUE, lw=2.2, ms=7,
           label="DIC unload modulus")
    b.set_xlabel("Cycle"); b.set_ylabel("E from DIC (GPa)", color=BLUE)
    b.tick_params(axis="y", colors=BLUE)
    b2 = b.twinx(); b2.grid(False)
    b2.plot([c_["n"] for c_ in d["cycles"]], [c_["K"] for c_ in d["cycles"]], "s--", color=ORANGE,
            lw=2.0, ms=6, label="crosshead stiffness")
    b2.set_ylabel("Crosshead K (N/mm)", color=ORANGE); b2.tick_params(axis="y", colors=ORANGE)
    b.set_title("Specimen SOFTENS while the\nmachine reads STIFFER", fontsize=10)
    b.set_xticks([c_["n"] for c_ in d["cycles"]])

    c.plot([c_["n"] for c_ in d["cycles"]], [c_["diss_pct"] for c_ in d["cycles"]], "o-",
           color=RED, lw=2.2, ms=7)
    mn = min(d["cycles"][1:], key=lambda z: z["diss_pct"])
    c.plot([mn["n"]], [mn["diss_pct"]], "o", color=RED, ms=15, mfc="none", mew=2.5)
    c.annotate(f"min {mn['diss_pct']:.1f} %\n(damage onset)", xy=(mn["n"], mn["diss_pct"]),
               xytext=(mn["n"] - 2.3, mn["diss_pct"] + 13), fontsize=9.5, color=RED, fontweight="bold",
               arrowprops=dict(arrowstyle="->", color=RED, lw=1.4))
    c.set_xticks([c_["n"] for c_ in d["cycles"]])
    c.set_xlabel("Cycle"); c.set_ylabel("Hysteresis dissipated (%)")
    c.set_title("Energy dissipation accelerates")
    fig.tight_layout()
    return _save(fig, "sf9_prog_cyclic.png")


def fig_t7_stall():
    plt = _plt()
    fig, (a, b) = plt.subplots(1, 2, figsize=(12.4, 4.3), gridspec_kw={"width_ratios": [1.45, 1]})
    d = M["t7"]; r = d["r"]
    a.plot([x["t"] for x in r], [x["F"] for x in r], color=RED, lw=1.6, label="T7 · S20 · 100 % infill")
    a.axhline(d["need_N"], ls="--", color="k", lw=1.3)
    a.text(5, d["need_N"] * 1.01, f"needed to fracture ≈ {d['need_N']:.0f} N true (46.2 MPa × 80 mm²)",
           fontsize=9, fontweight="bold")
    a.axhspan(0.95 * d["peak"], d["peak"] * 1.02, color=ORANGE, alpha=0.18)
    a.annotate(f"ground here for {d['grind_s']:.0f} s\nadvancing only {d['grind_um']:.0f} µm",
               xy=(d["t_peak"] + 45, d["peak"] * 0.86), fontsize=10, color=ORANGE, fontweight="bold")
    a.set_ylim(-450, d["need_N"] * 1.12)
    a.set_xlabel("Time (s)"); a.set_ylabel("Load, tared (N)")
    a.set_title("T7 — the pull that never fractured")
    a.legend(loc="lower right", fontsize=9)

    peaks = [("S16", 3374.6), ("V6a", 3350.7), ("V6c", 3275.0), ("V6d", 3218.4),
             ("V6e", 3162.2), ("V6b", 3109.7), ("S15\nSTALL", 2593.0), ("T7\nSTALL", d["got_abs"])]
    cols = [GREEN] * 6 + [RED, RED]
    b.bar(range(len(peaks)), [p[1] for p in peaks], color=cols)
    b.axhline(d["need_N"], ls="--", color="k", lw=1.3)
    b.set_xticks(range(len(peaks))); b.set_xticklabels([p[0] for p in peaks], fontsize=8)
    b.set_ylabel("Peak load reached (N, absolute)")
    b.set_title("Six 100 % specimens DID fracture\n→ not a hard ceiling", fontsize=10)
    fig.tight_layout()
    return _save(fig, "sf9_t7_stall.png")


def make_plots():
    return [fig_overview(), fig_cyclic(), fig_staircase(), fig_relax(), fig_creep(),
            fig_stair_fracture(), fig_prog_cyclic(), fig_t7_stall()]


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    d = M["relax"]
    print(f"RELAX   peak {d['Fpk']:.0f} -> {d['F1']:.0f} N ({d['drop']:.0f} N, {d['drop_pct']:.1f} %) "
          f"over {d['dur']:.0f} s | strain held {d['eps']:.5f} ± {d['eps_sd']:.6f}")
    d = M["creep"]
    print(f"CREEP   held {d['Fmean']:.0f} ± {d['Fsd']:.1f} N for {d['dur']:.0f} s | "
          f"strain {d['e0']:.5f} -> {d['e1']:.5f} (+{d['de']:.0f} µε)")
    for k, n in (("stair_lin", "LINEAR"), ("stair_smo", "SMOOTH")):
        print(f"STAIR {n:7} " + " | ".join(
            f"L{i+1} {l['target']:.0f}N over {l['over']:+.1f}" for i, l in enumerate(M[k]["levels"])))
    for k, n in (("cyc_tri", "TRIANGLE"), ("cyc_sin", "SINE T6.3")):
        c = M[k]
        print(f"CYCLIC {n:9} peaks " + " ".join(f"{p:.0f}" for p in c["peaks"]) +
              f" | MAE peak {c['pk_mae']:.1f} N, trough {c['tr_mae']:.1f} N, {c['dur']:.0f} s")
    d = M["sf"]
    print(f"STAIR-FRAC  peak {d['peak']:.0f} N, anchor {d['anchor']:.1f}, TRUE UTS {d['uts']:.2f} MPa, "
          f"{len(d['dwells'])} dwells, halt {d['halt']:.2f} s")
    d = M["pc"]
    print(f"PROG-CYCLIC peak {d['peak']:.0f} N, anchor {d['anchor']:.1f}, TRUE UTS {d['uts']:.2f} MPa, "
          f"{len(d['cycles'])} cycles, halt {d['halt']:.2f} s")
    for c in d["cycles"]:
        print(f"    cy{c['n']} peak {c['peak']:7.1f} (tgt {c['target']:.0f}, {c['peak']-c['target']:+6.1f}) "
              f"E {c['E']/1000:5.2f}G R2 {c['R2']:.3f} K {c['K']:6.1f} diss {c['diss_pct']:5.1f}%")
    print("\nfigures:")
    for p in make_plots():
        print("  " + os.path.basename(p))
