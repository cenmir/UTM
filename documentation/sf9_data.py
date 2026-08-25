"""SF9 (advanced test modes) — metrics + figures for the V6a deck.

Every number on the SF9 slides is computed HERE from the rig CSVs and imported by
generate_v6a_slides.py, so no value is transcribed by hand. Run standalone to regenerate the
figures and print the metric table:

    python documentation/sf9_data.py
"""
import os, sys, math, statistics as st

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.join(_HERE, "..")
_APP = os.path.join(_ROOT, "Software", "UTM_PyQt6")
sys.path.insert(0, _APP)
import utm_analysis as ua                                    # noqa: E402

DATA = os.path.join(_APP, "SF9 - Advanced Test Modes")
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
    # --- follow-up campaign 2026-08-11: the two re-runs that fixed T6.3 and T1 ---
    "cyc_t64":    "Specimen_S22_V1_Spray_CyclicTest_Sine/UTM_Test_20260811_141121_T6.4_CyclicTest_Sine.csv",
    "cyc_t65":    "Specimen_S22_V1_Spray_CyclicTest_Sine/UTM_Test_20260811_145039_T6.5_CyclicTest_Sine.csv",
    "sf_t73":     "Specimen_S22_V1_Spray_Staircase-Fracture/UTM_Test_20260811_151515_T7.3.csv",
    "t9_base":    "Specimen_S23_V1_Spray_CreepTest_T9/UTM_Test_20260811_160552_T9_Baseline.csv",
    "t9_creep":   "Specimen_S23_V1_Spray_CreepTest_T9/UTM_Test_20260811_16461b2_T9_Creep_600N_900s.csv",
}

# ⚠ The `Infill` header field is a LABEL ONLY (it enters no calculation) and the app's 100 % default
# reasserted itself after a restart: T6.4 / T6.5 / T9 all read "Infill: 100 %" in the CSV while the
# specimens (S22, S23) are 50 %. T7.3 has it right. Trust the specimen register, not the header.
INFILL = {"cyc_t64": 50, "cyc_t65": 50, "sf_t73": 50, "t9_base": 50, "t9_creep": 50}


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


def creep_baseline(key="t9_base"):
    """T9 run 1 — the 900 s ZERO-LOAD drift baseline that T1 never had.

    The specimen sits mounted at ~20 N and nothing is commanded, so anything the DIC reports is
    instrument/mount drift. Fitting the SLOPE (not an offset) is what makes it subtractable: the two
    runs are tared separately, so only a rate carries across. The first 30 s are dropped — the
    camera's own settle."""
    r = [x for x in rd(key) if x["lpx"] > 100 and x["t"] >= 30.0]
    t = [x["t"] for x in r]; e = [x["ec"] * 1e6 for x in r]
    slope, R2 = _fit(t, e)
    n = len(t); mt = sum(t) / n
    res = [ee - (slope * tt + (sum(e) / n - slope * mt)) for tt, ee in zip(t, e)]
    sd = st.pstdev(res)                                    # scatter ABOUT the trend = the noise floor
    se = sd / math.sqrt(sum((tt - mt) ** 2 for tt in t))    # standard error of the slope
    half = n // 2
    s1, _ = _fit(t[:half], e[:half]); s2, _ = _fit(t[half:], e[half:])
    F = [x["F"] for x in r]
    return dict(r=r, dur=t[-1] - t[0], n=n, n_raw=len(rd(key)),
                Fmean=st.mean(F), Fsd=st.pstdev(F), pos=r[0]["pos"],
                slope=slope, R2=R2, sd=sd, se=se, ci95=1.96 * se,
                total=slope * (t[-1] - t[0]), s1=s1, s2=s2, ratio=s2 / s1 if s1 else float("nan"),
                sub_err=1.96 * se * 900.0)                 # subtraction uncertainty over a 900 s hold


def creep_t9(key="t9_creep", drift=None, anchor=307.1):
    """T9 run 2 — 600 N tared held for 900 s on S23 (50 % infill), drift-corrected against run 1.

    The hold window is bounded by the load ARRIVING (first sample within 1 % of target after the
    ramp) and by the controller RELEASING (last non-zero commanded speed). Everything after that is
    a fixed-grip relaxation tail, which is a different experiment and must not be folded in.

    Creep vs drift is decided by SHAPE, a criterion fixed before the run: material creep decelerates
    (Findley n < 1, second-half slope < first-half), instrument drift is linear."""
    if drift is None:
        drift = creep_baseline()["slope"]
    r = [x for x in rd(key) if x["lpx"] > 100]
    i0 = next(i for i, x in enumerate(r) if x["F"] > 594.0 and x["t"] > 30.0)
    i1 = max(i for i, x in enumerate(r) if abs(x["spd"]) > 1e-9)
    h = r[i0:i1 + 1]; t0 = h[0]["t"]
    T = [x["t"] - t0 for x in h]
    E = [x["ec"] * 1e6 for x in h]
    Ec = [e - drift * t for e, t in zip(E, T)]             # drift-corrected
    e_inst = sum(Ec[:60]) / 60                             # strain on arrival at the hold load
    F = [x["F"] for x in h]; Fm = st.mean(F)
    raw = E[-1] - E[0]; net = Ec[-1] - Ec[0]
    # Findley power law  Δε = A·t^n  (fit in log-log; n<1 ⇔ decelerating primary creep)
    pts = [(t, e - e_inst) for t, e in zip(T, Ec) if t > 5 and e - e_inst > 1]
    nA, nR2 = _fit([math.log(t) for t, d in pts], [math.log(d) for t, d in pts])
    lA = math.exp((sum(math.log(d) for t, d in pts) - nA * sum(math.log(t) for t, d in pts)) / len(pts))
    half = len(T) // 2
    s1, _ = _fit(T[:half], Ec[:half]); s2, _ = _fit(T[half:], Ec[half:])
    tail = [x for x in r if x["t"] > h[-1]["t"] + 5]
    sig_e = Fm / AREA; sig_t = (Fm + anchor) / AREA
    return dict(r=r, hold=h, T=T, E=E, Ec=Ec, i0=i0, i1=i1, drift=drift,
                dur=T[-1], n=len(h), n_raw=len(rd(key)),
                Fmean=Fm, Fsd=st.pstdev(F), Fmin=min(F), Fmax=max(F),
                pos0=h[0]["pos"], pos1=h[-1]["pos"], dpos_um=(h[-1]["pos"] - h[0]["pos"]) * 1000,
                ddic_um=raw * 1e-6 * GAUGE * 1000, raw=raw, net=net,
                drift_ue=drift * T[-1], drift_pct=100 * drift * T[-1] / raw,
                e_inst=e_inst, ratio_pct=100 * net / e_inst,
                sigma_e=sig_e, sigma_t=sig_t, anchor=anchor,
                J0=e_inst * 1e-6 / sig_e * 1000, J1=Ec[-1] * 1e-6 / sig_e * 1000,
                findley_n=nA, findley_A=lA, findley_R2=nR2,
                s1=s1, s2=s2, ratio=s2 / s1 if s1 else float("nan"),
                spec_frac_um=100 * (raw * 1e-6 * GAUGE) / (h[-1]["pos"] - h[0]["pos"]),
                tail_dur=(tail[-1]["t"] - tail[0]["t"]) if tail else 0.0,
                tail_F0=tail[0]["F"] if tail else float("nan"),
                tail_F1=tail[-1]["F"] if tail else float("nan"),
                tail_drop=(tail[0]["F"] - tail[-1]["F"]) if tail else float("nan"),
                tail_pct=(100 * (1 - tail[-1]["F"] / tail[0]["F"])) if tail else float("nan"))


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
          if 0.5 * lo < t < lo + 0.6 * (hi - lo)]
    return dict(r=r, peaks=pk, troughs=tr, lo=lo, hi=hi,
                pk_err=[p - hi for p in pk], tr_err=[t - lo for t in tr],
                pk_mae=st.mean(abs(p - hi) for p in pk) if pk else float("nan"),
                tr_mae=st.mean(abs(t - lo) for t in tr) if tr else float("nan"),
                dur=r[-1]["t"])


def stair_fracture(key="sf"):
    r = rd(key); fi = _fracture(r)
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
                sf=stair_fracture(), pc=prog_cyclic(),
                # follow-up campaign — the two re-runs plus the fatigued-specimen fracture
                cyc_t64=cyclic("cyc_t64", 400.0, 1100.0), cyc_t65=cyclic("cyc_t65", 400.0, 1100.0),
                loops_t64=cyclic_loops("cyc_t64", 400.0, 1100.0),
                loops_t65=cyclic_loops("cyc_t65", 400.0, 1100.0),
                sf_t73=stair_fracture("sf_t73"),
                # S22's fatigue exposure is T6.4 + T6.5. COUNT it from the load extrema rather than
                # typing it: the deck, the registry and the posters all carried a hand-typed "15"
                # for weeks and nothing recomputed it, so nothing could contradict it. It is 16.
                n_cyc_s22=(len(cyclic("cyc_t64", 400.0, 1100.0)["peaks"])
                           + len(cyclic("cyc_t65", 400.0, 1100.0)["peaks"])),
                t9_base=creep_baseline(), t9=creep_t9())


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


def fig_t9_baseline():
    """T9 run 1 — the zero-load baseline. Two panels: the drift itself with its fit, and the proof
    that it is LINEAR (so subtractable) rather than log-shaped (which would be creep)."""
    plt = _plt()
    b = M["t9_base"]; r = b["r"]
    fig, (a, c) = plt.subplots(1, 2, figsize=(12.4, 4.2), gridspec_kw={"width_ratios": [1.35, 1]})
    t = [x["t"] for x in r]; e = [x["ec"] * 1e6 for x in r]
    a.plot(t, e, color=BLUE, lw=0.9, alpha=0.75, label="DIC strain, no load (%.1f N)" % b["Fmean"])
    ic = sum(e) / len(e) - b["slope"] * (sum(t) / len(t))
    a.plot(t, [b["slope"] * x + ic for x in t], color=RED, lw=2.2,
           label="least-squares drift  %+.4f µε/s  (R² %.2f)" % (b["slope"], b["R2"]))
    a.fill_between(t, [b["slope"] * x + ic - b["sd"] for x in t],
                   [b["slope"] * x + ic + b["sd"] for x in t], color=RED, alpha=0.13,
                   label="±1σ about the trend = ±%.0f µε NOISE FLOOR" % b["sd"])
    a.set_xlabel("Time (s)"); a.set_ylabel("Engineering strain, DIC  (µε)")
    a.legend(fontsize=8.5, loc="upper left")
    a.set_title("Nothing is commanded — so ALL of this is instrument drift\n"
                "%+.0f µε in %.0f s" % (b["total"], b["dur"]), fontsize=10)

    c.bar([0, 1], [b["s1"], b["s2"]], color=[GREY, GREY], width=0.55)
    c.axhline(b["slope"], ls="--", color=RED, lw=1.6, label="whole-run slope")
    for i, v in enumerate((b["s1"], b["s2"])):
        c.text(i, v + 0.012, "%+.3f" % v, ha="center", fontsize=10, fontweight="bold")
    c.set_xticks([0, 1]); c.set_xticklabels(["first half", "second half"])
    c.set_ylabel("Drift rate  (µε/s)"); c.set_ylim(0, max(b["s1"], b["s2"]) * 1.8)
    c.legend(fontsize=9, loc="lower right")
    c.set_title("Ratio %.2f — essentially CONSTANT.\nCreep would decelerate; this does not."
                % b["ratio"], fontsize=10)
    _note(c, 0.03, 0.90, "slope pinned to ±%.4f µε/s (95 %%)\n⇒ subtracting it over a 900 s hold\n"
                         "costs only ±%.0f µε" % (b["ci95"], b["sub_err"]),
          color=GREEN, fs=9, weight="bold")
    fig.tight_layout()
    return _save(fig, "sf9_t9_baseline.png")


def fig_creep_t9():
    """T9 run 2 — the creep hold itself. Force control · the drift-corrected creep curve with its
    Findley fit · the fixed-grip relaxation tail that came free after the policy released."""
    plt = _plt()
    d = M["t9"]; h = d["hold"]; T, E, Ec = d["T"], d["E"], d["Ec"]
    fig, (a, b, c) = plt.subplots(1, 3, figsize=(13.0, 4.2))

    a.plot([x["t"] for x in d["r"]], [x["F"] for x in d["r"]], color=RED, lw=1.4, label="Load")
    a.axvspan(h[0]["t"], h[-1]["t"], color=GREEN, alpha=0.12)
    a.set_xlabel("Time (s)"); a.set_ylabel("Load (N)", color=RED); a.tick_params(axis="y", colors=RED)
    a2 = a.twinx(); a2.grid(False)
    a2.plot([x["t"] for x in d["r"]], [x["pos"] for x in d["r"]], color=BLUE, lw=1.6,
            label="Crosshead position")
    a2.set_ylabel("Crosshead position (mm)", color=BLUE); a2.tick_params(axis="y", colors=BLUE)
    hh, ll = a.get_legend_handles_labels(); h2, l2 = a2.get_legend_handles_labels()
    a.legend(hh + h2, ll + l2, loc="lower right", fontsize=8.5)
    _note(a, 0.30, 0.55, "HOLD  %.1f ± %.1f N\n(±%.2f %% of target)"
          % (d["Fmean"], d["Fsd"], 100 * d["Fsd"] / d["Fmean"]), color=GREEN, fs=9.5, weight="bold")
    _note(a, 0.30, 0.33, "the crosshead must keep ADVANCING\n+%.0f µm to hold that force —\n"
                         "that motion IS the creep" % d["dpos_um"], color="#333", fs=8.5)
    a.set_title("Force held constant — by moving", fontsize=10)

    b.plot(T, E, color=GREY, lw=1.0, alpha=0.8, label="raw DIC  (+%.0f µε)" % d["raw"])
    b.plot(T, Ec, color=BLUE, lw=1.6, label="drift-corrected  (+%.0f µε)" % d["net"])
    fit = [d["e_inst"] + d["findley_A"] * (t ** d["findley_n"]) if t > 0 else d["e_inst"] for t in T]
    b.plot(T, fit, color=RED, lw=2.0, ls="--",
           label="Findley  Δε = %.0f·t^%.2f" % (d["findley_A"], d["findley_n"]))
    b.set_xlabel("Time into hold (s)"); b.set_ylabel("Engineering strain, DIC  (µε)")
    b.legend(fontsize=8.5, loc="lower right")
    _note(b, 0.03, 0.96, "n = %.2f < 1  ⇒  DECELERATING\n= primary creep, not linear drift"
          % d["findley_n"], color=GREEN, fs=9, weight="bold")
    _note(b, 0.03, 0.72, "net %.0f µε  =  %.0f× the %.0f µε noise floor"
          % (d["net"], d["net"] / M["t9_base"]["sd"], M["t9_base"]["sd"]), color="#333", fs=8.5)
    b.set_title("Creep curve — drift removed", fontsize=10)

    tail = [x for x in d["r"] if x["t"] > h[-1]["t"]]
    c.plot([x["t"] - h[-1]["t"] for x in tail], [x["F"] for x in tail], color=ORANGE, lw=1.8)
    c.set_xlabel("Time after the policy released (s)"); c.set_ylabel("Load (N)")
    c.set_title("BONUS — relaxation at frozen grip", fontsize=10)
    _note(c, 0.95, 0.92, "position frozen at %.4f mm\n%.0f → %.0f N  (−%.1f N, −%.1f %%)"
          % (d["pos1"], d["tail_F0"], d["tail_F1"], d["tail_drop"], d["tail_pct"]),
          color="#333", fs=9, ha="right", weight="bold")
    _note(c, 0.95, 0.16, "same specimen, same minute —\na free relaxation dataset", color=GREEN,
          fs=8.5, ha="right")
    fig.tight_layout()
    return _save(fig, "sf9_creep_t9.png")


def fig_creep_compare():
    """T1 vs T9 — why the same MODE gave a negative result once and a clean one the next time."""
    plt = _plt()
    t1, t9, b = M["creep"], M["t9"], M["t9_base"]
    fig, (a, c, e) = plt.subplots(1, 3, figsize=(13.0, 4.0))

    lab = ["stress\n(% of UTS)", "hold\nduration (s)", "creep strain\nmeasured (µε)"]
    v1 = [100 * t1["sigma"] / 46.2, t1["dur"], abs(t1["de"])]
    v9 = [100 * t9["sigma_t"] / 21.2, t9["dur"], t9["net"]]
    x = range(3)
    a.bar([i - 0.2 for i in x], v1, width=0.4, color=GREY, label="T1 (S20, 100 %)")
    a.bar([i + 0.2 for i in x], v9, width=0.4, color=GREEN, label="T9 (S23, 50 %)")
    a.set_yscale("log"); a.set_xticks(list(x)); a.set_xticklabels(lab, fontsize=8.5)
    for i, (p, q) in enumerate(zip(v1, v9)):
        a.text(i - 0.2, p * 1.15, "%.0f" % p, ha="center", fontsize=8.5, fontweight="bold")
        a.text(i + 0.2, q * 1.15, "%.0f" % q, ha="center", fontsize=8.5, fontweight="bold",
               color=GREEN)
    a.legend(fontsize=8.5, loc="upper left")
    a.set_title("Three knobs, all turned the right way", fontsize=10)

    names = ["T1\nmeasured", "T1\nnoise", "T9\nmeasured", "T9\nnoise"]
    vals = [abs(t1["de"]), t1["e_sd"] * 1e6, t9["net"], b["sd"]]
    cols = [GREY, RED, GREEN, RED]
    c.bar(range(4), vals, color=cols)
    for i, v in enumerate(vals):
        c.text(i, v + 25, "%.0f" % v, ha="center", fontsize=9, fontweight="bold")
    c.set_xticks(range(4)); c.set_xticklabels(names, fontsize=8.5)
    c.set_ylabel("Strain  (µε)")
    c.set_title("Signal vs noise — T1 %.1f× · T9 %.0f×"
                % (abs(t1["de"]) / (t1["e_sd"] * 1e6), t9["net"] / b["sd"]), fontsize=10)
    _note(c, 0.03, 0.95, "T1's 'creep' was smaller\nthan its own noise", color=RED, fs=8.5,
          weight="bold")

    e.plot(t9["T"], [x - t9["e_inst"] for x in t9["Ec"]], color=GREEN, lw=1.8, label="T9 — creep")
    e.plot(t9["T"], [b["slope"] * t for t in t9["T"]], color=RED, lw=1.8, ls="--",
           label="baseline drift (subtracted)")
    e.axhline(b["sd"], color=GREY, ls=":", lw=1.2)
    e.axhline(-b["sd"], color=GREY, ls=":", lw=1.2)
    e.fill_between(t9["T"], -b["sd"], b["sd"], color=GREY, alpha=0.18,
                   label="±%.0f µε noise floor" % b["sd"])
    e.set_xlabel("Time into hold (s)"); e.set_ylabel("Strain change  (µε)")
    e.legend(fontsize=8.5, loc="upper left")
    e.set_title("Curved vs straight — the shape test", fontsize=10)
    _note(e, 0.98, 0.42, "creep BENDS OVER, drift does not.\nThat is the discriminator —\n"
                         "and it was fixed BEFORE the run.", color="#333", fs=8.5, ha="right")
    fig.tight_layout()
    return _save(fig, "sf9_creep_compare.png")


def fig_cyclic_t65():
    """T6.5 — the cyclic re-run at 400/1100 N. Loops that actually close, and a modulus that falls."""
    plt = _plt()
    L = M["loops_t65"]; c65 = M["cyc_t65"]
    fig, (a, b, c) = plt.subplots(1, 3, figsize=(13.0, 4.2))

    r = c65["r"]
    a.plot([x["t"] for x in r], [x["F"] for x in r], color=RED, lw=1.3, label="Load")
    a.axhline(1100, ls="--", color=GREEN, lw=1.3); a.axhline(400, ls="--", color=GREEN, lw=1.3)
    a.set_xlabel("Time (s)"); a.set_ylabel("Load (N)")
    a.legend(fontsize=9, loc="lower right")
    _note(a, 0.03, 0.95, "8 cycles · peak error %.1f N\ntrough error %.1f N"
          % (c65["pk_mae"], c65["tr_mae"]), color=GREEN, fs=9, weight="bold")
    a.set_title("400 → 1100 N sine, 8 cycles", fontsize=10)

    cm = plt.get_cmap("viridis")
    for i, l in enumerate(L):
        pts = l["up"] + l["dn"]
        b.plot([x["ec"] * 1e6 for x in pts], [x["F"] / AREA for x in pts],
               color=cm(i / max(1, len(L) - 1)), lw=1.5, label="cycle %d" % l["n"])
    b.set_xlabel("Engineering strain, DIC  (µε)"); b.set_ylabel("Engineering stress  (MPa)")
    b.legend(fontsize=8, loc="upper left", ncol=2)
    b.set_title("Loops CLOSE and drift right\n(%.1f px excursion vs T6.3's %.1f)"
                % (L[0]["px_span"], M["loops_sin"][0]["px_span"]), fontsize=10)

    ns = [l["n"] for l in L]
    c.plot(ns, [l["area_kJm3"] for l in L], "o-", color=ORANGE, lw=2.0, label="loop area (kJ/m³)")
    c.set_xlabel("Cycle"); c.set_ylabel("Loop area  (kJ/m³)", color=ORANGE)
    c.tick_params(axis="y", colors=ORANGE)
    c2 = c.twinx(); c2.grid(False)
    c2.plot(ns, [l["E_dn"] / 1000 for l in L], "s-", color=BLUE, lw=2.0, label="unload E (GPa)")
    c2.set_ylabel("Unload modulus  (GPa)", color=BLUE); c2.tick_params(axis="y", colors=BLUE)
    hh, ll = c.get_legend_handles_labels(); h2, l2 = c2.get_legend_handles_labels()
    c.legend(hh + h2, ll + l2, fontsize=8.5, loc="upper right")
    c.set_title("Both fall monotonically:\n%.1f → %.1f kJ/m³ · %.2f → %.2f GPa"
                % (L[0]["area_kJm3"], L[-1]["area_kJm3"], L[0]["E_dn"] / 1000, L[-1]["E_dn"] / 1000),
                fontsize=10)
    fig.tight_layout()
    return _save(fig, "sf9_cyclic_t65.png")


def fig_cyclic_compare():
    """T6.3 vs T6.5 — the load bounds are the whole story."""
    plt = _plt()
    l3, l5 = M["loops_sin"], M["loops_t65"]
    fig, (a, b, c) = plt.subplots(1, 3, figsize=(13.0, 4.0))

    for LL, col, lab in ((l3, GREY, "T6.3  100→500 N"), (l5, GREEN, "T6.5  400→1100 N")):
        for i, l in enumerate(LL):
            pts = l["up"] + l["dn"]
            a.plot([x["ec"] * 1e6 for x in pts], [x["F"] / AREA for x in pts], color=col, lw=1.3,
                   label=lab if i == 0 else None)
    a.legend(fontsize=9, loc="upper left")
    a.set_xlabel("Engineering strain, DIC  (µε)"); a.set_ylabel("Engineering stress  (MPa)")
    a.set_title("Same mode, same specimen family —\nonly the BOUNDS changed", fontsize=10)

    names = ["T6.3", "T6.5"]
    px = [l3[0]["px_span"], l5[0]["px_span"]]
    b.bar(range(2), px, color=[GREY, GREEN], width=0.5)
    b.axhline(10, ls="--", color=GREEN, lw=1.5)
    for i, v in enumerate(px):
        b.text(i, v + 0.3, "%.1f px" % v, ha="center", fontsize=10, fontweight="bold")
    b.set_xticks(range(2)); b.set_xticklabels(names)
    b.set_ylabel("Strain excursion per cycle  (px)"); b.set_ylim(0, max(px) * 1.35)
    _note(b, 0.03, 0.95, "≥10 px is where the loop\nstops being quantisation noise",
          color=GREEN, fs=9, weight="bold")
    b.set_title("The prediction on p189 was 13.1 px.\nMeasured: %.1f px." % px[1], fontsize=10)

    r2 = [l3[0]["R2_dn"], l5[0]["R2_dn"]]
    ar = [l3[0]["area_kJm3"], l5[0]["area_kJm3"]]
    c.bar([i - 0.2 for i in range(2)], r2, width=0.38, color=BLUE, label="unload-fit R²")
    c2 = c.twinx(); c2.grid(False)
    c2.bar([i + 0.2 for i in range(2)], ar, width=0.38, color=ORANGE, label="loop area (kJ/m³)")
    c.set_xticks(range(2)); c.set_xticklabels(names)
    c.set_ylabel("Unload-fit R²", color=BLUE); c.set_ylim(0, 1.15)
    c2.set_ylabel("Loop area (kJ/m³)", color=ORANGE)
    for i, v in enumerate(r2):
        c.text(i - 0.2, v + 0.03, "%.2f" % v, ha="center", fontsize=9, fontweight="bold")
    for i, v in enumerate(ar):
        c2.text(i + 0.2, v + 0.4, "%.1f" % v, ha="center", fontsize=9, fontweight="bold")
    hh, ll = c.get_legend_handles_labels(); h2, l2 = c2.get_legend_handles_labels()
    c.legend(hh + h2, ll + l2, fontsize=8.5, loc="upper left")
    c.set_title("Modulus becomes fittable and the\nloop area becomes a real number", fontsize=10)
    fig.tight_layout()
    return _save(fig, "sf9_cyclic_compare.png")


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


# Reference-palette categorical slots, assigned in fixed order (skill: never cycle hues).
# Node was unavailable to run validate_palette.js, so these are the palette's own pre-validated
# slots 1/2/3 rather than hand-picked colours.
C_SPEC, C_MACH, C_MEAS = "#2a78d6", "#eb6834", "#1baf7a"
INK, INK2 = "#0b0b0b", "#52514e"


def _spring(ax, x0, x1, y, coils, amp, color, lw=2.4):
    """A zigzag spring. Tighter zigzag = stiffer spring, which is the whole visual point."""
    import numpy as _np
    n = coils * 2
    xs = _np.linspace(x0 + 0.12 * (x1 - x0), x1 - 0.12 * (x1 - x0), n + 1)
    ys = [y + (amp if i % 2 else -amp) for i in range(n + 1)]
    ys[0] = ys[-1] = y
    ax.plot([x0, xs[0]], [y, y], color=color, lw=lw, solid_capstyle="round")
    ax.plot(xs, ys, color=color, lw=lw, solid_capstyle="round")
    ax.plot([xs[-1], x1], [y, y], color=color, lw=lw, solid_capstyle="round")


def fig_teach_stiffness():
    """Teaching figure: why the crosshead reads STIFFER while the specimen SOFTENS."""
    plt = _plt()
    from matplotlib.patches import FancyBboxPatch
    fig = plt.figure(figsize=(13.0, 4.6))
    gs = fig.add_gridspec(1, 3, width_ratios=[1.25, 1.0, 1.05], wspace=0.28)

    # ---- A: what each sensor actually spans -------------------------------------------
    a = fig.add_subplot(gs[0]); a.set_xlim(0, 10); a.set_ylim(0, 10); a.axis("off")
    a.set_title("1 · The two rulers are not the same length", fontsize=11, fontweight="bold")
    parts = [("Motor\n+ screw", 0.3, 1.9, "#dcdcda"), ("Frame", 2.3, 1.5, "#dcdcda"),
             ("Grip", 3.9, 1.1, "#dcdcda"), ("SPECIMEN", 5.1, 2.0, "#cfe3f7"),
             ("Grip", 7.2, 1.1, "#dcdcda"), ("Load\ncell", 8.4, 1.3, "#dcdcda")]
    for lab, x, w, fc in parts:
        a.add_patch(FancyBboxPatch((x, 4.1), w, 1.7, boxstyle="round,pad=0.06",
                                   fc=fc, ec=INK2, lw=1.1))
        a.text(x + w / 2, 4.95, lab, ha="center", va="center", fontsize=8.5,
               fontweight="bold" if "SPEC" in lab else "normal", color=INK)
    a.plot([5.6, 6.6], [5.35, 5.35], "o", color=C_SPEC, ms=7)
    a.text(6.1, 5.9, "DIC dots", ha="center", fontsize=7.5, color=C_SPEC, fontweight="bold")
    a.annotate("", xy=(0.3, 7.0), xytext=(9.7, 7.0),
               arrowprops=dict(arrowstyle="<->", color=C_MEAS, lw=2.2))
    a.text(5.0, 7.35, "CROSSHEAD sees ALL of this", ha="center", fontsize=10,
           color=C_MEAS, fontweight="bold")
    a.annotate("", xy=(5.1, 3.4), xytext=(7.1, 3.4),
               arrowprops=dict(arrowstyle="<->", color=C_SPEC, lw=2.2))
    a.text(6.1, 2.95, "DIC sees ONLY the specimen", ha="center", fontsize=10,
           color=C_SPEC, fontweight="bold")
    a.text(5.0, 1.6, "So the crosshead number always contains the machine.\n"
                     "The DIC number cannot — the dots are on the specimen.",
           ha="center", fontsize=9, color=INK2, style="italic")

    # ---- B: two springs in series ------------------------------------------------------
    b = fig.add_subplot(gs[1]); b.set_xlim(0, 10); b.set_ylim(0, 10); b.axis("off")
    b.set_title("2 · They are two springs in a row", fontsize=11, fontweight="bold")
    for yy, cyc, coil_m, coil_s, km, ks in ((8.15, "Early — cycle 4", 4, 9, 1095, 2325),
                                            (3.95, "Late — cycle 8", 7, 6, 1411, 1727)):
        b.text(0.4, yy + 1.35, cyc, fontsize=9.5, fontweight="bold", color=INK)
        _spring(b, 0.6, 4.5, yy, coil_m, 0.5, C_MACH)
        _spring(b, 5.5, 9.4, yy, coil_s, 0.5, C_SPEC)
        b.text(2.55, yy - 1.15, "MACHINE\n%d N/mm" % km, ha="center", fontsize=8.5,
               color=C_MACH, fontweight="bold", linespacing=1.35)
        b.text(7.45, yy - 1.15, "SPECIMEN\n%d N/mm" % ks, ha="center", fontsize=8.5,
               color=C_SPEC, fontweight="bold", linespacing=1.35)
        b.plot([5.0, 5.0], [yy - 0.45, yy + 0.45], color=INK2, lw=1.0)
    b.annotate("", xy=(1.5, 5.55), xytext=(1.5, 6.55),
               arrowprops=dict(arrowstyle="->", color=C_MACH, lw=2.6))
    b.text(1.8, 6.05, "coils TIGHTEN\n→ stiffer", ha="left", va="center", fontsize=8.5,
           color=C_MACH, fontweight="bold")
    b.annotate("", xy=(6.4, 5.55), xytext=(6.4, 6.55),
               arrowprops=dict(arrowstyle="->", color=C_SPEC, lw=2.6))
    b.text(6.7, 6.05, "coils LOOSEN\n→ softer", ha="left", va="center", fontsize=8.5,
           color=C_SPEC, fontweight="bold")
    b.text(5.0, 1.15, "Pull a spring through a LOOSE CHAIN. As the chain\n"
                      "pulls tight your reading says 'stiffer' — even while\nthe spring itself is weakening.",
           ha="center", fontsize=9, color=INK2, style="italic")

    # ---- C: all three on ONE axis, same units -----------------------------------------
    c = fig.add_subplot(gs[2])
    cy = [x for x in M["pc"]["cycles"] if x["R2"] > 0.94]
    n = [x["n"] for x in cy]
    ks = [x["E"] for x in cy]                       # MPa == N/mm for A=80 mm², L=80 mm
    km = [x["K"] for x in cy]
    kmach = [1.0 / (1.0 / a_ - 1.0 / b_) for a_, b_ in zip(km, ks)]
    c.plot(n, ks, "o-", color=C_SPEC, lw=2.4, ms=8, label="SPECIMEN (from DIC)")
    c.plot(n, kmach, "s-", color=C_MACH, lw=2.4, ms=8, label="MACHINE (deduced)")
    c.plot(n, km, "^-", color=C_MEAS, lw=2.4, ms=8, label="What the crosshead READS")
    c.set_xticks(n); c.set_xlabel("Cycle"); c.set_ylabel("Stiffness  (N/mm)")
    c.set_title("3 · Same units, one axis — now it is obvious", fontsize=11, fontweight="bold")
    c.legend(fontsize=8.5, loc="upper right", framealpha=0.95)
    c.text(n[0] + 0.08, ks[0] + 110, "−26 %", color=C_SPEC, fontsize=9.5, fontweight="bold")
    c.text(n[-1] - 0.15, kmach[-1] - 230, "+29 %", ha="right", color=C_MACH, fontsize=9.5, fontweight="bold")
    c.text(n[-1] - 0.15, km[-1] - 230, "+4 %", ha="right", color=C_MEAS, fontsize=9.5, fontweight="bold")
    c.set_ylim(0, 2700)
    fig.tight_layout()
    return _save(fig, "sf9_teach_stiffness.png")


def fig_teach_dissipation():
    """Teaching figure: why energy loss per cycle dips and then climbs."""
    import numpy as _np
    plt = _plt()
    fig, (a, b) = plt.subplots(1, 2, figsize=(13.0, 4.4), gridspec_kw={"width_ratios": [1, 1.15]})

    x = _np.linspace(1, 8, 200)
    mach = 26 * _np.exp(-(x - 1) / 1.5) + 4        # bedding-in: big, fades fast
    dmg = 0.55 * _np.clip(x - 4.2, 0, None) ** 2.1  # damage: starts late, accelerates
    a.plot(x, mach, "--", color=C_MACH, lw=2.4, label="① Machine bedding in  (fades)")
    a.plot(x, dmg, "--", color=C_SPEC, lw=2.4, label="② Material damaging  (grows)")
    a.plot(x, mach + dmg, "-", color=INK, lw=3.0, label="What you MEASURE  (① + ②)")
    xm = x[int(_np.argmin(mach + dmg))]
    a.axvline(xm, color=INK2, ls=":", lw=1.4)
    a.annotate("THE DIP is just the crossover —\nwhere ① stops falling faster\nthan ② rises",
               xy=(xm + 0.05, float(_np.min(mach + dmg)) + 0.4), xytext=(5.45, 22.0),
               fontsize=9, color=INK2, fontweight="bold", ha="left",
               arrowprops=dict(arrowstyle="->", color=INK2, lw=1.4),
               bbox=dict(facecolor="white", alpha=0.88, edgecolor="none", pad=2.5))
    a.legend(fontsize=9, loc="upper right", framealpha=0.95)
    a.set_xlabel("Cycle"); a.set_ylabel("Energy lost per cycle  (%)")
    a.set_title("Two things are happening at once", fontsize=11, fontweight="bold")
    a.set_ylim(0, 36)

    cy = M["pc"]["cycles"]
    n = [c["n"] for c in cy]; d = [c["diss_pct"] for c in cy]
    mn = min(cy[1:], key=lambda z: z["diss_pct"])
    b.axvspan(0.6, mn["n"], color=C_MACH, alpha=0.10)
    b.axvspan(mn["n"], 8.4, color=C_SPEC, alpha=0.10)
    b.plot(n, d, "o-", color=INK, lw=2.6, ms=8)
    b.plot([mn["n"]], [mn["diss_pct"]], "o", color=INK, ms=15, mfc="none", mew=2.4)
    b.text(3.7, 29.5, "MACHINE settling\ndominates", ha="center", fontsize=9.5,
           color=C_MACH, fontweight="bold")
    b.text(7.1, 12.5, "MATERIAL damage\ndominates", ha="center", fontsize=9.5,
           color=C_SPEC, fontweight="bold")
    b.annotate("cycle %d — the crossover\n(%.1f %%, at %.0f N)" % (mn["n"], mn["diss_pct"], mn["peak"]),
               xy=(mn["n"] - 0.10, mn["diss_pct"] + 0.25), xytext=(2.6, 22.0),
               fontsize=9.5, fontweight="bold", ha="center",
               arrowprops=dict(arrowstyle="->", lw=1.5),
               bbox=dict(facecolor="white", alpha=0.9, edgecolor="none", pad=2.5))
    b.set_xticks(n); b.set_xlim(0.6, 8.4)
    b.set_xlabel("Cycle"); b.set_ylabel("Energy lost per cycle  (%)")
    b.set_title("The real T8 data — same U shape", fontsize=11, fontweight="bold")
    fig.tight_layout()
    return _save(fig, "sf9_teach_dissipation.png")


S17_HALT = os.path.join(_APP, "8.6.20 - Tensile test to Failure", "Specimen_S17_V2_Spray",
                        "StrainRate_Halt_Test_UTM_Test_20260728_211125.csv")


def fig_dic_halt():
    """Regenerates the SF1 dead-DIC proof figure (feat_dic_halt.png).

    The original PNG dates from 2026-07-29 and its generator was never committed, so the deck's
    oldest proof slide could not be rebuilt or audited. This reads the CSV directly.

    Marker count is the raw DIC_Blobs column — no derivation. It is a DISCRETE count (0/1/2), so it
    gets integer ticks and a step plot; the previous version drew it as a continuous line on a
    0.0-2.0 axis with half-marker gridlines, which implies values that cannot exist. Position and
    count are also split into stacked panels rather than sharing one pair of y-axes."""
    plt = _plt()
    rows = [l for l in open(S17_HALT, encoding="utf-8", errors="replace") if not l.startswith("#")]
    h = rows[0].strip().split(",")
    it, ip, ib = h.index("Time_s"), h.index("Position_mm"), h.index("DIC_Blobs")
    d = []
    for r in rows[1:]:
        p = r.split(",")
        try:
            d.append((float(p[it]), float(p[ip]), int(float(p[ib]))))
        except (ValueError, IndexError):
            continue
    w = [x for x in d if 20 <= x[0] <= 32]
    t = [x[0] for x in w]; pos = [x[1] for x in w]; nb = [x[2] for x in w]
    bad0 = next(x[0] for x in w if x[2] < 2)
    bad1 = next(x[0] for x in reversed(w) if x[2] < 2)
    halt = next((w[i][0] for i in range(1, len(w))
                 if abs(w[i][1] - w[-1][1]) < 0.005), bad1)

    fig, (a, b) = plt.subplots(2, 1, figsize=(7.6, 4.6), sharex=True,
                               gridspec_kw={"height_ratios": [2.1, 1], "hspace": 0.12})
    for ax in (a, b):
        ax.axvspan(bad0, bad1, color=RED, alpha=0.10, zorder=0)
    a.plot(t, pos, color="#1e5b3a", lw=2.2)
    a.axvline(halt, color="#1e5b3a", ls=":", lw=1.5)
    a.annotate("guard HALT — motor stopped\n(crosshead frozen at %.2f mm)" % w[-1][1],
               xy=(halt + 0.05, w[-1][1] - 0.02), xytext=(halt + 1.4, w[-1][1] - 0.72), fontsize=9,
               fontweight="bold", color="#1e5b3a",
               arrowprops=dict(arrowstyle="->", color="#1e5b3a", lw=1.5),
               bbox=dict(facecolor="white", alpha=0.88, edgecolor="none", pad=2))
    a.set_ylabel("Crosshead position  (mm)")
    a.set_title("Dead-DIC safety halt — S17 (a marker covered mid-test)",
                fontsize=11, fontweight="bold")

    b.step(t, nb, where="post", color=RED, lw=2.2)
    b.set_yticks([0, 1, 2])                      # a marker count cannot be 0.5
    b.set_ylim(-0.25, 2.35)
    b.set_ylabel("DIC markers\n(raw DIC_Blobs)", fontsize=9.5)
    b.set_xlabel("Time (s)")
    b.text((bad0 + bad1) / 2, 0.42, "markers lost → DIC BAD\n%.2f s" % (bad1 - bad0),
           ha="center", fontsize=9, color=RED, fontweight="bold",
           bbox=dict(facecolor="white", alpha=0.85, edgecolor="none", pad=2))
    for x_, lab in ((bad0, "2→1→0"), (bad1, "0→1→2")):
        b.annotate(lab, xy=(x_, 2.0), xytext=(x_ + (-1.5 if x_ == bad0 else 0.5), 2.15),
                   fontsize=8.5, color=RED, ha="center")
    fig.tight_layout()
    return _save(fig, "images/features/feat_dic_halt.png")


def fig_strain_terms():
    """Engineering vs true strain — both exact, both from the same measured L."""
    import numpy as _np
    plt = _plt()
    from matplotlib.patches import FancyBboxPatch
    fig = plt.figure(figsize=(13.0, 4.0))
    gs = fig.add_gridspec(1, 2, width_ratios=[1.15, 1.0], wspace=0.22)

    a = fig.add_subplot(gs[0]); a.set_xlim(0, 10); a.set_ylim(0, 10); a.axis("off")
    a.set_title("One measurement, two definitions", fontsize=11, fontweight="bold")
    a.add_patch(FancyBboxPatch((0.6, 6.6), 4.2, 1.5, boxstyle="round,pad=0.06",
                               fc="#e8e8e6", ec=INK2, lw=1.1))
    a.plot([1.3, 4.1], [7.35, 7.35], "o", color=C_SPEC, ms=8)
    a.annotate("", xy=(1.3, 6.1), xytext=(4.1, 6.1),
               arrowprops=dict(arrowstyle="<->", color=C_SPEC, lw=1.8))
    a.text(2.7, 5.55, "L₀  (tared at start)", ha="center", fontsize=9.5, color=C_SPEC, fontweight="bold")
    a.text(0.6, 8.5, "BEFORE", fontsize=9.5, fontweight="bold", color=INK2)

    a.add_patch(FancyBboxPatch((0.6, 2.8), 5.6, 1.5, boxstyle="round,pad=0.06",
                               fc="#e8e8e6", ec=INK2, lw=1.1))
    a.plot([1.3, 5.5], [3.55, 3.55], "o", color=C_SPEC, ms=8)
    a.annotate("", xy=(1.3, 2.3), xytext=(5.5, 2.3),
               arrowprops=dict(arrowstyle="<->", color=C_SPEC, lw=1.8))
    a.text(3.4, 1.75, "L  (now)", ha="center", fontsize=9.5, color=C_SPEC, fontweight="bold")
    a.text(0.6, 4.7, "AFTER", fontsize=9.5, fontweight="bold", color=INK2)
    a.text(0.6, 0.65, "The camera measures ONE number: the gap L.\nEverything else is arithmetic on it.",
           fontsize=9, color=INK2, style="italic")

    a.text(6.7, 8.2, "ENGINEERING\n(= nominal, = “Cauchy”)", fontsize=10, fontweight="bold", color=C_SPEC)
    a.text(6.7, 7.0, r"$\varepsilon = \dfrac{L - L_0}{L_0}$", fontsize=15, color=INK)
    a.text(6.7, 6.15, "always ÷ the ORIGINAL length", fontsize=8.5, color=INK2, style="italic")
    a.text(6.7, 4.6, "TRUE\n(= logarithmic, Hencky)", fontsize=10, fontweight="bold", color=C_MACH)
    a.text(6.7, 3.5, r"$\varepsilon = \ln\!\left(\dfrac{L}{L_0}\right)$", fontsize=15, color=INK)
    a.text(6.7, 2.6, "each step ÷ the CURRENT length", fontsize=8.5, color=INK2, style="italic")
    a.text(6.7, 1.5, "Both are EXACT.\nNeither is an estimate of the other.",
           fontsize=9, color=INK2, fontweight="bold")

    b = fig.add_subplot(gs[1])
    e = _np.linspace(0.0005, 0.25, 400)
    diff = 100 * (e - _np.log1p(e)) / e
    b.plot(e * 100, diff, color=C_MACH, lw=2.6)
    b.axvspan(0, 7, color=C_SPEC, alpha=0.13, zorder=0)
    for x_, lab, dy in ((1.0, "at 1 % strain", 2.4), (3.32, "at our ε_f (3.3 %)", 1.7),
                        (7.0, "at V6 worst (7 %)", 1.2)):
        y_ = 100 * (x_ / 100 - math.log1p(x_ / 100)) / (x_ / 100)
        b.plot([x_], [y_], "o", color=C_MACH, ms=8)
        b.annotate("%s → differ %.1f %%" % (lab, y_), xy=(x_, y_), xytext=(x_ + 1.0, y_ + dy),
                   fontsize=8.5, color=C_MACH, fontweight="bold",
                   bbox=dict(facecolor="white", alpha=0.85, edgecolor="none", pad=1.5))
    _note(b, 0.03, 0.96, "shaded = where PLA actually fails\n→ the two definitions agree to ~2 %",
          color=C_SPEC, fs=9, weight="bold")
    b.set_xlabel("Engineering strain  (%)")
    b.set_ylabel("How much they differ  (%)")
    b.set_title("At our strains the choice barely matters", fontsize=11, fontweight="bold")
    b.set_xlim(0, 25); b.set_ylim(0, 13)
    fig.tight_layout()
    return _save(fig, "sf9_strain_terms.png")


def fig_true_stress():
    """How much true stress would change the answer, in the context of errors already carried."""
    import numpy as _np
    plt = _plt()
    fig, (a, b) = plt.subplots(1, 2, figsize=(13.0, 4.0), gridspec_kw={"width_ratios": [1.05, 1]})

    e = _np.linspace(0, 0.22, 300)
    el = 100 * (1 / (1 - 0.35 * e) ** 2 - 1)
    pl = 100 * ((1 + e) - 1)
    a.plot(e * 100, el, color=C_SPEC, lw=2.6, label="elastic, ν = 0.35")
    a.plot(e * 100, pl, "--", color=C_MACH, lw=2.6, label="fully plastic (volume conserved)")
    a.axvspan(0, 7, color=GREEN, alpha=0.13, zorder=0)
    a.legend(fontsize=9, loc="upper left")
    _note(a, 0.97, 0.34, "our whole operating range\nsits in the shaded strip",
          color=GREEN, ha="right", va="bottom", fs=9, weight="bold")
    a.plot([3.32], [3.32], "o", color=INK, ms=9)
    a.annotate("T8 ε_f = 3.3 %\n→ true stress only +3.3 %", xy=(3.32, 3.32), xytext=(6.0, 1.2),
               fontsize=9, fontweight="bold",
               arrowprops=dict(arrowstyle="->", lw=1.4),
               bbox=dict(facecolor="white", alpha=0.9, edgecolor="none", pad=2))
    a.set_xlabel("Engineering strain  (%)")
    a.set_ylabel("True stress is HIGHER by  (%)")
    a.set_title("The size of the correction", fontsize=11, fontweight="bold")
    a.set_xlim(0, 22); a.set_ylim(0, 24)

    pc = M["pc"]
    items = [("Anchor correction\n(preload removed by the tare)", 100 * pc["anchor"] / pc["peak"], C_MACH),
             ("TRUE vs ENGINEERING stress\nat our ε_f", 3.3, C_SPEC),
             ("Specimen-to-specimen\n(T7.2 vs T8)", 0.9, C_MEAS)]
    ypos = range(len(items))
    b.barh(list(ypos), [i[1] for i in items], color=[i[2] for i in items], height=0.55)
    for i, (lab, v, c) in enumerate(items):
        b.text(v + 0.5, i, "%.1f %%" % v, va="center", fontsize=10, fontweight="bold", color=c)
    b.set_yticks(list(ypos)); b.set_yticklabels([i[0] for i in items], fontsize=9)
    b.invert_yaxis()
    b.set_xlabel("Effect on the reported stress  (%)")
    b.set_xlim(0, 27)
    b.set_title("…next to the errors we ALREADY carry", fontsize=11, fontweight="bold")
    _note(b, 0.97, 0.46, "true stress is a ~3 % refinement\nunder a 22 % correction",
          color=INK2, ha="right", fs=9, weight="bold")
    fig.tight_layout()
    return _save(fig, "sf9_true_stress.png")


def make_plots():
    return [fig_overview(), fig_cyclic(), fig_staircase(), fig_relax(), fig_creep(),
            fig_stair_fracture(), fig_prog_cyclic(), fig_t7_stall(),
            fig_stress_strain(), fig_cyclic_hyst(), fig_stair_modulus(), fig_literature(),
            fig_teach_stiffness(), fig_teach_dissipation(), fig_dic_halt(),
            fig_strain_terms(), fig_true_stress(),
            fig_t9_baseline(), fig_creep_t9(), fig_creep_compare(),
            fig_cyclic_t65(), fig_cyclic_compare()]


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
