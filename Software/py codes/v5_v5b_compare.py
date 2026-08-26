"""Compare V5 (S4) vs V5b (S3) tensile-to-failure tests, both 50% infill, LED off.
Prints all key parameters and % deviation of V5b relative to V5(a).
"""
import sys
sys.stdout.reconfigure(encoding="utf-8")
from statistics import mean, stdev

AREA = 80.0; GAUGE = 80.0
FILES = {
    "V5 (S4)":  r"Software\UTM_PyQt6\Test data\8.6.20 - Tensile test to Failure\Specimen_S4_V1_Spray\UTM_Test_20260612_172333_V5_TensionFailure.csv",
    "V5b (S3)": r"Software\UTM_PyQt6\Test data\8.6.20 - Tensile test to Failure\Specimen_S3_V1_Spray\UTM_Test_20260617_122450__V5b_TensionFailure.csv",
}


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
    mv_i0 = next(i for i, d in enumerate(data) if d["pos"] > 0.005)
    # reference gauge pixel length (median of valid rows during baseline)
    L0px = sorted(d["lpx"] for d in data[:mv_i0] if d["lpx"] > 100)
    L0px = L0px[len(L0px)//2]
    # fracture = first row (after motion) where markers separate: lpx clearly above gauge range
    fr_i = next(i for i in range(mv_i0, len(data))
                if data[i]["lpx"] > 100 and data[i]["lpx"] > 1.06*L0px)
    t_fr = data[fr_i]["t"]
    pre = data[:fr_i]
    post = [d for d in data[fr_i+1:] if d["t"] > t_fr+2.0 and d["lpx"] > 100]
    anchor = -mean(d["F"] for d in post)
    mv_i = next(i for i, d in enumerate(data) if d["pos"] > 0.005)
    t0 = data[mv_i]["t"]
    for d in data:
        d["sig"] = (d["F"]+anchor)/AREA
        d["Ftrue"] = d["F"]+anchor
    test = [d for d in pre[mv_i:] if d["lpx"] > 100]   # drop DIC-dropout rows
    uts = max(test, key=lambda d: d["sig"])
    last = max(test, key=lambda d: d["t"])             # last valid pre-fracture sample
    win = [d for d in test if 0.0005 <= d["ec"] <= 0.004]
    E, c1, r1 = linfit([d["ec"] for d in win], [d["sig"] for d in win])
    sy = next(d for d in test if E*(d["ec"]-0.002)+c1 >= d["sig"])
    pl = next((d for d in test if d["ec"] > 0.004 and d["sig"] < 0.98*(E*d["ec"]+c1)), None)
    gauge_elong = last["ec"]*GAUGE
    rig_takeup = last["pos"]-gauge_elong
    base = [d for d in data[:mv_i] if d["t"] > 5]
    # toughness (per nominal vol)
    tough = 0.0; prev = None
    for d in test:
        if prev and d["ec"] > prev["ec"]:
            tough += 0.5*(d["sig"]+prev["sig"])*(d["ec"]-prev["ec"])
        prev = d
    return {
        "anchor": anchor, "E": E/1000, "E_R2": r1,
        "pl_sig": pl["sig"] if pl else float("nan"), "pl_e": pl["ec"] if pl else float("nan"),
        "sy": sy["sig"], "sy_e": sy["ec"],
        "uts": uts["sig"], "uts_e": uts["ec"], "uts_F": uts["Ftrue"],
        "sigf": last["sig"], "ef": last["ec"], "ef_true": last["et"],
        "soften": (uts["sig"]-last["sig"])/uts["sig"]*100,
        "tough": tough*1000,
        "pos_fr": last["pos"], "gauge": gauge_elong, "rig": rig_takeup,
        "rig_k": uts["Ftrue"]/rig_takeup, "gauge_share": gauge_elong/last["pos"]*100,
        "dur": last["t"]-t0,
        "noiseF": stdev(d["F"] for d in base), "noiseE": stdev(d["ec"] for d in base),
        "dic_track": (data[fr_i-1]["t"]-t0)/(t_fr-t0)*100,
        "npts": len(test),
    }


a = analyze(FILES["V5 (S4)"])
b = analyze(FILES["V5b (S3)"])


def dev(x, y):  # % deviation of b(y) vs a(x)
    return (y-x)/x*100 if x else float("nan")


rows = [
    ("Preload anchor (post-fracture)", "anchor", "N", "%.0f"),
    ("Elastic modulus E", "E", "GPa", "%.2f"),
    ("  E fit R²", "E_R2", "", "%.4f"),
    ("Proportional limit σ", "pl_sig", "MPa", "%.2f"),
    ("Proportional limit ε", "pl_e", "", "%.4f"),
    ("Yield σ_y (0.2% offset)", "sy", "MPa", "%.2f"),
    ("Yield strain ε at σ_y", "sy_e", "", "%.4f"),
    ("UTS", "uts", "MPa", "%.2f"),
    ("UTS strain", "uts_e", "", "%.4f"),
    ("Peak true force", "uts_F", "N", "%.0f"),
    ("Fracture (failure) stress", "sigf", "MPa", "%.2f"),
    ("Failure strain ε_f (Cauchy)", "ef", "", "%.4f"),
    ("Failure strain ε_f (True)", "ef_true", "", "%.4f"),
    ("Softening UTS->fracture", "soften", "%", "%.1f"),
    ("Toughness (nominal vol)", "tough", "kJ/m³", "%.0f"),
    ("Crosshead at fracture", "pos_fr", "mm", "%.2f"),
    ("Gauge stretch (DIC)", "gauge", "mm", "%.2f"),
    ("Rig take-up", "rig", "mm", "%.2f"),
    ("Rig stiffness", "rig_k", "N/mm", "%.0f"),
    ("Gauge share of travel", "gauge_share", "%", "%.1f"),
    ("Test duration (pull)", "dur", "s", "%.1f"),
    ("Baseline force noise (σ)", "noiseF", "N", "%.2f"),
    ("Baseline ε_c noise (σ)", "noiseE", "", "%.6f"),
    ("DIC tracking", "dic_track", "%", "%.1f"),
    ("Hold data points (pull)", "npts", "", "%d"),
]

print(f"{'Parameter':<32}{'V5 (S4)':>14}{'V5b (S3)':>14}{'Δ% vs V5':>11}")
print("-"*71)
for label, key, unit, fmt in rows:
    va, vb = a[key], b[key]
    sa = (fmt % va) + (f" {unit}" if unit else "")
    sb = (fmt % vb) + (f" {unit}" if unit else "")
    d = dev(va, vb)
    ds = f"{d:+.1f}%" if key not in ("E_R2",) else "—"
    print(f"{label:<32}{sa:>14}{sb:>14}{ds:>11}")

# offset factors
print()
print("Offset factor to Chacón lower bound (k = lit_min / measured):")
for nm, val, lit in [("E", "E", 3.0), ("σ_y", "sy", 30), ("UTS", "uts", 32)]:
    print(f"  {nm:4}: V5 k={lit/a[val]:.2f}  | V5b k={lit/b[val]:.2f}")
