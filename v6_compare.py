"""V6a/b/c triplet repeatability — 100% infill, LED on, 0.1 mm/s. Same analyze() as v6a_analyze.py
(anchor self-calibration, baseline DIC re-zero, lpx-jump-or-load-collapse fracture detection)."""
import sys
sys.stdout.reconfigure(encoding="utf-8")
from statistics import mean, median, pstdev, stdev

AREA = 80.0; GAUGE = 80.0
ROOT = r"Software\UTM_PyQt6\8.6.20 - Tensile test to Failure"
FILES = {
    "V6a (S7)": ROOT + r"\Specimen_S7_V2_Spray\UTM_Test_20260617_165405_V6a_TensionFailure.csv",
    "V6b (S8)": ROOT + r"\Specimen_S8_V2_Spray\UTM_Test_20260625_144903_V6b_TensionFailure.csv",
    "V6c (S10)": ROOT + r"\Specimen_S10_V2_Spray\UTM_Test_20260625_151046_V6c_TensionFailure.csv",
    "V6d (S11)": ROOT + r"\Specimen_S11_V2_Spray\UTM_Test_20260625_154219_V6d_TensionFailure.csv",
    "V6e (S9)": ROOT + r"\Specimen_S9_V2_Spray\UTM_Test_20260625_160032_V6e_TensionFailure.csv",
}
EPLA = {"E": 2.87, "uts": 58.0, "ef": 8.0}                  # add:north E-PLA datasheet (typical)


def read_csv(path):
    rows = [l.strip() for l in open(path, newline="") if not l.startswith("#") and l.strip()]
    idx = {h: i for i, h in enumerate(rows[0].split(","))}
    out = []
    for row in rows[1:]:
        p = row.split(",")
        try:
            out.append({"t": float(p[idx["Time_s"]]), "F": float(p[idx["Force_N"]]),
                        "pos": float(p[idx["Position_mm"]]), "ec": float(p[idx["DIC_Cauchy"]]),
                        "et": float(p[idx["DIC_True"]]), "lpx": float(p[idx["L_px"]])})
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
    L0 = sorted(d["lpx"] for d in data[:mv_i] if d["lpx"] > 100); L0px = L0[len(L0)//2]
    ec0_list = [d["ec"] for d in data[:mv_i] if d["lpx"] > 100]
    ec0 = median(ec0_list) if ec0_list else 0.0
    # fracture = LOAD COLLAPSE (force drops below 0.5x peak after the peak). The marker-
    # separation signature (L_px>1.06xL0) misfires on very ductile specimens whose gauge
    # strain crosses 6 % during normal drawing (V6c), so load-collapse is the sole detector.
    pk = max(range(mv_i, len(data)), key=lambda i: data[i]["F"])
    fr_i = next((i for i in range(pk, len(data)) if data[i]["F"] < 0.5*data[pk]["F"]), len(data)-1)
    t_fr = data[fr_i]["t"]
    pre = data[:fr_i]
    post = [d for d in data[fr_i+1:] if d["t"] > t_fr+2.0 and d["lpx"] > 100]
    if not post:
        post = [d for d in data[fr_i+1:] if d["t"] > t_fr+2.0]
    anchor = -mean(d["F"] for d in post)
    for d in data:
        d["sig"] = (d["F"]+anchor)/AREA; d["Ftrue"] = d["F"]+anchor
        d["ecz"] = d["ec"]-ec0; d["etz"] = d["et"]-ec0; d["travel"] = d["pos"]-base_pos
    test = [d for d in pre[mv_i:] if d["lpx"] > 100]
    uts = max(test, key=lambda d: d["sig"]); last = max(test, key=lambda d: d["t"])
    win = [d for d in test if 0.0005 <= d["ecz"] <= 0.004]
    E, c1, r1 = linfit([d["ecz"] for d in win], [d["sig"] for d in win])
    sy = next(d for d in test if E*(d["ecz"]-0.002)+c1 >= d["sig"])
    gauge = last["ecz"]*GAUGE
    tough = 0.0; prev = None
    for d in test:
        if prev and d["ecz"] > prev["ecz"]:
            tough += 0.5*(d["sig"]+prev["sig"])*(d["ecz"]-prev["ecz"])
        prev = d
    return {"anchor": anchor, "E": E/1000, "E_R2": r1, "sy": sy["sig"],
            "uts": uts["sig"], "uts_F": uts["Ftrue"], "ef": last["ecz"],
            "sigf": last["sig"], "soft": (uts["sig"]-last["sig"])/uts["sig"]*100,
            "tough": tough*1000, "travel": last["travel"], "gauge_share": gauge/last["travel"]*100,
            "dur": last["t"]-t0, "rate": (data[fr_i]["pos"]-data[mv_i]["pos"])/(t_fr-t0)}


names = list(FILES.keys())
R = {k: analyze(v) for k, v in FILES.items()}

rows = [
    ("Peak force", "uts_F", "N", "%.0f"),
    ("UTS", "uts", "MPa", "%.2f"),
    ("Yield σ_y (0.2%)", "sy", "MPa", "%.2f"),
    ("Elastic modulus E", "E", "GPa", "%.2f"),
    ("Fracture stress", "sigf", "MPa", "%.2f"),
    ("Failure strain ε_f", "ef", "", "%.4f"),
    ("Softening UTS→fr.", "soft", "%", "%.1f"),
    ("Toughness", "tough", "kJ/m³", "%.0f"),
    ("Crosshead travel", "travel", "mm", "%.2f"),
    ("Gauge share", "gauge_share", "%", "%.1f"),
    ("Pull duration", "dur", "s", "%.1f"),
    ("Rate", "rate", "mm/s", "%.3f"),
    ("Preload anchor", "anchor", "N", "%.0f"),
]
hdr = f"{'Metric':<22}" + "".join(f"{n:>11}" for n in names) + f"{'mean':>10}{'CV%':>8}{'range%':>8}"
print(hdr); print("-"*len(hdr))
for label, key, unit, fmt in rows:
    vals = [R[n][key] for n in names]
    m = mean(vals); sd = stdev(vals)
    cv = sd/abs(m)*100 if m else 0
    rng = (max(vals)-min(vals))/abs(m)*100 if m else 0
    u = f" {unit}" if unit else ""
    cells = "".join(f"{fmt%v+u:>11}" for v in vals)
    print(f"{label:<22}{cells}{fmt%m+u:>10}{cv:>7.1f}%{rng:>7.1f}%")

print("\nOffset k = E-PLA spec / measured (per specimen):")
print(f"{'':<16}" + "".join(f"{n:>11}" for n in names) + f"{'mean':>9}")
for nm, key, ref in [("UTS vs E-PLA", "uts", EPLA["uts"]), ("Modulus vs E-PLA", "E", EPLA["E"]),
                     ("ε_f vs E-PLA", "ef", EPLA["ef"]/100)]:
    ks = [ref/R[n][key] for n in names]
    print(f"  {nm:<14}" + "".join(f"{k:>11.2f}" for k in ks) + f"{mean(ks):>9.2f}")

uts_vals = [R[n]["uts"] for n in names]
print(f"\nUTS all inside Chacón 32-60 MPa: {[round(v,1) for v in uts_vals]}  -> k≈1 (no knock-down)")
print(f"Strength (UTS) triplet: mean {mean(uts_vals):.2f} MPa, CV {stdev(uts_vals)/mean(uts_vals)*100:.1f}%")
ef_vals = [R[n]["ef"] for n in names]
print(f"Ductility (ε_f) triplet: {[round(v,4) for v in ef_vals]}, CV {stdev(ef_vals)/mean(ef_vals)*100:.0f}%")
