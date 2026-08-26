"""V6a (S7, 100% infill, LED on) tensile-to-failure analysis + V6a-vs-V5 comparison.
Prints full parameter table, offset factors, and the V6a/V5 deltas.
Reuses the validated anchor + load-collapse fracture logic; adds a DIC baseline
re-zero (V6a baseline e_c ~ -0.0008 from a slightly-early tare).
"""
import sys
sys.stdout.reconfigure(encoding="utf-8")
from statistics import mean, stdev, median

AREA = 80.0; GAUGE = 80.0
ROOT = r"Software\UTM_PyQt6\Test data\8.6.20 - Tensile test to Failure"
FILES = {
    "V5 (S4, 50%)":  ROOT + r"\Specimen_S4_V1_Spray\UTM_Test_20260612_172333_V5_TensionFailure.csv",
    "V6a (S7, 100%)": ROOT + r"\Specimen_S7_V2_Spray\UTM_Test_20260617_165405_V6a_TensionFailure.csv",
}
LIT = {"E": (3.0, 5.5), "sy": (30, 50), "uts": (32, 60)}  # Chacon (2017) FDM PLA


def read_csv(path):
    rows = []
    with open(path, newline="") as f:
        for line in f:
            if line.startswith("#") or not line.strip():
                continue
            rows.append(line.strip())
    idx = {h: i for i, h in enumerate(rows[0].split(","))}
    out = []
    for row in rows[1:]:
        p = row.split(",")
        try:
            out.append({"t": float(p[idx["Time_s"]]), "F": float(p[idx["Force_N"]]),
                        "pos": float(p[idx["Position_mm"]]), "ms": float(p[idx["Motor_Strain"]]),
                        "ec": float(p[idx["DIC_Cauchy"]]), "et": float(p[idx["DIC_True"]]),
                        "lpx": float(p[idx["L_px"]])})
        except (ValueError, IndexError):
            continue
    return out


def linfit(xs, ys):
    n = len(xs); sx, sy = sum(xs), sum(ys)
    sxx = sum(x*x for x in xs); sxy = sum(x*y for x, y in zip(xs, ys))
    sl = (n*sxy - sx*sy)/(n*sxx - sx*sx); ic = (sy - sl*sx)/n
    ym = sy/n
    r2 = 1 - sum((y-(sl*x+ic))**2 for x, y in zip(xs, ys))/sum((y-ym)**2 for y in ys)
    return sl, ic, r2


def analyze(path):
    data = read_csv(path)
    base_pos = sorted(d["pos"] for d in data[:30])[15]
    mv_i = next(i for i, d in enumerate(data) if d["pos"] > base_pos + 0.005)
    t0 = data[mv_i]["t"]
    L0px_list = sorted(d["lpx"] for d in data[:mv_i] if d["lpx"] > 100)
    L0px = L0px_list[len(L0px_list)//2]
    # baseline DIC strain offset (re-zero strain to the preloaded reference)
    ec0_list = [d["ec"] for d in data[:mv_i] if d["lpx"] > 100]
    ec0 = median(ec0_list) if ec0_list else 0.0
    # fracture: markers separate (lpx jump) else load collapse
    fr_lpx = next((i for i in range(mv_i, len(data))
                   if data[i]["lpx"] > 100 and data[i]["lpx"] > 1.06*L0px), None)
    if fr_lpx is not None:
        fr_i = fr_lpx
    else:
        pk_i = max(range(mv_i, len(data)), key=lambda i: data[i]["F"])
        fr_i = next((i for i in range(pk_i, len(data)) if data[i]["F"] < 0.5*data[pk_i]["F"]),
                    len(data) - 1)
    t_fr = data[fr_i]["t"]
    pre = data[:fr_i]
    post = [d for d in data[fr_i+1:] if d["t"] > t_fr+2.0 and d["lpx"] > 100]
    if not post:
        post = [d for d in data[fr_i+1:] if d["t"] > t_fr+2.0]
    anchor = -mean(d["F"] for d in post)
    for d in data:
        d["sig"] = (d["F"]+anchor)/AREA
        d["Ftrue"] = d["F"]+anchor
        d["ecz"] = d["ec"] - ec0           # re-zeroed Cauchy strain
        d["etz"] = d["et"] - ec0
        d["travel"] = d["pos"] - base_pos
    test = [d for d in pre[mv_i:] if d["lpx"] > 100]
    uts = max(test, key=lambda d: d["sig"])
    last = max(test, key=lambda d: d["t"])
    win = [d for d in test if 0.0005 <= d["ecz"] <= 0.004]
    E, c1, r1 = linfit([d["ecz"] for d in win], [d["sig"] for d in win])
    sy = next(d for d in test if E*(d["ecz"]-0.002)+c1 >= d["sig"])
    pl = next((d for d in test if d["ecz"] > 0.004 and d["sig"] < 0.98*(E*d["ecz"]+c1)), None)
    gauge_elong = last["ecz"]*GAUGE
    rig_takeup = last["travel"] - gauge_elong
    base = [d for d in data[:mv_i] if d["t"] > 5]
    tough = 0.0; prev = None
    for d in test:
        if prev and d["ecz"] > prev["ecz"]:
            tough += 0.5*(d["sig"]+prev["sig"])*(d["ecz"]-prev["ecz"])
        prev = d
    rate = (data[fr_i]["pos"]-data[mv_i]["pos"])/(t_fr-t0)
    return {
        "anchor": anchor, "E": E/1000, "E_R2": r1, "E_int": c1, "ec0": ec0,
        "pl_sig": pl["sig"] if pl else float("nan"), "pl_e": pl["ecz"] if pl else float("nan"),
        "sy": sy["sig"], "sy_e": sy["ecz"],
        "uts": uts["sig"], "uts_e": uts["ecz"], "uts_F": uts["Ftrue"], "uts_t": uts["t"]-t0,
        "sigf": last["sig"], "ef": last["ecz"], "ef_true": last["etz"],
        "soften": (uts["sig"]-last["sig"])/uts["sig"]*100,
        "tough": tough*1000,
        "travel_fr": last["travel"], "gauge": gauge_elong, "rig": rig_takeup,
        "rig_k": uts["Ftrue"]/rig_takeup, "gauge_share": gauge_elong/last["travel"]*100,
        "dur": last["t"]-t0, "rate": rate,
        "noiseF": stdev(d["F"] for d in base), "noiseE": stdev(d["ec"] for d in base),
        "dic_track": (data[fr_i-1]["t"]-t0)/(t_fr-t0)*100,
        "npts": len(test), "L0px": L0px,
        # arrays for plotting (re-zeroed)
        "xs": [d["ecz"] for d in test], "ys": [d["sig"] for d in test],
        "xs_pos": [d["travel"] for d in test], "ets": [d["etz"] for d in test],
        "lt_t": [d["t"]-t0 for d in data[mv_i:min(fr_i+14, len(data))]],
        "lt_F": [d["Ftrue"] for d in data[mv_i:min(fr_i+14, len(data))]],
    }


R = {k: analyze(v) for k, v in FILES.items()}
V5, V6 = R["V5 (S4, 50%)"], R["V6a (S7, 100%)"]

rows = [
    ("Crosshead rate", "rate", "mm/s", "%.3f"),
    ("Preload anchor (post-fract.)", "anchor", "N", "%.0f"),
    ("DIC baseline offset e_c0", "ec0", "", "%.6f"),
    ("Elastic modulus E", "E", "GPa", "%.2f"),
    ("  E fit R^2", "E_R2", "", "%.4f"),
    ("Proportional limit sigma", "pl_sig", "MPa", "%.2f"),
    ("Yield sigma_y (0.2%)", "sy", "MPa", "%.2f"),
    ("Yield strain at sigma_y", "sy_e", "", "%.4f"),
    ("UTS", "uts", "MPa", "%.2f"),
    ("UTS strain", "uts_e", "", "%.4f"),
    ("Peak true force", "uts_F", "N", "%.0f"),
    ("Fracture stress", "sigf", "MPa", "%.2f"),
    ("Failure strain e_f (Cauchy)", "ef", "", "%.4f"),
    ("Failure strain e_f (True)", "ef_true", "", "%.4f"),
    ("Softening UTS->fract.", "soften", "%", "%.1f"),
    ("Toughness (nominal vol)", "tough", "kJ/m3", "%.0f"),
    ("Crosshead travel at fract.", "travel_fr", "mm", "%.2f"),
    ("Gauge stretch (DIC)", "gauge", "mm", "%.2f"),
    ("Rig take-up", "rig", "mm", "%.2f"),
    ("Rig stiffness", "rig_k", "N/mm", "%.0f"),
    ("Gauge share of travel", "gauge_share", "%", "%.1f"),
    ("Pull duration", "dur", "s", "%.1f"),
    ("DIC tracking", "dic_track", "%", "%.1f"),
]
print(f"{'Parameter':<30}{'V5 (50%)':>13}{'V6a (100%)':>13}{'V6a/V5':>9}")
print("-"*65)
for label, key, unit, fmt in rows:
    a, b = V5[key], V6[key]
    sa = (fmt % a) + (f" {unit}" if unit else "")
    sb = (fmt % b) + (f" {unit}" if unit else "")
    ratio = f"{b/a:.2f}x" if (key not in ("E_R2", "ec0") and a) else "—"
    print(f"{label:<30}{sa:>13}{sb:>13}{ratio:>9}")

print("\nOffset factor k = Chacon_min / measured:")
for nm, key in [("E", "E"), ("sigma_y", "sy"), ("UTS", "uts")]:
    lo = LIT[key][0]
    print(f"  {nm:8}: V5 k={lo/V5[key]:.2f}   V6a k={lo/V6[key]:.2f}")
print("\nV6a common-factor feasible window [max_lo, min_hi]:")
los = [LIT[p][0]/V6[q] for p, q in [("E","E"),("sy","sy"),("uts","uts")]]
his = [LIT[p][1]/V6[q] for p, q in [("E","E"),("sy","sy"),("uts","uts")]]
print(f"  V6a: [{max(los):.2f}, {min(his):.2f}]   (k=1 means values already in Chacon range)")
print(f"\nV6a peak {V6['uts_F']:.0f} N vs load-cell 29.4 kN -> {V6['uts_F']/29400*100:.1f}% of range")
