"""Compare V5 (S4) / V5b (S3) / V5c (S2) tensile-to-failure tests.
All 50% infill, LED off. Prints 3-way table with %-deviation vs V5(a),
offset factors, and overlay comparison plots.
"""
import sys
sys.stdout.reconfigure(encoding="utf-8")
from statistics import mean, stdev
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

AREA = 80.0; GAUGE = 80.0
ROOT = r"Software\UTM_PyQt6\8.6.20 - Tensile test to Failure"
FILES = {
    "V5 (S4)":  ROOT + r"\Specimen_S4_V1_Spray\UTM_Test_20260612_172333_V5_TensionFailure.csv",
    "V5b (S3)": ROOT + r"\Specimen_S3_V1_Spray\UTM_Test_20260617_122450__V5b_TensionFailure.csv",
    # canonical V5c = 0.1 mm/s run (rate-matched to V5/V5b). The 0.2 mm/s re-run is "V5c2".
    "V5c (S2)": ROOT + r"\Specimen_S2_V1_Spray\UTM_Test_20260617_130559_V5c_0_TensionFailure.csv",
}
COLORS = {"V5 (S4)": "#1f77b4", "V5b (S3)": "#2e7d32", "V5c (S2)": "#d62728"}


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
    # baseline crosshead position (position may NOT be zeroed, e.g. V5c ~4.71 mm)
    base_pos = sorted(d["pos"] for d in data[:30])[15]
    # motion start: first row where crosshead advances past baseline
    mv_i = next(i for i, d in enumerate(data) if d["pos"] > base_pos + 0.005)
    t0 = data[mv_i]["t"]
    # reference gauge pixel length (median of valid baseline rows)
    L0px_list = sorted(d["lpx"] for d in data[:mv_i] if d["lpx"] > 100)
    L0px = L0px_list[len(L0px_list)//2]
    # fracture detection — two signatures:
    #  (a) markers separate: L_px jumps >6% above gauge length (V5, V5b)
    #  (b) halves recoil:    L_px drops back, no jump → fall back to load collapse (new V5c)
    fr_lpx = next((i for i in range(mv_i, len(data))
                   if data[i]["lpx"] > 100 and data[i]["lpx"] > 1.06*L0px), None)
    if fr_lpx is not None:
        fr_i = fr_lpx
    else:
        pk_i = max(range(mv_i, len(data)), key=lambda i: data[i]["F"])
        pk_F = data[pk_i]["F"]
        fr_i = next((i for i in range(pk_i, len(data)) if data[i]["F"] < 0.5 * pk_F),
                    len(data) - 1)
    t_fr = data[fr_i]["t"]
    pre = data[:fr_i]
    post = [d for d in data[fr_i+1:] if d["t"] > t_fr+2.0 and d["lpx"] > 100]
    anchor = -mean(d["F"] for d in post)
    for d in data:
        d["sig"] = (d["F"]+anchor)/AREA
        d["Ftrue"] = d["F"]+anchor
        d["travel"] = d["pos"] - base_pos
    test = [d for d in pre[mv_i:] if d["lpx"] > 100]   # drop DIC-dropout rows
    uts = max(test, key=lambda d: d["sig"])
    last = max(test, key=lambda d: d["t"])
    win = [d for d in test if 0.0005 <= d["ec"] <= 0.004]
    E, c1, r1 = linfit([d["ec"] for d in win], [d["sig"] for d in win])
    sy = next(d for d in test if E*(d["ec"]-0.002)+c1 >= d["sig"])
    pl = next((d for d in test if d["ec"] > 0.004 and d["sig"] < 0.98*(E*d["ec"]+c1)), None)
    gauge_elong = last["ec"]*GAUGE
    rig_takeup = last["travel"] - gauge_elong
    base = [d for d in data[:mv_i] if d["t"] > 5]
    tough = 0.0; prev = None
    for d in test:
        if prev and d["ec"] > prev["ec"]:
            tough += 0.5*(d["sig"]+prev["sig"])*(d["ec"]-prev["ec"])
        prev = d
    return {
        "anchor": anchor, "E": E/1000, "E_R2": r1, "E_int": c1,
        "pl_sig": pl["sig"] if pl else float("nan"), "pl_e": pl["ec"] if pl else float("nan"),
        "sy": sy["sig"], "sy_e": sy["ec"],
        "uts": uts["sig"], "uts_e": uts["ec"], "uts_F": uts["Ftrue"],
        "sigf": last["sig"], "ef": last["ec"], "ef_true": last["et"],
        "soften": (uts["sig"]-last["sig"])/uts["sig"]*100,
        "tough": tough*1000,
        "travel_fr": last["travel"], "gauge": gauge_elong, "rig": rig_takeup,
        "rig_k": uts["Ftrue"]/rig_takeup, "gauge_share": gauge_elong/last["travel"]*100,
        "dur": last["t"]-t0,
        "noiseF": stdev(d["F"] for d in base), "noiseE": stdev(d["ec"] for d in base),
        "dic_track": (data[fr_i-1]["t"]-t0)/(t_fr-t0)*100,
        "npts": len(test),
        # curve arrays for plotting (loading portion only)
        "xs": [d["ec"] for d in test], "ys": [d["sig"] for d in test],
        "xs_pos": [d["travel"] for d in test],
        # load-vs-time (force always valid; include a few rows past fracture for the drop)
        "lt_t": [d["t"]-t0 for d in data[mv_i:min(fr_i+12, len(data))]],
        "lt_F": [d["Ftrue"] for d in data[mv_i:min(fr_i+12, len(data))]],
        "uts_ts": uts["t"]-t0, "uts_Fp": uts["Ftrue"],
    }


R = {k: analyze(v) for k, v in FILES.items()}
KEYS = list(FILES.keys())
A = R[KEYS[0]]


def dev(x, y):
    return (y-x)/x*100 if x else float("nan")


rows = [
    ("Preload anchor (post-fracture)", "anchor", "N", "%.0f"),
    ("Elastic modulus E", "E", "GPa", "%.2f"),
    ("  E fit R^2", "E_R2", "", "%.4f"),
    ("Proportional limit sigma", "pl_sig", "MPa", "%.2f"),
    ("Yield sigma_y (0.2% offset)", "sy", "MPa", "%.2f"),
    ("Yield strain at sigma_y", "sy_e", "", "%.4f"),
    ("UTS", "uts", "MPa", "%.2f"),
    ("UTS strain", "uts_e", "", "%.4f"),
    ("Peak true force", "uts_F", "N", "%.0f"),
    ("Fracture (failure) stress", "sigf", "MPa", "%.2f"),
    ("Failure strain eps_f (Cauchy)", "ef", "", "%.4f"),
    ("Softening UTS->fracture", "soften", "%", "%.1f"),
    ("Toughness (nominal vol)", "tough", "kJ/m3", "%.0f"),
    ("Crosshead travel at fracture", "travel_fr", "mm", "%.2f"),
    ("Gauge stretch (DIC)", "gauge", "mm", "%.2f"),
    ("Rig take-up", "rig", "mm", "%.2f"),
    ("Rig stiffness", "rig_k", "N/mm", "%.0f"),
    ("Gauge share of travel", "gauge_share", "%", "%.1f"),
    ("Pull duration", "dur", "s", "%.1f"),
    ("Baseline force noise (sd)", "noiseF", "N", "%.2f"),
    ("Baseline eps_c noise (sd)", "noiseE", "", "%.6f"),
    ("DIC tracking", "dic_track", "%", "%.1f"),
]

hdr = f"{'Parameter':<31}" + "".join(f"{k:>13}" for k in KEYS) + f"{'d% V5b':>9}{'d% V5c':>9}"
print(hdr); print("-"*len(hdr))
for label, key, unit, fmt in rows:
    cells = "".join(f"{(fmt % R[k][key]):>13}" for k in KEYS)
    if key == "E_R2":
        d1 = d2 = "—"
    else:
        d1 = f"{dev(A[key], R[KEYS[1]][key]):+.1f}%"
        d2 = f"{dev(A[key], R[KEYS[2]][key]):+.1f}%"
    print(f"{label:<31}{cells}{d1:>9}{d2:>9}")

# ---- mean +/- spread across the 3 specimens for headline metrics ----
print("\nRepeatability (mean +/- range across V5/V5b/V5c):")
for label, key in [("E (GPa)", "E"), ("sigma_y (MPa)", "sy"), ("UTS (MPa)", "uts"),
                   ("eps_f", "ef"), ("Peak force (N)", "uts_F")]:
    vals = [R[k][key] for k in KEYS]
    m = mean(vals); rng = (max(vals)-min(vals))/m*100
    cv = stdev(vals)/m*100
    print(f"  {label:<16} {m:8.3f}  spread {rng:5.1f}%  CV {cv:4.1f}%")

# ---- offset factors ----
print("\nOffset factor k = Chacon_lower / measured:")
LIT = {"E": (3.0, 5.5), "sy": (30, 50), "uts": (32, 60)}
for key, nm in [("E", "E"), ("sy", "sigma_y"), ("uts", "UTS")]:
    lo = LIT[key][0]
    ks = [lo/R[k][key] for k in KEYS]
    print(f"  {nm:7}: " + "  ".join(f"{k}={v:.2f}" for k, v in zip(KEYS, ks))
          + f"   mean={mean(ks):.2f}")

# common-factor feasible window (intersection over all 3 specimens)
print("\nSingle common offset factor feasible window per specimen [max_lo, min_hi]:")
for k in KEYS:
    los = [LIT[p][0]/R[k][q] for p, q in [("E","E"),("sy","sy"),("uts","uts")]]
    his = [LIT[p][1]/R[k][q] for p, q in [("E","E"),("sy","sy"),("uts","uts")]]
    print(f"  {k}: [{max(los):.2f}, {min(his):.2f}]")

# ============ PLOT 1: overlay stress-strain ============
plt.rcParams.update({"font.size": 13})
fig, ax = plt.subplots(figsize=(12, 6.5))
for k in KEYS:
    ax.plot(R[k]["xs"], R[k]["ys"], "-", color=COLORS[k], lw=2.2, alpha=0.9,
            label=f"{k}: UTS {R[k]['uts']:.1f} MPa, e_f {R[k]['ef']:.4f}")
    ax.plot(R[k]["uts_e"], R[k]["uts"], "v", color=COLORS[k], ms=11, mec="black", mew=0.6)
    ax.plot(R[k]["ef"], R[k]["sigf"], "x", color=COLORS[k], ms=12, mew=2.8)
ax.set_xlabel("DIC Cauchy strain ε_c"); ax.set_ylabel("Engineering stress (MPa, nominal 80 mm²)")
ax.set_title("V5 / V5b / V5c — stress-strain overlay (50 % infill, LED off)", fontweight="bold")
ax.grid(alpha=0.3); ax.legend(loc="lower right", fontsize=11)
ax.set_xlim(-0.001, 0.034); ax.set_ylim(0, 24)
plt.tight_layout(); plt.savefig("images/V5/V5abc_stress_strain.png", dpi=150, bbox_inches="tight"); plt.close()

# ============ PLOT 2: grouped bars E / sigma_y / UTS ============
fig, ax = plt.subplots(figsize=(11, 6))
metrics = [("E×5 (GPa)", "E", 5.0), ("σ_y (MPa)", "sy", 1.0), ("UTS (MPa)", "uts", 1.0)]
xbase = range(len(metrics))
w = 0.25
for j, k in enumerate(KEYS):
    vals = [R[k][key]*scale for _, key, scale in metrics]
    xs = [x + (j-1)*w for x in xbase]
    bars = ax.bar(xs, vals, w, color=COLORS[k], label=k, edgecolor="black", lw=0.5)
    for x, key, scale in zip(xs, [m[1] for m in metrics], [m[2] for m in metrics]):
        ax.text(x, R[k][key]*scale + 0.3, f"{R[k][key]:.1f}", ha="center", fontsize=9)
ax.set_xticks(list(xbase)); ax.set_xticklabels([m[0] for m in metrics])
ax.set_ylabel("value (E shown ×5 for scale)")
ax.set_title("V5 / V5b / V5c — key properties (50 % infill, LED off)", fontweight="bold")
ax.legend(fontsize=11); ax.grid(axis="y", alpha=0.3)
plt.tight_layout(); plt.savefig("images/V5/V5abc_bars.png", dpi=150, bbox_inches="tight"); plt.close()

# ============ PLOT 3: offset factor per specimen ============
fig, ax = plt.subplots(figsize=(11, 6))
props = [("E", "E", 3.0), ("σ_y", "sy", 30), ("UTS", "uts", 32)]
xbase = range(len(props))
for j, k in enumerate(KEYS):
    ks = [LIT[key][0]/R[k][key] for _, key, _ in props]
    xs = [x + (j-1)*w for x in xbase]
    ax.bar(xs, ks, w, color=COLORS[k], label=k, edgecolor="black", lw=0.5)
    for x, v in zip(xs, ks):
        ax.text(x, v+0.03, f"{v:.2f}", ha="center", fontsize=9)
ax.axhspan(1.95, 2.63, color="gray", alpha=0.15, label="common-factor window")
ax.axhline(2.0, color="black", ls="--", lw=1, label="k = 2.0")
ax.set_xticks(list(xbase)); ax.set_xticklabels([p[0] for p in props])
ax.set_ylabel("offset factor k = lit_min / measured")
ax.set_title("V5 / V5b / V5c — infill offset factor (to Chacón lower bound)", fontweight="bold")
ax.legend(fontsize=10, ncol=2); ax.grid(axis="y", alpha=0.3); ax.set_ylim(0, 3.0)
plt.tight_layout(); plt.savefig("images/V5/V5abc_offset.png", dpi=150, bbox_inches="tight"); plt.close()

# ============ PLOT 4: load vs time (aligned to ramp start) ============
pre_mean = mean(R[k]["anchor"] for k in KEYS)       # preload (true force at ramp start)
peak_mean = mean(R[k]["uts_F"] for k in KEYS)
pk_lo = min(R[k]["uts_F"] for k in KEYS); pk_hi = max(R[k]["uts_F"] for k in KEYS)
dF = peak_mean - pre_mean
fig, ax = plt.subplots(figsize=(12, 6.3))
for k in KEYS:
    ax.plot(R[k]["lt_t"], R[k]["lt_F"], "-", color=COLORS[k], lw=2.0, alpha=0.9,
            label=f"{k}: preload {R[k]['anchor']:.0f} N → peak {R[k]['uts_F']:.0f} N")
    ax.plot(R[k]["uts_ts"], R[k]["uts_Fp"], "v", color=COLORS[k], ms=11, mec="black", mew=0.6)
# reference levels: peak (all three align here) and preload
ax.axhline(peak_mean, color="#d62728", ls="--", lw=1.3, alpha=0.8)
ax.axhline(pre_mean, color="#555", ls=":", lw=1.3, alpha=0.8)
ax.text(20, peak_mean+28, f"peak force {pk_lo:.0f}–{pk_hi:.0f} N  (spread {(pk_hi-pk_lo)/peak_mean*100:.1f} %)",
        fontsize=11, color="#d62728", fontweight="bold")
ax.text(0.4, pre_mean+28, f"preload ≈ {pre_mean:.0f} N", fontsize=11, color="#333")
# preload -> peak delta (net pull) double arrow in clear space at right
xa = 44.5
ax.annotate("", xy=(xa, peak_mean), xytext=(xa, pre_mean),
            arrowprops=dict(arrowstyle="<->", color="#7b1fa2", lw=2.4))
ax.text(xa-0.6, (peak_mean+pre_mean)/2,
        f"Δ = {dF:.0f} N\nnet pull\n(peak − preload)", fontsize=11, color="#7b1fa2",
        fontweight="bold", ha="right", va="center")
ax.text(15, 250, "Peaks align at ~1763 N. V5c (S2) holds the plateau ~10 s longer → more ductile.",
        fontsize=11, color="#444", bbox=dict(facecolor="#E7F1F8", edgecolor="none", boxstyle="round,pad=0.4"))
ax.set_xlabel("Time from ramp start (s)"); ax.set_ylabel("True force (N)")
ax.set_title("V5 / V5b / V5c — load vs time (aligned to ramp start, 0.1 mm/s)", fontweight="bold")
ax.grid(alpha=0.3); ax.legend(loc="upper left", fontsize=10.5)
ax.set_xlim(-1, 52); ax.set_ylim(-120, 1980)
plt.tight_layout(); plt.savefig("images/V5/V5abc_load_time.png", dpi=150, bbox_inches="tight"); plt.close()

# ============ PLOT 5: stress vs crosshead displacement ============
fig, ax = plt.subplots(figsize=(12, 6.3))
for k in KEYS:
    ax.plot(R[k]["xs_pos"], R[k]["ys"], "-", color=COLORS[k], lw=2.2, alpha=0.9,
            label=f"{k}: travel {R[k]['travel_fr']:.2f} mm, gauge share {R[k]['gauge_share']:.0f} %")
ax.set_xlabel("Crosshead displacement / travel (mm)"); ax.set_ylabel("Engineering stress (MPa, nominal 80 mm²)")
ax.set_title("V5 / V5b / V5c — stress vs crosshead displacement", fontweight="bold")
ax.grid(alpha=0.3); ax.legend(loc="lower right", fontsize=11)
ax.set_xlim(-0.05, 5.2); ax.set_ylim(0, 24)
plt.tight_layout(); plt.savefig("images/V5/V5abc_stress_disp.png", dpi=150, bbox_inches="tight"); plt.close()

# ============ PLOT 6: Cauchy strain vs crosshead displacement ============
fig, ax = plt.subplots(figsize=(12, 6.3))
for k in KEYS:
    ax.plot(R[k]["xs_pos"], R[k]["xs"], "-", color=COLORS[k], lw=2.2, alpha=0.9,
            label=f"{k}: ε_f {R[k]['ef']:.4f} at {R[k]['travel_fr']:.2f} mm travel")
    # reference line: slope = 1/gauge if all travel went to gauge (no rig compliance)
ax.plot([0, 5], [0, 5/GAUGE], "k:", lw=1.2, alpha=0.6, label="ideal: all travel → gauge (slope 1/80 mm)")
ax.set_xlabel("Crosshead displacement / travel (mm)"); ax.set_ylabel("DIC Cauchy strain ε_c")
ax.set_title("V5 / V5b / V5c — gauge strain vs crosshead displacement", fontweight="bold")
ax.grid(alpha=0.3); ax.legend(loc="upper left", fontsize=11)
ax.set_xlim(-0.05, 5.2); ax.set_ylim(-0.001, 0.034)
plt.tight_layout(); plt.savefig("images/V5/V5abc_strain_disp.png", dpi=150, bbox_inches="tight"); plt.close()

print("\nSaved plots: V5abc_stress_strain.png, V5abc_bars.png, V5abc_offset.png,")
print("             V5abc_load_time.png, V5abc_stress_disp.png, V5abc_strain_disp.png")
