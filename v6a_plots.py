"""Plots for the V6a (S7, 100% infill, LED on) deck + V6a-vs-V5 comparison overlays.
Self-contained (same analyze() as v6a_analyze.py). Generates:
  single : V6a_load_time / stress_strain / cauchy_true / stress_position / strain_position .png
  compare: V6a_v5_load_time / stress_strain / stress_disp / strain_disp .png
"""
import sys
sys.stdout.reconfigure(encoding="utf-8")
from statistics import mean, median
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

AREA = 80.0; GAUGE = 80.0
ROOT = r"Software\UTM_PyQt6\8.6.20 - Tensile test to Failure"
F_V5 = ROOT + r"\Specimen_S4_V1_Spray\UTM_Test_20260612_172333_V5_TensionFailure.csv"
F_V6 = ROOT + r"\Specimen_S7_V2_Spray\UTM_Test_20260617_165405_V6a_TensionFailure.csv"      # pilot (batch edge)
F_V6D = ROOT + r"\Specimen_S11_V2_Spray\UTM_Test_20260625_154219_V6d_TensionFailure.csv"    # representative (≈ n=5 mean)
BLUE = "#1f77b4"; RED = "#d62728"; PUR = "#6a1b9a"; ORANGE = "#e08214"; GREEN = "#2e7d32"


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
    return sl, ic


def analyze(path):
    data = read_csv(path)
    base_pos = sorted(d["pos"] for d in data[:30])[15]
    mv_i = next(i for i, d in enumerate(data) if d["pos"] > base_pos + 0.005)
    t0 = data[mv_i]["t"]
    L0 = sorted(d["lpx"] for d in data[:mv_i] if d["lpx"] > 100)
    L0px = L0[len(L0)//2]
    ec0_list = [d["ec"] for d in data[:mv_i] if d["lpx"] > 100]
    ec0 = median(ec0_list) if ec0_list else 0.0
    fr_lpx = next((i for i in range(mv_i, len(data))
                   if data[i]["lpx"] > 100 and data[i]["lpx"] > 1.06*L0px), None)
    if fr_lpx is not None:
        fr_i = fr_lpx
    else:
        pk = max(range(mv_i, len(data)), key=lambda i: data[i]["F"])
        fr_i = next((i for i in range(pk, len(data)) if data[i]["F"] < 0.5*data[pk]["F"]), len(data)-1)
    t_fr = data[fr_i]["t"]
    pre = data[:fr_i]
    post = [d for d in data[fr_i+1:] if d["t"] > t_fr+2.0 and d["lpx"] > 100]
    if not post:                       # DIC fully dropped out post-fracture (V6a) → use force only
        post = [d for d in data[fr_i+1:] if d["t"] > t_fr+2.0]
    anchor = -mean(d["F"] for d in post)
    for d in data:
        d["sig"] = (d["F"]+anchor)/AREA
        d["Ftrue"] = d["F"]+anchor
        d["ecz"] = d["ec"]-ec0
        d["etz"] = d["et"]-ec0
        d["travel"] = d["pos"]-base_pos
    test = [d for d in pre[mv_i:] if d["lpx"] > 100]
    uts = max(test, key=lambda d: d["sig"])
    last = max(test, key=lambda d: d["t"])
    win = [d for d in test if 0.0005 <= d["ecz"] <= 0.004]
    E, c1 = linfit([d["ecz"] for d in win], [d["sig"] for d in win])
    sy = next(d for d in test if E*(d["ecz"]-0.002)+c1 >= d["sig"])
    pl = next((d for d in test if d["ecz"] > 0.004 and d["sig"] < 0.98*(E*d["ecz"]+c1)), None)
    gauge = last["ecz"]*GAUGE; rig = last["travel"]-gauge
    return {"E": E, "c1": c1, "anchor": anchor, "uts": uts, "last": last, "sy": sy, "pl": pl,
            "test": test, "t0": t0, "fr_i": fr_i, "mv_i": mv_i, "data": data, "L0px": L0px,
            "gauge": gauge, "rig": rig, "rig_k": uts["Ftrue"]/rig, "gshare": gauge/last["travel"]*100,
            "lt_t": [d["t"]-t0 for d in data[mv_i:min(fr_i+14, len(data))]],
            "lt_F": [d["Ftrue"] for d in data[mv_i:min(fr_i+14, len(data))]],
            "uts_ts": uts["t"]-t0}


A = analyze(F_V6)          # V6a (pilot) — used for the single-specimen deep-dive plots
B = analyze(F_V5)          # V5
A6 = analyze(F_V6D)        # V6d — representative 100% (≈ n=5 mean) for the V6-vs-V5 comparison
test, uts, last, sy, pl = A["test"], A["uts"], A["last"], A["sy"], A["pl"]
E, c1 = A["E"], A["c1"]
plt.rcParams.update({"font.size": 13})

# ===== PLOT 1: V6a load vs time =====
pre_F = A["anchor"]; pk_F = uts["Ftrue"]; dF = pk_F - pre_F
fig, ax = plt.subplots(figsize=(12.5, 6.2))
ax.plot(A["lt_t"], A["lt_F"], "-", color=BLUE, lw=2.4)
ax.axhline(pk_F, color=RED, ls="--", lw=1.3, alpha=0.8)
ax.axhline(pre_F, color="#555", ls=":", lw=1.3, alpha=0.8)
ax.plot(A["uts_ts"], pk_F, "v", color=RED, ms=14, mec="black", mew=0.6, label=f"UTS {pk_F:.0f} N")
ax.text(2, pk_F+70, f"peak {pk_F:.0f} N (47.8 MPa)", color=RED, fontweight="bold", fontsize=12)
ax.text(2, pre_F+70, f"preload {pre_F:.0f} N", color="#333", fontsize=11)
xa = A["lt_t"][-1]-2
ax.annotate("", xy=(xa, pk_F), xytext=(xa, pre_F), arrowprops=dict(arrowstyle="<->", color=PUR, lw=2.4))
ax.text(xa-1.5, (pk_F+pre_F)/2, f"Δ = {dF:.0f} N\nnet pull", color=PUR, fontweight="bold", ha="right", va="center", fontsize=11)
ax.set_xlabel("Time from ramp start (s)"); ax.set_ylabel("True force (N)")
ax.set_title("8.6.20 V6a — load vs time (100 % infill, 0.1 mm/s)", fontweight="bold")
ax.grid(alpha=0.3); ax.legend(loc="lower right", fontsize=11)
ax.text(20, 700, "Long ductile pull (73 s): rises to UTS then softens ~7 %\nover a wide plastic plateau before fracture.",
        fontsize=11, color="#444", bbox=dict(facecolor="#E7F1F8", edgecolor="none", boxstyle="round,pad=0.4"))
plt.tight_layout(); plt.savefig("V6a_load_time.png", dpi=150, bbox_inches="tight"); plt.close()

# ===== PLOT 2: V6a stress-strain with 4 regions + 0.2% offset =====
fig, ax = plt.subplots(figsize=(11.5, 6.6))
xs = [d["ecz"] for d in test]; ys = [d["sig"] for d in test]
e_pl = pl["ecz"] if pl else sy["ecz"]; e_sy = sy["ecz"]; e_uts = uts["ecz"]; e_f = last["ecz"]
ax.axvspan(0, e_pl, color="#cfe8ff", alpha=0.5)
ax.axvspan(e_pl, e_uts, color="#fff3cd", alpha=0.6)
ax.axvspan(e_uts, e_f*1.04, color="#ffd9b3", alpha=0.5)
ax.plot(xs, ys, "-", color=BLUE, lw=2.6)
xx = [0, e_sy+0.004]
ax.plot(xx, [E*(x-0.002)+c1 for x in xx], "--", color="gray", lw=1.4, label="0.2 % offset line")
ax.plot(sy["ecz"], sy["sig"], "o", color=GREEN, ms=11, label=f"σ_y(0.2%) {sy['sig']:.1f} MPa")
ax.plot(uts["ecz"], uts["sig"], "v", color=RED, ms=13, mec="black", mew=0.6, label=f"UTS {uts['sig']:.1f} MPa")
ax.plot(last["ecz"], last["sig"], "x", color="black", ms=13, mew=3, label=f"fracture ε_f={last['ecz']:.4f}")
ymid = uts["sig"]*0.5
ax.text(e_pl/2, ymid, "I\nelastic", ha="center", fontsize=11, color="#1f5fa0", fontweight="bold")
ax.text((e_pl+e_uts)/2, ymid, "II–III\nyield→UTS", ha="center", fontsize=10.5, color="#8a6d00", fontweight="bold")
ax.text((e_uts+e_f)/2, ymid, "IV\nsoftening", ha="center", fontsize=11, color="#a0521a", fontweight="bold")
ax.set_xlabel("DIC Cauchy strain ε_c"); ax.set_ylabel("True stress (MPa, nominal 80 mm²)")
ax.set_title("8.6.20 V6a — stress–strain (100 % infill): E = 2.41 GPa", fontweight="bold")
ax.grid(alpha=0.3); ax.legend(loc="lower right", fontsize=10.5)
ax.set_xlim(-0.001, e_f*1.07); ax.set_ylim(0, uts["sig"]*1.12)
plt.tight_layout(); plt.savefig("V6a_stress_strain.png", dpi=150, bbox_inches="tight"); plt.close()

# ===== PLOT 3: V6a Cauchy vs True strain =====
fig, ax = plt.subplots(figsize=(11.5, 6.4))
ax.plot([d["ecz"] for d in test], ys, "-", color=BLUE, lw=2.4, label="vs Cauchy ε_c")
ax.plot([d["etz"] for d in test], ys, "-", color=ORANGE, lw=2.4, label="vs True ε_t = ln(1+ε_c)")
ax.plot(last["ecz"], last["sig"], "o", color=BLUE, ms=9); ax.plot(last["etz"], last["sig"], "o", color=ORANGE, ms=9)
ax.set_xlabel("DIC strain"); ax.set_ylabel("True stress (MPa)")
ax.set_title("8.6.20 V6a — Cauchy vs True strain", fontweight="bold")
ax.grid(alpha=0.3); ax.legend(loc="lower right", fontsize=11)
ax.text(0.004, uts["sig"]*0.9, f"At fracture: ε_c={last['ecz']:.4f}, ε_t={last['etz']:.4f}\n"
        f"(<0.5 % apart — strains small, conventions agree)", fontsize=11, color="#444",
        bbox=dict(facecolor="#fff7e6", edgecolor="none", boxstyle="round,pad=0.4"))
plt.tight_layout(); plt.savefig("V6a_cauchy_true.png", dpi=150, bbox_inches="tight"); plt.close()

# ===== PLOT 4: V6a stress vs crosshead position (gauge/rig split) =====
fig, ax = plt.subplots(figsize=(11.5, 6.4))
ax.plot([d["travel"] for d in test], ys, "-", color=BLUE, lw=2.4)
ax.plot(uts["travel"], uts["sig"], "v", color=RED, ms=13, mec="black", mew=0.6, label=f"UTS at {uts['travel']:.2f} mm")
ax.plot(last["travel"], last["sig"], "x", color="black", ms=13, mew=3, label=f"fracture at {last['travel']:.2f} mm")
ax.set_xlabel("Crosshead displacement / travel (mm)"); ax.set_ylabel("True stress (MPa)")
ax.set_title("8.6.20 V6a — stress vs crosshead position", fontweight="bold")
ax.grid(alpha=0.3); ax.legend(loc="lower right", fontsize=11)
ax.text(0.2, uts["sig"]*0.55,
        f"Crosshead moved {last['travel']:.2f} mm; gauge stretched only {A['gauge']:.2f} mm "
        f"({A['gshare']:.0f} %).\nRig/grip take-up {A['rig']:.2f} mm → rig stiffness "
        f"{A['rig_k']:.0f} N/mm.\nHigher force (3.8 kN) ⇒ ~2.7× the rig deflection of V5.",
        fontsize=11, color="#444", bbox=dict(facecolor="#E7F1F8", edgecolor="none", boxstyle="round,pad=0.4"))
plt.tight_layout(); plt.savefig("V6a_stress_position.png", dpi=150, bbox_inches="tight"); plt.close()

# ===== PLOT 5: V6a gauge strain vs crosshead position =====
fig, ax = plt.subplots(figsize=(12.5, 6.2))
ax.plot([d["travel"] for d in test], [d["ecz"] for d in test], "-", color=BLUE, lw=2.6, label="V6a gauge strain ε_c (DIC)")
ax.plot([0, last["travel"]*1.02], [0, last["travel"]*1.02/GAUGE], ":", color="#555", lw=1.4, label="ideal: all travel → gauge (slope 1/80)")
ax.plot(uts["travel"], uts["ecz"], "v", color=RED, ms=14, label=f"UTS at {uts['travel']:.2f} mm")
ax.plot(last["travel"], last["ecz"], "x", color="black", ms=14, mew=3, label=f"fracture ε_f={last['ecz']:.4f}")
ax.set_xlabel("Crosshead displacement / travel (mm)"); ax.set_ylabel("DIC Cauchy strain ε_c")
ax.set_title("8.6.20 V6a — gauge strain vs crosshead displacement", fontweight="bold")
ax.grid(alpha=0.3); ax.legend(loc="upper left", fontsize=10.5)
ax.text(2.7, 0.004, f"At fracture: {last['travel']:.2f} mm travel → only {A['gauge']:.2f} mm "
        f"({A['gshare']:.0f} %) stretches the gauge;\nthe rest ({A['rig']:.2f} mm) is rig/grip take-up "
        f"(more than V5: higher force, more compliance).", fontsize=10.5, color="#444",
        bbox=dict(facecolor="#E7F1F8", edgecolor="none", boxstyle="round,pad=0.4"))
plt.tight_layout(); plt.savefig("V6a_strain_position.png", dpi=150, bbox_inches="tight"); plt.close()

# ============ COMPARISON V6a vs V5 ============
def ss(d): return [x["ecz"] for x in d["test"]], [x["sig"] for x in d["test"]]
def sp(d): return [x["travel"] for x in d["test"]], [x["sig"] for x in d["test"]]
def ep(d): return [x["travel"] for x in d["test"]], [x["ecz"] for x in d["test"]]

# C1: load vs time
fig, ax = plt.subplots(figsize=(12, 6.3))
ax.plot(B["lt_t"], B["lt_F"], "-", color=BLUE, lw=2.3, label=f"V5 (50 % infill): peak {B['uts']['Ftrue']:.0f} N")
ax.plot(A6["lt_t"], A6["lt_F"], "-", color=RED, lw=2.3, label=f"V6 (100 % infill): peak {A6['uts']['Ftrue']:.0f} N")
ax.plot(B["uts_ts"], B["uts"]["Ftrue"], "v", color=BLUE, ms=11, mec="black", mew=0.6)
ax.plot(A6["uts_ts"], A6["uts"]["Ftrue"], "v", color=RED, ms=11, mec="black", mew=0.6)
ax.set_xlabel("Time from ramp start (s)"); ax.set_ylabel("True force (N)")
ax.set_title("V6 (100 % infill) vs V5 (50 % infill) — load vs time (both 0.1 mm/s)", fontweight="bold")
ax.grid(alpha=0.3); ax.legend(loc="center right", fontsize=12)
ax.text(3, 3200, "100 % infill carries ≈2.1× the peak force\n(batch mean 3697 vs 1767 N) and sustains a longer pull.",
        fontsize=11, color="#444", bbox=dict(facecolor="#fdecea", edgecolor="none", boxstyle="round,pad=0.4"))
ax.text(3, 2720, "V6 = representative specimen V6d  (≈ n = 5 mean)", fontsize=9.5, color="#777", style="italic")
plt.tight_layout(); plt.savefig("V6a_v5_load_time.png", dpi=150, bbox_inches="tight"); plt.close()

# C2: stress-strain
fig, ax = plt.subplots(figsize=(12, 6.5))
x5, y5 = ss(B); x6, y6 = ss(A6)
ax.plot(x5, y5, "-", color=BLUE, lw=2.4, label="V5 (50 % infill): UTS 22.1 MPa")
ax.plot(x6, y6, "-", color=RED, lw=2.4, label=f"V6 (100 % infill): UTS {A6['uts']['sig']:.1f} MPa")
ax.plot(B["uts"]["ecz"], B["uts"]["sig"], "v", color=BLUE, ms=11, mec="black", mew=0.6)
ax.plot(A6["uts"]["ecz"], A6["uts"]["sig"], "v", color=RED, ms=11, mec="black", mew=0.6)
ax.plot(B["last"]["ecz"], B["last"]["sig"], "x", color=BLUE, ms=12, mew=2.6)
ax.plot(A6["last"]["ecz"], A6["last"]["sig"], "x", color=RED, ms=12, mew=2.6)
ax.set_xlabel("DIC Cauchy strain ε_c"); ax.set_ylabel("True stress (MPa, nominal 80 mm²)")
ax.set_title("V6 (100 % infill) vs V5 (50 % infill) — stress–strain", fontweight="bold")
ax.grid(alpha=0.3); ax.legend(loc="center right", fontsize=12)
ax.text(0.006, 12, "Same nominal area (80 mm²). 100 % infill is ~2× stronger\n& ~1.7× stiffer; the 100 % batch is also more extensible (ε_f 3–7 %).",
        fontsize=11, color="#444", bbox=dict(facecolor="#fdecea", edgecolor="none", boxstyle="round,pad=0.4"))
ax.set_xlim(-0.001, 0.056); ax.set_ylim(0, 52)
plt.tight_layout(); plt.savefig("V6a_v5_stress_strain.png", dpi=150, bbox_inches="tight"); plt.close()

# C3: stress vs displacement
fig, ax = plt.subplots(figsize=(12, 6.3))
x5, y5 = sp(B); x6, y6 = sp(A6)
ax.plot(x5, y5, "-", color=BLUE, lw=2.4, label=f"V5 (50 % infill): gauge share {B['gshare']:.0f} %")
ax.plot(x6, y6, "-", color=RED, lw=2.4, label=f"V6 (100 % infill): gauge share {A6['gshare']:.0f} %")
ax.set_xlabel("Crosshead displacement / travel (mm)"); ax.set_ylabel("True stress (MPa)")
ax.set_title("V6 (100 % infill) vs V5 (50 % infill) — stress vs crosshead displacement", fontweight="bold")
ax.grid(alpha=0.3); ax.legend(loc="center right", fontsize=12)
ax.text(0.2, 30, "100 % infill needs ~2× the travel (7.3 vs 3.8 mm) to fracture —\nhigher force AND ~2× the gauge stretch — but reaches a\nSIMILAR gauge share (55 % vs 52 %).", fontsize=11, color="#444",
        bbox=dict(facecolor="#fdecea", edgecolor="none", boxstyle="round,pad=0.4"))
plt.tight_layout(); plt.savefig("V6a_v5_stress_disp.png", dpi=150, bbox_inches="tight"); plt.close()

# C4: Cauchy strain vs displacement
fig, ax = plt.subplots(figsize=(12, 6.3))
x5, y5 = ep(B); x6, y6 = ep(A6)
ax.plot(x5, y5, "-", color=BLUE, lw=2.4, label="V5 (50 % infill)")
ax.plot(x6, y6, "-", color=RED, lw=2.4, label="V6 (100 % infill)")
mt = max(B["last"]["travel"], A6["last"]["travel"])*1.02
ax.plot([0, mt], [0, mt/GAUGE], ":", color="#555", lw=1.4, label="ideal: all travel → gauge")
ax.set_xlabel("Crosshead displacement / travel (mm)"); ax.set_ylabel("DIC Cauchy strain ε_c")
ax.set_title("V6 (100 % infill) vs V5 (50 % infill) — gauge strain vs crosshead displacement", fontweight="bold")
ax.grid(alpha=0.3); ax.legend(loc="upper left", fontsize=12)
ax.text(2.8, 0.004, "Both sit below the ideal line (rig compliance) with SIMILAR slopes —\n~half the travel reaches the gauge in both (gauge share 55 % vs 52 %).\n100 % just travels further (stronger + more extensible).", fontsize=10.5, color="#444",
        bbox=dict(facecolor="#fdecea", edgecolor="none", boxstyle="round,pad=0.4"))
plt.tight_layout(); plt.savefig("V6a_v5_strain_disp.png", dpi=150, bbox_inches="tight"); plt.close()

print("Saved 9 plots: V6a_load_time/stress_strain/cauchy_true/stress_position/strain_position,")
print("               V6a_v5_load_time/stress_strain/stress_disp/strain_disp")
