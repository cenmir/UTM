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
    """CAUTION: a DIC dropout writes ec=0.0 / lpx=0 into the row rather than skipping it. Taking the
    first and last row of the hold blindly can land on a dropout and manufacture a huge fake strain
    change — it reported +3257 µε of 'creep' when the true change is about -14 µε. Always filter on
    lpx before differencing DIC strain."""
    r = rd("creep")
    h = max((s for s in _segs(r) if s[0] == "hold"), key=lambda s: s[2] - s[1])
    sg = r[h[1]:h[2] + 1]
    F = [x["F"] for x in sg]
    ok = [x for x in sg if x["lpx"] > 100]                      # DIC-valid rows only
    ec = [x["ec"] for x in ok]
    n_drop = len(sg) - len(ok)
    # least-squares drift over the hold is more robust than first-vs-last on noisy data
    slope, _ = _fit([x["t"] for x in ok], ec) if len(ok) > 5 else (float("nan"), 0)
    return dict(r=r, t0=r[h[1]]["t"], t1=r[h[2]]["t"], dur=r[h[2]]["t"] - r[h[1]]["t"],
                F0=sg[0]["F"], F1=sg[-1]["F"], Fmean=st.mean(F), Fsd=st.pstdev(F),
                e0=ok[0]["ec"], e1=ok[-1]["ec"], de=(ok[-1]["ec"] - ok[0]["ec"]) * 1e6,
                e_mean=st.mean(ec), e_sd=st.pstdev(ec), drift_ue_per_s=slope * 1e6,
                n_valid=len(ok), n_drop=n_drop, sigma=st.mean(F) / AREA)


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


def _load_extrema(r, lo, hi):
    """Peak/trough indices taken from the LOAD signal, not the commanded direction.

    The adaptive reversal lead deliberately flips direction BEFORE the load extreme and lets the
    crosshead coast into it, so a speed-based split assigns ~1 s of still-rising load to the
    'unloading' half. That silently corrupted the per-cycle modulus (it returned 0.22 GPa for a
    specimen that is ~2.5 GPa). Hysteresis band keeps noise from producing phantom extrema."""
    band = 0.15 * (hi - lo)
    out, state, best = [], "up", 0
    for i, x in enumerate(r):
        if state == "up":
            if x["F"] > r[best]["F"]:
                best = i
            elif x["F"] < r[best]["F"] - band:
                out.append(("peak", best)); state = "down"; best = i
        else:
            if x["F"] < r[best]["F"]:
                best = i
            elif x["F"] > r[best]["F"] + band:
                out.append(("trough", best)); state = "up"; best = i
    return out


def cyclic_loops(key, lo=100.0, hi=500.0):
    """Closed stress-strain loops per cycle + enclosed area = energy dissipated per unit volume.
    Shoelace over (strain, stress in MPa) gives MJ/m³, reported as kJ/m³. DIC-invalid rows are
    dropped first, or the loop closes through a spurious origin."""
    r = rd(key)
    ex = _load_extrema(r, lo, hi)
    loops = []
    for i in range(len(ex) - 2):
        (k0, a), (k1, b), (k2, c) = ex[i], ex[i + 1], ex[i + 2]
        if not (k0 == "trough" and k1 == "peak" and k2 == "trough"):
            continue
        if r[b]["F"] < 0.6 * hi:
            continue
        up = [x for x in r[a:b + 1] if x["lpx"] > 100]
        dn = [x for x in r[b:c + 1] if x["lpx"] > 100]
        if len(up) < 6 or len(dn) < 6:
            continue
        path = [(x["ec"], x["F"] / AREA) for x in up] + [(x["ec"], x["F"] / AREA) for x in dn]
        A = 0.0
        for j in range(len(path)):
            x1, y1 = path[j]; x2, y2 = path[(j + 1) % len(path)]
            A += x1 * y2 - x2 * y1
        Eup, R2up = _fit([x["ec"] for x in up], [x["F"] / AREA for x in up])
        Edn, R2dn = _fit([x["ec"] for x in dn], [x["F"] / AREA for x in dn])
        # Hysteresis in CROSSHEAD space (work = ∫F·dx, mJ). The strain axis is quantisation-limited
        # at these load bounds (see px_span below), so the stress-strain loop area is noise —
        # crosshead displacement has far finer resolution and the work loop IS meaningful.
        seg = r[a:c + 1]
        wi = sum(0.5 * (r[i]["F"] + r[i - 1]["F"]) * (r[i]["pos"] - r[i - 1]["pos"])
                 for i in range(a + 1, b + 1))
        wo = -sum(0.5 * (r[i]["F"] + r[i - 1]["F"]) * (r[i]["pos"] - r[i - 1]["pos"])
                  for i in range(b + 1, c + 1))
        lp = [x["lpx"] for x in up + dn]
        px_span = max(lp) - min(lp)
        L0 = st.mean(lp)
        loops.append(dict(n=len(loops) + 1, up=up, dn=dn,
                          area_kJm3=abs(A) / 2.0 * 1000.0, peak=r[b]["F"],
                          e_max=max(x["ec"] for x in up), e_min=min(x["ec"] for x in dn),
                          E_up=Eup, R2_up=R2up, E_dn=Edn, R2_dn=R2dn,
                          Win=wi, Wout=wo, diss_mJ=wi - wo,
                          diss_pct=100 * (wi - wo) / wi if wi else float("nan"),
                          px_span=px_span, ue_per_px=1e6 / L0,
                          # the loop only closes if the crosshead comes back to where it started;
                          # at these load bounds it ratchets, so the work integral is not a
                          # hysteresis area and comes out NEGATIVE. Flag it instead of plotting it.
                          ratchet_um=(dn[-1]["pos"] - up[0]["pos"]) * 1000.0,
                          closed=(wi - wo) > 0))
    return loops


def stair_modulus(key, targets=(300.0, 600.0, 900.0)):
    """Modulus re-measured on the RAMP into each level — the claim the Staircase slide makes.
    Each ramp spans its own stress interval, so this is stiffness as a function of stress level."""
    r = rd(key); out = []; prev = 0.0
    for t in targets:
        i0 = next((i for i in range(len(r)) if r[i]["F"] >= prev + 0.25 * (t - prev)), None)
        i1 = next((i for i in range(len(r)) if r[i]["F"] >= t * 0.97), None)
        if i0 is None or i1 is None or i1 <= i0:
            prev = t; continue
        seg = [x for x in r[i0:i1 + 1] if x["lpx"] > 100]
        E, R2 = _fit([x["ec"] for x in seg], [x["F"] / AREA for x in seg])
        out.append(dict(target=t, lo=prev, E=E, R2=R2, n=len(seg),
                        s_lo=prev / AREA, s_hi=t / AREA))
        prev = t
    return out


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
                loops_tri=cyclic_loops("cyc_tri"), loops_sin=cyclic_loops("cyc_sin"),
                mod_lin=stair_modulus("stair_lin"), mod_smo=stair_modulus("stair_smo"),
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
    ok = dic_ok(r)          # dropouts write ec=0.0 and would draw spikes straight down to zero
    a.plot([x["t"] for x in r], [x["F"] for x in r], color=RED, lw=1.7, label="Load")
    a.set_xlabel("Time (s)"); a.set_ylabel("Load (N)", color=RED); a.tick_params(axis="y", colors=RED)
    a2 = a.twinx(); a2.grid(False)
    a2.plot([x["t"] for x in ok], [x["ec"] for x in ok], color=BLUE, lw=1.6, label="DIC strain")
    a2.set_ylabel("Engineering strain, DIC", color=BLUE); a2.tick_params(axis="y", colors=BLUE)
    a2.set_ylim(0, max(x["ec"] for x in ok) * 1.25)
    a.axvline(r[d["i0"]]["t"], ls=":", color=GREY, lw=1.4)
    h, l = a.get_legend_handles_labels(); h2, l2 = a2.get_legend_handles_labels()
    a.legend(h + h2, l + l2, loc="lower right", fontsize=9)
    _note(a, 0.11, 0.42, "ramp\n(strain rising)", color=GREY, fs=9, ha="center", weight="bold")
    _note(a, 0.72, 0.42, "HOLD — crosshead frozen\nstrain flat, force decaying",
          color=GREY, fs=9, ha="center", weight="bold")
    a.set_title("Full run — ramp to target strain, then hold")

    hold = [x for x in r if x["t"] >= r[d["i0"]]["t"]]
    t0 = hold[0]["t"]
    b.plot([x["t"] - t0 for x in hold], [x["F"] for x in hold], color=RED, lw=2.2)
    b.set_xlabel("Time into hold (s)"); b.set_ylabel("Load (N)")
    b.set_title("Stress relaxation — %.0f N lost (%.1f %%)" % (d["drop"], d["drop_pct"]))
    _note(b, 0.03, 0.95, "%.0f N at hold start" % d["Fpk"], color=RED, fs=10, weight="bold")
    _note(b, 0.97, 0.62, "%.0f N after %.0f s" % (d["F1"], d["dur"]), color=RED, fs=10,
          ha="right", weight="bold")
    _note(b, 0.97, 0.95, "strain held %.5f ± %.6f\n(σ = %.2f %% of the held value)"
          % (d["eps"], d["eps_sd"], 100 * d["eps_sd"] / d["eps"]),
          color=BLUE, fs=9.5, ha="right", weight="bold")
    fig.tight_layout()
    return _save(fig, "sf9_relax.png")


def fig_creep():
    plt = _plt()
    fig, (a, b) = plt.subplots(1, 2, figsize=(12.4, 4.3))
    d = M["creep"]; r = d["r"]
    ok = dic_ok(r)
    a.plot([x["t"] for x in r], [x["F"] for x in r], color=RED, lw=1.7, label="Load")
    a.set_xlabel("Time (s)"); a.set_ylabel("Load (N)", color=RED); a.tick_params(axis="y", colors=RED)
    a2 = a.twinx(); a2.grid(False)
    a2.plot([x["t"] for x in ok], [x["ec"] for x in ok], color=BLUE, lw=1.6, label="DIC strain")
    a2.set_ylabel("Engineering strain, DIC", color=BLUE); a2.tick_params(axis="y", colors=BLUE)
    a2.set_ylim(0, max(x["ec"] for x in ok) * 1.35)
    a.axvline(d["t0"], ls=":", color=GREY, lw=1.4); a.axvline(d["t1"], ls=":", color=GREY, lw=1.4)
    h, l = a.get_legend_handles_labels(); h2, l2 = a2.get_legend_handles_labels()
    a.legend(h + h2, l + l2, loc="lower right", fontsize=9)
    _note(a, 0.52, 0.30, "HOLD force — %.0f N" % d["Fmean"], color=GREY, fs=9.5,
          ha="center", weight="bold")
    a.set_title("Full run — ramp to target load, then hold that force")

    hold = [x for x in ok if d["t0"] <= x["t"] <= d["t1"]]
    t0 = hold[0]["t"]
    b.plot([x["t"] - t0 for x in hold], [x["ec"] * 1e6 for x in hold], color=BLUE, lw=1.4,
           label="DIC strain (valid frames)")
    m = d["e_mean"] * 1e6; sd = d["e_sd"] * 1e6
    b.axhline(m, color=GREY, ls="--", lw=1.2)
    b.axhspan(m - sd, m + sd, color=GREY, alpha=0.20, label="±1σ DIC noise (±%.0f µε)" % sd)
    b.set_xlabel("Time into hold (s)"); b.set_ylabel("Engineering strain, DIC  (µε)")
    b.set_ylim(m - 6 * sd, m + 6 * sd)
    b.legend(fontsize=9, loc="upper right")
    b.set_title("Creep — drift %+.2f µε/s, i.e. none resolvable" % d["drift_ue_per_s"])
    _note(b, 0.03, 0.10, "%d of %d rows were DIC dropouts and are excluded —\ndifferencing across "
                         "one faked +3257 µε of 'creep'" % (d["n_drop"], d["n_drop"] + d["n_valid"]),
          color=RED, fs=8.5, va="bottom", weight="bold")
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
    a.set_title("T7.2 (S18, 50 %%) — steps to failure, %d dwells of >=5 s" % len(d["dwells"]))

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


def dic_ok(r, upto=None, hi=1.07):
    """DIC-valid rows with a PLAUSIBILITY bound on marker separation. At fracture the markers fly
    apart and L_px jumps (1668 -> 1825 px = 9 % 'strain') one sample BEFORE the load collapses, so
    slicing at the fracture index alone still lets one garbage point through and stretches every
    stress-strain axis to ~0.10 strain. Real ε_f here is ~3 %, so 7 % is a safe ceiling."""
    d = [x for x in r[:upto or len(r)] if x["lpx"] > 100]
    if not d:
        return d
    L0 = st.median([x["lpx"] for x in d[:200]])
    return [x for x in d if x["lpx"] < L0 * hi]


def _note(ax, x, y, text, color="#333", fs=9.0, ha="left", va="top", weight="normal"):
    """Annotation in AXES coordinates with an opaque-ish backing box, so text placed over a data
    line stays readable and cannot be hidden behind it."""
    return ax.text(x, y, text, transform=ax.transAxes, ha=ha, va=va, fontsize=fs, color=color,
                   fontweight=weight, zorder=20,
                   bbox=dict(facecolor="white", alpha=0.86, edgecolor="none", pad=2.5))


def fig_stress_strain():
    """Engineering stress vs DIC engineering strain for all six modes — the shape of each protocol
    in material space rather than against time."""
    plt = _plt()
    fig, axes = plt.subplots(2, 3, figsize=(13.0, 6.2))
    def ss(ax, r, upto=None, color=BLUE, lw=1.3):
        d = dic_ok(r, upto)
        ax.plot([x["ec"] for x in d], [x["F"] / AREA for x in d], color=color, lw=lw)
        return d

    a = axes[0][0]
    for L, c, lab in ((M["loops_tri"], GREY, "T5 Triangle"), (M["loops_sin"], BLUE, "T6.3 Sine")):
        for i, l in enumerate(L):
            pts = l["up"] + l["dn"]
            a.plot([x["ec"] for x in pts], [x["F"] / AREA for x in pts], color=c, lw=1.2,
                   label=lab if i == 0 else None)
    a.legend(fontsize=8.5, loc="upper left")
    _note(a, 0.97, 0.06, "whole cycle = %.1f px of\nmarker motion (%.0f µε/px)"
          % (M["loops_sin"][0]["px_span"], M["loops_sin"][0]["ue_per_px"]),
          color=RED, ha="right", va="bottom", fs=8.5, weight="bold")
    a.set_title("CYCLIC  [T5 · T6.3]", color=BLUE)

    b = axes[0][1]
    for k, c, lab in (("stair_lin", GREY, "T3 Linear"), ("stair_smo", BLUE, "T4 Smooth")):
        d = dic_ok(M[k]["r"])
        b.plot([x["ec"] for x in d], [x["F"] / AREA for x in d], color=c, lw=1.3, label=lab)
    b.legend(fontsize=8.5, loc="upper left")
    b.set_title("STAIRCASE  [T3 · T4]", color=BLUE)

    c_ = axes[0][2]
    ss(c_, M["relax"]["r"], color=ORANGE, lw=1.6)
    _note(c_, 0.05, 0.94, "vertical drop =\nrelaxation at fixed ε", color=ORANGE, fs=8.5, weight="bold")
    c_.set_title("RELAXATION  [T2]", color=ORANGE)

    d_ = axes[1][0]
    ss(d_, M["creep"]["r"], color=ORANGE, lw=1.6)
    _note(d_, 0.05, 0.94, "hold is a POINT —\nno resolvable creep", color=ORANGE, fs=8.5, weight="bold")
    d_.set_title("CREEP  [T1]", color=ORANGE)

    e_ = axes[1][1]
    ss(e_, M["sf"]["r"], upto=M["sf"]["fi"], color=RED, lw=1.4)
    e_.set_title("STAIRCASE → FRACTURE  [T7.2]", color=RED)

    f_ = axes[1][2]
    ss(f_, M["pc"]["r"], upto=M["pc"]["fi"], color=RED, lw=1.3)
    _note(f_, 0.05, 0.94, "nested loops =\nstiffness degradation", color=RED, fs=8.5, weight="bold")
    f_.set_title("PROGRESSIVE CYCLIC → FRACTURE  [T8]", color=RED)

    for ax in axes.ravel():
        ax.set_xlabel("Engineering strain, DIC  (–)")
        ax.set_ylabel("Engineering stress  (MPa)")
    fig.tight_layout()
    return _save(fig, "sf9_stress_strain.png")


def fig_cyclic_hyst():
    """Why the Cyclic loop is unusable — and it is NOT a resolution problem. The centroid is
    sub-pixel (0.1 px steps, ±0.021 px noise ⇒ SNR ≈ 170 on a 3.6 px loop). The loop is wrecked by a
    ~2 s REVERSAL LAG: at each direction change the load climbs while the strain is still falling,
    which is machine slack being re-taken, not material hysteresis."""
    plt = _plt()
    fig, (a, b, c) = plt.subplots(1, 3, figsize=(13.0, 4.2))
    L = M["loops_sin"][1]; seg = L["up"] + L["dn"]; t0 = seg[0]["t"]
    a.plot([x["t"] - t0 for x in seg], [x["F"] for x in seg], color=RED, lw=1.8, label="Load")
    a.set_xlabel("Time into cycle (s)"); a.set_ylabel("Load (N)", color=RED)
    a.tick_params(axis="y", colors=RED)
    a2 = a.twinx(); a2.grid(False)
    a2.plot([x["t"] - t0 for x in seg], [x["ec"] * 1e6 for x in seg], color=BLUE, lw=1.8,
            label="DIC strain")
    a2.set_ylabel("Engineering strain, DIC (µε)", color=BLUE); a2.tick_params(axis="y", colors=BLUE)
    iF = min(range(len(L["up"])), key=lambda i: L["up"][i]["F"])
    ie = min(range(len(L["up"])), key=lambda i: L["up"][i]["ec"])
    a.axvline(L["up"][iF]["t"] - t0, color=RED, ls=":", lw=1.5)
    a.axvline(L["up"][ie]["t"] - t0, color=BLUE, ls=":", lw=1.5)
    h, l = a.get_legend_handles_labels(); h2, l2 = a2.get_legend_handles_labels()
    a.legend(h + h2, l + l2, loc="upper center", fontsize=9)
    _note(a, 0.04, 0.52, "load min and strain min\nare %.1f s APART\nload +%.0f N while strain %+.0f µε"
          % (L["up"][ie]["t"] - L["up"][iF]["t"], L["up"][ie]["F"] - L["up"][iF]["F"],
             (L["up"][ie]["ec"] - L["up"][iF]["ec"]) * 1e6),
          color="#333", fs=8.5, weight="bold")
    a.set_title("Reversal lag — load rises while\nstrain is still falling", fontsize=10)

    for LL, col, lab in ((M["loops_tri"], GREY, "T5 Triangle"), (M["loops_sin"], BLUE, "T6.3 Sine")):
        for i, l2_ in enumerate(LL):
            pts = l2_["up"] + l2_["dn"]
            b.plot([x["ec"] * 1e6 for x in pts], [x["F"] / AREA for x in pts], color=col, lw=1.3,
                   label=lab if i == 0 else None)
    b.legend(fontsize=9, loc="upper left")
    _note(b, 0.97, 0.05, "loop area here is mostly SLACK,\nnot material hysteresis",
          color=RED, ha="right", va="bottom", fs=9, weight="bold")
    b.set_xlabel("Engineering strain, DIC  (µε)"); b.set_ylabel("Engineering stress  (MPa)")
    b.set_title("Resulting loops — distorted,\nand they never close", fontsize=10)

    names = ["T5\nTriangle", "T6.3\nSine", "T8 cy4", "T8 cy6", "T8 cy8", "T6.4\nPROPOSED"]
    pxs = [M["loops_tri"][0]["px_span"], M["loops_sin"][0]["px_span"], 5.2, 9.8, 14.8, 13.1]
    c.bar(range(6), pxs, color=[GREY, BLUE, RED, RED, RED, GREEN])
    for i, v in enumerate(pxs):
        c.text(i, v + 0.35, "%.1f" % v, ha="center", fontsize=9, fontweight="bold")
    c.axhline(10, ls="--", color=GREEN, lw=1.5)
    _note(c, 0.03, 0.95, "≥10 px gives a usable loop", color=GREEN, fs=9, weight="bold")
    c.set_xticks(range(6)); c.set_xticklabels(names, fontsize=8)
    c.set_ylabel("Strain excursion per cycle  (px)")
    c.set_ylim(0, 17.5)
    c.set_title("Signal size — T6.4 would give\n3.6× the current loop", fontsize=10)
    fig.tight_layout()
    return _save(fig, "sf9_cyclic_hyst.png")


def fig_stair_modulus():
    """Modulus re-measured on the ramp into every level — the Staircase mode's headline claim."""
    plt = _plt()
    fig, (a, b) = plt.subplots(1, 2, figsize=(12.4, 4.3), gridspec_kw={"width_ratios": [1.25, 1]})
    for k, col, lab in (("mod_lin", GREY, "T3 Linear"), ("mod_smo", BLUE, "T4 Smooth")):
        m = M[k]
        a.plot([(x["s_lo"] + x["s_hi"]) / 2 for x in m], [x["E"] / 1000 for x in m], "o-",
               color=col, lw=2.2, ms=8, label=lab)
        for x in m:
            a.annotate("R²%.3f" % x["R2"], xy=((x["s_lo"] + x["s_hi"]) / 2, x["E"] / 1000),
                       xytext=(0, -16), textcoords="offset points", ha="center", fontsize=8,
                       color=col)
    a.axhspan(2.65, 3.06, color=GREEN, alpha=0.13, zorder=0)
    _note(a, 0.03, 0.96, "shaded = literature FDM PLA\n2.65–3.06 GPa", color=GREEN, fs=9, weight="bold")
    a.legend(fontsize=9, loc="lower right")
    a.set_xlabel("Stress interval of the ramp  (MPa)"); a.set_ylabel("Modulus, DIC  (GPa)")
    a.set_title("Modulus re-measured at every level")

    lv = ["L1\n0→3.8", "L2\n3.8→7.5", "L3\n7.5→11.2"]
    w = 0.36; idx = range(len(lv))
    b.bar([i - w / 2 for i in idx], [x["E"] / 1000 for x in M["mod_lin"]], w, color=GREY, label="T3 Linear")
    b.bar([i + w / 2 for i in idx], [x["E"] / 1000 for x in M["mod_smo"]], w, color=BLUE, label="T4 Smooth")
    for i, x in enumerate(M["mod_lin"]):
        b.text(i - w / 2, x["E"] / 1000 + 0.05, "%.2f" % (x["E"] / 1000), ha="center", fontsize=8.5, color=GREY)
    for i, x in enumerate(M["mod_smo"]):
        b.text(i + w / 2, x["E"] / 1000 + 0.05, "%.2f" % (x["E"] / 1000), ha="center", fontsize=8.5, color=BLUE)
    b.set_xticks(list(idx)); b.set_xticklabels(lv, fontsize=8.5)
    b.set_ylabel("Modulus, DIC  (GPa)"); b.set_ylim(0, 3.6)
    b.legend(fontsize=9, loc="lower right")
    b.set_title("Stiffness rises as rig slack is squeezed out")
    fig.tight_layout()
    return _save(fig, "sf9_stair_modulus.png")


# add:north E-PLA TDS rev 2.1 (ISO 527 / 178) — the SAME reference the rest of this deck uses.
# Verified against the PDF: tensile strength at break 58 MPa, tensile modulus 2870 MPa, elongation
# at break 8 %, flexural 120 MPa / 3155 MPa, density 1.24 g/cc, Tg 55-60 °C (DSC), HDT 55 °C.
# The TDS carries NO creep and NO stress-relaxation data — those must come from journals, and the
# slide says so rather than blurring the two sources together.
SPEC = dict(uts=58.0, E=2.87, ef=8.0, tg="55–60 °C", flex=120.0, flex_E=3.155, rho=1.24)


def fig_literature():
    """SF9 results against the add:north E-PLA datasheet — same reference as the V6 slides, so the
    k-factors are directly comparable with p156/p163."""
    plt = _plt()
    fig, (a, b) = plt.subplots(1, 2, figsize=(12.4, 4.2))
    ours = [("T4 staircase\ntop level, 100 %", max(x["E"] for x in M["mod_smo"]) / 1000, BLUE),
            ("V6 quintet\nbroad fit, 100 %", 2.60, BLUE),
            ("T8 cy4\n50 % infill", M["pc"]["cycles"][3]["E"] / 1000, ORANGE),
            ("T8 cy8\n50 %, damaged", M["pc"]["cycles"][7]["E"] / 1000, ORANGE)]
    a.bar(range(len(ours)), [o[1] for o in ours], color=[o[2] for o in ours])
    for i, o in enumerate(ours):
        a.text(i, o[1] + 0.06, "%.2f" % o[1], ha="center", fontsize=9.5, fontweight="bold")
    a.axhline(SPEC["E"], color=GREEN, lw=2.2, ls="--")
    a.set_xticks(range(len(ours))); a.set_xticklabels([o[0] for o in ours], fontsize=8)
    a.set_ylabel("Tensile modulus  (GPa)"); a.set_ylim(0, 3.5)
    _note(a, 0.02, 0.97, "add:north E-PLA TDS · ISO 527 = %.2f GPa" % SPEC["E"],
          color=GREEN, fs=9, weight="bold")
    _note(a, 0.97, 0.06, "staircase top level lands on\nthe datasheet: k = %.2f"
          % (SPEC["E"] / ours[0][1]), color=BLUE, ha="right", va="bottom", fs=9, weight="bold")
    a.set_title("Modulus vs the datasheet")

    lab = ["V6 quintet\n100 % infill", "T7.2\n50 % infill", "T8\n50 % infill"]
    val = [46.2, M["sf"]["uts"], M["pc"]["uts"]]
    b.bar(range(len(val)), val, color=[BLUE, ORANGE, ORANGE])
    for i, v in enumerate(val):
        b.text(i, v + 0.8, "%.1f\nk=%.2f" % (v, SPEC["uts"] / v), ha="center", fontsize=9,
               fontweight="bold")
    b.axhline(SPEC["uts"], color=GREEN, lw=2.2, ls="--")
    b.axhline(46.2 / 2, color=GREY, lw=1.6, ls=":")
    b.set_xticks(range(len(val))); b.set_xticklabels(lab, fontsize=8.5)
    b.set_ylabel("Tensile strength  (MPa)"); b.set_ylim(0, 68)
    _note(b, 0.02, 0.97, "add:north E-PLA TDS · ISO 527 = %.0f MPa" % SPEC["uts"],
          color=GREEN, fs=9, weight="bold")
    _note(b, 0.97, 0.74, "dotted = half of our own 100 % result —\n50 % infill lands on it, k ≈ 2 knock-down",
          color=GREY, ha="right", fs=8.5, weight="bold")
    b.set_title("Strength vs the datasheet, and the infill knock-down")
    fig.tight_layout()
    return _save(fig, "sf9_literature.png")


def make_plots():
    return [fig_overview(), fig_cyclic(), fig_staircase(), fig_relax(), fig_creep(),
            fig_stair_fracture(), fig_prog_cyclic(), fig_t7_stall(),
            fig_stress_strain(), fig_cyclic_hyst(), fig_stair_modulus(), fig_literature()]


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
